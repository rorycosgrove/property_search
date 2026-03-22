import subprocess
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from packages.admin.service import (
    MigrationCommandFailedError,
    MigrationCommandTimedOutError,
    data_lifecycle_report,
    explain_source_quality,
    get_migration_status,
    list_source_quality_activity,
    source_quality_scorecards,
    run_database_migrations,
)


class _FakeLogger:
    def __init__(self):
        self.info_calls = []
        self.error_calls = []

    def info(self, event, **kwargs):
        self.info_calls.append((event, kwargs))

    def error(self, event, **kwargs):
        self.error_calls.append((event, kwargs))


def test_run_database_migrations_success():
    logger = _FakeLogger()

    def runner(*_args, **_kwargs):
        return SimpleNamespace(returncode=0, stdout="upgraded\n", stderr="")

    payload = run_database_migrations(logger=logger, executable="python", runner=runner, timeout=5)

    assert payload == {"status": "ok", "output": "upgraded"}
    assert logger.info_calls[0][0] == "migration_success"


def test_run_database_migrations_raises_on_nonzero_exit():
    logger = _FakeLogger()

    def runner(*_args, **_kwargs):
        return SimpleNamespace(returncode=1, stdout="", stderr="boom")

    with pytest.raises(MigrationCommandFailedError, match="boom"):
        run_database_migrations(logger=logger, executable="python", runner=runner, timeout=5)

    assert logger.error_calls[0][0] == "migration_failed"


def test_run_database_migrations_raises_on_timeout():
    logger = _FakeLogger()

    def runner(*_args, **_kwargs):
        raise subprocess.TimeoutExpired(cmd="alembic", timeout=5)

    with pytest.raises(MigrationCommandTimedOutError, match="Migration timed out"):
        run_database_migrations(logger=logger, executable="python", runner=runner, timeout=5)

    assert logger.error_calls[0][0] == "migration_timeout"


def test_get_migration_status_success():
    def runner(*_args, **_kwargs):
        return SimpleNamespace(returncode=0, stdout="abc123\n", stderr="")

    payload = get_migration_status(executable="python", runner=runner, timeout=5)

    assert payload == {"revision": "abc123"}


def test_get_migration_status_raises_on_nonzero_exit():
    def runner(*_args, **_kwargs):
        return SimpleNamespace(returncode=1, stdout="", stderr="bad status")

    with pytest.raises(MigrationCommandFailedError, match="bad status"):
        get_migration_status(executable="python", runner=runner, timeout=5)


def test_get_migration_status_raises_on_timeout():
    def runner(*_args, **_kwargs):
        raise subprocess.TimeoutExpired(cmd="alembic", timeout=5)

    with pytest.raises(MigrationCommandTimedOutError, match="Status check timed out"):
        get_migration_status(executable="python", runner=runner, timeout=5)


def test_list_source_quality_activity_uses_repository():
    db = SimpleNamespace()

    row = SimpleNamespace(
        id="sq-1",
        created_at=datetime(2026, 3, 21),
        source_id="source-1",
        source_name="Daft.ie",
        adapter_name="daft",
        run_type="scrape",
        total_fetched=100,
        parse_failed=4,
        new_count=10,
        updated_count=8,
        price_unchanged_count=70,
        dedup_conflicts=2,
        candidates_scored=None,
        created_count=None,
        auto_enabled_count=None,
        pending_approval_count=None,
        existing_count=None,
        skipped_invalid_count=None,
        skipped_invalid_config_count=None,
        score_avg=None,
        score_max=None,
        dry_run=None,
        follow_links=None,
        details={"geocode_success_rate": 95.0},
    )

    class FakeRepo:
        def __init__(self, _db):
            pass

        def list_recent(self, *, source_id=None, run_type=None, limit=100):
            assert source_id == "source-1"
            assert run_type == "scrape"
            assert limit == 20
            return [row]

    from packages.admin import service as admin_service

    original_repo = admin_service.SourceQualitySnapshotRepository
    admin_service.SourceQualitySnapshotRepository = FakeRepo
    try:
        payload = list_source_quality_activity(db, limit=20, source_id="source-1", run_type="scrape")
    finally:
        admin_service.SourceQualitySnapshotRepository = original_repo

    assert len(payload) == 1
    assert payload[0]["id"] == "sq-1"
    assert payload[0]["source_name"] == "Daft.ie"
    assert payload[0]["details"]["geocode_success_rate"] == 95.0


def test_source_quality_scorecards_recommends_promote_and_quarantine():
    now = datetime(2026, 3, 21, tzinfo=UTC)

    scrape_rows = [
        SimpleNamespace(
            source_id="s-good",
            source_name="Good Source",
            adapter_name="daft",
            total_fetched=100,
            parse_failed=2,
            new_count=2,
            updated_count=1,
            dedup_conflicts=0,
            created_at=now,
        ),
        SimpleNamespace(
            source_id="s-good",
            source_name="Good Source",
            adapter_name="daft",
            total_fetched=100,
            parse_failed=3,
            new_count=1,
            updated_count=1,
            dedup_conflicts=0,
            created_at=now,
        ),
        SimpleNamespace(
            source_id="s-bad",
            source_name="Bad Source",
            adapter_name="myhome",
            total_fetched=100,
            parse_failed=70,
            new_count=0,
            updated_count=0,
            dedup_conflicts=3,
            created_at=now,
        ),
        SimpleNamespace(
            source_id="s-bad",
            source_name="Bad Source",
            adapter_name="myhome",
            total_fetched=120,
            parse_failed=72,
            new_count=0,
            updated_count=0,
            dedup_conflicts=2,
            created_at=now,
        ),
    ]

    class FakeQualityRepo:
        def __init__(self, _db):
            pass

        def list_recent(self, *, source_id=None, run_type=None, limit=100):
            assert source_id is None
            if run_type == "scrape":
                return scrape_rows
            if run_type == "governance":
                return [
                    SimpleNamespace(
                        source_id="s-good",
                        created_at=now,
                        details={
                            "action": "promote",
                            "reason": "avg_parse_fail_rate=0.0250; threshold_met=0.1000",
                        },
                    ),
                    SimpleNamespace(
                        source_id="s-bad",
                        created_at=now,
                        details={
                            "action": "quarantine",
                            "reason": "avg_parse_fail_rate=0.6455; threshold_exceeded=0.5000",
                        },
                    ),
                ]
            return []

    class FakeSourceRepo:
        def __init__(self, _db):
            pass

        def get_all(self, enabled_only=False):
            assert enabled_only is False
            return [
                SimpleNamespace(id="s-good", name="Good Source", adapter_name="daft", enabled=False, tags=["pending_approval"]),
                SimpleNamespace(id="s-bad", name="Bad Source", adapter_name="myhome", enabled=True, tags=[]),
            ]

    from packages.admin import service as admin_service

    original_quality = admin_service.SourceQualitySnapshotRepository
    original_source = admin_service.SourceRepository
    original_datetime = admin_service.datetime
    admin_service.SourceQualitySnapshotRepository = FakeQualityRepo
    admin_service.SourceRepository = FakeSourceRepo

    class _FrozenDatetime:
        @staticmethod
        def now(_tz=None):
            return now

    admin_service.datetime = _FrozenDatetime
    try:
        payload = source_quality_scorecards(object(), lookback_hours=24, limit=10, min_samples=2)
    finally:
        admin_service.SourceQualitySnapshotRepository = original_quality
        admin_service.SourceRepository = original_source
        admin_service.datetime = original_datetime

    cards = {c["source_id"]: c for c in payload["scorecards"]}
    assert cards["s-good"]["recommendation"] == "promote"
    assert cards["s-bad"]["recommendation"] == "quarantine"
    assert cards["s-good"]["latest_governance_action"] == "promote"
    assert "threshold_met" in cards["s-good"]["latest_governance_reason"]
    assert cards["s-good"]["latest_governance_confidence"] is not None
    assert cards["s-good"]["latest_governance_confidence"] > 0
    assert cards["s-bad"]["latest_governance_action"] == "quarantine"
    assert "threshold_exceeded" in cards["s-bad"]["latest_governance_reason"]
    assert cards["s-bad"]["latest_governance_confidence"] is not None
    assert cards["s-bad"]["latest_governance_confidence"] > 0


def test_explain_source_quality_returns_decisions_and_scorecard():
    now = datetime(2026, 3, 21, tzinfo=UTC)

    class FakeQualityRepo:
        def __init__(self, _db):
            pass

        def list_recent(self, *, source_id=None, run_type=None, limit=100):
            if run_type == "scrape":
                return [
                    SimpleNamespace(
                        source_id="s-1",
                        source_name="Daft.ie",
                        adapter_name="daft",
                        total_fetched=100,
                        parse_failed=5,
                        new_count=3,
                        updated_count=2,
                        price_unchanged_count=60,
                        dedup_conflicts=1,
                        created_at=now,
                        details={"geocode_success_rate": 99.0},
                    )
                ]
            if run_type == "governance":
                return [
                    SimpleNamespace(
                        source_id="s-1",
                        total_fetched=300,
                        parse_failed=20,
                        new_count=8,
                        updated_count=4,
                        created_at=now,
                        details={
                            "action": "promote",
                            "reason": "avg_parse_fail_rate=0.0667; threshold_met=0.1000",
                            "thresholds": {"promote_parse_fail_rate": 0.1},
                            "source_tags": ["quality_promoted"],
                        },
                    )
                ]
            return []

    class FakeSourceRepo:
        def __init__(self, _db):
            pass

        def get_by_id(self, source_id):
            if source_id == "s-1":
                return SimpleNamespace(
                    id="s-1",
                    name="Daft.ie",
                    adapter_name="daft",
                    enabled=True,
                    tags=["quality_promoted"],
                )
            return None

        def get_all(self, enabled_only=False):
            assert enabled_only is False
            return [
                SimpleNamespace(
                    id="s-1",
                    name="Daft.ie",
                    adapter_name="daft",
                    enabled=True,
                    tags=["quality_promoted"],
                )
            ]

    from packages.admin import service as admin_service

    original_quality = admin_service.SourceQualitySnapshotRepository
    original_source = admin_service.SourceRepository
    original_datetime = admin_service.datetime
    admin_service.SourceQualitySnapshotRepository = FakeQualityRepo
    admin_service.SourceRepository = FakeSourceRepo

    class _FrozenDatetime:
        @staticmethod
        def now(_tz=None):
            return now

    admin_service.datetime = _FrozenDatetime
    try:
        payload = explain_source_quality(
            object(),
            source_id="s-1",
            lookback_hours=24,
            min_samples=1,
            governance_limit=5,
            scrape_limit=5,
        )
    finally:
        admin_service.SourceQualitySnapshotRepository = original_quality
        admin_service.SourceRepository = original_source
        admin_service.datetime = original_datetime

    assert payload["source_found"] is True
    assert payload["scorecard"]["source_id"] == "s-1"
    assert payload["governance_decisions"][0]["action"] == "promote"
    assert payload["recent_scrape_quality"][0]["total_fetched"] == 100


def test_data_lifecycle_report_returns_candidate_counts():
    from packages.storage.models import BackendLog, Property, PropertyPriceHistory, PropertyTimelineEvent

    counts = {
        Property: 12,
        BackendLog: 250,
        PropertyPriceHistory: 1042,
        PropertyTimelineEvent: 980,
    }

    class FakeQuery:
        def __init__(self, model):
            self.model = model

        def filter(self, *_args, **_kwargs):
            return self

        def count(self):
            return counts.get(self.model, 0)

    class FakeDB:
        def query(self, model):
            return FakeQuery(model)

    payload = data_lifecycle_report(
        FakeDB(),
        property_archive_days=365,
        backend_log_archive_days=90,
        rollup_days=180,
    )

    assert payload["candidates"]["property_archive"] == 12
    assert payload["candidates"]["backend_log_archive"] == 250
    assert payload["candidates"]["price_history_rollup"] == 1042
    assert payload["candidates"]["timeline_rollup"] == 980
    assert payload["actions"][0]["dry_run"] is True