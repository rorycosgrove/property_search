"""
PropertyPal.com source adapter.

Fetches property listings from propertypal.com — covers both
Northern Ireland and Republic of Ireland listings.
Parses the Next.js __NEXT_DATA__ JSON for reliable structured data.
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


class PropertyPalAdapter(SourceAdapter):
    """
    Adapter for PropertyPal.com listings (Ireland & Northern Ireland).

    Extracts structured listing data from the Next.js __NEXT_DATA__ JSON
    payload embedded in the HTML, which contains the full results array
    with property details, prices, coordinates, and images.
    """

    BASE_URL = "https://www.propertypal.com"

    def get_adapter_name(self) -> str:
        return "propertypal"

    def get_adapter_type(self) -> AdapterType:
        return AdapterType.SCRAPER

    def get_description(self) -> str:
        return "PropertyPal.com — property listings for Ireland & Northern Ireland"

    def get_default_config(self) -> dict[str, Any]:
        return {
            "areas": ["republic-of-ireland"],
            "max_pages": 5,
        }

    def get_config_schema(self) -> dict[str, Any]:
        return {
            "areas": {"type": "array", "items": {"type": "string"}, "description": "Area slugs"},
            "max_pages": {"type": "integer", "default": 5},
        }

    async def fetch_listings(self, source_config: dict[str, Any]) -> list[RawListing]:
        config = {**self.get_default_config(), **source_config}
        areas: list[str] = config.get("areas", ["republic-of-ireland"])

        # Support "region" key from seed config for backwards compat
        region = source_config.get("region")
        if region and region not in areas:
            areas = [region]

        max_pages: int = config.get("max_pages", 5)
        all_listings: list[RawListing] = []

        _PP_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36"
        async with httpx.AsyncClient(
            timeout=settings.request_timeout_seconds,
            headers={
                "User-Agent": _PP_UA,
                "sec-ch-ua": '"Not(A:Brand";v="99", "Google Chrome";v="133", "Chromium";v="133"',
                "sec-ch-ua-mobile": "?0",
                "sec-ch-ua-platform": '"Windows"',
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-IE,en;q=0.9",
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "none",
                "Upgrade-Insecure-Requests": "1",
            },
            follow_redirects=True,
        ) as client:
            for area in areas:
                for page in range(1, max_pages + 1):
                    url = f"{self.BASE_URL}/property-for-sale/{area}/page-{page}" if page > 1 else f"{self.BASE_URL}/property-for-sale/{area}"
                    try:
                        logger.info("propertypal_fetch_page", url=url, page=page)
                        response = await client.get(url)
                        response.raise_for_status()

                        listings = self._extract_listings_from_page(response.text, url)
                        if not listings:
                            break

                        all_listings.extend(listings)
                        delay = random.uniform(settings.scrape_delay_min_seconds, settings.scrape_delay_max_seconds)
                        await asyncio.sleep(delay)

                    except httpx.HTTPStatusError as e:
                        if e.response.status_code in {401, 403}:
                            logger.warning(
                                "propertypal_area_blocked",
                                url=url,
                                area=area,
                                page=page,
                                status=e.response.status_code,
                            )
                            break
                        logger.warning("propertypal_http_error", url=url, status=e.response.status_code)
                        break
                    except httpx.RequestError as e:
                        logger.error("propertypal_request_error", url=url, error=str(e))
                        break

        logger.info("propertypal_fetch_complete", total_listings=len(all_listings))
        return all_listings

    def parse_listing(self, raw: RawListing) -> NormalizedProperty | None:
        data = raw.raw_data
        if not data:
            return None

        try:
            address = str(data.get("displayAddress", "") or "").strip()
            path = data.get("path", "")
            url = (f"{self.BASE_URL}{path}" if path else raw.source_url).strip()

            if not address or not url:
                logger.debug(
                    "propertypal_parse_skipped_missing_required",
                    has_address=bool(address),
                    has_url=bool(url),
                )
                return None

            # Price
            price_info = data.get("price", {}) or {}
            price_val = price_info.get("price")
            price = float(price_val) if price_val is not None else None
            currency = price_info.get("currencySymbol", "")
            prefix = price_info.get("pricePrefix", "")
            suffix = price_info.get("priceSuffix", "")
            if price_val is not None:
                price_text = f"{prefix} {currency}{price_val:,.0f} {suffix}".strip()
            elif price_info.get("priceOnApplication"):
                price_text = "POA"
                price = None
            else:
                price_text = ""

            county = extract_county(address)
            eircode = extract_eircode(address)

            # BER rating — can be a string or a dict with alphanumericRating
            ber_raw = data.get("ber")
            if isinstance(ber_raw, dict):
                ber_raw = ber_raw.get("alphanumericRating") or ber_raw.get("rating")
            ber = normalize_ber(ber_raw)

            # Property type from style
            style = data.get("style", {}) or {}
            style_text = style.get("text", "") if isinstance(style, dict) else str(style)
            property_type = self._map_type(style_text)

            # Coordinates
            coord = data.get("coordinate", {}) or {}
            latitude = coord.get("latitude")
            longitude = coord.get("longitude")

            # Images
            images = self._extract_images(data.get("images", []))

            # Listing ID
            listing_id = str(data.get("pathId", data.get("id", "")))

            return NormalizedProperty(
                title=address,
                description=data.get("briefText"),
                url=url,
                address=address,
                address_line1=data.get("displayAddressLine1"),
                address_line2=data.get("displayAddressLine2"),
                town=data.get("town"),
                county=county or data.get("region"),
                eircode=eircode or data.get("postcode"),
                price=price,
                price_text=price_text,
                property_type=property_type,
                bedrooms=self._safe_int(data.get("numBedrooms")),
                bathrooms=self._safe_int(data.get("numBathrooms")),
                ber_rating=ber,
                images=images,
                raw_data=data,
                external_id=listing_id,
                latitude=latitude,
                longitude=longitude,
            )
        except Exception as e:
            logger.error("propertypal_parse_error", error=str(e))
            return None

    def _extract_listings_from_page(self, html: str, page_url: str) -> list[RawListing]:
        """
        Extract listings from the Next.js __NEXT_DATA__ JSON.

        PropertyPal is a Next.js app that embeds its initial data in a
        <script id="__NEXT_DATA__"> tag. The listing data is at:
        props.pageProps.initialState.properties.data.results
        """
        soup = BeautifulSoup(html, "lxml")
        listings: list[RawListing] = []
        now = datetime.now(UTC)

        # Parse __NEXT_DATA__ JSON
        next_data_script = soup.find("script", id="__NEXT_DATA__")
        if next_data_script and next_data_script.string:
            try:
                next_data = json.loads(next_data_script.string)
                results = (
                    next_data.get("props", {})
                    .get("pageProps", {})
                    .get("initialState", {})
                    .get("properties", {})
                    .get("data", {})
                    .get("results", [])
                )

                for result in results:
                    if not result.get("id"):
                        continue
                    # Skip hidden/unpublished listings
                    if result.get("hidden") or not result.get("published", True):
                        continue

                    path = result.get("path", "")
                    listings.append(RawListing(
                        raw_html="",
                        raw_data=result,
                        source_url=f"{self.BASE_URL}{path}" if path else page_url,
                        fetched_at=now,
                    ))

            except (json.JSONDecodeError, KeyError) as e:
                logger.warning("propertypal_next_data_parse_error", error=str(e))

        if not listings:
            # Fallback: parse listing links from HTML
            listings = self._extract_from_html(soup, page_url, now)

        return listings

    def _extract_from_html(self, soup: BeautifulSoup, page_url: str, now: datetime) -> list[RawListing]:
        """Fallback: extract listings from HTML links with numeric IDs."""
        listings: list[RawListing] = []
        seen_ids: set[str] = set()

        for link in soup.select("a[href]"):
            href = link.get("href", "")
            # Match PropertyPal listing URLs: /address-slug/NUMERIC_ID
            id_match = re.search(r"^/([a-z0-9-]+)/(\d{5,})$", href)
            if not id_match:
                continue

            listing_id = id_match.group(2)
            if listing_id in seen_ids:
                continue
            seen_ids.add(listing_id)

            text = link.get_text(" ", strip=True)
            if not text or len(text) < 10:
                continue

            # Try to extract price and address from link text
            price_match = re.search(r"((?:Guide Price|Offers Over|Asking Price)?\s*£[\d,]+)", text)
            price_text = price_match.group(0).strip() if price_match else ""

            # The address is usually repeated, take the first occurrence
            address_match = re.search(r"(?:Guide Price|Offers Over|Asking Price)?\s*£[\d,]+\s*(.+?)(?:\d+\s*Bed|\s*$)", text)
            address = address_match.group(1).strip() if address_match else text[:100]

            # Beds
            bed_match = re.search(r"(\d+)\s*Bed", text)
            bedrooms = int(bed_match.group(1)) if bed_match else None

            data = {
                "pathId": listing_id,
                "id": int(listing_id),
                "path": href,
                "displayAddress": address,
                "price": {"price": parse_price(price_text), "currencySymbol": "£", "pricePrefix": ""},
                "numBedrooms": bedrooms,
            }

            listings.append(RawListing(
                raw_html=str(link),
                raw_data=data,
                source_url=f"{self.BASE_URL}{href}",
                fetched_at=now,
            ))

        return listings

    @staticmethod
    def _extract_images(images_data: list) -> list[dict[str, str]]:
        """Extract image URLs from PropertyPal images array."""
        images = []
        if not isinstance(images_data, list):
            return images
        for img in images_data[:10]:
            if isinstance(img, dict):
                url = img.get("url", "")
                if url:
                    images.append({"url": url, "caption": img.get("imageType", "")})
        return images

    @staticmethod
    def _map_type(text: str) -> str | None:
        if not text:
            return None
        t = text.lower()
        if "apartment" in t or "flat" in t:
            return "apartment"
        if "house" in t or "detached" in t or "semi" in t or "terrace" in t:
            return "house"
        if "bungalow" in t:
            return "bungalow"
        if "site" in t or "land" in t:
            return "site"
        return "other"

    @staticmethod
    def _safe_int(val) -> int | None:
        try:
            return int(val) if val is not None else None
        except (ValueError, TypeError):
            return None
