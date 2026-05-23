"""Lightweight provider registry."""

from __future__ import annotations

from typing import Any, TypeVar

from mneno.providers.embedding import EmbeddingProvider
from mneno.providers.exceptions import (
    ProviderAlreadyRegisteredError,
    ProviderNotFoundError,
    ProviderValidationError,
)
from mneno.providers.llm import LLMProvider
from mneno.providers.reranker import RerankerProvider

T = TypeVar("T")


class ProviderRegistry:
    """Registry for optional provider implementations."""

    def __init__(self) -> None:
        self._embeddings: dict[str, EmbeddingProvider] = {}
        self._llms: dict[str, LLMProvider] = {}
        self._rerankers: dict[str, RerankerProvider] = {}

    def register_embedding(self, name: str, provider: EmbeddingProvider) -> None:
        """Register an embedding provider."""
        self._register(name, provider, self._embeddings, expected_type=EmbeddingProvider, provider_type="embedding")

    def get_embedding(self, name: str) -> EmbeddingProvider:
        """Return a registered embedding provider."""
        return self._get(name, self._embeddings, provider_type="embedding")

    def register_llm(self, name: str, provider: LLMProvider) -> None:
        """Register an LLM provider."""
        self._register(name, provider, self._llms, expected_type=LLMProvider, provider_type="llm")

    def get_llm(self, name: str) -> LLMProvider:
        """Return a registered LLM provider."""
        return self._get(name, self._llms, provider_type="llm")

    def register_reranker(self, name: str, provider: RerankerProvider) -> None:
        """Register a reranker provider."""
        self._register(name, provider, self._rerankers, expected_type=RerankerProvider, provider_type="reranker")

    def get_reranker(self, name: str) -> RerankerProvider:
        """Return a registered reranker provider."""
        return self._get(name, self._rerankers, provider_type="reranker")

    def _register(
        self,
        name: str,
        provider: T,
        registry: dict[str, T],
        *,
        expected_type: type[Any],
        provider_type: str,
    ) -> None:
        normalized_name = _normalize_name(name)
        if normalized_name in registry:
            raise ProviderAlreadyRegisteredError(f"{provider_type} provider already registered: {normalized_name}")
        if not isinstance(provider, expected_type):
            raise ProviderValidationError(f"Invalid {provider_type} provider: {normalized_name}")
        registry[normalized_name] = provider

    def _get(self, name: str, registry: dict[str, T], *, provider_type: str) -> T:
        normalized_name = _normalize_name(name)
        try:
            return registry[normalized_name]
        except KeyError as exc:
            raise ProviderNotFoundError(f"{provider_type} provider not found: {normalized_name}") from exc


def _normalize_name(name: str) -> str:
    normalized = name.strip()
    if not normalized:
        raise ProviderValidationError("provider name must not be empty")
    return normalized
