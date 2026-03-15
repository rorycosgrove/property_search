from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from packages.sources.discovery import canonicalize_source_url
from packages.sources.registry import get_adapter


@dataclass
class ValidatedDiscoveryCandidate:
    name: str
    url: str
    canonical_url: str
    adapter_type: str
    adapter_name: str
    config: dict[str, Any]
    poll_interval_seconds: int
    tags: list[str]


def validate_source_config(adapter_name: str, config: dict[str, Any] | None) -> list[str]:
    try:
        adapter = get_adapter(adapter_name)
    except KeyError:
        return [f"unknown adapter: {adapter_name}"]
    return adapter.validate_config(config or {})


def validate_discovery_candidate(
    candidate: dict[str, Any],
    *,
    adapter_names: set[str],
) -> tuple[ValidatedDiscoveryCandidate | None, str | None, list[str]]:
    adapter_name = (candidate.get("adapter_name") or "").strip().lower()
    url = (candidate.get("url") or "").strip()
    canonical_url = canonicalize_source_url(url)
    if adapter_name not in adapter_names or not url or not canonical_url:
        return None, "unknown_adapter_or_missing_url", []

    config = candidate.get("config") or {}
    config_errors = validate_source_config(adapter_name, config)
    if config_errors:
        return None, "invalid_adapter_config", config_errors

    tags = candidate.get("tags") or []
    if not isinstance(tags, list):
        tags = []

    validated = ValidatedDiscoveryCandidate(
        name=candidate.get("name") or f"Discovered {adapter_name}",
        url=url,
        canonical_url=canonical_url,
        adapter_type=candidate.get("adapter_type") or "scraper",
        adapter_name=adapter_name,
        config=config,
        poll_interval_seconds=int(candidate.get("poll_interval_seconds") or 21600),
        tags=tags,
    )
    return validated, None, []