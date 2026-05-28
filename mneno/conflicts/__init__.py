"""Conflict detection and safe memory resolution."""

from mneno.conflicts.detector import ConflictDetector
from mneno.conflicts.policies import ConflictPolicy
from mneno.conflicts.reports import (
    AddMemoryResult,
    ConflictAction,
    ConflictReport,
    ConflictSeverity,
    ConflictType,
)
from mneno.conflicts.resolver import ConflictResolutionResult, ConflictResolver

__all__ = [
    "AddMemoryResult",
    "ConflictAction",
    "ConflictDetector",
    "ConflictPolicy",
    "ConflictReport",
    "ConflictResolutionResult",
    "ConflictResolver",
    "ConflictSeverity",
    "ConflictType",
]
