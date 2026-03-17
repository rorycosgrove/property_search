"""Source management endpoints."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from packages.shared.schemas import SourceCreate, SourceUpdate
from packages.sources.discovery import load_all_discovery_candidates, load_discovery_candidates
from packages.sources.registry import get_adapter_names, list_adapters
from packages.sources.service import (
    SourceConfigValidationError,
    SourceDispatchFailedError,
    SourceNotFoundError,
    approve_discovered_source as approve_discovered_source_service,
    create_source as create_source_service,
    discover_sources_auto as discover_sources_auto_service,
    list_pending_discovered_sources as list_pending_discovered_sources_service,
    organic_run_to_dict,
    preview_discovery_candidates as preview_discovery_candidates_service,
    source_to_dict,
    trigger_full_discovery as trigger_full_discovery_service,
    trigger_full_organic_search as trigger_full_organic_search_service,
    trigger_source_scrape as trigger_source_scrape_service,
    update_source as update_source_service,
)
from packages.storage.database import get_db_session
from packages.storage.models import BackendLog
from packages.storage.repositories import OrganicSearchRunRepository, SourceRepository

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
@router.get("")
def list_sources(db: Session = Depends(get_db_session)):
    """List all configured sources."""
    repo = SourceRepository(db)
    sources = repo.get_all()
    return [source_to_dict(source) for source in sources]


@router.post("", status_code=201)
def create_source(data: SourceCreate, db: Session = Depends(get_db_session)):
    """Create a new source configuration."""
    repo = SourceRepository(db)
    try:
        return create_source_service(repo=repo, data=data, adapter_names=set(get_adapter_names()))
    except SourceConfigValidationError as exc:
        if len(exc.errors) == 1 and exc.errors[0] == f"unknown adapter: {data.adapter_name}":
            raise HTTPException(400, f"Unknown adapter: {data.adapter_name}") from exc
        raise HTTPException(
            status_code=400,
            detail={
                "code": "invalid_source_config",
                "adapter_name": exc.adapter_name,
                "errors": exc.errors,
            },
        ) from exc
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc


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
    return source_to_dict(source)


@router.patch("/{source_id}")
def update_source(source_id: str, data: SourceUpdate, db: Session = Depends(get_db_session)):
    """Update a source configuration."""
    repo = SourceRepository(db)
    try:
        return update_source_service(repo=repo, source_id=source_id, data=data)
    except SourceNotFoundError as exc:
        raise HTTPException(404, "Source not found") from exc
    except SourceConfigValidationError as exc:
        if len(exc.errors) == 1 and exc.errors[0] == f"unknown adapter: {exc.adapter_name}":
            raise HTTPException(400, f"Unknown adapter: {exc.adapter_name}") from exc
        raise HTTPException(
            status_code=400,
            detail={
                "code": "invalid_source_config",
                "adapter_name": exc.adapter_name,
                "errors": exc.errors,
            },
        ) from exc
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc


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
    try:
        return trigger_source_scrape_service(
            repo=repo,
            source_id=source_id,
            force=force,
            now_iso=_now_iso,
            record_event=lambda **kwargs: _record_backend_event(db, **kwargs),
        )
    except SourceNotFoundError as exc:
        raise HTTPException(404, "Source not found") from exc
    except SourceDispatchFailedError as exc:
        raise HTTPException(
            status_code=503,
            detail={
                "code": exc.code,
                "message": exc.message,
                "error": exc.error,
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
    run_repo = OrganicSearchRunRepository(db)
    try:
        return trigger_full_organic_search_service(
            run_repo=run_repo,
            force=force,
            run_alerts=run_alerts,
            run_llm_batch=run_llm_batch,
            llm_limit=llm_limit,
            now_iso=_now_iso,
            record_event=lambda **kwargs: _record_backend_event(db, **kwargs),
        )
    except SourceDispatchFailedError as exc:
        detail = {
            "code": exc.code,
            "message": exc.message,
            "error": exc.error,
        }
        if exc.task_type:
            detail["task_type"] = exc.task_type
        raise HTTPException(status_code=503, detail=detail) from exc


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
    return discover_sources_auto_service(
        repo=repo,
        auto_enable=auto_enable,
        limit=limit,
        adapter_names=set(get_adapter_names()),
        candidate_loader=load_discovery_candidates,
        now_iso=_now_iso,
        record_event=lambda **kwargs: _record_backend_event(db, **kwargs),
    )


@router.get("/discovery/pending")
def list_pending_discovered_sources(db: Session = Depends(get_db_session)):
    """List auto-discovered sources awaiting manual approval."""
    repo = SourceRepository(db)
    return list_pending_discovered_sources_service(repo=repo)


@router.post("/{source_id}/approve-discovered")
def approve_discovered_source(source_id: str, db: Session = Depends(get_db_session)):
    """Approve a pending auto-discovered source and enable it."""
    repo = SourceRepository(db)
    try:
        return approve_discovered_source_service(
            repo=repo,
            source_id=source_id,
            now_iso=_now_iso,
            record_event=lambda **kwargs: _record_backend_event(db, **kwargs),
        )
    except SourceNotFoundError as exc:
        raise HTTPException(404, "Source not found") from exc


@router.get("/trigger-all/history")
def list_full_organic_search_history(
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db_session),
):
    """List recent full organic search trigger runs."""
    run_repo = OrganicSearchRunRepository(db)
    runs = run_repo.list_recent(limit=limit)
    return [organic_run_to_dict(run) for run in runs]


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
    try:
        return trigger_full_discovery_service(
            dry_run=dry_run,
            follow_links=follow_links,
            limit=limit,
            include_grants=include_grants,
            now_iso=_now_iso,
            record_event=lambda **kwargs: _record_backend_event(db, **kwargs),
        )
    except SourceDispatchFailedError as exc:
        raise HTTPException(
            status_code=503,
            detail={
                "code": exc.code,
                "message": exc.message,
                "error": exc.error,
            },
        ) from exc


@router.get("/discover-full/preview")
def preview_discovery_candidates(
    limit: int = Query(50, ge=1, le=500),
    min_score: float = Query(0.0, ge=0.0, le=1.0, description="Minimum confidence score filter"),
):
    """Preview discovery candidates with confidence scores (no DB writes).

    Useful for auditing what the crawler would discover before triggering a run.
    """
    return preview_discovery_candidates_service(
        limit=limit,
        min_score=min_score,
        candidate_loader=load_all_discovery_candidates,
    )
