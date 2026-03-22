"""Automatic source discovery helpers.

Keeps candidate source definitions in one place so API and worker tasks
can use the same discovery logic.

New in v2: `load_all_discovery_candidates()` integrates the property crawler
and confidence scoring so callers get a scored, deduplicated candidate list
without needing to import those modules directly.
"""

from __future__ import annotations

import json
import logging
import os
import re
from urllib.parse import urlsplit, urlunsplit
from typing import Any

logger = logging.getLogger(__name__)

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
    {
        "name": "Daft.ie - Dublin (Auto)",
        "url": "https://www.daft.ie/property-for-sale/dublin",
        "adapter_type": "scraper",
        "adapter_name": "daft",
        "config": {"areas": ["dublin"], "max_pages": 4},
        "poll_interval_seconds": 21600,
        "tags": ["auto_discovered", "dublin"],
    },
    {
        "name": "MyHome.ie - Dublin (Auto)",
        "url": "https://www.myhome.ie/residential/dublin/property-for-sale",
        "adapter_type": "scraper",
        "adapter_name": "myhome",
        "config": {"counties": ["dublin"], "max_pages": 4},
        "poll_interval_seconds": 21600,
        "tags": ["auto_discovered", "dublin"],
    },
    {
        "name": "PropertyPal - Northern Ireland (Auto)",
        "url": "https://www.propertypal.com/property-for-sale/northern-ireland",
        "adapter_type": "scraper",
        "adapter_name": "propertypal",
        "config": {"region": "northern-ireland", "max_pages": 3},
        "poll_interval_seconds": 43200,
        "tags": ["auto_discovered", "northern_ireland"],
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


def source_identity_key(adapter_name: str | None, url: str) -> str:
    """Return a semantic identity key for duplicate-safe source matching.

    This collapses known URL variants that represent the same coverage slice,
    e.g. MyHome national pages with/without `/property-for-sale` suffix.
    """
    canonical_url = canonicalize_source_url(url)
    if not canonical_url:
        return ""

    adapter = (adapter_name or "").strip().lower()
    parts = urlsplit(canonical_url)
    path = (parts.path or "").strip("/").lower()

    if adapter == "daft":
        match = re.search(r"property-for-sale/([^/]+)", path)
        if match:
            return f"daft:{match.group(1)}"

    if adapter == "myhome":
        match = re.search(r"residential/([^/]+)", path)
        if match:
            # Covers both /residential/{area} and /residential/{area}/property-for-sale
            return f"myhome:{match.group(1)}"

    if adapter == "propertypal":
        match = re.search(r"property-for-sale/([^/]+)", path)
        if match:
            return f"propertypal:{match.group(1)}"

    return f"{adapter}:{canonical_url}"


def load_discovery_candidates() -> list[dict[str, Any]]:
    """Load discovery candidates from defaults + optional env JSON override.

    `AUTO_DISCOVERY_SOURCES_JSON` may contain a JSON array of source dicts.
    Invalid rows are ignored.
    """
    candidates = [dict(c) for c in DEFAULT_DISCOVERY_CANDIDATES]
    try:
        from packages.sources.crawler import STATIC_EXTENDED_CANDIDATES

        candidates.extend(dict(c) for c in STATIC_EXTENDED_CANDIDATES)
    except Exception:
        logger.warning("discovery.load_candidates: static extended candidates unavailable")

    raw = os.environ.get("AUTO_DISCOVERY_SOURCES_JSON", "").strip()
    if not raw:
        return _dedupe_candidates(candidates)

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return _dedupe_candidates(candidates)

    if not isinstance(parsed, list):
        return _dedupe_candidates(candidates)

    for item in parsed:
        if isinstance(item, dict) and _validate_candidate(item):
            candidates.append(item)

    return _dedupe_candidates(candidates)


def _dedupe_candidates(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Deduplicate candidates by semantic source identity while preserving order."""
    deduped: list[dict[str, Any]] = []
    seen_keys: set[str] = set()
    for candidate in candidates:
        key = source_identity_key(
            str(candidate.get("adapter_name") or ""),
            str(candidate.get("url") or ""),
        )
        if not key or key in seen_keys:
            continue
        seen_keys.add(key)
        deduped.append(candidate)

    return deduped


def load_all_discovery_candidates(
    *,
    use_crawler: bool = True,
    follow_links: bool = False,
    extra_seeds: list[str] | None = None,
    reject_below: float | None = None,
) -> list[Any]:
    """Return scored discovery candidates from all sources.

    This is the high-level entry point used by the unified discovery worker
    task.  It combines:

    1. The static default candidates (``DEFAULT_DISCOVERY_CANDIDATES``).
    2. Candidates from ``AUTO_DISCOVERY_SOURCES_JSON`` env override.
    3. All static extended candidates from the property crawler (no HTTP).
    4. Optionally: live-crawled candidates when ``follow_links=True``.

    Returns a list of :class:`~packages.sources.confidence.ScoredCandidate`
    objects sorted by score descending, filtered to >= ``reject_below``
    (defaults to ``PENDING_THRESHOLD`` = 0.40).

    Parameters
    ----------
    use_crawler:
        Include static extended candidates from the crawler module.
    follow_links:
        Perform live HTTP fetching of seed URLs (slower but finds more sources).
    extra_seeds:
        Additional seed URLs to pass to the live crawler.
    reject_below:
        Minimum confidence score; candidates below this are excluded.
    """
    from packages.sources.confidence import PENDING_THRESHOLD, score_candidates

    threshold = reject_below if reject_below is not None else PENDING_THRESHOLD

    # Base: env-configured + hardcoded defaults.
    base_candidates = load_discovery_candidates()

    crawler_candidates: list[dict[str, Any]] = []
    if use_crawler:
        try:
            from packages.sources.crawler import PropertySourceCrawler

            crawler = PropertySourceCrawler()
            crawler_candidates = crawler.discover(
                include_static=True,
                follow_links=follow_links,
                extra_seeds=extra_seeds,
            )
        except Exception as exc:
            logger.warning(
                "discovery.load_all: crawler unavailable, using base candidates only",
                extra={"error": str(exc), "follow_links": follow_links},
            )

    # Merge, dedup by canonical URL.
    all_candidates: list[dict[str, Any]] = []
    seen_urls: set[str] = set()

    for c in base_candidates + crawler_candidates:
        key = canonicalize_source_url(str(c.get("url") or ""))
        if not key or key in seen_urls:
            continue
        seen_urls.add(key)
        all_candidates.append(c)

    logger.info(
        "discovery.load_all: merged candidates",
        extra={"total": len(all_candidates), "follow_links": follow_links},
    )

    return score_candidates(all_candidates, reject_below=threshold)
