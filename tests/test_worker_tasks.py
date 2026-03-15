"""Tests for worker task local fallback behavior."""

from types import SimpleNamespace

import pytest

from apps.worker.tasks import (
    discover_all_sources,
    evaluate_alerts,
    enrich_batch_llm,
    enrich_property_llm,
    scrape_all_sources,
    scrape_source,
)


class _SessionCtx:
    """Simple context manager used to stub get_session()."""

    def __enter__(self):
        return object()

    def __exit__(self, exc_type, exc, tb):
        return False


def test_scrape_all_sources_falls_back_inline_when_scrape_queue_missing(monkeypatch):
    """When SCRAPE_QUEUE_URL is absent, sources should be processed inline."""
    monkeypatch.delenv("SCRAPE_QUEUE_URL", raising=False)

    fake_sources = [
        SimpleNamespace(id="source-1", enabled=True, tags=[], error_count=0),
        SimpleNamespace(id="source-2", enabled=True, tags=[], error_count=0),
    ]

    class FakeSourceRepository:
        def __init__(self, _db):
            pass

        def get_all(self, enabled_only=True):
            assert enabled_only is False
            return fake_sources

    send_calls: list[tuple[tuple, dict]] = []
    inline_calls: list[str] = []

    monkeypatch.setattr("packages.storage.database.get_session", lambda: _SessionCtx())
    monkeypatch.setattr("packages.storage.repositories.SourceRepository", FakeSourceRepository)
    monkeypatch.setattr(
        "apps.worker.tasks.discover_sources",
        lambda **_kwargs: {
            "created": 1,
            "existing": 0,
            "skipped_invalid": 0,
            "auto_enable": False,
        },
    )
    monkeypatch.setattr(
        "packages.shared.queue.send_task",
        lambda *args, **kwargs: send_calls.append((args, kwargs)),
    )
    monkeypatch.setattr(
        "apps.worker.tasks.scrape_source",
        lambda source_id: inline_calls.append(source_id) or {"source_id": source_id},
    )

    result = scrape_all_sources()

    assert result == {
        "dispatched": 2,
        "processed_inline": 2,
        "dispatch_mode": "inline",
        "discovery_during_scrape": {
            "created": 1,
            "existing": 0,
            "skipped_invalid": 0,
            "auto_enable": False,
            "enabled": True,
            "limit": 10,
        },
        "source_summary": {
            "total": 2,
            "enabled": 2,
            "pending_approval": 0,
            "disabled_by_errors": 0,
        },
    }
    assert inline_calls == ["source-1", "source-2"]
    assert send_calls == []


def test_scrape_all_sources_uses_sqs_dispatch_when_queue_configured(monkeypatch):
    """When SCRAPE_QUEUE_URL is present, tasks should be dispatched via SQS."""
    monkeypatch.setenv("SCRAPE_QUEUE_URL", "https://example.com/sqs/scrape")

    fake_sources = [
        SimpleNamespace(id="source-1", enabled=True, tags=[], error_count=0),
        SimpleNamespace(id="source-2", enabled=True, tags=[], error_count=0),
    ]

    class FakeSourceRepository:
        def __init__(self, _db):
            pass

        def get_all(self, enabled_only=True):
            assert enabled_only is False
            return fake_sources

    send_calls: list[tuple[tuple, dict]] = []
    inline_calls: list[str] = []

    monkeypatch.setattr("packages.storage.database.get_session", lambda: _SessionCtx())
    monkeypatch.setattr("packages.storage.repositories.SourceRepository", FakeSourceRepository)
    monkeypatch.setattr(
        "apps.worker.tasks.discover_sources",
        lambda **_kwargs: {
            "created": 0,
            "existing": 2,
            "skipped_invalid": 0,
            "auto_enable": False,
        },
    )
    monkeypatch.setattr(
        "packages.shared.queue.send_task",
        lambda *args, **kwargs: send_calls.append((args, kwargs)) or "msg-id",
    )
    monkeypatch.setattr(
        "apps.worker.tasks.scrape_source",
        lambda source_id: inline_calls.append(source_id) or {"source_id": source_id},
    )

    result = scrape_all_sources()

    assert result == {
        "dispatched": 2,
        "processed_inline": 0,
        "dispatch_mode": "sqs",
        "discovery_during_scrape": {
            "created": 0,
            "existing": 2,
            "skipped_invalid": 0,
            "auto_enable": False,
            "enabled": True,
            "limit": 10,
        },
        "source_summary": {
            "total": 2,
            "enabled": 2,
            "pending_approval": 0,
            "disabled_by_errors": 0,
        },
    }
    assert inline_calls == []
    assert len(send_calls) == 2
    assert send_calls[0][0] == ("scrape", "scrape_source", {"source_id": "source-1"})
    assert send_calls[1][0] == ("scrape", "scrape_source", {"source_id": "source-2"})


def test_scrape_source_skips_alert_enqueue_when_alert_queue_missing(monkeypatch):
    """A successful scrape should not fail locally when ALERT_QUEUE_URL is absent."""
    monkeypatch.delenv("ALERT_QUEUE_URL", raising=False)

    source_obj = SimpleNamespace(
        id="myhome-source-id",
        enabled=True,
        adapter_name="myhome",
        name="MyHome.ie",
        config={},
    )

    class FakeSourceRepository:
        def __init__(self, _db):
            self.mark_poll_success_called = False

        def get_by_id(self, source_id):
            assert source_id == "myhome-source-id"
            return source_obj

        def mark_poll_success(self, source_id, processed_count):
            assert source_id == "myhome-source-id"
            assert processed_count == 1
            self.mark_poll_success_called = True

        def mark_poll_error(self, source_id, _error):
            raise AssertionError(f"mark_poll_error should not be called for {source_id}")

        def should_skip_poll(self, _source):
            return False

        def try_acquire_scrape_lock(self, _source_id):
            return True

    class FakePropertyRepository:
        def __init__(self, _db):
            pass

        def get_by_content_hash(self, _content_hash):
            return None

        def create(self, **_kwargs):
            return None

    class FakePriceHistoryRepository:
        def __init__(self, _db):
            pass

    class FakeNormalizer:
        def normalize(self, _parsed):
            return {
                "content_hash": "hash-1",
                "address": "1 Main Street",
                "county": "Dublin",
                "latitude": 53.0,
                "longitude": -6.0,
                "price": 100000.0,
                "raw_data": {},
            }

    class FakeAdapter:
        async def fetch_listings(self, _config):
            return [SimpleNamespace(raw_data={}, source_url="https://example.com/1")]

        def parse_listing(self, _raw):
            return SimpleNamespace(raw_data={})

    send_calls: list[tuple[tuple, dict]] = []

    monkeypatch.setattr("packages.storage.database.get_session", lambda: _SessionCtx())
    monkeypatch.setattr("packages.storage.repositories.SourceRepository", FakeSourceRepository)
    monkeypatch.setattr("packages.storage.repositories.PropertyRepository", FakePropertyRepository)
    monkeypatch.setattr(
        "packages.storage.repositories.PriceHistoryRepository",
        FakePriceHistoryRepository,
    )
    monkeypatch.setattr("packages.normalizer.normalizer.PropertyNormalizer", FakeNormalizer)
    monkeypatch.setattr("packages.sources.registry.get_adapter", lambda _name: FakeAdapter())
    monkeypatch.setattr(
        "packages.shared.queue.send_task",
        lambda *args, **kwargs: send_calls.append((args, kwargs)) or "msg-id",
    )

    result = scrape_source("myhome-source-id")

    assert result["source_id"] == "myhome-source-id"
    assert result["new"] == 1
    assert result["updated"] == 0
    assert result["total_fetched"] == 1
    assert send_calls == []


def test_scrape_source_skips_when_poll_interval_not_elapsed(monkeypatch):
    """Scrape should short-circuit when source poll interval has not elapsed."""
    source_obj = SimpleNamespace(
        id="myhome-source-id",
        enabled=True,
        adapter_name="myhome",
        name="MyHome.ie",
        config={},
        poll_interval_seconds=900,
    )

    class FakeSourceRepository:
        def __init__(self, _db):
            pass

        def get_by_id(self, source_id):
            assert source_id == "myhome-source-id"
            return source_obj

        def should_skip_poll(self, _source):
            return True

        def try_acquire_scrape_lock(self, _source_id):
            raise AssertionError("Lock should not be attempted when poll interval skips")

    class FakePropertyRepository:
        def __init__(self, _db):
            raise AssertionError("Property repository should not be touched when skipping")

    class FakePriceHistoryRepository:
        def __init__(self, _db):
            raise AssertionError("Price history repository should not be touched when skipping")

    monkeypatch.setattr("packages.storage.database.get_session", lambda: _SessionCtx())
    monkeypatch.setattr("packages.storage.repositories.SourceRepository", FakeSourceRepository)
    monkeypatch.setattr("packages.storage.repositories.PropertyRepository", FakePropertyRepository)
    monkeypatch.setattr(
        "packages.storage.repositories.PriceHistoryRepository",
        FakePriceHistoryRepository,
    )

    result = scrape_source("myhome-source-id")

    assert result["source_id"] == "myhome-source-id"
    assert result["skipped"] is True
    assert result["reason"] == "poll_interval_not_elapsed"


def test_scrape_source_skips_when_source_lock_not_acquired(monkeypatch):
    """Scrape should short-circuit when another scrape is already in flight."""
    source_obj = SimpleNamespace(
        id="myhome-source-id",
        enabled=True,
        adapter_name="myhome",
        name="MyHome.ie",
        config={},
        poll_interval_seconds=900,
    )

    class FakeSourceRepository:
        def __init__(self, _db):
            pass

        def get_by_id(self, source_id):
            assert source_id == "myhome-source-id"
            return source_obj

        def should_skip_poll(self, _source):
            return False

        def try_acquire_scrape_lock(self, _source_id):
            return False

    class FakePropertyRepository:
        def __init__(self, _db):
            raise AssertionError("Property repository should not be touched when lock is unavailable")

    class FakePriceHistoryRepository:
        def __init__(self, _db):
            raise AssertionError("Price history repository should not be touched when lock is unavailable")

    monkeypatch.setattr("packages.storage.database.get_session", lambda: _SessionCtx())
    monkeypatch.setattr("packages.storage.repositories.SourceRepository", FakeSourceRepository)
    monkeypatch.setattr("packages.storage.repositories.PropertyRepository", FakePropertyRepository)
    monkeypatch.setattr(
        "packages.storage.repositories.PriceHistoryRepository",
        FakePriceHistoryRepository,
    )

    result = scrape_source("myhome-source-id")

    assert result["source_id"] == "myhome-source-id"
    assert result["skipped"] is True
    assert result["reason"] == "source_in_flight"


def test_scrape_all_sources_discovers_but_only_scrapes_enabled_snapshot(monkeypatch):
    """Discovery during scrape should report created sources while scraping enabled set."""
    monkeypatch.setenv("SCRAPE_QUEUE_URL", "https://example.com/sqs/scrape")

    # Source snapshot from DB remains enabled-only list for this cycle.
    fake_sources = [SimpleNamespace(id="enabled-source-1", enabled=True, tags=[], error_count=0)]

    class FakeSourceRepository:
        def __init__(self, _db):
            pass

        def get_all(self, enabled_only=True):
            assert enabled_only is False
            return fake_sources

    send_calls: list[tuple[tuple, dict]] = []

    monkeypatch.setattr("packages.storage.database.get_session", lambda: _SessionCtx())
    monkeypatch.setattr("packages.storage.repositories.SourceRepository", FakeSourceRepository)
    monkeypatch.setattr(
        "apps.worker.tasks.discover_sources",
        lambda **_kwargs: {
            "created": 1,
            "existing": 0,
            "skipped_invalid": 0,
            "auto_enable": False,
        },
    )
    monkeypatch.setattr(
        "packages.shared.queue.send_task",
        lambda *args, **kwargs: send_calls.append((args, kwargs)) or "msg-id",
    )

    result = scrape_all_sources()

    assert result["dispatched"] == 1
    assert result["dispatch_mode"] == "sqs"
    assert result["discovery_during_scrape"]["created"] == 1
    assert result["source_summary"]["enabled"] == 1
    assert send_calls == [(("scrape", "scrape_source", {"source_id": "enabled-source-1"}), {})]


def test_scrape_all_sources_can_disable_discovery_via_env(monkeypatch):
    """Discovery hook can be disabled and scrape dispatch should still run."""
    monkeypatch.setenv("SCRAPE_QUEUE_URL", "https://example.com/sqs/scrape")
    monkeypatch.setenv("DISCOVERY_DURING_SCRAPE_ENABLED", "false")

    fake_sources = [SimpleNamespace(id="source-1", enabled=True, tags=[], error_count=0)]

    class FakeSourceRepository:
        def __init__(self, _db):
            pass

        def get_all(self, enabled_only=True):
            assert enabled_only is False
            return fake_sources

    send_calls: list[tuple[tuple, dict]] = []
    discover_calls: list[dict] = []

    monkeypatch.setattr("packages.storage.database.get_session", lambda: _SessionCtx())
    monkeypatch.setattr("packages.storage.repositories.SourceRepository", FakeSourceRepository)
    monkeypatch.setattr(
        "apps.worker.tasks.discover_sources",
        lambda **kwargs: discover_calls.append(kwargs) or {
            "created": 999,
            "existing": 0,
            "skipped_invalid": 0,
            "auto_enable": False,
        },
    )
    monkeypatch.setattr(
        "packages.shared.queue.send_task",
        lambda *args, **kwargs: send_calls.append((args, kwargs)) or "msg-id",
    )

    result = scrape_all_sources()

    assert discover_calls == []
    assert result["dispatched"] == 1
    assert result["dispatch_mode"] == "sqs"
    assert result["discovery_during_scrape"]["enabled"] is False
    assert result["discovery_during_scrape"]["created"] == 0
    assert result["source_summary"]["enabled"] == 1
    assert send_calls == [(("scrape", "scrape_source", {"source_id": "source-1"}), {})]


def test_scrape_all_sources_continues_when_discovery_fails(monkeypatch):
    """Discovery failure should be non-fatal and scraping should continue."""
    monkeypatch.setenv("SCRAPE_QUEUE_URL", "https://example.com/sqs/scrape")

    fake_sources = [
        SimpleNamespace(id="source-1", enabled=True, tags=[], error_count=0),
        SimpleNamespace(id="source-2", enabled=True, tags=[], error_count=0),
    ]

    class FakeSourceRepository:
        def __init__(self, _db):
            pass

        def get_all(self, enabled_only=True):
            assert enabled_only is False
            return fake_sources

    send_calls: list[tuple[tuple, dict]] = []

    monkeypatch.setattr("packages.storage.database.get_session", lambda: _SessionCtx())
    monkeypatch.setattr("packages.storage.repositories.SourceRepository", FakeSourceRepository)
    monkeypatch.setattr(
        "apps.worker.tasks.discover_sources",
        lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("discovery exploded")),
    )
    monkeypatch.setattr(
        "packages.shared.queue.send_task",
        lambda *args, **kwargs: send_calls.append((args, kwargs)) or "msg-id",
    )

    result = scrape_all_sources()

    assert result["dispatched"] == 2
    assert result["dispatch_mode"] == "sqs"
    assert result["discovery_during_scrape"]["enabled"] is True
    assert result["discovery_during_scrape"]["auto_enable"] is False
    assert result["discovery_during_scrape"]["error"] == "discovery exploded"
    assert result["source_summary"]["enabled"] == 2
    assert send_calls == [
        (("scrape", "scrape_source", {"source_id": "source-1"}), {}),
        (("scrape", "scrape_source", {"source_id": "source-2"}), {}),
    ]


def test_evaluate_alerts_records_backend_log(monkeypatch):
    class FakeSession:
        def __init__(self):
            self.committed = False

        def commit(self):
            self.committed = True

    class FakeSessionCtx:
        def __init__(self):
            self.db = FakeSession()

        def __enter__(self):
            return self.db

        def __exit__(self, exc_type, exc, tb):
            return False

    class FakeAlertEngine:
        def __init__(self, _db):
            pass

        def evaluate_all(self):
            return 2

        def check_price_changes(self):
            return 1

    events: list[dict] = []

    monkeypatch.setattr("packages.storage.database.get_session", lambda: FakeSessionCtx())
    monkeypatch.setattr("packages.alerts.engine.AlertEngine", FakeAlertEngine)
    monkeypatch.setattr("apps.worker.tasks._record_backend_log", lambda **kwargs: events.append(kwargs))

    result = evaluate_alerts()

    assert result == {"search_alerts": 2, "price_alerts": 1}
    assert len(events) == 1
    assert events[0]["event_type"] == "alert_evaluation_complete"
    assert events[0]["context"]["search_alerts"] == 2
    assert events[0]["context"]["price_alerts"] == 1


def test_enrich_property_llm_records_success_backend_log(monkeypatch):
    class FakeSession:
        def commit(self):
            return None

    class FakeSessionCtx:
        def __enter__(self):
            return FakeSession()

        def __exit__(self, exc_type, exc, tb):
            return False

    prop = SimpleNamespace(
        id="prop-1",
        title="Test Home",
        address="1 Main St",
        county="Dublin",
        price=350000.0,
        property_type="house",
        bedrooms=3,
        bathrooms=2,
        floor_area_sqm=95,
        ber_rating="B2",
        description="Nice",
        latitude=53.3,
        longitude=-6.2,
    )

    class FakePropertyRepo:
        def __init__(self, _db):
            pass

        def get_by_id(self, _property_id):
            return prop

    class FakeSoldRepo:
        def __init__(self, _db):
            pass

        def get_nearby_sold(self, **_kwargs):
            return [SimpleNamespace(address="Sold A", price=300000, sale_date=None)]

    class FakeEnrichmentRepo:
        def __init__(self, _db):
            self.upsert_calls = []

        def upsert(self, property_id, payload):
            self.upsert_calls.append((property_id, payload))

    events: list[dict] = []

    monkeypatch.setattr("packages.storage.database.get_session", lambda: FakeSessionCtx())
    monkeypatch.setattr("packages.storage.repositories.PropertyRepository", FakePropertyRepo)
    monkeypatch.setattr("packages.storage.repositories.SoldPropertyRepository", FakeSoldRepo)
    monkeypatch.setattr("packages.storage.repositories.LLMEnrichmentRepository", FakeEnrichmentRepo)
    def _fake_run_async_success(coro):
        coro.close()
        return {"summary": "ok"}

    monkeypatch.setattr("apps.worker.tasks._run_async", _fake_run_async_success)
    monkeypatch.setattr("apps.worker.tasks._record_backend_log", lambda **kwargs: events.append(kwargs))
    monkeypatch.setattr("apps.worker.tasks.settings.llm_enabled", True)

    result = enrich_property_llm("prop-1")

    assert result == {"property_id": "prop-1", "enriched": True}
    assert any(e["event_type"] == "llm_enrichment_complete" for e in events)


def test_enrich_property_llm_records_failure_backend_log(monkeypatch):
    class FakeSession:
        def commit(self):
            return None

    class FakeSessionCtx:
        def __enter__(self):
            return FakeSession()

        def __exit__(self, exc_type, exc, tb):
            return False

    prop = SimpleNamespace(
        id="prop-1",
        title="Test Home",
        address="1 Main St",
        county="Dublin",
        price=350000.0,
        property_type="house",
        bedrooms=3,
        bathrooms=2,
        floor_area_sqm=95,
        ber_rating="B2",
        description="Nice",
        latitude=None,
        longitude=None,
    )

    class FakePropertyRepo:
        def __init__(self, _db):
            pass

        def get_by_id(self, _property_id):
            return prop

    class FakeSoldRepo:
        def __init__(self, _db):
            pass

    class FakeEnrichmentRepo:
        def __init__(self, _db):
            pass

        def upsert(self, _property_id, _payload):
            return None

    events: list[dict] = []

    monkeypatch.setattr("packages.storage.database.get_session", lambda: FakeSessionCtx())
    monkeypatch.setattr("packages.storage.repositories.PropertyRepository", FakePropertyRepo)
    monkeypatch.setattr("packages.storage.repositories.SoldPropertyRepository", FakeSoldRepo)
    monkeypatch.setattr("packages.storage.repositories.LLMEnrichmentRepository", FakeEnrichmentRepo)
    def _fake_run_async_fail(coro):
        coro.close()
        raise RuntimeError("llm failed")

    monkeypatch.setattr("apps.worker.tasks._run_async", _fake_run_async_fail)
    monkeypatch.setattr("apps.worker.tasks._record_backend_log", lambda **kwargs: events.append(kwargs))
    monkeypatch.setattr("apps.worker.tasks.settings.llm_enabled", True)

    with pytest.raises(RuntimeError, match="llm failed"):
        enrich_property_llm("prop-1")

    assert any(e["event_type"] == "llm_enrichment_failed" for e in events)


def test_enrich_batch_llm_records_skip_backend_log_when_queue_unconfigured(monkeypatch):
    events: list[dict] = []

    monkeypatch.setattr("apps.worker.tasks.settings.llm_enabled", True)
    monkeypatch.setattr("apps.worker.tasks._is_queue_configured", lambda _queue_name: False)
    monkeypatch.setattr("apps.worker.tasks._record_backend_log", lambda **kwargs: events.append(kwargs))

    result = enrich_batch_llm(limit=11)

    assert result == {"dispatched": 0, "reason": "llm_queue_unconfigured"}
    assert len(events) == 1
    assert events[0]["event_type"] == "llm_batch_skipped"
    assert events[0]["context"]["reason"] == "llm_queue_unconfigured"


def test_enrich_property_llm_records_skip_backend_log_when_disabled(monkeypatch):
    events: list[dict] = []

    monkeypatch.setattr("apps.worker.tasks.settings.llm_enabled", False)
    monkeypatch.setattr("apps.worker.tasks._record_backend_log", lambda **kwargs: events.append(kwargs))

    result = enrich_property_llm("prop-disabled")

    assert result == {
        "property_id": "prop-disabled",
        "enriched": False,
        "reason": "llm_disabled",
    }
    assert len(events) == 1
    assert events[0]["event_type"] == "llm_enrichment_skipped"


def test_enrich_property_llm_records_property_not_found_backend_log(monkeypatch):
    class FakeSession:
        def commit(self):
            return None

    class FakeSessionCtx:
        def __enter__(self):
            return FakeSession()

        def __exit__(self, exc_type, exc, tb):
            return False

    class FakePropertyRepo:
        def __init__(self, _db):
            pass

        def get_by_id(self, _property_id):
            return None

    class FakeSoldRepo:
        def __init__(self, _db):
            pass

    class FakeEnrichmentRepo:
        def __init__(self, _db):
            pass

    events: list[dict] = []

    monkeypatch.setattr("packages.storage.database.get_session", lambda: FakeSessionCtx())
    monkeypatch.setattr("packages.storage.repositories.PropertyRepository", FakePropertyRepo)
    monkeypatch.setattr("packages.storage.repositories.SoldPropertyRepository", FakeSoldRepo)
    monkeypatch.setattr("packages.storage.repositories.LLMEnrichmentRepository", FakeEnrichmentRepo)
    monkeypatch.setattr("apps.worker.tasks._record_backend_log", lambda **kwargs: events.append(kwargs))
    monkeypatch.setattr("apps.worker.tasks.settings.llm_enabled", True)

    result = enrich_property_llm("missing-prop")

    assert result == {"error": "Property not found"}
    assert len(events) == 1
    assert events[0]["event_type"] == "llm_enrichment_property_not_found"
    assert events[0]["context"]["property_id"] == "missing-prop"


def test_enrich_batch_llm_records_dispatched_backend_log(monkeypatch):
    class _IdField:
        def in_(self, _subquery):
            return self

        def desc(self):
            return self

        def __invert__(self):
            return self

    class FakeQuery:
        def __init__(self, rows):
            self._rows = rows

        def subquery(self):
            return object()

        def filter(self, *_args, **_kwargs):
            return self

        def order_by(self, *_args, **_kwargs):
            return self

        def limit(self, *_args, **_kwargs):
            return self

        def all(self):
            return self._rows

    class FakeSession:
        def __init__(self):
            self.calls = 0

        def query(self, *_args, **_kwargs):
            self.calls += 1
            if self.calls == 1:
                return FakeQuery([])
            return FakeQuery([SimpleNamespace(id="p1"), SimpleNamespace(id="p2")])

    class FakeSessionCtx:
        def __enter__(self):
            return FakeSession()

        def __exit__(self, exc_type, exc, tb):
            return False

    class FakeLLMEnrichment:
        property_id = _IdField()

    class FakeProperty:
        id = _IdField()
        first_listed_at = _IdField()

    send_calls: list[tuple] = []
    events: list[dict] = []

    monkeypatch.setattr("packages.storage.database.get_session", lambda: FakeSessionCtx())
    monkeypatch.setattr("packages.storage.models.LLMEnrichment", FakeLLMEnrichment)
    monkeypatch.setattr("packages.storage.models.Property", FakeProperty)
    monkeypatch.setattr("packages.shared.queue.send_task", lambda *args, **kwargs: send_calls.append((args, kwargs)) or "msg")
    monkeypatch.setattr("apps.worker.tasks._record_backend_log", lambda **kwargs: events.append(kwargs))
    monkeypatch.setattr("apps.worker.tasks.settings.llm_enabled", True)
    monkeypatch.setattr("apps.worker.tasks._is_queue_configured", lambda _queue_name: True)

    result = enrich_batch_llm(limit=3)

    assert result == {"dispatched": 2}
    assert len(send_calls) == 2
    assert len(events) == 1
    assert events[0]["event_type"] == "llm_batch_dispatched"
    assert events[0]["context"]["dispatched"] == 2


def test_discover_all_sources_skips_invalid_adapter_config(monkeypatch):
    class FakeRepo:
        def __init__(self, _db):
            self.created = []

        def get_all(self, enabled_only=False):
            return []

        def create(self, **kwargs):
            self.created.append(kwargs)
            return kwargs

    class FakeSession:
        def commit(self):
            return None

    class FakeSessionCtx:
        def __enter__(self):
            return FakeSession()

        def __exit__(self, exc_type, exc, tb):
            return False

    class FakeAdapter:
        def validate_config(self, config):
            if isinstance(config.get("areas"), list):
                return []
            return ["config.areas must be type 'array'"]

    repo_holder = {}

    def _repo_factory(db):
        repo = FakeRepo(db)
        repo_holder["repo"] = repo
        return repo

    monkeypatch.setattr("packages.storage.database.get_session", lambda: FakeSessionCtx())
    monkeypatch.setattr("packages.storage.repositories.SourceRepository", _repo_factory)
    monkeypatch.setattr("packages.sources.registry.get_adapter_names", lambda: ["daft"])
    monkeypatch.setattr("packages.sources.registry.get_adapter", lambda _name: FakeAdapter())
    monkeypatch.setattr(
        "packages.sources.discovery.load_all_discovery_candidates",
        lambda **_kwargs: [
            SimpleNamespace(
                candidate={
                    "name": "Broken Candidate",
                    "url": "https://www.daft.ie/property-for-sale/dublin",
                    "adapter_name": "daft",
                    "adapter_type": "api",
                    "config": {"areas": "dublin"},
                },
                score=0.8,
                activation="auto_enable",
                should_auto_enable=True,
                reasons=["known_adapter:daft"],
            )
        ],
    )
    monkeypatch.setattr("apps.worker.tasks._record_backend_log", lambda **_kwargs: None)

    result = discover_all_sources(limit=20, dry_run=False, follow_links=False, include_grants=False)

    assert result["property_sources"]["skipped_invalid_config"] == 1
    assert result["property_sources"]["auto_enabled"] == 0
    assert repo_holder["repo"].created == []
