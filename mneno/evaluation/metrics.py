"""Deterministic evaluation metrics for Mneno Bench integration."""

from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class MetricResult(BaseModel):
    """A single deterministic evaluation metric."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    value: float | int
    unit: str | None = Field(default=None, min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-compatible metric dictionary."""
        return self.model_dump(mode="json")

    def to_json(self) -> str:
        """Return stable metric JSON text."""
        return json.dumps(self.to_dict(), indent=2, sort_keys=True)


def precision_at_k(relevant_ids: list[str], retrieved_ids: list[str], k: int) -> float:
    """Return precision@k for retrieved IDs."""
    if k <= 0:
        raise ValueError("k must be greater than 0")
    selected = retrieved_ids[:k]
    if not selected:
        return 0.0
    relevant = set(relevant_ids)
    return len([memory_id for memory_id in selected if memory_id in relevant]) / len(selected)


def recall_at_k(relevant_ids: list[str], retrieved_ids: list[str], k: int) -> float:
    """Return recall@k for retrieved IDs."""
    if k <= 0:
        raise ValueError("k must be greater than 0")
    relevant = set(relevant_ids)
    if not relevant:
        return 0.0
    selected = set(retrieved_ids[:k])
    return len(selected & relevant) / len(relevant)


def mean_reciprocal_rank(relevant_ids: list[str], retrieved_ids: list[str]) -> float:
    """Return reciprocal rank for one query."""
    relevant = set(relevant_ids)
    if not relevant:
        return 0.0
    for index, memory_id in enumerate(retrieved_ids, start=1):
        if memory_id in relevant:
            return 1.0 / index
    return 0.0


def token_efficiency_ratio(original_tokens: int, final_tokens: int) -> float:
    """Return the fraction of original tokens removed from the final output."""
    _validate_non_negative_tokens(original_tokens, final_tokens)
    if original_tokens == 0:
        return 0.0
    return max((original_tokens - final_tokens) / original_tokens, 0.0)


def reduction_ratio(before_count: int, after_count: int) -> float:
    """Return structural reduction ratio."""
    if before_count < 0 or after_count < 0:
        raise ValueError("counts must be non-negative")
    if before_count == 0:
        return 0.0
    return max((before_count - after_count) / before_count, 0.0)


def context_utilization_ratio(used_tokens: int, available_tokens: int) -> float:
    """Return the fraction of available context budget used."""
    _validate_non_negative_tokens(used_tokens, available_tokens)
    if available_tokens == 0:
        return 0.0
    return min(used_tokens / available_tokens, 1.0)


def metric(
    name: str,
    value: float | int,
    *,
    unit: str | None = "ratio",
    metadata: dict[str, Any] | None = None,
) -> MetricResult:
    """Create a rounded metric result."""
    rounded_value = round(value, 6) if isinstance(value, float) else value
    return MetricResult(name=name, value=rounded_value, unit=unit, metadata=metadata or {})


def _validate_non_negative_tokens(first: int, second: int) -> None:
    if first < 0 or second < 0:
        raise ValueError("token counts must be non-negative")
