"""Tests for BackendLogRepository behavior."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

from packages.storage.repositories import BackendLogRepository


class _ExecuteResult:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return self._rows


class _FakeSession:
    def __init__(self):
        self.scalar_value = None
        self.scalars_rows = []
        self.execute_rows = []

        self.scalars_queries = []
        self.scalar_queries = []
        self.execute_queries = []

    def scalars(self, query):
        self.scalars_queries.append(query)
        return self.scalars_rows

    def scalar(self, query):
        self.scalar_queries.append(query)
        return self.scalar_value

    def execute(self, query):
        self.execute_queries.append(query)
        rows = self.execute_rows.pop(0)
        return _ExecuteResult(rows)


def test_list_recent_applies_level_and_event_filters(monkeypatch):
    fixed_now = datetime(2026, 3, 9, 12, 0, 0, tzinfo=UTC)
    monkeypatch.setattr("packages.storage.repositories.utc_now", lambda: fixed_now)

    session = _FakeSession()
    session.scalars_rows = [SimpleNamespace(id="log-1")]
    repo = BackendLogRepository(session)

    rows = repo.list_recent(hours=6, limit=5, level="error", event_type="scrape_source_complete")

    assert len(rows) == 1
    query = session.scalars_queries[0]
    compiled = query.compile()
    query_text = str(compiled).lower()
    params = compiled.params

    assert "backend_logs.level" in query_text
    assert "backend_logs.event_type" in query_text
    assert "limit" in query_text
    assert "ERROR" in params.values()
    assert "scrape_source_complete" in params.values()
    assert 5 in params.values()


def test_list_recent_errors_filters_to_error_and_warning(monkeypatch):
    fixed_now = datetime(2026, 3, 9, 12, 0, 0, tzinfo=UTC)
    monkeypatch.setattr("packages.storage.repositories.utc_now", lambda: fixed_now)

    session = _FakeSession()
    session.scalars_rows = []
    repo = BackendLogRepository(session)

    repo.list_recent_errors(hours=24, limit=10)

    query = session.scalars_queries[0]
    compiled = query.compile()
    query_text = str(compiled).lower()
    params = compiled.params

    assert "backend_logs.level" in query_text
    assert "warning" in str(params).lower()
    assert "error" in str(params).lower()
    assert 10 in params.values()


def test_count_recent_errors_returns_zero_when_scalar_none(monkeypatch):
    fixed_now = datetime(2026, 3, 9, 12, 0, 0, tzinfo=UTC)
    monkeypatch.setattr("packages.storage.repositories.utc_now", lambda: fixed_now)

    session = _FakeSession()
    session.scalar_value = None
    repo = BackendLogRepository(session)

    count = repo.count_recent_errors(hours=1)

    assert count == 0
    query = session.scalar_queries[0]
    query_text = str(query.compile()).lower()
    assert "count" in query_text
    assert "backend_logs" in query_text


def test_summary_returns_aggregated_counts(monkeypatch):
    fixed_now = datetime(2026, 3, 9, 12, 0, 0, tzinfo=UTC)
    monkeypatch.setattr("packages.storage.repositories.utc_now", lambda: fixed_now)

    session = _FakeSession()
    session.execute_rows = [
        [
            SimpleNamespace(level="ERROR", total=2),
            SimpleNamespace(level="WARNING", total=1),
        ],
        [
            SimpleNamespace(event_type="scrape_source_failed", total=2),
            SimpleNamespace(event_type="alert_dispatch_failed", total=1),
        ],
    ]
    repo = BackendLogRepository(session)

    result = repo.summary(hours=0)

    assert result["hours"] == 1
    assert result["total"] == 3
    assert result["by_level"] == [
        {"level": "ERROR", "count": 2},
        {"level": "WARNING", "count": 1},
    ]
    assert result["by_event_type"] == [
        {"event_type": "scrape_source_failed", "count": 2},
        {"event_type": "alert_dispatch_failed", "count": 1},
    ]
    assert len(session.execute_queries) == 2
