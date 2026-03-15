"""Source candidate confidence scoring.

Assigns a deterministic [0.0, 1.0] confidence score to a discovery candidate
so the activation policy can decide to auto-enable, pend for approval, or
reject it outright without human input on every run.

Activation thresholds
---------------------
  >= 0.70  → auto_enable (high confidence)
  0.40–0.69 → pending_approval (medium confidence)
  < 0.40   → reject (too uncertain to even create the source)

These values are intentionally conservative: it is better to pend for review
than to silently enable a noisy or irrelevant source.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# ── Thresholds ────────────────────────────────────────────────────────────────

AUTO_ENABLE_THRESHOLD = 0.70
PENDING_THRESHOLD = 0.40

# ── Known-good signals ────────────────────────────────────────────────────────

# Adapter names we fully trust (registered, well-tested scrapers).
_KNOWN_ADAPTERS: set[str] = {"daft", "myhome", "propertypal", "ppr", "rss"}

# Domains we consider authoritative for Irish/NI property search.
_TRUSTED_PROPERTY_DOMAINS: frozenset[str] = frozenset(
    [
        "daft.ie",
        "myhome.ie",
        "propertypal.com",
        "property.ie",
        "sherry-fitzgerald.ie",
        "savills.ie",
        "knight-frank.ie",
        "bideford.ie",
        "dng.ie",
        "remax.ie",
        "era.ie",
        "ppsr.ie",
        "propertypriceregister.ie",
        "bidx1.com",
        "lisney.com",
        "housesinireland.com",
        "propertypartner.ie",
        "allmoves.ie",
    ]
)

# Domain keywords that strongly hint a URL is property-related.
_PROPERTY_URL_KEYWORDS: tuple[str, ...] = (
    "property",
    "house",
    "home",
    "real-estate",
    "realestate",
    "estate",
    "residential",
    "for-sale",
    "forsale",
    "listing",
    "rent",
)

# Adapter types that have structured feeds (higher reliability).
_HIGH_RELIABILITY_ADAPTER_TYPES: frozenset[str] = frozenset(["rss", "api", "csv"])


@dataclass
class ScoredCandidate:
    """A discovery candidate with its computed confidence and disposition."""

    candidate: dict[str, Any]
    score: float
    reasons: list[str] = field(default_factory=list)
    activation: str = "pending"  # "auto_enable" | "pending" | "reject"

    @property
    def should_create(self) -> bool:
        """Whether this candidate should be persisted (not rejected)."""
        return self.activation != "reject"

    @property
    def should_auto_enable(self) -> bool:
        return self.activation == "auto_enable"


# ── Scorer ────────────────────────────────────────────────────────────────────


def score_candidate(candidate: dict[str, Any]) -> ScoredCandidate:
    """Score a single discovery candidate.

    The score is a weighted sum of independent signal contributions, clamped
    to [0.0, 1.0].  Each signal appends a human-readable reason string so
    operators can audit why a source was (or was not) auto-enabled.

    Signal weights
    ~~~~~~~~~~~~~~
    Known adapter name (hard requirement):  0.40
    Trusted domain:                         0.25
    Adapter type is structured feed:        0.10
    Property URL keyword present:           0.10
    Name looks descriptive (>= 10 chars):  0.05
    Has explicit config dict:               0.05
    Has explicit poll_interval:             0.05

    Penalty signals (subtract from score)
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    URL is bare root domain (no path):     -0.10
    Name contains generic placeholder:     -0.10
    """
    reasons: list[str] = []
    score = 0.0

    adapter_name = (candidate.get("adapter_name") or "").strip().lower()
    adapter_type = (candidate.get("adapter_type") or "").strip().lower()
    url = (candidate.get("url") or "").strip().lower()
    name = (candidate.get("name") or "").strip()
    config = candidate.get("config")
    poll = candidate.get("poll_interval_seconds")

    # ── Positive signals ──────────────────────────────────────────────────────

    if adapter_name in _KNOWN_ADAPTERS:
        score += 0.40
        reasons.append(f"known_adapter:{adapter_name}")
    else:
        reasons.append(f"unknown_adapter:{adapter_name or 'missing'}")

    domain = _extract_domain(url)
    if domain and any(url.endswith(td) or ("." + td) in url for td in _TRUSTED_PROPERTY_DOMAINS):
        score += 0.25
        reasons.append(f"trusted_domain:{domain}")
    else:
        reasons.append(f"unrecognised_domain:{domain or 'none'}")

    if adapter_type in _HIGH_RELIABILITY_ADAPTER_TYPES:
        score += 0.10
        reasons.append(f"structured_feed_type:{adapter_type}")

    if any(kw in url for kw in _PROPERTY_URL_KEYWORDS):
        score += 0.10
        reasons.append("property_url_keyword")

    if name and len(name) >= 10:
        score += 0.05
        reasons.append("descriptive_name")

    if isinstance(config, dict) and config:
        score += 0.05
        reasons.append("has_config")

    if poll and int(poll) > 0:
        score += 0.05
        reasons.append("has_poll_interval")

    # ── Penalty signals ───────────────────────────────────────────────────────

    from urllib.parse import urlsplit
    parts = urlsplit(url)
    if parts.path in ("", "/"):
        score -= 0.10
        reasons.append("penalty:bare_root_url")

    generic_words = {"discovered", "unknown", "untitled", "feed", "rss", "source"}
    if name and all(w.lower() in generic_words for w in name.split()):
        score -= 0.10
        reasons.append("penalty:generic_name")

    score = max(0.0, min(1.0, score))

    if score >= AUTO_ENABLE_THRESHOLD:
        activation = "auto_enable"
    elif score >= PENDING_THRESHOLD:
        activation = "pending"
    else:
        activation = "reject"

    return ScoredCandidate(
        candidate=candidate,
        score=round(score, 4),
        reasons=reasons,
        activation=activation,
    )


def score_candidates(
    candidates: list[dict[str, Any]],
    *,
    reject_below: float = PENDING_THRESHOLD,
) -> list[ScoredCandidate]:
    """Score a list of candidates, filtering out any below `reject_below`."""
    results = [score_candidate(c) for c in candidates]
    if reject_below > 0:
        results = [r for r in results if r.score >= reject_below]
    return sorted(results, key=lambda r: r.score, reverse=True)


# ── Helpers ───────────────────────────────────────────────────────────────────


def _extract_domain(url: str) -> str:
    """Return the registrable domain portion of a URL (e.g. 'daft.ie')."""
    from urllib.parse import urlsplit
    try:
        netloc = urlsplit(url).netloc.lower()
        # Strip port and www. prefix.
        netloc = netloc.split(":")[0]
        if netloc.startswith("www."):
            netloc = netloc[4:]
        return netloc
    except Exception:
        return ""
