"""
Daft.ie source adapter.

Fetches property listings from daft.ie — Ireland's largest property portal.
Uses the Daft gateway API for reliable structured JSON data.
Handles pagination, listing parsing, and normalization.
"""

from __future__ import annotations

import asyncio
import random
import re
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlparse, urlunparse

import httpx

from packages.shared.config import settings
from packages.shared.logging import get_logger
from packages.shared.schemas import AdapterType
from packages.shared.utils import extract_county, extract_eircode, normalize_ber, parse_price
from packages.sources.base import NormalizedProperty, RawListing, SourceAdapter

logger = get_logger(__name__)

# Daft gateway API endpoint (public, used by their SPA)
DAFT_API_URL = "https://gateway.daft.ie/old/v1/listings"

_BROWSER_UA_FALLBACKS: tuple[str, ...] = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36",
)

# Daft area slug → storedShapeIds mapping
AREA_SHAPE_MAP: dict[str, list[str]] = {
    "ireland": ["daft_ie"],
    "dublin": ["daft_county-dublin"],
    "cork": ["daft_county-cork"],
    "galway": ["daft_county-galway"],
    "limerick": ["daft_county-limerick"],
    "waterford": ["daft_county-waterford"],
    "kerry": ["daft_county-kerry"],
    "kildare": ["daft_county-kildare"],
    "meath": ["daft_county-meath"],
    "wicklow": ["daft_county-wicklow"],
    "wexford": ["daft_county-wexford"],
    "louth": ["daft_county-louth"],
    "mayo": ["daft_county-mayo"],
    "donegal": ["daft_county-donegal"],
    "tipperary": ["daft_county-tipperary"],
    "kilkenny": ["daft_county-kilkenny"],
    "clare": ["daft_county-clare"],
    "laois": ["daft_county-laois"],
    "offaly": ["daft_county-offaly"],
    "westmeath": ["daft_county-westmeath"],
    "sligo": ["daft_county-sligo"],
    "roscommon": ["daft_county-roscommon"],
    "leitrim": ["daft_county-leitrim"],
    "cavan": ["daft_county-cavan"],
    "monaghan": ["daft_county-monaghan"],
    "longford": ["daft_county-longford"],
    "carlow": ["daft_county-carlow"],
}


class _DaftBlockedError(Exception):
    def __init__(self, status_code: int):
        super().__init__(f"Daft access blocked with status {status_code}")
        self.status_code = status_code


class DaftAdapter(SourceAdapter):
    """
    Adapter for Daft.ie property listings.

    Uses the Daft gateway JSON API which provides reliable structured data
    including price, bedrooms, bathrooms, BER, floor area, coordinates, and images.
    """

    BASE_URL = "https://www.daft.ie"

    def get_adapter_name(self) -> str:
        return "daft"

    def get_adapter_type(self) -> AdapterType:
        return AdapterType.API

    def get_description(self) -> str:
        return "Daft.ie — Ireland's largest property listing site"

    def supports_incremental(self) -> bool:
        return False

    def get_default_config(self) -> dict[str, Any]:
        return {
            "areas": ["ireland"],
            "property_types": [],
            "min_price": None,
            "max_price": None,
            "min_beds": None,
            "max_pages": 5,
            "max_retries": settings.max_scrape_retries,
            "stale_page_threshold": 2,
            "tail_pass_pages": 1,
            "tail_pass_min_new_ids": 3,
            "history_tail_pass_pages": 1,
            "history_tail_trigger_min_new_ids": 3,
            "recent_listing_ids": [],
            "delay_seconds": None,
        }

    def get_config_schema(self) -> dict[str, Any]:
        return {
            "areas": {"type": "array", "items": {"type": "string"}, "description": "Area slugs (e.g., 'dublin', 'cork', 'ireland')"},
            "property_types": {"type": "array", "items": {"type": "string"}, "description": "Filter by type"},
            "min_price": {"type": "number", "description": "Minimum price filter"},
            "max_price": {"type": "number", "description": "Maximum price filter"},
            "min_beds": {"type": "integer", "description": "Minimum bedrooms"},
            "max_pages": {"type": "integer", "description": "Max pages to fetch per area", "default": 5},
            "max_retries": {"type": "integer", "description": "Retry attempts for transient API errors", "default": settings.max_scrape_retries},
            "stale_page_threshold": {
                "type": "integer",
                "description": "Stop area pagination after this many pages with no new IDs",
                "default": 2,
            },
            "tail_pass_pages": {
                "type": "integer",
                "description": "Extra pages to fetch past API boundary when boundary page has many new IDs",
                "default": 1,
            },
            "tail_pass_min_new_ids": {
                "type": "integer",
                "description": "Minimum new IDs on boundary page to trigger tail pass",
                "default": 3,
            },
            "history_tail_pass_pages": {
                "type": "integer",
                "description": "Extra pages to fetch when configured max_pages boundary still contains unseen IDs",
                "default": 1,
            },
            "history_tail_trigger_min_new_ids": {
                "type": "integer",
                "description": "Minimum unseen IDs (vs previous runs) on boundary page to trigger history tail pass",
                "default": 3,
            },
            "recent_listing_ids": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Recent listing IDs seen in previous runs to support adaptive backfill",
                "default": [],
            },
            "delay_seconds": {
                "type": "number",
                "description": "Optional fixed inter-page delay override for diagnostics or testing",
                "default": None,
            },
        }

    async def fetch_listings(self, source_config: dict[str, Any]) -> list[RawListing]:
        """Fetch listings from the Daft.ie gateway API."""
        config = {**self.get_default_config(), **source_config}
        areas: list[str] = config.get("areas", ["ireland"])
        max_pages: int = config.get("max_pages", 5)
        max_retries: int = max(0, int(config.get("max_retries", settings.max_scrape_retries)))
        stale_page_threshold: int = max(1, int(config.get("stale_page_threshold", 2)))
        tail_pass_pages: int = max(0, int(config.get("tail_pass_pages", 1)))
        tail_pass_min_new_ids: int = max(1, int(config.get("tail_pass_min_new_ids", 3)))
        history_tail_pass_pages: int = max(0, int(config.get("history_tail_pass_pages", 1)))
        history_tail_trigger_min_new_ids: int = max(
            1,
            int(config.get("history_tail_trigger_min_new_ids", 3)),
        )
        recent_listing_ids = self._coerce_recent_listing_ids(config.get("recent_listing_ids"))
        recent_listing_id_set = set(recent_listing_ids)
        delay_seconds = config.get("delay_seconds")
        page_size = 20
        all_listings: list[RawListing] = []

        async with httpx.AsyncClient(
            timeout=settings.request_timeout_seconds,
            headers={
                "Content-Type": "application/json",
                "Brand": "daft",
                "Platform": "web",
                "Accept": "application/json, text/plain, */*",
                "Accept-Language": "en-IE,en;q=0.9",
                "Origin": "https://www.daft.ie",
                "Referer": "https://www.daft.ie/",
            },
        ) as client:
            for area in areas:
                shape_ids = AREA_SHAPE_MAP.get(area.lower(), [f"daft_county-{area.lower()}"])
                seen_listing_ids: set[str] = set()
                consecutive_stale_pages = 0
                tail_pages_remaining = 0
                history_tail_pages_remaining = 0
                history_tail_extension_used = False
                effective_max_pages = max_pages
                page = 0

                while page < effective_max_pages:
                    offset = page * page_size
                    payload = self._build_api_payload(shape_ids, config, offset, page_size)

                    try:
                        data = await self._fetch_page_with_retries(
                            client=client,
                            payload=payload,
                            area=area,
                            page=page,
                            offset=offset,
                            max_retries=max_retries,
                        )
                    except _DaftBlockedError as exc:
                        logger.warning(
                            "daft_area_blocked",
                            area=area,
                            page=page,
                            status=exc.status_code,
                        )
                        break
                    if data is None:
                        page += 1
                        continue

                    api_listings = data.get("listings", [])
                    if not api_listings:
                        logger.info("daft_no_more_listings", area=area, page=page)
                        break

                    now = datetime.now(UTC)
                    new_ids_on_page = 0
                    unseen_vs_history_ids_on_page = 0
                    for entry in api_listings:
                        listing_data = entry.get("listing", {})
                        if not listing_data:
                            continue

                        listing_id = str(listing_data.get("id", "")).strip()
                        if listing_id:
                            if listing_id not in seen_listing_ids:
                                seen_listing_ids.add(listing_id)
                                new_ids_on_page += 1
                            if listing_id not in recent_listing_id_set:
                                unseen_vs_history_ids_on_page += 1

                        source_url = self._build_listing_url(listing_data.get("seoFriendlyPath", ""))
                        all_listings.append(
                            RawListing(
                                raw_html="",
                                raw_data=listing_data,
                                source_url=source_url,
                                fetched_at=now,
                            )
                        )

                    if new_ids_on_page == 0:
                        consecutive_stale_pages += 1
                        if consecutive_stale_pages >= stale_page_threshold:
                            logger.info(
                                "daft_stale_page_stop",
                                area=area,
                                page=page,
                                threshold=stale_page_threshold,
                            )
                            break
                    else:
                        consecutive_stale_pages = 0

                    paging = data.get("paging", {})
                    total_pages = int(paging.get("totalPages", 0) or 0)
                    at_reported_end = total_pages > 0 and page + 1 >= total_pages

                    if at_reported_end and tail_pass_pages > 0 and new_ids_on_page >= tail_pass_min_new_ids and tail_pages_remaining == 0:
                        tail_pages_remaining = tail_pass_pages
                        effective_max_pages = max(effective_max_pages, page + 1 + tail_pass_pages)
                        logger.info(
                            "daft_tail_pass_triggered",
                            area=area,
                            page=page,
                            new_ids_on_page=new_ids_on_page,
                            tail_pass_pages=tail_pass_pages,
                        )

                    if at_reported_end and tail_pages_remaining == 0:
                        break

                    at_configured_boundary = page + 1 >= max_pages
                    can_extend_from_history = (
                        history_tail_pass_pages > 0
                        and history_tail_pages_remaining == 0
                        and not history_tail_extension_used
                        and at_configured_boundary
                        and (total_pages == 0 or page + 1 < total_pages)
                        and unseen_vs_history_ids_on_page >= history_tail_trigger_min_new_ids
                    )
                    if can_extend_from_history:
                        history_tail_extension_used = True
                        history_tail_pages_remaining = history_tail_pass_pages
                        effective_max_pages = max(
                            effective_max_pages,
                            page + 1 + history_tail_pass_pages,
                        )
                        logger.info(
                            "daft_history_tail_pass_triggered",
                            area=area,
                            page=page,
                            unseen_vs_history_ids_on_page=unseen_vs_history_ids_on_page,
                            history_tail_pass_pages=history_tail_pass_pages,
                        )

                    if tail_pages_remaining > 0:
                        tail_pages_remaining -= 1
                    if history_tail_pages_remaining > 0:
                        history_tail_pages_remaining -= 1

                    if delay_seconds is None:
                        delay = random.uniform(
                            settings.scrape_delay_min_seconds,
                            settings.scrape_delay_max_seconds,
                        )
                    else:
                        delay = max(0.0, float(delay_seconds))
                    await asyncio.sleep(delay)
                    page += 1

        logger.info("daft_fetch_complete", total_listings=len(all_listings))
        return all_listings

    def parse_listing(self, raw: RawListing) -> NormalizedProperty | None:
        """Parse a Daft.ie API listing into normalized form."""
        data = raw.raw_data
        if not data:
            return None

        try:
            title = data.get("title", "").strip()
            address = title  # Daft uses title as full address
            price_text = data.get("price", "")
            price = parse_price(price_text)
            county = extract_county(address)
            eircode = extract_eircode(address)

            # BER rating
            ber_info = data.get("ber", {}) or {}
            ber_rating_val = ber_info.get("rating") if isinstance(ber_info, dict) else None
            ber = normalize_ber(ber_rating_val)
            ber_number = ber_info.get("code") if isinstance(ber_info, dict) else None

            # Floor area
            floor_area = self._parse_floor_area(data.get("floorArea"))

            # Coordinates (GeoJSON: [longitude, latitude])
            point = data.get("point", {}) or {}
            coords = point.get("coordinates", [])
            longitude = coords[0] if len(coords) >= 2 else None
            latitude = coords[1] if len(coords) >= 2 else None

            # Images
            images = self._extract_images(data.get("media", {}))

            # Beds / baths (API returns "3 Bed", "2 Bath")
            bedrooms = self._parse_bed_bath(data.get("numBedrooms", ""))
            bathrooms = self._parse_bed_bath(data.get("numBathrooms", ""))

            # Property type
            property_type = self._map_property_type(data.get("propertyType", ""))

            # URL
            seo_path = data.get("seoFriendlyPath", "")
            url = self._normalize_listing_url(
                f"{self.BASE_URL}{seo_path}" if seo_path else raw.source_url
            )

            # Listing ID
            listing_id = str(data.get("id", "")).strip()
            url_listing_id = self._extract_listing_id_from_url(url)

            if not listing_id and url_listing_id:
                listing_id = url_listing_id

            normalized_raw_data = dict(data)
            if url_listing_id:
                normalized_raw_data["url_listing_id"] = url_listing_id
            if listing_id and url_listing_id and listing_id != url_listing_id:
                logger.info(
                    "daft_identifier_mismatch_observed",
                    listing_id=listing_id,
                    url_listing_id=url_listing_id,
                    url=url,
                )

            if not title or not address or not url or not listing_id:
                logger.debug(
                    "daft_parse_skipped_missing_required",
                    has_title=bool(title),
                    has_address=bool(address),
                    has_url=bool(url),
                    has_listing_id=bool(listing_id),
                )
                return None

            # Publish date
            publish_ts = data.get("publishDate")
            first_listed = None
            if publish_ts and isinstance(publish_ts, (int, float)):
                first_listed = datetime.fromtimestamp(publish_ts / 1000, tz=UTC)

            return NormalizedProperty(
                title=title,
                description=None,
                url=url,
                address=address,
                county=county,
                eircode=eircode,
                price=price,
                price_text=price_text,
                property_type=property_type,
                bedrooms=bedrooms,
                bathrooms=bathrooms,
                floor_area_sqm=floor_area,
                ber_rating=ber,
                ber_number=ber_number,
                images=images,
                features={"sections": data.get("sections", [])},
                raw_data=normalized_raw_data,
                external_id=listing_id,
                first_listed_at=first_listed,
                latitude=latitude,
                longitude=longitude,
            )
        except Exception as e:
            logger.error("daft_parse_error", error=str(e), url=raw.source_url)
            return None

    # ── Private helpers ───────────────────────────────────────────────────────

    async def _fetch_page_with_retries(
        self,
        client: httpx.AsyncClient,
        payload: dict[str, Any],
        area: str,
        page: int,
        offset: int,
        max_retries: int,
    ) -> dict[str, Any] | None:
        """Fetch one API page with bounded retries for transient failures."""
        attempt = 0
        while True:
            try:
                logger.info("daft_api_fetch", area=area, page=page, offset=offset, attempt=attempt)
                response = await self._post_with_headers_fallback(
                    client,
                    DAFT_API_URL,
                    payload,
                    self._build_request_headers(area=area, attempt=attempt),
                )
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as exc:
                status = exc.response.status_code
                if status == 403 and attempt < max_retries:
                    attempt += 1
                    retry_delay = min(8.0, (2 ** attempt) + random.uniform(0.0, 0.8))
                    logger.warning(
                        "daft_blocked_retry",
                        area=area,
                        page=page,
                        status=status,
                        attempt=attempt,
                        delay_seconds=retry_delay,
                    )
                    await asyncio.sleep(retry_delay)
                    continue

                if status == 401:
                    raise _DaftBlockedError(status) from exc

                if status == 403:
                    raise _DaftBlockedError(status) from exc
                transient = status == 429 or status >= 500
                if transient and attempt < max_retries:
                    attempt += 1
                    retry_delay = min(8.0, (2 ** attempt) + random.uniform(0.0, 0.8))
                    logger.warning(
                        "daft_api_retry",
                        area=area,
                        page=page,
                        status=status,
                        attempt=attempt,
                        delay_seconds=retry_delay,
                    )
                    await asyncio.sleep(retry_delay)
                    continue
                logger.warning(
                    "daft_api_error",
                    area=area,
                    page=page,
                    status=status,
                    retried=attempt,
                )
                return None
            except httpx.RequestError as exc:
                if attempt < max_retries:
                    attempt += 1
                    retry_delay = min(8.0, (2 ** attempt) + random.uniform(0.0, 0.8))
                    logger.warning(
                        "daft_request_retry",
                        area=area,
                        page=page,
                        attempt=attempt,
                        delay_seconds=retry_delay,
                        error=str(exc),
                    )
                    await asyncio.sleep(retry_delay)
                    continue
                logger.error(
                    "daft_request_error",
                    area=area,
                    page=page,
                    retried=attempt,
                    error=str(exc),
                )
                return None

    @staticmethod
    def _looks_like_default_bot_ua(user_agent: str) -> bool:
        raw = (user_agent or "").strip().lower()
        return (not raw) or raw.startswith("propertysearch/")

    def _build_request_headers(self, *, area: str, attempt: int) -> dict[str, str]:
        configured_ua = (settings.user_agent or "").strip()
        if self._looks_like_default_bot_ua(configured_ua):
            user_agent = random.choice(_BROWSER_UA_FALLBACKS)
        else:
            user_agent = configured_ua

        # Derive sec-ch-ua version from UA string for consistency.
        ch_ver = "133"
        is_windows = "Windows" in user_agent
        platform = '"Windows"' if is_windows else ('"macOS"' if "Mac" in user_agent else '"Linux"')
        return {
            "User-Agent": user_agent,
            "sec-ch-ua": f'"Not(A:Brand";v="99", "Google Chrome";v="{ch_ver}", "Chromium";v="{ch_ver}"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": platform,
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-site",
        }

    @staticmethod
    async def _post_with_headers_fallback(
        client: httpx.AsyncClient,
        url: str,
        payload: dict[str, Any],
        headers: dict[str, str],
    ) -> httpx.Response:
        try:
            return await client.post(url, json=payload, headers=headers)
        except TypeError:
            # Test doubles may not accept per-request headers.
            return await client.post(url, json=payload)

    def _build_listing_url(self, seo_path: str) -> str:
        """Build and normalize a Daft listing URL from API path fragments."""
        raw = f"{self.BASE_URL}{seo_path}" if seo_path else ""
        return self._normalize_listing_url(raw)

    @staticmethod
    def _normalize_listing_url(url: str) -> str:
        """Normalize listing URL and strip query/fragment noise."""
        raw = (url or "").strip()
        if not raw:
            return ""
        parsed = urlparse(raw)
        if not parsed.scheme or not parsed.netloc:
            return ""
        normalized_path = parsed.path.rstrip("/")
        normalized = parsed._replace(scheme=parsed.scheme.lower(), netloc=parsed.netloc.lower(), path=normalized_path, query="", fragment="")
        return urlunparse(normalized)

    @staticmethod
    def _extract_listing_id_from_url(url: str) -> str | None:
        """Extract numeric listing ID from canonical Daft listing URLs."""
        if not url:
            return None
        parsed = urlparse(url)
        path = parsed.path.rstrip("/")
        if not path.startswith("/for-sale/"):
            return None
        match = re.search(r"/(\d+)$", path)
        return match.group(1) if match else None

    @classmethod
    def listing_identifiers(cls, raw_data: dict[str, Any] | None, source_url: str = "") -> set[str]:
        """Return all comparable identifiers for a Daft listing."""
        identifiers: set[str] = set()
        data = raw_data or {}
        listing_id = str(data.get("id", "")).strip()
        if listing_id:
            identifiers.add(listing_id)
        url_listing_id = cls._extract_listing_id_from_url(source_url)
        if url_listing_id:
            identifiers.add(url_listing_id)
        raw_url_listing_id = str(data.get("url_listing_id", "")).strip()
        if raw_url_listing_id:
            identifiers.add(raw_url_listing_id)
        return identifiers

    @classmethod
    def listing_matches_identifier(
        cls,
        *,
        raw_data: dict[str, Any] | None,
        source_url: str,
        external_id: str,
    ) -> bool:
        """Return True when the requested identifier matches the API ID or URL ID."""
        target = str(external_id or "").strip()
        if not target:
            return False
        return target in cls.listing_identifiers(raw_data, source_url)

    @staticmethod
    def _coerce_recent_listing_ids(value: Any, limit: int = 600) -> list[str]:
        """Return sanitized recent listing IDs from source config."""
        if not isinstance(value, list):
            return []
        cleaned: list[str] = []
        for item in value:
            listing_id = str(item).strip()
            if listing_id:
                cleaned.append(listing_id)
            if len(cleaned) >= limit:
                break
        return cleaned

    @staticmethod
    def _build_api_payload(shape_ids: list[str], config: dict, offset: int, page_size: int) -> dict:
        """Build the Daft gateway API request payload."""
        payload: dict[str, Any] = {
            "section": "residential-for-sale",
            "filters": [
                {"name": "adState", "values": ["published"]},
            ],
            "geoFilter": {"storedShapeIds": shape_ids},
            "paging": {"from": str(offset), "pageSize": str(page_size)},
        }

        min_price = config.get("min_price")
        max_price = config.get("max_price")
        if min_price:
            payload["filters"].append({"name": "salePrice_from", "values": [str(int(min_price))]})
        if max_price:
            payload["filters"].append({"name": "salePrice_to", "values": [str(int(max_price))]})

        min_beds = config.get("min_beds")
        if min_beds:
            payload["filters"].append({"name": "numBeds_from", "values": [str(int(min_beds))]})

        return payload

    @staticmethod
    def _parse_bed_bath(text: str) -> int | None:
        """Extract numeric value from '3 Bed' or '2 Bath' strings."""
        if not text:
            return None
        match = re.search(r"(\d+)", str(text))
        return int(match.group(1)) if match else None

    @staticmethod
    def _parse_floor_area(floor_area: dict | None) -> float | None:
        """Extract floor area in square meters from API response."""
        if not floor_area or not isinstance(floor_area, dict):
            return None
        try:
            value = floor_area.get("value", "")
            return float(str(value).replace(",", "")) if value else None
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _extract_images(media: dict | None) -> list[dict[str, str]]:
        """Extract image URLs from media section."""
        if not media or not isinstance(media, dict):
            return []
        images = []
        for img in media.get("images", [])[:10]:
            url = (
                img.get("size720x480")
                or img.get("size600x600")
                or img.get("size400x300")
                or img.get("size360x240")
                or ""
            )
            if url:
                images.append({"url": url, "caption": ""})
        return images

    @staticmethod
    def _map_property_type(type_text: str) -> str | None:
        """Map Daft property type text to our enum values."""
        if not type_text:
            return None
        text = type_text.lower()
        if "apartment" in text or "flat" in text:
            return "apartment"
        if "house" in text or "detached" in text or "semi-d" in text or "terrace" in text:
            return "house"
        if "duplex" in text:
            return "duplex"
        if "bungalow" in text:
            return "bungalow"
        if "studio" in text:
            return "studio"
        if "site" in text:
            return "site"
        return "other"
