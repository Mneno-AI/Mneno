"""Core Pydantic models for Mneno."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


def utc_now() -> datetime:
    """Return a timezone-aware UTC timestamp."""
    return datetime.now(UTC)


class MemoryType(StrEnum):
    """Supported memory categories for the MVP runtime."""

    FACT = "fact"
    PREFERENCE = "preference"
    INSTRUCTION = "instruction"
    EVENT = "event"
    SUMMARY = "summary"


class CompactionDecision(StrEnum):
    """Possible outcomes for a memory during compaction."""

    KEPT = "kept"
    MERGED = "merged"
    DISCARDED = "discarded"


class Memory(BaseModel):
    """A durable unit of agent memory."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(default_factory=lambda: str(uuid4()))
    content: str = Field(min_length=1)
    memory_type: MemoryType = MemoryType.FACT
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    importance: float = Field(default=0.5, ge=0.0, le=1.0)
    access_count: int = Field(default=0, ge=0)


class MemoryScore(BaseModel):
    """Explainable score components used to rank memories."""

    model_config = ConfigDict(extra="forbid")

    memory_id: str
    recency: float = Field(ge=0.0, le=1.0)
    importance: float = Field(ge=0.0, le=1.0)
    access_count: float = Field(ge=0.0, le=1.0)
    relevance: float = Field(ge=0.0, le=1.0)
    total: float = Field(ge=0.0, le=1.0)
    reasons: list[str] = Field(default_factory=list)


class CompactionDiff(BaseModel):
    """Explainable template for future memory compaction output."""

    model_config = ConfigDict(extra="forbid")

    kept: list[str] = Field(default_factory=list)
    merged: list[str] = Field(default_factory=list)
    discarded: list[str] = Field(default_factory=list)
    reasons: dict[str, str] = Field(default_factory=dict)


class MemoryPolicy(BaseModel):
    """Runtime policy controlling lightweight scoring and future compaction."""

    model_config = ConfigDict(extra="forbid")

    default_importance: float = Field(default=0.5, ge=0.0, le=1.0)
    recency_weight: float = Field(default=0.25, ge=0.0, le=1.0)
    importance_weight: float = Field(default=0.35, ge=0.0, le=1.0)
    access_weight: float = Field(default=0.15, ge=0.0, le=1.0)
    relevance_weight: float = Field(default=0.25, ge=0.0, le=1.0)
    recency_half_life_days: float = Field(default=30.0, gt=0.0)
    max_context_memories: int = Field(default=20, gt=0)
