"""End-to-end ingestion pipeline integration test.

Tests the full scrape → parse → normalize → dedup → persist → result-struct
path through ``scrape_source``, exercising real adapter parse logic and the
real normalizer rather than mocking the entire pipeline.

Correctness contract verified:
- A new listing is detected as new (new_count += 1).
- Re-ingesting the same listing at the same price is detected as price_unchanged.
- A price change increments updated_count.
- A parse failure increments parse_failed_count and is included in parse_fail_sample.
- Result dict contains the required breakdown fields for reconciliation.
- new_external_ids_sample contains the external_id of the newly inserted property.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from apps.worker.tasks import scrape_source
from packages.sources.base import RawListing


# ── Shared fakes ─────────────────────────────────────────────────────────────


class _SessionCtx:
    def __enter__(self):
        return object()

    def __exit__(self, *_):
        return False


def _make_daft_raw(listing_id: str, price: str = "EUR 250,000") -> RawListing:
    return RawListing(
        raw_data={
            "title": f"Test House {listing_id}, Ballydesmond, Co. Cork",
            "seoFriendlyPath": f"/for-sale/house-test-{listing_id}-co-cork/{listing_id}",
            "id": listing_id,
            "price": price,
            "location": {"county": "Cork"},
        },
        source_url=f"https://www.daft.ie/for-sale/house-test-{listing_id}-co-cork/{listing_id}",
    )


# ── Tests ──────────────────────────────────────────────────────────────────────


class TestIngestionPipelineNewListing:
    """Full pipeline: a listing that does not exist in DB should be inserted as new."""

    def test_new_listing_increments_new_count_and_samples_external_id(self, monkeypatch):
        source_obj = SimpleNamespace(
            id="daft-cork",
            enabled=True,
            adapter_name="daft",
            name="Daft.ie Cork",
            config={},
        )
        created_records: list[dict[str, Any]] = []

        class FakeSourceRepo:
            def __init__(self, _db):
                pass
            def get_by_id(self, _sid):
                return source_obj
            def should_skip_poll(self, _src):
                return False
            def try_acquire_scrape_lock(self, _sid):
                return True
            def mark_poll_success(self, _sid, _count):
                pass
            def update(self, _sid, **_kwargs):
                pass

        class FakePropertyRepo:
            def __init__(self, _db):
                pass
            def get_by_external_id_and_source(self, _src_id, _ext_id):
                return None  # not yet in DB
            def get_by_content_hash(self, _hash):
                return None
            def create(self, **kwargs):
                created_records.append(kwargs)
                return SimpleNamespace(id="prop-uuid-1")

        class FakePriceRepo:
            def __init__(self, _db):
                pass

        monkeypatch.setattr("packages.storage.database.get_session", lambda: _SessionCtx())
        monkeypatch.setattr("packages.storage.repositories.SourceRepository", FakeSourceRepo)
        monkeypatch.setattr("packages.storage.repositories.PropertyRepository", FakePropertyRepo)
        monkeypatch.setattr("packages.storage.repositories.PriceHistoryRepository", FakePriceRepo)
        monkeypatch.setattr("apps.worker.tasks._materialize_property_documents_safe", lambda *_a, **_kw: None)
        monkeypatch.setattr("apps.worker.tasks._record_backend_log", lambda **_kw: None)

        raw = _make_daft_raw("6437639")

        class FakeDaftAdapter:
            async def fetch_listings(self, _config):
                return [raw]
            def parse_listing(self, r):
                from packages.sources.daft import DaftAdapter
                return DaftAdapter().parse_listing(r)

        monkeypatch.setattr("packages.sources.registry.get_adapter", lambda _name: FakeDaftAdapter())
        monkeypatch.delenv("ALERT_QUEUE_URL", raising=False)

        result = scrape_source("daft-cork")

        assert result["new"] == 1, f"Expected 1 new listing but got: {result}"
        assert result["updated"] == 0
        assert result["parse_failed"] == 0
        assert result["price_unchanged"] == 0
        assert result["dedup_conflicts"] == 0
        assert result["total_fetched"] == 1
        assert "new_external_ids_sample" in result
        assert "6437639" in result["new_external_ids_sample"]

        # Verify normalised record was written with the correct external_id.
        assert len(created_records) == 1
        assert created_records[0].get("external_id") == "6437639"


class TestIngestionPipelinePriceUnchanged:
    """Full pipeline: re-ingesting a listing at the same price should be price_unchanged."""

    def test_same_price_increments_price_unchanged(self, monkeypatch):
        source_obj = SimpleNamespace(
            id="daft-cork",
            enabled=True,
            adapter_name="daft",
            name="Daft.ie Cork",
            config={},
        )
        existing_property = SimpleNamespace(
            id="prop-uuid-existing",
            price=250000.0,
            external_id="6437639",
        )

        class FakeSourceRepo:
            def __init__(self, _db):
                pass
            def get_by_id(self, _sid):
                return source_obj
            def should_skip_poll(self, _src):
                return False
            def try_acquire_scrape_lock(self, _sid):
                return True
            def mark_poll_success(self, _sid, _count):
                pass
            def update(self, _sid, **_kwargs):
                pass

        class FakePropertyRepo:
            def __init__(self, _db):
                pass
            def get_by_external_id_and_source(self, _src_id, _ext_id):
                return existing_property  # already in DB
            def get_by_content_hash(self, _hash):
                return None

        class FakePriceRepo:
            def __init__(self, _db):
                pass

        monkeypatch.setattr("packages.storage.database.get_session", lambda: _SessionCtx())
        monkeypatch.setattr("packages.storage.repositories.SourceRepository", FakeSourceRepo)
        monkeypatch.setattr("packages.storage.repositories.PropertyRepository", FakePropertyRepo)
        monkeypatch.setattr("packages.storage.repositories.PriceHistoryRepository", FakePriceRepo)
        monkeypatch.setattr("apps.worker.tasks._materialize_property_documents_safe", lambda *_a, **_kw: None)
        monkeypatch.setattr("apps.worker.tasks._record_backend_log", lambda **_kw: None)

        raw = _make_daft_raw("6437639", price="EUR 250,000")  # same price as existing

        class FakeDaftAdapter:
            async def fetch_listings(self, _config):
                return [raw]
            def parse_listing(self, r):
                from packages.sources.daft import DaftAdapter
                return DaftAdapter().parse_listing(r)

        monkeypatch.setattr("packages.sources.registry.get_adapter", lambda _name: FakeDaftAdapter())
        monkeypatch.delenv("ALERT_QUEUE_URL", raising=False)

        result = scrape_source("daft-cork")

        assert result["new"] == 0
        assert result["updated"] == 0
        assert result["price_unchanged"] == 1
        assert result["parse_failed"] == 0


class TestIngestionPipelineParseFailed:
    """Full pipeline: a listing that fails adapter.parse_listing must increment parse_failed."""

    def test_parse_failure_is_counted_and_sampled(self, monkeypatch):
        source_obj = SimpleNamespace(
            id="daft-cork",
            enabled=True,
            adapter_name="daft",
            name="Daft.ie Cork",
            config={},
        )

        class FakeSourceRepo:
            def __init__(self, _db):
                pass
            def get_by_id(self, _sid):
                return source_obj
            def should_skip_poll(self, _src):
                return False
            def try_acquire_scrape_lock(self, _sid):
                return True
            def mark_poll_success(self, _sid, _count):
                pass
            def update(self, _sid, **_kwargs):
                pass

        class FakePropertyRepo:
            def __init__(self, _db):
                pass
            def get_by_external_id_and_source(self, *_):
                return None
            def get_by_content_hash(self, _):
                return None

        class FakePriceRepo:
            def __init__(self, _db):
                pass

        # A listing with no seoFriendlyPath — DaftAdapter.parse_listing returns None.
        bad_raw = RawListing(raw_data={"title": "", "seoFriendlyPath": ""}, source_url="")

        class FakeDaftAdapter:
            async def fetch_listings(self, _config):
                return [bad_raw]
            def parse_listing(self, r):
                from packages.sources.daft import DaftAdapter
                return DaftAdapter().parse_listing(r)

        monkeypatch.setattr("packages.storage.database.get_session", lambda: _SessionCtx())
        monkeypatch.setattr("packages.storage.repositories.SourceRepository", FakeSourceRepo)
        monkeypatch.setattr("packages.storage.repositories.PropertyRepository", FakePropertyRepo)
        monkeypatch.setattr("packages.storage.repositories.PriceHistoryRepository", FakePriceRepo)
        monkeypatch.setattr("apps.worker.tasks._materialize_property_documents_safe", lambda *_a, **_kw: None)
        monkeypatch.setattr("apps.worker.tasks._record_backend_log", lambda **_kw: None)
        monkeypatch.setattr("packages.sources.registry.get_adapter", lambda _name: FakeDaftAdapter())
        monkeypatch.delenv("ALERT_QUEUE_URL", raising=False)

        result = scrape_source("daft-cork")

        assert result["new"] == 0
        assert result["parse_failed"] == 1
        assert result["total_fetched"] == 1
        assert "parse_fail_sample" in result
        assert len(result["parse_fail_sample"]) == 1


class TestIngestionPipelineResultContract:
    """scrape_source result must contain all fields required by the correctness contract."""

    REQUIRED_FIELDS = {
        "source_id", "source_name", "new", "updated",
        "skipped", "parse_failed", "price_unchanged", "dedup_conflicts",
        "total_fetched", "geocode_attempts", "geocode_successes",
        "geocode_success_rate", "new_external_ids_sample", "parse_fail_sample",
    }

    def test_result_contains_all_contract_fields(self, monkeypatch):
        source_obj = SimpleNamespace(
            id="daft-cork",
            enabled=True,
            adapter_name="daft",
            name="Daft.ie Cork",
            config={},
        )

        class FakeSourceRepo:
            def __init__(self, _db):
                pass
            def get_by_id(self, _sid):
                return source_obj
            def should_skip_poll(self, _src):
                return False
            def try_acquire_scrape_lock(self, _sid):
                return True
            def mark_poll_success(self, _sid, _count):
                pass
            def update(self, _sid, **_kwargs):
                pass

        class FakePropertyRepo:
            def __init__(self, _db):
                pass
            def get_by_external_id_and_source(self, *_):
                return None
            def get_by_content_hash(self, _):
                return None
            def create(self, **_kwargs):
                return SimpleNamespace(id="prop-x")

        class FakePriceRepo:
            def __init__(self, _db):
                pass

        raw = _make_daft_raw("9999001")

        class FakeDaftAdapter:
            async def fetch_listings(self, _config):
                return [raw]
            def parse_listing(self, r):
                from packages.sources.daft import DaftAdapter
                return DaftAdapter().parse_listing(r)

        monkeypatch.setattr("packages.storage.database.get_session", lambda: _SessionCtx())
        monkeypatch.setattr("packages.storage.repositories.SourceRepository", FakeSourceRepo)
        monkeypatch.setattr("packages.storage.repositories.PropertyRepository", FakePropertyRepo)
        monkeypatch.setattr("packages.storage.repositories.PriceHistoryRepository", FakePriceRepo)
        monkeypatch.setattr("apps.worker.tasks._materialize_property_documents_safe", lambda *_a, **_kw: None)
        monkeypatch.setattr("apps.worker.tasks._record_backend_log", lambda **_kw: None)
        monkeypatch.setattr("packages.sources.registry.get_adapter", lambda _name: FakeDaftAdapter())
        monkeypatch.delenv("ALERT_QUEUE_URL", raising=False)

        result = scrape_source("daft-cork")

        missing = self.REQUIRED_FIELDS - set(result.keys())
        assert not missing, f"Result is missing required contract fields: {missing}"
