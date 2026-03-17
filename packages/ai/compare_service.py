from __future__ import annotations

import json
from typing import Any, Callable

from fastapi import HTTPException
from sqlalchemy.orm import Session


def extract_compare_result_from_steps(steps: list[Any] | None) -> dict[str, Any] | None:
    """Extract persisted compare-set payload from run steps when present."""
    for step in steps or []:
        if not isinstance(step, dict):
            continue
        if step.get("step") != "compare_property_set":
            continue
        step_result = step.get("result")
        if isinstance(step_result, dict) and "ranking_mode" in step_result and "properties" in step_result:
            return step_result
    return None


def search_context_signature(value: Any) -> str:
    """Create a stable signature for auto-compare search context."""
    if not isinstance(value, dict):
        return "{}"
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"))
    except TypeError:
        # Non-serializable values should not break comparison cache safety.
        return "{}"


async def compute_compare_set(
    *,
    db: Session,
    property_ids: list[str],
    ranking_mode: str,
    weights: dict[str, Any] | None,
    property_repo_factory: Callable[[Session], Any],
    enrichment_repo_factory: Callable[[Session], Any],
    ensure_property_grants: Callable[[Session, Any], list[Any]],
    provider_getter: Callable[[], Any],
) -> dict[str, Any]:
    """Compute compare-set output used by manual and automatic comparison flows."""
    property_repo = property_repo_factory(db)
    enrichment_repo = enrichment_repo_factory(db)

    properties = []
    for property_id in property_ids:
        prop = property_repo.get_by_id(property_id)
        if not prop:
            raise HTTPException(404, f"Property not found: {property_id}")
        properties.append(prop)

    active_weights = weights or {
        "value": 0.4,
        "location": 0.2,
        "condition": 0.2,
        "potential": 0.2,
    }

    metrics: list[dict[str, Any]] = []
    for prop in properties:
        enrichment = enrichment_repo.get_by_property_id(str(prop.id))
        grant_matches = ensure_property_grants(db, prop)

        price_val = float(prop.price) if prop.price is not None else None
        area_val = float(prop.floor_area_sqm) if prop.floor_area_sqm is not None else None
        llm_score = float(enrichment.value_score) if enrichment and enrichment.value_score is not None else 0.0
        grants_estimated_total = sum(
            float(match.estimated_benefit) for match in grant_matches if match.estimated_benefit is not None
        )

        price_per_sqm = None
        if price_val and area_val and area_val > 0:
            price_per_sqm = price_val / area_val

        ber_boost = _ber_boost(prop.ber_rating)
        grants_boost = min(2.0, grants_estimated_total / 10000.0)
        hybrid_score = min(10.0, max(0.0, (llm_score * 0.75) + ber_boost + grants_boost))
        weighted_score = min(
            10.0,
            max(
                0.0,
                (llm_score * active_weights["value"])
                + (ber_boost * 10 * active_weights["condition"])
                + (grants_boost * 10 * active_weights["potential"])
                + (_location_score(prop.county) * active_weights["location"]),
            ),
        )

        image_url = None
        if prop.images and isinstance(prop.images, list) and len(prop.images) > 0:
            maybe_url = prop.images[0].get("url") if isinstance(prop.images[0], dict) else None
            if isinstance(maybe_url, str):
                image_url = maybe_url

        metrics.append(
            {
                "property_id": str(prop.id),
                "title": prop.title,
                "address": prop.address,
                "county": prop.county,
                "url": prop.url,
                "image_url": image_url,
                "price": price_val,
                "price_per_sqm": price_per_sqm,
                "bedrooms": prop.bedrooms,
                "bathrooms": prop.bathrooms,
                "floor_area_sqm": area_val,
                "ber_rating": prop.ber_rating,
                "llm_value_score": llm_score,
                "hybrid_score": hybrid_score,
                "weighted_score": weighted_score,
                "grants_estimated_total": grants_estimated_total,
                "grants_count": len(grant_matches),
            }
        )

    mode_to_key = {
        "llm_only": "llm_value_score",
        "hybrid": "hybrid_score",
        "user_weighted": "weighted_score",
    }
    score_key = mode_to_key.get(ranking_mode, "hybrid_score")
    metrics.sort(key=lambda metric: float(metric.get(score_key) or 0.0), reverse=True)
    winner = metrics[0]["property_id"] if metrics else None

    try:
        analysis = await _generate_compare_set_analysis(
            ranking_mode=ranking_mode,
            metrics=metrics,
            provider_getter=provider_getter,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail={
                "code": "llm_analysis_unavailable",
                "message": (
                    "LLM analysis is unavailable because the selected Bedrock model could not be invoked. "
                    "Check model access approvals/inference profile setup in AWS Bedrock."
                ),
                "error": str(exc)[:300],
            },
        ) from exc

    return {
        "ranking_mode": ranking_mode,
        "properties": metrics,
        "winner_property_id": winner,
        "analysis": analysis,
    }


async def run_auto_compare(
    *,
    db: Session,
    session_id: str,
    property_ids: list[str],
    ranking_mode: str,
    weights: dict[str, Any] | None,
    search_context: dict[str, Any],
    run_repo_factory: Callable[[Session], Any],
    compute_compare_set_fn: Callable[..., Any],
) -> dict[str, Any]:
    """Run an auto-compare for current search context and persist run metadata."""
    run_repo = run_repo_factory(db)

    latest_run = run_repo.get_latest_for_session(session_id=session_id, triggered_from="auto_compare")
    if latest_run and latest_run.status == "completed":
        latest_options = latest_run.options or {}
        latest_ids = latest_options.get("property_ids") if isinstance(latest_options, dict) else None
        if isinstance(latest_ids, list):
            normalized_latest_ids = [
                property_id for property_id in latest_ids if isinstance(property_id, str) and property_id
            ][:5]
            normalized_requested_ids = [
                property_id for property_id in property_ids if isinstance(property_id, str) and property_id
            ][:5]
            latest_result = extract_compare_result_from_steps(latest_run.steps)
            latest_search_signature = search_context_signature(latest_options.get("search_context"))
            requested_search_signature = search_context_signature(search_context)
            if (
                latest_options.get("ranking_mode") == ranking_mode
                and normalized_latest_ids == normalized_requested_ids
                and latest_search_signature == requested_search_signature
                and latest_result is not None
            ):
                return {
                    "run_id": str(latest_run.id),
                    "session_id": session_id,
                    "result": latest_result,
                    "cached": True,
                }

    try:
        result = await compute_compare_set_fn(
            db=db,
            property_ids=property_ids,
            ranking_mode=ranking_mode,
            weights=weights,
        )
        run = run_repo.create(
            status="completed",
            triggered_from="auto_compare",
            options={
                "session_id": session_id,
                "ranking_mode": ranking_mode,
                "property_ids": property_ids,
                "search_context": search_context,
            },
            steps=[
                {
                    "step": "compare_property_set",
                    "status": "completed",
                    "result": result,
                }
            ],
        )
        return {
            "run_id": str(run.id),
            "session_id": session_id,
            "result": result,
            "cached": False,
        }
    except HTTPException:
        raise
    except Exception as exc:
        run = run_repo.create(
            status="failed",
            triggered_from="auto_compare",
            options={
                "session_id": session_id,
                "ranking_mode": ranking_mode,
                "property_ids": property_ids,
                "search_context": search_context,
            },
            steps=[],
            error=str(exc),
        )
        raise HTTPException(
            status_code=503,
            detail={
                "code": "auto_compare_failed",
                "message": "Automatic comparison failed.",
                "run_id": str(run.id),
                "error": str(exc)[:300],
            },
        ) from exc


def latest_auto_compare_payload(
    *,
    db: Session,
    session_id: str,
    run_repo_factory: Callable[[Session], Any],
) -> dict[str, Any]:
    """Return latest persisted auto-compare run metadata for a session."""
    run_repo = run_repo_factory(db)
    run = run_repo.get_latest_for_session(session_id=session_id, triggered_from="auto_compare")
    if not run:
        raise HTTPException(404, "No auto-compare run for this session")

    latest_result = extract_compare_result_from_steps(run.steps)

    return {
        "run_id": str(run.id),
        "status": run.status,
        "options": run.options or {},
        "steps": run.steps or [],
        "result": latest_result,
        "error": run.error,
        "created_at": run.created_at.isoformat() if run.created_at else None,
    }


def _ber_boost(ber_rating: str | None) -> float:
    if not ber_rating:
        return 0.0
    rating = ber_rating.upper()
    if rating.startswith("A"):
        return 1.5
    if rating.startswith("B"):
        return 1.0
    if rating.startswith("C"):
        return 0.6
    if rating.startswith("D"):
        return 0.2
    return -0.2


def _location_score(county: str | None) -> float:
    if not county:
        return 5.0
    # Lightweight baseline until county-level market scoring is added.
    return 6.5 if county.lower() in {"dublin", "cork", "galway"} else 5.5


async def _generate_compare_set_analysis(
    *,
    ranking_mode: str,
    metrics: list[dict[str, Any]],
    provider_getter: Callable[[], Any],
) -> dict[str, Any]:
    provider = provider_getter()
    payload = json.dumps(metrics, ensure_ascii=True)
    prompt = (
        "You are evaluating value-for-money in Irish property listings. "
        "Given the property metrics JSON and ranking mode, return JSON only with keys: "
        "headline, recommendation, key_tradeoffs (array of strings), confidence (low|medium|high), reasoning.\n\n"
        f"Ranking mode: {ranking_mode}\n"
        f"Metrics JSON: {payload}"
    )

    response = await provider.generate(
        prompt=prompt,
        system_prompt=(
            "Be concise, practical, and transparent. If data is incomplete, state uncertainty explicitly."
        ),
        temperature=0.2,
        json_mode=True,
        max_tokens=800,
    )

    try:
        parsed = json.loads(response.content)
    except json.JSONDecodeError:
        parsed = {
            "headline": "Best value recommendation",
            "recommendation": response.content,
            "key_tradeoffs": ["Some structured metrics were unavailable."],
            "confidence": "medium",
        }

    citations = [
        {
            "type": "property",
            "property_id": metric.get("property_id"),
            "url": metric.get("url"),
            "label": metric.get("title"),
        }
        for metric in metrics
    ]

    return {
        "headline": parsed.get("headline") or "Best value recommendation",
        "recommendation": parsed.get("recommendation") or "No recommendation generated.",
        "key_tradeoffs": parsed.get("key_tradeoffs") or [],
        "confidence": parsed.get("confidence") or "medium",
        "reasoning": parsed.get("reasoning")
        or f"Ranking mode '{ranking_mode}' was used to optimize winner selection.",
        "citations": citations,
    }
