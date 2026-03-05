"""
Property data normalizer.

Takes NormalizedProperty data from source adapters and produces
fully normalized, deduplicated, enriched property records ready
for database insertion.
"""

from __future__ import annotations

import re
from typing import Any

from packages.shared.logging import get_logger
from packages.shared.utils import (
    content_hash,
    extract_county,
    extract_eircode,
    fuzzy_address_hash,
    normalize_address,
    normalize_ber,
    parse_price,
)
from packages.sources.base import NormalizedProperty

logger = get_logger(__name__)

# ── Property-type synonyms ────────────────────────────────────────────────────

_TYPE_MAP: dict[str, str] = {
    "detached house": "house",
    "semi-detached house": "house",
    "semi-d": "house",
    "terraced house": "house",
    "end-of-terrace": "house",
    "townhouse": "house",
    "country home": "house",
    "period home": "house",
    "apartment": "apartment",
    "flat": "apartment",
    "penthouse": "apartment",
    "maisonette": "apartment",
    "duplex": "duplex",
    "bungalow": "bungalow",
    "studio": "studio",
    "site": "site",
    "development site": "site",
    "land": "site",
}


def normalize_property_type(raw: str | None) -> str | None:
    """Map raw property type strings to canonical values."""
    if not raw:
        return None
    key = raw.strip().lower()
    if key in _TYPE_MAP:
        return _TYPE_MAP[key]
    # Check partial matches
    for pattern, mapped in _TYPE_MAP.items():
        if pattern in key:
            return mapped
    return key


def normalize_sale_type(raw: str | None) -> str:
    """Normalize sale type to a valid SaleType enum value."""
    if not raw:
        return "sale"
    t = raw.strip().lower()
    if "auction" in t:
        return "auction"
    if "new" in t or "new_home" in t:
        return "new_home"
    if "site" in t or "land" in t:
        return "site"
    return "sale"


def extract_bedrooms(prop: NormalizedProperty) -> int | None:
    """
    Extract bedrooms from the property data, checking multiple fields.
    """
    if prop.bedrooms is not None:
        return prop.bedrooms

    # Try to extract from title or description
    for text in [prop.title, prop.description or ""]:
        match = re.search(r"(\d+)\s*(?:bed(?:room)?s?|br)\b", text, re.IGNORECASE)
        if match:
            return int(match.group(1))

    return None


def extract_bathrooms(prop: NormalizedProperty) -> int | None:
    """Extract bathrooms from the property data."""
    if prop.bathrooms is not None:
        return prop.bathrooms

    for text in [prop.title, prop.description or ""]:
        match = re.search(r"(\d+)\s*(?:bath(?:room)?s?)\b", text, re.IGNORECASE)
        if match:
            return int(match.group(1))

    return None


def extract_floor_area(prop: NormalizedProperty) -> float | None:
    """Extract floor area in sq meters from the property data."""
    if prop.floor_area_sqm is not None:
        return prop.floor_area_sqm

    for text in [prop.description or "", prop.title]:
        # sq m / m2 / m²
        match = re.search(r"([\d,.]+)\s*(?:sq\.?\s*m|m²|m2)", text, re.IGNORECASE)
        if match:
            try:
                return float(match.group(1).replace(",", ""))
            except ValueError:
                continue
        # sq ft → convert to sq m
        match = re.search(r"([\d,.]+)\s*(?:sq\.?\s*ft|ft²|ft2)", text, re.IGNORECASE)
        if match:
            try:
                sqft = float(match.group(1).replace(",", ""))
                return round(sqft * 0.092903, 1)
            except ValueError:
                continue

    return None


class PropertyNormalizer:
    """
    Takes raw NormalizedProperty objects from adapters and produces
    fully normalized records suitable for database insertion.
    """

    def normalize(self, prop: NormalizedProperty) -> dict[str, Any]:
        """
        Normalize a property from adapter output to a record dict
        suitable for PropertyRepository.create().

        Returns a dict with all fields populated, including content_hash
        and address_hash for dedup.
        """
        # Address normalization
        address = normalize_address(prop.address)
        county = prop.county or extract_county(address)
        eircode = prop.eircode or extract_eircode(address + " " + (prop.description or ""))

        # Price
        price = prop.price
        if price is None and prop.price_text:
            price = parse_price(prop.price_text)

        # Features
        bedrooms = extract_bedrooms(prop)
        bathrooms = extract_bathrooms(prop)
        floor_area = extract_floor_area(prop)
        ber = prop.ber_rating or normalize_ber(prop.raw_data.get("ber_rating"))
        property_type = normalize_property_type(prop.property_type)
        sale_type = normalize_sale_type(prop.sale_type)

        # Content hash for deduplication (same listing from same source)
        c_hash = content_hash(
            address=address,
            price=price,
            bedrooms=bedrooms,
            source=prop.url,
        )

        # Fuzzy address hash for cross-source matching
        a_hash = fuzzy_address_hash(address)

        record = {
            "title": prop.title.strip() if prop.title else "",
            "description": (prop.description or "").strip() or None,
            "url": prop.url.strip(),
            "content_hash": c_hash,
            "address": address,
            "address_line1": prop.address_line1,
            "address_line2": prop.address_line2,
            "town": prop.town,
            "county": county,
            "eircode": eircode,
            "price": price,
            "property_type": property_type,
            "sale_type": sale_type,
            "bedrooms": bedrooms,
            "bathrooms": bathrooms,
            "floor_area_sqm": floor_area,
            "ber_rating": ber,
            "ber_number": prop.ber_number,
            "images": prop.images,
            "features": prop.features,
            "raw_data": prop.raw_data,
            "latitude": prop.latitude,
            "longitude": prop.longitude,
        }

        logger.debug(
            "property_normalized",
            url=prop.url,
            county=county,
            price=price,
            content_hash=c_hash[:16],
        )

        return record
