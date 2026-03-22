"""Admin endpoints — database migrations and diagnostics."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from packages.admin.service import (
    AdminServiceError,
    MigrationCommandFailedError,
    MigrationCommandTimedOutError,
    backend_health_summary,
    backend_logs_summary,
    data_lifecycle_schedule_metadata,
    data_lifecycle_report,
    diagnose_listing_by_external_id,
    explain_source_quality,
    get_migration_status,
    list_backend_logs,
    list_data_lifecycle_activity,
    list_discovery_activity,
    list_feed_activity,
    list_recent_errors,
    run_data_lifecycle_action,
    list_source_quality_activity,
    list_source_status,
    run_database_migrations,
    source_quality_scorecards,
    source_freshness_report,
)
from packages.shared.config import settings
from packages.shared.logging import get_logger
from packages.shared.queue import QueueDispatchError, dispatch_or_inline
from packages.storage.database import get_db_session

logger = get_logger(__name__)

router = APIRouter()


@router.post("/migrate", summary="Run Alembic migrations (upgrade head)")
def run_migrations():
    """Execute `alembic upgrade head` inside the Lambda environment."""
    try:
        return run_database_migrations(logger=logger)
    except MigrationCommandTimedOutError as exc:
        raise HTTPException(status_code=504, detail=exc.detail) from exc
    except MigrationCommandFailedError as exc:
        raise HTTPException(status_code=500, detail=exc.detail) from exc


@router.get("/migrate/status", summary="Current Alembic revision")
def migration_status():
    """Return the current Alembic migration revision."""
    try:
        return get_migration_status()
    except MigrationCommandTimedOutError as exc:
        raise HTTPException(status_code=504, detail=exc.detail) from exc
    except MigrationCommandFailedError as exc:
        raise HTTPException(status_code=500, detail=exc.detail) from exc


@router.get("/logs/feed-activity", summary="Recent feed refresh activity")
def get_feed_activity(
    limit: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db_session),
):
    return list_feed_activity(db, limit=limit)


@router.get("/logs/sources", summary="Current source status")
def get_source_status(db: Session = Depends(get_db_session)):
    return list_source_status(db)


@router.get("/sources/freshness", summary="Source poll freshness report")
def get_source_freshness(db: Session = Depends(get_db_session)):
    """Return freshness status for each enabled source.

    Sources that have not had a successful poll within 1.5× their
    poll_interval_seconds are flagged as stale.  Stale or never-polled
    sources represent live data gaps.
    """
    return source_freshness_report(db)


@router.get("/data-lifecycle/report", summary="Data lifecycle archival/rollup report")
def get_data_lifecycle_report(
    property_archive_days: int = Query(365, ge=30, le=3650),
    backend_log_archive_days: int = Query(90, ge=7, le=3650),
    rollup_days: int = Query(180, ge=30, le=3650),
    db: Session = Depends(get_db_session),
):
    """Return dry-run lifecycle candidates for archival and rollup workflows."""
    return data_lifecycle_report(
        db,
        property_archive_days=property_archive_days,
        backend_log_archive_days=backend_log_archive_days,
        rollup_days=rollup_days,
    )


@router.post("/data-lifecycle/actions/{action}", summary="Execute lifecycle action (dry-run only)")
def execute_data_lifecycle_action(
    action: str,
    dry_run: bool = Query(True, description="Must be true. non-dry-run is intentionally disabled"),
    property_archive_days: int = Query(365, ge=30, le=3650),
    backend_log_archive_days: int = Query(90, ge=7, le=3650),
    rollup_days: int = Query(180, ge=30, le=3650),
    db: Session = Depends(get_db_session),
):
    try:
        return run_data_lifecycle_action(
            db,
            action=action,
            dry_run=dry_run,
            property_archive_days=property_archive_days,
            backend_log_archive_days=backend_log_archive_days,
            rollup_days=rollup_days,
        )
    except AdminServiceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/data-lifecycle/history", summary="Recent lifecycle action history")
def get_data_lifecycle_history(
    hours: int = Query(168, ge=1, le=720),
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db_session),
):
    return list_data_lifecycle_activity(db, hours=hours, limit=limit)


@router.get("/data-lifecycle/schedule", summary="Lifecycle schedule and policy metadata")
def get_data_lifecycle_schedule(
    db: Session = Depends(get_db_session),
):
    return data_lifecycle_schedule_metadata(db, queue_settings=settings)


@router.get("/logs/discovery", summary="Recent discovery activity")
def get_discovery_activity(
    limit: int = Query(5, ge=1, le=50),
    db: Session = Depends(get_db_session),
):
    return list_discovery_activity(db, limit=limit)


@router.get("/logs/source-quality", summary="Recent source quality snapshots")
def get_source_quality_activity(
    limit: int = Query(50, ge=1, le=500),
    source_id: str | None = Query(None, min_length=36, max_length=36),
    run_type: str | None = Query(None, pattern="^(scrape|discovery|governance)$"),
    db: Session = Depends(get_db_session),
):
    return list_source_quality_activity(
        db,
        limit=limit,
        source_id=source_id,
        run_type=run_type,
    )


@router.get("/logs/source-quality/scorecards", summary="Rolling source quality scorecards")
def get_source_quality_scorecards(
    lookback_hours: int = Query(168, ge=1, le=720),
    limit: int = Query(100, ge=1, le=500),
    min_samples: int = Query(3, ge=1, le=50),
    db: Session = Depends(get_db_session),
):
    return source_quality_scorecards(
        db,
        lookback_hours=lookback_hours,
        limit=limit,
        min_samples=min_samples,
    )


@router.get("/logs/source-quality/{source_id}/explain", summary="Explain quality/governance for one source")
def get_source_quality_explain(
    source_id: str,
    lookback_hours: int = Query(168, ge=1, le=720),
    min_samples: int = Query(3, ge=1, le=50),
    governance_limit: int = Query(20, ge=1, le=200),
    scrape_limit: int = Query(20, ge=1, le=200),
    db: Session = Depends(get_db_session),
):
    return explain_source_quality(
        db,
        source_id=source_id,
        lookback_hours=lookback_hours,
        min_samples=min_samples,
        governance_limit=governance_limit,
        scrape_limit=scrape_limit,
    )


@router.post("/sources/quality-governance/evaluate", summary="Run source quality governance")
def run_source_quality_governance(
    recent_limit: int = Query(200, ge=10, le=2000),
    min_samples: int = Query(3, ge=1, le=20),
    quarantine_parse_fail_rate: float = Query(0.5, ge=0.1, le=1.0),
    promote_parse_fail_rate: float = Query(0.1, ge=0.0, le=0.5),
):
    """Evaluate source quality snapshots and apply promotion/quarantine rules."""
    from apps.worker.tasks import evaluate_source_quality_governance

    payload = {
        "recent_limit": recent_limit,
        "min_samples": min_samples,
        "quarantine_parse_fail_rate": quarantine_parse_fail_rate,
        "promote_parse_fail_rate": promote_parse_fail_rate,
    }
    try:
        return dispatch_or_inline(
            "scrape",
            "evaluate_source_quality_governance",
            payload,
            lambda **kwargs: evaluate_source_quality_governance(**kwargs),
        )
    except QueueDispatchError as exc:
        raise HTTPException(
            status_code=503,
            detail={
                "code": "source_quality_governance_dispatch_failed",
                "message": "Failed to dispatch source quality governance task.",
                "error": str(exc.error)[:300],
            },
        ) from exc


@router.get("/backend-logs", summary="Query backend logs")
def get_backend_logs(
    hours: int = Query(24, ge=1, le=168),
    limit: int = Query(100, ge=1, le=500),
    level: str | None = Query(None, description="Optional log level filter, e.g. ERROR or WARNING"),
    event_type: str | None = Query(None, description="Optional event type filter"),
    db: Session = Depends(get_db_session),
):
    return list_backend_logs(db, hours=hours, limit=limit, level=level, event_type=event_type)


@router.get("/backend-logs/summary", summary="Backend logs summary")
def get_backend_logs_summary(
    hours: int = Query(24, ge=1, le=168),
    db: Session = Depends(get_db_session),
):
    return backend_logs_summary(db, hours=hours)


@router.get("/logs/health", summary="Backend ingestion health summary")
def get_backend_health_summary(db: Session = Depends(get_db_session)):
    return backend_health_summary(db, queue_settings=settings)


@router.get("/logs/recent-errors", summary="Recent warning/error logs")
def get_recent_errors(
    level: str | None = Query(None, description="Optional log level filter, e.g. ERROR or WARNING"),
    limit: int = Query(25, ge=1, le=200),
    db: Session = Depends(get_db_session),
):
    return list_recent_errors(db, level=level, limit=limit)


@router.get("/listings/{external_id}/diagnose", summary="Diagnose why a listing was missed")
def diagnose_listing(
    external_id: str,
    adapter_name: str = Query("daft", description="Source adapter name, currently supports daft"),
    listing_url: str | None = Query(None, description="Optional listing URL for direct fallback probe"),
    similar_ids: str | None = Query(None, description="Optional comma-separated similar listing IDs for reverse anchored probe"),
    hours: int = Query(168, ge=1, le=720, description="Recent log lookback window in hours"),
    max_probe_sources: int = Query(25, ge=1, le=60, description="Maximum source/candidate probes to attempt"),
    probe_max_pages: int = Query(25, ge=5, le=300, description="Maximum pages to probe per target source"),
    db: Session = Depends(get_db_session),
):
    try:
        return diagnose_listing_by_external_id(
            db,
            external_id=external_id,
            adapter_name=adapter_name,
            listing_url=listing_url,
            similar_ids=similar_ids,
            repair=False,
            hours=hours,
            max_probe_sources=max_probe_sources,
            probe_max_pages=probe_max_pages,
        )
    except AdminServiceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/listings/{external_id}/repair", summary="Diagnose and repair a missed listing")
def repair_listing(
    external_id: str,
    adapter_name: str = Query("daft", description="Source adapter name, currently supports daft"),
    listing_url: str | None = Query(None, description="Optional listing URL for direct fallback probe"),
    similar_ids: str | None = Query(None, description="Optional comma-separated similar listing IDs for reverse anchored probe"),
    hours: int = Query(168, ge=1, le=720, description="Recent log lookback window in hours"),
    max_probe_sources: int = Query(25, ge=1, le=60, description="Maximum source/candidate probes to attempt"),
    probe_max_pages: int = Query(25, ge=5, le=300, description="Maximum pages to probe per target source"),
    db: Session = Depends(get_db_session),
):
    try:
        return diagnose_listing_by_external_id(
            db,
            external_id=external_id,
            adapter_name=adapter_name,
            listing_url=listing_url,
            similar_ids=similar_ids,
            repair=True,
            hours=hours,
            max_probe_sources=max_probe_sources,
            probe_max_pages=probe_max_pages,
        )
    except AdminServiceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
