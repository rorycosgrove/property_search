"""Balanced property source crawler.

Discovers new property listing sources by:
1. Fetching a curated list of seed directories and portals.
2. Following links one level deep within each seed domain.
3. Extracting candidate source URLs from page content (RSS feeds, known portals).
4. Returning raw candidate dicts that can be scored by `confidence.py`.

Design constraints
------------------
- Never follows links outside the seed domain (no open crawl).
- Maximum 1 hop from each seed URL (balanced mode).
- Respects a per-host request cap to avoid hammering servers.
- Adds a realistic User-Agent and ~1 s delay between host requests.
- Does NOT write to the database — it only returns candidate dicts.
"""

from __future__ import annotations

import logging
import re
import time
from typing import Any
from urllib.parse import urljoin, urlsplit, urlunsplit
from urllib.robotparser import RobotFileParser

logger = logging.getLogger(__name__)

# ── Seed catalogue ─────────────────────────────────────────────────────────────
# Each entry is a URL to fetch.  We look for RSS feeds, known portal patterns,
# and on-page links to property-listing sub-sections.

PROPERTY_SEED_URLS: list[str] = [
    # ── Major Irish portals ───────────────────────────────────────────────────
    "https://www.daft.ie/sitemap.xml",
    "https://www.myhome.ie/sitemap.xml",
    "https://www.propertypal.com/sitemap.xml",
    "https://www.property.ie/property-for-sale/ireland/",
    "https://www.property.ie/sitemap.xml",
    # ── Estate agent federation directories ──────────────────────────────────
    "https://www.ipav.ie/find-an-agent",            # IPAV member agents
    "https://www.psra.ie/agents",                   # PSRA licence registry
    # ── REA / chain portals ───────────────────────────────────────────────────
    "https://www.rea.ie/property-for-sale/",
    "https://www.sherry-fitzgerald.ie/properties/for-sale/",
    "https://www.dng.ie/buy/",
    "https://www.savills.ie/properties/",
    "https://www.lisney.com/properties/for-sale/",
    "https://www.housesinireland.com/",
    "https://www.allmoves.ie/property-for-sale",
    "https://bidx1.com/en/auctions",
    # ── Northern Ireland portals ──────────────────────────────────────────────
    "https://www.propertynews.com/",
    "https://www.propertypalace.com/",
    # ── RSS / feed aggregators ────────────────────────────────────────────────
    "https://www.daft.ie/rss/property-for-sale",
    "https://www.myhome.ie/rss/residential/ireland/property-for-sale",
    # ── Government / statutory ───────────────────────────────────────────────
    "https://www.propertypriceregister.ie/",
    # ── Auction houses ────────────────────────────────────────────────────────
    "https://www.allsop.ie/residential/current-sales/",
    "https://www.rohrsons.ie/",
    # ── New-homes portals ─────────────────────────────────────────────────────
    "https://www.newhomes.ie/",
    "https://www.homesales.ie/",
    "https://www.propsearch.ie/",
    # ── County-specific pages (already in registry but useful for crawl) ──────
    "https://www.daft.ie/property-for-sale/cork",
    "https://www.daft.ie/property-for-sale/galway",
    "https://www.daft.ie/property-for-sale/limerick",
    "https://www.daft.ie/property-for-sale/waterford",
    "https://www.daft.ie/property-for-sale/kilkenny",
    "https://www.daft.ie/property-for-sale/wexford",
    "https://www.daft.ie/property-for-sale/kerry",
    "https://www.daft.ie/property-for-sale/mayo",
    "https://www.daft.ie/property-for-sale/donegal",
    "https://www.myhome.ie/residential/cork/property-for-sale",
    "https://www.myhome.ie/residential/galway/property-for-sale",
    "https://www.myhome.ie/residential/limerick/property-for-sale",
    "https://www.myhome.ie/residential/waterford/property-for-sale",
    "https://www.myhome.ie/residential/kilkenny/property-for-sale",
    "https://www.propertypal.com/property-for-sale/belfast",
    "https://www.propertypal.com/property-for-sale/derry",
]

# Static candidates derived from local knowledge (no HTTP needed).
# These are the "always include" candidates beyond the 6 currently hardcoded.
STATIC_EXTENDED_CANDIDATES: list[dict[str, Any]] = [
    # ── Regional daft ──────────────────────────────────────────────────────────
    {
        "name": "Daft.ie - Cork (Auto)",
        "url": "https://www.daft.ie/property-for-sale/cork",
        "adapter_type": "scraper",
        "adapter_name": "daft",
        "config": {"areas": ["cork"], "max_pages": 4},
        "poll_interval_seconds": 21600,
        "tags": ["auto_discovered", "cork"],
    },
    {
        "name": "Daft.ie - Galway (Auto)",
        "url": "https://www.daft.ie/property-for-sale/galway",
        "adapter_type": "scraper",
        "adapter_name": "daft",
        "config": {"areas": ["galway"], "max_pages": 4},
        "poll_interval_seconds": 21600,
        "tags": ["auto_discovered", "galway"],
    },
    {
        "name": "Daft.ie - Limerick (Auto)",
        "url": "https://www.daft.ie/property-for-sale/limerick",
        "adapter_type": "scraper",
        "adapter_name": "daft",
        "config": {"areas": ["limerick"], "max_pages": 3},
        "poll_interval_seconds": 21600,
        "tags": ["auto_discovered", "limerick"],
    },
    {
        "name": "Daft.ie - Waterford (Auto)",
        "url": "https://www.daft.ie/property-for-sale/waterford",
        "adapter_type": "scraper",
        "adapter_name": "daft",
        "config": {"areas": ["waterford"], "max_pages": 3},
        "poll_interval_seconds": 21600,
        "tags": ["auto_discovered", "waterford"],
    },
    {
        "name": "Daft.ie - Kerry (Auto)",
        "url": "https://www.daft.ie/property-for-sale/kerry",
        "adapter_type": "scraper",
        "adapter_name": "daft",
        "config": {"areas": ["kerry"], "max_pages": 3},
        "poll_interval_seconds": 21600,
        "tags": ["auto_discovered", "kerry"],
    },
    {
        "name": "Daft.ie - Kildare (Auto)",
        "url": "https://www.daft.ie/property-for-sale/kildare",
        "adapter_type": "scraper",
        "adapter_name": "daft",
        "config": {"areas": ["kildare"], "max_pages": 3},
        "poll_interval_seconds": 21600,
        "tags": ["auto_discovered", "kildare"],
    },
    {
        "name": "Daft.ie - Wicklow (Auto)",
        "url": "https://www.daft.ie/property-for-sale/wicklow",
        "adapter_type": "scraper",
        "adapter_name": "daft",
        "config": {"areas": ["wicklow"], "max_pages": 3},
        "poll_interval_seconds": 21600,
        "tags": ["auto_discovered", "wicklow"],
    },
    {
        "name": "Daft.ie - Meath (Auto)",
        "url": "https://www.daft.ie/property-for-sale/meath",
        "adapter_type": "scraper",
        "adapter_name": "daft",
        "config": {"areas": ["meath"], "max_pages": 3},
        "poll_interval_seconds": 43200,
        "tags": ["auto_discovered", "meath"],
    },
    {
        "name": "Daft.ie - Louth (Auto)",
        "url": "https://www.daft.ie/property-for-sale/louth",
        "adapter_type": "scraper",
        "adapter_name": "daft",
        "config": {"areas": ["louth"], "max_pages": 3},
        "poll_interval_seconds": 43200,
        "tags": ["auto_discovered", "louth"],
    },
    {
        "name": "Daft.ie - Mayo (Auto)",
        "url": "https://www.daft.ie/property-for-sale/mayo",
        "adapter_type": "scraper",
        "adapter_name": "daft",
        "config": {"areas": ["mayo"], "max_pages": 3},
        "poll_interval_seconds": 43200,
        "tags": ["auto_discovered", "mayo"],
    },
    {
        "name": "Daft.ie - Donegal (Auto)",
        "url": "https://www.daft.ie/property-for-sale/donegal",
        "adapter_type": "scraper",
        "adapter_name": "daft",
        "config": {"areas": ["donegal"], "max_pages": 3},
        "poll_interval_seconds": 43200,
        "tags": ["auto_discovered", "donegal"],
    },
    {
        "name": "Daft.ie - Wexford (Auto)",
        "url": "https://www.daft.ie/property-for-sale/wexford",
        "adapter_type": "scraper",
        "adapter_name": "daft",
        "config": {"areas": ["wexford"], "max_pages": 3},
        "poll_interval_seconds": 43200,
        "tags": ["auto_discovered", "wexford"],
    },
    {
        "name": "Daft.ie - Tipperary (Auto)",
        "url": "https://www.daft.ie/property-for-sale/tipperary",
        "adapter_type": "scraper",
        "adapter_name": "daft",
        "config": {"areas": ["tipperary"], "max_pages": 3},
        "poll_interval_seconds": 43200,
        "tags": ["auto_discovered", "tipperary"],
    },
    # ── Regional MyHome ───────────────────────────────────────────────────────
    {
        "name": "MyHome.ie - Cork (Auto)",
        "url": "https://www.myhome.ie/residential/cork/property-for-sale",
        "adapter_type": "scraper",
        "adapter_name": "myhome",
        "config": {"counties": ["cork"], "max_pages": 4},
        "poll_interval_seconds": 21600,
        "tags": ["auto_discovered", "cork"],
    },
    {
        "name": "MyHome.ie - Galway (Auto)",
        "url": "https://www.myhome.ie/residential/galway/property-for-sale",
        "adapter_type": "scraper",
        "adapter_name": "myhome",
        "config": {"counties": ["galway"], "max_pages": 3},
        "poll_interval_seconds": 21600,
        "tags": ["auto_discovered", "galway"],
    },
    {
        "name": "MyHome.ie - Limerick (Auto)",
        "url": "https://www.myhome.ie/residential/limerick/property-for-sale",
        "adapter_type": "scraper",
        "adapter_name": "myhome",
        "config": {"counties": ["limerick"], "max_pages": 3},
        "poll_interval_seconds": 21600,
        "tags": ["auto_discovered", "limerick"],
    },
    {
        "name": "MyHome.ie - Waterford (Auto)",
        "url": "https://www.myhome.ie/residential/waterford/property-for-sale",
        "adapter_type": "scraper",
        "adapter_name": "myhome",
        "config": {"counties": ["waterford"], "max_pages": 3},
        "poll_interval_seconds": 43200,
        "tags": ["auto_discovered", "waterford"],
    },
    {
        "name": "MyHome.ie - Kildare (Auto)",
        "url": "https://www.myhome.ie/residential/kildare/property-for-sale",
        "adapter_type": "scraper",
        "adapter_name": "myhome",
        "config": {"counties": ["kildare"], "max_pages": 3},
        "poll_interval_seconds": 43200,
        "tags": ["auto_discovered", "kildare"],
    },
    {
        "name": "MyHome.ie - Wicklow (Auto)",
        "url": "https://www.myhome.ie/residential/wicklow/property-for-sale",
        "adapter_type": "scraper",
        "adapter_name": "myhome",
        "config": {"counties": ["wicklow"], "max_pages": 3},
        "poll_interval_seconds": 43200,
        "tags": ["auto_discovered", "wicklow"],
    },
    # ── PropertyPal extra regions ─────────────────────────────────────────────
    {
        "name": "PropertyPal - Belfast (Auto)",
        "url": "https://www.propertypal.com/property-for-sale/belfast",
        "adapter_type": "scraper",
        "adapter_name": "propertypal",
        "config": {"region": "belfast", "max_pages": 3},
        "poll_interval_seconds": 21600,
        "tags": ["auto_discovered", "belfast"],
    },
    {
        "name": "PropertyPal - Derry/Londonderry (Auto)",
        "url": "https://www.propertypal.com/property-for-sale/derry-londonderry",
        "adapter_type": "scraper",
        "adapter_name": "propertypal",
        "config": {"region": "derry-londonderry", "max_pages": 3},
        "poll_interval_seconds": 43200,
        "tags": ["auto_discovered", "derry"],
    },
    {
        "name": "PropertyPal - County Antrim (Auto)",
        "url": "https://www.propertypal.com/property-for-sale/county-antrim",
        "adapter_type": "scraper",
        "adapter_name": "propertypal",
        "config": {"region": "county-antrim", "max_pages": 3},
        "poll_interval_seconds": 43200,
        "tags": ["auto_discovered", "antrim"],
    },
    {
        "name": "PropertyPal - County Down (Auto)",
        "url": "https://www.propertypal.com/property-for-sale/county-down",
        "adapter_type": "scraper",
        "adapter_name": "propertypal",
        "config": {"region": "county-down", "max_pages": 3},
        "poll_interval_seconds": 43200,
        "tags": ["auto_discovered", "down"],
    },
    # ── Property.ie ───────────────────────────────────────────────────────────
    {
        "name": "Property.ie - National (RSS)",
        "url": "https://www.property.ie/property-for-sale/ireland/",
        "adapter_type": "rss",
        "adapter_name": "rss",
        "config": {"feed_type": "property_portal"},
        "poll_interval_seconds": 43200,
        "tags": ["auto_discovered", "national", "crawler_discovered"],
    },
    # ── Auction sources ───────────────────────────────────────────────────────
    {
        "name": "BidX1 - Residential Auctions (RSS)",
        "url": "https://bidx1.com/en/auctions",
        "adapter_type": "rss",
        "adapter_name": "rss",
        "config": {"feed_type": "auction"},
        "poll_interval_seconds": 86400,
        "tags": ["auto_discovered", "auction", "crawler_discovered"],
    },
]

# ── Per-adapter county expansion table ────────────────────────────────────────
# Used to programmatically generate per-county candidates for known adapters.
_DAFT_COUNTIES: list[str] = [
    "carlow", "cavan", "clare", "cork", "donegal", "galway", "kerry",
    "kildare", "kilkenny", "laois", "leitrim", "limerick", "longford",
    "louth", "mayo", "meath", "monaghan", "offaly", "roscommon", "sligo",
    "tipperary", "waterford", "westmeath", "wexford", "wicklow",
    "dublin",  # already a default but include for completeness
]

_MYHOME_COUNTIES: list[str] = [
    "carlow", "cavan", "clare", "cork", "donegal", "galway", "kerry",
    "kildare", "kilkenny", "laois", "leitrim", "limerick", "longford",
    "louth", "mayo", "meath", "monaghan", "offaly", "roscommon", "sligo",
    "tipperary", "waterford", "westmeath", "wexford", "wicklow",
    "dublin",
]

_PROPERTYPAL_REGIONS: list[str] = [
    "republic-of-ireland",
    "northern-ireland",
    "belfast",
    "derry-londonderry",
    "county-antrim",
    "county-armagh",
    "county-down",
    "county-fermanagh",
    "county-tyrone",
    "county-donegal",
    "county-galway",
    "county-dublin",
    "county-cork",
]

# ── Regex helpers ──────────────────────────────────────────────────────────────
_RSS_HREF_RE = re.compile(
    r'<link[^>]+type=["\']application/rss\+xml["\'][^>]*href=["\']([^"\']+)["\']',
    re.IGNORECASE,
)
_HREF_RE = re.compile(r'href=["\']([^"\'#?]{10,})["\']', re.IGNORECASE)

_PROPERTY_PATH_KEYWORDS: frozenset[str] = frozenset(
    [
        "property-for-sale",
        "forsale",
        "for-sale",
        "residential",
        "houses-for-sale",
        "homes-for-sale",
        "real-estate",
        "listings",
        "property",
    ]
)

_HTTP_TIMEOUT = 10  # seconds
_HOST_DELAY = 1.2   # seconds between requests to the same host
_MAX_LINKS_PER_SEED = 30  # how many on-page links to follow (balanced mode)
_HOST_REQUEST_CAP = 5     # maximum HTTP requests per unique host per crawl run


class PropertySourceCrawler:
    """Discovers property source URLs from seed portals.

    Usage::

        crawler = PropertySourceCrawler()
        candidates = crawler.discover(include_static=True, follow_links=True)
    """

    def __init__(self) -> None:
        self._host_request_counts: dict[str, int] = {}
        self._last_host_request: dict[str, float] = {}
        self._robots_cache: dict[str, RobotFileParser | None] = {}

    # ── Public API ─────────────────────────────────────────────────────────────

    def discover(
        self,
        *,
        include_static: bool = True,
        follow_links: bool = True,
        extra_seeds: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Run the full discovery pipeline.

        Parameters
        ----------
        include_static:
            Always include `STATIC_EXTENDED_CANDIDATES` — no HTTP needed.
        follow_links:
            Fetch seeds and follow one level of property-relevant links.
        extra_seeds:
            Additional seed URLs to include in the live crawl.

        Returns
        -------
        list[dict]
            Raw candidate dicts (not yet scored or persisted).
        """
        collected: list[dict[str, Any]] = []

        if include_static:
            collected.extend(STATIC_EXTENDED_CANDIDATES)
            logger.info(f"crawler: loaded {len(STATIC_EXTENDED_CANDIDATES)} static extended candidates")

        # Programmatically generated per-county candidates.
        collected.extend(self._generate_county_candidates())

        if follow_links:
            seeds = list(PROPERTY_SEED_URLS) + (extra_seeds or [])
            crawl_results = self._crawl_seeds(seeds)
            collected.extend(crawl_results)
            logger.info(f"crawler: live crawl added {len(crawl_results)} candidates")

        return self._dedup(collected)

    # ── Static generator ───────────────────────────────────────────────────────

    def _generate_county_candidates(self) -> list[dict[str, Any]]:
        """Generate per-county candidates for all known adapters."""
        already_named: set[str] = {c["name"] for c in STATIC_EXTENDED_CANDIDATES}
        results: list[dict[str, Any]] = []

        for county in _DAFT_COUNTIES:
            name = f"Daft.ie - {county.title()} (Auto)"
            if name in already_named:
                continue
            results.append({
                "name": name,
                "url": f"https://www.daft.ie/property-for-sale/{county}",
                "adapter_type": "scraper",
                "adapter_name": "daft",
                "config": {"areas": [county], "max_pages": 3},
                "poll_interval_seconds": 43200,
                "tags": ["auto_discovered", county],
            })

        for county in _MYHOME_COUNTIES:
            name = f"MyHome.ie - {county.title()} (Auto)"
            if name in already_named:
                continue
            results.append({
                "name": name,
                "url": f"https://www.myhome.ie/residential/{county}/property-for-sale",
                "adapter_type": "scraper",
                "adapter_name": "myhome",
                "config": {"counties": [county], "max_pages": 3},
                "poll_interval_seconds": 43200,
                "tags": ["auto_discovered", county],
            })

        for region in _PROPERTYPAL_REGIONS:
            name = f"PropertyPal - {region.replace('-', ' ').title()} (Auto)"
            if name in already_named:
                continue
            results.append({
                "name": name,
                "url": f"https://www.propertypal.com/property-for-sale/{region}",
                "adapter_type": "scraper",
                "adapter_name": "propertypal",
                "config": {"region": region, "max_pages": 3},
                "poll_interval_seconds": 43200,
                "tags": ["auto_discovered"],
            })

        return results

    # ── Live crawl ─────────────────────────────────────────────────────────────

    def _crawl_seeds(self, seeds: list[str]) -> list[dict[str, Any]]:
        """Fetch seed URLs and extract property-listing candidates."""
        results: list[dict[str, Any]] = []

        for seed_url in seeds:
            host = _host(seed_url)
            if not host:
                continue
            if not self._may_fetch(host, seed_url):
                logger.debug(f"crawler: skipping {seed_url} (robots/cap)")
                continue

            html = self._fetch(seed_url)
            if not html:
                continue

            # Extract and follow property-relevant links one level deep.
            links = self._extract_property_links(html, seed_url)
            for link in links[:_MAX_LINKS_PER_SEED]:
                link_host = _host(link)
                if not link_host or link_host != host:
                    # Only follow within the same domain.
                    continue
                if not self._may_fetch(link_host, link):
                    continue
                link_html = self._fetch(link)
                if link_html:
                    candidate = self._html_to_candidate(link, link_html)
                    if candidate:
                        results.append(candidate)

            # Also try to extract RSS feeds from the seed page itself.
            rss_results = self._extract_rss_candidates(html, seed_url)
            results.extend(rss_results)

        return results

    def _fetch(self, url: str) -> str | None:
        """Fetch a URL with a polite delay and return the response text."""
        try:
            import urllib.request
            host = _host(url)
            if host:
                self._polite_delay(host)

            req = urllib.request.Request(
                url,
                headers={"User-Agent": _USER_AGENT},
            )
            with urllib.request.urlopen(req, timeout=_HTTP_TIMEOUT) as resp:
                ct = resp.headers.get_content_type() or ""
                if not any(t in ct for t in ("html", "xml", "rss", "text")):
                    return None
                raw = resp.read(512 * 1024)  # cap at 512 KB
                return raw.decode("utf-8", errors="replace")

        except Exception as exc:
            logger.debug(f"crawler: fetch failed for {url}: {exc}")
            return None
        finally:
            host = _host(url)
            if host:
                self._host_request_counts[host] = self._host_request_counts.get(host, 0) + 1

    def _polite_delay(self, host: str) -> None:
        """Enforce a minimum inter-request delay per host."""
        last = self._last_host_request.get(host, 0.0)
        elapsed = time.monotonic() - last
        if elapsed < _HOST_DELAY:
            time.sleep(_HOST_DELAY - elapsed)
        self._last_host_request[host] = time.monotonic()

    def _may_fetch(self, host: str, url: str) -> bool:
        """Check robots.txt and per-host cap."""
        if self._host_request_counts.get(host, 0) >= _HOST_REQUEST_CAP:
            return False
        rp = self._get_robots(host)
        if rp is not None and not rp.can_fetch(_USER_AGENT, url):
            return False
        return True

    def _get_robots(self, host: str) -> RobotFileParser | None:
        if host in self._robots_cache:
            return self._robots_cache[host]

        robots_url = f"https://{host}/robots.txt"
        rp = RobotFileParser()
        rp.set_url(robots_url)
        try:
            rp.read()
        except Exception:
            rp = None
        self._robots_cache[host] = rp
        return rp

    def _extract_property_links(self, html: str, base_url: str) -> list[str]:
        """Return absolute links that look like property listing pages."""
        links: list[str] = []
        for m in _HREF_RE.finditer(html):
            href = m.group(1).strip()
            if not href or href.startswith("javascript:") or href.startswith("mailto:"):
                continue
            abs_url = _absolutize(href, base_url)
            if not abs_url:
                continue
            path = urlsplit(abs_url).path.lower()
            if any(kw in path for kw in _PROPERTY_PATH_KEYWORDS):
                links.append(abs_url)
        return list(dict.fromkeys(links))  # deduplicate while preserving order

    def _extract_rss_candidates(self, html: str, base_url: str) -> list[dict[str, Any]]:
        """Extract RSS feed links from an HTML page."""
        candidates: list[dict[str, Any]] = []
        host = _host(base_url)
        for m in _RSS_HREF_RE.finditer(html):
            href = m.group(1).strip()
            abs_url = _absolutize(href, base_url)
            if not abs_url:
                continue
            adapter_name = _adapter_name_for_host(host or "")
            candidates.append({
                "name": f"RSS Feed – {host} (Auto)",
                "url": abs_url,
                "adapter_type": "rss",
                "adapter_name": adapter_name,
                "config": {"feed_type": "rss_auto"},
                "poll_interval_seconds": 43200,
                "tags": ["auto_discovered", "rss", "crawler_discovered"],
            })
        return candidates

    def _html_to_candidate(self, url: str, html: str) -> dict[str, Any] | None:
        """Convert a fetched property-listing page into a source candidate."""
        host = _host(url)
        if not host:
            return None

        adapter_name = _adapter_name_for_host(host)
        adapter_type = "scraper" if adapter_name in {"daft", "myhome", "propertypal"} else "rss"

        # Extract a title from the HTML <title> tag.
        title_match = re.search(r"<title[^>]*>([^<]{3,100})</title>", html, re.IGNORECASE)
        title = title_match.group(1).strip() if title_match else f"Discovered – {host}"
        title = re.sub(r"\s+", " ", title)

        # Derive a region/area tag from the URL path.
        parts = urlsplit(url)
        path_parts = [p for p in parts.path.strip("/").split("/") if p]
        area_tag = path_parts[-1] if path_parts else host

        return {
            "name": f"{title} (Auto)",
            "url": url,
            "adapter_type": adapter_type,
            "adapter_name": adapter_name,
            "config": {"max_pages": 3},
            "poll_interval_seconds": 43200,
            "tags": ["auto_discovered", "crawler_discovered", area_tag[:40]],
        }

    # ── Deduplication ──────────────────────────────────────────────────────────

    def _dedup(self, candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
        from packages.sources.discovery import canonicalize_source_url
        seen: set[str] = set()
        result: list[dict[str, Any]] = []
        for c in candidates:
            key = canonicalize_source_url(str(c.get("url") or ""))
            if not key or key in seen:
                continue
            seen.add(key)
            result.append(c)
        return result


# ── Module-level helpers ───────────────────────────────────────────────────────

_USER_AGENT = (
    "Mozilla/5.0 (compatible; PropertySearchBot/1.0; "
    "+https://github.com/your-org/property_search)"
)

_HOST_TO_ADAPTER: dict[str, str] = {
    "daft.ie": "daft",
    "myhome.ie": "myhome",
    "propertypal.com": "propertypal",
    "property.ie": "rss",
    "propertypriceregister.ie": "ppr",
    "bidx1.com": "rss",
    "allsop.ie": "rss",
    "sherry-fitzgerald.ie": "rss",
    "lisney.com": "rss",
    "dng.ie": "rss",
    "savills.ie": "rss",
    "rea.ie": "rss",
    "housesinireland.com": "rss",
    "propertynews.com": "rss",
    "newhomes.ie": "rss",
    "homesales.ie": "rss",
    "propsearch.ie": "rss",
}


def _adapter_name_for_host(host: str) -> str:
    """Return the adapter name for a host, defaulting to 'rss'."""
    host_clean = host.lower().lstrip("www.")
    for key, adapter in _HOST_TO_ADAPTER.items():
        if host_clean == key or host_clean.endswith("." + key):
            return adapter
    return "rss"


def _host(url: str) -> str:
    """Extract the host from a URL, stripping www. prefix."""
    try:
        netloc = urlsplit(url).netloc.lower()
        netloc = netloc.split(":")[0]
        if netloc.startswith("www."):
            netloc = netloc[4:]
        return netloc
    except Exception:
        return ""


def _absolutize(href: str, base_url: str) -> str | None:
    """Convert a potentially relative href to an absolute URL."""
    try:
        abs_url = urljoin(base_url, href)
        parts = urlsplit(abs_url)
        if parts.scheme not in ("http", "https"):
            return None
        # Normalise: strip fragment and trailing slash.
        path = parts.path.rstrip("/") or "/"
        return urlunsplit((parts.scheme, parts.netloc, path, "", ""))
    except Exception:
        return None
