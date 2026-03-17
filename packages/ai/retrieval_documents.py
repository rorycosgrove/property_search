"""Builders and materializers for unified retrieval documents.

These documents are the foundation for vectorization across listings,
incentives, market context, and historic property state.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any

from packages.analytics.engine import AnalyticsEngine
from packages.shared.utils import utc_now
from packages.storage.repositories import (
    GrantProgramRepository,
    LLMEnrichmentRepository,
    PriceHistoryRepository,
    PropertyDocumentRepository,
    PropertyGrantMatchRepository,
    PropertyRepository,
)


def _stable_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _compact_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _money(value: Any) -> str:
    if value is None:
        return "unknown"
    try:
        return f"EUR {float(value):,.0f}"
    except (TypeError, ValueError):
        return str(value)


def build_property_listing_document(property_obj: Any, enrichment: Any | None = None) -> dict[str, Any]:
    content_lines = [
        f"Listing: {property_obj.title}",
        f"Address: {property_obj.address}",
        f"County: {property_obj.county or 'unknown'}",
        f"Price: {_money(property_obj.price)}",
        f"Property type: {property_obj.property_type or 'unknown'}",
        f"Bedrooms: {property_obj.bedrooms or 'unknown'}",
        f"Bathrooms: {property_obj.bathrooms or 'unknown'}",
        f"BER: {property_obj.ber_rating or 'unknown'}",
        f"Status: {property_obj.status}",
        f"URL: {property_obj.url}",
    ]
    if property_obj.description:
        content_lines.append(f"Description: {property_obj.description}")
    if enrichment and enrichment.summary:
        content_lines.append(f"LLM summary: {enrichment.summary}")
    if enrichment and enrichment.neighbourhood_notes:
        content_lines.append(f"Neighbourhood notes: {enrichment.neighbourhood_notes}")
    if enrichment and enrichment.pros:
        content_lines.append(f"Pros: {', '.join(str(p) for p in enrichment.pros)}")
    if enrichment and enrichment.cons:
        content_lines.append(f"Cons: {', '.join(str(c) for c in enrichment.cons)}")

    content = "\n".join(content_lines)
    return {
        "document_type": "listing_snapshot",
        "scope_type": "property",
        "scope_key": str(property_obj.id),
        "document_key": f"listing_snapshot:{property_obj.id}",
        "content_hash": _stable_hash(content),
        "property_id": str(property_obj.id),
        "source_id": str(property_obj.source_id),
        "canonical_property_id": getattr(property_obj, "canonical_property_id", None),
        "county": property_obj.county,
        "title": property_obj.title,
        "content": content,
        "metadata_json": {
            "price": float(property_obj.price) if property_obj.price is not None else None,
            "status": property_obj.status,
            "url": property_obj.url,
            "external_id": getattr(property_obj, "external_id", None),
            "has_llm_enrichment": bool(enrichment),
        },
        "effective_at": getattr(property_obj, "updated_at", None) or utc_now(),
    }


def build_property_history_documents(property_obj: Any, price_history: list[Any]) -> list[dict[str, Any]]:
    documents: list[dict[str, Any]] = []
    for entry in price_history:
        recorded_at = getattr(entry, "recorded_at", None)
        content = "\n".join(
            [
                f"Property price history event for {property_obj.address}",
                f"Recorded at: {recorded_at.isoformat() if recorded_at else 'unknown'}",
                f"Observed price: {_money(getattr(entry, 'price', None))}",
                f"Price change: {_money(getattr(entry, 'price_change', None))}",
                f"Price change pct: {getattr(entry, 'price_change_pct', None)}",
            ]
        )
        key_suffix = recorded_at.isoformat() if recorded_at else f"idx:{len(documents)}"
        documents.append(
            {
                "document_type": "price_history_event",
                "scope_type": "property",
                "scope_key": str(property_obj.id),
                "document_key": f"price_history_event:{property_obj.id}:{key_suffix}",
                "content_hash": _stable_hash(content),
                "property_id": str(property_obj.id),
                "source_id": str(property_obj.source_id),
                "canonical_property_id": getattr(property_obj, "canonical_property_id", None),
                "county": property_obj.county,
                "title": f"Price history event for {property_obj.title}",
                "content": content,
                "metadata_json": {
                    "price": float(entry.price) if getattr(entry, "price", None) is not None else None,
                    "price_change": float(entry.price_change) if getattr(entry, "price_change", None) is not None else None,
                    "price_change_pct": getattr(entry, "price_change_pct", None),
                },
                "effective_at": recorded_at,
            }
        )
    return documents


def build_grant_match_documents(property_obj: Any, grant_matches: list[Any]) -> list[dict[str, Any]]:
    documents: list[dict[str, Any]] = []
    for match in grant_matches:
        grant = getattr(match, "grant_program", None)
        if not grant:
            continue
        eligibility = _compact_json(getattr(grant, "eligibility_rules", {}) or {})
        content = "\n".join(
            [
                f"Grant match for {property_obj.address}",
                f"Grant: {grant.name}",
                f"Status: {match.status}",
                f"Estimated benefit: {_money(getattr(match, 'estimated_benefit', None) or getattr(grant, 'max_amount', None))}",
                f"Grant description: {grant.description or 'n/a'}",
                f"Grant eligibility rules: {eligibility}",
                f"Reason: {match.reason or 'n/a'}",
            ]
        )
        documents.append(
            {
                "document_type": "grant_match",
                "scope_type": "property",
                "scope_key": str(property_obj.id),
                "document_key": f"grant_match:{property_obj.id}:{grant.id}",
                "content_hash": _stable_hash(content),
                "property_id": str(property_obj.id),
                "source_id": str(property_obj.source_id),
                "canonical_property_id": getattr(property_obj, "canonical_property_id", None),
                "county": property_obj.county,
                "title": f"Grant eligibility: {grant.name}",
                "content": content,
                "metadata_json": {
                    "grant_program_id": str(grant.id),
                    "grant_code": grant.code,
                    "status": match.status,
                    "country": grant.country,
                    "region": grant.region,
                    "estimated_benefit": float(match.estimated_benefit) if getattr(match, "estimated_benefit", None) is not None else None,
                    "valid_from": grant.valid_from.isoformat() if getattr(grant, "valid_from", None) else None,
                    "valid_to": grant.valid_to.isoformat() if getattr(grant, "valid_to", None) else None,
                },
                "effective_at": getattr(match, "created_at", None) or utc_now(),
            }
        )
    return documents


def build_market_snapshot_document(
    county: str | None,
    summary: Any,
    trends: list[Any],
    *,
    period: str,
    effective_at: datetime | None = None,
) -> dict[str, Any]:
    scope_type = "county" if county else "national"
    scope_key = (county or "national").lower()
    trend_text = "; ".join(
        f"{getattr(item, 'period', '')}:{_money(getattr(item, 'avg_price', None))} ({getattr(item, 'count', 0)} sales)"
        for item in trends[:12]
    )
    content = "\n".join(
        [
            f"Market snapshot for {county or 'Ireland'}",
            f"Average price: {_money(getattr(summary, 'avg_price', None))}",
            f"Median price: {_money(getattr(summary, 'median_price', None))}",
            f"Total active listings: {getattr(summary, 'total_active_listings', 0)}",
            f"New listings 24h: {getattr(summary, 'new_listings_24h', 0)}",
            f"Price changes 24h: {getattr(summary, 'price_changes_24h', 0)}",
            f"Total sold PPR: {getattr(summary, 'total_sold_ppr', 0)}",
            f"Trend: {trend_text or 'n/a'}",
        ]
    )
    return {
        "document_type": "market_snapshot",
        "scope_type": scope_type,
        "scope_key": scope_key,
        "document_key": f"market_snapshot:{scope_key}:{period}",
        "content_hash": _stable_hash(content),
        "property_id": None,
        "source_id": None,
        "canonical_property_id": None,
        "county": county,
        "title": f"Market snapshot: {county or 'Ireland'} ({period})",
        "content": content,
        "metadata_json": {
            "period": period,
            "avg_price": getattr(summary, "avg_price", None),
            "median_price": getattr(summary, "median_price", None),
            "total_active_listings": getattr(summary, "total_active_listings", None),
            "new_listings_24h": getattr(summary, "new_listings_24h", None),
            "price_changes_24h": getattr(summary, "price_changes_24h", None),
            "total_sold_ppr": getattr(summary, "total_sold_ppr", None),
            "trends": [
                {
                    "period": getattr(item, "period", None),
                    "avg_price": getattr(item, "avg_price", None),
                    "count": getattr(item, "count", None),
                }
                for item in trends[:12]
            ],
        },
        "effective_at": effective_at or datetime.now(UTC),
    }


def build_market_trend_documents(
    county: str | None,
    trends: list[Any],
    *,
    generated_at: datetime | None = None,
) -> list[dict[str, Any]]:
    scope_type = "county" if county else "national"
    scope_key = (county or "national").lower()
    effective_default = generated_at or datetime.now(UTC)

    documents: list[dict[str, Any]] = []
    for trend in trends:
        period = str(getattr(trend, "period", "") or "unknown")
        avg_price = getattr(trend, "avg_price", None)
        sale_count = int(getattr(trend, "count", 0) or 0)
        content = "\n".join(
            [
                f"Historical market trend for {county or 'Ireland'}",
                f"Period: {period}",
                f"Average sold price: {_money(avg_price)}",
                f"Sales volume: {sale_count}",
            ]
        )
        documents.append(
            {
                "document_type": "market_trend_period",
                "scope_type": scope_type,
                "scope_key": scope_key,
                "document_key": f"market_trend:{scope_key}:{period}",
                "content_hash": _stable_hash(content),
                "property_id": None,
                "source_id": None,
                "canonical_property_id": None,
                "county": county,
                "title": f"Market trend {period}: {county or 'Ireland'}",
                "content": content,
                "metadata_json": {
                    "period": period,
                    "avg_price": avg_price,
                    "count": sale_count,
                },
                "effective_at": effective_default,
            }
        )
    return documents


def build_grant_program_documents(grants: list[Any]) -> list[dict[str, Any]]:
    documents: list[dict[str, Any]] = []
    for grant in grants:
        eligibility = _compact_json(getattr(grant, "eligibility_rules", {}) or {})
        max_amount = getattr(grant, "max_amount", None)
        currency = getattr(grant, "currency", None) or "EUR"
        if max_amount is not None:
            benefit_text = f"{currency} {float(max_amount):,.0f}"
        else:
            benefit_text = "n/a"

        content = "\n".join(
            [
                f"Incentive program: {grant.name}",
                f"Code: {grant.code}",
                f"Authority: {getattr(grant, 'authority', None) or 'n/a'}",
                f"Country: {grant.country}",
                f"Region: {getattr(grant, 'region', None) or 'n/a'}",
                f"Benefit type: {getattr(grant, 'benefit_type', None) or 'n/a'}",
                f"Maximum amount: {benefit_text}",
                f"Active: {bool(getattr(grant, 'active', False))}",
                f"Valid from: {getattr(grant, 'valid_from', None) or 'n/a'}",
                f"Valid to: {getattr(grant, 'valid_to', None) or 'n/a'}",
                f"Description: {getattr(grant, 'description', None) or 'n/a'}",
                f"Eligibility rules: {eligibility}",
                f"Source URL: {getattr(grant, 'source_url', None) or 'n/a'}",
            ]
        )

        documents.append(
            {
                "document_type": "incentive_program",
                "scope_type": "incentive_program",
                "scope_key": str(grant.id),
                "document_key": f"incentive_program:{grant.id}",
                "content_hash": _stable_hash(content),
                "property_id": None,
                "source_id": None,
                "canonical_property_id": None,
                "county": getattr(grant, "region", None),
                "title": f"Incentive: {grant.name}",
                "content": content,
                "metadata_json": {
                    "grant_program_id": str(grant.id),
                    "grant_code": grant.code,
                    "country": grant.country,
                    "region": getattr(grant, "region", None),
                    "authority": getattr(grant, "authority", None),
                    "benefit_type": getattr(grant, "benefit_type", None),
                    "max_amount": float(max_amount) if max_amount is not None else None,
                    "currency": currency,
                    "active": bool(getattr(grant, "active", False)),
                    "valid_from": getattr(grant, "valid_from", None).isoformat() if getattr(grant, "valid_from", None) else None,
                    "valid_to": getattr(grant, "valid_to", None).isoformat() if getattr(grant, "valid_to", None) else None,
                    "source_url": getattr(grant, "source_url", None),
                    "eligibility_rules": getattr(grant, "eligibility_rules", {}) or {},
                },
                "effective_at": utc_now(),
            }
        )
    return documents


def materialize_property_documents(db: Any, property_id: str) -> int:
    property_repo = PropertyRepository(db)
    doc_repo = PropertyDocumentRepository(db)
    price_repo = PriceHistoryRepository(db)
    grant_repo = PropertyGrantMatchRepository(db)
    enrichment_repo = LLMEnrichmentRepository(db)

    property_obj = property_repo.get_by_id(property_id)
    if not property_obj:
        return 0

    enrichment = enrichment_repo.get_by_property_id(property_id)
    price_history = price_repo.list_for_property(property_id)
    grant_matches = grant_repo.list_for_property(property_id)

    documents = [build_property_listing_document(property_obj, enrichment)]
    documents.extend(build_property_history_documents(property_obj, price_history))
    documents.extend(build_grant_match_documents(property_obj, grant_matches))

    count = 0
    for document in documents:
        key = document.pop("document_key")
        doc_repo.upsert_document(key, **document)
        count += 1
    return count


def materialize_market_documents(db: Any, county: str | None = None) -> int:
    engine = AnalyticsEngine(db)
    doc_repo = PropertyDocumentRepository(db)
    now = datetime.now(UTC)
    period = now.strftime("%Y-%m")
    summary = engine.get_summary()
    if county:
        county_stats = next(
            (item for item in engine.get_county_stats() if str(getattr(item, "county", "")).lower() == county.lower()),
            None,
        )
        if county_stats:
            summary = type("_CountySummary", (), {
                "avg_price": getattr(county_stats, "avg_price", None),
                "median_price": getattr(county_stats, "median_price", None),
                "total_active_listings": getattr(county_stats, "count", 0),
                "new_listings_24h": None,
                "price_changes_24h": None,
                "total_sold_ppr": None,
            })()
    trends = engine.get_price_trends(county=county, months=12)
    count = 0

    snapshot_document = build_market_snapshot_document(county, summary, trends, period=period, effective_at=now)
    snapshot_key = snapshot_document.pop("document_key")
    doc_repo.upsert_document(snapshot_key, **snapshot_document)
    count += 1

    trend_documents = build_market_trend_documents(county, trends, generated_at=now)
    for document in trend_documents:
        key = document.pop("document_key")
        doc_repo.upsert_document(key, **document)
        count += 1

    return count


def materialize_incentive_documents(db: Any, active_only: bool = False) -> int:
    grant_repo = GrantProgramRepository(db)
    doc_repo = PropertyDocumentRepository(db)

    grants = grant_repo.list_programs(active_only=active_only)
    documents = build_grant_program_documents(grants)

    count = 0
    for document in documents:
        key = document.pop("document_key")
        doc_repo.upsert_document(key, **document)
        count += 1
    return count


def materialize_reference_documents(
    db: Any,
    *,
    county: str | None = None,
    include_incentives: bool = True,
    active_grants_only: bool = False,
) -> dict[str, int]:
    result: dict[str, int] = {
        "market_documents": materialize_market_documents(db, county=county),
        "incentive_documents": 0,
    }
    if include_incentives:
        result["incentive_documents"] = materialize_incentive_documents(db, active_only=active_grants_only)
    result["total_documents"] = result["market_documents"] + result["incentive_documents"]
    return result