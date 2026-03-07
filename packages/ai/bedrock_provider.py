"""
Amazon Bedrock LLM provider.

Uses AWS Bedrock Runtime to invoke Amazon Titan and Nova foundation models
for property enrichment. No API keys required — uses IAM credentials.

Free tier models: Amazon Titan Text Express, Amazon Nova Micro/Lite.
"""

from __future__ import annotations

import json
import time
from typing import Any

from packages.ai.provider import LLMProvider, LLMResponse
from packages.shared.config import settings
from packages.shared.logging import get_logger

logger = get_logger(__name__)

# Model ID → request/response format mapping
_TITAN_MODELS = {"amazon.titan-text-express-v1", "amazon.titan-text-lite-v1"}
_NOVA_MODELS = {"amazon.nova-micro-v1:0", "amazon.nova-lite-v1:0", "amazon.nova-pro-v1:0"}
_CLAUDE_MODELS = {"anthropic.claude-3-haiku-20240307-v1:0", "anthropic.claude-3-sonnet-20240229-v1:0", "anthropic.claude-3-5-sonnet-20240620-v1:0"}


class BedrockProvider(LLMProvider):
    """LLM provider backed by Amazon Bedrock Runtime."""

    def __init__(self, model_id: str | None = None, region: str | None = None):
        self.model_id = model_id or settings.bedrock_model_id
        self.region = region or settings.aws_region
        self._client = None

    def _get_client(self):
        if self._client is None:
            import boto3

            self._client = boto3.client(
                "bedrock-runtime",
                region_name=self.region,
            )
        return self._client

    def get_provider_name(self) -> str:
        return "bedrock"

    def get_model_name(self) -> str:
        return self.model_id

    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.3,
        max_tokens: int = 2000,
        json_mode: bool = False,
    ) -> LLMResponse:
        start = time.monotonic()

        if json_mode and system_prompt:
            system_prompt += "\nYou MUST respond with valid JSON only. No markdown fences."

        body = self._build_request_body(prompt, system_prompt, temperature, max_tokens)

        try:
            client = self._get_client()
            response = client.invoke_model(
                modelId=self.model_id,
                contentType="application/json",
                accept="application/json",
                body=json.dumps(body),
            )

            response_body = json.loads(response["body"].read())
            content = self._extract_content(response_body)
            token_usage = self._extract_token_usage(response_body)
            elapsed_ms = int((time.monotonic() - start) * 1000)

            return LLMResponse(
                content=content,
                model=self.model_id,
                provider="bedrock",
                prompt_tokens=token_usage.get("prompt_tokens"),
                completion_tokens=token_usage.get("completion_tokens"),
                total_tokens=token_usage.get("total_tokens"),
                processing_time_ms=elapsed_ms,
                raw=response_body,
            )

        except Exception as e:
            elapsed_ms = int((time.monotonic() - start) * 1000)
            logger.error(
                "bedrock_error", error=str(e), model=self.model_id, elapsed_ms=elapsed_ms
            )
            raise

    async def health_check(self) -> bool:
        try:
            import boto3

            client = boto3.client("bedrock", region_name=self.region)
            response = client.list_foundation_models(byProvider="Amazon")
            return len(response.get("modelSummaries", [])) > 0
        except Exception:
            return False

    def _build_request_body(
        self,
        prompt: str,
        system_prompt: str | None,
        temperature: float,
        max_tokens: int,
    ) -> dict[str, Any]:
        """Build the model-specific request body."""
        full_prompt = prompt
        if system_prompt:
            full_prompt = f"{system_prompt}\n\n{prompt}"

        if self.model_id in _TITAN_MODELS:
            return {
                "inputText": full_prompt,
                "textGenerationConfig": {
                    "maxTokenCount": max_tokens,
                    "temperature": temperature,
                    "topP": 0.9,
                },
            }

        if self.model_id in _NOVA_MODELS or self.model_id in _CLAUDE_MODELS:
            messages = [{"role": "user", "content": [{"text": prompt}]}]
            body: dict[str, Any] = {
                "messages": messages,
                "inferenceConfig": {
                    "maxTokens": max_tokens,
                    "temperature": temperature,
                    "topP": 0.9,
                },
            }
            if system_prompt:
                body["system"] = [{"text": system_prompt}]
            return body

        # Default: Converse-style body (works for most newer models)
        messages = [{"role": "user", "content": [{"text": prompt}]}]
        body = {
            "messages": messages,
            "inferenceConfig": {
                "maxTokens": max_tokens,
                "temperature": temperature,
                "topP": 0.9,
            },
        }
        if system_prompt:
            body["system"] = [{"text": system_prompt}]
        return body

    def _extract_content(self, response_body: dict[str, Any]) -> str:
        """Extract generated text from model-specific response."""
        # Titan format
        if "results" in response_body:
            results = response_body["results"]
            if results:
                return results[0].get("outputText", "")

        # Nova / Converse format
        if "output" in response_body:
            output = response_body["output"]
            if isinstance(output, dict) and "message" in output:
                message = output["message"]
                content_blocks = message.get("content", [])
                if content_blocks:
                    return content_blocks[0].get("text", "")

        # Fallback: try common paths
        if "completion" in response_body:
            return response_body["completion"]

        return str(response_body)

    def _extract_token_usage(self, response_body: dict[str, Any]) -> dict[str, int | None]:
        """Extract token usage from model-specific response."""
        usage: dict[str, int | None] = {
            "prompt_tokens": None,
            "completion_tokens": None,
            "total_tokens": None,
        }

        # Nova / Converse format
        if "usage" in response_body:
            u = response_body["usage"]
            usage["prompt_tokens"] = u.get("inputTokens")
            usage["completion_tokens"] = u.get("outputTokens")
            usage["total_tokens"] = u.get("totalTokens")

        # Titan format
        elif "inputTextTokenCount" in response_body:
            usage["prompt_tokens"] = response_body.get("inputTextTokenCount")
            results = response_body.get("results", [{}])
            if results:
                usage["completion_tokens"] = results[0].get("tokenCount")
            if usage["prompt_tokens"] and usage["completion_tokens"]:
                usage["total_tokens"] = usage["prompt_tokens"] + usage["completion_tokens"]

        return usage
