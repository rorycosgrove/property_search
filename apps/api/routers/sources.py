"""Source management endpoints."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from packages.shared.schemas import SourceCreate, SourceUpdate
from packages.sources.discovery import canonicalize_source_url, load_discovery_candidates
from packages.sources.registry import get_adapter_names, list_adapters
from packages.storage.database import get_db_session
from packages.storage.repositories import OrganicSearchRunRepository, SourceRepository

router = APIRouter()


def _merge_tags(existing: list[str] | None, additions: list[str]) -> list[str]:
    seen: set[str] = set()
    merged: list[str] = []
    for value in (existing or []) + additions:
        if value and value not in seen:
            seen.add(value)
            merged.append(value)
    return merged


@router.get("")
def list_sources(db: Session = Depends(get_db_session)):
    """List all configured sources."""
    repo = SourceRepository(db)
    sources = repo.get_all()
    return [_to_dict(s) for s in sources]


@router.post("", status_code=201)
def create_source(data: SourceCreate, db: Session = Depends(get_db_session)):
    """Create a new source configuration."""
    repo = SourceRepository(db)

    # Validate adapter name
    if data.adapter_name not in get_adapter_names():
        raise HTTPException(400, f"Unknown adapter: {data.adapter_name}")

    existing = repo.get_by_url(data.url)
    if existing:
        raise HTTPException(409, "Source with this URL already exists")

    source = repo.create(
        name=data.name,
        url=data.url,
        adapter_type=data.adapter_type,
        adapter_name=data.adapter_name,
        config=data.config or {},
        enabled=data.enabled,
        poll_interval_seconds=data.poll_interval_seconds,
        tags=data.tags or [],
    )
    return _to_dict(source)


@router.get("/adapters")
def list_available_adapters():
    """List all available source adapters with their config schemas."""
    return [a.model_dump() for a in list_adapters()]


@router.get("/{source_id}")
def get_source(source_id: str, db: Session = Depends(get_db_session)):
    """Get a single source by ID."""
    repo = SourceRepository(db)
    source = repo.get_by_id(source_id)
    if not source:
        raise HTTPException(404, "Source not found")
    return _to_dict(source)


@router.patch("/{source_id}")
def update_source(source_id: str, data: SourceUpdate, db: Session = Depends(get_db_session)):
    """Update a source configuration."""
    repo = SourceRepository(db)
    source = repo.get_by_id(source_id)
    if not source:
        raise HTTPException(404, "Source not found")

    updates = data.model_dump(exclude_unset=True)
    updated = repo.update(source_id, **updates)
    return _to_dict(updated)


@router.delete("/{source_id}", status_code=204)
def delete_source(source_id: str, db: Session = Depends(get_db_session)):
    """Delete a source."""
    repo = SourceRepository(db)
    if not repo.get_by_id(source_id):
        raise HTTPException(404, "Source not found")
    repo.delete(source_id)


@router.post("/{source_id}/trigger")
def trigger_scrape(
    source_id: str,
    force: bool = Query(False, description="Bypass poll interval and force immediate scrape"),
    db: Session = Depends(get_db_session),
):
    """Manually trigger a scrape for a source."""
    repo = SourceRepository(db)
    source = repo.get_by_id(source_id)
    if not source:
        raise HTTPException(404, "Source not found")

    from apps.worker.tasks import scrape_source
    from packages.shared.queue import send_task

    try:
        message_id = send_task("scrape", "scrape_source", {"source_id": source_id, "force": force})
        return {"task_id": message_id, "status": "dispatched", "force": force}
    except Exception:
        result = scrape_source(source_id, force=force)
        return {"status": "processed_inline", "result": result, "force": force}


@router.post("/trigger-all")
def trigger_full_organic_search(
    force: bool = Query(False, description="Bypass source poll intervals for this run"),
    run_alerts: bool = Query(True, description="Trigger alert evaluation after scrape"),
    run_llm_batch: bool = Query(True, description="Trigger LLM enrichment batch"),
    llm_limit: int = Query(50, ge=1, le=500, description="Max properties to enrich"),
    db: Session = Depends(get_db_session),
):
    """Trigger the full organic search pipeline.

    Steps:
    1) scrape_all_sources
    2) evaluate_alerts (optional)
    3) enrich_batch_llm (optional)
    """
    from apps.worker.tasks import enrich_batch_llm, evaluate_alerts, scrape_all_sources
    from packages.shared.queue import send_task

    steps: list[dict] = []
    run_repo = OrganicSearchRunRepository(db)

    def _dispatch_or_inline(queue_type: str, task_type: str, payload: dict, inline_fn):
        try:
            task_id = send_task(queue_type, task_type, payload)
            return {
                "step": task_type,
                "status": "dispatched",
                "task_id": task_id,
            }
        except Exception:
            result = inline_fn(**payload)
            return {
                "step": task_type,
                "status": "processed_inline",
                "result": result,
            }

    steps.append(_dispatch_or_inline("scrape", "scrape_all_sources", {"force": force}, scrape_all_sources))

    if run_alerts:
        steps.append(_dispatch_or_inline("alert", "evaluate_alerts", {}, evaluate_alerts))

    if run_llm_batch:
        steps.append(_dispatch_or_inline("llm", "enrich_batch_llm", {"limit": llm_limit}, enrich_batch_llm))

    statuses = {s["status"] for s in steps}
    if statuses == {"dispatched"}:
        status = "dispatched"
    elif statuses == {"processed_inline"}:
        status = "processed_inline"
    else:
        status = "mixed"

    run = run_repo.create(
        status=status,
        triggered_from="api_sources_trigger_all",
        options={
            "force": force,
            "run_alerts": run_alerts,
            "run_llm_batch": run_llm_batch,
            "llm_limit": llm_limit,
        },
        steps=steps,
    )

    return {
        "run_id": str(run.id),
        "status": status,
        "steps": steps,
    }


@router.post("/discover-auto")
def discover_sources_auto(
    auto_enable: bool = Query(True, description="Enable discovered sources immediately"),
    limit: int = Query(25, ge=1, le=200),
    db: Session = Depends(get_db_session),
):
    """Auto-discover known feed/source candidates and add missing ones.

    By default discovered sources are created disabled with `pending_approval` tag.
    """
    repo = SourceRepository(db)
    adapter_names = set(get_adapter_names())
    created = []
    existing = []
    skipped_invalid = []
    existing_sources = repo.get_all(enabled_only=False)
    existing_by_canonical = {
        canonicalize_source_url(str(s.url or "")): s
        for s in existing_sources
        if canonicalize_source_url(str(s.url or ""))
    }

    for candidate in load_discovery_candidates()[:limit]:
        adapter_name = candidate.get("adapter_name")
        url = candidate.get("url")
        canonical_url = canonicalize_source_url(str(url or ""))
        if adapter_name not in adapter_names or not url or not canonical_url:
            skipped_invalid.append({"url": url, "reason": "unknown_adapter_or_missing_url"})
            continue

        current = existing_by_canonical.get(canonical_url)
        if current:
            existing.append({"id": str(current.id), "url": current.url, "name": current.name})
            continue

        tags = _merge_tags(
            candidate.get("tags", []),
            ["auto_discovered"] + ([] if auto_enable else ["pending_approval"]),
        )
        source = repo.create(
            name=candidate.get("name") or f"Discovered {adapter_name}",
            url=url,
            adapter_type=candidate.get("adapter_type") or "scraper",
            adapter_name=adapter_name,
            config=candidate.get("config") or {},
            enabled=auto_enable,
            poll_interval_seconds=int(candidate.get("poll_interval_seconds") or 21600),
            tags=tags,
        )
        existing_by_canonical[canonical_url] = source
        created.append(_to_dict(source))

    return {
        "run_at": datetime.now(UTC).isoformat(),
        "created": created,
        "existing": existing,
        "skipped_invalid": skipped_invalid,
        "auto_enable": auto_enable,
    }


@router.get("/discovery/pending")
def list_pending_discovered_sources(db: Session = Depends(get_db_session)):
    """List auto-discovered sources awaiting manual approval."""
    repo = SourceRepository(db)
    pending = [
        s for s in repo.get_all() if isinstance(s.tags, list) and "pending_approval" in s.tags
    ]
    return [_to_dict(s) for s in pending]


@router.post("/{source_id}/approve-discovered")
def approve_discovered_source(source_id: str, db: Session = Depends(get_db_session)):
    """Approve a pending auto-discovered source and enable it."""
    repo = SourceRepository(db)
    source = repo.get_by_id(source_id)
    if not source:
        raise HTTPException(404, "Source not found")

    if not isinstance(source.tags, list):
        source.tags = []

    source.tags = [tag for tag in source.tags if tag != "pending_approval"]
    source.enabled = True
    updated = repo.update(source_id, tags=source.tags, enabled=True)
    return _to_dict(updated)


@router.get("/trigger-all/history")
def list_full_organic_search_history(
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db_session),
):
    """List recent full organic search trigger runs."""
    run_repo = OrganicSearchRunRepository(db)
    runs = run_repo.list_recent(limit=limit)
    return [_organic_run_to_dict(r) for r in runs]


def _to_dict(source) -> dict:
    return {
        "id": str(source.id),
        "name": source.name,
        "url": source.url,
        "adapter_type": source.adapter_type,
        "adapter_name": source.adapter_name,
        "config": source.config,
        "enabled": source.enabled,
        "poll_interval_seconds": source.poll_interval_seconds,
        "tags": source.tags,
        "last_polled_at": source.last_polled_at.isoformat() if source.last_polled_at else None,
        "last_success_at": source.last_success_at.isoformat() if source.last_success_at else None,
        "last_error": source.last_error,
        "error_count": source.error_count,
        "total_listings": source.total_listings,
        "created_at": source.created_at.isoformat() if source.created_at else None,
        "updated_at": source.updated_at.isoformat() if source.updated_at else None,
    }


def _organic_run_to_dict(run) -> dict:
    return {
        "id": str(run.id),
        "status": run.status,
        "triggered_from": run.triggered_from,
        "options": run.options or {},
        "steps": run.steps or [],
        "error": run.error,
        "created_at": run.created_at.isoformat() if run.created_at else None,
    }
