"""
LLM service layer.

Provides high-level property enrichment functions that use the
configured LLM provider (Amazon Bedrock). Handles provider
switching via DynamoDB config and caching of results.
"""

from __future__ import annotations

import json
import os
from typing import Any

from packages.ai.bedrock_provider import BedrockProvider
from packages.ai.prompts import (
    COMPARISON_PROMPT,
    MARKET_TREND_PROMPT,
    PROPERTY_SUMMARY_PROMPT,
    SYSTEM_PROMPT,
)
from packages.ai.provider import LLMProvider, LLMResponse
from packages.shared.config import settings
from packages.shared.logging import get_logger

logger = get_logger(__name__)

_runtime_provider_override: str | None = None
_runtime_model_override: str | None = None

# ── Provider factory ──────────────────────────────────────────────────────────

def llm_runtime_status() -> dict:
    """Return LLM runtime status for diagnostics and API readiness checks."""
    provider = _get_active_provider_name()
    model = _get_active_model()
    enabled = bool(settings.llm_enabled)
    queue_configured = bool(settings.llm_queue_url or os.environ.get("LLM_QUEUE_URL", ""))
    reason = "ok"
    if not enabled:
        reason = "llm_disabled"
    elif not queue_configured:
        reason = "llm_queue_unconfigured"

    return {
        "enabled": enabled,
        "provider": provider,
        "model": model,
        "queue_configured": queue_configured,
        "ready_for_enrichment": enabled and queue_configured,
        "reason": reason,
        "runtime_override": bool(_runtime_provider_override or _runtime_model_override),
        "dynamo_config_table": getattr(settings, "dynamodb_config_table", None),
        "aws_region": getattr(settings, "aws_region", None),
    }

def get_provider(provider_name: str | None = None, model: str | None = None) -> LLMProvider:
    """
    Get an LLM provider instance.

    Checks DynamoDB for runtime config override, then falls back to settings.
    """
    provider_name = provider_name or _get_active_provider_name()
    active_model = model or _get_active_model()

    if provider_name != "bedrock":
        logger.warning("llm_provider_not_supported", provider=provider_name, fallback="bedrock")

    return BedrockProvider(model_id=active_model)


def _get_active_provider_name() -> str:
    """Get the active provider name, checking DynamoDB cache first."""
    if _runtime_provider_override:
        return _runtime_provider_override

    try:
        return _get_dynamo_config("llm_provider") or settings.llm_provider
    except Exception:
        return settings.llm_provider


def _get_active_model() -> str | None:
    """Get the active model name from DynamoDB cache."""
    if _runtime_model_override:
        return _runtime_model_override

    try:
        return _get_dynamo_config("llm_model") or settings.bedrock_model_id
    except Exception:
        return settings.bedrock_model_id


def set_active_provider(provider: str, model: str | None = None) -> bool:
    """Set the active LLM provider in DynamoDB (runtime config)."""
    global _runtime_provider_override, _runtime_model_override

    # Always keep a local runtime override so local dev still works without DynamoDB access.
    _runtime_provider_override = provider
    if model:
        _runtime_model_override = model

    try:
        _set_dynamo_config("llm_provider", provider)
        if model:
            _set_dynamo_config("llm_model", model)
        logger.info("llm_provider_changed", provider=provider, model=model)
        return True
    except Exception as e:
        logger.warning(
            "llm_config_dynamo_unavailable_using_runtime_override",
            error=str(e),
            provider=provider,
            model=model,
        )
        return True


# ── DynamoDB config helpers ───────────────────────────────────────────────────

_dynamo_client = None


def _get_dynamo():
    global _dynamo_client
    if _dynamo_client is None:
        import boto3
        _dynamo_client = boto3.resource("dynamodb", region_name=settings.aws_region)
    return _dynamo_client


def _get_dynamo_config(key: str) -> str | None:
    """Read a config value from the DynamoDB config table."""
    table = _get_dynamo().Table(settings.dynamodb_config_table)
    response = table.get_item(Key={"config_key": key})
    item = response.get("Item")
    return item.get("config_value") if item else None


def _set_dynamo_config(key: str, value: str) -> None:
    """Write a config value to the DynamoDB config table."""
    table = _get_dynamo().Table(settings.dynamodb_config_table)
    table.put_item(Item={"config_key": key, "config_value": value})


# ── High-level enrichment functions ───────────────────────────────────────────


async def enrich_property(
    property_data: dict[str, Any],
    nearby_sold: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """
    Generate LLM enrichment for a property listing.

    Returns a dict matching LLMEnrichment model fields.
    """
    provider = get_provider()

    # Format nearby sold data
    sold_text = "No comparable sales data available."
    if nearby_sold:
        lines = []
        for s in nearby_sold[:10]:
            price_val = s.get('price')
            price_str = f"€{price_val:,.0f}" if isinstance(price_val, (int, float)) else "N/A"
            lines.append(
                f"  - {s.get('address', 'Unknown')}: {price_str} "
                f"({s.get('sale_date', 'N/A')})"
            )
        sold_text = "\n".join(lines)

    prompt = PROPERTY_SUMMARY_PROMPT.format(
        title=property_data.get("title", ""),
        address=property_data.get("address", ""),
        county=property_data.get("county", ""),
        price=f"€{property_data.get('price', 0):,.0f}" if property_data.get("price") else "POA",
        property_type=property_data.get("property_type", "Unknown"),
        bedrooms=property_data.get("bedrooms", "N/A"),
        bathrooms=property_data.get("bathrooms", "N/A"),
        floor_area_sqm=property_data.get("floor_area_sqm", "N/A"),
        ber_rating=property_data.get("ber_rating", "N/A"),
        description=(property_data.get("description", "") or "")[:1000],
        nearby_sold=sold_text,
    )

    response = await provider.generate(
        prompt=prompt,
        system_prompt=SYSTEM_PROMPT,
        temperature=0.3,
        json_mode=True,
    )

    return _parse_enrichment_response(response, provider)


async def analyze_market(market_data: dict[str, Any]) -> dict[str, Any]:
    """Generate LLM market analysis."""
    provider = get_provider()

    prompt = MARKET_TREND_PROMPT.format(
        county=market_data.get("county", "National"),
        avg_price=f"€{market_data.get('avg_price', 0):,.0f}",
        median_price=f"€{market_data.get('median_price', 0):,.0f}",
        listing_count=market_data.get("listing_count", 0),
        price_trend=market_data.get("price_trend", "N/A"),
        new_listings=market_data.get("new_listings", 0),
        ber_distribution=market_data.get("ber_distribution", "N/A"),
    )

    response = await provider.generate(
        prompt=prompt,
        system_prompt=SYSTEM_PROMPT,
        temperature=0.4,
        json_mode=True,
    )

    try:
        return json.loads(response.content)
    except json.JSONDecodeError:
        return {"market_summary": response.content, "raw_response": True}


async def compare_properties(
    prop_a: dict[str, Any],
    prop_b: dict[str, Any],
) -> dict[str, Any]:
    """Generate LLM comparison of two properties."""
    provider = get_provider()

    def format_prop(p: dict) -> str:
        return (
            f"Title: {p.get('title', '')}\n"
            f"Address: {p.get('address', '')}\n"
            f"Price: €{p.get('price', 0):,.0f}\n"
            f"Type: {p.get('property_type', 'Unknown')}\n"
            f"Beds: {p.get('bedrooms', 'N/A')}, Baths: {p.get('bathrooms', 'N/A')}\n"
            f"Area: {p.get('floor_area_sqm', 'N/A')} sq m\n"
            f"BER: {p.get('ber_rating', 'N/A')}\n"
            f"Description: {(p.get('description', '') or '')[:500]}"
        )

    prompt = COMPARISON_PROMPT.format(
        property_a=format_prop(prop_a),
        property_b=format_prop(prop_b),
    )

    response = await provider.generate(
        prompt=prompt,
        system_prompt=SYSTEM_PROMPT,
        temperature=0.3,
        json_mode=True,
    )

    try:
        return json.loads(response.content)
    except json.JSONDecodeError:
        return {"recommendation": response.content, "raw_response": True}


# ── Helpers ───────────────────────────────────────────────────────────────────


def _parse_enrichment_response(response: LLMResponse, provider: LLMProvider) -> dict[str, Any]:
    """Parse LLM enrichment response into a structured dict."""
    try:
        data = json.loads(response.content)
    except json.JSONDecodeError:
        data = {"summary": response.content}

    return {
        "summary": data.get("summary", ""),
        "value_score": _clamp_float(data.get("value_score"), 1.0, 10.0),
        "value_reasoning": data.get("value_reasoning", ""),
        "pros": data.get("pros", []),
        "cons": data.get("cons", []),
        "extracted_features": data.get("extracted_features", {}),
        "neighbourhood_notes": data.get("neighbourhood_notes", ""),
        "investment_potential": data.get("investment_potential", ""),
        "llm_provider": provider.get_provider_name(),
        "llm_model": provider.get_model_name(),
        "processing_time_ms": response.processing_time_ms,
    }


def _clamp_float(val: Any, lo: float, hi: float) -> float | None:
    """Clamp a value to [lo, hi] range, returning None if invalid."""
    if val is None:
        return None
    try:
        f = float(val)
        return max(lo, min(hi, f))
    except (ValueError, TypeError):
        return None
