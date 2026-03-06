"""Property CRUD and search endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from sqlalchemy.orm import Session

from packages.shared.constants import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE
from packages.shared.schemas import PropertyFilters, PropertyListResponse, PropertyResponse
from packages.storage.database import get_db_session
from packages.storage.repositories import PropertyRepository

router = APIRouter()


@router.get("", response_model=PropertyListResponse)
def list_properties(
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE, description="Items per page"),
    county: str | None = Query(None, max_length=100),
    min_price: float | None = Query(None, ge=0),
    max_price: float | None = Query(None, ge=0),
    min_beds: int | None = Query(None, ge=0, le=20),
    max_beds: int | None = Query(None, ge=0, le=20),
    property_types: str | None = Query(None, description="Comma-separated types"),
    sale_type: str | None = None,
    keywords: str | None = Query(None, max_length=500),
    ber_ratings: str | None = Query(None, description="Comma-separated BER ratings"),
    sort_by: str = Query("created_at", pattern="^(price|created_at|date|beds|bedrooms)$"),
    sort_dir: str = Query("desc", pattern="^(asc|desc)$"),
    lat: float | None = Query(None, ge=-90, le=90),
    lng: float | None = Query(None, ge=-180, le=180),
    radius_km: float | None = Query(None, ge=0.1, le=100),
    db: Session = Depends(get_db_session),
):
    """List/search properties with full filtering, sorting, and pagination."""
    # Validate price range
    if min_price is not None and max_price is not None and min_price > max_price:
        raise HTTPException(status_code=400, detail="min_price cannot be greater than max_price")

    # Validate bedroom range
    if min_beds is not None and max_beds is not None and min_beds > max_beds:
        raise HTTPException(status_code=400, detail="min_beds cannot be greater than max_beds")

    # Validate geospatial params
    if (lat is not None or lng is not None or radius_km is not None):
        if not (lat is not None and lng is not None and radius_km is not None):
            raise HTTPException(
                status_code=400,
                detail="lat, lng, and radius_km must all be provided together"
            )

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
def get_price_history(
    property_id: str = Path(..., min_length=36, max_length=36),
    limit: int = Query(100, ge=1, le=1000, description="Max number of history entries"),
    db: Session = Depends(get_db_session),
):
    """Get price history for a property."""
    from packages.storage.repositories import PriceHistoryRepository

    repo = PriceHistoryRepository(db)
    history = repo.get_for_property(property_id)
    # Limit results to prevent large responses
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
