from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from packages.storage.models import BackendLog, Source
from packages.storage.repositories import BackendLogRepository


def backend_log_to_dict(row: BackendLog) -> dict[str, Any]:
    return {
        "id": row.id,
        "timestamp": row.created_at.isoformat() if row.created_at else None,
        "level": row.level,
        "event_type": row.event_type,
        "component": row.component,
        "source_id": row.source_id,
        "message": row.message,
        "context": row.context_json or {},
    }


def list_feed_activity(db: Session, *, limit: int = 10) -> list[dict[str, Any]]:
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


def list_source_status(db: Session) -> list[dict[str, Any]]:
    rows = db.query(Source).order_by(Source.name.asc()).all()
    return [
        {
            "id": source.id,
            "name": source.name,
            "enabled": bool(source.enabled),
            "status": "disabled" if not source.enabled else ("warning" if (source.error_count or 0) > 0 else "active"),
            "error_count": int(source.error_count or 0),
            "last_error": source.last_error,
            "last_polled_at": source.last_polled_at.isoformat() if source.last_polled_at else None,
            "last_success_at": source.last_success_at.isoformat() if source.last_success_at else None,
            "poll_interval_seconds": source.poll_interval_seconds,
            "total_listings": int(source.total_listings or 0),
        }
        for source in rows
    ]


def list_discovery_activity(db: Session, *, limit: int = 5) -> list[dict[str, Any]]:
    rows = (
        db.query(BackendLog)
        .filter(
            BackendLog.event_type.in_(
                [
                    "source_discovery_complete",
                    "discovery_during_scrape_complete",
                    "discovery_during_scrape_failed",
                ]
            )
        )
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


def list_backend_logs(
    db: Session,
    *,
    hours: int = 24,
    limit: int = 100,
    level: str | None = None,
    event_type: str | None = None,
) -> list[dict[str, Any]]:
    repo = BackendLogRepository(db)
    rows = repo.list_recent(hours=hours, limit=limit, level=level, event_type=event_type)
    return [backend_log_to_dict(row) for row in rows]


def backend_logs_summary(db: Session, *, hours: int = 24) -> dict[str, Any]:
    repo = BackendLogRepository(db)
    return repo.summary(hours=hours)


def backend_health_summary(db: Session, *, queue_settings: Any) -> dict[str, Any]:
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
        context = row.context_json or {}
        geocode_attempts += int(context.get("geocode_attempts") or 0)
        geocode_successes += int(context.get("geocode_successes") or 0)

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
            "scrape_queue_configured": bool(queue_settings.scrape_queue_url),
            "alert_queue_configured": bool(queue_settings.alert_queue_url),
            "llm_queue_configured": bool(queue_settings.llm_queue_url),
        },
        "last_error": {
            "timestamp": last_error.created_at.isoformat() if last_error and last_error.created_at else None,
            "message": last_error.message if last_error else None,
            "event_type": last_error.event_type if last_error else None,
            "level": last_error.level if last_error else None,
        },
    }


def list_recent_errors(
    db: Session,
    *,
    level: str | None = None,
    limit: int = 25,
) -> list[dict[str, Any]]:
    repo = BackendLogRepository(db)
    if level:
        rows = repo.list_recent(hours=24, limit=limit, level=level)
    else:
        rows = repo.list_recent_errors(hours=24, limit=limit)

    return [backend_log_to_dict(row) for row in rows]
