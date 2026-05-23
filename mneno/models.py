"""Core Pydantic models for Mneno."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator


def utc_now() -> datetime:
    """Return a timezone-aware UTC timestamp."""
    return datetime.now(UTC)


def normalize_tags(tags: list[str]) -> list[str]:
    """Normalize tags while preserving their input order."""
    normalized: list[str] = []
    seen: set[str] = set()
    for tag in tags:
        clean_tag = tag.strip().lower()
        if not clean_tag:
            raise ValueError("tags must not be empty")
        if clean_tag not in seen:
            normalized.append(clean_tag)
            seen.add(clean_tag)
    return normalized


class MemoryType(StrEnum):
    """Supported memory categories for the MVP runtime."""

    EPISODIC = "episodic"
    SEMANTIC = "semantic"
    OPERATIONAL = "operational"
    PREFERENCE = "preference"


class CompactionDecisionType(StrEnum):
    """Possible outcomes for a memory during compaction."""

    KEPT = "kept"
    MERGED = "merged"
    DISCARDED = "discarded"


class Memory(BaseModel):
    """A durable unit of agent memory."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(default_factory=lambda: str(uuid4()))
    content: str = Field(min_length=1)
    memory_type: MemoryType = MemoryType.SEMANTIC
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    importance: float = Field(default=0.5, ge=0.0, le=1.0)
    access_count: int = Field(default=0, ge=0)
    last_accessed_at: datetime | None = None
    source: str | None = Field(default=None, min_length=1)
    tags: list[str] = Field(default_factory=list)

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, tags: list[str]) -> list[str]:
        """Normalize memory tags."""
        return normalize_tags(tags)


class MemoryScore(BaseModel):
    """Explainable score components used to rank memories."""

    model_config = ConfigDict(extra="forbid")

    memory_id: str
    total: float = Field(ge=0.0, le=1.0)
    relevance: float = Field(ge=0.0, le=1.0)
    importance: float = Field(ge=0.0, le=1.0)
    recency: float = Field(ge=0.0, le=1.0)
    frequency: float = Field(ge=0.0, le=1.0)
    freshness: float = Field(ge=0.0, le=1.0)
    reasons: list[str] = Field(default_factory=list)


class MemorySearchResult(BaseModel):
    """A ranked memory result with an explainable score."""

    model_config = ConfigDict(extra="forbid")

    memory: Memory
    score: MemoryScore
    rank: int = Field(gt=0)


class AddMemoryRequest(BaseModel):
    """Validated request for creating a memory."""

    model_config = ConfigDict(extra="forbid")

    content: str = Field(min_length=1)
    memory_type: MemoryType = MemoryType.SEMANTIC
    importance: float = Field(default=0.5, ge=0.0, le=1.0)
    metadata: dict[str, Any] = Field(default_factory=dict)
    source: str | None = Field(default=None, min_length=1)
    tags: list[str] = Field(default_factory=list)

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, tags: list[str]) -> list[str]:
        """Normalize request tags using the same rules as Memory."""
        return normalize_tags(tags)


class SearchMemoryRequest(BaseModel):
    """Validated request for searching memories."""

    model_config = ConfigDict(extra="forbid")

    query: str = Field(min_length=1)
    limit: int = Field(default=5, gt=0)


class CompactionDecision(BaseModel):
    """Explainable decision for one memory processed during compaction."""

    model_config = ConfigDict(extra="forbid")

    memory_id: str
    decision: CompactionDecisionType
    reason: str = Field(min_length=1)
    score_before: float = Field(ge=0.0, le=1.0)
    related_memory_ids: list[str] = Field(default_factory=list)
    resulting_memory_id: str | None = None


class CompactionStats(BaseModel):
    """Aggregate statistics for a compaction operation."""

    model_config = ConfigDict(extra="forbid")

    before_count: int = Field(ge=0)
    after_count: int = Field(ge=0)
    kept_count: int = Field(ge=0)
    merged_count: int = Field(ge=0)
    discarded_count: int = Field(ge=0)
    created_count: int = Field(ge=0)
    estimated_reduction_ratio: float = Field(ge=0.0, le=1.0)


class CompactionDiff(BaseModel):
    """Explainable template for future memory compaction output."""

    model_config = ConfigDict(extra="forbid")

    kept: list[CompactionDecision] = Field(default_factory=list)
    merged: list[CompactionDecision] = Field(default_factory=list)
    discarded: list[CompactionDecision] = Field(default_factory=list)
    created: list[Memory] = Field(default_factory=list)
    summary: str = ""
    stats: CompactionStats = Field(
        default_factory=lambda: CompactionStats(
            before_count=0,
            after_count=0,
            kept_count=0,
            merged_count=0,
            discarded_count=0,
            created_count=0,
            estimated_reduction_ratio=0.0,
        )
    )


class MemoryPolicy(BaseModel):
    """Runtime policy controlling lightweight scoring and future compaction."""

    model_config = ConfigDict(extra="forbid")

    default_importance: float = Field(default=0.5, ge=0.0, le=1.0)
    recency_weight: float = Field(default=0.25, ge=0.0, le=1.0)
    importance_weight: float = Field(default=0.35, ge=0.0, le=1.0)
    access_weight: float = Field(default=0.15, ge=0.0, le=1.0)
    relevance_weight: float = Field(default=0.25, ge=0.0, le=1.0)
    freshness_weight: float = Field(default=0.10, ge=0.0, le=1.0)
    recency_half_life_days: float = Field(default=30.0, gt=0.0)
    freshness_decay_days: float = Field(default=180.0, gt=0.0)
    max_context_memories: int = Field(default=20, gt=0)
