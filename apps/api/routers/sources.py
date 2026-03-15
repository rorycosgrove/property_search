"""Source management endpoints."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from packages.shared.schemas import SourceCreate, SourceUpdate
from packages.sources.discovery import canonicalize_source_url, load_discovery_candidates
from packages.sources.registry import get_adapter, get_adapter_names, list_adapters
from packages.storage.database import get_db_session
from packages.storage.models import BackendLog
from packages.storage.repositories import OrganicSearchRunRepository, SourceRepository
from packages.shared.queue import QueueDispatchError, dispatch_or_inline

router = APIRouter()


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _record_backend_event(
    db: Session,
    *,
    event_type: str,
    message: str,
    level: str = "INFO",
    source_id: str | None = None,
    context: dict | None = None,
) -> None:
    db.add(
        BackendLog(
            level=level,
            event_type=event_type,
            component="api.sources",
            source_id=source_id,
            message=message,
            context_json=context or {},
        )
    )


def _validate_source_config(adapter_name: str, config: dict | None) -> None:
    try:
        adapter = get_adapter(adapter_name)
    except KeyError as exc:
        raise HTTPException(400, f"Unknown adapter: {adapter_name}") from exc

    errors = adapter.validate_config(config or {})
    if errors:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "invalid_source_config",
                "adapter_name": adapter_name,
                "errors": errors,
            },
        )

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

    _validate_source_config(data.adapter_name, data.config)

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
    if "config" in updates:
        _validate_source_config(source.adapter_name, updates.get("config") or {})
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
    timestamp = _now_iso()

    try:
        dispatch_result = dispatch_or_inline(
            "scrape",
            "scrape_source",
            {"source_id": source_id, "force": force},
            scrape_source,
        )
        _record_backend_event(
            db,
            event_type="source_scrape_triggered",
            message="Manual source scrape triggered",
            source_id=source_id,
            context={"force": force, "status": dispatch_result.get("status"), "timestamp": timestamp},
        )
        return {**dispatch_result, "force": force, "timestamp": timestamp}
    except QueueDispatchError as exc:
        raise HTTPException(
            status_code=503,
            detail={
                "code": "scrape_dispatch_failed",
                "message": "Failed to dispatch scrape task to queue.",
                "error": str(exc)[:300],
            },
        ) from exc


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

    steps: list[dict] = []
    run_repo = OrganicSearchRunRepository(db)

    def _dispatch_or_inline(queue_type: str, task_type: str, payload: dict, inline_fn):
        timestamp = _now_iso()
        try:
            dispatch_result = dispatch_or_inline(queue_type, task_type, payload, inline_fn)
            return {
                "step": task_type,
                "timestamp": timestamp,
                **dispatch_result,
            }
        except QueueDispatchError as exc:
            raise HTTPException(
                status_code=503,
                detail={
                    "code": "pipeline_dispatch_failed",
                    "message": f"Failed to dispatch task '{task_type}' to queue.",
                    "task_type": task_type,
                    "error": str(exc)[:300],
                },
            ) from exc

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
    _record_backend_event(
        db,
        event_type="organic_search_triggered",
        message="Full organic search triggered",
        context={
            "status": status,
            "steps": steps,
            "options": {
                "force": force,
                "run_alerts": run_alerts,
                "run_llm_batch": run_llm_batch,
                "llm_limit": llm_limit,
            },
            "timestamp": _now_iso(),
        },
    )

    return {
        "run_id": str(run.id),
        "status": status,
        "steps": steps,
        "created_at": run.created_at.isoformat() if run.created_at else None,
    }


@router.post("/discover-auto")
def discover_sources_auto(
    auto_enable: bool = Query(False, description="Enable discovered sources immediately"),
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
    timestamp = _now_iso()
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
            skipped_invalid.append({"url": url, "reason": "unknown_adapter_or_missing_url", "timestamp": timestamp})
            continue

        adapter = get_adapter(adapter_name)
        config = candidate.get("config") or {}
        config_errors = adapter.validate_config(config)
        if config_errors:
            skipped_invalid.append(
                {
                    "url": url,
                    "reason": "invalid_adapter_config",
                    "errors": config_errors,
                    "timestamp": timestamp,
                }
            )
            continue

        current = existing_by_canonical.get(canonical_url)
        if current:
            existing.append({"id": str(current.id), "url": current.url, "name": current.name, "timestamp": timestamp})
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
            config=config,
            enabled=auto_enable,
            poll_interval_seconds=int(candidate.get("poll_interval_seconds") or 21600),
            tags=tags,
        )
        existing_by_canonical[canonical_url] = source
        created.append(_to_dict(source))

    _record_backend_event(
        db,
        event_type="source_discovery_manual_complete",
        message="Manual source discovery completed",
        context={
            "created": len(created),
            "existing": len(existing),
            "skipped_invalid": len(skipped_invalid),
            "auto_enable": auto_enable,
            "limit": limit,
            "timestamp": timestamp,
        },
    )

    return {
        "run_at": timestamp,
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
    _record_backend_event(
        db,
        event_type="source_discovered_approved",
        message="Discovered source approved",
        source_id=source_id,
        context={"timestamp": _now_iso(), "source_name": getattr(updated, "name", None)},
    )
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


@router.post("/discover-full")
def discover_sources_full(
    dry_run: bool = Query(False, description="Preview without writing to the database"),
    follow_links: bool = Query(False, description="Enable live HTTP crawl of seed pages (slower)"),
    limit: int = Query(200, ge=1, le=500, description="Maximum new sources to create"),
    include_grants: bool = Query(True, description="Also run grant program discovery"),
    db: Session = Depends(get_db_session),
):
    """Run the unified source + grant discovery crawler.

    Uses confidence scoring to auto-enable high-confidence sources (>= 0.70)
    and pend medium ones (0.40-0.69).  Sources below 0.40 are silently rejected.

    Set ``dry_run=true`` to preview what would be created without any DB writes.
    Set ``follow_links=true`` to enable live HTTP crawling of seed pages for
    additional source discovery (takes longer).
    """
    from apps.worker.tasks import discover_all_sources

    timestamp = _now_iso()

    try:
        result = dispatch_or_inline(
            "scrape",
            "discover_all_sources",
            {
                "limit": limit,
                "dry_run": dry_run,
                "follow_links": follow_links,
                "include_grants": include_grants,
            },
            lambda: discover_all_sources(
                limit=limit,
                dry_run=dry_run,
                follow_links=follow_links,
                include_grants=include_grants,
            ),
        )
    except QueueDispatchError as exc:
        raise HTTPException(
            status_code=503,
            detail={
                "code": "discovery_dispatch_failed",
                "message": "Failed to dispatch full discovery task to queue.",
                "error": str(exc)[:300],
            },
        ) from exc

    _record_backend_event(
        db,
        event_type="unified_discovery_triggered",
        message="Unified source + grant discovery triggered via API",
        context={
            "dry_run": dry_run,
            "follow_links": follow_links,
            "limit": limit,
            "include_grants": include_grants,
            "timestamp": timestamp,
            "status": result.get("status"),
        },
    )
    return result


@router.get("/discover-full/preview")
def preview_discovery_candidates(
    limit: int = Query(50, ge=1, le=500),
    min_score: float = Query(0.0, ge=0.0, le=1.0, description="Minimum confidence score filter"),
):
    """Preview discovery candidates with confidence scores (no DB writes).

    Useful for auditing what the crawler would discover before triggering a run.
    """
    from packages.sources.discovery import load_all_discovery_candidates

    scored = load_all_discovery_candidates(use_crawler=True, follow_links=False, reject_below=0.0)
    candidates = [
        {
            "name": sc.candidate.get("name"),
            "url": sc.candidate.get("url"),
            "adapter_name": sc.candidate.get("adapter_name"),
            "adapter_type": sc.candidate.get("adapter_type"),
            "score": sc.score,
            "activation": sc.activation,
            "reasons": sc.reasons,
            "tags": sc.candidate.get("tags", []),
        }
        for sc in scored
        if sc.score >= min_score
    ]
    return {
        "total": len(candidates),
        "shown": min(len(candidates), limit),
        "candidates": candidates[:limit],
    }
