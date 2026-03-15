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


def _record_backend_log(
    *,
    level: str,
    event_type: str,
    message: str,
    component: str = "worker.tasks",
    source_id: str | None = None,
    context: dict[str, Any] | None = None,
) -> None:
    """Persist an operational event for settings diagnostics.

    This is best-effort and should never break ingestion if logging persistence fails.
    """
    try:
        from packages.storage.database import get_session
        from packages.storage.models import BackendLog

        retention_days = max(int(getattr(settings, "backend_log_retention_days", 7) or 7), 1)
        cutoff = datetime.now(UTC) - timedelta(days=retention_days)

        with get_session() as db:
            # Keep the table bounded without requiring external cron.
            db.query(BackendLog).filter(BackendLog.created_at < cutoff).delete()
            db.add(
                BackendLog(
                    level=level.upper(),
                    event_type=event_type,
                    component=component,
                    source_id=source_id,
                    message=message,
                    context_json=context or {},
                )
            )
    except Exception:
        logger.warning("backend_log_persist_failed", event_type=event_type)


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


def scrape_all_sources(force: bool = False) -> dict[str, Any]:
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
            _record_backend_log(
                level="INFO",
                event_type="discovery_during_scrape_complete",
                message="Source discovery during scrape completed",
                context=discovery_summary,
            )
        except Exception as exc:
            discovery_summary = {
                **discovery_summary,
                "error": str(exc),
            }
            logger.warning("discovery_during_scrape_failed", error=str(exc))
            _record_backend_log(
                level="WARNING",
                event_type="discovery_during_scrape_failed",
                message="Source discovery during scrape failed",
                context=discovery_summary,
            )

    with get_session() as db:
        repo = SourceRepository(db)
        all_sources = repo.get_all(enabled_only=False)
        enabled_sources = [s for s in all_sources if bool(getattr(s, "enabled", False))]
        pending_approval_count = sum(
            1 for s in all_sources if isinstance(getattr(s, "tags", None), list) and "pending_approval" in (s.tags or [])
        )
        auto_disabled_count = sum(
            1
            for s in all_sources
            if not bool(getattr(s, "enabled", False)) and int(getattr(s, "error_count", 0) or 0) >= 5
        )
        source_ids = [str(s.id) for s in enabled_sources]

    logger.info(f"Dispatching scrape for {len(source_ids)} sources")
    _record_backend_log(
        level="INFO",
        event_type="scrape_all_sources_started",
        message="Dispatching scrape across enabled sources",
        context={
            "enabled_sources": len(source_ids),
            "source_summary": {
                "total": len(all_sources),
                "enabled": len(enabled_sources),
                "pending_approval": pending_approval_count,
                "disabled_by_errors": auto_disabled_count,
            },
        },
    )

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
            payload = {"source_id": sid}
            if force:
                payload["force"] = True
            try:
                send_task("scrape", "scrape_source", payload)
            except Exception as exc:
                logger.warning(
                    "scrape_queue_dispatch_failed_fallback_inline",
                    source_id=sid,
                    error=str(exc),
                )
                if force:
                    scrape_source(sid, force=True)
                else:
                    scrape_source(sid)
                processed_inline += 1
        else:
            if force:
                scrape_source(sid, force=True)
            else:
                scrape_source(sid)
            processed_inline += 1
        dispatched += 1

    result = {
        "dispatched": dispatched,
        "processed_inline": processed_inline,
        "dispatch_mode": "sqs" if use_sqs_dispatch else "inline",
        "discovery_during_scrape": discovery_summary,
        "source_summary": {
            "total": len(all_sources),
            "enabled": len(enabled_sources),
            "pending_approval": pending_approval_count,
            "disabled_by_errors": auto_disabled_count,
        },
    }
    _record_backend_log(
        level="INFO",
        event_type="scrape_all_sources_dispatched",
        message="Scrape dispatch completed",
        context=result,
    )
    return result


def scrape_source(source_id: str, force: bool = False) -> dict[str, Any]:
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

        if source_repo.should_skip_poll(source) and not force:
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
            adapter = get_adapter(source.adapter_name)
            config = source.config or {}
            raw_listings = _run_async(adapter.fetch_listings(config))
            logger.info(f"Fetched {len(raw_listings)} listings from {source.name}")

            new_count = 0
            updated_count = 0
            skipped_count = 0
            dedup_conflict_count = 0
            geocode_attempts = 0
            geocode_successes = 0

            for raw in raw_listings:
                parsed = adapter.parse_listing(raw)
                if not parsed:
                    skipped_count += 1
                    continue

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

                record = normalizer.normalize(parsed)
                existing = property_repo.get_by_content_hash(record["content_hash"])

                if existing:
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
                            property_repo.update(str(existing.id), price=new_price, status="price_changed")
                            updated_count += 1
                        else:
                            skipped_count += 1
                    else:
                        skipped_count += 1
                else:
                    if not record.get("latitude"):
                        geocode_attempts += 1
                        geo = _run_async(
                            _geocode_safe(record.get("address", ""), record.get("county"))
                        )
                        if geo:
                            record["latitude"] = geo.latitude
                            record["longitude"] = geo.longitude
                            geocode_successes += 1
                        else:
                            _record_backend_log(
                                level="WARNING",
                                event_type="geocode_failed",
                                message="Geocoding returned no result for property",
                                source_id=source_id,
                                context={
                                    "source_name": source.name,
                                    "address": record.get("address"),
                                    "county": record.get("county"),
                                },
                            )

                    record["source_id"] = source_id
                    record["status"] = "new"
                    record["first_listed_at"] = datetime.now(UTC)
                    try:
                        with _nested_tx_or_noop(db):
                            property_repo.create(**record)
                        new_count += 1
                    except IntegrityError:
                        skipped_count += 1
                        dedup_conflict_count += 1
                        logger.info(
                            "property_dedup_conflict_skipped",
                            source_id=source_id,
                            content_hash=record.get("content_hash"),
                        )

            source_repo.mark_poll_success(source_id, new_count + updated_count)

            result = {
                "source_id": source_id,
                "source_name": source.name,
                "new": new_count,
                "updated": updated_count,
                "skipped": skipped_count,
                "total_fetched": len(raw_listings),
                "geocode_attempts": geocode_attempts,
                "geocode_successes": geocode_successes,
                "geocode_success_rate": (
                    round((geocode_successes / geocode_attempts) * 100, 2)
                    if geocode_attempts
                    else 100.0
                ),
            }

            logger.info(f"Scrape complete: {result}")
            _record_backend_log(
                level="INFO",
                event_type="scrape_source_complete",
                message="Source scrape completed",
                source_id=source_id,
                context=result,
            )
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

            if (new_count > 0 or updated_count > 0) and _is_queue_configured("alert"):
                from packages.shared.queue import send_task

                try:
                    send_task("alert", "evaluate_alerts", {})
                except Exception as exc:
                    logger.warning(
                        "alert_queue_dispatch_failed",
                        source_id=source_id,
                        error=str(exc),
                    )

            return result

        except Exception as exc:
            logger.error(f"Scrape failed for {source.name}: {exc}")
            try:
                source_repo.mark_poll_error(source_id, str(exc))
                db.commit()
            except Exception as mark_err:
                logger.warning(f"Failed to persist scrape error status: {mark_err}")
            _record_backend_log(
                level="ERROR",
                event_type="scrape_source_failed",
                message="Source scrape failed",
                source_id=source_id,
                context={"source_name": source.name, "error": str(exc)},
            )
            raise


def discover_sources(auto_enable: bool = False, limit: int = 25) -> dict[str, Any]:
    """Discover default and configured feed candidates and add missing sources.

    Sources are created disabled by default and require approval unless
    `auto_enable=True` is passed.
    """
    from packages.sources.discovery import canonicalize_source_url, load_discovery_candidates
    from packages.sources.registry import get_adapter_names
    from packages.storage.database import get_session
    from packages.storage.repositories import SourceRepository

    adapter_names = set(get_adapter_names())
    created = 0
    created_enabled = 0
    created_pending_approval = 0
    existing = 0
    skipped_invalid = 0

    with get_session() as db:
        repo = SourceRepository(db)
        existing_sources = repo.get_all(enabled_only=False)
        existing_by_canonical = {
            canonicalize_source_url(str(getattr(s, "url", "") or "")): s
            for s in existing_sources
            if canonicalize_source_url(str(getattr(s, "url", "") or ""))
        }

        for candidate in load_discovery_candidates()[: max(limit, 1)]:
            adapter_name = candidate.get("adapter_name")
            url = candidate.get("url")
            canonical_url = canonicalize_source_url(str(url or ""))

            if adapter_name not in adapter_names or not url or not canonical_url:
                skipped_invalid += 1
                continue

            if canonical_url in existing_by_canonical:
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
            existing_by_canonical[canonical_url] = True
            created += 1
            if auto_enable:
                created_enabled += 1
            else:
                created_pending_approval += 1

    result = {
        "run_at": datetime.now(UTC).isoformat(),
        "created": created,
        "created_enabled": created_enabled,
        "created_pending_approval": created_pending_approval,
        "existing": existing,
        "skipped_invalid": skipped_invalid,
        "auto_enable": auto_enable,
    }
    logger.info("source_discovery_complete", **result)
    _record_backend_log(
        level="INFO",
        event_type="source_discovery_complete",
        message="Source discovery run completed",
        context=result,
    )
    return result


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

    _record_backend_log(
        level="INFO",
        event_type="alert_evaluation_complete",
        message="Alert evaluation run completed",
        context={
            "search_alerts": int(search_alerts or 0),
            "price_alerts": int(price_alerts or 0),
        },
    )

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
        _record_backend_log(
            level="WARNING",
            event_type="llm_enrichment_skipped",
            message="LLM enrichment skipped because llm is disabled",
            context={"property_id": property_id, "reason": "llm_disabled"},
        )
        return {"property_id": property_id, "enriched": False, "reason": "llm_disabled"}

    with get_session() as db:
        prop_repo = PropertyRepository(db)
        sold_repo = SoldPropertyRepository(db)
        enrichment_repo = LLMEnrichmentRepository(db)

        prop = prop_repo.get_by_id(property_id)
        if not prop:
            _record_backend_log(
                level="WARNING",
                event_type="llm_enrichment_property_not_found",
                message="LLM enrichment skipped because property was not found",
                context={"property_id": property_id},
            )
            return {"error": "Property not found"}

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
            _record_backend_log(
                level="INFO",
                event_type="llm_enrichment_complete",
                message="LLM enrichment completed for property",
                context={
                    "property_id": property_id,
                    "nearby_sold_count": len(nearby_sold),
                },
            )
            return {"property_id": property_id, "enriched": True}
        except Exception as exc:
            logger.error(f"LLM enrichment failed: {exc}")
            _record_backend_log(
                level="ERROR",
                event_type="llm_enrichment_failed",
                message="LLM enrichment failed for property",
                context={"property_id": property_id, "error": str(exc)[:300]},
            )
            raise

def enrich_batch_llm(limit: int = LLM_BATCH_SIZE) -> dict[str, Any]:
    """Enrich a batch of un-enriched properties."""
    from packages.shared.queue import send_task
    from packages.storage.database import get_session
    from packages.storage.models import LLMEnrichment, Property

    if not settings.llm_enabled:
        logger.warning("llm_batch_skipped", reason="llm_disabled", limit=limit)
        _record_backend_log(
            level="WARNING",
            event_type="llm_batch_skipped",
            message="LLM batch enrichment skipped because llm is disabled",
            context={"limit": int(limit), "reason": "llm_disabled"},
        )
        return {"dispatched": 0, "reason": "llm_disabled"}

    if not _is_queue_configured("llm"):
        logger.warning("llm_batch_skipped", reason="llm_queue_unconfigured", limit=limit)
        _record_backend_log(
            level="WARNING",
            event_type="llm_batch_skipped",
            message="LLM batch enrichment skipped because llm queue is unconfigured",
            context={"limit": int(limit), "reason": "llm_queue_unconfigured"},
        )
        return {"dispatched": 0, "reason": "llm_queue_unconfigured"}

    with get_session() as db:
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

    _record_backend_log(
        level="INFO",
        event_type="llm_batch_dispatched",
        message="LLM batch enrichment dispatch completed",
        context={"requested_limit": int(limit), "dispatched": dispatched},
    )

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


# ── Unified source discovery ──────────────────────────────────────────────────


def discover_all_sources(
    limit: int = 200,
    dry_run: bool = False,
    follow_links: bool = False,
    include_grants: bool = True,
) -> dict[str, Any]:
    """Unified source + grant discovery with confidence-based activation.

    This supersedes the simple ``discover_sources()`` task for production
    scheduled runs.  It:

    1. Runs the property crawler (static extended candidates + optional live crawl).
    2. Scores each candidate via ``packages.sources.confidence``.
    3. Auto-enables high-confidence sources (score >= 0.70), pends medium ones.
    4. Optionally discovers new grant programs from Irish/NI government portals.

    Parameters
    ----------
    limit:
        Maximum number of new sources to create (applied after scoring).
    dry_run:
        When True, return all discoveries without persisting anything.
    follow_links:
        Pass-through to the crawler — enables live HTTP fetching of seed pages.
        Slower but discovers more sources.  Safe to leave False on scheduled runs.
    include_grants:
        Also run grant source discovery (``packages.grants.discovery``).
    """
    from packages.sources.discovery import canonicalize_source_url, load_all_discovery_candidates
    from packages.sources.registry import get_adapter, get_adapter_names
    from packages.storage.database import get_session
    from packages.storage.repositories import SourceRepository

    run_at = datetime.now(UTC).isoformat()
    adapter_names = set(get_adapter_names())

    scored = load_all_discovery_candidates(
        use_crawler=True,
        follow_links=follow_links,
    )

    property_stats: dict[str, Any] = {
        "candidates_scored": len(scored),
        "auto_enabled": 0,
        "pending_approval": 0,
        "existing": 0,
        "skipped_invalid": 0,
        "skipped_invalid_config": 0,
        "skipped_limit": 0,
        "dry_run": dry_run,
        "created": [],
    }

    if not dry_run:
        with get_session() as db:
            repo = SourceRepository(db)
            existing_sources = repo.get_all(enabled_only=False)
            existing_by_canonical = {
                canonicalize_source_url(str(getattr(s, "url", "") or "")): s
                for s in existing_sources
                if canonicalize_source_url(str(getattr(s, "url", "") or ""))
            }
            created_count = 0

            for scored_c in scored:
                if created_count >= limit:
                    property_stats["skipped_limit"] += 1
                    continue

                candidate = scored_c.candidate
                adapter_name = (candidate.get("adapter_name") or "").strip().lower()
                url = (candidate.get("url") or "").strip()
                canonical_url = canonicalize_source_url(str(url or ""))

                if adapter_name not in adapter_names or not url or not canonical_url:
                    property_stats["skipped_invalid"] += 1
                    continue

                config = candidate.get("config") or {}
                try:
                    adapter = get_adapter(adapter_name)
                except KeyError:
                    property_stats["skipped_invalid"] += 1
                    continue

                config_errors = adapter.validate_config(config)
                if config_errors:
                    property_stats["skipped_invalid_config"] += 1
                    logger.warning(
                        "discover_all_sources_skip_invalid_config",
                        adapter_name=adapter_name,
                        url=url,
                        errors=config_errors,
                    )
                    continue

                if canonical_url in existing_by_canonical:
                    property_stats["existing"] += 1
                    continue

                auto_enable = scored_c.should_auto_enable
                tags = list(candidate.get("tags") or [])
                if "auto_discovered" not in tags:
                    tags.append("auto_discovered")
                if not auto_enable and "pending_approval" not in tags:
                    tags.append("pending_approval")
                # Attach confidence metadata as a tag for visibility.
                tags.append(f"confidence:{scored_c.score:.2f}")

                repo.create(
                    name=candidate.get("name") or f"Discovered {adapter_name}",
                    url=url,
                    adapter_type=candidate.get("adapter_type") or "scraper",
                    adapter_name=adapter_name,
                    config=config,
                    enabled=auto_enable,
                    poll_interval_seconds=int(candidate.get("poll_interval_seconds") or 21600),
                    tags=tags,
                )
                existing_by_canonical[canonical_url] = True
                created_count += 1

                if auto_enable:
                    property_stats["auto_enabled"] += 1
                else:
                    property_stats["pending_approval"] += 1

                property_stats["created"].append({
                    "name": candidate.get("name"),
                    "url": url,
                    "score": scored_c.score,
                    "activation": scored_c.activation,
                })

    else:
        # Dry-run: populate created list for preview without DB writes.
        for sc in scored[:limit]:
            property_stats["created"].append({
                "name": sc.candidate.get("name"),
                "url": sc.candidate.get("url"),
                "score": sc.score,
                "activation": sc.activation,
                "reasons": sc.reasons,
            })
            if sc.activation == "auto_enable":
                property_stats["auto_enabled"] += 1
            else:
                property_stats["pending_approval"] += 1

    # ── Grant discovery ───────────────────────────────────────────────────────
    grant_stats: dict[str, Any] = {"skipped": True}
    if include_grants:
        try:
            from packages.grants.discovery import discover_grant_programs
            grant_stats = discover_grant_programs(dry_run=dry_run)
        except Exception as grant_exc:
            logger.warning("discover_all_sources: grant discovery failed", error=str(grant_exc))
            grant_stats = {"error": str(grant_exc)}

    result = {
        "run_at": run_at,
        "property_sources": property_stats,
        "grant_programs": grant_stats,
        "follow_links": follow_links,
        "limit": limit,
    }

    logger.info("discover_all_sources_complete", **{
        k: v for k, v in result.items() if not isinstance(v, (dict, list))
    })
    _record_backend_log(
        level="INFO",
        event_type="unified_discovery_complete",
        message="Unified source + grant discovery run completed",
        context=result,
    )
    return result

