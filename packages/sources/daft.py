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
from datetime import datetime, timezone
from typing import Any

import httpx

from packages.shared.config import settings
from packages.shared.logging import get_logger
from packages.shared.schemas import AdapterType
from packages.shared.utils import extract_county, extract_eircode, normalize_ber, parse_price
from packages.sources.base import NormalizedProperty, RawListing, SourceAdapter

logger = get_logger(__name__)

# Daft gateway API endpoint (public, used by their SPA)
DAFT_API_URL = "https://gateway.daft.ie/old/v1/listings"

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
        return AdapterType.SCRAPER

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
        }

    def get_config_schema(self) -> dict[str, Any]:
        return {
            "areas": {"type": "array", "items": {"type": "string"}, "description": "Area slugs (e.g., 'dublin', 'cork', 'ireland')"},
            "property_types": {"type": "array", "items": {"type": "string"}, "description": "Filter by type"},
            "min_price": {"type": "number", "description": "Minimum price filter"},
            "max_price": {"type": "number", "description": "Maximum price filter"},
            "min_beds": {"type": "integer", "description": "Minimum bedrooms"},
            "max_pages": {"type": "integer", "description": "Max pages to fetch per area", "default": 5},
        }

    async def fetch_listings(self, source_config: dict[str, Any]) -> list[RawListing]:
        """Fetch listings from the Daft.ie gateway API."""
        config = {**self.get_default_config(), **source_config}
        areas: list[str] = config.get("areas", ["ireland"])
        max_pages: int = config.get("max_pages", 5)
        page_size = 20
        all_listings: list[RawListing] = []

        async with httpx.AsyncClient(
            timeout=settings.request_timeout_seconds,
            headers={
                "User-Agent": settings.user_agent,
                "Content-Type": "application/json",
                "Brand": "daft",
                "Platform": "web",
            },
        ) as client:
            for area in areas:
                shape_ids = AREA_SHAPE_MAP.get(area.lower(), [f"daft_county-{area.lower()}"])

                for page in range(max_pages):
                    offset = page * page_size
                    payload = self._build_api_payload(shape_ids, config, offset, page_size)

                    try:
                        logger.info("daft_api_fetch", area=area, page=page, offset=offset)
                        response = await client.post(DAFT_API_URL, json=payload)
                        response.raise_for_status()

                        data = response.json()
                        api_listings = data.get("listings", [])

                        if not api_listings:
                            logger.info("daft_no_more_listings", area=area, page=page)
                            break

                        now = datetime.now(timezone.utc)
                        for entry in api_listings:
                            listing_data = entry.get("listing", {})
                            if listing_data:
                                all_listings.append(
                                    RawListing(
                                        raw_html="",
                                        raw_data=listing_data,
                                        source_url=f"{self.BASE_URL}{listing_data.get('seoFriendlyPath', '')}",
                                        fetched_at=now,
                                    )
                                )

                        # Check if we've reached the last page
                        paging = data.get("paging", {})
                        total_pages = paging.get("totalPages", 0)
                        if page + 1 >= total_pages:
                            break

                        # Respect rate limits
                        delay = random.uniform(
                            settings.scrape_delay_min_seconds,
                            settings.scrape_delay_max_seconds,
                        )
                        await asyncio.sleep(delay)

                    except httpx.HTTPStatusError as e:
                        logger.warning("daft_api_error", area=area, status=e.response.status_code)
                        break
                    except httpx.RequestError as e:
                        logger.error("daft_request_error", area=area, error=str(e))
                        break

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
            url = f"{self.BASE_URL}{seo_path}" if seo_path else raw.source_url

            # Listing ID
            listing_id = str(data.get("id", ""))

            # Publish date
            publish_ts = data.get("publishDate")
            first_listed = None
            if publish_ts and isinstance(publish_ts, (int, float)):
                first_listed = datetime.fromtimestamp(publish_ts / 1000, tz=timezone.utc)

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
                raw_data=data,
                external_id=listing_id,
                first_listed_at=first_listed,
                latitude=latitude,
                longitude=longitude,
            )
        except Exception as e:
            logger.error("daft_parse_error", error=str(e), url=raw.source_url)
            return None

    # ── Private helpers ───────────────────────────────────────────────────────

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
