"""LLM / AI endpoints."""

from __future__ import annotations

import json
import os
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from packages.ai.chat_service import (
    create_conversation_payload,
    get_conversation_payload,
    send_message_payload,
)
from packages.ai.compare_service import (
    compute_compare_set,
    latest_auto_compare_payload,
    run_auto_compare,
)
from packages.shared.schemas import (
    AutoCompareRequest,
    CompareSetRequest,
    ConversationCreate,
    ConversationMessageCreate,
    LLMConfigUpdate,
)
from packages.storage.database import get_db_session
from packages.storage.repositories import (
    ConversationRepository,
    LLMEnrichmentRepository,
    OrganicSearchRunRepository,
    PropertyGrantMatchRepository,
    PropertyRepository,
)
from packages.shared.config import settings
from packages.shared.queue import QueueDispatchError, dispatch_or_inline
from packages.ai.bedrock_provider import BedrockProvider
from packages.ai.service import (
    llm_runtime_status,
    set_active_provider,
    get_provider,
    _get_active_provider_name,
)

router = APIRouter()


def _model_requires_inference_profile(model_id: str | None) -> bool:
    """Return True for model families that commonly require inference profiles."""
    if not model_id:
        return False
    return model_id.startswith("amazon.nova-")

def _llm_queue_configured() -> bool:
    return bool(settings.llm_queue_url or os.environ.get("LLM_QUEUE_URL", ""))


def _get_provider_dynamic():
    # Import lazily so tests patching packages.ai.service.get_provider still apply.
    from packages.ai.service import get_provider as dynamic_get_provider

    return dynamic_get_provider()


def _ensure_property_grants(db: Session, prop) -> list:
    """Return cached grant matches for a property, evaluating once when missing."""
    grant_match_repo = PropertyGrantMatchRepository(db)
    matches = grant_match_repo.list_for_property(str(prop.id))
    if matches:
        return matches

    try:
        from packages.grants.engine import evaluate_property_grants

        refreshed = evaluate_property_grants(db, property_obj=prop)
        if refreshed:
            return refreshed
    except Exception:
        # Grant evaluation failures should not block compare/chat flows.
        return matches
    return matches


def _serialize_grant_citations(matches: list) -> list[dict[str, Any]]:
    citations: list[dict[str, Any]] = []
    for match in matches:
        grant = getattr(match, "grant_program", None)
        if not grant:
            continue
        estimated = getattr(match, "estimated_benefit", None)
        citations.append(
            {
                "type": "grant",
                "grant_program_id": str(getattr(grant, "id", "")),
                "code": getattr(grant, "code", None),
                "label": getattr(grant, "name", None),
                "url": getattr(grant, "source_url", None),
                "status": getattr(match, "status", None),
                "estimated_benefit": float(estimated) if estimated is not None else None,
            }
        )
    return citations


@router.get("/config")
def get_llm_config():
    """Get current LLM configuration."""
    runtime = llm_runtime_status()
    provider_name = _get_active_provider_name()
    provider = get_provider(provider_name)
    return {
        "enabled": runtime["enabled"],
        "provider": provider.get_provider_name(),
        "model": provider.get_model_name(),
        "queue_configured": runtime["queue_configured"],
        "ready_for_enrichment": runtime["ready_for_enrichment"],
        "reason": runtime["reason"],
    }


@router.get("/models")
def get_llm_models():
    """Get available LLM models for provider selection UI."""
    provider = BedrockProvider(region=settings.aws_region)
    options = provider.get_runtime_ui_model_options()
    option_ids = {m["id"] for m in options}
    preferred_default = "amazon.titan-text-lite-v1"
    if preferred_default in option_ids:
        default_model = preferred_default
    elif settings.bedrock_model_id in option_ids:
        default_model = settings.bedrock_model_id
    elif options:
        default_model = options[0]["id"]
    else:
        default_model = settings.bedrock_model_id

    return {
        "provider": "bedrock",
        "models": options,
        "default_model": default_model,
    }


@router.put("/config")
def update_llm_config(data: LLMConfigUpdate):
    """Update LLM provider configuration (stored in DynamoDB)."""
    provider_str = data.provider or "bedrock"
    model_str = data.bedrock_model
    updated = set_active_provider(provider_str, model_str)
    if not updated:
        raise HTTPException(
            status_code=503,
            detail="Failed to persist LLM config to DynamoDB. Check AWS credentials and table access.",
        )
    warning = None
    if (
        provider_str == "bedrock"
        and _model_requires_inference_profile(model_str)
        and not settings.bedrock_inference_profile_id
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
        "inference_profile_configured": bool(settings.bedrock_inference_profile_id),
    }


@router.get("/health")
async def llm_health():
    """Check LLM provider availability."""
    runtime = llm_runtime_status()
    if not runtime["enabled"]:
        return {**runtime, "healthy": False}

    provider = get_provider()
    healthy = await provider.health_check()
    model_listed = True
    invoke_ready = True
    invoke_error = None
    if isinstance(provider, BedrockProvider):
        model_listed = provider.is_model_listed(provider.get_model_name())
        if not model_listed:
            healthy = False

        # Ensure status reflects real invoke readiness, not just model listing metadata.
        try:
            await provider.generate(
                prompt='{"ok": true}',
                system_prompt='Return valid JSON only.',
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
        "inference_profile_configured": bool(settings.bedrock_inference_profile_id),
    }


@router.get("/enrichment/{property_id}")
def get_enrichment(property_id: str, db: Session = Depends(get_db_session)):
    """Get LLM enrichment data for a property."""
    repo = LLMEnrichmentRepository(db)
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


@router.post("/enrich/{property_id}")
def trigger_enrichment(property_id: str, db: Session = Depends(get_db_session)):
    """Trigger LLM enrichment for a property."""
    runtime = llm_runtime_status()
    if not runtime["enabled"]:
        raise HTTPException(status_code=503, detail="LLM enrichment is disabled")

    repo = PropertyRepository(db)
    prop = repo.get_by_id(property_id)
    if not prop:
        raise HTTPException(404, "Property not found")

    from apps.worker.tasks import enrich_property_llm

    try:
        return dispatch_or_inline(
            "llm",
            "enrich_property_llm",
            {"property_id": property_id},
            enrich_property_llm,
        )
    except QueueDispatchError as exc:
        raise HTTPException(
            status_code=503,
            detail={
                "code": "llm_dispatch_failed",
                "task_type": "enrich_property_llm",
                "message": "Failed to dispatch LLM enrichment task to queue.",
                "error": str(exc)[:300],
            },
        ) from exc


@router.post("/enrich-batch")
def trigger_batch_enrichment(limit: int = 50):
    """Trigger LLM enrichment for a batch of un-enriched properties."""
    runtime = llm_runtime_status()
    if not runtime["enabled"]:
        raise HTTPException(status_code=503, detail="LLM enrichment is disabled")

    from apps.worker.tasks import enrich_batch_llm

    try:
        dispatch_result = dispatch_or_inline(
            "llm",
            "enrich_batch_llm",
            {"limit": limit},
            enrich_batch_llm,
        )
        return {**dispatch_result, "limit": limit}
    except QueueDispatchError as exc:
        raise HTTPException(
            status_code=503,
            detail={
                "code": "llm_dispatch_failed",
                "task_type": "enrich_batch_llm",
                "message": "Failed to dispatch LLM batch enrichment task to queue.",
                "error": str(exc)[:300],
            },
        ) from exc


@router.post("/compare")
async def compare_properties(
    property_a_id: str,
    property_b_id: str,
    db: Session = Depends(get_db_session),
):
    """Compare two properties using LLM analysis."""
    from packages.ai.service import compare_properties as llm_compare

    repo = PropertyRepository(db)
    prop_a = repo.get_by_id(property_a_id)
    prop_b = repo.get_by_id(property_b_id)

    if not prop_a or not prop_b:
        raise HTTPException(404, "One or both properties not found")

    def _prop_dict(p):
        return {
            "title": p.title,
            "address": p.address,
            "county": p.county,
            "price": float(p.price) if p.price else None,
            "property_type": p.property_type,
            "bedrooms": p.bedrooms,
            "bathrooms": p.bathrooms,
            "floor_area_sqm": float(p.floor_area_sqm) if p.floor_area_sqm else None,
            "ber_rating": p.ber_rating,
            "description": p.description,
        }

    result = await llm_compare(_prop_dict(prop_a), _prop_dict(prop_b))
    return result


@router.get("/stats")
def get_llm_stats(db: Session = Depends(get_db_session)):
    """Get LLM enrichment statistics."""
    repo = LLMEnrichmentRepository(db)
    return {
        "total_processed": repo.count_processed(),
        "avg_processing_time_ms": repo.avg_processing_time(),
    }


@router.post("/compare-set")
async def compare_property_set(data: CompareSetRequest, db: Session = Depends(get_db_session)):
    """Compare up to 5 properties and return mode-specific value ranking + LLM analysis."""
    result = await compute_compare_set(
        db=db,
        property_ids=data.property_ids,
        ranking_mode=data.ranking_mode,
        weights=data.weights.model_dump() if data.weights else None,
        property_repo_factory=PropertyRepository,
        enrichment_repo_factory=LLMEnrichmentRepository,
        ensure_property_grants=_ensure_property_grants,
        provider_getter=_get_provider_dynamic,
    )
    return result


@router.post("/auto-compare")
async def auto_compare(
    data: AutoCompareRequest,
    db: Session = Depends(get_db_session),
):
    """Run an auto-compare for current search context and persist run metadata."""
    session_id = data.session_id.strip()
    return await run_auto_compare(
        db=db,
        session_id=session_id,
        property_ids=data.property_ids,
        ranking_mode=data.ranking_mode,
        weights=data.weights.model_dump() if data.weights else None,
        search_context=data.search_context,
        run_repo_factory=OrganicSearchRunRepository,
        compute_compare_set_fn=lambda **kwargs: compute_compare_set(
            **kwargs,
            property_repo_factory=PropertyRepository,
            enrichment_repo_factory=LLMEnrichmentRepository,
            ensure_property_grants=_ensure_property_grants,
            provider_getter=_get_provider_dynamic,
        ),
    )


@router.get("/auto-compare/latest")
def get_latest_auto_compare(
    session_id: str = Query(..., min_length=1),
    db: Session = Depends(get_db_session),
):
    """Return latest persisted auto-compare run metadata for a session."""
    return latest_auto_compare_payload(
        db=db,
        session_id=session_id,
        run_repo_factory=OrganicSearchRunRepository,
    )


@router.post("/chat/conversations", status_code=201)
def create_conversation(data: ConversationCreate, db: Session = Depends(get_db_session)):
    """Create a new LLM chat conversation."""
    return create_conversation_payload(
        db=db,
        data=data,
        conversation_repo_factory=ConversationRepository,
    )


@router.get("/chat/conversations/{conversation_id}")
def get_conversation(conversation_id: str, db: Session = Depends(get_db_session)):
    """Get a conversation and all messages."""
    return get_conversation_payload(
        db=db,
        conversation_id=conversation_id,
        conversation_repo_factory=ConversationRepository,
    )


@router.post("/chat/conversations/{conversation_id}/messages")
async def send_message(
    conversation_id: str,
    data: ConversationMessageCreate,
    db: Session = Depends(get_db_session),
):
    """Send a user message and receive assistant response."""
    return await send_message_payload(
        db=db,
        conversation_id=conversation_id,
        data=data,
        conversation_repo_factory=ConversationRepository,
        property_repo_factory=PropertyRepository,
        ensure_property_grants_fn=_ensure_property_grants,
        serialize_grant_citations_fn=_serialize_grant_citations,
        provider_getter=_get_provider_dynamic,
    )


