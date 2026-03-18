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
