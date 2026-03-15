"""Grant program discovery engine.

Discovers Irish and Northern Irish grant programs by:
1. Starting from a curated list of authoritative government/agency seed URLs.
2. Fetching those pages and extracting grant-relevant information using
   keyword/pattern matching on page text and structured data.
3. Returning a list of candidate ``GrantProgram``-compatible dicts that can
   be upserted into the database.

Design constraints
------------------
- Bounded crawl: 1–2 levels deep per seed domain.
- Respects robots.txt and uses a polite request delay.
- All keyword matching is local (no LLM calls here).
- Returns candidates even if the DB is unavailable (pure discovery).
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

GRANT_SEED_URLS: list[str] = [
    # ── Republic of Ireland — government portals ──────────────────────────────
    "https://www.gov.ie/en/collection/housing-grants/",
    "https://www.gov.ie/en/collection/derelict-sites/",
    "https://www.gov.ie/en/service/vacant-property-refurbishment-grant/",
    "https://www.gov.ie/en/service/croí-cónaithe-towns-fund/",
    "https://www.gov.ie/en/collection/urban-regeneration-development-fund/",
    "https://www.gov.ie/en/collection/local-authority-affordable-purchase-scheme/",
    "https://www.gov.ie/en/collection/first-home-scheme/",
    "https://www.gov.ie/en/collection/help-to-buy-htb/",
    # ── SEAI ──────────────────────────────────────────────────────────────────
    "https://www.seai.ie/grants/",
    "https://www.seai.ie/grants/home-energy-grants/",
    "https://www.seai.ie/grants/home-energy-grants/deep-retrofit-grant/",
    # ── LDA ───────────────────────────────────────────────────────────────────
    "https://www.lda.ie/homes/",
    # ── Housing Agency ───────────────────────────────────────────────────────
    "https://www.housingagency.ie/housing-information/vacant-homes/",
    "https://www.housingagency.ie/housing-information/affordable-housing/",
    # ── Local Government Ireland ──────────────────────────────────────────────
    "https://www.lgma.ie/",
    # ── Revenue Commissioners ─────────────────────────────────────────────────
    "https://www.revenue.ie/en/property/help-to-buy-incentive/index.aspx",
    # ── Department of Rural and Community Development ─────────────────────────
    "https://www.gov.ie/en/collection/town-and-village-renewal-scheme/",
    "https://www.gov.ie/en/collection/clár/",
    # ── Pobal ─────────────────────────────────────────────────────────────────
    "https://www.pobal.ie/funding-programmes/",
    # ── Northern Ireland ──────────────────────────────────────────────────────
    "https://www.nihe.gov.uk/housing-help/grants-and-adaptations",
    "https://www.co-ownership.org/",
    "https://www.communities-ni.gov.uk/topics/housing",
    "https://www.communities-ni.gov.uk/topics/urban-regeneration",
    "https://www.investni.com/support-for-business/grants-and-financial-support",
    # ── Citizens Information ──────────────────────────────────────────────────
    "https://www.citizensinformation.ie/en/housing/housing-grants-and-schemes/",
    "https://www.citizensinformation.ie/en/housing/owning-a-home/",
    # ── Money Guide Ireland ───────────────────────────────────────────────────
    "https://www.moneyguideireland.com/government-grants-available-to-homeowners.html",
]

# ── Keyword classifiers ────────────────────────────────────────────────────────

# Page must contain at least one of these to be considered grant-relevant.
_GRANT_TRIGGER_KEYWORDS: frozenset[str] = frozenset([
    "grant", "scheme", "fund", "incentive", "subsidy", "rebate",
    "refurbishment", "renovation", "retrofit", "vacant", "derelict",
    "affordable", "first-time buyer", "help to buy", "shared equity",
    "co-ownership", "energy upgrade", "ber rating",
])

# Keywords that strongly indicate a DERELICT / vacant property grant.
_DERELICT_KEYWORDS: frozenset[str] = frozenset([
    "derelict", "vacant", "abandoned", "empty home", "empty property",
    "croí cónaithe", "croi conaithe", "derelict sites",
    "vacant refurb", "town regeneration", "urban regeneration",
    "unfit dwelling", "unfit property",
])

# Keywords for energy retrofit grants.
_ENERGY_KEYWORDS: frozenset[str] = frozenset([
    "seai", "energy grant", "deep retrofit", "insulation grant",
    "heat pump", "ber", "energy upgrade", "home energy",
])

# Mapping of source domain → country code for generated candidates.
_DOMAIN_COUNTRY: dict[str, str] = {
    "gov.ie": "IE",
    "seai.ie": "IE",
    "lda.ie": "IE",
    "housingagency.ie": "IE",
    "revenue.ie": "IE",
    "pobal.ie": "IE",
    "citizensinformation.ie": "IE",
    "lgma.ie": "IE",
    "firsthomescheme.ie": "IE",
    "nihe.gov.uk": "NI",
    "co-ownership.org": "NI",
    "communities-ni.gov.uk": "NI",
    "investni.com": "NI",
    "gov.uk": "NI",
    "moneyguideireland.com": "IE",
    "thinkproperty.ie": "IE",
}

# ── Patterns ───────────────────────────────────────────────────────────────────
_TITLE_RE = re.compile(r"<title[^>]*>([^<]{3,200})</title>", re.IGNORECASE)
_H1_RE = re.compile(r"<h[12][^>]*>([^<]{3,200})</h[12]>", re.IGNORECASE)
_AMOUNT_RE = re.compile(r"[€£](\d[\d,\.]+)", re.IGNORECASE)
_HREF_RE = re.compile(r'href=["\']([^"\'#?]{10,})["\']', re.IGNORECASE)

_HTTP_TIMEOUT = 12
_HOST_DELAY = 1.5
_HOST_REQUEST_CAP = 4
_MAX_LINKS_PER_SEED = 25

_USER_AGENT = (
    "Mozilla/5.0 (compatible; PropertySearchGrantBot/1.0; "
    "+https://github.com/your-org/property_search)"
)


class GrantSourceCrawler:
    """Discovers grant program sources from Irish/NI government portals."""

    def __init__(self) -> None:
        self._host_request_counts: dict[str, int] = {}
        self._last_host_request: dict[str, float] = {}
        self._robots_cache: dict[str, RobotFileParser | None] = {}

    def discover(
        self,
        extra_seeds: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Run grant portal crawl and return raw candidate dicts.

        Each returned dict is compatible with ``GrantProgram`` model fields.
        """
        candidates: list[dict[str, Any]] = []
        seeds = list(GRANT_SEED_URLS) + (extra_seeds or [])

        for seed_url in seeds:
            host = _host(seed_url)
            if not host or not self._may_fetch(host, seed_url):
                logger.debug(f"grant_crawler: skipping {seed_url}")
                continue

            html = self._fetch(seed_url)
            if not html:
                continue

            page_lower = _strip_html(html).lower()
            if not any(kw in page_lower for kw in _GRANT_TRIGGER_KEYWORDS):
                logger.debug(f"grant_crawler: no grant keywords on {seed_url}")
                continue

            # Extract a candidate from this page.
            candidate = self._page_to_candidate(seed_url, html, page_lower)
            if candidate:
                candidates.append(candidate)

            # One level of link-following for grant-relevant sub-pages.
            links = self._extract_grant_links(html, seed_url, host)
            for link in links[:_MAX_LINKS_PER_SEED]:
                link_host = _host(link)
                if not link_host or not self._may_fetch(link_host, link):
                    continue
                link_html = self._fetch(link)
                if not link_html:
                    continue
                link_lower = _strip_html(link_html).lower()
                if not any(kw in link_lower for kw in _GRANT_TRIGGER_KEYWORDS):
                    continue
                sub_candidate = self._page_to_candidate(link, link_html, link_lower)
                if sub_candidate:
                    candidates.append(sub_candidate)

        # Deduplicate by source_url.
        seen: set[str] = set()
        result: list[dict[str, Any]] = []
        for c in candidates:
            key = (c.get("source_url") or c.get("code") or "").strip().lower()
            if not key or key in seen:
                continue
            seen.add(key)
            result.append(c)

        logger.info(f"grant_crawler: discovered {len(result)} candidates")
        return result

    # ── Page fetching ─────────────────────────────────────────────────────────

    def _fetch(self, url: str) -> str | None:
        try:
            import urllib.request
            host = _host(url)
            if host:
                self._polite_delay(host)
            req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
            with urllib.request.urlopen(req, timeout=_HTTP_TIMEOUT) as resp:
                ct = resp.headers.get_content_type() or ""
                if not any(t in ct for t in ("html", "xml", "text")):
                    return None
                raw = resp.read(256 * 1024)  # cap at 256 KB
                return raw.decode("utf-8", errors="replace")
        except Exception as exc:
            logger.debug(f"grant_crawler: fetch failed for {url}: {exc}")
            return None
        finally:
            host = _host(url)
            if host:
                self._host_request_counts[host] = self._host_request_counts.get(host, 0) + 1

    def _polite_delay(self, host: str) -> None:
        last = self._last_host_request.get(host, 0.0)
        elapsed = time.monotonic() - last
        if elapsed < _HOST_DELAY:
            time.sleep(_HOST_DELAY - elapsed)
        self._last_host_request[host] = time.monotonic()

    def _may_fetch(self, host: str, url: str) -> bool:
        if self._host_request_counts.get(host, 0) >= _HOST_REQUEST_CAP:
            return False
        rp = self._get_robots(host)
        if rp is not None and not rp.can_fetch(_USER_AGENT, url):
            return False
        return True

    def _get_robots(self, host: str) -> RobotFileParser | None:
        if host in self._robots_cache:
            return self._robots_cache[host]
        rp = RobotFileParser()
        rp.set_url(f"https://{host}/robots.txt")
        try:
            rp.read()
        except Exception:
            rp = None
        self._robots_cache[host] = rp
        return rp

    # ── Candidate extraction ──────────────────────────────────────────────────

    def _page_to_candidate(
        self, url: str, html: str, page_lower: str
    ) -> dict[str, Any] | None:
        """Convert a grant-relevant page into a candidate dict."""
        host = _host(url)
        country = _country_for_host(host)

        # Extract title from <title> or first <h1>/<h2>.
        title = ""
        m = _TITLE_RE.search(html)
        if m:
            title = re.sub(r"\s+", " ", m.group(1)).strip()
        if not title:
            m = _H1_RE.search(html)
            if m:
                title = re.sub(r"<[^>]+>", "", m.group(1)).strip()

        if not title or len(title) < 5:
            return None

        # Skip clearly non-grant pages.
        if not any(kw in title.lower() for kw in _GRANT_TRIGGER_KEYWORDS | {"housing", "homes", "property"}):
            return None

        # Determine grant type from keywords.
        grant_tags: list[str] = []
        if any(kw in page_lower for kw in _DERELICT_KEYWORDS):
            grant_tags.append("derelict")
        if any(kw in page_lower for kw in _ENERGY_KEYWORDS):
            grant_tags.append("energy_retrofit")

        # Extract the largest mentioned money amount as a proxy for max_amount.
        max_amount: float | None = None
        amounts: list[float] = []
        for m_amt in _AMOUNT_RE.finditer(page_lower):
            try:
                amounts.append(float(m_amt.group(1).replace(",", "")))
            except ValueError:
                pass
        if amounts:
            max_amount = max(amounts)

        # Derive currency from country.
        currency = "GBP" if country == "NI" else "EUR"

        # Generate a stable code from the URL slug.
        parts = urlsplit(url)
        slug = parts.path.strip("/").replace("/", "-").replace("_", "-")[:60].upper()
        code = f"{country}-DISCOVERED-{slug}" if slug else f"{country}-DISCOVERED-{host.upper()[:20]}"

        # Build the candidate.
        eligibility_rules: dict[str, Any] = {"country": country}
        if "derelict" in grant_tags:
            eligibility_rules["property_condition"] = ["vacant", "derelict"]
        if "energy_retrofit" in grant_tags:
            eligibility_rules["grant_category"] = "energy_retrofit"

        return {
            "code": code,
            "name": title,
            "country": country,
            "authority": _authority_for_host(host),
            "description": f"Discovered via crawler from {url}. Review and update description before enabling.",
            "eligibility_rules": eligibility_rules,
            "benefit_type": "grant",
            "max_amount": max_amount,
            "currency": currency,
            "active": False,  # Discovered grants start inactive — require human review.
            "source_url": url,
            "_discovery_tags": grant_tags,
            "_confidence": "crawler_discovered",
        }

    # ── Link extraction ───────────────────────────────────────────────────────

    def _extract_grant_links(
        self, html: str, base_url: str, base_host: str
    ) -> list[str]:
        """Return same-host links that look grant-related."""
        links: list[str] = []
        for m in _HREF_RE.finditer(html):
            href = m.group(1).strip()
            if not href or href.startswith("javascript:"):
                continue
            abs_url = _absolutize(href, base_url)
            if not abs_url:
                continue
            if _host(abs_url) != base_host:
                continue
            path_lower = urlsplit(abs_url).path.lower()
            if any(kw.replace(" ", "-") in path_lower for kw in _GRANT_TRIGGER_KEYWORDS):
                links.append(abs_url)
        return list(dict.fromkeys(links))


# ── Public API ─────────────────────────────────────────────────────────────────


def discover_grant_programs(
    dry_run: bool = False,
    extra_seeds: list[str] | None = None,
) -> dict[str, Any]:
    """Discover and optionally persist new grant programs.

    Parameters
    ----------
    dry_run:
        When True returns candidates without writing to the database.
    extra_seeds:
        Additional seed URLs to crawl.

    Returns
    -------
    dict with keys: candidates_found, created, existing, dry_run, candidates (in dry-run mode)
    """
    crawler = GrantSourceCrawler()
    candidates = crawler.discover(extra_seeds=extra_seeds)

    result: dict[str, Any] = {
        "candidates_found": len(candidates),
        "created": 0,
        "existing": 0,
        "dry_run": dry_run,
    }

    if dry_run:
        result["candidates"] = candidates
        return result

    from packages.storage.database import get_session
    from packages.storage.repositories import GrantProgramRepository

    with get_session() as db:
        repo = GrantProgramRepository(db)
        existing_codes = {g.code for g in repo.list_programs(active_only=False)}

        for candidate in candidates:
            code = candidate.get("code")
            if not code or code in existing_codes:
                result["existing"] += 1
                continue

            # Strip internal-only fields before persisting.
            grant_data = {
                k: v for k, v in candidate.items()
                if not k.startswith("_") and k in {
                    "code", "name", "country", "authority", "description",
                    "eligibility_rules", "benefit_type", "max_amount",
                    "currency", "active", "source_url",
                }
            }

            try:
                repo.create(**grant_data)
                existing_codes.add(code)
                result["created"] += 1
            except Exception as exc:
                logger.warning(
                    "grant_discovery: failed to persist candidate: %s — %s",
                    code,
                    str(exc),
                )

        db.commit()

    logger.info("grant_discovery_complete", **result)
    return result


# ── Helpers ────────────────────────────────────────────────────────────────────

def _strip_html(html: str) -> str:
    """Remove HTML tags for keyword matching."""
    return re.sub(r"<[^>]+>", " ", html)


def _host(url: str) -> str:
    try:
        netloc = urlsplit(url).netloc.lower()
        netloc = netloc.split(":")[0]
        if netloc.startswith("www."):
            netloc = netloc[4:]
        return netloc
    except Exception:
        return ""


def _country_for_host(host: str) -> str:
    for domain, country in _DOMAIN_COUNTRY.items():
        if host == domain or host.endswith("." + domain):
            return country
    # Default to IE for unknown Irish-sounding domains.
    if host.endswith(".ie"):
        return "IE"
    if host.endswith(".gov.uk") or host.endswith(".org.uk") or host.endswith(".co.uk"):
        return "NI"
    return "IE"


def _authority_for_host(host: str) -> str:
    authority_map: dict[str, str] = {
        "gov.ie": "Government of Ireland",
        "seai.ie": "Sustainable Energy Authority of Ireland",
        "lda.ie": "Land Development Agency",
        "housingagency.ie": "The Housing Agency",
        "revenue.ie": "Revenue Commissioners",
        "pobal.ie": "Pobal",
        "nihe.gov.uk": "Northern Ireland Housing Executive",
        "co-ownership.org": "Co-Ownership Housing",
        "communities-ni.gov.uk": "Department for Communities (NI)",
        "citizensinformation.ie": "Citizens Information Board",
    }
    for domain, auth in authority_map.items():
        if host == domain or host.endswith("." + domain):
            return auth
    return host.title()


def _absolutize(href: str, base_url: str) -> str | None:
    try:
        abs_url = urljoin(base_url, href)
        parts = urlsplit(abs_url)
        if parts.scheme not in ("http", "https"):
            return None
        path = parts.path.rstrip("/") or "/"
        return urlunsplit((parts.scheme, parts.netloc, path, "", ""))
    except Exception:
        return None
