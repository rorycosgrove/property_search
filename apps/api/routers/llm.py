"""LLM / AI endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from packages.shared.schemas import LLMConfigUpdate
from packages.storage.database import get_db_session
from packages.storage.repositories import LLMEnrichmentRepository, PropertyRepository

router = APIRouter()


@router.get("/config")
def get_llm_config():
    """Get current LLM configuration."""
    from packages.ai.service import _get_active_provider_name, get_provider

    provider_name = _get_active_provider_name()
    provider = get_provider(provider_name)

    return {
        "provider": provider.get_provider_name(),
        "model": provider.get_model_name(),
    }


@router.put("/config")
def update_llm_config(data: LLMConfigUpdate):
    """Update LLM provider configuration (stored in DynamoDB)."""
    from packages.ai.service import set_active_provider

    provider_str = data.provider or "bedrock"
    model_str = data.bedrock_model
    set_active_provider(provider_str, model_str)
    return {"provider": provider_str, "model": model_str, "updated": True}


@router.get("/health")
async def llm_health():
    """Check LLM provider availability."""
    from packages.ai.service import get_provider

    provider = get_provider()
    healthy = await provider.health_check()
    return {
        "provider": provider.get_provider_name(),
        "model": provider.get_model_name(),
        "healthy": healthy,
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
    repo = PropertyRepository(db)
    prop = repo.get_by_id(property_id)
    if not prop:
        raise HTTPException(404, "Property not found")

    from packages.shared.queue import send_task
    message_id = send_task("llm", "enrich_property_llm", {"property_id": property_id})
    return {"task_id": message_id, "status": "dispatched"}


@router.post("/enrich-batch")
def trigger_batch_enrichment(limit: int = 50):
    """Trigger LLM enrichment for a batch of un-enriched properties."""
    from packages.shared.queue import send_task
    message_id = send_task("llm", "enrich_batch_llm", {"limit": limit})
    return {"task_id": message_id, "status": "dispatched", "limit": limit}


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
