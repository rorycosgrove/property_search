"""Capture-rate reconciliation script.

Reads recent ``scrape_source_complete`` backend-log events and computes
rolling ingestion metrics per source.  Outputs a diagnostic table that
answers: "Is the system capturing listings at the expected rate?"

Usage:
    python scripts/dev/check_capture_rate.py
    python scripts/dev/check_capture_rate.py --hours 72 --min-runs 3
    python scripts/dev/check_capture_rate.py --source-id <uuid>

Exit codes:
    0  — all sources healthy (capture rate >= threshold, no sources stale)
    1  — one or more sources at risk (print warnings for operator)
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime, timedelta

# ---------------------------------------------------------------------------
# Thresholds (match docs/CORRECTNESS_CONTRACT.md)
# ---------------------------------------------------------------------------
CAPTURE_RATE_WARN_THRESHOLD = 0.95   # warn when new / total_fetched drops below 5%
STALE_MULTIPLIER = 1.5               # flag source if last success > 1.5× interval ago
HIGH_FAIL_RATE_THRESHOLD = 0.05      # parse failures above 5% of fetched = concern
HIGH_DEDUP_RATE_THRESHOLD = 0.10     # dedup conflicts above 10% of fetched = concern


def _load_env() -> None:
    """Best-effort .env loader so the script works standalone."""
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass


def _compute_capture_metrics(rows: list[dict]) -> dict:
    """Aggregate sourcelevel metrics across many scrape_source_complete rows."""
    total_fetched = sum(int(r.get("total_fetched") or 0) for r in rows)
    total_new = sum(int(r.get("new") or 0) for r in rows)
    total_updated = sum(int(r.get("updated") or 0) for r in rows)
    total_parse_failed = sum(int(r.get("parse_failed") or 0) for r in rows)
    total_price_unchanged = sum(int(r.get("price_unchanged") or 0) for r in rows)
    total_dedup = sum(int(r.get("dedup_conflicts") or 0) for r in rows)

    capture_rate = round(total_new / total_fetched, 4) if total_fetched else 0.0
    parse_fail_rate = round(total_parse_failed / total_fetched, 4) if total_fetched else 0.0
    dedup_rate = round(total_dedup / total_fetched, 4) if total_fetched else 0.0

    return {
        "runs": len(rows),
        "total_fetched": total_fetched,
        "total_new": total_new,
        "total_updated": total_updated,
        "total_parse_failed": total_parse_failed,
        "total_price_unchanged": total_price_unchanged,
        "total_dedup_conflicts": total_dedup,
        "capture_rate": capture_rate,
        "parse_fail_rate": parse_fail_rate,
        "dedup_rate": dedup_rate,
    }


def main(argv: list[str] | None = None) -> int:  # noqa: PLR0912
    parser = argparse.ArgumentParser(description="Compute ingestion capture-rate metrics.")
    parser.add_argument("--hours", type=int, default=168, help="Look-back window in hours (default: 168 = 7 days)")
    parser.add_argument("--min-runs", type=int, default=1, help="Minimum scrape runs to consider a source reportable")
    parser.add_argument("--source-id", type=str, default=None, help="Restrict to a specific source UUID")
    parser.add_argument("--json", action="store_true", help="Output raw JSON instead of table")
    args = parser.parse_args(argv)

    _load_env()

    try:
        from packages.storage.database import get_session
        from packages.storage.models import BackendLog, Source
        from sqlalchemy import and_
    except ImportError as exc:
        print(f"ERROR: Could not import backend modules — is the virtualenv active? ({exc})", file=sys.stderr)
        return 2

    cutoff = datetime.now(UTC) - timedelta(hours=args.hours)

    with get_session() as db:
        # --- pull scrape_source_complete events ---
        query = (
            db.query(BackendLog)
            .filter(
                BackendLog.event_type == "scrape_source_complete",
                BackendLog.created_at >= cutoff,
            )
        )
        if args.source_id:
            query = query.filter(BackendLog.source_id == args.source_id)
        log_rows = query.order_by(BackendLog.created_at.desc()).all()

        # --- pull enabled source metadata ---
        sources_by_id = {
            str(s.id): s
            for s in db.query(Source).all()
        }

    # --- group by source_id ---
    by_source: dict[str, list[dict]] = {}
    for row in log_rows:
        sid = str(row.source_id or "unknown")
        if sid not in by_source:
            by_source[sid] = []
        by_source[sid].append(row.context_json or {})

    report: list[dict] = []
    at_risk = False

    for sid, rows in by_source.items():
        if len(rows) < args.min_runs:
            continue
        metrics = _compute_capture_metrics(rows)

        source = sources_by_id.get(sid)
        source_name = source.name if source else sid
        interval = int((source.poll_interval_seconds if source else None) or 21600)
        last_success = source.last_success_at if source else None

        stale = False
        stale_seconds = None
        if last_success is not None:
            age = (datetime.now(UTC) - last_success).total_seconds()
            if age > interval * STALE_MULTIPLIER:
                stale = True
                stale_seconds = int(age)

        flags: list[str] = []
        if metrics["capture_rate"] < CAPTURE_RATE_WARN_THRESHOLD and metrics["total_fetched"] > 20:
            flags.append(f"LOW_CAPTURE_RATE ({metrics['capture_rate']:.1%})")
        if metrics["parse_fail_rate"] > HIGH_FAIL_RATE_THRESHOLD:
            flags.append(f"HIGH_PARSE_FAIL ({metrics['parse_fail_rate']:.1%})")
        if metrics["dedup_rate"] > HIGH_DEDUP_RATE_THRESHOLD:
            flags.append(f"HIGH_DEDUP ({metrics['dedup_rate']:.1%})")
        if stale:
            flags.append(f"STALE ({stale_seconds}s ago, limit {int(interval * STALE_MULTIPLIER)}s)")
        if source and not source.enabled:
            flags.append("DISABLED")

        if flags:
            at_risk = True

        report.append({
            "source_id": sid,
            "source_name": source_name,
            "enabled": bool(source.enabled) if source else None,
            **metrics,
            "stale": stale,
            "stale_seconds": stale_seconds,
            "last_success_at": last_success.isoformat() if last_success else None,
            "flags": flags,
        })

    report.sort(key=lambda r: (0 if r["flags"] else 1, r["source_name"]))

    if args.json:
        print(json.dumps({"generated_at": datetime.now(UTC).isoformat(), "report": report}, indent=2))
        return 1 if at_risk else 0

    # --- pretty table ---
    print(f"\nCapture Rate Report  |  window: {args.hours}h  |  {datetime.now(UTC).strftime('%Y-%m-%d %H:%M UTC')}")
    print("=" * 100)
    fmt = "{:<30}  {:>5}  {:>10}  {:>6}  {:>7}  {:>12}  {:>10}  {}"
    print(fmt.format("Source", "Runs", "Fetched", "New", "Updated", "CaptureRate", "ParseFail%", "Flags"))
    print("-" * 100)
    for r in report:
        flag_str = ", ".join(r["flags"]) if r["flags"] else "OK"
        print(fmt.format(
            r["source_name"][:30],
            r["runs"],
            r["total_fetched"],
            r["total_new"],
            r["total_updated"],
            f"{r['capture_rate']:.1%}",
            f"{r['parse_fail_rate']:.1%}",
            flag_str,
        ))

    if not report:
        print("  (no scrape runs found in the specified window)")

    print("=" * 100)
    if at_risk:
        print("\n⚠  One or more sources are at risk — see flagged rows above.")
    else:
        print("\n✓  All sources meet correctness thresholds.")
    print()

    return 1 if at_risk else 0


if __name__ == "__main__":
    sys.exit(main())
