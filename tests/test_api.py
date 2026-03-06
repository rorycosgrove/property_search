"""Tests for FastAPI endpoints (uses TestClient)."""
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from apps.api.main import app


@pytest.fixture
def client():
    return TestClient(app)


class TestHealthEndpoint:
    def test_health_ok(self, client):
        from packages.storage.database import get_db_session
        import boto3

        mock_session = MagicMock()
        mock_session.execute.return_value = None
        app.dependency_overrides[get_db_session] = lambda: mock_session

        try:
            with patch.object(boto3, "client") as mock_client_func:
                mock_client = MagicMock()
                mock_client.list_foundation_models.return_value = {
                    "modelSummaries": [{"modelId": "amazon.titan-text-express-v1"}]
                }
                mock_client_func.return_value = mock_client

                resp = client.get("/health")
                assert resp.status_code == 200
                data = resp.json()
                assert data["status"] in ("healthy", "degraded")
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
