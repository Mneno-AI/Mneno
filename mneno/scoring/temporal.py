"""Deterministic temporal and lexical memory scoring."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from mneno.hierarchy.layers import LAYER_SCORE_ADJUSTMENT, MemoryLayer
from mneno.models import Memory, MemoryPolicy, MemoryScore, MemoryStatus
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
    "did",
    "does",
    "how",
    "it",
    "that",
    "this",
    "was",
    "were",
    "who",
    "why",
}
CURRENT_SESSION_BOOST = 0.15
TEMPORAL_CURRENT_SESSION_BOOST = 0.20
RELATED_SESSION_BOOST = 0.05
TEMPORAL_QUERY_TERMS = {"current", "currently", "latest", "now", "recent", "recently", "today", "tonight"}
STATUS_SCORE_ADJUSTMENT = {
    MemoryStatus.ARCHIVED: -0.45,
    MemoryStatus.SUPERSEDED: -0.40,
}


@dataclass(frozen=True)
class _LexicalMatch:
    relevance: float
    token_overlap: float
    matched_terms: list[str]
    exact_terms: list[str]
    phrase_match: bool
    substring_match: bool


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
    lexical_match = _lexical_match(query, _searchable_text(memory))
    keyword_relevance = lexical_match.relevance
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
        + active_policy.freshness_weight
    )
    if query.strip():
        total_weight += active_policy.relevance_weight
    total = weighted_total / total_weight if total_weight > 0 else 0.0
    total += LAYER_SCORE_ADJUSTMENT.get(memory.layer, 0.0)
    total += _status_adjustment(memory)
    total = min(max(total, 0.0), 1.0)

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
            lexical_match=lexical_match,
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


def _lexical_match(query: str, content: str) -> _LexicalMatch:
    query_tokens_list = _tokens(query)
    query_tokens = set(query_tokens_list)
    if not query_tokens:
        return _LexicalMatch(0.0, 0.0, [], [], False, False)

    content_tokens_list = _tokens(content)
    content_tokens = set(content_tokens_list)
    if not content_tokens:
        return _LexicalMatch(0.0, 0.0, [], [], False, False)

    matched_terms = sorted(query_tokens & content_tokens)
    token_overlap = len(matched_terms) / len(query_tokens)
    raw_query_tokens = set(_raw_tokens(query))
    raw_content_tokens = set(_raw_tokens(content))
    exact_terms = sorted(raw_query_tokens & raw_content_tokens)
    exact_term_ratio = len(exact_terms) / len(raw_query_tokens) if raw_query_tokens else 0.0
    phrase_match = 2 <= len(query_tokens_list) <= 6 and _contains_sequence(content_tokens_list, query_tokens_list)
    substring_match = bool(query_tokens_list) and " ".join(query_tokens_list) in " ".join(content_tokens_list)
    relevance = min(
        token_overlap * 0.75
        + exact_term_ratio * 0.15
        + (0.10 if phrase_match else 0.0)
        + (0.10 if substring_match else 0.0),
        1.0,
    )
    return _LexicalMatch(
        relevance=relevance,
        token_overlap=token_overlap,
        matched_terms=matched_terms,
        exact_terms=exact_terms,
        phrase_match=phrase_match,
        substring_match=substring_match,
    )


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
            memory.layer.value,
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
    lexical_match: _LexicalMatch,
    semantic_relevance: float | None,
    embedding_provider_name: str | None,
) -> list[str]:
    reasons = [f"Matched query term: {term}" for term in lexical_match.exact_terms]
    normalized_only = sorted(set(lexical_match.matched_terms) - set(lexical_match.exact_terms))
    reasons.extend(f"Normalized query term match: {term}" for term in normalized_only)
    if len(lexical_match.matched_terms) > 1:
        reasons.append(f"Multi-token query overlap: {lexical_match.token_overlap:.2f}")
    if lexical_match.phrase_match:
        reasons.append("Short query phrase match")
    if lexical_match.substring_match:
        reasons.append("Exact content substring match")
    layer_reason = _layer_reason(memory.layer)
    if layer_reason is not None:
        reasons.append(layer_reason)
    if semantic_relevance is not None and embedding_provider_name is not None:
        reasons.append(
            f"Semantic similarity {semantic_relevance:.2f} from embedding provider '{embedding_provider_name}'"
        )
    if memory.status is MemoryStatus.ARCHIVED:
        reasons.append("Archived memory penalty applied")
    elif memory.status is MemoryStatus.SUPERSEDED:
        reasons.append("Superseded memory penalty applied")
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


def _layer_reason(layer: MemoryLayer) -> str | None:
    if layer is MemoryLayer.OPERATIONAL:
        return "Operational layer retrieval boost applied"
    if layer is MemoryLayer.WORKING:
        return "Working layer retrieval boost applied"
    if layer is MemoryLayer.SEMANTIC:
        return "Semantic layer retrieval boost applied"
    if layer is MemoryLayer.ARCHIVED:
        return "Archived layer retrieval penalty applied"
    if layer is MemoryLayer.SHORT_TERM:
        return "Short-term layer retrieval penalty applied"
    return None


def _tokens(text: str) -> list[str]:
    return [_normalize_token(token) for token in _raw_tokens(text)]


def _raw_tokens(text: str) -> list[str]:
    return [token.lower() for token in TOKEN_PATTERN.findall(text) if token.lower() not in STOPWORDS]


def _normalize_token(token: str) -> str:
    normalized = token.lower()
    if len(normalized) > 4 and normalized.endswith("ies"):
        return f"{normalized[:-3]}y"
    if len(normalized) > 4 and normalized.endswith(("ches", "shes", "xes", "zes", "ses")):
        return normalized[:-2]
    if len(normalized) > 3 and normalized.endswith("s") and not normalized.endswith(("ss", "us", "is")):
        return normalized[:-1]
    return normalized


def _contains_sequence(content_tokens: list[str], query_tokens: list[str]) -> bool:
    query_length = len(query_tokens)
    return any(
        content_tokens[index : index + query_length] == query_tokens
        for index in range(len(content_tokens) - query_length + 1)
    )


def session_adjusted_score(
    score: MemoryScore,
    *,
    memory: Memory,
    current_session_id: str | None,
    related_session_ids: set[str] | None = None,
    query: str = "",
) -> MemoryScore:
    """Apply bounded current-session and continuity boosts to a score."""
    boost = 0.0
    reason: str | None = None
    if current_session_id is not None and memory.session_id == current_session_id:
        if _is_temporally_local_query(query):
            boost = TEMPORAL_CURRENT_SESSION_BOOST
            reason = "Temporal query boost applied for active session"
        else:
            boost = CURRENT_SESSION_BOOST
            reason = "Session match boost applied for active session"
    elif memory.session_id is not None and memory.session_id in (related_session_ids or set()):
        boost = RELATED_SESSION_BOOST
        reason = "Related session continuity boost applied"
    if reason is None:
        return score
    return score.model_copy(update={"total": min(score.total + boost, 1.0), "reasons": [*score.reasons, reason]})


def score_trace_data(
    memory: Memory,
    score: MemoryScore,
    *,
    query: str,
    current_session_id: str | None = None,
    related_session_ids: set[str] | None = None,
) -> dict[str, Any]:
    """Return stable, JSON-compatible retrieval diagnostics for one memory."""
    lexical_match = _lexical_match(query, _searchable_text(memory))
    current_session_boost = 0.0
    continuity_boost = 0.0
    if current_session_id is not None and memory.session_id == current_session_id:
        current_session_boost = (
            TEMPORAL_CURRENT_SESSION_BOOST if _is_temporally_local_query(query) else CURRENT_SESSION_BOOST
        )
    elif memory.session_id is not None and memory.session_id in (related_session_ids or set()):
        continuity_boost = RELATED_SESSION_BOOST
    return {
        "memory_id": memory.id,
        "content_preview": memory.content[:160],
        "memory_type": memory.memory_type.value,
        "layer": memory.layer.value,
        "status": memory.status.value,
        "session_id": memory.session_id,
        "importance": memory.importance,
        "access_count": memory.access_count,
        "recency_component": score.recency,
        "frequency_component": score.frequency,
        "freshness_component": score.freshness,
        "keyword_relevance_component": round(lexical_match.relevance, 6),
        "overall_relevance_component": score.relevance,
        "semantic_relevance_component": score.semantic_relevance,
        "matched_query_terms": lexical_match.matched_terms,
        "exact_query_terms": lexical_match.exact_terms,
        "phrase_match": lexical_match.phrase_match,
        "substring_match": lexical_match.substring_match,
        "hierarchy_layer_adjustment": LAYER_SCORE_ADJUSTMENT.get(memory.layer, 0.0),
        "status_adjustment": _status_adjustment(memory),
        "current_session_boost": current_session_boost,
        "continuity_boost": continuity_boost,
        "final_score": score.total,
        "score_reasons": score.reasons,
    }


def _is_temporally_local_query(query: str) -> bool:
    return bool(set(_raw_tokens(query)) & TEMPORAL_QUERY_TERMS)


def _status_adjustment(memory: Memory) -> float:
    if memory.status is MemoryStatus.ARCHIVED and memory.layer is MemoryLayer.ARCHIVED:
        return 0.0
    return STATUS_SCORE_ADJUSTMENT.get(memory.status, 0.0)
