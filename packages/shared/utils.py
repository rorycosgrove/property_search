"""
Shared utility functions used across the application.

Hashing, date parsing, currency formatting, Irish data constants, etc.
"""

from __future__ import annotations

import hashlib
import re
import uuid
from datetime import UTC, datetime

from dateutil import parser as dateutil_parser

# ── Irish Counties ────────────────────────────────────────────────────────────

REPUBLIC_COUNTIES = [
    "Carlow", "Cavan", "Clare", "Cork", "Donegal", "Dublin",
    "Galway", "Kerry", "Kildare", "Kilkenny", "Laois", "Leitrim",
    "Limerick", "Longford", "Louth", "Mayo", "Meath", "Monaghan",
    "Offaly", "Roscommon", "Sligo", "Tipperary", "Waterford",
    "Westmeath", "Wexford", "Wicklow",
]

NI_COUNTIES = [
    "Antrim", "Armagh", "Derry", "Down", "Fermanagh", "Tyrone",
]

ALL_COUNTIES = REPUBLIC_COUNTIES + NI_COUNTIES

# Map of common aliases/abbreviations used in Irish property listings
COUNTY_ALIASES: dict[str, str] = {
    "co. dublin": "Dublin",
    "co dublin": "Dublin",
    "co. cork": "Cork",
    "co cork": "Cork",
    "co. galway": "Galway",
    "co galway": "Galway",
    "co. kerry": "Kerry",
    "co kerry": "Kerry",
    "co. mayo": "Mayo",
    "co. meath": "Meath",
    "co. kildare": "Kildare",
    "co. wicklow": "Wicklow",
    "co. wexford": "Wexford",
    "co. waterford": "Waterford",
    "co. kilkenny": "Kilkenny",
    "co. tipperary": "Tipperary",
    "co. limerick": "Limerick",
    "co. clare": "Clare",
    "co. louth": "Louth",
    "co. laois": "Laois",
    "co. offaly": "Offaly",
    "co. westmeath": "Westmeath",
    "co. longford": "Longford",
    "co. roscommon": "Roscommon",
    "co. sligo": "Sligo",
    "co. leitrim": "Leitrim",
    "co. donegal": "Donegal",
    "co. cavan": "Cavan",
    "co. monaghan": "Monaghan",
    "co. carlow": "Carlow",
    "co. fermanagh": "Fermanagh",
    "co. tyrone": "Tyrone",
    "co. armagh": "Armagh",
    "co. antrim": "Antrim",
    "co. down": "Down",
    "co. derry": "Derry",
    "co. londonderry": "Derry",
    "londonderry": "Derry",
    "derry / londonderry": "Derry",
}


# ── Hashing ───────────────────────────────────────────────────────────────────

def content_hash(address: str, price: float | None, bedrooms: int | None, source: str) -> str:
    """
    Generate a SHA-256 content hash for deduplication.

    Uses normalized address + price + bedrooms + source to detect same listing
    from the same source. For cross-source dedup, use fuzzy_address_hash.
    """
    normalized = normalize_address(address).lower().strip()
    parts = [normalized, str(price or ""), str(bedrooms or ""), source]
    raw = "|".join(parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def fuzzy_address_hash(address: str) -> str:
    """
    Generate a fuzzy hash for cross-source address matching.

    Strips common noise words, normalizes spacing, lowercases.
    Two listings from different sources for the same property
    should produce the same fuzzy hash.
    """
    addr = normalize_address(address).lower()
    # Remove common noise
    for word in ["apartment", "apt", "flat", "unit", "no.", "no"]:
        addr = addr.replace(word, "")
    # Remove all non-alphanumeric except spaces
    addr = re.sub(r"[^a-z0-9\s]", "", addr)
    # Collapse whitespace
    addr = re.sub(r"\s+", " ", addr).strip()
    return hashlib.sha256(addr.encode("utf-8")).hexdigest()[:16]


def canonical_property_id(
    address: str | None,
    county: str | None = None,
    eircode: str | None = None,
) -> str | None:
    """Generate a deterministic canonical property identity.

    Prefer Eircode when available. Otherwise fall back to normalized address + county.
    Returns a UUIDv5 string or None when insufficient identity data is present.
    """
    normalized_eircode = (eircode or "").upper().replace(" ", "").strip()
    if normalized_eircode:
        return str(uuid.uuid5(uuid.NAMESPACE_URL, f"property:eircode:{normalized_eircode}"))

    normalized_address = normalize_address(address or "").lower().strip()
    normalized_county = (county or extract_county(normalized_address) or "").strip().lower()
    if not normalized_address:
        return None

    return str(
        uuid.uuid5(
            uuid.NAMESPACE_URL,
            f"property:address:{normalized_address}|county:{normalized_county}",
        )
    )


# ── Address Parsing ───────────────────────────────────────────────────────────

def normalize_address(address: str) -> str:
    """Normalize address string: trim, collapse whitespace, fix encoding."""
    if not address:
        return ""
    addr = address.strip()
    addr = re.sub(r"\s+", " ", addr)
    # Fix common encoding issues
    addr = addr.replace("\u00a0", " ")  # non-breaking space
    addr = addr.replace("â€™", "'")
    return addr


def extract_county(address: str) -> str | None:
    """
    Extract county name from an Irish address string.

    Tries known county names and aliases. Returns the standardized county name.
    """
    if not address:
        return None

    addr_lower = address.lower().strip()

    # First check aliases (more specific, e.g. "Co. Dublin")
    for alias, county in COUNTY_ALIASES.items():
        if alias in addr_lower:
            return county

    # Then check bare county names (from end of string backwards — county is usually last)
    for county in ALL_COUNTIES:
        if county.lower() in addr_lower:
            return county

    return None


def extract_eircode(text: str) -> str | None:
    """
    Extract an Eircode from text.

    Eircode format: A65 F4E2 (routing key + unique identifier).
    Routing key: letter + 2 digits (or letters). Unique ID: 4 alphanumeric.
    """
    if not text:
        return None
    match = re.search(r"\b([A-Z]\d{2})\s?([A-Z0-9]{4})\b", text.upper())
    if match:
        return f"{match.group(1)} {match.group(2)}"
    return None


# ── Price Parsing ─────────────────────────────────────────────────────────────

def parse_price(price_text: str) -> float | None:
    """
    Parse Irish property price text into a numeric value (EUR).

    Handles: €350,000 | €350000 | 350,000 | EUR 350k | Price on Application
    """
    if not price_text:
        return None

    text = price_text.strip().upper()

    # Skip non-numeric indicators
    if any(kw in text for kw in ["POA", "PRICE ON APPLICATION", "AMV", "GUIDE"]):
        # Try to extract number anyway (AMV: €350,000)
        pass

    # Remove currency symbols and text
    text = re.sub(r"[€£$]", "", text)
    text = re.sub(r"\b(EUR|GBP|EURO)\b", "", text)
    text = re.sub(r"\b(FROM|TO|ASKING|OFFERS?\s*(OVER|AROUND|IN\s*EXCESS))\b", "", text)
    text = text.strip()

    if not text:
        return None

    # Handle "350k" or "1.2m" shorthand
    match_k = re.search(r"([\d,.]+)\s*k\b", text, re.IGNORECASE)
    if match_k:
        try:
            return float(match_k.group(1).replace(",", "")) * 1_000
        except ValueError:
            pass

    match_m = re.search(r"([\d,.]+)\s*m\b", text, re.IGNORECASE)
    if match_m:
        try:
            return float(match_m.group(1).replace(",", "")) * 1_000_000
        except ValueError:
            pass

    # Standard numeric extraction
    match_num = re.search(r"[\d,]+(?:\.\d+)?", text)
    if match_num:
        try:
            return float(match_num.group(0).replace(",", ""))
        except ValueError:
            pass

    return None


# ── Date Parsing ──────────────────────────────────────────────────────────────

def parse_date(date_str: str | None) -> datetime | None:
    """Parse a date string to datetime, timezone-aware (UTC). Returns None on failure."""
    if not date_str:
        return None
    try:
        dt = dateutil_parser.parse(date_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        return dt
    except (ValueError, TypeError):
        return None


def utc_now() -> datetime:
    """Current UTC datetime, timezone-aware."""
    return datetime.now(UTC)


# ── Currency Formatting ──────────────────────────────────────────────────────

def format_eur(amount: float | None) -> str:
    """Format a number as EUR currency string. E.g. 350000 → '€350,000'."""
    if amount is None:
        return "N/A"
    if amount >= 1_000_000:
        return f"€{amount:,.0f}"
    return f"€{amount:,.0f}"


# ── BER Rating ────────────────────────────────────────────────────────────────

BER_RATINGS_ORDERED = [
    "A1", "A2", "A3", "B1", "B2", "B3", "C1", "C2", "C3",
    "D1", "D2", "E1", "E2", "F", "G", "Exempt",
]


def normalize_ber(ber_text: str | None) -> str | None:
    """Normalize a BER rating string to standard format (e.g. 'B2', 'Exempt')."""
    if not ber_text:
        return None
    text = ber_text.strip().upper()

    if "EXEMPT" in text:
        return "Exempt"

    # Match pattern like A1, B2, C3, D1, E2, F, G
    match = re.search(r"\b([A-G])(\d)?\b", text)
    if match:
        letter = match.group(1)
        number = match.group(2) or ""
        rating = f"{letter}{number}"
        if rating in BER_RATINGS_ORDERED:
            return rating
        # Bare letter (F, G)
        if letter in ("F", "G"):
            return letter

    return None
