"""
OpenAI LLM provider.

Uses the OpenAI API (GPT-4o-mini, GPT-4o, etc.) for property enrichment.
Compatible with any OpenAI-compatible API (Azure OpenAI, etc.).
"""

from __future__ import annotations

import time
from typing import Any

from packages.shared.config import settings
from packages.shared.logging import get_logger
from packages.ai.provider import LLMProvider, LLMResponse

logger = get_logger(__name__)


class OpenAIProvider(LLMProvider):
    """LLM provider backed by OpenAI API."""

    def __init__(self, api_key: str | None = None, model: str | None = None):
        self.api_key = api_key or settings.openai_api_key
        self.model = model or settings.openai_model

        if not self.api_key:
            logger.warning("openai_no_api_key")

    def get_provider_name(self) -> str:
        return "openai"

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
        # Lazy import to avoid issues when openai is not installed
        from openai import AsyncOpenAI

        start = time.monotonic()

        client = AsyncOpenAI(api_key=self.api_key)

        messages: list[dict[str, str]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}

        try:
            response = await client.chat.completions.create(**kwargs)

            elapsed_ms = int((time.monotonic() - start) * 1000)
            choice = response.choices[0] if response.choices else None

            return LLMResponse(
                content=choice.message.content if choice else "",
                model=response.model,
                provider="openai",
                prompt_tokens=response.usage.prompt_tokens if response.usage else None,
                completion_tokens=response.usage.completion_tokens if response.usage else None,
                total_tokens=response.usage.total_tokens if response.usage else None,
                processing_time_ms=elapsed_ms,
                raw=response.model_dump() if hasattr(response, "model_dump") else {},
            )

        except Exception as e:
            elapsed_ms = int((time.monotonic() - start) * 1000)
            logger.error("openai_error", error=str(e), model=self.model, elapsed_ms=elapsed_ms)
            raise

    async def health_check(self) -> bool:
        if not self.api_key:
            return False
        try:
            from openai import AsyncOpenAI
            client = AsyncOpenAI(api_key=self.api_key)
            await client.models.list()
            return True
        except Exception:
            return False
