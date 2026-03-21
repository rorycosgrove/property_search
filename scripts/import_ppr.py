"""Standalone PPR import script. Can run outside Celery."""
import sys
import os
import asyncio
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from packages.storage.database import get_session
from packages.storage.models import SoldProperty
from packages.sources.ppr import PPRAdapter
from packages.shared.config import get_settings
from packages.shared.logging import get_logger

logger = get_logger(__name__)


async def _import_ppr(years: int = 2) -> int:
    adapter = PPRAdapter()
    config = {"min_year": datetime.now().year - years}
    raw_listings = await adapter.fetch_listings(config)
    logger.info("fetched_ppr_records", count=len(raw_listings))

    imported = 0
    with get_session() as session:
        existing_hashes = {
            row[0]
            for row in session.query(SoldProperty.content_hash).all()
            if row[0]
        }


        for raw in raw_listings:
            normalized = adapter.parse_listing(raw)
            if not normalized:
                continue
            # Skip if price is missing or invalid
            if normalized.price is None:
                logger.debug("ppr_import_skipped_missing_price", address=normalized.address)
                continue
            c_hash = normalized.raw_data.get("content_hash", "")
            if c_hash in existing_hashes:
                continue

            sold = SoldProperty(
                address=normalized.address,
                county=normalized.county,
                price=normalized.price,
                sale_date=normalized.raw_data.get("sale_date"),
                is_new=normalized.raw_data.get("not_full_market_price", False) is False,
                content_hash=c_hash,
            )
            session.add(sold)
            imported += 1

            if imported % 2000 == 0:
                session.flush()
                logger.info("ppr_progress", imported=imported)

        session.commit()

    logger.info("ppr_import_complete", imported=imported)
    return imported


def main():
    years = int(sys.argv[1]) if len(sys.argv) > 1 else 2
    print(f"Importing PPR data ({years} year(s))...")
    count = asyncio.run(_import_ppr(years))
    print(f"Done. Imported {count} record(s).")


if __name__ == "__main__":
    main()
