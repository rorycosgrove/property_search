"""Hybrid retrieval service for property-grounded AI context.

Provides lexical keyword retrieval over the ``PropertyDocument`` corpus with
freshness-weighted ranking.  The goal is to surface the most relevant stored
evidence (listing snapshots, price history, market trends, grants) to provide
to the LLM as grounding context.

Usage::

    from packages.ai.retrieval_service import retrieve_context

    chunks = retrieve_context(
        session=db,
        query="3-bed semi detached Galway grant support",
        property_id="<uuid>",
        county="Galway",
        limit=10,
    )
    context_text = "\\n\\n".join(c["content_snippet"] for c in chunks)
"""

from __future__ import annotations

import math
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from packages.storage.repositories import PropertyDocumentRepository

# Document-type relevance weighting (higher = surface first when scores tie)
_DOC_TYPE_PRIORITY: dict[str, int] = {
    "listing_snapshot": 10,
    "grant_match": 9,
    "incentive_program": 8,
    "price_history_event": 7,
    "market_snapshot": 6,
    "market_trend_period": 5,
}

# Maximum age (days) after which freshness score floors out
_FRESHNESS_HALF_LIFE_DAYS = 60


def _freshness_score(effective_at: datetime | None) -> float:
    """Exponential decay freshness score in [0, 1].

    Returns 1.0 for documents with no date (assume always fresh) or very
    recent documents, decaying toward ~0.13 at 3 × half-life.
    """
    if effective_at is None:
        return 0.5  # unknown age — middle-of-the-road
    now = datetime.now(UTC)
    eff = effective_at if effective_at.tzinfo else effective_at.replace(tzinfo=UTC)
    age_days = max((now - eff).total_seconds() / 86400, 0)
    return math.exp(-age_days / _FRESHNESS_HALF_LIFE_DAYS)


def _keyword_density(text: str, terms: list[str]) -> float:
    """Fraction of query terms that appear in text (case-insensitive)."""
    if not terms or not text:
        return 0.0
    lower = text.lower()
    hits = sum(1 for t in terms if t.lower() in lower)
    return hits / len(terms)


def _score_document(doc: Any, terms: list[str]) -> float:
    """Combined relevance + freshness score for ranking retrieved documents."""
    content = doc.content or ""
    title = doc.title or ""
    combined_text = f"{title} {content}"

    kw_density = _keyword_density(combined_text, terms)
    type_priority = _DOC_TYPE_PRIORITY.get(doc.document_type, 4) / 10  # normalise to [0,1]
    freshness = _freshness_score(doc.effective_at)

    # Weights: keyword match dominates, supported by type priority and freshness
    return (kw_density * 0.55) + (type_priority * 0.25) + (freshness * 0.20)


def _snippet(content: str, max_chars: int = 600) -> str:
    """Trim content to a reasonable snippet for prompt injection."""
    if len(content) <= max_chars:
        return content
    return content[:max_chars].rsplit(" ", 1)[0] + "…"


def retrieve_context(
    session: Session,
    query: str,
    *,
    property_id: str | None = None,
    county: str | None = None,
    doc_types: list[str] | None = None,
    limit: int = 10,
    min_score: float = 0.05,
) -> list[dict[str, Any]]:
    """Retrieve and rank document chunks relevant to *query*.

    Parameters
    ----------
    session:
        Active SQLAlchemy ``Session``.
    query:
        Free-text query (e.g. user's chat message or property description).
    property_id:
        If set, restrict retrieval to documents for this property.
    county:
        If set, restrict broad (non-property) retrieval to this county.
    doc_types:
        Optional allowlist of document types.  ``None`` = all types.
    limit:
        Maximum number of chunks to return after re-ranking.
    min_score:
        Minimum combined score threshold; very low-quality matches are dropped.

    Returns
    -------
    list of dicts with keys:
        ``document_key``, ``document_type``, ``title``, ``content_snippet``,
        ``relevance_score``, ``freshness_score``, ``property_id``, ``county``,
        ``effective_at``, ``metadata``.
    """
    # Tokenise query into individual terms (simple whitespace split)
    terms = [t for t in query.split() if len(t) >= 3]

    repo = PropertyDocumentRepository(session)

    # Pull a wider candidate set from DB (2× limit) and then re-rank in memory
    candidates = repo.search_documents(
        terms,
        county=county,
        property_id=property_id,
        doc_types=doc_types,
        limit=limit * 2,
    )

    scored: list[tuple[float, Any]] = []
    for doc in candidates:
        score = _score_document(doc, terms)
        if score >= min_score:
            scored.append((score, doc))

    scored.sort(key=lambda x: x[0], reverse=True)

    results: list[dict[str, Any]] = []
    for score, doc in scored[:limit]:
        results.append(
            {
                "document_key": doc.document_key,
                "document_type": doc.document_type,
                "title": doc.title or doc.document_type,
                "content_snippet": _snippet(doc.content),
                "relevance_score": round(score, 4),
                "freshness_score": round(_freshness_score(doc.effective_at), 4),
                "property_id": doc.property_id,
                "county": doc.county,
                "effective_at": doc.effective_at.isoformat() if doc.effective_at else None,
                "metadata": doc.metadata_json or {},
            }
        )

    return results


def format_context_for_prompt(chunks: list[dict[str, Any]]) -> str:
    """Convert retrieved chunks into a compact, LLM-friendly context block."""
    if not chunks:
        return ""

    lines: list[str] = ["=== RETRIEVED EVIDENCE ==="]
    for i, chunk in enumerate(chunks, 1):
        date_str = f" ({chunk['effective_at'][:10]})" if chunk["effective_at"] else ""
        lines.append(f"\n[{i}] {chunk['title']}{date_str}")
        lines.append(chunk["content_snippet"])

    lines.append("\n=== END EVIDENCE ===")
    return "\n".join(lines)
