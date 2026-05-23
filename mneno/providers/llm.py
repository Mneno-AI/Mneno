"""LLM provider protocol and deterministic dummy implementation."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from mneno.providers.exceptions import ProviderValidationError


@runtime_checkable
class LLMProvider(Protocol):
    """Protocol for future LLM providers."""

    name: str

    def generate(
        self,
        prompt: str,
        *,
        system_prompt: str | None = None,
        temperature: float = 0.0,
        max_tokens: int | None = None,
    ) -> str:
        """Generate text from a prompt."""


class DummyLLMProvider:
    """Deterministic local LLM provider for tests and examples."""

    name = "dummy"

    def generate(
        self,
        prompt: str,
        *,
        system_prompt: str | None = None,
        temperature: float = 0.0,
        max_tokens: int | None = None,
    ) -> str:
        """Return a deterministic placeholder response."""
        if not prompt:
            raise ProviderValidationError("prompt must not be empty")
        if temperature < 0:
            raise ProviderValidationError("temperature must be non-negative")
        if max_tokens is not None and max_tokens <= 0:
            raise ProviderValidationError("max_tokens must be greater than 0")

        prefix = f"{system_prompt.strip()} | " if system_prompt else ""
        response = f"{prefix}Dummy response: {prompt.strip()}"
        if max_tokens is None:
            return response
        return " ".join(response.split()[:max_tokens])
