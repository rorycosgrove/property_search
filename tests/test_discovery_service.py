"""Tests for Phase 3 discovery service and property brief generation."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from packages.properties.service import get_brief_payload, PropertyNotFoundError


# ── Helpers ────────────────────────────────────────────────────────────────

def _utcnow():
    return datetime.now(timezone.utc)


def _make_prop(*, price=350_000.0, bedrooms=3, county="Dublin", ber_rating="B2",
               latitude=53.3, longitude=-6.3, status="active", enrichment=None,
               created_at=None):
    prop = MagicMock()
    prop.id = "prop-1"
    prop.title = "3 Bed House, Dublin"
    prop.description = "A nice house"
    prop.url = "https://example.com/prop-1"
    prop.address = "1 Main St, Dublin"
    prop.county = county
    prop.eircode = "D01 A1B2"
    prop.price = price
    prop.price_text = f"€{price:,.0f}"
    prop.property_type = "house"
    prop.sale_type = "sale"
    prop.bedrooms = bedrooms
    prop.bathrooms = 2
    prop.floor_area_sqm = 110.0
    prop.ber_rating = ber_rating
    prop.ber_number = "12345678"
    prop.images = []
    prop.features = {}
    prop.raw_data = {}
    prop.latitude = latitude
    prop.longitude = longitude
    prop.status = status
    prop.source_id = "src-1"
    prop.external_id = "ext-1"
    prop.content_hash = "abc123"
    prop.first_listed_at = None
    prop.created_at = created_at or _utcnow() - timedelta(days=10)
    prop.updated_at = _utcnow()
    prop.last_updated_at = None
    prop.enrichment = enrichment
    prop.price_history = []
    return prop


def _make_property_repo(prop):
    repo = MagicMock()
    repo.get_by_id.return_value = prop
    return repo


def _make_price_history_repo(history=None):
    repo = MagicMock()

    class _Hist:
        def __init__(self, price, pct, recorded_at):
            self.id = "h1"
            self.price = price
            self.price_change = None
            self.price_change_pct = pct
            self.recorded_at = recorded_at

    repo.get_for_property.return_value = history or []
    return repo


def _make_timeline_repo(events=None):
    repo = MagicMock()
    repo.list_for_property.return_value = events or []
    return repo


def _make_document_repo(docs=None):
    repo = MagicMock()
    repo.list_for_property.return_value = docs or []
    return repo


# ── Brief generation ────────────────────────────────────────────────────────

class TestGetBriefPayload:
    def test_returns_brief_structure(self):
        prop = _make_prop()
        brief = get_brief_payload(
            property_repo=_make_property_repo(prop),
            price_history_repo=_make_price_history_repo(),
            timeline_repo=_make_timeline_repo(),
            document_repo=_make_document_repo(),
            property_id="prop-1",
        )
        assert brief["property_id"] == "prop-1"
        assert "generated_at" in brief
        assert "completeness_score" in brief
        assert "listing" in brief
        assert "ai_analysis" in brief
        assert "risk_flags" in brief
        assert "data_sources" in brief

    def test_raises_not_found_for_missing_property(self):
        repo = MagicMock()
        repo.get_by_id.return_value = None
        with pytest.raises(PropertyNotFoundError):
            get_brief_payload(
                property_repo=repo,
                price_history_repo=_make_price_history_repo(),
                timeline_repo=_make_timeline_repo(),
                document_repo=_make_document_repo(),
                property_id="missing",
            )

    def test_flags_missing_ber_rating(self):
        prop = _make_prop(ber_rating=None)
        brief = get_brief_payload(
            property_repo=_make_property_repo(prop),
            price_history_repo=_make_price_history_repo(),
            timeline_repo=_make_timeline_repo(),
            document_repo=_make_document_repo(),
            property_id="prop-1",
        )
        flags = brief["risk_flags"]
        assert any("BER" in f for f in flags)

    def test_flags_stale_listing(self):
        # Created 100 days ago
        old_date = _utcnow() - timedelta(days=100)
        prop = _make_prop(created_at=old_date)
        brief = get_brief_payload(
            property_repo=_make_property_repo(prop),
            price_history_repo=_make_price_history_repo(),
            timeline_repo=_make_timeline_repo(),
            document_repo=_make_document_repo(),
            property_id="prop-1",
        )
        assert any("days" in f for f in brief["risk_flags"])

    def test_includes_ai_analysis_when_enrichment_present(self):
        enr = MagicMock()
        enr.summary = "Great buy."
        enr.value_score = 8.5
        enr.value_reasoning = "Below market rate."
        enr.pros = ["Good location"]
        enr.cons = ["Small garden"]
        enr.neighbourhood_notes = "Quiet area"
        enr.investment_potential = "Strong rental demand"
        enr.llm_provider = "bedrock"
        enr.llm_model = "claude-3"
        enr.processed_at = _utcnow()
        enr.processing_time_ms = 1200
        enr.extracted_features = {}

        prop = _make_prop(enrichment=enr)
        brief = get_brief_payload(
            property_repo=_make_property_repo(prop),
            price_history_repo=_make_price_history_repo(),
            timeline_repo=_make_timeline_repo(),
            document_repo=_make_document_repo(),
            property_id="prop-1",
        )
        assert brief["ai_analysis"]["summary"] == "Great buy."
        assert brief["ai_analysis"]["value_score"] == 8.5
        assert brief["ai_analysis"]["pros"] == ["Good location"]

    def test_data_sources_counts_are_accurate(self):
        class _FakeDoc:
            document_key = "doc-1"
            document_type = "BER"
            title = "BER Cert"
            effective_at = None
            county = "Dublin"

        prop = _make_prop()
        brief = get_brief_payload(
            property_repo=_make_property_repo(prop),
            price_history_repo=_make_price_history_repo(),
            timeline_repo=_make_timeline_repo(),
            document_repo=_make_document_repo(docs=[_FakeDoc()]),
            property_id="prop-1",
        )
        assert brief["data_sources"]["rag_documents"] == 1


# ── Discovery signal helpers ────────────────────────────────────────────────

class TestDiscoverySignalHelpers:
    """Smoke tests that the discovery module is importable and callable via mocked DB."""

    def test_get_discovery_feed_returns_list(self):
        from packages.properties.discovery import get_discovery_feed

        db = MagicMock()
        # Each sub-query call to db.execute returns an empty result
        mock_result = MagicMock()
        mock_result.all.return_value = []
        mock_result.scalars.return_value.unique.return_value.all.return_value = []
        db.execute.return_value = mock_result

        result = get_discovery_feed(db, limit=10)
        assert isinstance(result, list)

    def test_base_card_includes_required_fields(self):
        from packages.properties.discovery import _base_card

        prop = _make_prop()
        card = _base_card("price_drop", "high", prop)
        for key in ("signal_type", "severity", "property_id", "title", "address", "county", "price", "url", "status", "created_at"):
            assert key in card, f"Missing key: {key}"

    def test_prop_image_returns_string_url(self):
        from packages.properties.discovery import _prop_image

        prop_with_str = _make_prop()
        prop_with_str.images = ["https://example.com/img.jpg"]
        assert _prop_image(prop_with_str) == "https://example.com/img.jpg"

        prop_with_dict = _make_prop()
        prop_with_dict.images = [{"url": "https://example.com/img2.jpg"}]
        assert _prop_image(prop_with_dict) == "https://example.com/img2.jpg"

        prop_empty = _make_prop()
        prop_empty.images = []
        assert _prop_image(prop_empty) is None
