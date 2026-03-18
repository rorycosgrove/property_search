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
from packages.ai.runtime_service import (
    llm_config_payload,
    llm_enrichment_payload,
    llm_health_payload,
    llm_models_payload,
    llm_stats_payload,
    trigger_batch_enrichment_payload,
    trigger_enrichment_payload,
    update_llm_config_payload,
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
    PropertyDocumentRepository,
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
    return llm_config_payload(
        runtime_status_fn=llm_runtime_status,
        active_provider_name_fn=_get_active_provider_name,
        provider_getter=get_provider,
    )


@router.get("/models")
def get_llm_models():
    """Get available LLM models for provider selection UI."""
    return llm_models_payload(settings_obj=settings, bedrock_provider_cls=BedrockProvider)


@router.put("/config")
def update_llm_config(data: LLMConfigUpdate):
    """Update LLM provider configuration (stored in DynamoDB)."""
    return update_llm_config_payload(
        data=data,
        settings_obj=settings,
        set_active_provider_fn=set_active_provider,
    )


@router.get("/health")
async def llm_health():
    """Check LLM provider availability."""
    return await llm_health_payload(
        runtime_status_fn=llm_runtime_status,
        provider_getter=_get_provider_dynamic,
        bedrock_provider_cls=BedrockProvider,
        settings_obj=settings,
    )


@router.get("/enrichment/{property_id}")
def get_enrichment(property_id: str, db: Session = Depends(get_db_session)):
    """Get LLM enrichment data for a property."""
    return llm_enrichment_payload(
        db=db,
        property_id=property_id,
        enrichment_repo_factory=LLMEnrichmentRepository,
    )


@router.post("/enrich/{property_id}")
def trigger_enrichment(property_id: str, db: Session = Depends(get_db_session)):
    """Trigger LLM enrichment for a property."""
    from apps.worker.tasks import enrich_property_llm

    return trigger_enrichment_payload(
        db=db,
        property_id=property_id,
        runtime_status_fn=llm_runtime_status,
        property_repo_factory=PropertyRepository,
        dispatch_or_inline_fn=dispatch_or_inline,
        queue_error_cls=QueueDispatchError,
        inline_task_fn=enrich_property_llm,
    )


@router.post("/enrich-batch")
def trigger_batch_enrichment(limit: int = 50):
    """Trigger LLM enrichment for a batch of un-enriched properties."""
    from apps.worker.tasks import enrich_batch_llm

    return trigger_batch_enrichment_payload(
        limit=limit,
        runtime_status_fn=llm_runtime_status,
        dispatch_or_inline_fn=dispatch_or_inline,
        queue_error_cls=QueueDispatchError,
        inline_task_fn=enrich_batch_llm,
    )


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
    return llm_stats_payload(db=db, enrichment_repo_factory=LLMEnrichmentRepository)


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
        property_document_repo_factory=PropertyDocumentRepository,
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
            property_document_repo_factory=PropertyDocumentRepository,
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


