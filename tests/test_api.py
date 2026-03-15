"""Tests for FastAPI endpoints (uses TestClient)."""
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from apps.api.main import app


@pytest.fixture
def client():
    return TestClient(app)


class TestHealthEndpoint:
    def test_health_ok(self, client):
        from packages.storage.database import get_db_session

        mock_session = MagicMock()
        mock_session.execute.return_value = None
        app.dependency_overrides[get_db_session] = lambda: mock_session

        try:
            mock_boto3 = MagicMock()
            with patch.dict("sys.modules", {"boto3": mock_boto3}):
                mock_client = MagicMock()
                mock_client.list_foundation_models.return_value = {
                    "modelSummaries": [{"modelId": "amazon.titan-text-express-v1"}]
                }
                mock_boto3.client.return_value = mock_client

                resp = client.get("/health")
                assert resp.status_code == 200
                data = resp.json()
                assert data["status"] in ("healthy", "degraded")
                assert "backend_errors_last_hour" in data
        finally:
            app.dependency_overrides.clear()

    def test_health_reports_backend_error_count_value(self, client):
        from packages.storage.database import get_db_session

        mock_session = MagicMock()
        mock_session.execute.return_value = None
        app.dependency_overrides[get_db_session] = lambda: mock_session

        try:
            mock_boto3 = MagicMock()
            with patch.dict("sys.modules", {"boto3": mock_boto3}):
                mock_client = MagicMock()
                mock_client.list_foundation_models.return_value = {
                    "modelSummaries": [{"modelId": "amazon.titan-text-express-v1"}]
                }
                mock_boto3.client.return_value = mock_client

                with patch("apps.api.routers.health.BackendLogRepository") as MockRepo:
                    MockRepo.return_value.count_recent_errors.return_value = 4

                    resp = client.get("/health")

                assert resp.status_code == 200
                data = resp.json()
                assert data["backend_errors_last_hour"] == 4
        finally:
            app.dependency_overrides.clear()


class TestAdminLogsEndpoint:
    def test_get_backend_logs(self, client):
        from packages.storage.database import get_db_session

        mock_session = MagicMock()
        app.dependency_overrides[get_db_session] = lambda: mock_session

        try:
            with patch(
                "apps.api.routers.admin.list_backend_logs",
                return_value=[
                    {
                        "id": "log-1",
                        "timestamp": "2026-03-09T00:00:00",
                        "level": "INFO",
                        "event_type": "scrape_source_complete",
                        "component": "worker.tasks",
                        "source_id": "source-1",
                        "message": "done",
                        "context": {"new": 1},
                    }
                ],
            ) as mock_list:

                resp = client.get("/api/v1/admin/backend-logs?hours=12&limit=5")

                assert resp.status_code == 200
                data = resp.json()
                assert len(data) == 1
                assert data[0]["id"] == "log-1"
                assert data[0]["event_type"] == "scrape_source_complete"
                assert data[0]["context"]["new"] == 1
                mock_list.assert_called_once_with(
                    mock_session,
                    hours=12,
                    limit=5,
                    level=None,
                    event_type=None,
                )
        finally:
            app.dependency_overrides.clear()

    def test_get_backend_logs_summary(self, client):
        from packages.storage.database import get_db_session

        mock_session = MagicMock()
        app.dependency_overrides[get_db_session] = lambda: mock_session

        try:
            with patch("apps.api.routers.admin.backend_logs_summary") as mock_summary:
                mock_summary.return_value = {
                    "hours": 24,
                    "total": 3,
                    "by_level": [{"level": "ERROR", "count": 1}],
                    "by_event_type": [{"event_type": "scrape_source_failed", "count": 1}],
                }

                resp = client.get("/api/v1/admin/backend-logs/summary?hours=24")

                assert resp.status_code == 200
                data = resp.json()
                assert data["total"] == 3
                assert data["by_level"][0]["level"] == "ERROR"
                mock_summary.assert_called_once_with(mock_session, hours=24)
        finally:
            app.dependency_overrides.clear()

    def test_get_backend_logs_uses_real_repository_path(self, client):
        from packages.storage.database import get_db_session

        class FakeSession:
            def __init__(self):
                self.scalars_called = False

            def scalars(self, _query):
                self.scalars_called = True
                return [
                    MagicMock(
                        id="log-real-1",
                        created_at=datetime(2026, 3, 9),
                        level="WARNING",
                        event_type="llm_batch_skipped",
                        component="worker.tasks",
                        source_id=None,
                        message="skipped",
                        context_json={"reason": "llm_queue_unconfigured"},
                    )
                ]

        fake_session = FakeSession()
        app.dependency_overrides[get_db_session] = lambda: fake_session

        try:
            resp = client.get("/api/v1/admin/backend-logs?hours=6&limit=10&level=warning")
            assert resp.status_code == 200
            data = resp.json()
            assert len(data) == 1
            assert data[0]["id"] == "log-real-1"
            assert data[0]["level"] == "WARNING"
            assert data[0]["context"]["reason"] == "llm_queue_unconfigured"
            assert fake_session.scalars_called is True
        finally:
            app.dependency_overrides.clear()

    def test_get_backend_logs_event_type_filter_uses_real_repository_query(self, client):
        from packages.storage.database import get_db_session

        class FakeSession:
            def __init__(self):
                self.last_query = None

            def scalars(self, query):
                self.last_query = query
                return [
                    MagicMock(
                        id="log-real-2",
                        created_at=datetime(2026, 3, 9),
                        level="ERROR",
                        event_type="scrape_source_failed",
                        component="worker.tasks",
                        source_id="source-1",
                        message="failed",
                        context_json={"error": "boom"},
                    )
                ]

        fake_session = FakeSession()
        app.dependency_overrides[get_db_session] = lambda: fake_session

        try:
            resp = client.get(
                "/api/v1/admin/backend-logs?hours=24&limit=10&event_type=scrape_source_failed"
            )
            assert resp.status_code == 200
            data = resp.json()
            assert len(data) == 1
            assert data[0]["event_type"] == "scrape_source_failed"

            compiled = fake_session.last_query.compile()
            query_text = str(compiled).lower()
            params = compiled.params
            assert "backend_logs.event_type" in query_text
            assert "scrape_source_failed" in params.values()
        finally:
            app.dependency_overrides.clear()

    def test_get_backend_logs_summary_uses_real_repository_path(self, client):
        from packages.storage.database import get_db_session

        class _Result:
            def __init__(self, rows):
                self._rows = rows

            def all(self):
                return self._rows

        class FakeSession:
            def __init__(self):
                self.execute_calls = 0

            def execute(self, _query):
                self.execute_calls += 1
                if self.execute_calls == 1:
                    return _Result(
                        [
                            MagicMock(level="ERROR", total=2),
                            MagicMock(level="WARNING", total=1),
                        ]
                    )
                return _Result(
                    [
                        MagicMock(event_type="scrape_source_failed", total=2),
                        MagicMock(event_type="llm_enrichment_failed", total=1),
                    ]
                )

        fake_session = FakeSession()
        app.dependency_overrides[get_db_session] = lambda: fake_session

        try:
            resp = client.get("/api/v1/admin/backend-logs/summary?hours=24")
            assert resp.status_code == 200
            data = resp.json()
            assert data["total"] == 3
            assert data["by_level"][0]["level"] == "ERROR"
            assert data["by_event_type"][0]["event_type"] == "scrape_source_failed"
            assert fake_session.execute_calls == 2
        finally:
            app.dependency_overrides.clear()


class TestPropertiesEndpoint:
    def test_list_properties(self, client):
        from packages.storage.database import get_db_session

        mock_session = MagicMock()
        app.dependency_overrides[get_db_session] = lambda: mock_session

        try:
            with patch("apps.api.routers.properties.PropertyRepository") as MockRepo:
                instance = MockRepo.return_value
                instance.list_properties.return_value = ([], 0)
                resp = client.get("/api/v1/properties")
                assert resp.status_code == 200
                data = resp.json()
                assert "items" in data
                assert "total" in data
        finally:
            app.dependency_overrides.clear()

    def test_health_reports_backend_error_count_through_real_repository(self, client):
        from packages.storage.database import get_db_session

        class FakeSession:
            def __init__(self):
                self.execute_called = False
                self.scalar_called = False

            def execute(self, _query):
                self.execute_called = True
                return None

            def scalar(self, _query):
                self.scalar_called = True
                return 2

        fake_session = FakeSession()
        app.dependency_overrides[get_db_session] = lambda: fake_session

        try:
            mock_boto3 = MagicMock()
            with patch.dict("sys.modules", {"boto3": mock_boto3}):
                mock_client = MagicMock()
                mock_client.list_foundation_models.return_value = {
                    "modelSummaries": [{"modelId": "amazon.titan-text-express-v1"}]
                }
                mock_boto3.client.return_value = mock_client

                resp = client.get("/health")

            assert resp.status_code == 200
            data = resp.json()
            assert data["backend_errors_last_hour"] == 2
            assert fake_session.execute_called is True
            assert fake_session.scalar_called is True
        finally:
            app.dependency_overrides.clear()

    def test_get_property_not_found(self, client):
        from packages.storage.database import get_db_session

        mock_session = MagicMock()
        app.dependency_overrides[get_db_session] = lambda: mock_session

        try:
            with patch("apps.api.routers.properties.PropertyRepository") as MockRepo:
                instance = MockRepo.return_value
                instance.get_by_id.return_value = None
                resp = client.get("/api/v1/properties/00000000-0000-0000-0000-000000000000")
                assert resp.status_code == 404
        finally:
            app.dependency_overrides.clear()


class TestSourcesEndpoint:
    def test_list_sources(self, client):
        from packages.storage.database import get_db_session

        mock_session = MagicMock()
        app.dependency_overrides[get_db_session] = lambda: mock_session

        try:
            with patch("apps.api.routers.sources.SourceRepository") as MockRepo:
                instance = MockRepo.return_value
                instance.get_all.return_value = []
                resp = client.get("/api/v1/sources")
                assert resp.status_code == 200
        finally:
            app.dependency_overrides.clear()

    def test_list_adapters(self, client):
        resp = client.get("/api/v1/sources/adapters")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert any(a["name"] == "daft" for a in data)

    def test_trigger_source_dispatches_to_queue(self, client):
        from packages.storage.database import get_db_session

        mock_session = MagicMock()
        app.dependency_overrides[get_db_session] = lambda: mock_session

        try:
            with patch("apps.api.routers.sources.SourceRepository") as MockRepo:
                repo = MockRepo.return_value
                repo.get_by_id.return_value = MagicMock(id="source-1")

                with patch("packages.shared.queue.send_task", return_value="task-123"):
                    resp = client.post("/api/v1/sources/source-1/trigger")

                assert resp.status_code == 200
                data = resp.json()
                assert data["status"] == "dispatched"
                assert data["task_id"] == "task-123"
        finally:
            app.dependency_overrides.clear()

    def test_trigger_source_processes_inline_when_queue_missing(self, client):
        from packages.storage.database import get_db_session

        mock_session = MagicMock()
        app.dependency_overrides[get_db_session] = lambda: mock_session

        try:
            with patch("apps.api.routers.sources.SourceRepository") as MockRepo:
                repo = MockRepo.return_value
                repo.get_by_id.return_value = MagicMock(id="source-1")

                with patch("packages.shared.queue.send_task", side_effect=ValueError("No queue URL configured")):
                    with patch("apps.worker.tasks.scrape_source", return_value={"new": 1}):
                        resp = client.post("/api/v1/sources/source-1/trigger")

                assert resp.status_code == 200
                data = resp.json()
                assert data["status"] == "processed_inline"
                assert data["result"]["new"] == 1
        finally:
            app.dependency_overrides.clear()

    def test_trigger_source_returns_503_when_queue_dispatch_fails_unexpectedly(self, client):
        from packages.storage.database import get_db_session

        mock_session = MagicMock()
        app.dependency_overrides[get_db_session] = lambda: mock_session

        try:
            with patch("apps.api.routers.sources.SourceRepository") as MockRepo:
                repo = MockRepo.return_value
                repo.get_by_id.return_value = MagicMock(id="source-1")

                with patch("packages.shared.queue.send_task", side_effect=RuntimeError("SQS access denied")):
                    resp = client.post("/api/v1/sources/source-1/trigger")

                assert resp.status_code == 503
                body = resp.json()
                assert body["detail"]["code"] == "scrape_dispatch_failed"
                assert "dispatch scrape task" in body["detail"]["message"].lower()
        finally:
            app.dependency_overrides.clear()

    def test_trigger_source_inline_failure_is_not_reported_as_dispatch_failure(self, client):
        from packages.storage.database import get_db_session

        mock_session = MagicMock()
        app.dependency_overrides[get_db_session] = lambda: mock_session

        try:
            with patch("apps.api.routers.sources.SourceRepository") as MockRepo:
                repo = MockRepo.return_value
                repo.get_by_id.return_value = MagicMock(id="source-1")

                with patch("packages.shared.queue.send_task", side_effect=ValueError("No queue URL configured")):
                    with patch("apps.worker.tasks.scrape_source", side_effect=RuntimeError("inline scrape failed")):
                        with pytest.raises(RuntimeError, match="inline scrape failed"):
                            client.post("/api/v1/sources/source-1/trigger")
        finally:
            app.dependency_overrides.clear()

    def test_trigger_full_organic_search_dispatches_all_steps(self, client):
        from packages.storage.database import get_db_session

        mock_session = MagicMock()
        app.dependency_overrides[get_db_session] = lambda: mock_session

        try:
            with patch("packages.shared.queue.send_task") as mock_send_task:
                mock_send_task.side_effect = ["task-scrape", "task-alert", "task-llm"]
                with patch("apps.api.routers.sources.OrganicSearchRunRepository") as MockRunRepo:
                    run_repo = MockRunRepo.return_value
                    run_repo.create.return_value = MagicMock(id="run-123")

                    resp = client.post("/api/v1/sources/trigger-all")

            assert resp.status_code == 200
            data = resp.json()
            assert data["run_id"] == "run-123"
            assert data["status"] == "dispatched"
            assert len(data["steps"]) == 3
            assert data["steps"][0]["step"] == "scrape_all_sources"
            assert data["steps"][1]["step"] == "evaluate_alerts"
            assert data["steps"][2]["step"] == "enrich_batch_llm"
        finally:
            app.dependency_overrides.clear()

    def test_trigger_full_organic_search_processes_inline_when_queues_missing(self, client):
        from packages.storage.database import get_db_session

        mock_session = MagicMock()
        app.dependency_overrides[get_db_session] = lambda: mock_session

        try:
            with patch("packages.shared.queue.send_task", side_effect=ValueError("No queue URL configured")):
                with patch(
                    "apps.worker.tasks.scrape_all_sources",
                    return_value={
                        "dispatched": 3,
                        "discovery_during_scrape": {
                            "created": 1,
                            "existing": 2,
                            "skipped_invalid": 0,
                            "auto_enable": False,
                            "enabled": True,
                            "limit": 10,
                        },
                    },
                ):
                    with patch("apps.worker.tasks.evaluate_alerts", return_value={"evaluated": 2}):
                        with patch("apps.worker.tasks.enrich_batch_llm", return_value={"dispatched": 5}):
                            with patch("apps.api.routers.sources.OrganicSearchRunRepository") as MockRunRepo:
                                run_repo = MockRunRepo.return_value
                                run_repo.create.return_value = MagicMock(id="run-456")
                                resp = client.post("/api/v1/sources/trigger-all?llm_limit=5")

            assert resp.status_code == 200
            data = resp.json()
            assert data["run_id"] == "run-456"
            assert data["status"] == "processed_inline"
            assert len(data["steps"]) == 3
            assert data["steps"][0]["result"]["dispatched"] == 3
            assert data["steps"][0]["result"]["discovery_during_scrape"]["created"] == 1
            assert data["steps"][1]["result"]["evaluated"] == 2
            assert data["steps"][2]["result"]["dispatched"] == 5
        finally:
            app.dependency_overrides.clear()

    def test_trigger_full_organic_search_returns_503_on_unexpected_dispatch_failure(self, client):
        from packages.storage.database import get_db_session

        mock_session = MagicMock()
        app.dependency_overrides[get_db_session] = lambda: mock_session

        try:
            with patch("packages.shared.queue.send_task", side_effect=RuntimeError("SQS permissions invalid")):
                resp = client.post("/api/v1/sources/trigger-all")

            assert resp.status_code == 503
            body = resp.json()
            assert body["detail"]["code"] == "pipeline_dispatch_failed"
            assert body["detail"]["task_type"] == "scrape_all_sources"
        finally:
            app.dependency_overrides.clear()

    def test_trigger_full_organic_search_inline_failure_is_not_reported_as_dispatch_failure(self, client):
        from packages.storage.database import get_db_session

        mock_session = MagicMock()
        app.dependency_overrides[get_db_session] = lambda: mock_session

        try:
            with patch("packages.shared.queue.send_task", side_effect=ValueError("No queue URL configured")):
                with patch("apps.worker.tasks.scrape_all_sources", side_effect=RuntimeError("inline pipeline failed")):
                    with pytest.raises(RuntimeError, match="inline pipeline failed"):
                        client.post("/api/v1/sources/trigger-all")
        finally:
            app.dependency_overrides.clear()

    def test_trigger_full_organic_search_history(self, client):
        from datetime import UTC, datetime
        from packages.storage.database import get_db_session

        mock_session = MagicMock()
        app.dependency_overrides[get_db_session] = lambda: mock_session

        try:
            now = datetime.now(UTC)
            mock_run = MagicMock(
                id="run-1",
                status="dispatched",
                triggered_from="api_sources_trigger_all",
                options={"run_alerts": True},
                steps=[{"step": "scrape_all_sources", "status": "dispatched"}],
                error=None,
                created_at=now,
            )
            with patch("apps.api.routers.sources.OrganicSearchRunRepository") as MockRunRepo:
                run_repo = MockRunRepo.return_value
                run_repo.list_recent.return_value = [mock_run]

                resp = client.get("/api/v1/sources/trigger-all/history?limit=5")

            assert resp.status_code == 200
            data = resp.json()
            assert isinstance(data, list)
            assert len(data) == 1
            assert data[0]["id"] == "run-1"
            assert data[0]["status"] == "dispatched"
        finally:
            app.dependency_overrides.clear()

    def test_discover_sources_auto_creates_missing_sources(self, client):
        from packages.storage.database import get_db_session

        mock_session = MagicMock()
        app.dependency_overrides[get_db_session] = lambda: mock_session

        try:
            with patch("apps.api.routers.sources.get_adapter_names", return_value=["daft", "myhome", "propertypal"]):
                with patch("apps.api.routers.sources.load_discovery_candidates", return_value=[
                    {
                        "name": "Auto One",
                        "url": "https://example.com/a",
                        "adapter_type": "scraper",
                        "adapter_name": "daft",
                        "config": {},
                    }
                ]):
                    with patch("apps.api.routers.sources.SourceRepository") as MockRepo:
                        repo = MockRepo.return_value
                        repo.get_by_url.return_value = None
                        created_source = MagicMock(
                            id="source-new",
                            name="Auto One",
                            url="https://example.com/a",
                            adapter_type="scraper",
                            adapter_name="daft",
                            config={},
                            enabled=False,
                            poll_interval_seconds=21600,
                            tags=["auto_discovered", "pending_approval"],
                            last_polled_at=None,
                            last_success_at=None,
                            last_error=None,
                            error_count=0,
                            total_listings=0,
                            created_at=None,
                            updated_at=None,
                        )
                        repo.create.return_value = created_source

                        resp = client.post("/api/v1/sources/discover-auto")

            assert resp.status_code == 200
            data = resp.json()
            assert len(data["created"]) == 1
            assert data["created"][0]["id"] == "source-new"
            assert data["auto_enable"] is False
        finally:
            app.dependency_overrides.clear()

    def test_list_pending_discovered_sources(self, client):
        from packages.storage.database import get_db_session

        mock_session = MagicMock()
        app.dependency_overrides[get_db_session] = lambda: mock_session

        try:
            pending = MagicMock(
                id="pending-1",
                name="Pending Feed",
                url="https://example.com/pending",
                adapter_type="scraper",
                adapter_name="daft",
                config={},
                enabled=False,
                poll_interval_seconds=21600,
                tags=["auto_discovered", "pending_approval"],
                last_polled_at=None,
                last_success_at=None,
                last_error=None,
                error_count=0,
                total_listings=0,
                created_at=None,
                updated_at=None,
            )
            approved = MagicMock(
                id="approved-1",
                name="Approved Feed",
                url="https://example.com/approved",
                adapter_type="scraper",
                adapter_name="myhome",
                config={},
                enabled=True,
                poll_interval_seconds=21600,
                tags=["auto_discovered"],
                last_polled_at=None,
                last_success_at=None,
                last_error=None,
                error_count=0,
                total_listings=0,
                created_at=None,
                updated_at=None,
            )

            with patch("apps.api.routers.sources.SourceRepository") as MockRepo:
                repo = MockRepo.return_value
                repo.get_all.return_value = [pending, approved]

                resp = client.get("/api/v1/sources/discovery/pending")

            assert resp.status_code == 200
            data = resp.json()
            assert len(data) == 1
            assert data[0]["id"] == "pending-1"
        finally:
            app.dependency_overrides.clear()

    def test_approve_discovered_source(self, client):
        from packages.storage.database import get_db_session

        mock_session = MagicMock()
        app.dependency_overrides[get_db_session] = lambda: mock_session

        try:
            source = MagicMock(
                id="source-approve",
                name="Pending Feed",
                url="https://example.com/pending",
                adapter_type="scraper",
                adapter_name="daft",
                config={},
                enabled=False,
                poll_interval_seconds=21600,
                tags=["auto_discovered", "pending_approval"],
                last_polled_at=None,
                last_success_at=None,
                last_error=None,
                error_count=0,
                total_listings=0,
                created_at=None,
                updated_at=None,
            )

            with patch("apps.api.routers.sources.SourceRepository") as MockRepo:
                repo = MockRepo.return_value
                repo.get_by_id.return_value = source
                updated = MagicMock(
                    id="source-approve",
                    name="Pending Feed",
                    url="https://example.com/pending",
                    adapter_type="scraper",
                    adapter_name="daft",
                    config={},
                    enabled=True,
                    poll_interval_seconds=21600,
                    tags=["auto_discovered"],
                    last_polled_at=None,
                    last_success_at=None,
                    last_error=None,
                    error_count=0,
                    total_listings=0,
                    created_at=None,
                    updated_at=None,
                )
                repo.update.return_value = updated

                resp = client.post("/api/v1/sources/source-approve/approve-discovered")

            assert resp.status_code == 200
            data = resp.json()
            assert data["enabled"] is True
            assert "pending_approval" not in data["tags"]
        finally:
            app.dependency_overrides.clear()

    def test_discover_sources_full_returns_503_on_dispatch_failure(self, client):
        from packages.storage.database import get_db_session

        mock_session = MagicMock()
        app.dependency_overrides[get_db_session] = lambda: mock_session

        try:
            with patch("packages.shared.queue.send_task", side_effect=RuntimeError("SQS down")):
                resp = client.post("/api/v1/sources/discover-full")

            assert resp.status_code == 503
            detail = resp.json()["detail"]
            assert detail["code"] == "discovery_dispatch_failed"
            assert "full discovery task" in detail["message"].lower()
        finally:
            app.dependency_overrides.clear()

    def test_preview_discovery_candidates_filters_by_score(self, client):
        candidate_low = MagicMock(
            candidate={"name": "Low", "url": "https://low", "adapter_name": "daft", "adapter_type": "scraper"},
            score=0.2,
            activation="reject",
            reasons=["low confidence"],
        )
        candidate_high = MagicMock(
            candidate={"name": "High", "url": "https://high", "adapter_name": "daft", "adapter_type": "scraper"},
            score=0.9,
            activation="enable",
            reasons=["strong signal"],
        )

        with patch(
            "apps.api.routers.sources.load_all_discovery_candidates",
            return_value=[candidate_low, candidate_high],
        ):
            resp = client.get("/api/v1/sources/discover-full/preview?min_score=0.5&limit=10")

        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["shown"] == 1
        assert data["candidates"][0]["name"] == "High"


class TestGrantsEndpoint:
    def test_list_grants(self, client):
        from packages.storage.database import get_db_session

        mock_session = MagicMock()
        app.dependency_overrides[get_db_session] = lambda: mock_session

        try:
            with patch("apps.api.routers.grants.grants_list", return_value=[]) as mock_list:
                resp = client.get("/api/v1/grants")
                assert resp.status_code == 200
                assert resp.json() == []
                mock_list.assert_called_once_with(mock_session, country=None, active_only=True)
        finally:
            app.dependency_overrides.clear()

    def test_evaluate_property_grants(self, client):
        from packages.storage.database import get_db_session

        mock_session = MagicMock()
        app.dependency_overrides[get_db_session] = lambda: mock_session

        try:
            with patch("apps.api.routers.grants.PropertyRepository") as MockPropertyRepo:
                prop_repo = MockPropertyRepo.return_value
                prop_repo.get_by_id.return_value = MagicMock(id="prop-1")

                with patch("apps.api.routers.grants.evaluate_property_grants", return_value=[MagicMock(), MagicMock()]):
                    resp = client.post("/api/v1/grants/property/prop-1/evaluate")

                assert resp.status_code == 200
                data = resp.json()
                assert data["property_id"] == "prop-1"
                assert data["matches"] == 2
                assert data["status"] == "evaluated"
        finally:
            app.dependency_overrides.clear()

    def test_get_property_grants(self, client):
        from packages.storage.database import get_db_session

        mock_session = MagicMock()
        app.dependency_overrides[get_db_session] = lambda: mock_session

        try:
            with patch("apps.api.routers.grants.grants_property", return_value=[]) as mock_grants_property:
                resp = client.get("/api/v1/grants/property/prop-1")

                assert resp.status_code == 200
                assert resp.json() == []
                mock_grants_property.assert_called_once_with(mock_session, "prop-1")
        finally:
            app.dependency_overrides.clear()

    def test_discover_grant_programs(self, client):
        with patch(
            "apps.api.routers.grants.grants_discover",
            return_value={"candidates_found": 3, "created": 1, "existing": 2, "dry_run": True},
        ) as mock_discover:
            resp = client.post("/api/v1/grants/discover?dry_run=true")

            assert resp.status_code == 200
            assert resp.json()["candidates_found"] == 3
            mock_discover.assert_called_once_with(dry_run=True)

    def test_list_discovered_grants(self, client):
        from packages.storage.database import get_db_session

        mock_session = MagicMock()
        app.dependency_overrides[get_db_session] = lambda: mock_session

        try:
            with patch("apps.api.routers.grants.grants_list_discovered", return_value=[]) as mock_list:
                resp = client.get("/api/v1/grants/discovered/pending")

                assert resp.status_code == 200
                assert resp.json() == []
                mock_list.assert_called_once_with(mock_session)
        finally:
            app.dependency_overrides.clear()

    def test_activate_discovered_grant_404(self, client):
        from packages.grants.service import GrantNotFoundError
        from packages.storage.database import get_db_session

        mock_session = MagicMock()
        app.dependency_overrides[get_db_session] = lambda: mock_session

        try:
            with patch(
                "apps.api.routers.grants.grants_activate_discovered",
                side_effect=GrantNotFoundError("g-404"),
            ):
                resp = client.post("/api/v1/grants/g-404/activate")

                assert resp.status_code == 404
                assert "Grant not found" in resp.text
        finally:
            app.dependency_overrides.clear()


class TestLLMChatEndpoint:
    def test_chat_message_round_trip(self, client):
        from packages.storage.database import get_db_session

        mock_session = MagicMock()
        app.dependency_overrides[get_db_session] = lambda: mock_session

        try:
            with patch("apps.api.routers.llm.ConversationRepository") as MockConvoRepo:
                with patch("apps.api.routers.llm.PropertyRepository") as MockPropRepo:
                    with patch("packages.ai.service.get_provider") as mock_get_provider:
                        convo_repo = MockConvoRepo.return_value
                        prop_repo = MockPropRepo.return_value

                        convo_repo.get_conversation.return_value = MagicMock(
                            id="conv-1",
                            title="Test",
                            user_identifier="user-1",
                            context={},
                            created_at=None,
                            updated_at=None,
                            messages=[],
                        )

                        user_msg = MagicMock(
                            id="msg-user",
                            conversation_id="conv-1",
                            role="user",
                            content="hello",
                            citations=[],
                            prompt_tokens=None,
                            completion_tokens=None,
                            total_tokens=None,
                            processing_time_ms=None,
                            created_at=None,
                        )
                        assistant_msg = MagicMock(
                            id="msg-assistant",
                            conversation_id="conv-1",
                            role="assistant",
                            content="Hi there",
                            citations=[],
                            prompt_tokens=10,
                            completion_tokens=15,
                            total_tokens=25,
                            processing_time_ms=120,
                            created_at=None,
                        )
                        convo_repo.add_message.side_effect = [user_msg, assistant_msg]
                        prop_repo.get_by_id.return_value = None

                        mock_provider = MagicMock()
                        mock_provider.generate = AsyncMock(return_value=MagicMock(
                            content="Hi there",
                            prompt_tokens=10,
                            completion_tokens=15,
                            total_tokens=25,
                            processing_time_ms=120,
                        ))
                        mock_get_provider.return_value = mock_provider

                        resp = client.post(
                            "/api/v1/llm/chat/conversations/conv-1/messages",
                            json={"content": "hello"},
                        )
                        assert resp.status_code == 200
                        data = resp.json()
                        assert data["conversation_id"] == "conv-1"
                        assert data["assistant_message"]["content"] == "Hi there"
        finally:
            app.dependency_overrides.clear()


class TestLLMCompareSetEndpoint:
    def test_compare_set(self, client):
        from packages.storage.database import get_db_session

        mock_session = MagicMock()
        app.dependency_overrides[get_db_session] = lambda: mock_session

        try:
            with patch("apps.api.routers.llm.PropertyRepository") as MockPropRepo:
                with patch("apps.api.routers.llm.LLMEnrichmentRepository") as MockEnrichRepo:
                    with patch("apps.api.routers.llm.PropertyGrantMatchRepository") as MockGrantRepo:
                        with patch("packages.ai.service.get_provider") as mock_get_provider:
                            prop_repo = MockPropRepo.return_value
                            enrich_repo = MockEnrichRepo.return_value
                            grant_repo = MockGrantRepo.return_value

                            prop_repo.get_by_id.side_effect = [
                                MagicMock(
                                    id="p1",
                                    title="Home 1",
                                    address="Addr 1",
                                    county="Dublin",
                                    url="https://example.com/1",
                                    price=450000,
                                    floor_area_sqm=100,
                                    bedrooms=3,
                                    bathrooms=2,
                                    ber_rating="B2",
                                    images=[{"url": "https://img/1.jpg"}],
                                ),
                                MagicMock(
                                    id="p2",
                                    title="Home 2",
                                    address="Addr 2",
                                    county="Cork",
                                    url="https://example.com/2",
                                    price=430000,
                                    floor_area_sqm=95,
                                    bedrooms=3,
                                    bathrooms=2,
                                    ber_rating="C1",
                                    images=[{"url": "https://img/2.jpg"}],
                                ),
                            ]

                            enrich_repo.get_by_property_id.side_effect = [
                                MagicMock(value_score=7.6),
                                MagicMock(value_score=7.1),
                            ]
                            grant_repo.list_for_property.return_value = []

                            mock_provider = MagicMock()
                            mock_provider.generate = AsyncMock(return_value=MagicMock(
                                content=(
                                    '{"headline":"Value result",'
                                    '"recommendation":"p1 wins",'
                                    '"key_tradeoffs":["higher price"],'
                                    '"confidence":"medium"}'
                                ),
                            ))
                            mock_get_provider.return_value = mock_provider

                            resp = client.post(
                                "/api/v1/llm/compare-set",
                                json={
                                    "property_ids": ["p1", "p2"],
                                    "ranking_mode": "hybrid",
                                },
                            )
                            assert resp.status_code == 200
                            data = resp.json()
                            assert data["ranking_mode"] == "hybrid"
                            assert len(data["properties"]) == 2
                            assert data["analysis"]["headline"] == "Value result"
        finally:
            app.dependency_overrides.clear()

    def test_compare_set_fail_fast_when_llm_unavailable(self, client):
        from packages.storage.database import get_db_session

        mock_session = MagicMock()
        app.dependency_overrides[get_db_session] = lambda: mock_session

        try:
            with patch("apps.api.routers.llm.PropertyRepository") as MockPropRepo:
                with patch("apps.api.routers.llm.LLMEnrichmentRepository") as MockEnrichRepo:
                    with patch("apps.api.routers.llm.PropertyGrantMatchRepository") as MockGrantRepo:
                        with patch("packages.ai.service.get_provider") as mock_get_provider:
                            prop_repo = MockPropRepo.return_value
                            enrich_repo = MockEnrichRepo.return_value
                            grant_repo = MockGrantRepo.return_value

                            prop_repo.get_by_id.side_effect = [
                                MagicMock(id="p1", title="Home 1", address="Addr 1", county="Dublin", url="https://example.com/1", price=450000, floor_area_sqm=100, bedrooms=3, bathrooms=2, ber_rating="B2", images=[]),
                                MagicMock(id="p2", title="Home 2", address="Addr 2", county="Cork", url="https://example.com/2", price=430000, floor_area_sqm=95, bedrooms=3, bathrooms=2, ber_rating="C1", images=[]),
                            ]
                            enrich_repo.get_by_property_id.side_effect = [MagicMock(value_score=7.0), MagicMock(value_score=6.8)]
                            grant_repo.list_for_property.return_value = []

                            mock_provider = MagicMock()
                            mock_provider.generate = AsyncMock(side_effect=RuntimeError("bedrock_configuration_error: invoke failed"))
                            mock_get_provider.return_value = mock_provider

                            resp = client.post(
                                "/api/v1/llm/compare-set",
                                json={"property_ids": ["p1", "p2"], "ranking_mode": "hybrid"},
                            )

                            assert resp.status_code == 503
                            body = resp.json()
                            assert body["detail"]["code"] == "llm_analysis_unavailable"
                            assert "could not be invoked" in body["detail"]["message"]
        finally:
            app.dependency_overrides.clear()

    def test_auto_compare_persists_run_and_returns_result(self, client):
        from packages.storage.database import get_db_session

        mock_session = MagicMock()
        app.dependency_overrides[get_db_session] = lambda: mock_session

        try:
            with patch("apps.api.routers.llm.PropertyRepository") as MockPropRepo:
                with patch("apps.api.routers.llm.LLMEnrichmentRepository") as MockEnrichRepo:
                    with patch("apps.api.routers.llm.PropertyGrantMatchRepository") as MockGrantRepo:
                        with patch("apps.api.routers.llm.OrganicSearchRunRepository") as MockRunRepo:
                            with patch("packages.ai.service.get_provider") as mock_get_provider:
                                prop_repo = MockPropRepo.return_value
                                enrich_repo = MockEnrichRepo.return_value
                                grant_repo = MockGrantRepo.return_value
                                run_repo = MockRunRepo.return_value

                                prop_repo.get_by_id.side_effect = [
                                    MagicMock(id="p1", title="Home 1", address="Addr 1", county="Dublin", url="https://example.com/1", price=450000, floor_area_sqm=100, bedrooms=3, bathrooms=2, ber_rating="B2", images=[]),
                                    MagicMock(id="p2", title="Home 2", address="Addr 2", county="Cork", url="https://example.com/2", price=430000, floor_area_sqm=95, bedrooms=3, bathrooms=2, ber_rating="C1", images=[]),
                                ]
                                enrich_repo.get_by_property_id.side_effect = [MagicMock(value_score=7.0), MagicMock(value_score=6.8)]
                                grant_repo.list_for_property.return_value = []
                                run_repo.get_latest_for_session.return_value = None
                                run_repo.create.return_value = MagicMock(id="run-123")

                                mock_provider = MagicMock()
                                mock_provider.generate = AsyncMock(return_value=MagicMock(
                                    content='{"headline":"Auto compare","recommendation":"p1","key_tradeoffs":[],"confidence":"medium"}'
                                ))
                                mock_get_provider.return_value = mock_provider

                                resp = client.post(
                                    "/api/v1/llm/auto-compare",
                                    json={
                                        "session_id": "session-1",
                                        "property_ids": ["p1", "p2"],
                                        "ranking_mode": "hybrid",
                                        "search_context": {"query": "dublin"},
                                    },
                                )

                                assert resp.status_code == 200
                                data = resp.json()
                                assert data["session_id"] == "session-1"
                                assert data["result"]["ranking_mode"] == "hybrid"
                                assert data["cached"] is False
                                run_repo.create.assert_called()
                                persisted_steps = run_repo.create.call_args.kwargs["steps"]
                                assert persisted_steps[0]["step"] == "compare_property_set"
                                assert persisted_steps[0]["result"]["ranking_mode"] == "hybrid"
        finally:
            app.dependency_overrides.clear()

    def test_auto_compare_uses_cached_run_when_inputs_match(self, client):
        from packages.storage.database import get_db_session

        mock_session = MagicMock()
        app.dependency_overrides[get_db_session] = lambda: mock_session

        try:
            with patch("apps.api.routers.llm.PropertyRepository") as MockPropRepo:
                with patch("apps.api.routers.llm.OrganicSearchRunRepository") as MockRunRepo:
                    prop_repo = MockPropRepo.return_value
                    run_repo = MockRunRepo.return_value

                    run_repo.get_latest_for_session.return_value = MagicMock(
                        id="run-cached",
                        status="completed",
                        options={
                            "session_id": "session-1",
                            "ranking_mode": "hybrid",
                            "property_ids": ["p1", "p2"],
                        },
                        steps=[
                            {
                                "step": "compare_property_set",
                                "status": "completed",
                                "result": {
                                    "ranking_mode": "hybrid",
                                    "properties": [{"property_id": "p1"}, {"property_id": "p2"}],
                                    "winner_property_id": "p1",
                                    "analysis": {
                                        "headline": "Cached",
                                        "recommendation": "p1",
                                        "key_tradeoffs": [],
                                        "confidence": "medium",
                                        "citations": [],
                                    },
                                },
                            }
                        ],
                    )

                    resp = client.post(
                        "/api/v1/llm/auto-compare",
                        json={
                            "session_id": "session-1",
                            "property_ids": ["p1", "p2"],
                            "ranking_mode": "hybrid",
                        },
                    )

                    assert resp.status_code == 200
                    data = resp.json()
                    assert data["run_id"] == "run-cached"
                    assert data["cached"] is True
                    assert data["result"]["winner_property_id"] == "p1"
                    prop_repo.get_by_id.assert_not_called()
                    run_repo.create.assert_not_called()
        finally:
            app.dependency_overrides.clear()

    def test_auto_compare_does_not_use_cached_run_when_search_context_differs(self, client):
        from packages.storage.database import get_db_session

        mock_session = MagicMock()
        app.dependency_overrides[get_db_session] = lambda: mock_session

        try:
            with patch("apps.api.routers.llm.PropertyRepository") as MockPropRepo:
                with patch("apps.api.routers.llm.LLMEnrichmentRepository") as MockEnrichRepo:
                    with patch("apps.api.routers.llm.PropertyGrantMatchRepository") as MockGrantRepo:
                        with patch("apps.api.routers.llm.OrganicSearchRunRepository") as MockRunRepo:
                            with patch("packages.ai.service.get_provider") as mock_get_provider:
                                prop_repo = MockPropRepo.return_value
                                enrich_repo = MockEnrichRepo.return_value
                                grant_repo = MockGrantRepo.return_value
                                run_repo = MockRunRepo.return_value

                                run_repo.get_latest_for_session.return_value = MagicMock(
                                    id="run-cached",
                                    status="completed",
                                    options={
                                        "session_id": "session-1",
                                        "ranking_mode": "hybrid",
                                        "property_ids": ["p1", "p2"],
                                        "search_context": {"filters": {"max_price": 600000}},
                                    },
                                    steps=[
                                        {
                                            "step": "compare_property_set",
                                            "status": "completed",
                                            "result": {
                                                "ranking_mode": "hybrid",
                                                "properties": [{"property_id": "p1"}, {"property_id": "p2"}],
                                                "winner_property_id": "p1",
                                                "analysis": {
                                                    "headline": "Cached",
                                                    "recommendation": "p1",
                                                    "key_tradeoffs": [],
                                                    "confidence": "medium",
                                                    "citations": [],
                                                },
                                            },
                                        }
                                    ],
                                )
                                run_repo.create.return_value = MagicMock(id="run-fresh")

                                prop_repo.get_by_id.side_effect = [
                                    MagicMock(id="p1", title="Home 1", address="Addr 1", county="Dublin", url="https://example.com/1", price=450000, floor_area_sqm=100, bedrooms=3, bathrooms=2, ber_rating="B2", images=[]),
                                    MagicMock(id="p2", title="Home 2", address="Addr 2", county="Cork", url="https://example.com/2", price=430000, floor_area_sqm=95, bedrooms=3, bathrooms=2, ber_rating="C1", images=[]),
                                ]
                                enrich_repo.get_by_property_id.side_effect = [MagicMock(value_score=7.0), MagicMock(value_score=6.8)]
                                grant_repo.list_for_property.return_value = []

                                mock_provider = MagicMock()
                                mock_provider.generate = AsyncMock(return_value=MagicMock(
                                    content='{"headline":"Fresh compare","recommendation":"p1","key_tradeoffs":[],"confidence":"medium"}'
                                ))
                                mock_get_provider.return_value = mock_provider

                                resp = client.post(
                                    "/api/v1/llm/auto-compare",
                                    json={
                                        "session_id": "session-1",
                                        "property_ids": ["p1", "p2"],
                                        "ranking_mode": "hybrid",
                                        "search_context": {"filters": {"max_price": 500000}},
                                    },
                                )

                                assert resp.status_code == 200
                                data = resp.json()
                                assert data["cached"] is False
                                run_repo.create.assert_called_once()
        finally:
            app.dependency_overrides.clear()

    def test_auto_compare_latest_returns_run(self, client):
        from packages.storage.database import get_db_session

        mock_session = MagicMock()
        app.dependency_overrides[get_db_session] = lambda: mock_session

        try:
            with patch("apps.api.routers.llm.OrganicSearchRunRepository") as MockRunRepo:
                run_repo = MockRunRepo.return_value
                run_repo.get_latest_for_session.return_value = MagicMock(
                    id="run-1",
                    status="completed",
                    options={"session_id": "session-1"},
                    steps=[
                        {
                            "step": "compare_property_set",
                            "status": "completed",
                            "result": {
                                "ranking_mode": "hybrid",
                                "properties": [{"property_id": "p1"}, {"property_id": "p2"}],
                                "winner_property_id": "p1",
                                "analysis": {
                                    "headline": "Auto compare",
                                    "recommendation": "p1",
                                    "key_tradeoffs": [],
                                    "confidence": "medium",
                                    "citations": [],
                                },
                            },
                        }
                    ],
                    error=None,
                    created_at=datetime(2026, 1, 1, 12, 0, 0),
                )

                resp = client.get("/api/v1/llm/auto-compare/latest?session_id=session-1")
                assert resp.status_code == 200
                data = resp.json()
                assert data["run_id"] == "run-1"
                assert data["status"] == "completed"
                assert data["result"]["winner_property_id"] == "p1"
                run_repo.get_latest_for_session.assert_called_once_with(
                    session_id="session-1",
                    triggered_from="auto_compare",
                )
        finally:
            app.dependency_overrides.clear()

    def test_auto_compare_latest_handles_legacy_run_without_result(self, client):
        from packages.storage.database import get_db_session

        mock_session = MagicMock()
        app.dependency_overrides[get_db_session] = lambda: mock_session

        try:
            with patch("apps.api.routers.llm.OrganicSearchRunRepository") as MockRunRepo:
                run_repo = MockRunRepo.return_value
                run_repo.get_latest_for_session.return_value = MagicMock(
                    id="run-legacy",
                    status="completed",
                    options={"session_id": "session-legacy", "ranking_mode": "hybrid"},
                    steps=[{"step": "compare_property_set", "status": "completed"}],
                    error=None,
                    created_at=datetime(2026, 1, 2, 8, 30, 0),
                )

                resp = client.get("/api/v1/llm/auto-compare/latest?session_id=session-legacy")
                assert resp.status_code == 200
                data = resp.json()
                assert data["run_id"] == "run-legacy"
                assert data["status"] == "completed"
                assert data["result"] is None
        finally:
            app.dependency_overrides.clear()

    def test_auto_compare_rejects_invalid_ranking_mode(self, client):
        from packages.storage.database import get_db_session

        mock_session = MagicMock()
        app.dependency_overrides[get_db_session] = lambda: mock_session

        try:
            resp = client.post(
                "/api/v1/llm/auto-compare",
                json={
                    "session_id": "session-1",
                    "property_ids": ["p1", "p2"],
                    "ranking_mode": "invalid_mode",
                },
            )
            assert resp.status_code == 422
        finally:
            app.dependency_overrides.clear()

    def test_auto_compare_rejects_too_few_properties(self, client):
        from packages.storage.database import get_db_session

        mock_session = MagicMock()
        app.dependency_overrides[get_db_session] = lambda: mock_session

        try:
            resp = client.post(
                "/api/v1/llm/auto-compare",
                json={
                    "session_id": "session-1",
                    "property_ids": ["p1"],
                    "ranking_mode": "hybrid",
                },
            )
            assert resp.status_code == 422
        finally:
            app.dependency_overrides.clear()


class TestLLMEnrichmentDispatch:
    def test_update_llm_config_warns_for_nova_without_inference_profile(self, client):
        with patch("apps.api.routers.llm.settings.bedrock_inference_profile_id", ""):
            with patch("packages.ai.service.set_active_provider", return_value=True):
                resp = client.put(
                    "/api/v1/llm/config",
                    json={"provider": "bedrock", "bedrock_model": "amazon.nova-pro-v1:0"},
                )

                assert resp.status_code == 200
                data = resp.json()
                assert data["updated"] is True
                assert data["inference_profile_configured"] is False
                assert "inference_profile" in (data.get("warning") or "").lower()

    def test_llm_health_reports_queue_unconfigured(self, client):
        with patch("apps.api.routers.llm.settings.llm_enabled", True):
            with patch("apps.api.routers.llm.settings.llm_queue_url", ""):
                with patch("apps.api.routers.llm.os.environ", {}):
                    with patch("packages.ai.service.get_provider") as mock_get_provider:
                        mock_provider = MagicMock()
                        mock_provider.get_provider_name.return_value = "bedrock"
                        mock_provider.get_model_name.return_value = "anthropic.claude-3-haiku-20240307-v1:0"
                        mock_provider.health_check = AsyncMock(return_value=True)
                        mock_get_provider.return_value = mock_provider

                        resp = client.get("/api/v1/llm/health")
                        assert resp.status_code == 200
                        data = resp.json()
                        assert data["enabled"] is True
                        assert data["queue_configured"] is False
                        assert data["ready_for_enrichment"] is False
                        assert data["reason"] == "llm_queue_unconfigured"

    def test_enrich_disabled_returns_503(self, client):
        from packages.storage.database import get_db_session

        mock_session = MagicMock()
        app.dependency_overrides[get_db_session] = lambda: mock_session

        try:
            with patch("apps.api.routers.llm.settings.llm_enabled", False):
                resp = client.post("/api/v1/llm/enrich/p-1")
                assert resp.status_code == 503
                assert "disabled" in resp.text.lower()
        finally:
            app.dependency_overrides.clear()

    def test_enrich_queue_misconfigured_falls_back_inline(self, client):
        from packages.storage.database import get_db_session

        mock_session = MagicMock()
        app.dependency_overrides[get_db_session] = lambda: mock_session

        try:
            with patch("apps.api.routers.llm.settings.llm_enabled", True):
                with patch("apps.api.routers.llm.settings.llm_queue_url", ""):
                    with patch("apps.api.routers.llm.os.environ", {}):
                        with patch("apps.api.routers.llm.PropertyRepository") as MockRepo:
                            repo = MockRepo.return_value
                            repo.get_by_id.return_value = MagicMock(id="p-1")
                            with patch("packages.shared.queue.send_task", side_effect=ValueError("No queue URL configured for 'llm'. Set the env var.")):
                                with patch("apps.worker.tasks.enrich_property_llm", return_value={"property_id": "p-1", "enriched": True}):
                                    resp = client.post("/api/v1/llm/enrich/p-1")

                        assert resp.status_code == 200
                        body = resp.json()
                        assert body["status"] == "processed_inline"
                        assert body["result"]["property_id"] == "p-1"
        finally:
            app.dependency_overrides.clear()

    def test_enrich_dispatch_failure_returns_503(self, client):
        from packages.storage.database import get_db_session

        mock_session = MagicMock()
        app.dependency_overrides[get_db_session] = lambda: mock_session

        try:
            with patch("apps.api.routers.llm.settings.llm_enabled", True):
                with patch("apps.api.routers.llm.PropertyRepository") as MockRepo:
                    repo = MockRepo.return_value
                    repo.get_by_id.return_value = MagicMock(id="p-1")
                    with patch("packages.shared.queue.send_task", side_effect=RuntimeError("SQS access denied")):
                        resp = client.post("/api/v1/llm/enrich/p-1")

                    assert resp.status_code == 503
                    body = resp.json()
                    assert body["detail"]["code"] == "llm_dispatch_failed"
                    assert body["detail"]["task_type"] == "enrich_property_llm"
        finally:
            app.dependency_overrides.clear()

    def test_enrich_inline_failure_is_not_reported_as_dispatch_failure(self, client):
        from packages.storage.database import get_db_session

        mock_session = MagicMock()
        app.dependency_overrides[get_db_session] = lambda: mock_session

        try:
            with patch("apps.api.routers.llm.settings.llm_enabled", True):
                with patch("apps.api.routers.llm.settings.llm_queue_url", ""):
                    with patch("apps.api.routers.llm.os.environ", {}):
                        with patch("apps.api.routers.llm.PropertyRepository") as MockRepo:
                            repo = MockRepo.return_value
                            repo.get_by_id.return_value = MagicMock(id="p-1")
                            with patch(
                                "packages.shared.queue.send_task",
                                side_effect=ValueError("No queue URL configured for 'llm'. Set the env var."),
                            ):
                                with patch(
                                    "apps.worker.tasks.enrich_property_llm",
                                    side_effect=RuntimeError("inline task failed"),
                                ):
                                    with pytest.raises(RuntimeError, match="inline task failed"):
                                        client.post("/api/v1/llm/enrich/p-1")
        finally:
            app.dependency_overrides.clear()

    def test_enrich_dispatch_success(self, client):
        from packages.storage.database import get_db_session

        mock_session = MagicMock()
        app.dependency_overrides[get_db_session] = lambda: mock_session

        try:
            with patch("apps.api.routers.llm.settings.llm_enabled", True):
                with patch("apps.api.routers.llm.settings.llm_queue_url", "https://sqs.example/llm"):
                    with patch("apps.api.routers.llm.PropertyRepository") as MockRepo:
                        repo = MockRepo.return_value
                        repo.get_by_id.return_value = MagicMock(id="p-1")
                        with patch("packages.shared.queue.send_task") as mock_send_task:
                            mock_send_task.return_value = "msg-123"
                            resp = client.post("/api/v1/llm/enrich/p-1")
                            assert resp.status_code == 200
                            data = resp.json()
                            assert data["task_id"] == "msg-123"
                            assert data["status"] == "dispatched"
        finally:
            app.dependency_overrides.clear()

    def test_enrich_batch_queue_misconfigured_falls_back_inline(self, client):
        with patch("apps.api.routers.llm.settings.llm_enabled", True):
            with patch("apps.api.routers.llm.settings.llm_queue_url", ""):
                with patch("apps.api.routers.llm.os.environ", {}):
                    with patch("packages.shared.queue.send_task", side_effect=ValueError("No queue URL configured for 'llm'. Set the env var.")):
                        with patch("apps.worker.tasks.enrich_batch_llm", return_value={"dispatched": 3}):
                            resp = client.post("/api/v1/llm/enrich-batch?limit=3")

                    assert resp.status_code == 200
                    body = resp.json()
                    assert body["status"] == "processed_inline"
                    assert body["result"]["dispatched"] == 3
                    assert body["limit"] == 3

    def test_enrich_batch_dispatch_failure_returns_503(self, client):
        with patch("apps.api.routers.llm.settings.llm_enabled", True):
            with patch("apps.api.routers.llm.settings.llm_queue_url", "https://sqs.example/llm"):
                with patch("packages.shared.queue.send_task", side_effect=RuntimeError("SQS permissions invalid")):
                    resp = client.post("/api/v1/llm/enrich-batch?limit=5")

                assert resp.status_code == 503
                body = resp.json()
                assert body["detail"]["code"] == "llm_dispatch_failed"
                assert body["detail"]["task_type"] == "enrich_batch_llm"
