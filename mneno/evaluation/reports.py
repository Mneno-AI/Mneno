"""Serializable evaluation reports and operation results."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from mneno.evaluation.metrics import MetricResult
from mneno.models import utc_now


class SerializableEvaluationModel(BaseModel):
    """Base model with stable dict and JSON export helpers."""

    model_config = ConfigDict(extra="forbid")

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-compatible dictionary."""
        return self.model_dump(mode="json")

    def to_json(self) -> str:
        """Return stable JSON text."""
        return json.dumps(self.to_dict(), indent=2, sort_keys=True)


class EvaluationReport(SerializableEvaluationModel):
    """Top-level evaluation report for benchmark runs."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(default_factory=lambda: str(uuid4()))
    benchmark_name: str = Field(min_length=1)
    created_at: datetime = Field(default_factory=utc_now)
    metrics: list[MetricResult] = Field(default_factory=list)
    trace_ids: list[str] = Field(default_factory=list)
    summary: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class SearchEvaluationResult(SerializableEvaluationModel):
    """Standardized search evaluation result."""

    model_config = ConfigDict(extra="forbid")

    query: str
    result_count: int = Field(ge=0)
    candidate_count: int = Field(ge=0)
    latency_ms: float = Field(ge=0.0)
    trace_id: str | None = None
    metrics: list[MetricResult] = Field(default_factory=list)
    selected_memory_ids: list[str] = Field(default_factory=list)
    relevant_memory_ids: list[str] = Field(default_factory=list)
    memories_scanned: int = Field(ge=0)
    explainability_event_count: int = Field(ge=0)
    trace_ids: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @property
    def selected_count(self) -> int:
        """Backward-compatible alias for result_count."""
        return self.result_count


class ContextEvaluationResult(SerializableEvaluationModel):
    """Standardized context-building evaluation result."""

    model_config = ConfigDict(extra="forbid")

    query: str
    included_count: int = Field(ge=0)
    excluded_count: int = Field(ge=0)
    estimated_tokens: int = Field(ge=0)
    budget: int = Field(ge=0)
    latency_ms: float = Field(ge=0.0)
    trace_id: str | None = None
    metrics: list[MetricResult] = Field(default_factory=list)
    included_memory_ids: list[str] = Field(default_factory=list)
    excluded_memory_ids: list[str] = Field(default_factory=list)
    candidate_count: int = Field(ge=0)
    explainability_event_count: int = Field(ge=0)
    trace_ids: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @property
    def token_count(self) -> int:
        """Backward-compatible alias for estimated_tokens."""
        return self.estimated_tokens

    @property
    def available_tokens(self) -> int:
        """Backward-compatible alias for budget."""
        return self.budget

    @property
    def selected_count(self) -> int:
        """Backward-compatible alias for included_count."""
        return self.included_count


class CompactionEvaluationResult(SerializableEvaluationModel):
    """Standardized compaction evaluation result."""

    model_config = ConfigDict(extra="forbid")

    before_count: int = Field(ge=0)
    after_count: int = Field(ge=0)
    reduction_ratio: float = Field(ge=0.0, le=1.0)
    latency_ms: float = Field(ge=0.0)
    trace_id: str | None = None
    metrics: list[MetricResult] = Field(default_factory=list)
    kept_count: int = Field(ge=0)
    merged_count: int = Field(ge=0)
    discarded_count: int = Field(ge=0)
    created_count: int = Field(ge=0)
    explainability_event_count: int = Field(ge=0)
    trace_ids: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
