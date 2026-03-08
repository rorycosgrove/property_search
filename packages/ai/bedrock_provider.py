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

_BEDROCK_UI_MODELS: list[dict[str, str]] = [
    {"id": "amazon.titan-text-lite-v1", "label": "Amazon Titan Text Lite"},
    {"id": "anthropic.claude-3-haiku-20240307-v1:0", "label": "Anthropic Claude 3 Haiku"},
    {"id": "anthropic.claude-3-sonnet-20240229-v1:0", "label": "Anthropic Claude 3 Sonnet"},
    {"id": "amazon.nova-micro-v1:0", "label": "Amazon Nova Micro (may require inference profile)"},
    {"id": "amazon.nova-lite-v1:0", "label": "Amazon Nova Lite (may require inference profile)"},
    {"id": "amazon.nova-pro-v1:0", "label": "Amazon Nova Pro (may require inference profile)"},
]

_FALLBACK_MODEL_ORDER = [m["id"] for m in _BEDROCK_UI_MODELS]


class BedrockProvider(LLMProvider):
    """LLM provider backed by Amazon Bedrock Runtime."""

    def __init__(self, model_id: str | None = None, region: str | None = None):
        self.model_id = model_id or settings.bedrock_model_id
        self.region = region or settings.aws_region
        self.inference_profile_id = settings.bedrock_inference_profile_id or None
        self._client = None
        self._control_client = None

    def _get_client(self):
        if self._client is None:
            import boto3

            self._client = boto3.client(
                "bedrock-runtime",
                region_name=self.region,
            )
        return self._client

    def _get_control_client(self):
        if self._control_client is None:
            import boto3

            self._control_client = boto3.client(
                "bedrock",
                region_name=self.region,
            )
        return self._control_client

    @staticmethod
    def get_ui_model_options() -> list[dict[str, str]]:
        """Return curated Bedrock models suitable for general use in this app."""
        return list(_BEDROCK_UI_MODELS)

    def get_runtime_ui_model_options(self) -> list[dict[str, str]]:
        """Discover currently listed on-demand text models from Bedrock."""
        try:
            client = self._get_control_client()
            response = client.list_foundation_models()
            summaries = response.get("modelSummaries", [])
        except Exception:
            return self.get_ui_model_options()

        options: list[dict[str, str]] = []
        for summary in summaries:
            model_id = summary.get("modelId")
            if not model_id or not isinstance(model_id, str):
                continue

            # This provider currently supports Titan/Nova/Claude request formats.
            if not (model_id.startswith("amazon.") or model_id.startswith("anthropic.")):
                continue

            output_modalities = summary.get("outputModalities") or []
            if output_modalities and "TEXT" not in output_modalities:
                continue

            inference_types = summary.get("inferenceTypesSupported") or []
            if inference_types and "ON_DEMAND" not in inference_types:
                continue

            provider_name = (summary.get("providerName") or "").strip()
            model_name = (summary.get("modelName") or model_id).strip()
            label = f"{provider_name} {model_name}".strip()
            options.append({"id": model_id, "label": label})

        if not options:
            return self.get_ui_model_options()

        options.sort(key=lambda item: item["label"].lower())
        return options

    def get_provider_name(self) -> str:
        return "bedrock"

    def get_model_name(self) -> str:
        return self.model_id

    @staticmethod
    def _classify_error_name(error_name: str) -> str:
        """Map provider/client exception class names to coarse error categories."""
        throttle_errors = {"ThrottlingException", "TooManyRequestsException"}
        config_errors = {
            "AccessDeniedException",
            "UnrecognizedClientException",
            "ExpiredTokenException",
            "ResourceNotFoundException",
            "ValidationException",
            "InvalidParameterException",
            "UnknownServiceError",
            "NoRegionError",
            "NoCredentialsError",
            "PartialCredentialsError",
        }
        transport_errors = {"EndpointConnectionError", "ConnectTimeoutError", "ReadTimeoutError"}

        if error_name in throttle_errors:
            return "throttle"
        if error_name in config_errors:
            return "configuration"
        if error_name in transport_errors:
            return "transport"
        return "unknown"

    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.3,
        max_tokens: int = 2000,
        json_mode: bool = False,
    ) -> LLMResponse:
        start = time.monotonic()
        configured_model = self.model_id

        if json_mode and system_prompt:
            system_prompt += "\nYou MUST respond with valid JSON only. No markdown fences."

        raw_body, used_model = self._invoke_with_fallbacks(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            start=start,
        )

        try:
            response_body = json.loads(raw_body)
        except json.JSONDecodeError as exc:
            elapsed_ms = int((time.monotonic() - start) * 1000)
            logger.error(
                "bedrock_response_json_invalid",
                error=str(exc),
                model=configured_model,
                elapsed_ms=elapsed_ms,
            )
            raise ValueError("bedrock_invalid_json_response") from exc

        content = self._extract_content(response_body)
        token_usage = self._extract_token_usage(response_body)
        elapsed_ms = int((time.monotonic() - start) * 1000)

        return LLMResponse(
            content=content,
            model=used_model,
            provider="bedrock",
            prompt_tokens=token_usage.get("prompt_tokens"),
            completion_tokens=token_usage.get("completion_tokens"),
            total_tokens=token_usage.get("total_tokens"),
            processing_time_ms=elapsed_ms,
            raw=response_body,
        )

    async def health_check(self) -> bool:
        try:
            client = self._get_control_client()
            response = client.list_foundation_models()
            return len(response.get("modelSummaries", [])) > 0
        except Exception:
            return False

    def is_model_listed(self, model_id: str | None = None) -> bool:
        """Return True when the model appears in Bedrock foundation model listings."""
        target_model = model_id or self.model_id
        try:
            model_ids = set(self._list_foundation_model_ids())
            return target_model in model_ids
        except Exception:
            return False

    def _invoke_model_raw(self, model_id: str, body: dict[str, Any]) -> bytes:
        client = self._get_client()
        target_model_id = self.inference_profile_id or model_id
        response = client.invoke_model(
            modelId=target_model_id,
            contentType="application/json",
            accept="application/json",
            body=json.dumps(body),
        )
        return response["body"].read()

    def _invoke_with_fallbacks(
        self,
        prompt: str,
        system_prompt: str | None,
        temperature: float,
        max_tokens: int,
        start: float,
    ) -> tuple[bytes, str]:
        candidates = self._build_invoke_candidates(self.model_id)
        seen = set()
        candidates = [m for m in candidates if not (m in seen or seen.add(m))]
        last_exc: Exception | None = None

        for idx, candidate in enumerate(candidates):
            body = self._build_request_body(
                prompt,
                system_prompt,
                temperature,
                max_tokens,
                model_id=candidate,
            )
            try:
                return self._invoke_model_raw(candidate, body), candidate
            except Exception as exc:
                last_exc = exc
                if not self._is_model_restriction_error(exc):
                    self._raise_invoke_error(exc, start, candidate)

                next_candidate = candidates[idx + 1] if idx + 1 < len(candidates) else None
                if next_candidate:
                    logger.warning(
                        "bedrock_model_fallback",
                        from_model=candidate,
                        to_model=next_candidate,
                        error=str(exc),
                    )
                    continue

                self._raise_invoke_error(exc, start, candidate)

        if last_exc is not None:
            self._raise_invoke_error(last_exc, start, candidates[-1] if candidates else self.model_id)

        raise RuntimeError("bedrock_configuration_error: no candidate models available")

    def _build_invoke_candidates(self, configured_model: str) -> list[str]:
        # Inference profiles are bound to model groups; avoid speculative fallback switching.
        if self.inference_profile_id:
            return [configured_model]

        runtime_candidates = [opt["id"] for opt in self.get_runtime_ui_model_options()]
        return [configured_model] + runtime_candidates + _FALLBACK_MODEL_ORDER

    def _raise_invoke_error(self, exc: Exception, start: float, attempted_model: str) -> None:
        elapsed_ms = int((time.monotonic() - start) * 1000)
        error_name = exc.__class__.__name__
        category = self._classify_error_name(error_name)
        logger.error(
            "bedrock_invoke_failed",
            error=str(exc),
            error_name=error_name,
            category=category,
            model=attempted_model,
            elapsed_ms=elapsed_ms,
        )
        raise RuntimeError(f"bedrock_{category}_error: {exc}") from exc

    def _is_model_restriction_error(self, exc: Exception) -> bool:
        message = str(exc).lower()
        return any(
            token in message
            for token in (
                "accessdenied",
                "not authorized",
                "not authorized to invoke",
                "model access",
                "resourcenotfoundexception",
                "end of its life",
                "on-demand throughput",
                "doesn't support on-demand",
                "does not support on-demand",
                "inference profile",
                "model identifier is invalid",
                "resource not found",
            )
        )

    def _list_foundation_model_ids(self) -> list[str]:
        client = self._get_control_client()
        response = client.list_foundation_models()
        return [m.get("modelId") for m in response.get("modelSummaries", []) if m.get("modelId")]

    def _build_request_body(
        self,
        prompt: str,
        system_prompt: str | None,
        temperature: float,
        max_tokens: int,
        model_id: str | None = None,
    ) -> dict[str, Any]:
        """Build the model-specific request body."""
        active_model = model_id or self.model_id
        full_prompt = prompt
        if system_prompt:
            full_prompt = f"{system_prompt}\n\n{prompt}"

        if active_model in _TITAN_MODELS:
            return {
                "inputText": full_prompt,
                "textGenerationConfig": {
                    "maxTokenCount": max_tokens,
                    "temperature": temperature,
                    "topP": 0.9,
                },
            }

        if active_model in _NOVA_MODELS or active_model in _CLAUDE_MODELS:
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
