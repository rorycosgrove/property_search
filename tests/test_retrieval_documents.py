from datetime import UTC, datetime
from types import SimpleNamespace

from packages.ai.retrieval_documents import (
    build_grant_match_documents,
    build_market_snapshot_document,
    build_property_history_documents,
    build_property_listing_document,
)


def _property() -> SimpleNamespace:
    return SimpleNamespace(
        id="prop-1",
        source_id="source-1",
        canonical_property_id="canon-1",
        county="Dublin",
        title="12 Main Street",
        address="12 Main Street, Dublin",
        price=450000,
        property_type="house",
        bedrooms=3,
        bathrooms=2,
        ber_rating="B2",
        status="active",
        url="https://example.com/property/1",
        description="Renovated family home",
        updated_at=datetime(2026, 3, 15, tzinfo=UTC),
        external_id="listing-1",
    )


def test_build_property_listing_document_includes_identity_and_summary():
    prop = _property()
    enrichment = SimpleNamespace(
        summary="Strong family home in a desirable area.",
        neighbourhood_notes="Near schools and parks.",
        pros=["renovated", "large garden"],
        cons=["busy road"],
    )
    document = build_property_listing_document(prop, enrichment)

    assert document["document_type"] == "listing_snapshot"
    assert document["document_key"] == "listing_snapshot:prop-1"
    assert document["canonical_property_id"] == "canon-1"
    assert "LLM summary" in document["content"]


def test_build_property_history_documents_emits_event_documents():
    prop = _property()
    history = [
        SimpleNamespace(
            price=450000,
            price_change=-10000,
            price_change_pct=-2.17,
            recorded_at=datetime(2026, 3, 1, tzinfo=UTC),
        )
    ]
    documents = build_property_history_documents(prop, history)

    assert len(documents) == 1
    assert documents[0]["document_type"] == "price_history_event"
    assert documents[0]["effective_at"] == history[0].recorded_at


def test_build_grant_match_documents_includes_grant_metadata():
    prop = _property()
    grant = SimpleNamespace(
        id="grant-1",
        code="SEAI-1",
        name="Home Energy Grant",
        country="IE",
        region="Dublin",
        description="Upgrade insulation and heat pump support",
        eligibility_rules={"min_ber": "C3"},
        max_amount=30000,
        valid_from=None,
        valid_to=None,
    )
    match = SimpleNamespace(
        status="eligible",
        estimated_benefit=25000,
        reason="BER and county checks passed",
        created_at=datetime(2026, 3, 15, tzinfo=UTC),
        grant_program=grant,
    )
    documents = build_grant_match_documents(prop, [match])

    assert len(documents) == 1
    assert documents[0]["document_type"] == "grant_match"
    assert documents[0]["metadata_json"]["grant_code"] == "SEAI-1"


def test_build_market_snapshot_document_captures_period_and_trends():
    summary = SimpleNamespace(
        avg_price=410000,
        median_price=395000,
        total_active_listings=1200,
        new_listings_24h=42,
        price_changes_24h=18,
        total_sold_ppr=30000,
    )
    trends = [SimpleNamespace(period="2026-02", avg_price=405000, count=120)]
    document = build_market_snapshot_document("Dublin", summary, trends, period="2026-03")

    assert document["document_type"] == "market_snapshot"
    assert document["document_key"] == "market_snapshot:dublin:2026-03"
    assert document["metadata_json"]["period"] == "2026-03"