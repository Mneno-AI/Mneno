"""Provider protocols and registry for optional Mneno integrations."""

from mneno.providers.embedding import DummyEmbeddingProvider, EmbeddingProvider, EmbeddingResult
from mneno.providers.exceptions import (
    ProviderAlreadyRegisteredError,
    ProviderError,
    ProviderNotFoundError,
    ProviderValidationError,
)
from mneno.providers.llm import DummyLLMProvider, LLMProvider
from mneno.providers.registry import ProviderRegistry
from mneno.providers.reranker import DummyRerankerProvider, RerankerProvider

__all__ = [
    "DummyEmbeddingProvider",
    "DummyLLMProvider",
    "DummyRerankerProvider",
    "EmbeddingProvider",
    "EmbeddingResult",
    "LLMProvider",
    "ProviderAlreadyRegisteredError",
    "ProviderError",
    "ProviderNotFoundError",
    "ProviderRegistry",
    "ProviderValidationError",
    "RerankerProvider",
]
