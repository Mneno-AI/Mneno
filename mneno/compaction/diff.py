"""Utilities for explainable compaction diffs."""

from __future__ import annotations

from mneno.models import CompactionDecision, CompactionDecisionType, CompactionDiff, CompactionStats


def create_empty_diff() -> CompactionDiff:
    """Create an empty compaction diff template."""
    return CompactionDiff()


def add_decision(
    diff: CompactionDiff,
    *,
    memory_id: str,
    decision: CompactionDecisionType,
    reason: str,
    score_before: float = 0.0,
    related_memory_ids: list[str] | None = None,
    resulting_memory_id: str | None = None,
) -> CompactionDiff:
    """Return a new diff with one explainable compaction decision recorded."""
    data = diff.model_copy(deep=True)
    compaction_decision = CompactionDecision(
        memory_id=memory_id,
        decision=decision,
        reason=reason,
        score_before=score_before,
        related_memory_ids=related_memory_ids or [],
        resulting_memory_id=resulting_memory_id,
    )
    if decision is CompactionDecisionType.KEPT:
        data.kept.append(compaction_decision)
    elif decision is CompactionDecisionType.MERGED:
        data.merged.append(compaction_decision)
    elif decision is CompactionDecisionType.DISCARDED:
        data.discarded.append(compaction_decision)
    data.stats = CompactionStats(
        before_count=data.stats.before_count,
        after_count=len(data.kept) + len(data.created),
        kept_count=len(data.kept),
        merged_count=len(data.merged),
        discarded_count=len(data.discarded),
        created_count=len(data.created),
        estimated_reduction_ratio=data.stats.estimated_reduction_ratio,
    )
    return data
