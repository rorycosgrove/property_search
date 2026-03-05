"""
Abstract LLM provider interface.

Defines the contract that all LLM providers implement.
Runtime switching between providers is supported via DynamoDB configuration.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class LLMResponse:
    """Structured response from an LLM call."""
    content: str
    model: str
    provider: str
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None
    processing_time_ms: int | None = None
    raw: dict[str, Any] = field(default_factory=dict)


class LLMProvider(ABC):
    """Abstract interface for LLM providers."""

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.3,
        max_tokens: int = 2000,
        json_mode: bool = False,
    ) -> LLMResponse:
        """
        Generate a completion from the LLM.

        Args:
            prompt: User prompt text.
            system_prompt: Optional system prompt.
            temperature: Sampling temperature (0=deterministic, 1=creative).
            max_tokens: Maximum tokens in the response.
            json_mode: If True, request JSON-formatted output.

        Returns:
            Structured LLM response.
        """
        ...

    @abstractmethod
    def get_provider_name(self) -> str:
        """Return provider identifier (e.g., 'bedrock')."""
        ...

    @abstractmethod
    def get_model_name(self) -> str:
        """Return the model name being used."""
        ...

    @abstractmethod
    async def health_check(self) -> bool:
        """Check if the provider is available and responding."""
        ...
