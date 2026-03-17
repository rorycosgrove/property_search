from __future__ import annotations

from typing import Any, Callable

from fastapi import HTTPException
from sqlalchemy.orm import Session


def model_requires_inference_profile(model_id: str | None) -> bool:
    """Return True for model families that commonly require inference profiles."""
    if not model_id:
        return False
    return model_id.startswith("amazon.nova-")


def llm_config_payload(
    *,
    runtime_status_fn: Callable[[], dict[str, Any]],
    active_provider_name_fn: Callable[[], str],
    provider_getter: Callable[[str | None], Any],
) -> dict[str, Any]:
    runtime = runtime_status_fn()
    provider_name = active_provider_name_fn()
    provider = provider_getter(provider_name)
    return {
        "enabled": runtime["enabled"],
        "provider": provider.get_provider_name(),
        "model": provider.get_model_name(),
        "queue_configured": runtime["queue_configured"],
        "ready_for_enrichment": runtime["ready_for_enrichment"],
        "reason": runtime["reason"],
    }


def llm_models_payload(*, settings_obj: Any, bedrock_provider_cls: type) -> dict[str, Any]:
    provider = bedrock_provider_cls(region=settings_obj.aws_region)
    options = provider.get_runtime_ui_model_options()
    option_ids = {model["id"] for model in options}
    preferred_default = "amazon.titan-text-lite-v1"
    if preferred_default in option_ids:
        default_model = preferred_default
    elif settings_obj.bedrock_model_id in option_ids:
        default_model = settings_obj.bedrock_model_id
    elif options:
        default_model = options[0]["id"]
    else:
        default_model = settings_obj.bedrock_model_id

    return {
        "provider": "bedrock",
        "models": options,
        "default_model": default_model,
    }


def update_llm_config_payload(
    *,
    data: Any,
    settings_obj: Any,
    set_active_provider_fn: Callable[[str, str | None], bool],
) -> dict[str, Any]:
    provider_str = data.provider or "bedrock"
    model_str = data.bedrock_model
    updated = set_active_provider_fn(provider_str, model_str)
    if not updated:
        raise HTTPException(
            status_code=503,
            detail="Failed to persist LLM config to DynamoDB. Check AWS credentials and table access.",
        )

    warning = None
    if (
        provider_str == "bedrock"
        and model_requires_inference_profile(model_str)
        and not settings_obj.bedrock_inference_profile_id
    ):
        warning = (
            "Selected model may require BEDROCK_INFERENCE_PROFILE_ID for invocation. "
            "Set it in .env and restart the API."
        )

    return {
        "provider": provider_str,
        "model": model_str,
        "updated": True,
        "warning": warning,
        "inference_profile_configured": bool(settings_obj.bedrock_inference_profile_id),
    }


async def llm_health_payload(
    *,
    runtime_status_fn: Callable[[], dict[str, Any]],
    provider_getter: Callable[[], Any],
    bedrock_provider_cls: type,
    settings_obj: Any,
) -> dict[str, Any]:
    runtime = runtime_status_fn()
    if not runtime["enabled"]:
        return {**runtime, "healthy": False}

    provider = provider_getter()
    healthy = await provider.health_check()
    model_listed = True
    invoke_ready = True
    invoke_error = None

    if isinstance(provider, bedrock_provider_cls):
        model_listed = provider.is_model_listed(provider.get_model_name())
        if not model_listed:
            healthy = False

        try:
            await provider.generate(
                prompt='{"ok": true}',
                system_prompt="Return valid JSON only.",
                json_mode=True,
                max_tokens=32,
                temperature=0.0,
            )
        except Exception as exc:
            invoke_ready = False
            invoke_error = str(exc)
            healthy = False

    reason = runtime["reason"]
    if reason == "ok" and not model_listed:
        reason = "model_not_listed"
    if reason == "ok" and not invoke_ready:
        reason = "model_invoke_failed"

    return {
        "enabled": runtime["enabled"],
        "provider": provider.get_provider_name(),
        "model": provider.get_model_name(),
        "queue_configured": runtime["queue_configured"],
        "ready_for_enrichment": runtime["ready_for_enrichment"],
        "reason": reason,
        "healthy": healthy,
        "model_listed": model_listed,
        "invoke_ready": invoke_ready,
        "invoke_error": invoke_error,
        "inference_profile_configured": bool(settings_obj.bedrock_inference_profile_id),
    }


def llm_enrichment_payload(
    *,
    db: Session,
    property_id: str,
    enrichment_repo_factory: Callable[[Session], Any],
) -> dict[str, Any]:
    repo = enrichment_repo_factory(db)
    enrichment = repo.get_by_property_id(property_id)
    if not enrichment:
        raise HTTPException(404, "No enrichment data for this property")

    return {
        "id": str(enrichment.id),
        "property_id": str(enrichment.property_id),
        "summary": enrichment.summary,
        "value_score": enrichment.value_score,
        "value_reasoning": enrichment.value_reasoning,
        "pros": enrichment.pros,
        "cons": enrichment.cons,
        "extracted_features": enrichment.extracted_features,
        "neighbourhood_notes": enrichment.neighbourhood_notes,
        "investment_potential": enrichment.investment_potential,
        "llm_provider": enrichment.llm_provider,
        "llm_model": enrichment.llm_model,
        "processed_at": enrichment.processed_at.isoformat() if enrichment.processed_at else None,
    }


def trigger_enrichment_payload(
    *,
    db: Session,
    property_id: str,
    runtime_status_fn: Callable[[], dict[str, Any]],
    property_repo_factory: Callable[[Session], Any],
    dispatch_or_inline_fn: Callable[..., dict[str, Any]],
    queue_error_cls: type,
    inline_task_fn: Callable[..., Any],
) -> dict[str, Any]:
    runtime = runtime_status_fn()
    if not runtime["enabled"]:
        raise HTTPException(status_code=503, detail="LLM enrichment is disabled")

    repo = property_repo_factory(db)
    prop = repo.get_by_id(property_id)
    if not prop:
        raise HTTPException(404, "Property not found")

    try:
        return dispatch_or_inline_fn(
            "llm",
            "enrich_property_llm",
            {"property_id": property_id},
            inline_task_fn,
        )
    except queue_error_cls as exc:
        raise HTTPException(
            status_code=503,
            detail={
                "code": "llm_dispatch_failed",
                "task_type": "enrich_property_llm",
                "message": "Failed to dispatch LLM enrichment task to queue.",
                "error": str(exc)[:300],
            },
        ) from exc


def trigger_batch_enrichment_payload(
    *,
    limit: int,
    runtime_status_fn: Callable[[], dict[str, Any]],
    dispatch_or_inline_fn: Callable[..., dict[str, Any]],
    queue_error_cls: type,
    inline_task_fn: Callable[..., Any],
) -> dict[str, Any]:
    runtime = runtime_status_fn()
    if not runtime["enabled"]:
        raise HTTPException(status_code=503, detail="LLM enrichment is disabled")

    try:
        dispatch_result = dispatch_or_inline_fn(
            "llm",
            "enrich_batch_llm",
            {"limit": limit},
            inline_task_fn,
        )
        return {**dispatch_result, "limit": limit}
    except queue_error_cls as exc:
        raise HTTPException(
            status_code=503,
            detail={
                "code": "llm_dispatch_failed",
                "task_type": "enrich_batch_llm",
                "message": "Failed to dispatch LLM batch enrichment task to queue.",
                "error": str(exc)[:300],
            },
        ) from exc


def llm_stats_payload(*, db: Session, enrichment_repo_factory: Callable[[Session], Any]) -> dict[str, Any]:
    repo = enrichment_repo_factory(db)
    return {
        "total_processed": repo.count_processed(),
        "avg_processing_time_ms": repo.avg_processing_time(),
    }
