"""
Worker tasks — property ingestion pipeline.

Pipeline: scrape → normalize → geocode → store → detect changes → alert → enrich (LLM)

Each task is idempotent and can be retried safely.
Tasks are invoked by SQS Lambda handlers (replacing Celery).
"""

from __future__ import annotations

import asyncio
import os
from contextlib import nullcontext
from datetime import UTC, date, datetime, timedelta
from typing import Any

from sqlalchemy.exc import IntegrityError

from packages.shared.constants import (
    ALERT_CLEANUP_DAYS,
    LLM_BATCH_SIZE,
    NEARBY_SOLD_LIMIT,
    NEARBY_SOLD_RADIUS_KM,
)
from packages.shared.config import settings
from packages.shared.logging import get_logger

logger = get_logger(__name__)


def _run_async(coro):
    """Helper to run async code in sync task functions."""
    try:
        # This worker module is synchronous, so asyncio.run is the safest lifecycle.
        return asyncio.run(coro)
    except RuntimeError as exc:
        raise RuntimeError("Cannot run async task from an active event loop") from exc


def _is_queue_configured(queue_name: str) -> bool:
    """Return True when queue URL is configured in process env vars."""
    env_url = os.environ.get(f"{queue_name.upper()}_QUEUE_URL", "")
    return bool(env_url)


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    value = raw.strip().lower()
    if value in {"1", "true", "yes", "on"}:
        return True
    if value in {"0", "false", "no", "off"}:
        return False
    return default


def _env_int(name: str, default: int, minimum: int = 1, maximum: int = 200) -> int:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        parsed = int(raw)
    except ValueError:
        return default
    return max(minimum, min(parsed, maximum))


def _nested_tx_or_noop(db: Any):
    """Use SAVEPOINT when available, otherwise no-op context (test doubles)."""
    begin_nested = getattr(db, "begin_nested", None)
    if callable(begin_nested):
        return begin_nested()
    return nullcontext()


# ── Source scraping tasks ─────────────────────────────────────────────────────


def scrape_all_sources() -> dict[str, Any]:
    """Scrape all enabled sources.

    In cloud environments this dispatches SQS scrape tasks. In local environments
    without SQS queue URLs, it runs sources inline for easier development.
    """
    from packages.shared.queue import send_task
    from packages.storage.database import get_session
    from packages.storage.repositories import SourceRepository

    discovery_enabled = _env_bool("DISCOVERY_DURING_SCRAPE_ENABLED", True)
    discovery_auto_enable = _env_bool("DISCOVERY_DURING_SCRAPE_AUTO_ENABLE", False)
    discovery_limit = _env_int("DISCOVERY_DURING_SCRAPE_LIMIT", 10)

    discovery_summary: dict[str, Any] = {
        "created": 0,
        "existing": 0,
        "skipped_invalid": 0,
        "auto_enable": discovery_auto_enable,
        "enabled": discovery_enabled,
        "limit": discovery_limit,
    }
    if discovery_enabled:
        try:
            discovery_summary = {
                **discovery_summary,
                **discover_sources(auto_enable=discovery_auto_enable, limit=discovery_limit),
            }
            logger.info("discovery_during_scrape_complete", **discovery_summary)
        except Exception as exc:
            discovery_summary = {
                **discovery_summary,
                "error": str(exc),
            }
            logger.warning("discovery_during_scrape_failed", error=str(exc))

    with get_session() as db:
        repo = SourceRepository(db)
        sources = repo.get_all(enabled_only=True)
        source_ids = [str(s.id) for s in sources]

    logger.info(f"Dispatching scrape for {len(source_ids)} sources")

    dispatched = 0
    processed_inline = 0
    use_sqs_dispatch = _is_queue_configured("scrape")

    if not use_sqs_dispatch:
        logger.warning(
            "scrape_queue_not_configured",
            message="SCRAPE_QUEUE_URL missing; running scrape_source inline",
        )

    for sid in source_ids:
        if use_sqs_dispatch:
            send_task("scrape", "scrape_source", {"source_id": sid})
        else:
            scrape_source(sid)
            processed_inline += 1
        dispatched += 1

    return {
        "dispatched": dispatched,
        "processed_inline": processed_inline,
        "dispatch_mode": "sqs" if use_sqs_dispatch else "inline",
        "discovery_during_scrape": discovery_summary,
    }


def discover_sources(auto_enable: bool = False, limit: int = 25) -> dict[str, Any]:
    """Discover default and configured feed candidates and add missing sources.

    Sources are created disabled by default and require approval unless
    `auto_enable=True` is passed.
    """
    from packages.sources.discovery import load_discovery_candidates
    from packages.sources.registry import get_adapter_names
    from packages.storage.database import get_session
    from packages.storage.repositories import SourceRepository

    adapter_names = set(get_adapter_names())
    created = 0
    existing = 0
    skipped_invalid = 0

    with get_session() as db:
        repo = SourceRepository(db)
        for candidate in load_discovery_candidates()[: max(limit, 1)]:
            adapter_name = candidate.get("adapter_name")
            url = candidate.get("url")

            if adapter_name not in adapter_names or not url:
                skipped_invalid += 1
                continue

            if repo.get_by_url(url):
                existing += 1
                continue

            tags = list(candidate.get("tags") or [])
            if "auto_discovered" not in tags:
                tags.append("auto_discovered")
            if not auto_enable and "pending_approval" not in tags:
                tags.append("pending_approval")

            repo.create(
                name=candidate.get("name") or f"Discovered {adapter_name}",
                url=url,
                adapter_type=candidate.get("adapter_type") or "scraper",
                adapter_name=adapter_name,
                config=candidate.get("config") or {},
                enabled=auto_enable,
                poll_interval_seconds=int(candidate.get("poll_interval_seconds") or 21600),
                tags=tags,
            )
            created += 1

    result = {
        "created": created,
        "existing": existing,
        "skipped_invalid": skipped_invalid,
        "auto_enable": auto_enable,
    }
    logger.info("source_discovery_complete", **result)
    return result


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

        source = source_repo.get_by_id(source_id)
        if not source:
            logger.error(f"Source {source_id} not found")
            return {"error": "Source not found"}

        if not source.enabled:
            return {"skipped": True, "reason": "Source disabled"}

        if source_repo.should_skip_poll(source):
            logger.info(
                "source_poll_interval_skip",
                source_id=source_id,
                poll_interval_seconds=source.poll_interval_seconds,
            )
            logger.info(
                "scrape_redundancy_metrics",
                source_id=source_id,
                source_name=source.name,
                skip_reason="poll_interval_not_elapsed",
                skipped_count=1,
                dedup_conflicts=0,
            )
            return {
                "source_id": source_id,
                "source_name": source.name,
                "skipped": True,
                "reason": "poll_interval_not_elapsed",
            }

        if not source_repo.try_acquire_scrape_lock(source_id):
            logger.info("source_in_flight_skip", source_id=source_id)
            logger.info(
                "scrape_redundancy_metrics",
                source_id=source_id,
                source_name=source.name,
                skip_reason="source_in_flight",
                skipped_count=1,
                dedup_conflicts=0,
            )
            return {
                "source_id": source_id,
                "source_name": source.name,
                "skipped": True,
                "reason": "source_in_flight",
            }

        property_repo = PropertyRepository(db)
        price_repo = PriceHistoryRepository(db)
        normalizer = PropertyNormalizer()

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
            dedup_conflict_count = 0

            for raw in raw_listings:
                parsed = adapter.parse_listing(raw)
                if not parsed:
                    skipped_count += 1
                    continue

                # Check if this is a PPR record (sold property)
                if parsed.raw_data.get("ppr_record"):
                    try:
                        with _nested_tx_or_noop(db):
                            inserted = _handle_ppr_record(db, parsed)
                        if inserted:
                            new_count += 1
                        else:
                            skipped_count += 1
                    except Exception as exc:
                        skipped_count += 1
                        logger.warning("ppr_record_insert_failed", source_id=source_id, error=str(exc))
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
                            price_repo.add_entry_if_new_price(
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
                    record["first_listed_at"] = datetime.now(UTC)
                    try:
                        with _nested_tx_or_noop(db):
                            property_repo.create(**record)
                        new_count += 1
                    except IntegrityError:
                        # Another concurrent scrape inserted this listing first.
                        skipped_count += 1
                        dedup_conflict_count += 1
                        logger.info(
                            "property_dedup_conflict_skipped",
                            source_id=source_id,
                            content_hash=record.get("content_hash"),
                        )

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
            logger.info(
                "scrape_redundancy_metrics",
                source_id=source_id,
                source_name=source.name,
                skip_reason="none",
                skipped_count=skipped_count,
                dedup_conflicts=dedup_conflict_count,
                new_count=new_count,
                updated_count=updated_count,
            )

            # 6. Dispatch alert evaluation for new/changed properties
            if new_count > 0 or updated_count > 0:
                from packages.shared.queue import send_task

                if _is_queue_configured("alert"):
                    send_task("alert", "evaluate_alerts", {})
                else:
                    logger.warning(
                        "alert_queue_not_configured",
                        source_id=source_id,
                        new=new_count,
                        updated=updated_count,
                    )

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
        duplicate_count = 0
        skipped_invalid_count = 0
        failed_count = 0

        for raw in raw_listings:
            parsed = adapter.parse_listing(raw)
            if not parsed:
                skipped_invalid_count += 1
                continue

            content_hash = parsed.raw_data.get("content_hash", "")
            if sold_repo.get_by_content_hash(content_hash):
                duplicate_count += 1
                continue

            try:
                with db.begin_nested():
                    inserted = _handle_ppr_record(db, parsed)
                if inserted:
                    new_count += 1
                else:
                    skipped_invalid_count += 1
            except Exception as exc:
                failed_count += 1
                logger.warning("ppr_import_record_failed", error=str(exc))

    return {
        "total_downloaded": len(raw_listings),
        "new_records": new_count,
        "duplicates": duplicate_count,
        "skipped_invalid": skipped_invalid_count,
        "failed": failed_count,
    }


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

    if not settings.llm_enabled:
        logger.warning("llm_enrichment_skipped", reason="llm_disabled", property_id=property_id)
        return {"property_id": property_id, "enriched": False, "reason": "llm_disabled"}

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

    if not settings.llm_enabled:
        logger.warning("llm_batch_skipped", reason="llm_disabled", limit=limit)
        return {"dispatched": 0, "reason": "llm_disabled"}

    if not _is_queue_configured("llm"):
        logger.warning("llm_batch_skipped", reason="llm_queue_unconfigured", limit=limit)
        return {"dispatched": 0, "reason": "llm_queue_unconfigured"}

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

    cutoff = datetime.now(UTC) - timedelta(days=days)

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


def _handle_ppr_record(db, parsed) -> bool:
    """Insert a parsed PPR record into the SoldProperty table."""
    from packages.storage.repositories import SoldPropertyRepository

    # Skip records without a valid price (NOT NULL constraint on sold_properties)
    if parsed.price is None:
        logger.debug("ppr_record_skipped", reason="missing_price")
        return False

    repo = SoldPropertyRepository(db)
    raw = parsed.raw_data
    sale_date = _parse_ppr_sale_date(raw.get("sale_date"))
    if sale_date is None:
        logger.debug("ppr_record_skipped", reason="invalid_sale_date", sale_date=raw.get("sale_date"))
        return False

    repo.create(
        address=parsed.address,
        county=parsed.county,
        price=parsed.price,
        sale_date=sale_date,
        is_new=raw.get("is_new", False),
        is_full_market_price=raw.get("is_full_market_price", True),
        vat_exclusive=raw.get("vat_exclusive", False),
        property_size_description=raw.get("property_size_description"),
        content_hash=raw.get("content_hash", ""),
    )
    return True


def _parse_ppr_sale_date(value: Any) -> date | None:
    """Parse PPR sale_date values from adapters into a date instance."""
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, str):
        cleaned = value.strip()
        for fmt in ("%d/%m/%Y", "%Y-%m-%d"):
            try:
                return datetime.strptime(cleaned, fmt).date()
            except ValueError:
                continue
    return None
