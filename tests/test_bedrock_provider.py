"""Tests for the Amazon Bedrock LLM provider."""
import json
from unittest.mock import MagicMock, patch

import pytest

from packages.ai.bedrock_provider import BedrockProvider
from packages.ai.provider import LLMResponse


class TestBedrockProvider:
    def setup_method(self):
        self.provider = BedrockProvider(
            model_id="amazon.titan-text-express-v1", region="eu-west-1"
        )

    def test_provider_name(self):
        assert self.provider.get_provider_name() == "bedrock"

    def test_model_name(self):
        assert self.provider.get_model_name() == "amazon.titan-text-express-v1"

    def test_build_request_body_titan(self):
        body = self.provider._build_request_body(
            prompt="Hello", system_prompt=None, temperature=0.3, max_tokens=100
        )
        assert "inputText" in body
        assert body["inputText"] == "Hello"
        assert body["textGenerationConfig"]["maxTokenCount"] == 100

    def test_build_request_body_titan_with_system(self):
        body = self.provider._build_request_body(
            prompt="Hello", system_prompt="You are helpful.", temperature=0.5, max_tokens=200
        )
        assert "You are helpful." in body["inputText"]
        assert "Hello" in body["inputText"]

    def test_build_request_body_nova(self):
        provider = BedrockProvider(model_id="amazon.nova-micro-v1:0")
        body = provider._build_request_body(
            prompt="Hello", system_prompt="Be concise.", temperature=0.3, max_tokens=150
        )
        assert "messages" in body
        assert body["messages"][0]["role"] == "user"
        assert body["messages"][0]["content"][0]["text"] == "Hello"
        assert body["system"] == [{"text": "Be concise."}]
        assert body["inferenceConfig"]["maxTokens"] == 150

    def test_extract_content_titan(self):
        response = {"results": [{"outputText": "Test response"}]}
        assert self.provider._extract_content(response) == "Test response"

    def test_extract_content_nova(self):
        response = {
            "output": {
                "message": {
                    "content": [{"text": "Nova response"}]
                }
            }
        }
        assert self.provider._extract_content(response) == "Nova response"

    def test_extract_content_completion_fallback(self):
        response = {"completion": "Fallback response"}
        assert self.provider._extract_content(response) == "Fallback response"

    def test_extract_token_usage_titan(self):
        response = {
            "inputTextTokenCount": 10,
            "results": [{"tokenCount": 20, "outputText": "..."}],
        }
        usage = self.provider._extract_token_usage(response)
        assert usage["prompt_tokens"] == 10
        assert usage["completion_tokens"] == 20
        assert usage["total_tokens"] == 30

    def test_extract_token_usage_nova(self):
        response = {
            "usage": {
                "inputTokens": 15,
                "outputTokens": 25,
                "totalTokens": 40,
            }
        }
        usage = self.provider._extract_token_usage(response)
        assert usage["prompt_tokens"] == 15
        assert usage["completion_tokens"] == 25
        assert usage["total_tokens"] == 40

    @pytest.mark.asyncio
    async def test_generate_titan(self):
        titan_response = {
            "inputTextTokenCount": 5,
            "results": [{"tokenCount": 10, "outputText": "Generated text"}],
        }
        mock_client = MagicMock()
        mock_body = MagicMock()
        mock_body.read.return_value = json.dumps(titan_response).encode()
        mock_client.invoke_model.return_value = {"body": mock_body}
        self.provider._client = mock_client

        result = await self.provider.generate("Test prompt")

        assert isinstance(result, LLMResponse)
        assert result.content == "Generated text"
        assert result.provider == "bedrock"
        assert result.model == "amazon.titan-text-express-v1"
        assert result.prompt_tokens == 5
        assert result.completion_tokens == 10

    @pytest.mark.asyncio
    async def test_health_check_ok(self):
        import boto3
        with patch.object(boto3, "client") as mock_client_func:
            mock_client = MagicMock()
            mock_client.list_foundation_models.return_value = {
                "modelSummaries": [{"modelId": "amazon.titan-text-express-v1"}]
            }
            mock_client_func.return_value = mock_client

            result = await self.provider.health_check()
            assert result is True

    @pytest.mark.asyncio
    async def test_health_check_failure(self):
        import boto3
        with patch.object(boto3, "client") as mock_client_func:
            mock_client_func.side_effect = Exception("Connection error")

            result = await self.provider.health_check()
            assert result is False
