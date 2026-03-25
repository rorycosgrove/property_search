"""
Geocoding service.

Uses Nominatim (OpenStreetMap) for forward geocoding of Irish addresses.
Includes caching and rate limiting (1 request/second for Nominatim TOS).
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import Any

from packages.shared.config import settings
from packages.shared.logging import get_logger

logger = get_logger(__name__)

# ── Geocode result ────────────────────────────────────────────────────────────


@dataclass
class GeoResult:
    """Result from geocoding a single address."""
    latitude: float
    longitude: float
    display_name: str = ""
    confidence: float = 0.0
    raw: dict[str, Any] | None = None


# ── Simple in-memory cache ────────────────────────────────────────────────────

_cache: dict[str, GeoResult | None] = {}
_last_request_time: float = 0.0


def _build_query(address: str, county: str | None = None) -> str:
    query = address
    if county and county.lower() not in address.lower():
        query = f"{address}, Co. {county}"
    return f"{query}, Ireland"


async def geocode_address(address: str, county: str | None = None, db: Any | None = None) -> GeoResult | None:
    """
    Geocode an Irish address using Nominatim.

    Respects Nominatim usage policy (max 1 request/second).
    Returns None if geocoding fails.
    """
    global _last_request_time

    if not address:
        return None

    query = _build_query(address, county)

    # Check cache
    cache_key = query.lower().strip()
    if cache_key in _cache:
        return _cache[cache_key]

    if db is not None:
        try:
            from packages.storage.repositories import GeocodeCacheRepository

            cache_repo = GeocodeCacheRepository(db)
            cached = cache_repo.record_hit(cache_key)
            if cached:
                geo = GeoResult(
                    latitude=float(cached.latitude),
                    longitude=float(cached.longitude),
                    display_name=cached.display_name or "",
                    confidence=float(cached.confidence or 0.0),
                    raw=cached.raw_json or {},
                )
                _cache[cache_key] = geo
                return geo
        except Exception as exc:
            logger.warning("geocode_cache_lookup_error", query=query, error=str(exc))

    # Rate limit — Nominatim requires max 1 request/second
    now = time.monotonic()
    elapsed = now - _last_request_time
    if elapsed < 1.0:
        await asyncio.sleep(1.0 - elapsed)

    try:
        import httpx

        async with httpx.AsyncClient(
            timeout=settings.request_timeout_seconds,
            headers={"User-Agent": settings.geocoder_user_agent},
        ) as client:
            params = {
                "q": query,
                "format": "jsonv2",
                "countrycodes": "ie,gb",
                "limit": 1,
                "addressdetails": 1,
            }
            base_url = "https://nominatim.openstreetmap.org/search"
            response = await client.get(base_url, params=params)
            response.raise_for_status()
            _last_request_time = time.monotonic()

            results = response.json()

            if not results:
                logger.debug("geocode_no_results", query=query)
                _cache[cache_key] = None
                return None

            result = results[0]
            geo = GeoResult(
                latitude=float(result["lat"]),
                longitude=float(result["lon"]),
                display_name=result.get("display_name", ""),
                confidence=float(result.get("importance", 0)),
                raw=result,
            )

            _cache[cache_key] = geo
            if db is not None:
                try:
                    from packages.storage.repositories import GeocodeCacheRepository

                    GeocodeCacheRepository(db).upsert_success(
                        query=cache_key,
                        provider=settings.geocoder_provider,
                        latitude=geo.latitude,
                        longitude=geo.longitude,
                        display_name=geo.display_name,
                        confidence=geo.confidence,
                        raw_json=geo.raw or {},
                    )
                except Exception as exc:
                    logger.warning("geocode_cache_write_error", query=query, error=str(exc))
            logger.debug(
                "geocode_success",
                query=query,
                lat=geo.latitude,
                lng=geo.longitude,
            )
            return geo

    except Exception as e:
        logger.warning("geocode_error", query=query, error=str(e))
        _last_request_time = time.monotonic()
        return None


def clear_geocode_cache() -> None:
    """Clear the in-memory geocode cache."""
    _cache.clear()
