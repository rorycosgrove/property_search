from __future__ import annotations

from typing import Any

from packages.shared.schemas import PropertyFilters


class PropertyServiceError(Exception):
    """Base exception for property-domain service errors."""


class PropertyValidationError(PropertyServiceError):
    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


class PropertyNotFoundError(PropertyServiceError):
    def __init__(self, property_id: str):
        self.property_id = property_id
        super().__init__(f"property not found: {property_id}")


def _parse_csv_values(value: str | None) -> list[str] | None:
    if not value:
        return None
    parsed = [item.strip() for item in value.split(",") if item.strip()]
    return parsed or None


def _parse_keywords(value: str | None) -> list[str] | None:
    if not value:
        return None
    if "," in value:
        return _parse_csv_values(value)
    parsed = [item.strip() for item in value.split() if item.strip()]
    return parsed or None


def build_property_filters(
    *,
    page: int,
    size: int,
    county: str | None,
    min_price: float | None,
    max_price: float | None,
    min_beds: int | None,
    max_beds: int | None,
    property_types: str | None,
    sale_type: str | None,
    keywords: str | None,
    ber_ratings: str | None,
    sort_by: str,
    sort_dir: str,
    lat: float | None,
    lng: float | None,
    radius_km: float | None,
    eligible_only: bool,
    min_eligible_grants_total: float | None,
) -> PropertyFilters:
    if min_price is not None and max_price is not None and min_price > max_price:
        raise PropertyValidationError("min_price cannot be greater than max_price")

    if min_beds is not None and max_beds is not None and min_beds > max_beds:
        raise PropertyValidationError("min_beds cannot be greater than max_beds")

    if lat is not None or lng is not None or radius_km is not None:
        if not (lat is not None and lng is not None and radius_km is not None):
            raise PropertyValidationError("lat, lng, and radius_km must all be provided together")

    return PropertyFilters(
        counties=[county] if county else None,
        min_price=min_price,
        max_price=max_price,
        min_bedrooms=min_beds,
        max_bedrooms=max_beds,
        property_types=_parse_csv_values(property_types),
        sale_type=sale_type,
        keywords=_parse_keywords(keywords),
        ber_ratings=_parse_csv_values(ber_ratings),
        lat=lat,
        lng=lng,
        radius_km=radius_km,
        eligible_only=eligible_only,
        min_eligible_grants_total=min_eligible_grants_total,
        sort_by=sort_by,
        sort_order=sort_dir,
        page=page,
        per_page=size,
    )


def property_to_dict(
    prop: Any,
    *,
    eligible_grants_total: float | None = None,
    net_price: float | None = None,
) -> dict[str, Any]:
    enrichment = None
    if prop.enrichment:
        enrichment = {
            "summary": prop.enrichment.summary,
            "value_score": prop.enrichment.value_score,
            "value_reasoning": prop.enrichment.value_reasoning,
            "pros": prop.enrichment.pros or [],
            "cons": prop.enrichment.cons or [],
            "extracted_features": prop.enrichment.extracted_features or {},
            "neighbourhood_notes": prop.enrichment.neighbourhood_notes,
            "investment_potential": prop.enrichment.investment_potential,
            "llm_provider": prop.enrichment.llm_provider,
            "llm_model": prop.enrichment.llm_model,
            "processed_at": prop.enrichment.processed_at.isoformat() if prop.enrichment.processed_at else None,
            "processing_time_ms": prop.enrichment.processing_time_ms,
        }

    price_history = []
    if hasattr(prop, "price_history") and prop.price_history:
        price_history = [
            {
                "price": float(h.price),
                "price_change": float(h.price_change) if h.price_change else None,
                "price_change_pct": float(h.price_change_pct) if h.price_change_pct else None,
                "recorded_at": h.recorded_at.isoformat(),
            }
            for h in prop.price_history
        ]

    return {
        "id": str(prop.id),
        "title": prop.title,
        "description": prop.description,
        "url": prop.url,
        "address": prop.address,
        "county": prop.county,
        "eircode": prop.eircode,
        "price": float(prop.price) if prop.price else None,
        "property_type": prop.property_type,
        "sale_type": prop.sale_type,
        "bedrooms": prop.bedrooms,
        "bathrooms": prop.bathrooms,
        "floor_area_sqm": float(prop.floor_area_sqm) if prop.floor_area_sqm else None,
        "ber_rating": prop.ber_rating,
        "images": prop.images or [],
        "features": prop.features or {},
        "latitude": prop.latitude,
        "longitude": prop.longitude,
        "status": prop.status,
        "source_id": str(prop.source_id) if prop.source_id else None,
        "external_id": prop.external_id,
        "content_hash": prop.content_hash,
        "first_listed_at": prop.first_listed_at.isoformat() if prop.first_listed_at else None,
        "created_at": prop.created_at.isoformat() if prop.created_at else None,
        "updated_at": prop.updated_at.isoformat() if prop.updated_at else None,
        "eligible_grants_total": eligible_grants_total,
        "net_price": net_price,
        "enrichment": enrichment,
        "price_history": price_history,
    }


def list_properties_payload(
    *,
    repo: Any,
    page: int,
    size: int,
    county: str | None,
    min_price: float | None,
    max_price: float | None,
    min_beds: int | None,
    max_beds: int | None,
    property_types: str | None,
    sale_type: str | None,
    keywords: str | None,
    ber_ratings: str | None,
    sort_by: str,
    sort_dir: str,
    lat: float | None,
    lng: float | None,
    radius_km: float | None,
    eligible_only: bool,
    min_eligible_grants_total: float | None,
) -> dict[str, Any]:
    filters = build_property_filters(
        page=page,
        size=size,
        county=county,
        min_price=min_price,
        max_price=max_price,
        min_beds=min_beds,
        max_beds=max_beds,
        property_types=property_types,
        sale_type=sale_type,
        keywords=keywords,
        ber_ratings=ber_ratings,
        sort_by=sort_by,
        sort_dir=sort_dir,
        lat=lat,
        lng=lng,
        radius_km=radius_km,
        eligible_only=eligible_only,
        min_eligible_grants_total=min_eligible_grants_total,
    )
    metrics_by_property_id: dict[str, dict[str, float]] = {}
    use_grant_aware_query = (
        sort_by == "net_price"
        or bool(eligible_only)
        or min_eligible_grants_total is not None
    )
    if use_grant_aware_query:
        items, total, metrics_by_property_id = repo.list_properties_with_eligible_grants(filters)
    else:
        items, total = repo.list_properties(filters)

    serialized_items = []
    for prop in items:
        metrics = metrics_by_property_id.get(str(prop.id), {})
        serialized_items.append(
            property_to_dict(
                prop,
                eligible_grants_total=metrics.get("eligible_grants_total"),
                net_price=metrics.get("net_price"),
            )
        )

    return {
        "items": serialized_items,
        "total": total,
        "page": page,
        "per_page": size,
        "pages": -(-total // size),
    }


def get_property_payload(*, repo: Any, property_id: str) -> dict[str, Any]:
    prop = repo.get_by_id(property_id)
    if not prop:
        raise PropertyNotFoundError(property_id)
    return property_to_dict(prop)


def get_similar_payload(*, repo: Any, property_id: str, limit: int) -> list[dict[str, Any]]:
    prop = repo.get_by_id(property_id)
    if not prop:
        raise PropertyNotFoundError(property_id)
    similar = repo.find_similar(property_id, limit=limit)
    return [property_to_dict(p) for p in similar]


def get_sold_comps_payload(
    *,
    property_repo: Any,
    sold_repo: Any,
    property_id: str,
    limit: int,
    min_similarity: float,
) -> dict[str, Any]:
    prop = property_repo.get_by_id(property_id)
    if not prop:
        raise PropertyNotFoundError(property_id)

    if prop.latitude is not None and prop.longitude is not None:
        sold_items = sold_repo.get_nearby_sold(
            lat=prop.latitude,
            lng=prop.longitude,
            radius_km=2.0,
            limit=limit,
        )
        return {
            "property_id": property_id,
            "strategy": "geo_radius",
            "items": [
                {
                    "id": str(item.id),
                    "address": item.address,
                    "county": item.county,
                    "price": float(item.price) if item.price else None,
                    "sale_date": item.sale_date.isoformat() if item.sale_date else None,
                    "latitude": item.latitude,
                    "longitude": item.longitude,
                    "match_method": "geo_radius",
                    "match_confidence": "high",
                }
                for item in sold_items
            ],
        }

    fuzzy_hash = getattr(prop, "fuzzy_address_hash", None)
    comps = sold_repo.get_confident_comparable_sold(
        address=prop.address,
        county=prop.county,
        fuzzy_address_hash_value=fuzzy_hash,
        limit=limit,
        min_similarity=min_similarity,
    )
    return {
        "property_id": property_id,
        "strategy": "address_fuzzy",
        "items": comps,
    }


def get_price_history_payload(*, repo: Any, property_id: str, limit: int) -> list[dict[str, Any]]:
    history = repo.get_for_property(property_id)
    # Guard against very large history responses.
    history = history[-limit:] if len(history) > limit else history
    return [
        {
            "id": str(h.id),
            "price": float(h.price),
            "price_change": float(h.price_change) if h.price_change else None,
            "price_change_pct": float(h.price_change_pct) if h.price_change_pct else None,
            "recorded_at": h.recorded_at.isoformat(),
        }
        for h in history
    ]


def get_timeline_payload(*, repo: Any, property_id: str, limit: int) -> list[dict[str, Any]]:
    history = repo.list_for_property(property_id, limit=limit)
    return [
        {
            "id": str(event.id),
            "event_type": event.event_type,
            "occurred_at": event.occurred_at.isoformat() if event.occurred_at else None,
            "price": float(event.price) if event.price is not None else None,
            "price_change": float(event.price_change) if event.price_change is not None else None,
            "price_change_pct": float(event.price_change_pct) if event.price_change_pct is not None else None,
            "source_id": event.source_id,
            "adapter_name": event.adapter_name,
            "source_url": event.source_url,
            "detection_method": event.detection_method,
            "confidence_score": float(event.confidence_score) if event.confidence_score is not None else None,
            "dedup_key": event.dedup_key,
            "evidence": event.evidence or {},
            "metadata": event.metadata_json or {},
        }
        for event in history
    ]


def get_intelligence_payload(
    *,
    property_repo: Any,
    price_history_repo: Any,
    timeline_repo: Any,
    document_repo: Any,
    property_id: str,
) -> dict[str, Any]:
    """Consolidated intelligence payload for a single property.

    Combines: listing detail, price history, timeline, RAG documents, and a
    completeness score so the frontend can surface a single unified view.
    """
    prop = property_repo.get_by_id(property_id)
    if not prop:
        raise PropertyNotFoundError(property_id)

    listing = property_to_dict(prop)

    price_history = get_price_history_payload(
        repo=price_history_repo,
        property_id=property_id,
        limit=50,
    )

    timeline = get_timeline_payload(
        repo=timeline_repo,
        property_id=property_id,
        limit=50,
    )

    # Retrieve stored RAG documents for this property
    documents = document_repo.list_for_property(property_id)
    doc_summaries = [
        {
            "document_key": d.document_key,
            "document_type": d.document_type,
            "title": d.title,
            "effective_at": d.effective_at.isoformat() if d.effective_at else None,
            "county": d.county,
        }
        for d in documents
    ]

    # Simple completeness score: fraction of key data points present
    checks = [
        bool(prop.price),
        bool(prop.bedrooms),
        bool(prop.county),
        bool(prop.latitude and prop.longitude),
        bool(prop.ber_rating),
        bool(prop.enrichment),
        len(price_history) > 0,
        len(timeline) > 0,
        len(documents) > 0,
    ]
    completeness_score = round(sum(checks) / len(checks), 2)

    return {
        "property_id": property_id,
        "listing": listing,
        "price_history": price_history,
        "timeline": timeline,
        "documents": doc_summaries,
        "completeness_score": completeness_score,
        "data_sources": {
            "price_history_entries": len(price_history),
            "timeline_events": len(timeline),
            "rag_documents": len(documents),
        },
    }


def get_brief_payload(
    *,
    property_repo: Any,
    price_history_repo: Any,
    timeline_repo: Any,
    document_repo: Any,
    property_id: str,
) -> dict[str, Any]:
    """Generate a structured decision brief for a single property.

    Combines listing detail, price history, AI enrichment, and key risk flags
    into a report format suited for saving or sharing.
    """
    intel = get_intelligence_payload(
        property_repo=property_repo,
        price_history_repo=price_history_repo,
        timeline_repo=timeline_repo,
        document_repo=document_repo,
        property_id=property_id,
    )
    listing = intel["listing"]
    enr = listing.get("enrichment") or {}
    price_history = intel["price_history"]

    # -- Price change summary --
    price_change_summary: list[dict] = []
    for h in price_history[:5]:
        if h.get("price_change_pct"):
            price_change_summary.append({
                "date": h["recorded_at"],
                "price": h["price"],
                "change_pct": h["price_change_pct"],
            })

    # -- Risk flags --
    risk_flags: list[str] = []
    from datetime import datetime, timedelta, timezone
    if listing.get("created_at"):
        try:
            listed_dt = datetime.fromisoformat(listing["created_at"].replace("Z", "+00:00"))
            days_on = (datetime.now(timezone.utc) - listed_dt).days
            if days_on > 90:
                risk_flags.append(f"Listed for {days_on} days — may indicate reduced demand")
        except ValueError:
            pass

    if not listing.get("ber_rating"):
        risk_flags.append("BER rating not available — energy performance unknown")
    if not listing.get("latitude"):
        risk_flags.append("Geographic data incomplete — transport links unverifiable")
    if len(price_history) > 0 and price_history[0].get("price_change_pct", 0) <= -5:
        risk_flags.append(f"Recent price drop of {abs(price_history[0]['price_change_pct']):.1f}% — verify reason")

    # -- Grant summary --
    net_price = listing.get("net_price")
    eligible_grants_total = listing.get("eligible_grants_total")

    return {
        "property_id": property_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "completeness_score": intel["completeness_score"],
        "listing": {
            "title": listing.get("title"),
            "address": listing.get("address"),
            "county": listing.get("county"),
            "price": listing.get("price"),
            "net_price": net_price,
            "eligible_grants_total": eligible_grants_total,
            "bedrooms": listing.get("bedrooms"),
            "bathrooms": listing.get("bathrooms"),
            "floor_area_sqm": listing.get("floor_area_sqm"),
            "ber_rating": listing.get("ber_rating"),
            "property_type": listing.get("property_type"),
            "status": listing.get("status"),
            "url": listing.get("url"),
        },
        "ai_analysis": {
            "summary": enr.get("summary"),
            "value_score": enr.get("value_score"),
            "value_reasoning": enr.get("value_reasoning"),
            "pros": enr.get("pros", []),
            "cons": enr.get("cons", []),
            "neighbourhood_notes": enr.get("neighbourhood_notes"),
            "investment_potential": enr.get("investment_potential"),
        },
        "price_history_summary": price_change_summary,
        "timeline_event_count": len(intel["timeline"]),
        "evidence_document_count": len(intel["documents"]),
        "risk_flags": risk_flags,
        "data_sources": intel["data_sources"],
    }
