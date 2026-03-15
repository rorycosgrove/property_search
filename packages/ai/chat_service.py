from __future__ import annotations

from typing import Any, Callable

from fastapi import HTTPException
from sqlalchemy.orm import Session


def message_to_dict(message: Any) -> dict[str, Any]:
    return {
        "id": str(message.id),
        "conversation_id": str(message.conversation_id),
        "role": message.role,
        "content": message.content,
        "citations": message.citations or [],
        "prompt_tokens": message.prompt_tokens,
        "completion_tokens": message.completion_tokens,
        "total_tokens": message.total_tokens,
        "processing_time_ms": message.processing_time_ms,
        "created_at": message.created_at.isoformat() if message.created_at else None,
    }


def conversation_to_dict(conversation: Any) -> dict[str, Any]:
    messages = list(conversation.messages or [])
    messages.sort(key=lambda message: message.created_at)
    return {
        "id": str(conversation.id),
        "title": conversation.title,
        "user_identifier": conversation.user_identifier,
        "context": conversation.context or {},
        "created_at": conversation.created_at.isoformat() if conversation.created_at else None,
        "updated_at": conversation.updated_at.isoformat() if conversation.updated_at else None,
        "messages": [message_to_dict(message) for message in messages],
    }


def build_chat_prompt(
    *,
    user_content: str,
    property_context: dict[str, Any] | None,
    retrieval_context: dict[str, Any] | None,
) -> str:
    retrieval = retrieval_context or {}
    retrieval_lines = ""
    if retrieval:
        retrieval_lines = (
            "Current retrieval context:\n"
            f"- ranking_mode: {retrieval.get('ranking_mode')}\n"
            f"- shortlist_size: {retrieval.get('shortlist_size')}\n"
            f"- winner_property_id: {retrieval.get('winner_property_id')}\n"
            f"- winner_property_title: {retrieval.get('winner_property_title')}\n"
            "\n"
        )

    if not property_context:
        return f"{retrieval_lines}User question:\n{user_content}" if retrieval_lines else user_content

    grants = property_context.get("grants") or []
    grant_lines = ""
    if grants:
        formatted = []
        for grant in grants[:5]:
            name = grant.get("name") or grant.get("code") or "Unknown grant"
            status = grant.get("status") or "unknown"
            benefit = grant.get("estimated_benefit")
            benefit_text = f", est benefit {benefit}" if benefit is not None else ""
            formatted.append(f"- {name}: {status}{benefit_text}")
        grant_lines = "Potential grants:\n" + "\n".join(formatted) + "\n"

    return (
        f"{retrieval_lines}"
        "Context property:\n"
        f"- ID: {property_context.get('id')}\n"
        f"- Title: {property_context.get('title')}\n"
        f"- Address: {property_context.get('address')}\n"
        f"- County: {property_context.get('county')}\n"
        f"- Price: {property_context.get('price')}\n"
        f"- Type: {property_context.get('property_type')}\n"
        f"- Beds/Baths: {property_context.get('bedrooms')}/{property_context.get('bathrooms')}\n"
        f"- BER: {property_context.get('ber_rating')}\n"
        f"{grant_lines}"
        "\n"
        "User question:\n"
        f"{user_content}"
    )


def create_conversation_payload(
    *,
    db: Session,
    data: Any,
    conversation_repo_factory: Callable[[Session], Any],
) -> dict[str, Any]:
    repo = conversation_repo_factory(db)
    conversation = repo.create_conversation(
        user_identifier=data.user_identifier,
        title=data.title,
        context=data.context,
    )
    return conversation_to_dict(conversation)


def get_conversation_payload(
    *,
    db: Session,
    conversation_id: str,
    conversation_repo_factory: Callable[[Session], Any],
) -> dict[str, Any]:
    repo = conversation_repo_factory(db)
    conversation = repo.get_conversation(conversation_id)
    if not conversation:
        raise HTTPException(404, "Conversation not found")
    return conversation_to_dict(conversation)


async def send_message_payload(
    *,
    db: Session,
    conversation_id: str,
    data: Any,
    conversation_repo_factory: Callable[[Session], Any],
    property_repo_factory: Callable[[Session], Any],
    ensure_property_grants_fn: Callable[[Session, Any], list[Any]],
    serialize_grant_citations_fn: Callable[[list[Any]], list[dict[str, Any]]],
    provider_getter: Callable[[], Any],
) -> dict[str, Any]:
    convo_repo = conversation_repo_factory(db)
    property_repo = property_repo_factory(db)

    conversation = convo_repo.get_conversation(conversation_id)
    if not conversation:
        raise HTTPException(404, "Conversation not found")

    user_message = convo_repo.add_message(
        conversation_id=conversation_id,
        role="user",
        content=data.content,
    )

    property_context = None
    request_context = dict(data.retrieval_context or {})
    grant_matches: list[Any] = []

    if data.property_id:
        prop = property_repo.get_by_id(data.property_id)
        if prop:
            grant_matches = ensure_property_grants_fn(db, prop)
            property_context = {
                "id": str(prop.id),
                "title": prop.title,
                "address": prop.address,
                "county": prop.county,
                "price": float(prop.price) if prop.price is not None else None,
                "property_type": prop.property_type,
                "bedrooms": prop.bedrooms,
                "bathrooms": prop.bathrooms,
                "ber_rating": prop.ber_rating,
                "url": prop.url,
                "grants": [
                    {
                        "code": match.grant_program.code if match.grant_program else None,
                        "name": match.grant_program.name if match.grant_program else None,
                        "status": match.status,
                        "estimated_benefit": float(match.estimated_benefit)
                        if match.estimated_benefit is not None
                        else None,
                    }
                    for match in grant_matches
                ],
            }
            request_context.update(
                {
                    "selected_property_id": str(prop.id),
                    "selected_property_title": prop.title,
                    "grant_count": len(grant_matches),
                    "grants_considered": [
                        {
                            "code": match.grant_program.code if match.grant_program else None,
                            "status": match.status,
                            "estimated_benefit": float(match.estimated_benefit)
                            if match.estimated_benefit is not None
                            else None,
                        }
                        for match in grant_matches[:5]
                    ],
                }
            )

    provider = provider_getter()
    prompt = build_chat_prompt(
        user_content=data.content,
        property_context=property_context,
        retrieval_context=request_context,
    )
    response = await provider.generate(
        prompt=prompt,
        system_prompt=(
            "You are Property Copilot for Ireland and UK/NI housing markets. "
            "Answer with clear recommendations, and when facts are property-specific "
            "or scheme-specific, include concise citation hints."
        ),
        temperature=0.3,
        max_tokens=1200,
    )

    citations: list[dict[str, Any]] = []
    if property_context:
        citations.append(
            {
                "type": "property",
                "property_id": property_context["id"],
                "url": property_context.get("url"),
                "label": property_context.get("title"),
            }
        )
        citations.extend(serialize_grant_citations_fn(grant_matches))

    assistant_message = convo_repo.add_message(
        conversation_id=conversation_id,
        role="assistant",
        content=response.content,
        citations=citations,
        prompt_tokens=response.prompt_tokens,
        completion_tokens=response.completion_tokens,
        total_tokens=response.total_tokens,
        processing_time_ms=response.processing_time_ms,
    )

    return {
        "conversation_id": conversation_id,
        "user_message": message_to_dict(user_message),
        "assistant_message": message_to_dict(assistant_message),
        "retrieval_context": request_context,
    }
