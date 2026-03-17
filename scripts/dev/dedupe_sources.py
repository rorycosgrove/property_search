"""Deduplicate source rows by canonical URL.

Usage:
  python scripts/dev/dedupe_sources.py --dry-run
  python scripts/dev/dedupe_sources.py --apply

Behavior:
- Groups sources by canonical URL (`packages.sources.discovery.canonicalize_source_url`).
- Chooses one keeper per group (prefer enabled, then earliest created_at).
- Reassigns properties from duplicate source IDs to keeper source ID.
- Deletes duplicate source rows.
"""

from __future__ import annotations

import argparse
from collections import defaultdict
from dataclasses import dataclass

from packages.sources.discovery import source_identity_key
from packages.storage.database import get_session
from packages.storage.models import Property, Source


@dataclass
class SourceRow:
    id: str
    adapter_name: str
    url: str
    enabled: bool
    created_at: object


@dataclass
class GroupPlan:
    canonical_url: str
    keeper_id: str
    duplicate_ids: list[str]


def _pick_keeper(sources: list[SourceRow]) -> SourceRow:
    """Pick deterministic keeper: enabled first, then oldest created_at."""
    return sorted(
        sources,
        key=lambda s: (
            0 if bool(s.enabled) else 1,
            s.created_at or 0,
            s.id,
        ),
    )[0]


def _build_plan(all_sources: list[SourceRow]) -> list[GroupPlan]:
    grouped: dict[str, list[SourceRow]] = defaultdict(list)
    for source in all_sources:
        key = source_identity_key(source.adapter_name, str(source.url or ""))
        if not key:
            continue
        grouped[key].append(source)

    plan: list[GroupPlan] = []
    for canonical_url, sources in grouped.items():
        if len(sources) <= 1:
            continue
        keeper = _pick_keeper(sources)
        dupes = [s.id for s in sources if s.id != keeper.id]
        if dupes:
            plan.append(GroupPlan(canonical_url=canonical_url, keeper_id=str(keeper.id), duplicate_ids=dupes))

    return sorted(plan, key=lambda p: p.canonical_url)


def _print_plan(plan: list[GroupPlan]) -> None:
    if not plan:
        print("No duplicate canonical source URLs found.")
        return

    print(f"Found {len(plan)} duplicate canonical source group(s):")
    for item in plan:
        print(f"- {item.canonical_url}")
        print(f"  keeper: {item.keeper_id}")
        print(f"  duplicates: {', '.join(item.duplicate_ids)}")


def _apply_plan(plan: list[GroupPlan]) -> tuple[int, int]:
    moved_properties = 0
    deleted_sources = 0

    if not plan:
        return moved_properties, deleted_sources

    with get_session() as db:
        for item in plan:
            for duplicate_id in item.duplicate_ids:
                moved = (
                    db.query(Property)
                    .filter(Property.source_id == duplicate_id)
                    .update({Property.source_id: item.keeper_id}, synchronize_session=False)
                )
                moved_properties += int(moved or 0)

                source = db.get(Source, duplicate_id)
                if source:
                    db.delete(source)
                    deleted_sources += 1

        db.commit()

    return moved_properties, deleted_sources


def main() -> int:
    parser = argparse.ArgumentParser(description="Deduplicate source records by canonical URL")
    parser.add_argument("--apply", action="store_true", help="Apply dedupe changes")
    parser.add_argument("--dry-run", action="store_true", help="Print dedupe plan only")
    args = parser.parse_args()

    with get_session() as db:
        all_sources = [
            SourceRow(
                id=str(s.id),
                adapter_name=str(s.adapter_name or ""),
                url=str(s.url or ""),
                enabled=bool(s.enabled),
                created_at=s.created_at,
            )
            for s in db.query(Source).all()
        ]

    plan = _build_plan(all_sources)
    _print_plan(plan)

    if args.dry_run or not args.apply:
        print("Dry run complete. Use --apply to execute changes.")
        return 0

    moved_properties, deleted_sources = _apply_plan(plan)
    print(f"Applied dedupe: moved_properties={moved_properties}, deleted_sources={deleted_sources}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
