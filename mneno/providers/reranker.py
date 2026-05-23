"""Reranker provider protocol and deterministic dummy implementation."""

from __future__ import annotations

import re
from typing import Protocol, runtime_checkable

from mneno.providers.exceptions import ProviderValidationError

TOKEN_PATTERN = re.compile(r"[a-zA-Z0-9]+")


@runtime_checkable
class RerankerProvider(Protocol):
    """Protocol for future reranker providers."""

    name: str

    def rerank(self, query: str, documents: list[str]) -> list[int]:
        """Return reordered document indices."""


class DummyRerankerProvider:
    """Keyword-overlap reranker for tests and examples."""

    name = "dummy"

    def rerank(self, query: str, documents: list[str]) -> list[int]:
        """Rank document indices by deterministic keyword overlap."""
        if not isinstance(documents, list):
            raise ProviderValidationError("documents must be a list")
        query_tokens = set(_tokens(query))
        scored: list[tuple[int, int]] = []
        for index, document in enumerate(documents):
            if not isinstance(document, str):
                raise ProviderValidationError("all documents must be strings")
            document_tokens = set(_tokens(document))
            scored.append((index, len(query_tokens & document_tokens)))
        scored.sort(key=lambda item: (item[1], -item[0]), reverse=True)
        return [index for index, _score in scored]


def _tokens(text: str) -> list[str]:
    return [token.lower() for token in TOKEN_PATTERN.findall(text)]
