"""Explainable context package models."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from mneno.context.policies import ContextPolicy


class ContextItem(BaseModel):
    """A memory included in a built context package."""

    model_config = ConfigDict(extra="forbid")

    memory_id: str
    content: str
    score: float = Field(ge=0.0, le=1.0)
    estimated_tokens: int = Field(gt=0)
    reason: str = Field(min_length=1)


class ExcludedContextItem(BaseModel):
    """A memory excluded from a built context package."""

    model_config = ConfigDict(extra="forbid")

    memory_id: str
    content: str
    score: float = Field(ge=0.0, le=1.0)
    estimated_tokens: int = Field(gt=0)
    reason: str = Field(min_length=1)


class ContextStats(BaseModel):
    """Aggregate statistics for a built context package."""

    model_config = ConfigDict(extra="forbid")

    max_tokens: int = Field(gt=0)
    reserve_tokens: int = Field(ge=0)
    available_tokens: int = Field(ge=0)
    used_tokens: int = Field(ge=0)
    remaining_tokens: int = Field(ge=0)
    included_count: int = Field(ge=0)
    excluded_count: int = Field(ge=0)
    total_candidates: int = Field(ge=0)
    policy_name: str | None = None
    preset: str | None = None
    min_score: float = Field(ge=0.0, le=1.0)
    max_items: int | None = Field(default=None, gt=0)
    strategy: str
    candidate_count_before_filter: int = Field(ge=0)
    candidate_count_after_filter: int = Field(ge=0)


class ContextPackage(BaseModel):
    """Final context text plus inclusion and exclusion explanations."""

    model_config = ConfigDict(extra="forbid")

    query: str
    text: str
    policy_name: str | None = None
    policy: ContextPolicy
    preset: str | None = None
    included: list[ContextItem] = Field(default_factory=list)
    excluded: list[ExcludedContextItem] = Field(default_factory=list)
    stats: ContextStats
    trace_id: str | None = None
