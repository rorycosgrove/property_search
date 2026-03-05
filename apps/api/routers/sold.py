"""Sold property (PPR) endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from packages.shared.schemas import SoldPropertyFilters
from packages.storage.database import get_db_session
from packages.storage.repositories import SoldPropertyRepository

router = APIRouter()


@router.get("")
def list_sold(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    county: str | None = None,
    min_price: float | None = None,
    max_price: float | None = None,
    min_year: int | None = None,
    max_year: int | None = None,
    sort_by: str = "sale_date",
    sort_dir: str = "desc",
    lat: float | None = None,
    lng: float | None = None,
    radius_km: float | None = None,
    db: Session = Depends(get_db_session),
):
    """List sold properties (PPR data) with filtering and pagination."""
    from datetime import date as date_type

    repo = SoldPropertyRepository(db)
    filters = SoldPropertyFilters(
        county=county,
        min_price=min_price,
        max_price=max_price,
        date_from=date_type(min_year, 1, 1) if min_year else None,
        date_to=date_type(max_year, 12, 31) if max_year else None,
        lat=lat,
        lng=lng,
        radius_km=radius_km,
        page=page,
        per_page=size,
    )
    items, total = repo.list_sold(filters)

    return {
        "items": [
            {
                "id": str(s.id),
                "address": s.address,
                "county": s.county,
                "price": float(s.price) if s.price else None,
                "sale_date": s.sale_date.isoformat() if s.sale_date else None,
                "is_new": s.is_new,
                "is_full_market_price": s.is_full_market_price,
                "property_size_description": s.property_size_description,
                "latitude": s.latitude,
                "longitude": s.longitude,
            }
            for s in items
        ],
        "total": total,
        "page": page,
        "per_page": size,
        "pages": -(-total // size),
    }


@router.get("/nearby")
def get_nearby_sold(
    lat: float = Query(...),
    lng: float = Query(...),
    radius_km: float = Query(5, ge=0.1, le=50),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db_session),
):
    """Get sold properties near a location."""
    repo = SoldPropertyRepository(db)
    items = repo.get_nearby_sold(lat=lat, lng=lng, radius_km=radius_km, limit=limit)
    return [
        {
            "id": str(s.id),
            "address": s.address,
            "county": s.county,
            "price": float(s.price) if s.price else None,
            "sale_date": s.sale_date.isoformat() if s.sale_date else None,
            "latitude": s.latitude,
            "longitude": s.longitude,
        }
        for s in items
    ]


@router.get("/stats")
def get_sold_stats(
    county: str | None = None,
    group_by: str = Query("quarter", pattern="^(month|quarter|year)$"),
    db: Session = Depends(get_db_session),
):
    """Get sold property statistics grouped by time period."""
    repo = SoldPropertyRepository(db)
    return repo.get_stats_by_county(county=county, group_by=group_by)
