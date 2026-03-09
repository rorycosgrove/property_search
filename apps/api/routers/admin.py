"""Admin endpoints — database migrations and diagnostics."""

from __future__ import annotations

import subprocess
import sys
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from packages.shared.config import settings
from packages.shared.constants import MIGRATION_STATUS_TIMEOUT_SECONDS, MIGRATION_TIMEOUT_SECONDS
from packages.shared.logging import get_logger
from packages.storage.database import get_db_session
from packages.storage.models import BackendLog, Source

logger = get_logger(__name__)

router = APIRouter()


@router.post("/migrate", summary="Run Alembic migrations (upgrade head)")
def run_migrations():
    """Execute `alembic upgrade head` inside the Lambda environment."""
    try:
        result = subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            capture_output=True,
            text=True,
            timeout=MIGRATION_TIMEOUT_SECONDS,
        )
        if result.returncode != 0:
            logger.error("migration_failed", stderr=result.stderr)
            raise HTTPException(status_code=500, detail=result.stderr)
        logger.info("migration_success", stdout=result.stdout)
        return {"status": "ok", "output": result.stdout.strip()}
    except subprocess.TimeoutExpired:
        logger.error("migration_timeout")
        raise HTTPException(status_code=504, detail="Migration timed out")
    except Exception as e:
        logger.error("migration_error", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/migrate/status", summary="Current Alembic revision")
def migration_status():
    """Return the current Alembic migration revision."""
    try:
        result = subprocess.run(
            [sys.executable, "-m", "alembic", "current"],
            capture_output=True,
            text=True,
            timeout=MIGRATION_STATUS_TIMEOUT_SECONDS,
        )
        if result.returncode != 0:
            raise HTTPException(status_code=500, detail=result.stderr)
        return {"revision": result.stdout.strip()}
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=504, detail="Status check timed out")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/logs/feed-activity", summary="Recent feed refresh activity")
def get_feed_activity(
    limit: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db_session),
):
    rows = (
        db.query(BackendLog)
        .filter(BackendLog.event_type == "scrape_source_complete")
        .order_by(BackendLog.created_at.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id": row.id,
            "timestamp": row.created_at.isoformat() if row.created_at else None,
            "source_id": row.source_id,
            "source_name": (row.context_json or {}).get("source_name"),
            "new": (row.context_json or {}).get("new", 0),
            "updated": (row.context_json or {}).get("updated", 0),
            "skipped": (row.context_json or {}).get("skipped", 0),
            "total_fetched": (row.context_json or {}).get("total_fetched", 0),
            "geocode_success_rate": (row.context_json or {}).get("geocode_success_rate", 0),
            "status": "success",
        }
        for row in rows
    ]


@router.get("/logs/sources", summary="Current source status")
def get_source_status(db: Session = Depends(get_db_session)):
    rows = db.query(Source).order_by(Source.name.asc()).all()
    return [
        {
            "id": s.id,
            "name": s.name,
            "enabled": bool(s.enabled),
            "status": "disabled" if not s.enabled else ("warning" if (s.error_count or 0) > 0 else "active"),
            "error_count": int(s.error_count or 0),
            "last_error": s.last_error,
            "last_polled_at": s.last_polled_at.isoformat() if s.last_polled_at else None,
            "last_success_at": s.last_success_at.isoformat() if s.last_success_at else None,
            "poll_interval_seconds": s.poll_interval_seconds,
            "total_listings": int(s.total_listings or 0),
        }
        for s in rows
    ]


@router.get("/logs/discovery", summary="Recent discovery activity")
def get_discovery_activity(
    limit: int = Query(5, ge=1, le=50),
    db: Session = Depends(get_db_session),
):
    rows = (
        db.query(BackendLog)
        .filter(BackendLog.event_type.in_(["source_discovery_complete", "discovery_during_scrape_complete", "discovery_during_scrape_failed"]))
        .order_by(BackendLog.created_at.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id": row.id,
            "timestamp": row.created_at.isoformat() if row.created_at else None,
            "event_type": row.event_type,
            "level": row.level,
            "message": row.message,
            "context": row.context_json or {},
        }
        for row in rows
    ]


@router.get("/logs/health", summary="Backend ingestion health summary")
def get_backend_health_summary(db: Session = Depends(get_db_session)):
    recent_scrapes = (
        db.query(BackendLog)
        .filter(BackendLog.event_type == "scrape_source_complete")
        .order_by(BackendLog.created_at.desc())
        .limit(100)
        .all()
    )

    geocode_attempts = 0
    geocode_successes = 0
    for row in recent_scrapes:
        ctx = row.context_json or {}
        geocode_attempts += int(ctx.get("geocode_attempts") or 0)
        geocode_successes += int(ctx.get("geocode_successes") or 0)

    geocode_success_rate = round((geocode_successes / geocode_attempts) * 100, 2) if geocode_attempts else 100.0

    last_error = (
        db.query(BackendLog)
        .filter(BackendLog.level.in_(["ERROR", "WARNING"]))
        .order_by(BackendLog.created_at.desc())
        .first()
    )

    recent_window_start = datetime.now(UTC) - timedelta(hours=24)
    scrape_count_24h = (
        db.query(func.count(BackendLog.id))
        .filter(
            BackendLog.event_type == "scrape_source_complete",
            BackendLog.created_at >= recent_window_start,
        )
        .scalar()
    )

    return {
        "scrape_runs_24h": int(scrape_count_24h or 0),
        "geocode_attempts": geocode_attempts,
        "geocode_successes": geocode_successes,
        "geocode_success_rate": geocode_success_rate,
        "queue_config": {
            "scrape_queue_configured": bool(settings.scrape_queue_url),
            "alert_queue_configured": bool(settings.alert_queue_url),
            "llm_queue_configured": bool(settings.llm_queue_url),
        },
        "last_error": {
            "timestamp": last_error.created_at.isoformat() if last_error and last_error.created_at else None,
            "message": last_error.message if last_error else None,
            "event_type": last_error.event_type if last_error else None,
            "level": last_error.level if last_error else None,
        },
    }


@router.get("/logs/recent-errors", summary="Recent warning/error logs")
def get_recent_errors(
    level: str | None = Query(None, description="Optional log level filter, e.g. ERROR or WARNING"),
    limit: int = Query(25, ge=1, le=200),
    db: Session = Depends(get_db_session),
):
    query = db.query(BackendLog)
    if level:
        query = query.filter(BackendLog.level == level.upper())
    else:
        query = query.filter(BackendLog.level.in_(["ERROR", "WARNING"]))

    rows = query.order_by(BackendLog.created_at.desc()).limit(limit).all()
    return [
        {
            "id": row.id,
            "timestamp": row.created_at.isoformat() if row.created_at else None,
            "level": row.level,
            "event_type": row.event_type,
            "component": row.component,
            "source_id": row.source_id,
            "message": row.message,
            "context": row.context_json or {},
        }
        for row in rows
    ]
