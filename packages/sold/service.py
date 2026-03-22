from __future__ import annotations

from datetime import date as date_type
from typing import Any

from packages.shared.schemas import SoldPropertyFilters


class SoldServiceError(Exception):
    """Base exception for sold-property domain service errors."""


class SoldValidationError(SoldServiceError):
    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


def build_sold_filters(
    *,
    page: int,
    size: int,
    county: str | None,
    min_price: float | None,
    max_price: float | None,
    min_year: int | None,
    max_year: int | None,
    lat: float | None,
    lng: float | None,
    radius_km: float | None,
) -> SoldPropertyFilters:
    return SoldPropertyFilters(
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


def sold_to_dict(sold: Any) -> dict[str, Any]:
    return {
        "id": str(sold.id),
        "address": sold.address,
        "county": sold.county,
        "price": float(sold.price) if sold.price else None,
        "sale_date": sold.sale_date.isoformat() if sold.sale_date else None,
        "is_new": sold.is_new,
        "is_full_market_price": sold.is_full_market_price,
        "property_size_description": sold.property_size_description,
        "latitude": sold.latitude,
        "longitude": sold.longitude,
    }


def list_sold_payload(
    *,
    repo: Any,
    page: int,
    size: int,
    county: str | None,
    min_price: float | None,
    max_price: float | None,
    min_year: int | None,
    max_year: int | None,
    lat: float | None,
    lng: float | None,
    radius_km: float | None,
) -> dict[str, Any]:
    filters = build_sold_filters(
        page=page,
        size=size,
        county=county,
        min_price=min_price,
        max_price=max_price,
        min_year=min_year,
        max_year=max_year,
        lat=lat,
        lng=lng,
        radius_km=radius_km,
    )
    items, total = repo.list_sold(filters)
    return {
        "items": [sold_to_dict(item) for item in items],
        "total": total,
        "page": page,
        "per_page": size,
        "pages": -(-total // size),
    }


def nearby_sold_payload(*, repo: Any, lat: float, lng: float, radius_km: float, limit: int) -> list[dict[str, Any]]:
    items = repo.get_nearby_sold(lat=lat, lng=lng, radius_km=radius_km, limit=limit)
    return [
        {
            "id": str(item.id),
            "address": item.address,
            "county": item.county,
            "price": float(item.price) if item.price else None,
            "sale_date": item.sale_date.isoformat() if item.sale_date else None,
            "latitude": item.latitude,
            "longitude": item.longitude,
        }
        for item in items
    ]


def sold_stats_payload(*, repo: Any, county: str | None, group_by: str) -> list[dict[str, Any]]:
    return repo.get_stats_by_county(county=county, group_by=group_by)
