from datetime import UTC, datetime
from types import SimpleNamespace

from packages.ai.retrieval_documents import (
    build_grant_program_documents,
    build_market_trend_documents,
    build_grant_match_documents,
    build_market_snapshot_document,
    build_property_history_documents,
    build_property_listing_document,
    materialize_property_documents,
    materialize_incentive_documents,
    materialize_market_documents,
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


def test_build_market_trend_documents_emits_historical_period_docs():
    trends = [
        SimpleNamespace(period="2026-01", avg_price=390000, count=95),
        SimpleNamespace(period="2026-02", avg_price=405000, count=120),
    ]

    documents = build_market_trend_documents("Dublin", trends)

    assert len(documents) == 2
    assert documents[0]["document_type"] == "market_trend_period"
    assert documents[0]["document_key"] == "market_trend:dublin:2026-01"
    assert documents[1]["metadata_json"]["count"] == 120


def test_build_grant_program_documents_emits_incentive_scope_docs():
    grant = SimpleNamespace(
        id="grant-101",
        code="RETROFIT-PLUS",
        name="Retrofit Plus",
        country="IE",
        region="Dublin",
        authority="SEAI",
        description="Retrofit support for heat and insulation",
        eligibility_rules={"min_ber": "C3"},
        benefit_type="grant",
        max_amount=45000,
        currency="EUR",
        active=True,
        valid_from=None,
        valid_to=None,
        source_url="https://example.gov.ie/grants/retrofit-plus",
    )

    documents = build_grant_program_documents([grant])

    assert len(documents) == 1
    assert documents[0]["document_type"] == "incentive_program"
    assert documents[0]["scope_type"] == "incentive_program"
    assert documents[0]["metadata_json"]["grant_code"] == "RETROFIT-PLUS"


def test_materialize_market_documents_upserts_snapshot_and_trends(monkeypatch):
    class FakeAnalyticsEngine:
        def __init__(self, _db):
            pass

        def get_summary(self):
            return SimpleNamespace(
                avg_price=410000,
                median_price=395000,
                total_active_listings=1200,
                new_listings_24h=42,
                price_changes_24h=18,
                total_sold_ppr=30000,
            )

        def get_county_stats(self):
            return []

        def get_price_trends(self, county=None, months=12):
            assert county == "Dublin"
            assert months == 12
            return [
                SimpleNamespace(period="2026-01", avg_price=390000, count=95),
                SimpleNamespace(period="2026-02", avg_price=405000, count=120),
            ]

    class FakePropertyDocumentRepository:
        def __init__(self, _db):
            self.calls = []

        def upsert_document(self, document_key, **kwargs):
            self.calls.append((document_key, kwargs))

    captured = {"repo": None}

    def _repo_factory(db):
        repo = FakePropertyDocumentRepository(db)
        captured["repo"] = repo
        return repo

    monkeypatch.setattr("packages.ai.retrieval_documents.AnalyticsEngine", FakeAnalyticsEngine)
    monkeypatch.setattr("packages.ai.retrieval_documents.PropertyDocumentRepository", _repo_factory)

    count = materialize_market_documents(object(), county="Dublin")

    assert count == 3
    keys = [k for k, _ in captured["repo"].calls]
    assert "market_snapshot:dublin:" in keys[0]
    assert "market_trend:dublin:2026-01" in keys
    assert "market_trend:dublin:2026-02" in keys


def test_materialize_incentive_documents_upserts_all_programs(monkeypatch):
    grant = SimpleNamespace(
        id="grant-101",
        code="RETROFIT-PLUS",
        name="Retrofit Plus",
        country="IE",
        region="Dublin",
        authority="SEAI",
        description="Retrofit support",
        eligibility_rules={"min_ber": "C3"},
        benefit_type="grant",
        max_amount=45000,
        currency="EUR",
        active=True,
        valid_from=None,
        valid_to=None,
        source_url="https://example.gov.ie/grants/retrofit-plus",
    )

    class FakeGrantProgramRepository:
        def __init__(self, _db):
            pass

        def list_programs(self, active_only=True):
            assert active_only is False
            return [grant]

    class FakePropertyDocumentRepository:
        def __init__(self, _db):
            self.calls = []

        def upsert_document(self, document_key, **kwargs):
            self.calls.append((document_key, kwargs))

    captured = {"repo": None}

    def _repo_factory(db):
        repo = FakePropertyDocumentRepository(db)
        captured["repo"] = repo
        return repo

    monkeypatch.setattr("packages.ai.retrieval_documents.GrantProgramRepository", FakeGrantProgramRepository)
    monkeypatch.setattr("packages.ai.retrieval_documents.PropertyDocumentRepository", _repo_factory)

    count = materialize_incentive_documents(object(), active_only=False)

    assert count == 1
    assert captured["repo"].calls[0][0] == "incentive_program:grant-101"


def test_materialize_property_documents_upserts_listing_history_and_grant_docs(monkeypatch):
    prop = _property()
    enrichment = SimpleNamespace(
        summary="Solid value opportunity.",
        neighbourhood_notes="Close to schools.",
        pros=["garden"],
        cons=["dated kitchen"],
    )
    price_history = [
        SimpleNamespace(
            price=440000,
            price_change=-10000,
            price_change_pct=-2.22,
            recorded_at=datetime(2026, 3, 10, tzinfo=UTC),
        )
    ]
    grant_program = SimpleNamespace(
        id="grant-1",
        code="SEAI-1",
        name="Home Energy Grant",
        country="IE",
        region="Dublin",
        description="Upgrade support",
        eligibility_rules={"min_ber": "C3"},
        max_amount=30000,
        valid_from=None,
        valid_to=None,
    )
    grant_matches = [
        SimpleNamespace(
            status="eligible",
            estimated_benefit=25000,
            reason="County and BER passed",
            created_at=datetime(2026, 3, 15, tzinfo=UTC),
            grant_program=grant_program,
        )
    ]

    class FakePropertyRepository:
        def __init__(self, _db):
            pass

        def get_by_id(self, property_id):
            assert property_id == "prop-1"
            return prop

    class FakePropertyDocumentRepository:
        def __init__(self, _db):
            self.calls = []

        def upsert_document(self, document_key, **kwargs):
            self.calls.append((document_key, kwargs))

    class FakePriceHistoryRepository:
        def __init__(self, _db):
            pass

        def list_for_property(self, property_id):
            assert property_id == "prop-1"
            return price_history

    class FakeGrantMatchRepository:
        def __init__(self, _db):
            pass

        def list_for_property(self, property_id):
            assert property_id == "prop-1"
            return grant_matches

    class FakeLLMEnrichmentRepository:
        def __init__(self, _db):
            pass

        def get_by_property_id(self, property_id):
            assert property_id == "prop-1"
            return enrichment

    captured = {"repo": None}

    def _doc_repo_factory(db):
        repo = FakePropertyDocumentRepository(db)
        captured["repo"] = repo
        return repo

    monkeypatch.setattr("packages.ai.retrieval_documents.PropertyRepository", FakePropertyRepository)
    monkeypatch.setattr("packages.ai.retrieval_documents.PropertyDocumentRepository", _doc_repo_factory)
    monkeypatch.setattr("packages.ai.retrieval_documents.PriceHistoryRepository", FakePriceHistoryRepository)
    monkeypatch.setattr("packages.ai.retrieval_documents.PropertyGrantMatchRepository", FakeGrantMatchRepository)
    monkeypatch.setattr("packages.ai.retrieval_documents.LLMEnrichmentRepository", FakeLLMEnrichmentRepository)

    count = materialize_property_documents(object(), "prop-1")

    assert count == 3
    keys = [key for key, _kwargs in captured["repo"].calls]
    assert "listing_snapshot:prop-1" in keys
    assert any(key.startswith("price_history_event:prop-1:") for key in keys)
    assert any(key.startswith("grant_match:prop-1:") for key in keys)