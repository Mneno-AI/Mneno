"""Temporal memory scoring with keyword relevance placeholder logic."""

from __future__ import annotations

import math
import re
from datetime import UTC, datetime

from mneno.models import Memory, MemoryPolicy, MemoryScore
from mneno.providers.embedding import EmbeddingProvider
from mneno.retrieval.similarity import safe_similarity

TOKEN_PATTERN = re.compile(r"[a-zA-Z0-9]+")
STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "for",
    "in",
    "is",
    "of",
    "or",
    "the",
    "to",
    "what",
    "with",
}


class TemporalMemoryScorer:
    """Score memories using recency, importance, access frequency, and keyword overlap."""

    def __init__(
        self, *, policy: MemoryPolicy | None = None, embedding_provider: EmbeddingProvider | None = None
    ) -> None:
        self.policy = policy or MemoryPolicy()
        self.embedding_provider = embedding_provider

    def score(self, memory: Memory, *, query: str = "", use_semantic: bool = True) -> MemoryScore:
        """Score a memory for a query."""
        embedding_provider = self.embedding_provider if use_semantic else None
        return calculate_memory_score(memory, query=query, policy=self.policy, embedding_provider=embedding_provider)


def calculate_memory_score(
    memory: Memory,
    *,
    query: str = "",
    policy: MemoryPolicy | None = None,
    embedding_provider: EmbeddingProvider | None = None,
) -> MemoryScore:
    """Calculate a bounded, explainable score for a memory."""
    active_policy = policy or MemoryPolicy()
    recency = _recency_score(memory.updated_at, half_life_days=active_policy.recency_half_life_days)
    frequency = min(memory.access_count / 10.0, 1.0)
    freshness = _freshness_score(memory.created_at, decay_days=active_policy.freshness_decay_days)
    keyword_relevance, matched_terms = _keyword_overlap(query, _searchable_text(memory))
    semantic_relevance = _semantic_relevance(query, memory, embedding_provider=embedding_provider)
    relevance = max(keyword_relevance, semantic_relevance or 0.0)

    weighted_total = (
        recency * active_policy.recency_weight
        + memory.importance * active_policy.importance_weight
        + frequency * active_policy.access_weight
        + relevance * active_policy.relevance_weight
        + freshness * active_policy.freshness_weight
    )
    total_weight = (
        active_policy.recency_weight
        + active_policy.importance_weight
        + active_policy.access_weight
        + active_policy.relevance_weight
        + active_policy.freshness_weight
    )
    total = weighted_total / total_weight if total_weight > 0 else 0.0

    return MemoryScore(
        memory_id=memory.id,
        total=round(min(max(total, 0.0), 1.0), 6),
        relevance=round(relevance, 6),
        importance=memory.importance,
        recency=round(recency, 6),
        frequency=round(frequency, 6),
        freshness=round(freshness, 6),
        semantic_relevance=round(semantic_relevance, 6) if semantic_relevance is not None else None,
        reasons=_score_reasons(
            memory,
            recency=recency,
            frequency=frequency,
            freshness=freshness,
            matched_terms=matched_terms,
            semantic_relevance=semantic_relevance,
            embedding_provider_name=embedding_provider.name if embedding_provider is not None else None,
        ),
    )


def _recency_score(updated_at: datetime, *, half_life_days: float) -> float:
    now = datetime.now(UTC)
    if updated_at.tzinfo is None:
        updated_at = updated_at.replace(tzinfo=UTC)
    age_seconds = max((now - updated_at).total_seconds(), 0.0)
    half_life_seconds = half_life_days * 24 * 60 * 60
    return math.exp(-math.log(2) * age_seconds / half_life_seconds)


def _freshness_score(created_at: datetime, *, decay_days: float) -> float:
    now = datetime.now(UTC)
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=UTC)
    age_days = max((now - created_at).total_seconds(), 0.0) / (24 * 60 * 60)
    return max(1.0 - (age_days / decay_days), 0.0)


def _keyword_overlap(query: str, content: str) -> tuple[float, list[str]]:
    query_tokens = set(_tokens(query))
    if not query_tokens:
        return 0.0, []

    content_tokens = set(_tokens(content))
    if not content_tokens:
        return 0.0, []

    matched_terms = sorted(query_tokens & content_tokens)
    return len(matched_terms) / len(query_tokens), matched_terms


def _semantic_relevance(
    query: str,
    memory: Memory,
    *,
    embedding_provider: EmbeddingProvider | None,
) -> float | None:
    if embedding_provider is None or not query:
        return None
    # TODO: add an embedding cache/index layer before persisting vectors or supporting large memory sets.
    query_embedding, memory_embedding = embedding_provider.embed([query, memory.content])
    return safe_similarity(query_embedding, memory_embedding)


def _searchable_text(memory: Memory) -> str:
    return " ".join(
        [
            memory.content,
            memory.memory_type.value,
            memory.source or "",
            " ".join(memory.tags),
        ]
    )


def _score_reasons(
    memory: Memory,
    *,
    recency: float,
    frequency: float,
    freshness: float,
    matched_terms: list[str],
    semantic_relevance: float | None,
    embedding_provider_name: str | None,
) -> list[str]:
    reasons = [f"Matched query term: {term}" for term in matched_terms]
    if semantic_relevance is not None and embedding_provider_name is not None:
        reasons.append(
            f"Semantic similarity {semantic_relevance:.2f} from embedding provider '{embedding_provider_name}'"
        )
    if memory.importance >= 0.75:
        reasons.append("High importance memory")
    elif memory.importance <= 0.25:
        reasons.append("Low importance memory")
    if recency >= 0.85:
        reasons.append("Recently updated")
    elif recency <= 0.35:
        reasons.append("Not recently updated")
    if frequency > 0:
        reasons.append("Frequently accessed memory" if frequency >= 0.5 else "Previously accessed memory")
    if freshness <= 0.25:
        reasons.append("Freshness penalty applied for older memory")
    if not reasons:
        reasons.append("Baseline score from importance, recency, freshness, and access signals")
    return reasons


def _tokens(text: str) -> list[str]:
    return [token.lower() for token in TOKEN_PATTERN.findall(text) if token.lower() not in STOPWORDS]
