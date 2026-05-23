"""Embedding-powered semantic retrieval."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from mneno.models import Memory
from mneno.providers.embedding import EmbeddingProvider
from mneno.providers.exceptions import ProviderNotFoundError, ProviderValidationError
from mneno.retrieval.similarity import safe_similarity


class SemanticSearchResult(BaseModel):
    """A ranked semantic retrieval result."""

    model_config = ConfigDict(extra="forbid")

    memory: Memory
    similarity: float = Field(ge=0.0, le=1.0)
    rank: int = Field(gt=0)
    reason: str = Field(min_length=1)


class SemanticRetriever:
    """Rank memories by embedding similarity."""

    def __init__(self, embedding_provider: EmbeddingProvider | None = None) -> None:
        self.embedding_provider = embedding_provider

    def rank(self, query: str, memories: list[Memory], *, top_k: int | None = None) -> list[SemanticSearchResult]:
        """Return semantic search results ranked by similarity."""
        if self.embedding_provider is None:
            raise ProviderNotFoundError("Semantic retrieval requires an embedding provider")
        if top_k is not None and top_k <= 0:
            raise ValueError("top_k must be greater than 0")
        if not memories:
            return []

        # TODO: add an embedding cache/index layer before persisting vectors or supporting large memory sets.
        texts = [query, *[memory.content for memory in memories]]
        embeddings = self.embedding_provider.embed(texts)
        if len(embeddings) != len(texts):
            raise ProviderValidationError("Embedding provider returned the wrong number of vectors")

        query_embedding = embeddings[0]
        scored = [
            (
                memory,
                safe_similarity(query_embedding, memory_embedding),
            )
            for memory, memory_embedding in zip(memories, embeddings[1:], strict=True)
        ]
        scored.sort(key=lambda item: (item[1], item[0].updated_at, item[0].id), reverse=True)
        if top_k is not None:
            scored = scored[:top_k]
        return [
            SemanticSearchResult(
                memory=memory,
                similarity=similarity,
                rank=index,
                reason=f"Semantic similarity {similarity:.2f} from embedding provider '{self.embedding_provider.name}'",
            )
            for index, (memory, similarity) in enumerate(scored, start=1)
        ]
