"""
Worker tasks — property ingestion pipeline.

Pipeline: scrape → normalize → geocode → store → detect changes → alert → enrich (LLM)

Each task is idempotent and can be retried safely.
Tasks are invoked by SQS Lambda handlers (replacing Celery).
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any

from packages.shared.constants import (
    ALERT_CLEANUP_DAYS,
    LLM_BATCH_SIZE,
    NEARBY_SOLD_LIMIT,
    NEARBY_SOLD_RADIUS_KM,
    SOURCE_ERROR_THRESHOLD,
)
from packages.shared.logging import get_logger

logger = get_logger(__name__)


def _run_async(coro):
    """Helper to run async code in sync task functions."""
    return asyncio.run(coro)


# ── Source scraping tasks ─────────────────────────────────────────────────────


def scrape_all_sources() -> dict[str, Any]:
    """Scrape all enabled sources. Dispatches individual scrape tasks via SQS."""
    from packages.shared.queue import send_task
    from packages.storage.database import get_session
    from packages.storage.repositories import SourceRepository

    with get_session() as db:
        repo = SourceRepository(db)
        sources = repo.get_all(enabled_only=True)
        source_ids = [str(s.id) for s in sources]

    logger.info(f"Dispatching scrape for {len(source_ids)} sources")

    dispatched = 0
    for sid in source_ids:
        send_task("scrape", "scrape_source", {"source_id": sid})
        dispatched += 1

    return {"dispatched": dispatched}


def scrape_source(source_id: str) -> dict[str, Any]:
    """
    Scrape a single source and run the full ingestion pipeline.

    Pipeline: fetch → parse → normalize → geocode → store → detect changes
    """
    from packages.normalizer.normalizer import PropertyNormalizer
    from packages.sources.registry import get_adapter
    from packages.storage.database import get_session
    from packages.storage.repositories import (
        PriceHistoryRepository,
        PropertyRepository,
        SourceRepository,
    )

    with get_session() as db:
        source_repo = SourceRepository(db)
        property_repo = PropertyRepository(db)
        price_repo = PriceHistoryRepository(db)
        normalizer = PropertyNormalizer()

        source = source_repo.get_by_id(source_id)
        if not source:
            logger.error(f"Source {source_id} not found")
            return {"error": "Source not found"}

        if not source.enabled:
            return {"skipped": True, "reason": "Source disabled"}

        try:
            # 1. Fetch raw listings
            adapter = get_adapter(source.adapter_name)
            config = source.config or {}
            raw_listings = _run_async(adapter.fetch_listings(config))
            logger.info(f"Fetched {len(raw_listings)} listings from {source.name}")

            # 2. Parse + Normalize
            new_count = 0
            updated_count = 0
            skipped_count = 0

            for raw in raw_listings:
                parsed = adapter.parse_listing(raw)
                if not parsed:
                    skipped_count += 1
                    continue

                # Check if this is a PPR record (sold property)
                if parsed.raw_data.get("ppr_record"):
                    try:
                        _handle_ppr_record(db, parsed)
                        db.flush()
                        new_count += 1
                    except Exception:
                        db.rollback()
                    continue

                # Normalize
                record = normalizer.normalize(parsed)

                # 3. Check for existing property (dedup by content_hash)
                existing = property_repo.get_by_content_hash(record["content_hash"])

                if existing:
                    # Check for price change
                    if record.get("price") and existing.price:
                        new_price = float(record["price"])
                        old_price = float(existing.price)
                        if abs(new_price - old_price) > 0.01:
                            change = new_price - old_price
                            change_pct = (change / old_price * 100) if old_price else 0
                            price_repo.add_entry(
                                property_id=str(existing.id),
                                price=new_price,
                                price_change=change,
                                price_change_pct=change_pct,
                            )

                            # Update property price
                            property_repo.update(str(existing.id),
                                price=new_price,
                                status="price_changed",
                            )
                            updated_count += 1
                        else:
                            skipped_count += 1
                    else:
                        skipped_count += 1
                else:
                    # 4. Geocode if no lat/lng
                    if not record.get("latitude"):
                        geo = _run_async(
                            _geocode_safe(record.get("address", ""), record.get("county"))
                        )
                        if geo:
                            record["latitude"] = geo.latitude
                            record["longitude"] = geo.longitude

                    # 5. Store new property
                    record["source_id"] = source_id
                    record["status"] = "new"
                    record["first_listed_at"] = datetime.now(timezone.utc)
                    property_repo.create(**record)
                    new_count += 1

            # Mark source as successfully polled
            source_repo.mark_poll_success(source_id, new_count + updated_count)

            result = {
                "source_id": source_id,
                "source_name": source.name,
                "new": new_count,
                "updated": updated_count,
                "skipped": skipped_count,
                "total_fetched": len(raw_listings),
            }

            logger.info(f"Scrape complete: {result}")

            # 6. Dispatch alert evaluation for new/changed properties
            if new_count > 0 or updated_count > 0:
                from packages.shared.queue import send_task
                send_task("alert", "evaluate_alerts", {})

            return result

        except Exception as exc:
            logger.error(f"Scrape failed for {source.name}: {exc}")
            # Use existing session for error marking
            try:
                source_repo.mark_poll_error(source_id, str(exc))
                db.commit()
            except Exception as mark_err:
                logger.warning(f"Failed to persist scrape error status: {mark_err}")
            raise


# ── PPR import ────────────────────────────────────────────────────────────────


def import_ppr() -> dict[str, Any]:
    """Import Property Price Register data."""
    from packages.sources.ppr import PPRAdapter
    from packages.storage.database import get_session
    from packages.storage.repositories import SoldPropertyRepository

    adapter = PPRAdapter()
    config = {"min_year": datetime.now().year - 2}

    raw_listings = _run_async(adapter.fetch_listings(config))
    logger.info(f"PPR: downloaded {len(raw_listings)} records")

    with get_session() as db:
        sold_repo = SoldPropertyRepository(db)
        new_count = 0

        for raw in raw_listings:
            parsed = adapter.parse_listing(raw)
            if not parsed:
                continue

            content_hash = parsed.raw_data.get("content_hash", "")
            if sold_repo.get_by_content_hash(content_hash):
                continue

            _handle_ppr_record(db, parsed)
            db.flush()
            new_count += 1

        db.commit()

    return {"total_downloaded": len(raw_listings), "new_records": new_count}


# ── Alert evaluation ──────────────────────────────────────────────────────────


def evaluate_alerts() -> dict[str, int]:
    """Evaluate all saved searches and price changes for alerts."""
    from packages.alerts.engine import AlertEngine
    from packages.storage.database import get_session

    with get_session() as db:
        engine = AlertEngine(db)
        search_alerts = engine.evaluate_all()
        price_alerts = engine.check_price_changes()
        db.commit()

    return {"search_alerts": search_alerts, "price_alerts": price_alerts}


# ── LLM enrichment tasks ─────────────────────────────────────────────────────


def enrich_property_llm(property_id: str) -> dict[str, Any]:
    """Enrich a single property using LLM analysis."""
    from packages.ai.service import enrich_property
    from packages.storage.database import get_session
    from packages.storage.repositories import (
        LLMEnrichmentRepository,
        PropertyRepository,
        SoldPropertyRepository,
    )

    with get_session() as db:
        prop_repo = PropertyRepository(db)
        sold_repo = SoldPropertyRepository(db)
        enrichment_repo = LLMEnrichmentRepository(db)

        prop = prop_repo.get_by_id(property_id)
        if not prop:
            return {"error": "Property not found"}

        # Get nearby sold properties for context
        nearby_sold = []
        if prop.latitude and prop.longitude:
            sold_props = sold_repo.get_nearby_sold(
                lat=prop.latitude,
                lng=prop.longitude,
                radius_km=NEARBY_SOLD_RADIUS_KM,
                limit=NEARBY_SOLD_LIMIT,
            )
            nearby_sold = [
                {
                    "address": s.address,
                    "price": float(s.price) if s.price else 0,
                    "sale_date": s.sale_date.isoformat() if s.sale_date else "",
                }
                for s in sold_props
            ]

        # Build property data dict
        property_data = {
            "title": prop.title,
            "address": prop.address,
            "county": prop.county,
            "price": float(prop.price) if prop.price else None,
            "property_type": prop.property_type,
            "bedrooms": prop.bedrooms,
            "bathrooms": prop.bathrooms,
            "floor_area_sqm": prop.floor_area_sqm,
            "ber_rating": prop.ber_rating,
            "description": prop.description,
        }

        try:
            result = _run_async(enrich_property(property_data, nearby_sold))
            enrichment_repo.upsert(property_id, result)
            db.commit()
            return {"property_id": property_id, "enriched": True}
        except Exception as exc:
            logger.error(f"LLM enrichment failed: {exc}")
            raise


def enrich_batch_llm(limit: int = LLM_BATCH_SIZE) -> dict[str, Any]:
    """Enrich a batch of un-enriched properties."""
    from packages.shared.queue import send_task
    from packages.storage.database import get_session
    from packages.storage.models import LLMEnrichment, Property

    with get_session() as db:
        # Find properties without enrichment
        enriched_ids = db.query(LLMEnrichment.property_id).subquery()
        unenriched = (
            db.query(Property.id)
            .filter(~Property.id.in_(enriched_ids))
            .order_by(Property.first_listed_at.desc())
            .limit(limit)
            .all()
        )

    dispatched = 0
    for p in unenriched:
        send_task("llm", "enrich_property_llm", {"property_id": str(p.id)})
        dispatched += 1

    return {"dispatched": dispatched}


# ── Cleanup tasks ─────────────────────────────────────────────────────────────


def cleanup_old_alerts(days: int = ALERT_CLEANUP_DAYS) -> dict[str, int]:
    """Remove acknowledged alerts older than N days."""
    from packages.storage.database import get_session
    from packages.storage.models import Alert

    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    with get_session() as db:
        deleted = (
            db.query(Alert)
            .filter(Alert.acknowledged.is_(True), Alert.created_at < cutoff)
            .delete(synchronize_session=False)
        )
        db.commit()

    return {"deleted": deleted}


# ── Private helpers ───────────────────────────────────────────────────────────


async def _geocode_safe(address: str, county: str | None) -> Any:
    """Geocode with error handling."""
    try:
        from packages.normalizer.geocoder import geocode_address
        return await geocode_address(address, county)
    except Exception:
        return None


def _handle_ppr_record(db, parsed) -> None:
    """Insert a parsed PPR record into the SoldProperty table."""
    from packages.storage.repositories import SoldPropertyRepository

    # Skip records without a valid price (NOT NULL constraint on sold_properties)
    if parsed.price is None:
        return

    repo = SoldPropertyRepository(db)
    raw = parsed.raw_data

    repo.create(
        address=parsed.address,
        county=parsed.county,
        price=parsed.price,
        sale_date=raw.get("sale_date"),
        is_new=raw.get("is_new", False),
        is_full_market_price=raw.get("is_full_market_price", True),
        vat_exclusive=raw.get("vat_exclusive", False),
        property_size_description=raw.get("property_size_description"),
        content_hash=raw.get("content_hash", ""),
    )
