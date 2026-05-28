"""Serializable evaluation reports and operation results."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from mneno.evaluation.metrics import MetricResult
from mneno.models import utc_now


class EvaluationReport(BaseModel):
    """Top-level evaluation report for benchmark runs."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(default_factory=lambda: str(uuid4()))
    benchmark_name: str = Field(min_length=1)
    created_at: datetime = Field(default_factory=utc_now)
    metrics: list[MetricResult] = Field(default_factory=list)
    trace_ids: list[str] = Field(default_factory=list)
    summary: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class SearchEvaluationResult(BaseModel):
    """Standardized search evaluation result."""

    model_config = ConfigDict(extra="forbid")

    query: str
    selected_memory_ids: list[str] = Field(default_factory=list)
    relevant_memory_ids: list[str] = Field(default_factory=list)
    candidate_count: int = Field(ge=0)
    selected_count: int = Field(ge=0)
    memories_scanned: int = Field(ge=0)
    explainability_event_count: int = Field(ge=0)
    latency_ms: float = Field(ge=0.0)
    metrics: list[MetricResult] = Field(default_factory=list)
    trace_ids: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ContextEvaluationResult(BaseModel):
    """Standardized context-building evaluation result."""

    model_config = ConfigDict(extra="forbid")

    query: str
    included_memory_ids: list[str] = Field(default_factory=list)
    excluded_memory_ids: list[str] = Field(default_factory=list)
    token_count: int = Field(ge=0)
    available_tokens: int = Field(ge=0)
    candidate_count: int = Field(ge=0)
    selected_count: int = Field(ge=0)
    explainability_event_count: int = Field(ge=0)
    latency_ms: float = Field(ge=0.0)
    metrics: list[MetricResult] = Field(default_factory=list)
    trace_ids: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class CompactionEvaluationResult(BaseModel):
    """Standardized compaction evaluation result."""

    model_config = ConfigDict(extra="forbid")

    before_count: int = Field(ge=0)
    after_count: int = Field(ge=0)
    kept_count: int = Field(ge=0)
    merged_count: int = Field(ge=0)
    discarded_count: int = Field(ge=0)
    created_count: int = Field(ge=0)
    explainability_event_count: int = Field(ge=0)
    latency_ms: float = Field(ge=0.0)
    metrics: list[MetricResult] = Field(default_factory=list)
    trace_ids: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
