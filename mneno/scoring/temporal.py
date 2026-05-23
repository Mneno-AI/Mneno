"""Temporal memory scoring with keyword relevance placeholder logic."""

from __future__ import annotations

import math
import re
from datetime import UTC, datetime

from mneno.models import Memory, MemoryPolicy, MemoryScore

TOKEN_PATTERN = re.compile(r"[a-zA-Z0-9]+")


class TemporalMemoryScorer:
    """Score memories using recency, importance, access frequency, and keyword overlap."""

    def __init__(self, *, policy: MemoryPolicy | None = None) -> None:
        self.policy = policy or MemoryPolicy()

    def score(self, memory: Memory, *, query: str = "") -> MemoryScore:
        """Score a memory for a query."""
        return calculate_memory_score(memory, query=query, policy=self.policy)


def calculate_memory_score(memory: Memory, *, query: str = "", policy: MemoryPolicy | None = None) -> MemoryScore:
    """Calculate a bounded, explainable score for a memory."""
    active_policy = policy or MemoryPolicy()
    recency = _recency_score(memory.updated_at, half_life_days=active_policy.recency_half_life_days)
    access = min(memory.access_count / 10.0, 1.0)
    relevance = _keyword_overlap(query, memory.content)

    weighted_total = (
        recency * active_policy.recency_weight
        + memory.importance * active_policy.importance_weight
        + access * active_policy.access_weight
        + relevance * active_policy.relevance_weight
    )
    total_weight = (
        active_policy.recency_weight
        + active_policy.importance_weight
        + active_policy.access_weight
        + active_policy.relevance_weight
    )
    total = weighted_total / total_weight if total_weight > 0 else 0.0

    return MemoryScore(
        memory_id=memory.id,
        recency=round(recency, 6),
        importance=memory.importance,
        access_count=round(access, 6),
        relevance=round(relevance, 6),
        total=round(min(max(total, 0.0), 1.0), 6),
        reasons=[
            "recent memories are favored",
            "importance is provided by the caller or policy default",
            "access count is normalized with a simple cap",
            "query relevance uses temporary keyword overlap until semantic retrieval exists",
        ],
    )


def _recency_score(updated_at: datetime, *, half_life_days: float) -> float:
    now = datetime.now(UTC)
    if updated_at.tzinfo is None:
        updated_at = updated_at.replace(tzinfo=UTC)
    age_seconds = max((now - updated_at).total_seconds(), 0.0)
    half_life_seconds = half_life_days * 24 * 60 * 60
    return math.exp(-math.log(2) * age_seconds / half_life_seconds)


def _keyword_overlap(query: str, content: str) -> float:
    query_tokens = set(_tokens(query))
    if not query_tokens:
        return 0.0

    content_tokens = set(_tokens(content))
    if not content_tokens:
        return 0.0

    return len(query_tokens & content_tokens) / len(query_tokens)


def _tokens(text: str) -> list[str]:
    return [token.lower() for token in TOKEN_PATTERN.findall(text)]
