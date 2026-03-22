from __future__ import annotations

import json
import re
import subprocess
import sys
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urlparse

import httpx

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from packages.shared.constants import MIGRATION_STATUS_TIMEOUT_SECONDS, MIGRATION_TIMEOUT_SECONDS
from packages.storage.models import BackendLog, Source
from packages.storage.models import Property, PropertyPriceHistory, PropertyTimelineEvent
from packages.storage.repositories import (
    BackendLogRepository,
    PriceHistoryRepository,
    PropertyRepository,
    SourceQualitySnapshotRepository,
    SourceRepository,
)


class AdminServiceError(Exception):
    """Base exception for admin-domain service failures."""


class MigrationCommandFailedError(AdminServiceError):
    def __init__(self, detail: str):
        self.detail = detail
        super().__init__(detail)


class MigrationCommandTimedOutError(AdminServiceError):
    def __init__(self, detail: str):
        self.detail = detail
        super().__init__(detail)


def run_database_migrations(
    *,
    logger: Any,
    executable: str = sys.executable,
    timeout: int = MIGRATION_TIMEOUT_SECONDS,
    runner: Any = subprocess.run,
) -> dict[str, Any]:
    try:
        result = runner(
            [executable, "-m", "alembic", "upgrade", "head"],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if result.returncode != 0:
            logger.error("migration_failed", stderr=result.stderr)
            raise MigrationCommandFailedError(result.stderr)
        logger.info("migration_success", stdout=result.stdout)
        return {"status": "ok", "output": result.stdout.strip()}
    except subprocess.TimeoutExpired as exc:
        logger.error("migration_timeout")
        raise MigrationCommandTimedOutError("Migration timed out") from exc
    except AdminServiceError:
        raise
    except Exception as exc:
        logger.error("migration_error", error=str(exc))
        raise MigrationCommandFailedError(str(exc)) from exc


def get_migration_status(
    *,
    executable: str = sys.executable,
    timeout: int = MIGRATION_STATUS_TIMEOUT_SECONDS,
    runner: Any = subprocess.run,
) -> dict[str, str]:
    try:
        result = runner(
            [executable, "-m", "alembic", "current"],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if result.returncode != 0:
            raise MigrationCommandFailedError(result.stderr)
        return {"revision": result.stdout.strip()}
    except subprocess.TimeoutExpired as exc:
        raise MigrationCommandTimedOutError("Status check timed out") from exc
    except AdminServiceError:
        raise
    except Exception as exc:
        raise MigrationCommandFailedError(str(exc)) from exc


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


def source_freshness_report(db: Session) -> dict[str, Any]:
    """Return freshness status for all enabled sources.

    A source is *stale* when it has not had a successful poll within 1.5×
    its ``poll_interval_seconds``.  *never_polled* sources have no
    ``last_success_at`` at all.  Both categories are correctness risks.
    """
    from datetime import UTC, datetime
    now = datetime.now(UTC)
    rows = db.query(Source).filter(Source.enabled.is_(True)).order_by(Source.name.asc()).all()

    stale: list[dict[str, Any]] = []
    never_polled: list[dict[str, Any]] = []
    healthy: list[dict[str, Any]] = []

    for source in rows:
        interval = int(source.poll_interval_seconds or 21600)
        entry: dict[str, Any] = {
            "id": source.id,
            "name": source.name,
            "poll_interval_seconds": interval,
            "last_success_at": source.last_success_at.isoformat() if source.last_success_at else None,
            "error_count": int(source.error_count or 0),
        }
        if source.last_success_at is None:
            never_polled.append(entry)
        elif (now - source.last_success_at).total_seconds() > interval * 1.5:
            age = int((now - source.last_success_at).total_seconds())
            stale.append({**entry, "stale_seconds": age, "expected_max_seconds": int(interval * 1.5)})
        else:
            age = int((now - source.last_success_at).total_seconds())
            healthy.append({**entry, "age_seconds": age})

    return {
        "checked_at": now.isoformat(),
        "healthy_count": len(healthy),
        "stale_count": len(stale),
        "never_polled_count": len(never_polled),
        "at_risk": len(stale) + len(never_polled) > 0,
        "stale": stale,
        "never_polled": never_polled,
        "healthy": healthy,
    }


def data_lifecycle_report(
    db: Session,
    *,
    property_archive_days: int = 365,
    backend_log_archive_days: int = 90,
    rollup_days: int = 180,
) -> dict[str, Any]:
    """Return archival and rollup candidates for lifecycle operations.

    This endpoint is intentionally read-only: it provides a safe dry-run
    overview before any destructive or archival jobs are introduced.
    """
    now = datetime.now(UTC)

    property_cutoff = now - timedelta(days=max(property_archive_days, 1))
    log_cutoff = now - timedelta(days=max(backend_log_archive_days, 1))
    rollup_cutoff = now - timedelta(days=max(rollup_days, 1))

    property_archive_candidates = (
        db.query(Property)
        .filter(Property.status.in_(["sold", "withdrawn"]))
        .filter(Property.updated_at < property_cutoff)
        .count()
    )

    backend_log_archive_candidates = (
        db.query(BackendLog)
        .filter(BackendLog.created_at < log_cutoff)
        .count()
    )

    price_history_rollup_candidates = (
        db.query(PropertyPriceHistory)
        .filter(PropertyPriceHistory.recorded_at < rollup_cutoff)
        .count()
    )

    timeline_rollup_candidates = (
        db.query(PropertyTimelineEvent)
        .filter(PropertyTimelineEvent.occurred_at < rollup_cutoff)
        .count()
    )

    return {
        "checked_at": now.isoformat(),
        "cutoffs": {
            "property_archive_before": property_cutoff.isoformat(),
            "backend_log_archive_before": log_cutoff.isoformat(),
            "rollup_before": rollup_cutoff.isoformat(),
        },
        "candidates": {
            "property_archive": int(property_archive_candidates),
            "backend_log_archive": int(backend_log_archive_candidates),
            "price_history_rollup": int(price_history_rollup_candidates),
            "timeline_rollup": int(timeline_rollup_candidates),
        },
        "actions": [
            {
                "id": "archive_properties",
                "description": "Archive sold/withdrawn properties older than cutoff",
                "dry_run": True,
            },
            {
                "id": "archive_backend_logs",
                "description": "Archive backend logs older than cutoff",
                "dry_run": True,
            },
            {
                "id": "rollup_price_and_timeline",
                "description": "Roll up historical price/timeline events older than cutoff",
                "dry_run": True,
            },
        ],
    }


def run_data_lifecycle_action(
    db: Session,
    *,
    action: str,
    dry_run: bool = True,
    property_archive_days: int = 365,
    backend_log_archive_days: int = 90,
    rollup_days: int = 180,
) -> dict[str, Any]:
    """Execute a lifecycle action in dry-run mode and emit an audit log.

    Safety guard: non-dry-run execution is intentionally blocked until
    dedicated archival/rollup jobs with rollback strategy are introduced.
    """
    allowed_actions = {
        "archive_properties": "property_archive",
        "archive_backend_logs": "backend_log_archive",
        "rollup_price_and_timeline": None,
    }

    normalized = str(action or "").strip()
    if normalized not in allowed_actions:
        raise AdminServiceError(
            f"invalid action '{normalized}'. expected one of: {', '.join(allowed_actions)}"
        )

    if not dry_run:
        raise AdminServiceError(
            "non-dry-run lifecycle execution is disabled. pass dry_run=true"
        )

    report = data_lifecycle_report(
        db,
        property_archive_days=property_archive_days,
        backend_log_archive_days=backend_log_archive_days,
        rollup_days=rollup_days,
    )
    candidates = report.get("candidates", {})

    if normalized == "rollup_price_and_timeline":
        affected = int(candidates.get("price_history_rollup", 0)) + int(candidates.get("timeline_rollup", 0))
    else:
        candidate_key = allowed_actions[normalized]
        affected = int(candidates.get(candidate_key or "", 0))

    payload = {
        "status": "dry_run_completed",
        "action": normalized,
        "dry_run": True,
        "executed_at": datetime.now(UTC).isoformat(),
        "affected_candidates": affected,
        "report": report,
    }

    db.add(
        BackendLog(
            level="INFO",
            event_type="admin_data_lifecycle_action",
            component="api",
            message=f"Lifecycle action dry-run executed: {normalized}",
            context_json={
                "action": normalized,
                "dry_run": True,
                "affected_candidates": affected,
                "cutoffs": report.get("cutoffs", {}),
            },
        )
    )
    db.flush()

    return payload


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


def list_source_quality_activity(
    db: Session,
    *,
    limit: int = 50,
    source_id: str | None = None,
    run_type: str | None = None,
) -> list[dict[str, Any]]:
    repo = SourceQualitySnapshotRepository(db)
    rows = repo.list_recent(source_id=source_id, run_type=run_type, limit=limit)
    return [
        {
            "id": row.id,
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "source_id": row.source_id,
            "source_name": row.source_name,
            "adapter_name": row.adapter_name,
            "run_type": row.run_type,
            "total_fetched": row.total_fetched,
            "parse_failed": row.parse_failed,
            "new_count": row.new_count,
            "updated_count": row.updated_count,
            "price_unchanged_count": row.price_unchanged_count,
            "dedup_conflicts": row.dedup_conflicts,
            "candidates_scored": row.candidates_scored,
            "created_count": row.created_count,
            "auto_enabled_count": row.auto_enabled_count,
            "pending_approval_count": row.pending_approval_count,
            "existing_count": row.existing_count,
            "skipped_invalid_count": row.skipped_invalid_count,
            "skipped_invalid_config_count": row.skipped_invalid_config_count,
            "score_avg": row.score_avg,
            "score_max": row.score_max,
            "dry_run": row.dry_run,
            "follow_links": row.follow_links,
            "details": row.details or {},
        }
        for row in rows
    ]


def source_quality_scorecards(
    db: Session,
    *,
    lookback_hours: int = 168,
    limit: int = 100,
    min_samples: int = 3,
) -> dict[str, Any]:
    """Build rolling per-source quality scorecards from recent scrape snapshots."""
    now = datetime.now(UTC)
    cutoff = now - timedelta(hours=max(lookback_hours, 1))

    quality_repo = SourceQualitySnapshotRepository(db)
    source_repo = SourceRepository(db)

    # Fetch a larger working set, then apply time/min-sample filtering in-process.
    working_limit = max(limit * 25, 1000)
    snapshots = quality_repo.list_recent(run_type="scrape", limit=min(working_limit, 5000))
    snapshots = [s for s in snapshots if getattr(s, "created_at", None) and s.created_at >= cutoff]

    governance_rows = quality_repo.list_recent(run_type="governance", limit=min(working_limit, 5000))
    governance_rows = [
        g for g in governance_rows if getattr(g, "source_id", None) and getattr(g, "created_at", None) and g.created_at >= cutoff
    ]
    latest_governance_by_source: dict[str, Any] = {}
    for row in governance_rows:
        sid = str(getattr(row, "source_id", "") or "").strip()
        if not sid:
            continue
        current = latest_governance_by_source.get(sid)
        if current is None or row.created_at > current.created_at:
            latest_governance_by_source[sid] = row

    by_source: dict[str, list[Any]] = defaultdict(list)
    for snap in snapshots:
        sid = str(getattr(snap, "source_id", "") or "").strip()
        if sid:
            by_source[sid].append(snap)

    sources = source_repo.get_all(enabled_only=False)
    source_by_id = {str(getattr(s, "id", "")): s for s in sources}

    cards: list[dict[str, Any]] = []
    dropped_min_samples = 0

    for source_id, rows in by_source.items():
        rows_sorted = sorted(rows, key=lambda r: getattr(r, "created_at", now), reverse=True)
        samples = len(rows_sorted)
        if samples < max(min_samples, 1):
            dropped_min_samples += 1
            continue

        total_fetched = sum(int(getattr(r, "total_fetched", 0) or 0) for r in rows_sorted)
        parse_failed = sum(int(getattr(r, "parse_failed", 0) or 0) for r in rows_sorted)
        useful_changes = sum(
            int(getattr(r, "new_count", 0) or 0) + int(getattr(r, "updated_count", 0) or 0)
            for r in rows_sorted
        )
        dedup_conflicts = sum(int(getattr(r, "dedup_conflicts", 0) or 0) for r in rows_sorted)

        avg_parse_fail_rate = (parse_failed / total_fetched) if total_fetched > 0 else None
        latest = rows_sorted[0]
        latest_fetched = int(getattr(latest, "total_fetched", 0) or 0)
        latest_failed = int(getattr(latest, "parse_failed", 0) or 0)
        latest_rate = (latest_failed / latest_fetched) if latest_fetched > 0 else None

        baseline_rows = rows_sorted[1:]
        baseline_fetched = sum(int(getattr(r, "total_fetched", 0) or 0) for r in baseline_rows)
        baseline_failed = sum(int(getattr(r, "parse_failed", 0) or 0) for r in baseline_rows)
        baseline_rate = (baseline_failed / baseline_fetched) if baseline_fetched > 0 else avg_parse_fail_rate
        trend_delta = (latest_rate - baseline_rate) if (latest_rate is not None and baseline_rate is not None) else None

        source = source_by_id.get(source_id)
        tags = list(getattr(source, "tags", None) or []) if source else []
        enabled = bool(getattr(source, "enabled", False)) if source else False
        pending = "pending_approval" in tags

        if avg_parse_fail_rate is None:
            risk = "unknown"
            recommendation = "monitor"
        elif avg_parse_fail_rate >= 0.5:
            risk = "high"
            recommendation = "quarantine" if enabled else "monitor"
        elif avg_parse_fail_rate >= 0.25:
            risk = "medium"
            recommendation = "monitor"
        else:
            risk = "low"
            recommendation = "promote" if pending and useful_changes > 0 else "monitor"

        cards.append(
            {
                "source_id": source_id,
                "source_name": getattr(source, "name", None) or getattr(latest, "source_name", None),
                "adapter_name": getattr(source, "adapter_name", None) or getattr(latest, "adapter_name", None),
                "enabled": enabled,
                "tags": tags,
                "samples": samples,
                "total_fetched": total_fetched,
                "parse_failed": parse_failed,
                "avg_parse_fail_rate": round(avg_parse_fail_rate, 4) if avg_parse_fail_rate is not None else None,
                "latest_parse_fail_rate": round(latest_rate, 4) if latest_rate is not None else None,
                "baseline_parse_fail_rate": round(baseline_rate, 4) if baseline_rate is not None else None,
                "parse_fail_trend_delta": round(trend_delta, 4) if trend_delta is not None else None,
                "useful_changes": useful_changes,
                "dedup_conflicts": dedup_conflicts,
                "risk_level": risk,
                "recommendation": recommendation,
                "last_observed_at": latest.created_at.isoformat() if getattr(latest, "created_at", None) else None,
                "latest_governance_action": (
                    (latest_governance_by_source.get(source_id).details or {}).get("action")
                    if latest_governance_by_source.get(source_id)
                    else None
                ),
                "latest_governance_reason": (
                    (latest_governance_by_source.get(source_id).details or {}).get("reason")
                    if latest_governance_by_source.get(source_id)
                    else None
                ),
                "latest_governance_at": (
                    latest_governance_by_source.get(source_id).created_at.isoformat()
                    if latest_governance_by_source.get(source_id)
                    and getattr(latest_governance_by_source.get(source_id), "created_at", None)
                    else None
                ),
                "latest_governance_confidence": (
                    _governance_confidence_for_scorecard(
                        action=(latest_governance_by_source.get(source_id).details or {}).get("action"),
                        avg_parse_fail_rate=avg_parse_fail_rate,
                        thresholds=(latest_governance_by_source.get(source_id).details or {}).get("thresholds") or {},
                    )
                    if latest_governance_by_source.get(source_id)
                    else None
                ),
            }
        )

    cards.sort(
        key=lambda c: (
            {"high": 0, "medium": 1, "low": 2, "unknown": 3}.get(c["risk_level"], 4),
            -(c.get("samples") or 0),
        )
    )
    cards = cards[: max(1, limit)]

    return {
        "generated_at": now.isoformat(),
        "lookback_hours": int(max(lookback_hours, 1)),
        "min_samples": int(max(min_samples, 1)),
        "total_sources_seen": len(by_source),
        "dropped_min_samples": dropped_min_samples,
        "returned": len(cards),
        "scorecards": cards,
    }


def _governance_confidence_for_scorecard(
    *,
    action: str | None,
    avg_parse_fail_rate: float | None,
    thresholds: dict[str, Any],
) -> float | None:
    """Estimate confidence in latest governance action from threshold distance."""
    if avg_parse_fail_rate is None or action not in {"promote", "quarantine"}:
        return None

    promote_thr = float(thresholds.get("promote_parse_fail_rate", 0.1) or 0.1)
    quarantine_thr = float(thresholds.get("quarantine_parse_fail_rate", 0.5) or 0.5)

    if action == "promote":
        denom = promote_thr if promote_thr > 0 else 0.1
        score = (promote_thr - avg_parse_fail_rate) / denom
    else:
        denom = (1.0 - quarantine_thr) if quarantine_thr < 1.0 else 0.5
        score = (avg_parse_fail_rate - quarantine_thr) / denom

    return round(max(0.0, min(1.0, score)), 4)


def explain_source_quality(
    db: Session,
    *,
    source_id: str,
    lookback_hours: int = 168,
    min_samples: int = 3,
    governance_limit: int = 20,
    scrape_limit: int = 20,
) -> dict[str, Any]:
    """Return explainable quality and governance context for a single source."""
    source_repo = SourceRepository(db)
    source = source_repo.get_by_id(source_id)

    scorecards_payload = source_quality_scorecards(
        db,
        lookback_hours=lookback_hours,
        limit=500,
        min_samples=min_samples,
    )
    scorecard = next(
        (card for card in scorecards_payload.get("scorecards", []) if card.get("source_id") == source_id),
        None,
    )

    quality_repo = SourceQualitySnapshotRepository(db)
    governance_rows = quality_repo.list_recent(source_id=source_id, run_type="governance", limit=governance_limit)
    scrape_rows = quality_repo.list_recent(source_id=source_id, run_type="scrape", limit=scrape_limit)

    decisions = [
        {
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "action": (row.details or {}).get("action"),
            "reason": (row.details or {}).get("reason"),
            "thresholds": (row.details or {}).get("thresholds") or {},
            "source_tags": (row.details or {}).get("source_tags") or [],
            "parse_failed": row.parse_failed,
            "total_fetched": row.total_fetched,
            "new_count": row.new_count,
            "updated_count": row.updated_count,
        }
        for row in governance_rows
    ]

    recent_scrape = [
        {
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "total_fetched": row.total_fetched,
            "parse_failed": row.parse_failed,
            "new_count": row.new_count,
            "updated_count": row.updated_count,
            "price_unchanged_count": row.price_unchanged_count,
            "dedup_conflicts": row.dedup_conflicts,
            "details": row.details or {},
        }
        for row in scrape_rows
    ]

    return {
        "source_id": source_id,
        "source_found": source is not None,
        "source": {
            "id": getattr(source, "id", None),
            "name": getattr(source, "name", None),
            "adapter_name": getattr(source, "adapter_name", None),
            "enabled": bool(getattr(source, "enabled", False)) if source else False,
            "tags": list(getattr(source, "tags", None) or []) if source else [],
        },
        "scorecard": scorecard,
        "governance_decisions": decisions,
        "recent_scrape_quality": recent_scrape,
        "meta": {
            "lookback_hours": int(max(lookback_hours, 1)),
            "min_samples": int(max(min_samples, 1)),
            "governance_limit": int(max(governance_limit, 1)),
            "scrape_limit": int(max(scrape_limit, 1)),
        },
    }


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


def list_data_lifecycle_activity(
    db: Session,
    *,
    hours: int = 168,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """Return recent lifecycle dry-run actions for operator audit timelines."""
    repo = BackendLogRepository(db)
    rows = repo.list_recent(
        hours=hours,
        limit=limit,
        event_type="admin_data_lifecycle_action",
    )
    return [backend_log_to_dict(row) for row in rows]


def data_lifecycle_schedule_metadata(
    db: Session,
    *,
    queue_settings: Any,
) -> dict[str, Any]:
    """Return lifecycle scheduling and policy metadata for operator visibility."""
    repo = BackendLogRepository(db)
    recent_runs = repo.list_recent(
        hours=24 * 30,
        limit=1,
        event_type="admin_data_lifecycle_action",
    )
    last_run = recent_runs[0] if recent_runs else None

    return {
        "checked_at": datetime.now(UTC).isoformat(),
        "execution_mode": {
            "destructive_enabled": False,
            "dry_run_only": True,
            "note": "Destructive lifecycle execution remains disabled until feature-flag and rollback controls are implemented.",
        },
        "cadence": {
            "source_scrape_interval_seconds": int(getattr(queue_settings, "scrape_poll_interval_seconds", 0) or 0),
            "rss_poll_interval_seconds": int(getattr(queue_settings, "rss_poll_interval_seconds", 0) or 0),
            "ppr_poll_interval_seconds": int(getattr(queue_settings, "ppr_poll_interval_seconds", 0) or 0),
            "lifecycle_action_trigger": "manual_admin_dry_run",
        },
        "policy": {
            "backend_log_retention_days": int(getattr(queue_settings, "backend_log_retention_days", 0) or 0),
            "default_property_archive_days": 365,
            "default_rollup_days": 180,
        },
        "last_lifecycle_run": backend_log_to_dict(last_run) if last_run else None,
    }


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


def _source_to_dict(source: Any) -> dict[str, Any]:
    config = getattr(source, "config", None) or {}
    tags = list(getattr(source, "tags", None) or [])
    return {
        "id": getattr(source, "id", None),
        "name": getattr(source, "name", None),
        "url": getattr(source, "url", None),
        "adapter_name": getattr(source, "adapter_name", None),
        "adapter_type": getattr(source, "adapter_type", None),
        "enabled": bool(getattr(source, "enabled", False)),
        "config": config,
        "tags": tags,
        "pending_approval": "pending_approval" in tags,
    }


def _property_to_dict(prop: Any) -> dict[str, Any]:
    source = getattr(prop, "source", None)
    raw_data = getattr(prop, "raw_data", None) or {}
    return {
        "id": getattr(prop, "id", None),
        "source_id": getattr(prop, "source_id", None),
        "source_name": getattr(source, "name", None),
        "source_adapter": getattr(source, "adapter_name", None),
        "external_id": getattr(prop, "external_id", None),
        "url_listing_id": raw_data.get("url_listing_id"),
        "url": getattr(prop, "url", None),
        "address": getattr(prop, "address", None),
        "status": getattr(prop, "status", None),
        "created_at": getattr(prop, "created_at", None).isoformat() if getattr(prop, "created_at", None) else None,
        "updated_at": getattr(prop, "updated_at", None).isoformat() if getattr(prop, "updated_at", None) else None,
        "canonical_property_id": getattr(prop, "canonical_property_id", None),
    }


def _candidate_priority(target: dict[str, Any]) -> tuple[int, int, int, int, str]:
    name = str(target.get("name") or "")
    tags = [str(tag).lower() for tag in target.get("tags") or []]
    config = target.get("config") or {}
    label = " ".join([name, str(target.get("url") or ""), " ".join(tags), json.dumps(config, sort_keys=True)]).lower()
    areas = [str(area).lower() for area in config.get("areas") or [] if area]
    is_national = "national" in label or "ireland" in areas or str(config.get("search_area") or "").lower() == "ireland"
    is_dublin = "dublin" in label
    enabled_rank = 0 if target.get("enabled") else 1
    existing_rank = 0 if target.get("id") else 1
    return (1 if is_national else 0, 1 if is_dublin else 0, enabled_rank, existing_rank, label)


def _derive_daft_probe_hints(*, listing_url: str | None, external_id: str) -> dict[str, Any]:
    """Infer targeting hints for faster Daft diagnostic probing."""
    hints: dict[str, Any] = {
        "is_national": False,
        "county_token": None,
        "city_token": None,
    }
    if not listing_url:
        return hints

    parsed = urlparse(str(listing_url))
    path = (parsed.path or "").lower()
    if "/property-for-sale/ireland" in path:
        hints["is_national"] = True

    county_match = re.search(r"-co-([a-z]+)", path)
    if county_match:
        hints["county_token"] = county_match.group(1)

    # Useful fallback when URL includes location slug without county marker.
    if not hints["county_token"]:
        parts = [part for part in path.split("/") if part]
        if len(parts) >= 3:
            slug = parts[-2]
            for token in slug.split("-"):
                if token and token not in {"for", "sale", "house", "apartment", "detached", "terraced"}:
                    hints["city_token"] = token
                    break

    return hints


def _target_matches_hints(target: dict[str, Any], hints: dict[str, Any]) -> bool:
    label = " ".join(
        [
            str(target.get("name") or ""),
            str(target.get("url") or ""),
            json.dumps(target.get("config") or {}, sort_keys=True),
        ]
    ).lower()
    county = str(hints.get("county_token") or "").strip().lower()
    city = str(hints.get("city_token") or "").strip().lower()

    if county and county in label:
        return True
    if city and city in label:
        return True
    if hints.get("is_national") and ("ireland" in label or "national" in label):
        return True
    return False


def _reorder_probe_targets(probe_targets: list[dict[str, Any]], *, hints: dict[str, Any]) -> list[dict[str, Any]]:
    """Prioritize likely matching regional sources before broad scans."""
    hinted = [target for target in probe_targets if _target_matches_hints(target, hints)]
    others = [target for target in probe_targets if target not in hinted]

    # Within each group, prefer enabled and persisted sources first.
    def _rank(target: dict[str, Any]) -> tuple[int, int, str]:
        enabled_rank = 0 if target.get("enabled") else 1
        persisted_rank = 0 if target.get("id") else 1
        label = str(target.get("name") or target.get("url") or "")
        return (enabled_rank, persisted_rank, label)

    hinted.sort(key=_rank)
    others.sort(key=_rank)
    return hinted + others


def _diagnostic_probe_stages(*, probe_max_pages: int, max_probe_sources: int) -> list[dict[str, int | str]]:
    """Build a progressive probe plan: fast targeted pass, then deeper passes if needed."""
    max_pages = max(5, int(probe_max_pages or 25))
    max_sources = max(1, int(max_probe_sources or 25))
    return [
        {
            "stage": "targeted_fast",
            "target_limit": min(max_sources, 6),
            "max_pages": min(max_pages, 12),
        },
        {
            "stage": "targeted_deep",
            "target_limit": min(max_sources, 4),
            "max_pages": min(max_pages, 40),
        },
        {
            "stage": "broad_deep",
            "target_limit": max_sources,
            "max_pages": max_pages,
        },
    ]


def _extract_listing_url_components(listing_url: str) -> dict[str, str | None]:
    parsed = urlparse(str(listing_url or "").strip())
    path = (parsed.path or "").strip().rstrip("/")
    parts = [part for part in path.split("/") if part]
    slug = parts[-2].lower() if len(parts) >= 2 else ""
    url_listing_id = parts[-1] if parts else ""
    county_match = re.search(r"-co-([a-z]+)", slug)
    county = county_match.group(1).lower() if county_match else None
    return {
        "slug": slug or None,
        "url_listing_id": url_listing_id or None,
        "county": county,
    }


def _sanitize_identifier_csv(value: str | None, *, limit: int = 12) -> list[str]:
    if not value:
        return []
    parts = [part.strip() for part in str(value).split(",")]
    out: list[str] = []
    for part in parts:
        if not part:
            continue
        # Keep numeric IDs only for consistent matching behavior.
        if not re.fullmatch(r"\d{4,}", part):
            continue
        if part not in out:
            out.append(part)
        if len(out) >= limit:
            break
    return out


def _resolve_identifier_aliases(
    *,
    external_id: str,
    listing_url: str | None,
    similar_ids: list[str] | None,
) -> list[str]:
    aliases: list[str] = []
    for candidate in [str(external_id).strip()] + list(similar_ids or []):
        if candidate and candidate not in aliases:
            aliases.append(candidate)

    if listing_url:
        comps = _extract_listing_url_components(listing_url)
        url_listing_id = str(comps.get("url_listing_id") or "").strip()
        if url_listing_id and url_listing_id not in aliases:
            aliases.append(url_listing_id)
    return aliases


def _probe_listing_page_metadata(listing_url: str | None) -> dict[str, Any] | None:
    """Try a lightweight listing page fetch to detect bot blocking and extract Daft ID if visible."""
    if not listing_url:
        return None
    normalized = str(listing_url).strip()
    if not normalized:
        return None
    try:
        with httpx.Client(timeout=10.0, follow_redirects=True) as client:
            response = client.get(normalized)
            html = response.text or ""
            title_match = re.search(r"<title>([^<]+)</title>", html, flags=re.IGNORECASE)
            page_title = title_match.group(1).strip() if title_match else ""
            daft_id_match = re.search(r"Daft ID:\s*(\d+)", html, flags=re.IGNORECASE)
            daft_id = daft_id_match.group(1) if daft_id_match else None
            bot_blocked = response.status_code in {403, 429} or "security check | daft" in html.lower()
            return {
                "url": str(response.url),
                "status_code": response.status_code,
                "page_title": page_title,
                "daft_id": daft_id,
                "bot_blocked": bot_blocked,
            }
    except Exception as exc:
        return {
            "url": normalized,
            "status_code": None,
            "page_title": None,
            "daft_id": None,
            "bot_blocked": False,
            "error": str(exc),
        }


def _raw_listing_matches_aliases(raw_listing: Any, *, adapter: Any, aliases: list[str]) -> bool:
    raw_data = getattr(raw_listing, "raw_data", None)
    source_url = getattr(raw_listing, "source_url", "")
    for alias in aliases:
        if adapter.listing_matches_identifier(
            raw_data=raw_data,
            source_url=source_url,
            external_id=alias,
        ):
            return True
    return False


def _raw_listing_matches_reverse_signature(
    raw_listing: Any,
    *,
    adapter: Any,
    external_id: str,
    slug: str | None,
    url_listing_id: str | None,
) -> bool:
    raw_data = getattr(raw_listing, "raw_data", None) or {}
    source_url = str(getattr(raw_listing, "source_url", "") or "")
    seo_path = str(raw_data.get("seoFriendlyPath") or "").strip().lower()
    normalized_url = adapter._normalize_listing_url(source_url).lower()

    if adapter.listing_matches_identifier(
        raw_data=raw_data,
        source_url=source_url,
        external_id=external_id,
    ):
        return True

    if slug and slug in seo_path:
        return True
    if slug and slug in normalized_url:
        return True
    if url_listing_id and f"/{url_listing_id}" in seo_path:
        return True
    if url_listing_id and f"/{url_listing_id}" in normalized_url:
        return True
    return False


def _reverse_probe_from_listing_url(
    *,
    listing_url: str,
    adapter: Any,
    external_id: str,
    probe_max_pages: int,
    bot_blocked: bool,
    run_async: Any,
) -> dict[str, Any]:
    from packages.sources.daft import AREA_SHAPE_MAP

    components = _extract_listing_url_components(listing_url)
    county = str(components.get("county") or "").strip().lower()
    slug = str(components.get("slug") or "").strip().lower() or None
    url_listing_id = str(components.get("url_listing_id") or "").strip() or None

    areas: list[str] = []
    if county and county in AREA_SHAPE_MAP:
        areas.append(county)
    if "ireland" not in areas:
        areas.append("ireland")

    max_pages = min(max(8, int(probe_max_pages or 25)), 12) if bot_blocked else max(25, int(probe_max_pages or 25))
    attempted_sources: list[dict[str, Any]] = []
    for area in areas:
        config = {
            "areas": [area],
            "max_pages": max_pages,
            "delay_seconds": 0,
            "max_retries": 2,
            "stale_page_threshold": 10,
            "tail_pass_pages": 2,
            "tail_pass_min_new_ids": 1,
            "history_tail_pass_pages": 0,
            "recent_listing_ids": [],
        }
        attempted_sources.append(
            {
                "name": f"reverse_url_probe:{area}",
                "url": listing_url,
                "enabled": False,
                "stage": "reverse_from_url",
                "max_pages": max_pages,
            }
        )
        listings = run_async(adapter.fetch_listings(config))
        for raw_listing in listings:
            if _raw_listing_matches_reverse_signature(
                raw_listing,
                adapter=adapter,
                external_id=external_id,
                slug=slug,
                url_listing_id=url_listing_id,
            ):
                return {
                    "matched_raw": raw_listing,
                    "matched_target": {
                        "id": None,
                        "name": f"Reverse URL Probe ({area})",
                        "url": listing_url,
                        "adapter_name": "daft",
                        "adapter_type": "api",
                        "enabled": False,
                        "config": config,
                        "tags": ["reverse_probe"],
                        "pending_approval": False,
                    },
                    "attempted_sources": attempted_sources,
                }

    return {
        "matched_raw": None,
        "matched_target": None,
        "attempted_sources": attempted_sources,
    }


def _reverse_probe_from_similar_ids(
    *,
    adapter: Any,
    external_id: str,
    similar_ids: list[str],
    probe_targets: list[dict[str, Any]],
    probe_max_pages: int,
    max_anchor_sources: int = 6,
    max_anchor_pages: int = 20,
    run_async: Any,
) -> dict[str, Any]:
    """Reverse-anchor probe: locate a known similar listing first, then search target in same source."""
    if not similar_ids:
        return {
            "matched_raw": None,
            "matched_target": None,
            "attempted_sources": [],
            "anchor": None,
        }

    anchor_target: dict[str, Any] | None = None
    anchor_raw: Any | None = None
    attempted_sources: list[dict[str, Any]] = []
    anchor_scan_pages = min(max(8, int(max_anchor_pages or 20)), max(8, int(probe_max_pages or 25)))

    for target in probe_targets[: max(1, int(max_anchor_sources or 6))]:
        config = {
            **(target.get("config") or {}),
            "delay_seconds": 0,
            "max_pages": anchor_scan_pages,
            "max_retries": 2,
            "stale_page_threshold": 8,
            "tail_pass_pages": 1,
            "tail_pass_min_new_ids": 1,
            "history_tail_pass_pages": 0,
            "recent_listing_ids": [],
        }
        attempted_sources.append(
            {
                "name": target.get("name"),
                "url": target.get("url"),
                "enabled": target.get("enabled"),
                "stage": "reverse_similar_anchor",
                "max_pages": anchor_scan_pages,
                "similar_ids": similar_ids,
            }
        )
        listings = run_async(adapter.fetch_listings(config))
        for raw in listings:
            raw_data = getattr(raw, "raw_data", None)
            raw_url = getattr(raw, "source_url", "")
            if any(
                adapter.listing_matches_identifier(raw_data=raw_data, source_url=raw_url, external_id=sid)
                for sid in similar_ids
            ):
                anchor_target = target
                anchor_raw = raw
                break
        if anchor_target is not None:
            break

    if anchor_target is None:
        return {
            "matched_raw": None,
            "matched_target": None,
            "attempted_sources": attempted_sources,
            "anchor": None,
        }

    deep_pages = max(anchor_scan_pages, min(int(probe_max_pages or 25), anchor_scan_pages + 10))
    deep_config = {
        **(anchor_target.get("config") or {}),
        "delay_seconds": 0,
        "max_pages": deep_pages,
        "max_retries": 2,
        "stale_page_threshold": 10,
        "tail_pass_pages": 2,
        "tail_pass_min_new_ids": 1,
        "history_tail_pass_pages": 0,
        "recent_listing_ids": [],
    }
    attempted_sources.append(
        {
            "name": anchor_target.get("name"),
            "url": anchor_target.get("url"),
            "enabled": anchor_target.get("enabled"),
            "stage": "reverse_similar_target_search",
            "max_pages": deep_pages,
            "anchor_similar_found": True,
        }
    )
    listings = run_async(adapter.fetch_listings(deep_config))
    for raw in listings:
        if adapter.listing_matches_identifier(
            raw_data=getattr(raw, "raw_data", None),
            source_url=getattr(raw, "source_url", ""),
            external_id=external_id,
        ):
            return {
                "matched_raw": raw,
                "matched_target": anchor_target,
                "attempted_sources": attempted_sources,
                "anchor": {
                    "target": anchor_target,
                    "similar_match_identifiers": sorted(
                        adapter.listing_identifiers(
                            getattr(anchor_raw, "raw_data", None),
                            getattr(anchor_raw, "source_url", ""),
                        )
                    ) if anchor_raw is not None else [],
                },
            }

    return {
        "matched_raw": None,
        "matched_target": anchor_target,
        "attempted_sources": attempted_sources,
        "anchor": {
            "target": anchor_target,
            "similar_match_identifiers": sorted(
                adapter.listing_identifiers(
                    getattr(anchor_raw, "raw_data", None),
                    getattr(anchor_raw, "source_url", ""),
                )
            ) if anchor_raw is not None else [],
        },
    }


def _filter_logs_for_identifier(rows: list[BackendLog], external_id: str) -> list[dict[str, Any]]:
    target = str(external_id or "").strip()
    matched: list[dict[str, Any]] = []
    for row in rows:
        context = row.context_json or {}
        haystack = " ".join(
            [
                str(row.message or ""),
                str(row.event_type or ""),
                json.dumps(context, sort_keys=True, default=str),
            ]
        )
        if target and target in haystack:
            matched.append(backend_log_to_dict(row))
    return matched


def _build_daft_probe_targets(db: Session) -> list[dict[str, Any]]:
    from packages.sources.discovery import canonicalize_source_url, load_discovery_candidates

    repo = SourceRepository(db)
    existing_sources = [source for source in repo.get_all(enabled_only=False) if getattr(source, "adapter_name", None) == "daft"]
    targets = [_source_to_dict(source) for source in existing_sources]
    existing_urls = {
        canonicalize_source_url(str(source.url or ""))
        for source in existing_sources
        if canonicalize_source_url(str(source.url or ""))
    }

    for candidate in load_discovery_candidates():
        if candidate.get("adapter_name") != "daft":
            continue
        candidate_url = canonicalize_source_url(str(candidate.get("url") or ""))
        if not candidate_url or candidate_url in existing_urls:
            continue
        targets.append(
            {
                "id": None,
                "name": candidate.get("name"),
                "url": candidate.get("url"),
                "adapter_name": "daft",
                "adapter_type": candidate.get("adapter_type") or "api",
                "enabled": False,
                "config": candidate.get("config") or {},
                "tags": list(candidate.get("tags") or []),
                "pending_approval": True,
            }
        )

    return sorted(targets, key=_candidate_priority)


def _upsert_repair_source(db: Session, target: dict[str, Any]) -> tuple[Source, str]:
    repo = SourceRepository(db)
    existing_source_id = target.get("id")
    if existing_source_id:
        source = repo.get_by_id(str(existing_source_id))
        if not source:
            raise AdminServiceError(f"Source {existing_source_id} not found during repair")
        tags = [tag for tag in list(source.tags or []) if tag != "pending_approval"]
        if "auto_repaired" not in tags:
            tags.append("auto_repaired")
        updated = repo.update(str(source.id), enabled=True, tags=tags)
        if not updated:
            raise AdminServiceError(f"Failed to update source {source.id} during repair")
        return updated, "enabled_existing_source"

    tags = [tag for tag in list(target.get("tags") or []) if tag != "pending_approval"]
    for tag in ["auto_discovered", "auto_repaired"]:
        if tag not in tags:
            tags.append(tag)
    created = repo.create(
        name=target.get("name") or f"Daft Repair {target.get('url')}",
        url=target.get("url"),
        adapter_type="api",
        adapter_name="daft",
        config=target.get("config") or {},
        enabled=True,
        poll_interval_seconds=21600,
        tags=tags,
    )
    return created, "created_source"


def _repair_daft_listing(db: Session, *, target: dict[str, Any], raw_listing: Any) -> dict[str, Any]:
    from apps.worker.tasks import _geocode_safe, _materialize_property_documents_safe, _run_async
    from packages.normalizer.normalizer import PropertyNormalizer
    from packages.sources.daft import DaftAdapter

    source, source_action = _upsert_repair_source(db, target)
    adapter = DaftAdapter()
    parsed = adapter.parse_listing(raw_listing)
    if not parsed:
        return {
            "status": "probe_found_but_parse_failed",
            "source_action": source_action,
            "source": _source_to_dict(source),
        }

    normalizer = PropertyNormalizer()
    property_repo = PropertyRepository(db)
    price_repo = PriceHistoryRepository(db)

    record = normalizer.normalize(parsed)
    existing = None
    external_id = record.get("external_id")
    if external_id:
        existing = property_repo.get_by_external_id_and_source(str(source.id), str(external_id))
    if not existing:
        existing = property_repo.get_by_content_hash(record["content_hash"])
    if not existing and record.get("url"):
        suffix = str(record["url"]).rstrip("/").split("/")[-1]
        url_matches = property_repo.list_by_url_suffix(f"/{suffix}") if suffix else []
        existing = url_matches[0] if url_matches else None

    if existing:
        return {
            "status": "already_present",
            "source_action": source_action,
            "source": _source_to_dict(source),
            "property": _property_to_dict(existing),
        }

    if not record.get("latitude"):
        geo = _run_async(_geocode_safe(record.get("address", ""), record.get("county")))
        if geo:
            record["latitude"] = geo.latitude
            record["longitude"] = geo.longitude

    record["source_id"] = str(source.id)
    record["status"] = "new"
    record["first_listed_at"] = datetime.now(UTC)
    try:
        created_property = property_repo.create(**record)
        created_property_id = str(created_property.id) if getattr(created_property, "id", None) else None
        _materialize_property_documents_safe(db, created_property_id)
        return {
            "status": "created_property",
            "source_action": source_action,
            "source": _source_to_dict(source),
            "property": _property_to_dict(created_property),
        }
    except IntegrityError:
        db.rollback()
        match = property_repo.get_by_content_hash(record["content_hash"])
        return {
            "status": "integrity_conflict",
            "source_action": source_action,
            "source": _source_to_dict(source),
            "property": _property_to_dict(match) if match else None,
        }


def _attempt_daft_scrape_fallback(
    db: Session,
    *,
    external_id: str,
    probe_targets: list[dict[str, Any]],
    max_sources: int = 6,
) -> dict[str, Any]:
    """Fallback recovery path: force-scrape likely Daft sources and re-check persistence."""
    from apps.worker.tasks import scrape_source

    property_repo = PropertyRepository(db)

    source_ids_enabled = [
        str(target.get("id"))
        for target in probe_targets
        if target.get("id") and target.get("enabled")
    ]
    source_ids_other = [
        str(target.get("id"))
        for target in probe_targets
        if target.get("id") and not target.get("enabled")
    ]
    ordered_source_ids = []
    seen: set[str] = set()
    for source_id in source_ids_enabled + source_ids_other:
        if source_id not in seen:
            seen.add(source_id)
            ordered_source_ids.append(source_id)
    source_ids = ordered_source_ids[: max(1, max_sources)]

    runs: list[dict[str, Any]] = []
    for source_id in source_ids:
        try:
            result = scrape_source(source_id, force=True)
            runs.append(
                {
                    "source_id": source_id,
                    "status": "ok",
                    "result": result,
                }
            )
        except Exception as exc:
            runs.append(
                {
                    "source_id": source_id,
                    "status": "error",
                    "error": str(exc),
                }
            )

    matched_props = [
        _property_to_dict(prop)
        for prop in property_repo.list_by_external_id(external_id)
        if getattr(getattr(prop, "source", None), "adapter_name", None) == "daft"
    ]
    matched_by_url = [
        _property_to_dict(prop)
        for prop in property_repo.list_by_url_suffix(f"/{external_id}")
        if getattr(getattr(prop, "source", None), "adapter_name", None) == "daft"
    ]

    return {
        "attempted": bool(source_ids),
        "attempted_source_ids": source_ids,
        "runs": runs,
        "found": bool(matched_props or matched_by_url),
        "matched_properties": matched_props,
        "matched_properties_by_url": matched_by_url,
    }


def _default_repair_target_for_daft(probe_targets: list[dict[str, Any]]) -> dict[str, Any]:
    for target in probe_targets:
        if target.get("id") and target.get("enabled"):
            return target
    for target in probe_targets:
        if target.get("id"):
            return target
    return {
        "id": None,
        "name": "Daft.ie Ireland (repair)",
        "url": "https://www.daft.ie/property-for-sale/ireland",
        "adapter_name": "daft",
        "adapter_type": "api",
        "enabled": False,
        "config": {"areas": ["ireland"], "max_pages": 5},
        "tags": ["auto_discovered", "auto_repaired"],
        "pending_approval": False,
    }


def _probe_daft_listing_url(*, listing_url: str, aliases: list[str]) -> Any | None:
    from packages.sources.base import RawListing
    from packages.sources.daft import DaftAdapter

    adapter = DaftAdapter()
    normalized_url = adapter._normalize_listing_url(listing_url)
    if not normalized_url:
        return None

    meta = _probe_listing_page_metadata(normalized_url)
    if not meta:
        return None
    if meta.get("bot_blocked"):
        return None
    if int(meta.get("status_code") or 0) < 200 or int(meta.get("status_code") or 0) >= 300:
        return None

    try:
        with httpx.Client(timeout=15.0, follow_redirects=True) as client:
            response = client.get(normalized_url)
            response.raise_for_status()
            html = response.text or ""
    except Exception:
        return None

    daft_id_match = re.search(r"Daft ID:\s*(\d+)", html, flags=re.IGNORECASE)
    daft_id = daft_id_match.group(1) if daft_id_match else ""
    parsed_url = urlparse(normalized_url)
    seo_path = parsed_url.path
    title_match = re.search(r'<meta\s+property="og:title"\s+content="([^"]+)"', html, flags=re.IGNORECASE)
    title = title_match.group(1).strip() if title_match else ""
    url_listing_id = adapter._extract_listing_id_from_url(normalized_url) or ""

    identifier_set = {value for value in aliases + [daft_id, url_listing_id] if value}
    if not identifier_set.intersection(set(aliases)):
        return None

    return RawListing(
        raw_html=html,
        raw_data={
            "id": daft_id or (aliases[0] if aliases else ""),
            "title": title,
            "seoFriendlyPath": seo_path,
            "url_listing_id": url_listing_id,
        },
        source_url=normalized_url,
        fetched_at=datetime.now(UTC),
    )


def diagnose_listing_by_external_id(
    db: Session,
    *,
    external_id: str,
    adapter_name: str = "daft",
    listing_url: str | None = None,
    similar_ids: str | None = None,
    repair: bool = False,
    hours: int = 168,
    log_limit: int = 500,
    max_probe_sources: int = 25,
    probe_max_pages: int = 25,
) -> dict[str, Any]:
    target_id = str(external_id or "").strip()
    if not target_id:
        raise AdminServiceError("external_id is required")

    property_repo = PropertyRepository(db)
    backend_repo = BackendLogRepository(db)

    sanitized_similar_ids = _sanitize_identifier_csv(similar_ids)
    page_probe = _probe_listing_page_metadata(listing_url)
    resolved_aliases = _resolve_identifier_aliases(
        external_id=target_id,
        listing_url=listing_url,
        similar_ids=sanitized_similar_ids,
    )
    page_daft_id = str((page_probe or {}).get("daft_id") or "").strip()
    if page_daft_id and page_daft_id not in resolved_aliases:
        resolved_aliases.append(page_daft_id)

    persisted_external_matches: list[dict[str, Any]] = []
    persisted_url_matches: list[dict[str, Any]] = []
    seen_property_ids: set[str] = set()
    for alias in resolved_aliases:
        for prop in property_repo.list_by_external_id(alias):
            if getattr(getattr(prop, "source", None), "adapter_name", None) != adapter_name:
                continue
            prop_id = str(getattr(prop, "id", ""))
            if prop_id and prop_id not in seen_property_ids:
                seen_property_ids.add(prop_id)
                persisted_external_matches.append(_property_to_dict(prop))
        for prop in property_repo.list_by_url_suffix(f"/{alias}"):
            if getattr(getattr(prop, "source", None), "adapter_name", None) != adapter_name:
                continue
            prop_id = str(getattr(prop, "id", ""))
            if prop_id and prop_id not in seen_property_ids:
                seen_property_ids.add(prop_id)
                persisted_url_matches.append(_property_to_dict(prop))

    recent_logs = _filter_logs_for_identifier(
        backend_repo.list_recent(hours=hours, limit=log_limit),
        target_id,
    )

    response: dict[str, Any] = {
        "external_id": target_id,
        "adapter_name": adapter_name,
        "identity_resolution": {
            "canonical": resolved_aliases[0] if resolved_aliases else target_id,
            "aliases": resolved_aliases,
            "listing_url": listing_url,
            "page_probe": page_probe,
        },
        "persisted_matches": persisted_external_matches,
        "persisted_url_matches": persisted_url_matches,
        "recent_logs": recent_logs,
        "probe": None,
        "diagnosis": {
            "status": "unknown",
            "reason": None,
            "recommended_action": None,
        },
        "repair": None,
    }

    if persisted_external_matches or persisted_url_matches:
        response["diagnosis"] = {
            "status": "already_present",
            "reason": "listing_already_persisted",
            "recommended_action": "no_repair_needed",
        }
        return response

    if adapter_name != "daft":
        response["diagnosis"] = {
            "status": "not_supported",
            "reason": "diagnostic_probe_only_implemented_for_daft",
            "recommended_action": "inspect_backend_logs",
        }
        return response

    from apps.worker.tasks import _run_async
    from packages.sources.daft import DaftAdapter

    adapter = DaftAdapter()

    if bool((page_probe or {}).get("bot_blocked")) and not sanitized_similar_ids and not repair:
        response["probe"] = {
            "matched": False,
            "attempted_sources": [],
        }
        response["diagnosis"] = {
            "status": "not_found_live",
            "reason": "bot_blocked_html_probe",
            "recommended_action": "provide_similar_ids_or_run_repair_fallback",
        }
        return response

    hints = _derive_daft_probe_hints(listing_url=listing_url, external_id=target_id)
    probe_targets = _build_daft_probe_targets(db)[: max(1, max_probe_sources)]
    probe_targets = _reorder_probe_targets(probe_targets, hints=hints)
    probe_stages = _diagnostic_probe_stages(
        probe_max_pages=probe_max_pages,
        max_probe_sources=max_probe_sources,
    )
    bot_blocked = bool((page_probe or {}).get("bot_blocked"))
    if bot_blocked:
        probe_stages = [
            {
                "stage": "bot_blocked_minimal",
                "target_limit": min(max(1, max_probe_sources), 3),
                "max_pages": min(max(5, probe_max_pages), 12),
            }
        ]
    matched_raw = None
    matched_target = None
    attempted_sources: list[dict[str, Any]] = []
    attempted_target_ids: set[str] = set()

    if sanitized_similar_ids:
        similar_probe = _reverse_probe_from_similar_ids(
            adapter=adapter,
            external_id=resolved_aliases[0] if resolved_aliases else target_id,
            similar_ids=sanitized_similar_ids,
            probe_targets=probe_targets,
            probe_max_pages=probe_max_pages,
            max_anchor_sources=3 if bot_blocked else 6,
            max_anchor_pages=12 if bot_blocked else 20,
            run_async=_run_async,
        )
        attempted_sources.extend(similar_probe.get("attempted_sources") or [])
        matched_raw = similar_probe.get("matched_raw")
        matched_target = similar_probe.get("matched_target")
        if similar_probe.get("anchor"):
            response["probe"] = {
                "matched": bool(matched_raw),
                "attempted_sources": attempted_sources,
                "reverse_anchor": similar_probe.get("anchor"),
                "similar_ids_used": sanitized_similar_ids,
            }

    if listing_url:
        reverse_result = _reverse_probe_from_listing_url(
            listing_url=listing_url,
            adapter=adapter,
            external_id=resolved_aliases[0] if resolved_aliases else target_id,
            probe_max_pages=probe_max_pages,
            bot_blocked=bot_blocked,
            run_async=_run_async,
        )
        attempted_sources.extend(reverse_result.get("attempted_sources") or [])
        if matched_raw is None:
            matched_raw = reverse_result.get("matched_raw")
            matched_target = reverse_result.get("matched_target")

    if matched_raw is None:
        for stage in probe_stages:
            stage_name = str(stage.get("stage") or "unknown")
            stage_target_limit = int(stage.get("target_limit") or 1)
            stage_max_pages = int(stage.get("max_pages") or 5)

            stage_targets: list[dict[str, Any]] = []
            for target in probe_targets:
                target_key = str(target.get("id") or target.get("url") or "")
                if target_key in attempted_target_ids:
                    continue
                stage_targets.append(target)
                if len(stage_targets) >= stage_target_limit:
                    break

            if not stage_targets:
                continue

            for target in stage_targets:
                configured_max_pages = 0
                try:
                    configured_max_pages = int((target.get("config") or {}).get("max_pages") or 0)
                except (TypeError, ValueError):
                    configured_max_pages = 0

                effective_probe_max_pages = max(configured_max_pages, stage_max_pages)
                probe_config = {
                    **(target.get("config") or {}),
                    "delay_seconds": 0,
                    "max_pages": effective_probe_max_pages,
                    "max_retries": 2,
                    "stale_page_threshold": 4 if stage_name == "bot_blocked_minimal" else (6 if stage_name == "targeted_fast" else 8),
                    "tail_pass_pages": 0 if stage_name == "bot_blocked_minimal" else (1 if stage_name == "targeted_fast" else 2),
                    "tail_pass_min_new_ids": 2,
                    "history_tail_pass_pages": 0,
                    "recent_listing_ids": [],
                }
                attempted_sources.append(
                    {
                        "name": target.get("name"),
                        "url": target.get("url"),
                        "enabled": target.get("enabled"),
                        "stage": stage_name,
                        "max_pages": effective_probe_max_pages,
                    }
                )
                target_key = str(target.get("id") or target.get("url") or "")
                if target_key:
                    attempted_target_ids.add(target_key)

                listings = _run_async(adapter.fetch_listings(probe_config))
                for raw_listing in listings:
                    if _raw_listing_matches_aliases(raw_listing, adapter=adapter, aliases=resolved_aliases):
                        matched_raw = raw_listing
                        matched_target = target
                        break
                if matched_raw is not None:
                    break
            if matched_raw is not None:
                break

    if matched_raw is None:
        fallback_target = _default_repair_target_for_daft(probe_targets)
        fallback_raw = None
        if listing_url:
            fallback_raw = _probe_daft_listing_url(listing_url=listing_url, aliases=resolved_aliases)
        if fallback_raw is not None:
            matched_raw = fallback_raw
            matched_target = fallback_target
            attempted_sources.append(
                {
                    "name": "direct_listing_url_probe",
                    "url": listing_url,
                    "enabled": False,
                }
            )
        else:
            scrape_fallback = None
            if repair:
                scrape_fallback = _attempt_daft_scrape_fallback(
                    db,
                    external_id=target_id,
                    probe_targets=probe_targets,
                )
            if scrape_fallback and scrape_fallback.get("found"):
                first_prop = (scrape_fallback.get("matched_properties") or scrape_fallback.get("matched_properties_by_url") or [None])[0]
                response["probe"] = {
                    "matched": False,
                    "attempted_sources": attempted_sources,
                    "scrape_fallback": scrape_fallback,
                }
                response["diagnosis"] = {
                    "status": "repaired",
                    "reason": "api_probe_missed_listing_recovered_via_scrape_fallback",
                    "recommended_action": "none",
                }
                response["repair"] = {
                    "status": "created_via_scrape_fallback",
                    "source_action": "fallback_scrape",
                    "source": None,
                    "property": first_prop,
                }
                return response

            response["probe"] = {
                "matched": False,
                "attempted_sources": attempted_sources,
                "scrape_fallback": scrape_fallback,
            }
            response["diagnosis"] = {
                "status": "not_found_live",
                "reason": (
                    "bot_blocked_html_probe"
                    if bool((page_probe or {}).get("bot_blocked"))
                    else "listing_not_in_current_probe_sources"
                ),
                "recommended_action": (
                    "retry_with_listing_url"
                    if not listing_url
                    else "expand_probe_or_verify_listing_still_live"
                ),
            }
            return response

    raw_data = getattr(matched_raw, "raw_data", None) or {}
    parsed = adapter.parse_listing(matched_raw)
    response["probe"] = {
        "matched": True,
        "attempted_sources": attempted_sources,
        "match_source": matched_target,
        "matched_identifiers": sorted(adapter.listing_identifiers(raw_data, getattr(matched_raw, "source_url", ""))),
        "listing_url": getattr(matched_raw, "source_url", None),
        "title": raw_data.get("title"),
        "api_id": str(raw_data.get("id", "")).strip() or None,
        "url_listing_id": adapter._extract_listing_id_from_url(getattr(matched_raw, "source_url", "")),
        "normalized_preview": {
            "external_id": getattr(parsed, "external_id", None),
            "url": getattr(parsed, "url", None),
            "address": getattr(parsed, "address", None),
            "price": getattr(parsed, "price", None),
            "county": getattr(parsed, "county", None),
        } if parsed else None,
    }
    response["diagnosis"] = {
        "status": "found_live_missing_from_store",
        "reason": "listing_available_via_daft_probe_but_not_persisted",
        "recommended_action": "repair_ingest_listing" if repair else "run_with_repair=true",
    }

    if repair:
        response["repair"] = _repair_daft_listing(db, target=matched_target, raw_listing=matched_raw)
        repair_status = str((response["repair"] or {}).get("status") or "")
        if repair_status in {"created_property", "already_present", "integrity_conflict"}:
            response["diagnosis"]["status"] = "repaired"
            response["diagnosis"]["recommended_action"] = "none"

    return response
