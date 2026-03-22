"""API tests for source adapter config validation."""

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from apps.api.main import app


@pytest.fixture
def client():
    return TestClient(app)


def test_create_source_rejects_invalid_adapter_config(client):
    from packages.storage.database import get_db_session

    mock_session = MagicMock()
    app.dependency_overrides[get_db_session] = lambda: mock_session

    payload = {
        "name": "Daft Invalid Config",
        "url": "https://www.daft.ie/property-for-sale/dublin",
        "adapter_type": "api",
        "adapter_name": "daft",
        "config": {"areas": "dublin"},
        "enabled": True,
        "poll_interval_seconds": 900,
        "tags": [],
    }

    try:
        response = client.post("/api/v1/sources", json=payload)
        assert response.status_code == 400
        body = response.json()
        assert body["detail"]["code"] == "invalid_source_config"
        assert body["detail"]["adapter_name"] == "daft"
        assert any("config.areas" in msg for msg in body["detail"]["errors"])
    finally:
        app.dependency_overrides.clear()


def test_update_source_rejects_invalid_adapter_config(client):
    from packages.storage.database import get_db_session

    mock_session = MagicMock()
    app.dependency_overrides[get_db_session] = lambda: mock_session

    try:
        with pytest.MonkeyPatch.context() as mp:
            from apps.api.routers import sources as sources_router

            fake_repo = MagicMock()
            fake_repo.get_by_id.return_value = MagicMock(id="source-1", adapter_name="daft")
            mp.setattr(sources_router, "SourceRepository", lambda _db: fake_repo)

            response = client.patch(
                "/api/v1/sources/source-1",
                json={"config": {"areas": "dublin"}},
            )

            assert response.status_code == 400
            body = response.json()
            assert body["detail"]["code"] == "invalid_source_config"
            fake_repo.update.assert_not_called()
    finally:
        app.dependency_overrides.clear()


def test_discover_auto_skips_candidates_with_invalid_adapter_config(client):
    from packages.storage.database import get_db_session

    mock_session = MagicMock()
    app.dependency_overrides[get_db_session] = lambda: mock_session

    try:
        with pytest.MonkeyPatch.context() as mp:
            from apps.api.routers import sources as sources_router

            fake_repo = MagicMock()
            fake_repo.get_all.return_value = []
            mp.setattr(sources_router, "SourceRepository", lambda _db: fake_repo)

            mp.setattr(
                sources_router,
                "load_discovery_candidates",
                lambda: [
                    {
                        "name": "Broken Daft Candidate",
                        "url": "https://www.daft.ie/property-for-sale/dublin",
                        "adapter_type": "api",
                        "adapter_name": "daft",
                        "config": {"areas": "dublin"},
                    }
                ],
            )

            mp.setattr(sources_router, "get_adapter_names", lambda: ["daft"])

            response = client.post("/api/v1/sources/discover-auto")

            assert response.status_code == 200
            body = response.json()
            assert body["created"] == []
            assert len(body["skipped_invalid"]) == 1
            assert body["skipped_invalid"][0]["reason"] == "invalid_adapter_config"
            fake_repo.create.assert_not_called()
    finally:
        app.dependency_overrides.clear()
