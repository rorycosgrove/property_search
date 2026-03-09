"""Automatic source discovery helpers.

Keeps candidate source definitions in one place so API and worker tasks
can use the same discovery logic.
"""

from __future__ import annotations

import json
import os
from urllib.parse import urlsplit, urlunsplit
from typing import Any

DEFAULT_DISCOVERY_CANDIDATES: list[dict[str, Any]] = [
    {
        "name": "Daft.ie - National (Auto)",
        "url": "https://www.daft.ie/property-for-sale/ireland",
        "adapter_type": "scraper",
        "adapter_name": "daft",
        "config": {"search_area": "ireland", "max_pages": 5},
        "poll_interval_seconds": 21600,
        "tags": ["auto_discovered", "national"],
    },
    {
        "name": "MyHome.ie - National (Auto)",
        "url": "https://www.myhome.ie/residential/ireland/property-for-sale",
        "adapter_type": "scraper",
        "adapter_name": "myhome",
        "config": {"max_pages": 5},
        "poll_interval_seconds": 21600,
        "tags": ["auto_discovered", "national"],
    },
    {
        "name": "PropertyPal - ROI (Auto)",
        "url": "https://www.propertypal.com/property-for-sale/republic-of-ireland",
        "adapter_type": "scraper",
        "adapter_name": "propertypal",
        "config": {"region": "republic-of-ireland", "max_pages": 3},
        "poll_interval_seconds": 43200,
        "tags": ["auto_discovered", "roi"],
    },
]


def _validate_candidate(item: dict[str, Any]) -> bool:
    required = {"name", "url", "adapter_type", "adapter_name"}
    return required.issubset(item.keys())


def canonicalize_source_url(url: str) -> str:
    """Normalize source URLs for duplicate-safe comparisons."""
    value = (url or "").strip()
    if not value:
        return ""

    parts = urlsplit(value)
    scheme = (parts.scheme or "https").lower()
    netloc = parts.netloc.lower()
    path = parts.path.rstrip("/") or "/"
    # Ignore query/fragment for source identity, as feeds often vary params.
    return urlunsplit((scheme, netloc, path, "", ""))


def load_discovery_candidates() -> list[dict[str, Any]]:
    """Load discovery candidates from defaults + optional env JSON override.

    `AUTO_DISCOVERY_SOURCES_JSON` may contain a JSON array of source dicts.
    Invalid rows are ignored.
    """
    candidates = [dict(c) for c in DEFAULT_DISCOVERY_CANDIDATES]
    raw = os.environ.get("AUTO_DISCOVERY_SOURCES_JSON", "").strip()
    if not raw:
        return candidates

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return candidates

    if not isinstance(parsed, list):
        return candidates

    for item in parsed:
        if isinstance(item, dict) and _validate_candidate(item):
            candidates.append(item)

    # Deduplicate candidates by canonical URL while preserving order.
    deduped: list[dict[str, Any]] = []
    seen_urls: set[str] = set()
    for candidate in candidates:
        key = canonicalize_source_url(str(candidate.get("url") or ""))
        if not key or key in seen_urls:
            continue
        seen_urls.add(key)
        deduped.append(candidate)

    return deduped
