"""Conflict report models for memory lifecycle decisions."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from mneno.models import Memory, utc_now


class ConflictType(StrEnum):
    """Supported deterministic conflict categories."""

    CONTRADICTION = "contradiction"
    SUPERSESSION = "supersession"
    DUPLICATE = "duplicate"
    STALE_CONFLICT = "stale_conflict"
    PREFERENCE_CHANGE = "preference_change"
    OPERATIONAL_CHANGE = "operational_change"


class ConflictSeverity(StrEnum):
    """Conflict severity used by reports and resolution policy."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ConflictAction(StrEnum):
    """Suggested safe resolution actions."""

    KEEP_BOTH = "keep_both"
    SUPERSEDE_EXISTING = "supersede_existing"
    MARK_CONFLICTED = "mark_conflicted"
    ARCHIVE_EXISTING = "archive_existing"
    MERGE = "merge"


class ConflictReport(BaseModel):
    """Explainable report for a detected relationship between memories."""

    model_config = ConfigDict(extra="forbid")

    conflict_id: str = Field(default_factory=lambda: str(uuid4()))
    conflict_type: ConflictType
    severity: ConflictSeverity
    new_memory_id: str
    existing_memory_id: str
    reason: str = Field(min_length=1)
    evidence: list[str] = Field(default_factory=list)
    suggested_action: ConflictAction
    created_at: datetime = Field(default_factory=utc_now)


class AddMemoryResult(BaseModel):
    """Richer add result including conflict detection and resolution details."""

    model_config = ConfigDict(extra="forbid")

    memory: Memory
    conflict_reports: list[ConflictReport] = Field(default_factory=list)
    resolution_actions: list[str] = Field(default_factory=list)
    trace_id: str | None = None
