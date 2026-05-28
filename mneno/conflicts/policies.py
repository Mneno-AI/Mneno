"""Conflict detection and resolution policy models."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ConflictPolicy(BaseModel):
    """Policy controlling deterministic conflict detection and safe resolution."""

    model_config = ConfigDict(extra="forbid")

    detect_duplicates: bool = True
    detect_preference_changes: bool = True
    detect_negations: bool = True
    auto_supersede_preferences: bool = True
    auto_archive_duplicates: bool = False
    mark_conflicts: bool = True
    similarity_threshold: float = Field(default=0.75, ge=0.0, le=1.0)
