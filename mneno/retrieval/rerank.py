"""Optional second-stage reranking for memory search results."""

from __future__ import annotations

from mneno.models import MemorySearchResult
from mneno.providers.exceptions import ProviderValidationError
from mneno.providers.reranker import RerankerProvider


class RerankingEngine:
    """Rerank existing memory search results with an optional provider."""

    def __init__(self, reranker_provider: RerankerProvider | None = None) -> None:
        self.reranker_provider = reranker_provider

    def rerank(
        self,
        query: str,
        results: list[MemorySearchResult],
        *,
        top_k: int | None = None,
    ) -> list[MemorySearchResult]:
        """Rerank results, returning unchanged results when no provider is configured."""
        if self.reranker_provider is None or not results:
            return results
        if top_k is not None and top_k <= 0:
            raise ValueError("top_k must be greater than 0")

        candidate_count = min(top_k or len(results), len(results))
        candidates = results[:candidate_count]
        tail = results[candidate_count:]
        documents = [result.memory.content for result in candidates]
        indices = self.reranker_provider.rerank(query, documents)
        ordered_candidate_indices = self._validate_indices(indices, candidate_count)
        missing_indices = [index for index in range(candidate_count) if index not in ordered_candidate_indices]
        ordered_candidates = [candidates[index] for index in [*ordered_candidate_indices, *missing_indices]]
        ordered_results = [*ordered_candidates, *tail]

        return [
            result.model_copy(
                update={
                    "rank": index,
                    "original_rank": result.rank,
                    "reranked_rank": index,
                    "rerank_reason": f"Reranked by provider '{self.reranker_provider.name}'",
                    "reranker_name": self.reranker_provider.name,
                }
            )
            for index, result in enumerate(ordered_results, start=1)
        ]

    def _validate_indices(self, indices: list[int], candidate_count: int) -> list[int]:
        if not isinstance(indices, list):
            raise ProviderValidationError("reranker must return a list of indices")

        seen: set[int] = set()
        for index in indices:
            if not isinstance(index, int):
                raise ProviderValidationError("reranker indices must be integers")
            if index < 0 or index >= candidate_count:
                raise ProviderValidationError(f"reranker index out of range: {index}")
            if index in seen:
                raise ProviderValidationError(f"reranker returned duplicate index: {index}")
            seen.add(index)
        return indices
