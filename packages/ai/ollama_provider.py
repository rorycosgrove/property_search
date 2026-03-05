"""
Ollama LLM provider.

Connects to a local Ollama instance for property enrichment.
Default model: llama3.1:8b (configurable).
"""

from __future__ import annotations

import time
from typing import Any

import httpx

from packages.shared.config import settings
from packages.shared.logging import get_logger
from packages.ai.provider import LLMProvider, LLMResponse

logger = get_logger(__name__)


class OllamaProvider(LLMProvider):
    """LLM provider backed by local Ollama instance."""

    def __init__(self, base_url: str | None = None, model: str | None = None):
        self.base_url = (base_url or settings.ollama_endpoint).rstrip("/")
        self.model = model or settings.ollama_model

    def get_provider_name(self) -> str:
        return "ollama"

    def get_model_name(self) -> str:
        return self.model

    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.3,
        max_tokens: int = 2000,
        json_mode: bool = False,
    ) -> LLMResponse:
        start = time.monotonic()

        payload: dict[str, Any] = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }

        if system_prompt:
            payload["system"] = system_prompt

        if json_mode:
            payload["format"] = "json"

        try:
            async with httpx.AsyncClient(timeout=120) as client:
                response = await client.post(
                    f"{self.base_url}/api/generate",
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()

            elapsed_ms = int((time.monotonic() - start) * 1000)

            return LLMResponse(
                content=data.get("response", ""),
                model=data.get("model", self.model),
                provider="ollama",
                prompt_tokens=data.get("prompt_eval_count"),
                completion_tokens=data.get("eval_count"),
                total_tokens=(data.get("prompt_eval_count") or 0) + (data.get("eval_count") or 0),
                processing_time_ms=elapsed_ms,
                raw=data,
            )

        except Exception as e:
            elapsed_ms = int((time.monotonic() - start) * 1000)
            logger.error("ollama_error", error=str(e), model=self.model, elapsed_ms=elapsed_ms)
            raise

    async def health_check(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                response = await client.get(f"{self.base_url}/api/tags")
                return response.status_code == 200
        except Exception:
            return False

    async def list_models(self) -> list[str]:
        """List available models from the Ollama instance."""
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(f"{self.base_url}/api/tags")
                response.raise_for_status()
                data = response.json()
                return [m["name"] for m in data.get("models", [])]
        except Exception as e:
            logger.warning("ollama_list_models_error", error=str(e))
            return []
