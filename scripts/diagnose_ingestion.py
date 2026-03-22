#!/usr/bin/env python
"""Diagnose ingestion pipeline status and recent activity."""

from datetime import datetime, UTC
from packages.storage.database import get_db_session
from packages.storage.repositories import (
    PropertyRepository,
    SourceRepository,
    BackendLogRepository,
)


def main():
    db = next(get_db_session())

    # Check property counts by status
    prop_repo = PropertyRepository(db)
    stats = prop_repo.get_stats()
    print("=== Property Stats ===")
    print(f"Total: {stats['total']}")
    print(f"Avg Price: {stats['avg_price']}")

    # Check recent backend logs
    log_repo = BackendLogRepository(db)
    recent_errors = log_repo.list_recent_errors(hours=24, limit=20)
    print("\n=== Recent Errors (last 24h) ===")
    if recent_errors:
        for log in recent_errors[:10]:
            print(f"{log.created_at} [{log.level}] {log.event_type}: {log.message[:100]}")
    else:
        print("No errors found")

    # Check source status
    src_repo = SourceRepository(db)
    sources = src_repo.get_all(enabled_only=True)
    print(f"\n=== Enabled Sources ({len(sources)}) ===")
    now = datetime.now(UTC)
    for src in sources:
        if src.last_polled_at:
            delta = (now - src.last_polled_at).total_seconds() / 3600
            interval_hours = (src.poll_interval_seconds or 900) / 3600
            status = "STALE" if delta > interval_hours else "OK"
            print(
                f"{src.name}: last_polled={delta:.1f}h ago [{status}], "
                f"errors={src.error_count}, total_listings={src.total_listings}"
            )
        else:
            print(f"{src.name}: NEVER POLLED")

    # Check recent scrape activity
    recent_logs = log_repo.list_recent(hours=24, limit=30, event_type="property_created")
    print(f"\n=== Recent Property Creations (last 24h) ===")
    if recent_logs:
        print(f"Found {len(recent_logs)} creation events")
        for log in recent_logs[:5]:
            print(f"  {log.created_at}: {log.message[:80]}")
    else:
        print("No property creations found in last 24h")

    db.close()


if __name__ == "__main__":
    main()
