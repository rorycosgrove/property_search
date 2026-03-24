import subprocess
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from packages.admin.service import (
    AdminServiceError,
    MigrationCommandFailedError,
    MigrationCommandTimedOutError,
    data_lifecycle_report,
    data_lifecycle_schedule_metadata,
    explain_source_quality,
    backend_health_summary,
    get_migration_status,
    list_feed_activity,
    list_recent_errors,
    list_source_status,
    list_source_quality_activity,
    run_data_lifecycle_action,
    source_net_new_summary,
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


def test_list_source_status_uses_live_listing_count():
    source = SimpleNamespace(
        id="source-1",
        name="Daft Feed",
        enabled=True,
        error_count=0,
        last_error=None,
        last_polled_at=None,
        last_success_at=None,
        poll_interval_seconds=900,
        total_listings=0,
    )

    rows = [(source, 12)]

    class FakeQuery:
        def __init__(self, result_rows):
            self.result_rows = result_rows

        def outerjoin(self, *_args, **_kwargs):
            return self

        def group_by(self, *_args, **_kwargs):
            return self

        def order_by(self, *_args, **_kwargs):
            return self

        def all(self):
            return self.result_rows

    class FakeDB:
        def query(self, *_args, **_kwargs):
            return FakeQuery(rows)

    payload = list_source_status(FakeDB())

    assert len(payload) == 1
    assert payload[0]["id"] == "source-1"
    assert payload[0]["total_listings"] == 12


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


def test_run_data_lifecycle_action_dry_run_writes_audit_log():
    from packages.storage.models import BackendLog, Property, PropertyPriceHistory, PropertyTimelineEvent

    counts = {
        Property: 5,
        BackendLog: 100,
        PropertyPriceHistory: 40,
        PropertyTimelineEvent: 60,
    }

    class FakeQuery:
        def __init__(self, model):
            self.model = model

        def filter(self, *_args, **_kwargs):
            return self

        def count(self):
            return counts.get(self.model, 0)

    class FakeDB:
        def __init__(self):
            self.added = []

        def query(self, model):
            return FakeQuery(model)

        def add(self, row):
            self.added.append(row)

        def flush(self):
            return None

    db = FakeDB()
    payload = run_data_lifecycle_action(
        db,
        action="archive_properties",
        dry_run=True,
    )

    assert payload["status"] == "dry_run_completed"
    assert payload["affected_candidates"] == 5
    assert len(db.added) == 1
    log = db.added[0]
    assert log.event_type == "admin_data_lifecycle_action"
    assert log.context_json["action"] == "archive_properties"


def test_run_data_lifecycle_action_rejects_non_dry_run():
    class FakeDB:
        def query(self, _model):
            class _Q:
                def filter(self, *_args, **_kwargs):
                    return self

                def count(self):
                    return 0

            return _Q()

        def add(self, _row):
            raise AssertionError("add should not be called")

        def flush(self):
            raise AssertionError("flush should not be called")

    with pytest.raises(AdminServiceError, match="lifecycle_destructive_execution_enabled"):
        run_data_lifecycle_action(
            FakeDB(),
            action="archive_properties",
            dry_run=False,
        )


def test_run_data_lifecycle_action_rejects_non_dry_run_without_flag_enabled():
    class FakeDB:
        def query(self, _model):
            class _Q:
                def filter(self, *_args, **_kwargs):
                    return self

                def count(self):
                    return 0

            return _Q()

    settings = SimpleNamespace(
        lifecycle_destructive_execution_enabled=False,
        lifecycle_rollback_plan_id="rollbacks/2026-03-lifecycle",
    )

    with pytest.raises(AdminServiceError, match="lifecycle_destructive_execution_enabled"):
        run_data_lifecycle_action(
            FakeDB(),
            action="archive_properties",
            queue_settings=settings,
            dry_run=False,
        )


def test_run_data_lifecycle_action_rejects_non_dry_run_without_rollback_plan():
    class FakeDB:
        def query(self, _model):
            class _Q:
                def filter(self, *_args, **_kwargs):
                    return self

                def count(self):
                    return 0

            return _Q()

    settings = SimpleNamespace(
        lifecycle_destructive_execution_enabled=True,
        lifecycle_rollback_plan_id="",
    )

    with pytest.raises(AdminServiceError, match="lifecycle_rollback_plan_id"):
        run_data_lifecycle_action(
            FakeDB(),
            action="archive_properties",
            queue_settings=settings,
            dry_run=False,
        )


def test_data_lifecycle_schedule_metadata_exposes_execution_readiness():
    class FakeRepo:
        def __init__(self, _db):
            pass

        def list_recent(self, **_kwargs):
            return []

    with pytest.MonkeyPatch.context() as m:
        m.setattr("packages.admin.service.BackendLogRepository", FakeRepo)
        payload = data_lifecycle_schedule_metadata(
            SimpleNamespace(),
            queue_settings=SimpleNamespace(
                scrape_poll_interval_seconds=21600,
                rss_poll_interval_seconds=3600,
                ppr_poll_interval_seconds=86400,
                backend_log_retention_days=7,
                lifecycle_destructive_execution_enabled=True,
                lifecycle_rollback_plan_id="rollbacks/2026-03-lifecycle",
            ),
        )

    assert payload["execution_mode"]["destructive_enabled"] is True
    assert payload["execution_mode"]["rollback_plan_id_configured"] is True
    assert payload["execution_mode"]["destructive_ready"] is True
    assert payload["execution_mode"]["dry_run_only"] is False


def test_backend_health_summary_ignores_non_actionable_last_error():
    scrape_rows = [
        SimpleNamespace(
            context_json={"geocode_attempts": 4, "geocode_successes": 3},
        )
    ]
    error_rows = [
        SimpleNamespace(
            created_at=datetime(2026, 3, 24, tzinfo=UTC),
            level="WARNING",
            event_type="daft_area_blocked",
            message="blocked",
            context_json={"source_name": "Daft.ie", "error": "status 403"},
        ),
        SimpleNamespace(
            created_at=datetime(2026, 3, 24, tzinfo=UTC),
            level="ERROR",
            event_type="scrape_source_failed",
            message="failed",
            context_json={"source_name": "MyHome", "error": "database timeout"},
        ),
    ]

    class FakeQuery:
        def __init__(self, rows):
            self._rows = rows

        def filter(self, *_args, **_kwargs):
            return self

        def order_by(self, *_args, **_kwargs):
            return self

        def limit(self, *_args, **_kwargs):
            return self

        def all(self):
            return self._rows

        def scalar(self):
            return 7

    class FakeDB:
        def __init__(self):
            self.query_calls = 0

        def query(self, *_args, **_kwargs):
            self.query_calls += 1
            if self.query_calls == 1:
                return FakeQuery(scrape_rows)
            if self.query_calls == 2:
                return FakeQuery(error_rows)
            return FakeQuery([])

    payload = backend_health_summary(
        FakeDB(),
        queue_settings=SimpleNamespace(
            scrape_queue_url="http://example.com/scrape",
            alert_queue_url="http://example.com/alert",
            llm_queue_url="",
        ),
    )

    assert payload["scrape_runs_24h"] == 7
    assert payload["geocode_attempts"] == 4
    assert payload["geocode_successes"] == 3
    assert payload["last_error"]["event_type"] == "scrape_source_failed"
    assert payload["last_error"]["level"] == "ERROR"


def test_list_recent_errors_filters_non_actionable_external_noise_by_default():
    rows = [
        SimpleNamespace(
            id="log-1",
            created_at=datetime(2026, 3, 24, tzinfo=UTC),
            level="WARNING",
            event_type="daft_cursor_auto_reset",
            component="worker.tasks",
            source_id="source-1",
            message="cursor reset",
            context_json={"source_name": "Daft.ie"},
        ),
        SimpleNamespace(
            id="log-2",
            created_at=datetime(2026, 3, 24, tzinfo=UTC),
            level="ERROR",
            event_type="scrape_source_failed",
            component="worker.tasks",
            source_id="source-2",
            message="failed",
            context_json={"source_name": "MyHome", "error": "Unconsumed column names: metadata_json"},
        ),
    ]

    class FakeRepo:
        def __init__(self, _db):
            pass

        def list_recent(self, *, hours=24, limit=25, level=None, event_type=None):
            return rows

        def list_recent_errors(self, *, hours=24, limit=25):
            return rows

    from packages.admin import service as admin_service

    with pytest.MonkeyPatch.context() as m:
        m.setattr(admin_service, "BackendLogRepository", FakeRepo)
        payload = list_recent_errors(SimpleNamespace(), limit=10)

    assert [item["id"] for item in payload] == ["log-2"]


def test_list_recent_errors_can_include_non_actionable_noise():
    rows = [
        SimpleNamespace(
            id="log-1",
            created_at=datetime(2026, 3, 24, tzinfo=UTC),
            level="WARNING",
            event_type="propertypal_area_blocked",
            component="worker.tasks",
            source_id="source-1",
            message="area blocked",
            context_json={"source_name": "PropertyPal"},
        ),
        SimpleNamespace(
            id="log-2",
            created_at=datetime(2026, 3, 24, tzinfo=UTC),
            level="ERROR",
            event_type="scrape_source_failed",
            component="worker.tasks",
            source_id="source-2",
            message="failed",
            context_json={"source_name": "MyHome", "error": "database timeout"},
        ),
    ]

    class FakeRepo:
        def __init__(self, _db):
            pass

        def list_recent(self, *, hours=24, limit=25, level=None, event_type=None):
            return rows

        def list_recent_errors(self, *, hours=24, limit=25):
            return rows

    from packages.admin import service as admin_service

    with pytest.MonkeyPatch.context() as m:
        m.setattr(admin_service, "BackendLogRepository", FakeRepo)
        payload = list_recent_errors(SimpleNamespace(), limit=10, include_non_actionable=True)

    assert [item["id"] for item in payload] == ["log-1", "log-2"]


# ─── list_feed_activity ────────────────────────────────────────────────────────


def test_list_feed_activity_surfaces_ingest_reason_fields():
    now = datetime(2026, 3, 22, tzinfo=UTC)
    rows = [
        SimpleNamespace(
            id="log-1",
            created_at=now,
            source_id="src-1",
            context_json={
                "source_name": "Daft Cork",
                "new": 0,
                "updated": 0,
                "skipped": 80,
                "total_fetched": 80,
                "geocode_success_rate": 100.0,
                "existing_by_external_id": 75,
                "existing_by_content_hash": 5,
                "zero_fetch_reason": "all_existing_mixed",
            },
        )
    ]

    class FakeQuery:
        def __init__(self, result_rows):
            self._rows = result_rows

        def filter(self, *_a, **_kw):
            return self

        def order_by(self, *_a, **_kw):
            return self

        def limit(self, *_a, **_kw):
            return self

        def all(self):
            return self._rows

    class FakeDB:
        def query(self, *_a, **_kw):
            return FakeQuery(rows)

    payload = list_feed_activity(FakeDB(), limit=1)

    assert len(payload) == 1
    row = payload[0]
    assert row["existing_by_external_id"] == 75
    assert row["existing_by_content_hash"] == 5
    assert row["zero_fetch_reason"] == "all_existing_mixed"


# ─── source_net_new_summary ────────────────────────────────────────────────────


def test_source_net_new_summary_ranks_stalled_sources_first():
    now = datetime(2026, 3, 22, tzinfo=UTC)

    def _make_log(source_id, source_name, new, total_fetched, at=now):
        return SimpleNamespace(
            source_id=source_id,
            created_at=at,
            context_json={
                "source_name": source_name,
                "new": new,
                "updated": 0,
                "total_fetched": total_fetched,
                "zero_fetch_reason": "no_results" if total_fetched == 0 else None,
            },
        )

    log_rows = [
        _make_log("src-active", "Active Source", new=5, total_fetched=80),
        _make_log("src-stalled", "Stalled Source", new=0, total_fetched=0),
        _make_log("src-stalled", "Stalled Source", new=0, total_fetched=0),
    ]

    class FakeQuery:
        def __init__(self, result_rows):
            self._rows = result_rows

        def filter(self, *_a, **_kw):
            return self

        def order_by(self, *_a, **_kw):
            return self

        def limit(self, *_a, **_kw):
            return self

        def all(self):
            return self._rows

    class FakeDB:
        def query(self, *_a, **_kw):
            return FakeQuery(log_rows)

    result = source_net_new_summary(FakeDB(), runs=10)

    assert len(result) == 2
    # Stalled source should appear first
    assert result[0]["source_id"] == "src-stalled"
    assert result[0]["zero_ingestion"] is True
    assert result[0]["consecutive_zero_new"] == 2
    assert result[0]["consecutive_zero_fetch"] == 2
    assert result[0]["total_new"] == 0

    assert result[1]["source_id"] == "src-active"
    assert result[1]["zero_ingestion"] is False
    assert result[1]["total_new"] == 5


def test_source_net_new_summary_consecutive_zero_streak_stops_at_first_success():
    """consecutive_zero_new should stop counting when a non-zero new run is found."""
    now = datetime(2026, 3, 22, tzinfo=UTC)
    from datetime import timedelta

    def _log(new, total_fetched, offset_mins=0):
        return SimpleNamespace(
            source_id="src-1",
            created_at=now - timedelta(minutes=offset_mins),
            context_json={
                "source_name": "Test Source",
                "new": new,
                "updated": 0,
                "total_fetched": total_fetched,
                "zero_fetch_reason": None,
            },
        )

    # Most recent two are zero, then one was successful
    log_rows = [_log(0, 80, 0), _log(0, 80, 10), _log(3, 80, 20)]

    class FakeQuery:
        def filter(self, *_a, **_kw):
            return self

        def order_by(self, *_a, **_kw):
            return self

        def limit(self, *_a, **_kw):
            return self

        def all(self):
            return log_rows

    class FakeDB:
        def query(self, *_a, **_kw):
            return FakeQuery()

    result = source_net_new_summary(FakeDB(), runs=10)

    assert len(result) == 1
    assert result[0]["consecutive_zero_new"] == 2  # streak stops at the successful run
    assert result[0]["total_new"] == 3