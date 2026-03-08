"""Tests for FastAPI endpoints (uses TestClient)."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from apps.api.main import app


@pytest.fixture
def client():
    return TestClient(app)


class TestHealthEndpoint:
    def test_health_ok(self, client):
        import boto3

        from packages.storage.database import get_db_session

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


class TestGrantsEndpoint:
    def test_list_grants(self, client):
        from packages.storage.database import get_db_session

        mock_session = MagicMock()
        app.dependency_overrides[get_db_session] = lambda: mock_session

        try:
            with patch("apps.api.routers.grants.GrantProgramRepository") as MockRepo:
                instance = MockRepo.return_value
                instance.list_programs.return_value = []
                resp = client.get("/api/v1/grants")
                assert resp.status_code == 200
                assert resp.json() == []
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


class TestLLMEnrichmentDispatch:
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

    def test_enrich_queue_misconfigured_returns_503(self, client):
        from packages.storage.database import get_db_session

        mock_session = MagicMock()
        app.dependency_overrides[get_db_session] = lambda: mock_session

        try:
            with patch("apps.api.routers.llm.settings.llm_enabled", True):
                with patch("apps.api.routers.llm.settings.llm_queue_url", ""):
                    with patch("apps.api.routers.llm.os.environ", {}):
                        resp = client.post("/api/v1/llm/enrich/p-1")
                        assert resp.status_code == 503
                        assert "queue" in resp.text.lower()
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
