"""Backfill persisted address matching fields for properties and sold properties."""

from __future__ import annotations

from packages.shared.logging import get_logger
from packages.shared.utils import fuzzy_address_hash, normalize_address
from packages.storage.database import get_session
from packages.storage.models import Property, SoldProperty

logger = get_logger(__name__)


BATCH_SIZE = 2000


def _normalized(address: str | None) -> str | None:
    if not address:
        return None
    return normalize_address(address).lower()


def backfill_properties() -> int:
    updated = 0
    with get_session() as session:
        rows = (
            session.query(Property)
            .filter(
                (Property.address_normalized.is_(None))
                | (Property.fuzzy_address_hash.is_(None))
            )
            .yield_per(BATCH_SIZE)
        )

        for row in rows:
            row.address_normalized = _normalized(row.address)
            row.fuzzy_address_hash = fuzzy_address_hash(row.address or "") if row.address else None
            updated += 1

            if updated % BATCH_SIZE == 0:
                session.flush()
                logger.info("backfill_properties_progress", updated=updated)

    logger.info("backfill_properties_done", updated=updated)
    return updated


def backfill_sold_properties() -> int:
    updated = 0
    with get_session() as session:
        rows = (
            session.query(SoldProperty)
            .filter(
                (SoldProperty.address_normalized.is_(None))
                | (SoldProperty.fuzzy_address_hash.is_(None))
            )
            .yield_per(BATCH_SIZE)
        )

        for row in rows:
            row.address_normalized = _normalized(row.address)
            row.fuzzy_address_hash = fuzzy_address_hash(row.address or "") if row.address else None
            updated += 1

            if updated % BATCH_SIZE == 0:
                session.flush()
                logger.info("backfill_sold_properties_progress", updated=updated)

    logger.info("backfill_sold_properties_done", updated=updated)
    return updated


def main() -> None:
    print("Backfilling address match fields...")
    prop_count = backfill_properties()
    sold_count = backfill_sold_properties()
    print(f"Done. properties={prop_count} sold_properties={sold_count}")


if __name__ == "__main__":
    main()
