"""Compaction policy configuration."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator

from mneno.models import MemoryType, normalize_tags


class CompactionPolicy(BaseModel):
    """Controls deterministic local memory compaction behavior."""

    model_config = ConfigDict(extra="forbid")

    max_memories: int | None = Field(default=None, gt=0)
    min_score_to_keep: float = Field(default=0.20, ge=0.0, le=1.0)
    merge_duplicates: bool = True
    discard_stale: bool = True
    stale_after_days: int | None = Field(default=180, gt=0)
    preserve_memory_types: list[MemoryType] = Field(
        default_factory=lambda: [MemoryType.OPERATIONAL, MemoryType.PREFERENCE]
    )
    preserve_tags: list[str] = Field(default_factory=list)
    explain: bool = True

    @field_validator("preserve_tags")
    @classmethod
    def validate_preserve_tags(cls, tags: list[str]) -> list[str]:
        """Normalize preserved tags."""
        return normalize_tags(tags)
