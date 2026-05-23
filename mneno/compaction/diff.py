"""Utilities for explainable compaction diffs."""

from __future__ import annotations

from mneno.models import CompactionDecision, CompactionDiff


def create_empty_diff() -> CompactionDiff:
    """Create an empty compaction diff template."""
    return CompactionDiff()


def add_decision(diff: CompactionDiff, *, memory_id: str, decision: CompactionDecision, reason: str) -> CompactionDiff:
    """Return a new diff with one explainable compaction decision recorded."""
    data = diff.model_copy(deep=True)
    if decision is CompactionDecision.KEPT:
        data.kept.append(memory_id)
    elif decision is CompactionDecision.MERGED:
        data.merged.append(memory_id)
    elif decision is CompactionDecision.DISCARDED:
        data.discarded.append(memory_id)
    data.reasons[memory_id] = reason
    return data
