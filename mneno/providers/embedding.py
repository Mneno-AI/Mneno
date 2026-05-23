"""Embedding provider protocol and deterministic dummy implementation."""

from __future__ import annotations

import hashlib
import re
from typing import Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field

from mneno.providers.exceptions import ProviderValidationError

TOKEN_PATTERN = re.compile(r"[a-zA-Z0-9]+")


@runtime_checkable
class EmbeddingProvider(Protocol):
    """Protocol for future embedding providers."""

    name: str

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Return one vector per input text."""


class EmbeddingResult(BaseModel):
    """Typed embedding response for future provider adapters."""

    model_config = ConfigDict(extra="forbid")

    provider: str
    embeddings: list[list[float]] = Field(default_factory=list)


class DummyEmbeddingProvider:
    """Deterministic local embedding provider for tests and examples."""

    name = "dummy"

    def __init__(self, *, dimensions: int = 8) -> None:
        if dimensions <= 0:
            raise ProviderValidationError("dimensions must be greater than 0")
        self.dimensions = dimensions

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Convert text deterministically into small fake vectors."""
        if not isinstance(texts, list):
            raise ProviderValidationError("texts must be a list")
        return [self._embed_one(text) for text in texts]

    def _embed_one(self, text: str) -> list[float]:
        if not isinstance(text, str):
            raise ProviderValidationError("all texts must be strings")
        vector = [0.0 for _index in range(self.dimensions)]
        tokens = TOKEN_PATTERN.findall(text.lower())
        if not tokens:
            return vector
        for token in tokens:
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            index = digest[0] % self.dimensions
            vector[index] += 1.0
        magnitude = sum(vector) or 1.0
        return [round(value / magnitude, 6) for value in vector]
