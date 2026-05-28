"""LLM provider protocol and deterministic dummy implementation."""

from __future__ import annotations

import json
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

        if "mneno.memory_extraction.v1" in prompt:
            response = _dummy_extraction_response(prompt)
            return _truncate(response, max_tokens)
        if "mneno.compaction_merge.v1" in prompt:
            response = _dummy_compaction_response(prompt)
            return _truncate(response, max_tokens)

        prefix = f"{system_prompt.strip()} | " if system_prompt else ""
        response = f"{prefix}Dummy response: {prompt.strip()}"
        return _truncate(response, max_tokens)


def _truncate(response: str, max_tokens: int | None) -> str:
    if max_tokens is None:
        return response
    return " ".join(response.split()[:max_tokens])


def _dummy_extraction_response(prompt: str) -> str:
    lowered = prompt.lower()
    memories: list[dict[str, object]] = []
    if "mneno" in lowered:
        memories.append(
            {
                "content": "User is building Mneno, a Python SDK for explainable AI memory.",
                "memory_type": "semantic",
                "importance": 0.9,
                "tags": ["project", "mneno"],
                "metadata": {"provider": "dummy"},
                "reason": "Project identity is durable context.",
            }
        )
    if "prefers python" in lowered or "prefer python" in lowered:
        memories.append(
            {
                "content": "User prefers Python 3.11.",
                "memory_type": "preference",
                "importance": 0.8,
                "tags": ["preference", "python"],
                "metadata": {"provider": "dummy"},
                "reason": "User preference is useful durable context.",
            }
        )
    return json.dumps(memories)


def _dummy_compaction_response(prompt: str) -> str:
    lines = [line.removeprefix("- ").strip() for line in prompt.splitlines() if line.strip().startswith("- ")]
    best = max(lines, key=len) if lines else "Merged memory"
    return json.dumps({"content": f"LLM merged memory: {best}"})
