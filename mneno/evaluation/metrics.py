"""Deterministic evaluation metrics for Mneno Bench integration."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class MetricResult(BaseModel):
    """A single deterministic evaluation metric."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    value: float
    unit: str = Field(min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)


def precision_at_k(retrieved_ids: list[str], relevant_ids: list[str], k: int) -> float:
    """Return precision@k for retrieved IDs."""
    if k <= 0:
        raise ValueError("k must be greater than 0")
    selected = retrieved_ids[:k]
    if not selected:
        return 0.0
    relevant = set(relevant_ids)
    return len([memory_id for memory_id in selected if memory_id in relevant]) / len(selected)


def recall_at_k(retrieved_ids: list[str], relevant_ids: list[str], k: int) -> float:
    """Return recall@k for retrieved IDs."""
    if k <= 0:
        raise ValueError("k must be greater than 0")
    relevant = set(relevant_ids)
    if not relevant:
        return 0.0
    selected = set(retrieved_ids[:k])
    return len(selected & relevant) / len(relevant)


def mean_reciprocal_rank(retrieved_ids: list[str], relevant_ids: list[str]) -> float:
    """Return reciprocal rank for one query."""
    relevant = set(relevant_ids)
    if not relevant:
        return 0.0
    for index, memory_id in enumerate(retrieved_ids, start=1):
        if memory_id in relevant:
            return 1.0 / index
    return 0.0


def token_efficiency_ratio(selected_tokens: int, available_tokens: int) -> float:
    """Return selected token usage divided by available token budget."""
    if available_tokens <= 0:
        raise ValueError("available_tokens must be greater than 0")
    return selected_tokens / available_tokens


def reduction_ratio(before_count: int, after_count: int) -> float:
    """Return structural reduction ratio."""
    if before_count < 0 or after_count < 0:
        raise ValueError("counts must be non-negative")
    if before_count == 0:
        return 0.0
    return max((before_count - after_count) / before_count, 0.0)


def metric(name: str, value: float, *, unit: str = "ratio", metadata: dict[str, Any] | None = None) -> MetricResult:
    """Create a rounded metric result."""
    return MetricResult(name=name, value=round(value, 6), unit=unit, metadata=metadata or {})
