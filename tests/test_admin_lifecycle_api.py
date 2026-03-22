"""API tests for admin data lifecycle endpoints."""

from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from apps.api.main import app


def _client() -> TestClient:
    return TestClient(app)


def test_get_data_lifecycle_report_endpoint():
    from packages.storage.database import get_db_session

    mock_session = MagicMock()
    app.dependency_overrides[get_db_session] = lambda: mock_session

    try:
        with patch("apps.api.routers.admin.data_lifecycle_report") as mock_report:
            mock_report.return_value = {
                "checked_at": "2026-03-22T00:00:00+00:00",
                "cutoffs": {
                    "property_archive_before": "2025-03-22T00:00:00+00:00",
                    "backend_log_archive_before": "2025-12-22T00:00:00+00:00",
                    "rollup_before": "2025-09-22T00:00:00+00:00",
                },
                "candidates": {
                    "property_archive": 11,
                    "backend_log_archive": 80,
                    "price_history_rollup": 510,
                    "timeline_rollup": 390,
                },
                "actions": [
                    {"id": "archive_properties", "description": "...", "dry_run": True}
                ],
            }

            client = _client()
            resp = client.get(
                "/api/v1/admin/data-lifecycle/report?property_archive_days=400&backend_log_archive_days=120&rollup_days=200"
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["candidates"]["property_archive"] == 11
        mock_report.assert_called_once_with(
            mock_session,
            property_archive_days=400,
            backend_log_archive_days=120,
            rollup_days=200,
        )
    finally:
        app.dependency_overrides.clear()


def test_execute_data_lifecycle_action_endpoint():
    from packages.storage.database import get_db_session

    mock_session = MagicMock()
    app.dependency_overrides[get_db_session] = lambda: mock_session

    try:
        with patch("apps.api.routers.admin.run_data_lifecycle_action") as mock_run:
            mock_run.return_value = {
                "status": "dry_run_completed",
                "action": "archive_properties",
                "dry_run": True,
                "executed_at": "2026-03-22T00:00:00+00:00",
                "affected_candidates": 11,
                "report": {
                    "checked_at": "2026-03-22T00:00:00+00:00",
                    "cutoffs": {},
                    "candidates": {},
                    "actions": [],
                },
            }

            client = _client()
            resp = client.post(
                "/api/v1/admin/data-lifecycle/actions/archive_properties?dry_run=true&property_archive_days=365"
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "dry_run_completed"
        assert data["action"] == "archive_properties"
        mock_run.assert_called_once_with(
            mock_session,
            action="archive_properties",
            dry_run=True,
            property_archive_days=365,
            backend_log_archive_days=90,
            rollup_days=180,
        )
    finally:
        app.dependency_overrides.clear()


def test_execute_data_lifecycle_action_returns_400_for_invalid_action():
    from packages.storage.database import get_db_session

    mock_session = MagicMock()
    app.dependency_overrides[get_db_session] = lambda: mock_session

    try:
        client = _client()
        resp = client.post("/api/v1/admin/data-lifecycle/actions/not-a-real-action?dry_run=true")
        assert resp.status_code == 400
    finally:
        app.dependency_overrides.clear()


def test_get_data_lifecycle_history_endpoint():
    from packages.storage.database import get_db_session

    mock_session = MagicMock()
    app.dependency_overrides[get_db_session] = lambda: mock_session

    try:
        with patch("apps.api.routers.admin.list_data_lifecycle_activity") as mock_history:
            mock_history.return_value = [
                {
                    "id": "log-1",
                    "timestamp": "2026-03-22T00:00:00+00:00",
                    "level": "INFO",
                    "event_type": "admin_data_lifecycle_action",
                    "component": "api",
                    "source_id": None,
                    "message": "Lifecycle action dry-run executed: archive_properties",
                    "context": {
                        "action": "archive_properties",
                        "dry_run": True,
                        "affected_candidates": 11,
                    },
                }
            ]

            client = _client()
            resp = client.get("/api/v1/admin/data-lifecycle/history?hours=48&limit=20")

        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["event_type"] == "admin_data_lifecycle_action"
        mock_history.assert_called_once_with(mock_session, hours=48, limit=20)
    finally:
        app.dependency_overrides.clear()


def test_get_data_lifecycle_schedule_endpoint():
    from packages.storage.database import get_db_session

    mock_session = MagicMock()
    app.dependency_overrides[get_db_session] = lambda: mock_session

    try:
        with patch("apps.api.routers.admin.data_lifecycle_schedule_metadata") as mock_schedule:
            mock_schedule.return_value = {
                "checked_at": "2026-03-22T00:00:00+00:00",
                "execution_mode": {
                    "destructive_enabled": False,
                    "dry_run_only": True,
                    "note": "dry-run only",
                },
                "cadence": {
                    "source_scrape_interval_seconds": 21600,
                    "rss_poll_interval_seconds": 3600,
                    "ppr_poll_interval_seconds": 86400,
                    "lifecycle_action_trigger": "manual_admin_dry_run",
                },
                "policy": {
                    "backend_log_retention_days": 7,
                    "default_property_archive_days": 365,
                    "default_rollup_days": 180,
                },
                "last_lifecycle_run": None,
            }

            client = _client()
            resp = client.get("/api/v1/admin/data-lifecycle/schedule")

        assert resp.status_code == 200
        data = resp.json()
        assert data["execution_mode"]["dry_run_only"] is True
        assert data["cadence"]["source_scrape_interval_seconds"] == 21600
        assert data["policy"]["backend_log_retention_days"] == 7
        mock_schedule.assert_called_once()
    finally:
        app.dependency_overrides.clear()
