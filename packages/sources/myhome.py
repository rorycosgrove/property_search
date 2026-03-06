"""
MyHome.ie source adapter.

Fetches property listings from myhome.ie — Ireland's second-largest property portal.
Parses the Angular transfer state (ng-state) JSON embedded in HTML for reliable
structured data including price, bedrooms, bathrooms, BER, floor area, and images.
"""

from __future__ import annotations

import asyncio
import json
import random
import re
from datetime import UTC, datetime
from typing import Any

import httpx
from bs4 import BeautifulSoup

from packages.shared.config import settings
from packages.shared.logging import get_logger
from packages.shared.schemas import AdapterType
from packages.shared.utils import extract_county, extract_eircode, normalize_ber, parse_price
from packages.sources.base import NormalizedProperty, RawListing, SourceAdapter

logger = get_logger(__name__)


class MyHomeAdapter(SourceAdapter):
    """
    Adapter for MyHome.ie property listings.

    Fetches search result pages and extracts structured listing data from the
    Angular transfer state (<script id="ng-state">), which contains the full
    SearchResults array with all property details as JSON.
    """

    BASE_URL = "https://www.myhome.ie"

    def get_adapter_name(self) -> str:
        return "myhome"

    def get_adapter_type(self) -> AdapterType:
        return AdapterType.SCRAPER

    def get_description(self) -> str:
        return "MyHome.ie — Irish Times property portal"

    def get_default_config(self) -> dict[str, Any]:
        return {
            "counties": [],
            "property_types": [],
            "min_price": None,
            "max_price": None,
            "max_pages": 5,
        }

    def get_config_schema(self) -> dict[str, Any]:
        return {
            "counties": {"type": "array", "items": {"type": "string"}, "description": "Counties to search"},
            "property_types": {"type": "array", "items": {"type": "string"}, "description": "Property type filter"},
            "min_price": {"type": "number", "description": "Minimum price filter"},
            "max_price": {"type": "number", "description": "Maximum price filter"},
            "max_pages": {"type": "integer", "description": "Max pages per county", "default": 5},
        }

    async def fetch_listings(self, source_config: dict[str, Any]) -> list[RawListing]:
        config = {**self.get_default_config(), **source_config}
        max_pages: int = config.get("max_pages", 5)
        all_listings: list[RawListing] = []

        urls = self._build_urls(source_config.get("base_url", ""), config)

        async with httpx.AsyncClient(
            timeout=settings.request_timeout_seconds,
            headers={
                "User-Agent": settings.user_agent,
                "Accept": "text/html,application/xhtml+xml",
                "Accept-Language": "en-IE,en;q=0.9",
            },
            follow_redirects=True,
        ) as client:
            for base_url in urls:
                for page in range(1, max_pages + 1):
                    url = f"{base_url}?page={page}" if page > 1 else base_url
                    try:
                        logger.info("myhome_fetch_page", url=url, page=page)
                        response = await client.get(url)
                        response.raise_for_status()

                        listings = self._extract_listings_from_page(response.text, url)
                        if not listings:
                            break

                        all_listings.extend(listings)

                        delay = random.uniform(
                            settings.scrape_delay_min_seconds,
                            settings.scrape_delay_max_seconds,
                        )
                        await asyncio.sleep(delay)

                    except httpx.HTTPStatusError as e:
                        logger.warning("myhome_http_error", url=url, status=e.response.status_code)
                        break
                    except httpx.RequestError as e:
                        logger.error("myhome_request_error", url=url, error=str(e))
                        break

        logger.info("myhome_fetch_complete", total_listings=len(all_listings))
        return all_listings

    def parse_listing(self, raw: RawListing) -> NormalizedProperty | None:
        data = raw.raw_data
        if not data:
            return None

        try:
            address = data.get("Address", "") or data.get("DisplayAddress", "")
            display_address = data.get("DisplayAddress", address)
            price_text = data.get("PriceAsString", "")
            price = parse_price(price_text)
            county = extract_county(display_address)
            eircode = extract_eircode(display_address)
            ber = normalize_ber(data.get("BerRating"))

            # Floor area
            floor_area = None
            size_val = data.get("SizeStringMeters")
            if size_val is not None:
                try:
                    floor_area = float(size_val)
                except (ValueError, TypeError):
                    pass

            # Coordinates
            brochure_map = data.get("BrochureMap", {}) or {}
            latitude = brochure_map.get("latitude")
            longitude = brochure_map.get("longitude")
            # Fallback to Location if BrochureMap is empty
            if not latitude or not longitude:
                location = data.get("Location", {}) or {}
                lat = location.get("lat")
                lon = location.get("lon")
                if lat and lon and lat != 0 and lon != 0:
                    latitude = lat
                    longitude = lon

            # Property URL
            brochure_url = data.get("BrochureUrl", "")
            url = f"{self.BASE_URL}{brochure_url}" if brochure_url else raw.source_url

            # Listing ID
            listing_id = str(data.get("PropertyId", ""))

            # Images
            images = self._extract_images(data)

            # Property type
            property_type = self._map_property_type(data.get("PropertyType", ""))

            # First listed date
            first_listed = None
            created_on = data.get("CreatedOnDate")
            if created_on and isinstance(created_on, str):
                try:
                    first_listed = datetime.fromisoformat(created_on.replace("+00:00", "+00:00"))
                except (ValueError, TypeError):
                    pass

            return NormalizedProperty(
                title=display_address,
                description=None,
                url=url,
                address=address,
                county=county,
                eircode=eircode,
                price=price,
                price_text=price_text,
                property_type=property_type,
                bedrooms=self._safe_int(data.get("NumberOfBeds")),
                bathrooms=self._safe_int(data.get("NumberOfBathrooms")),
                floor_area_sqm=floor_area,
                ber_rating=ber,
                images=images,
                raw_data=data,
                external_id=listing_id,
                first_listed_at=first_listed,
                latitude=latitude,
                longitude=longitude,
            )
        except Exception as e:
            logger.error("myhome_parse_error", error=str(e))
            return None

    # ── Private helpers ───────────────────────────────────────────────────────

    def _build_urls(self, base_url: str, config: dict) -> list[str]:
        """Build MyHome.ie search URLs."""
        if base_url:
            return [base_url]
        counties = config.get("counties", [])
        if counties:
            return [
                f"{self.BASE_URL}/residential/{county.lower()}/property-for-sale"
                for county in counties
            ]
        return [f"{self.BASE_URL}/residential/ireland/property-for-sale"]

    def _extract_listings_from_page(self, html: str, page_url: str) -> list[RawListing]:
        """
        Extract listings from the Angular transfer state (ng-state) JSON.

        MyHome.ie is an Angular app that embeds its initial data in a
        <script id="ng-state"> tag containing JSON. The SearchResults array
        inside this JSON has all the property listing data.
        """
        soup = BeautifulSoup(html, "lxml")
        listings: list[RawListing] = []
        now = datetime.now(UTC)

        # Parse Angular transfer state
        ng_state = soup.find("script", id="ng-state")
        if ng_state and ng_state.string:
            try:
                state_data = json.loads(ng_state.string)
                search_results = self._find_search_results(state_data)

                for result in search_results:
                    property_id = result.get("PropertyId")
                    if not property_id:
                        continue
                    # Skip sale-agreed properties
                    if result.get("IsSaleAgreed"):
                        continue

                    listings.append(
                        RawListing(
                            raw_html="",
                            raw_data=result,
                            source_url=page_url,
                            fetched_at=now,
                        )
                    )
            except (json.JSONDecodeError, KeyError) as e:
                logger.warning("myhome_ng_state_parse_error", error=str(e))

        if not listings:
            # Fallback: try parsing HTML brochure links
            listings = self._extract_from_html(soup, page_url, now)

        return listings

    @staticmethod
    def _find_search_results(state_data: dict) -> list[dict]:
        """
        Find the SearchResults array in the ng-state JSON.

        The ng-state JSON has dynamic keys. We search through top-level
        values for a dict with a 'b' key containing 'SearchResults'.
        """
        for key, val in state_data.items():
            if isinstance(val, dict):
                b_val = val.get("b")
                if isinstance(b_val, dict) and "SearchResults" in b_val:
                    return b_val["SearchResults"]
        return []

    def _extract_from_html(self, soup: BeautifulSoup, page_url: str, now: datetime) -> list[RawListing]:
        """Fallback: extract listings from HTML brochure links."""
        listings: list[RawListing] = []
        brochure_links = soup.select("a[href*='/brochure/']")

        seen_ids: set[str] = set()
        for link in brochure_links:
            href = link.get("href", "")
            id_match = re.search(r"/(\d+)/?$", href)
            if not id_match:
                continue

            listing_id = id_match.group(1)
            if listing_id in seen_ids:
                continue
            seen_ids.add(listing_id)

            text = link.get_text(" ", strip=True)
            if not text:
                continue

            # Extract price from text (e.g., "€1,150,000 Address ...")
            price_match = re.search(r"(€[\d,]+(?:\.\d+)?|AMV\s*€[\d,]+(?:\.\d+)?|POA)", text)
            price_text = price_match.group(0) if price_match else ""

            # Address is the rest after price
            address = re.sub(r"^(€[\d,]+(?:\.\d+)?|AMV\s*€[\d,]+(?:\.\d+)?|POA)\s*", "", text).strip()
            # Remove trailing property details
            address = re.split(r"\d+\s*beds?", address, flags=re.IGNORECASE)[0].strip()

            data = {
                "PropertyId": int(listing_id),
                "DisplayAddress": address,
                "Address": address,
                "PriceAsString": price_text,
                "BrochureUrl": href if href.startswith("/") else href,
            }

            listings.append(
                RawListing(
                    raw_html=str(link),
                    raw_data=data,
                    source_url=page_url,
                    fetched_at=now,
                )
            )

        return listings

    @staticmethod
    def _extract_images(data: dict) -> list[dict[str, str]]:
        """Extract image URLs from MyHome listing data."""
        images = []

        # Main photo
        main_photo = data.get("MainPhoto") or data.get("MainPhotoWeb")
        if main_photo and isinstance(main_photo, str):
            images.append({"url": main_photo, "caption": "Main photo"})

        # Photos array
        photos = data.get("Photos", [])
        if isinstance(photos, list):
            for photo in photos[:9]:  # Up to 10 total with main
                url = ""
                if isinstance(photo, dict):
                    url = photo.get("Url") or photo.get("url") or ""
                elif isinstance(photo, str):
                    url = photo
                if url and url not in [img["url"] for img in images]:
                    images.append({"url": url, "caption": ""})

        return images

    @staticmethod
    def _map_property_type(text: str) -> str | None:
        if not text:
            return None
        t = text.lower()
        if "apartment" in t or "flat" in t:
            return "apartment"
        if "house" in t or "detached" in t or "semi-d" in t or "terrace" in t:
            return "house"
        if "duplex" in t:
            return "duplex"
        if "bungalow" in t:
            return "bungalow"
        if "studio" in t:
            return "studio"
        if "site" in t:
            return "site"
        return "other"

    @staticmethod
    def _safe_int(val) -> int | None:
        try:
            return int(val) if val is not None else None
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _safe_float(val) -> float | None:
        try:
            return float(str(val).replace(",", "")) if val is not None else None
        except (ValueError, TypeError):
            return None
