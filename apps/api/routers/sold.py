"""Sold property (PPR) endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from packages.sold.service import (
    list_sold_payload,
    nearby_sold_payload,
    sold_stats_payload,
)
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
    address_contains: str | None = Query(None, max_length=255),
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
    repo = SoldPropertyRepository(db)
    return list_sold_payload(
        repo=repo,
        page=page,
        size=size,
        county=county,
        min_price=min_price,
        max_price=max_price,
        address_contains=address_contains,
        min_year=min_year,
        max_year=max_year,
        lat=lat,
        lng=lng,
        radius_km=radius_km,
    )


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
    return nearby_sold_payload(repo=repo, lat=lat, lng=lng, radius_km=radius_km, limit=limit)


@router.get("/stats")
def get_sold_stats(
    county: str | None = None,
    group_by: str = Query("quarter", pattern="^(month|quarter|year)$"),
    db: Session = Depends(get_db_session),
):
    """Get sold property statistics grouped by time period."""
    repo = SoldPropertyRepository(db)
    return sold_stats_payload(repo=repo, county=county, group_by=group_by)
