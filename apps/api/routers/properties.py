"""Property CRUD and search endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from packages.shared.schemas import PropertyFilters, PropertyListResponse, PropertyResponse
from packages.storage.database import get_db_session
from packages.storage.repositories import PropertyRepository

router = APIRouter()


@router.get("", response_model=PropertyListResponse)
def list_properties(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    county: str | None = None,
    min_price: float | None = None,
    max_price: float | None = None,
    min_beds: int | None = None,
    max_beds: int | None = None,
    property_types: str | None = Query(None, description="Comma-separated types"),
    sale_type: str | None = None,
    keywords: str | None = None,
    ber_ratings: str | None = Query(None, description="Comma-separated BER ratings"),
    sort_by: str = "first_listed_at",
    sort_dir: str = "desc",
    lat: float | None = None,
    lng: float | None = None,
    radius_km: float | None = None,
    db: Session = Depends(get_db_session),
):
    """List/search properties with full filtering, sorting, and pagination."""
    repo = PropertyRepository(db)

    # Parse comma-separated lists
    type_list = [t.strip() for t in property_types.split(",")] if property_types else None
    ber_list = [b.strip() for b in ber_ratings.split(",")] if ber_ratings else None

    filters = PropertyFilters(
        counties=[county] if county else None,
        min_price=min_price,
        max_price=max_price,
        min_bedrooms=min_beds,
        max_bedrooms=max_beds,
        property_types=type_list,
        ber_ratings=ber_list,
        lat=lat,
        lng=lng,
        radius_km=radius_km,
        sort_by=sort_by,
        sort_order=sort_dir,
        page=page,
        per_page=size,
    )

    items, total = repo.list_properties(filters)

    return {
        "items": [_to_response(p) for p in items],
        "total": total,
        "page": page,
        "per_page": size,
        "pages": -(-total // size),  # ceil division
    }


@router.get("/{property_id}", response_model=PropertyResponse)
def get_property(property_id: str, db: Session = Depends(get_db_session)):
    """Get a single property by ID with full details."""
    repo = PropertyRepository(db)
    prop = repo.get_by_id(property_id)
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")
    return _to_response(prop)


@router.get("/{property_id}/price-history")
def get_price_history(property_id: str, db: Session = Depends(get_db_session)):
    """Get price history for a property."""
    from packages.storage.repositories import PriceHistoryRepository

    repo = PriceHistoryRepository(db)
    history = repo.get_for_property(property_id)
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


@router.get("/{property_id}/similar")
def get_similar(
    property_id: str,
    limit: int = Query(5, ge=1, le=20),
    db: Session = Depends(get_db_session),
):
    """Find similar properties based on location, price, and type."""
    repo = PropertyRepository(db)
    prop = repo.get_by_id(property_id)
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")

    similar = repo.find_similar(property_id, limit=limit)
    return [_to_response(s) for s in similar]


def _to_response(prop) -> dict:
    """Convert a Property ORM model to a response dict."""
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
    if hasattr(prop, 'price_history') and prop.price_history:
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
        "enrichment": enrichment,
        "price_history": price_history,
    }
