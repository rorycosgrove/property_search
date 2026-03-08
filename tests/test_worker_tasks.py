"""Tests for worker task local fallback behavior."""

from types import SimpleNamespace

from apps.worker.tasks import scrape_all_sources, scrape_source


class _SessionCtx:
    """Simple context manager used to stub get_session()."""

    def __enter__(self):
        return object()

    def __exit__(self, exc_type, exc, tb):
        return False


def test_scrape_all_sources_falls_back_inline_when_scrape_queue_missing(monkeypatch):
    """When SCRAPE_QUEUE_URL is absent, sources should be processed inline."""
    monkeypatch.delenv("SCRAPE_QUEUE_URL", raising=False)

    fake_sources = [SimpleNamespace(id="source-1"), SimpleNamespace(id="source-2")]

    class FakeSourceRepository:
        def __init__(self, _db):
            pass

        def get_all(self, enabled_only=True):
            assert enabled_only is True
            return fake_sources

    send_calls: list[tuple[tuple, dict]] = []
    inline_calls: list[str] = []

    monkeypatch.setattr("packages.storage.database.get_session", lambda: _SessionCtx())
    monkeypatch.setattr("packages.storage.repositories.SourceRepository", FakeSourceRepository)
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
    }
    assert inline_calls == ["source-1", "source-2"]
    assert send_calls == []


def test_scrape_all_sources_uses_sqs_dispatch_when_queue_configured(monkeypatch):
    """When SCRAPE_QUEUE_URL is present, tasks should be dispatched via SQS."""
    monkeypatch.setenv("SCRAPE_QUEUE_URL", "https://example.com/sqs/scrape")

    fake_sources = [SimpleNamespace(id="source-1"), SimpleNamespace(id="source-2")]

    class FakeSourceRepository:
        def __init__(self, _db):
            pass

        def get_all(self, enabled_only=True):
            assert enabled_only is True
            return fake_sources

    send_calls: list[tuple[tuple, dict]] = []
    inline_calls: list[str] = []

    monkeypatch.setattr("packages.storage.database.get_session", lambda: _SessionCtx())
    monkeypatch.setattr("packages.storage.repositories.SourceRepository", FakeSourceRepository)
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
