"""Tests for Alembic migration 007_backend_logs."""

from __future__ import annotations

import importlib.util
from pathlib import Path

from sqlalchemy import DateTime, String, Text
from sqlalchemy.dialects import postgresql


def _migration_module():
    migration_file = Path(__file__).resolve().parents[1] / "alembic" / "versions" / "007_backend_logs.py"
    spec = importlib.util.spec_from_file_location("migration_007_backend_logs", migration_file)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_migration_revision_metadata_is_correct():
    mig = _migration_module()

    assert mig.revision == "007_backend_logs"
    assert mig.down_revision == "006_organic_search_runs"
    assert mig.branch_labels is None
    assert mig.depends_on is None


def test_upgrade_creates_backend_logs_table_and_indexes(monkeypatch):
    mig = _migration_module()

    captured: dict[str, object] = {}
    index_calls: list[tuple[str, str, list[str]]] = []

    def fake_create_table(name, *columns):
        captured["name"] = name
        captured["columns"] = columns

    def fake_create_index(name, table_name, columns):
        index_calls.append((name, table_name, list(columns)))

    monkeypatch.setattr(mig.op, "create_table", fake_create_table)
    monkeypatch.setattr(mig.op, "create_index", fake_create_index)

    mig.upgrade()

    assert captured["name"] == "backend_logs"
    columns = {col.name: col for col in captured["columns"]}
    assert set(columns.keys()) == {
        "id",
        "level",
        "event_type",
        "component",
        "source_id",
        "message",
        "context",
        "created_at",
    }

    assert isinstance(columns["id"].type, String)
    assert columns["id"].type.length == 36
    assert columns["id"].primary_key is True

    assert isinstance(columns["level"].type, String)
    assert columns["level"].nullable is False
    assert isinstance(columns["event_type"].type, String)
    assert columns["event_type"].nullable is False

    assert isinstance(columns["component"].type, String)
    assert columns["component"].nullable is False
    assert columns["component"].server_default is not None

    assert isinstance(columns["source_id"].type, String)
    assert columns["source_id"].nullable is True
    assert isinstance(columns["message"].type, Text)
    assert columns["message"].nullable is False

    assert isinstance(columns["context"].type, postgresql.JSONB)
    assert columns["context"].nullable is False
    assert columns["context"].server_default is not None
    assert "jsonb" in str(columns["context"].server_default.arg).lower()

    assert isinstance(columns["created_at"].type, DateTime)
    assert columns["created_at"].nullable is False
    assert columns["created_at"].server_default is not None

    assert index_calls == [
        ("ix_backend_logs_created_at", "backend_logs", ["created_at"]),
        ("ix_backend_logs_source_id", "backend_logs", ["source_id"]),
        ("ix_backend_logs_event_created", "backend_logs", ["event_type", "created_at"]),
        ("ix_backend_logs_level_created", "backend_logs", ["level", "created_at"]),
    ]


def test_downgrade_drops_indexes_then_table(monkeypatch):
    mig = _migration_module()

    dropped_indexes: list[tuple[str, str]] = []
    dropped_tables: list[str] = []

    def fake_drop_index(name, table_name=None):
        dropped_indexes.append((name, table_name))

    def fake_drop_table(name):
        dropped_tables.append(name)

    monkeypatch.setattr(mig.op, "drop_index", fake_drop_index)
    monkeypatch.setattr(mig.op, "drop_table", fake_drop_table)

    mig.downgrade()

    assert dropped_indexes == [
        ("ix_backend_logs_level_created", "backend_logs"),
        ("ix_backend_logs_event_created", "backend_logs"),
        ("ix_backend_logs_source_id", "backend_logs"),
        ("ix_backend_logs_created_at", "backend_logs"),
    ]
    assert dropped_tables == ["backend_logs"]
