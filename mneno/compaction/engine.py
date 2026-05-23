"""Deterministic local memory compaction engine."""

from __future__ import annotations

import re
from collections.abc import Iterable
from datetime import UTC, datetime
from typing import Any

from mneno.compaction.policies import CompactionPolicy
from mneno.models import (
    CompactionDecision,
    CompactionDecisionType,
    CompactionDiff,
    CompactionStats,
    Memory,
    MemoryScore,
    MemoryType,
    utc_now,
)
from mneno.providers.llm import LLMProvider
from mneno.scoring.temporal import TemporalMemoryScorer

TOKEN_PATTERN = re.compile(r"[a-zA-Z0-9]+")
NEAR_DUPLICATE_THRESHOLD = 0.75
HIGH_IMPORTANCE_THRESHOLD = 0.75


class CompactionEngine:
    """Compact memories locally while preserving explainable decisions."""

    def __init__(
        self,
        *,
        policy: CompactionPolicy | None = None,
        scorer: TemporalMemoryScorer | None = None,
        llm_provider: LLMProvider | None = None,
    ) -> None:
        self.policy = policy or CompactionPolicy()
        self.scorer = scorer or TemporalMemoryScorer()
        self.llm_provider = llm_provider

    def compact(self, memories: list[Memory], *, policy: CompactionPolicy | None = None) -> CompactionDiff:
        """Analyze memories and return an explainable compaction diff."""
        active_policy = policy or self.policy
        scores = {memory.id: self.scorer.score(memory) for memory in memories}
        merged_groups = self._find_merge_groups(memories) if active_policy.merge_duplicates else []
        merged_ids = {memory.id for group in merged_groups for memory in group}

        kept: list[CompactionDecision] = []
        merged: list[CompactionDecision] = []
        discarded: list[CompactionDecision] = []
        created: list[Memory] = []

        for group in merged_groups:
            consolidated = self._merge_group(group)
            created.append(consolidated)
            related_ids = [memory.id for memory in group]
            reason = f"Merged with {len(group) - 1} similar memories based on token overlap"
            for memory in group:
                merged.append(
                    self._decision(
                        memory,
                        CompactionDecisionType.MERGED,
                        reason,
                        scores[memory.id],
                        related_memory_ids=[memory_id for memory_id in related_ids if memory_id != memory.id],
                        resulting_memory_id=consolidated.id,
                    )
                )

        for memory in memories:
            if memory.id in merged_ids:
                continue

            score = scores[memory.id]
            keep_reason = self._keep_reason(memory, score, active_policy)
            if keep_reason is not None:
                kept.append(self._decision(memory, CompactionDecisionType.KEPT, keep_reason, score))
                continue

            discard_reason = self._discard_reason(memory, score, active_policy)
            if discard_reason is not None:
                discarded.append(self._decision(memory, CompactionDecisionType.DISCARDED, discard_reason, score))
                continue

            kept.append(
                self._decision(
                    memory,
                    CompactionDecisionType.KEPT,
                    f"Kept because score {score.total:.2f} is above min_score_to_keep",
                    score,
                )
            )

        kept, discarded = self._apply_max_memories(
            kept=kept,
            discarded=discarded,
            created=created,
            scores=scores,
            policy=active_policy,
        )
        return self._build_diff(
            before_count=len(memories),
            kept=kept,
            merged=merged,
            discarded=discarded,
            created=created,
        )

    def _find_merge_groups(self, memories: list[Memory]) -> list[list[Memory]]:
        remaining = sorted(memories, key=lambda memory: (memory.content.lower(), memory.id))
        groups: list[list[Memory]] = []
        used_ids: set[str] = set()

        for memory in remaining:
            if memory.id in used_ids:
                continue

            group = [memory]
            for candidate in remaining:
                if candidate.id == memory.id or candidate.id in used_ids:
                    continue
                if self._is_duplicate_or_near_duplicate(memory, candidate):
                    group.append(candidate)

            if len(group) > 1:
                group.sort(key=lambda item: item.id)
                groups.append(group)
                used_ids.update(item.id for item in group)

        return groups

    def _is_duplicate_or_near_duplicate(self, first: Memory, second: Memory) -> bool:
        first_normalized = _normalize_content(first.content)
        second_normalized = _normalize_content(second.content)
        if not first_normalized or not second_normalized:
            return False
        if first_normalized == second_normalized:
            return True

        first_tokens = set(_tokens(first_normalized))
        second_tokens = set(_tokens(second_normalized))
        if not first_tokens or not second_tokens:
            return False
        overlap = len(first_tokens & second_tokens) / len(first_tokens | second_tokens)
        return overlap >= NEAR_DUPLICATE_THRESHOLD

    def _merge_group(self, group: list[Memory]) -> Memory:
        best = max(group, key=lambda memory: (memory.importance, len(memory.content), memory.updated_at))
        metadata = _merge_metadata(group)
        metadata["source_memory_ids"] = [memory.id for memory in group]
        memory_type = _merged_memory_type(group)
        return Memory(
            content=f"Merged memory: {best.content}",
            memory_type=memory_type,
            metadata=metadata,
            created_at=min(memory.created_at for memory in group),
            updated_at=utc_now(),
            importance=max(memory.importance for memory in group),
            access_count=sum(memory.access_count for memory in group),
            last_accessed_at=_max_optional_datetime(memory.last_accessed_at for memory in group),
            source="compaction",
            tags=sorted({tag for memory in group for tag in memory.tags}),
        )

    def _keep_reason(self, memory: Memory, score: MemoryScore, policy: CompactionPolicy) -> str | None:
        if memory.memory_type in policy.preserve_memory_types:
            return f"Kept because memory type '{memory.memory_type.value}' is preserved by policy"
        preserved_tags = set(policy.preserve_tags)
        matching_tags = sorted(preserved_tags & set(memory.tags))
        if matching_tags:
            return f"Kept because tag '{matching_tags[0]}' is preserved by policy"
        if memory.importance >= HIGH_IMPORTANCE_THRESHOLD:
            return f"Kept because importance {memory.importance:.2f} is above threshold"
        if score.total >= policy.min_score_to_keep:
            return f"Kept because score {score.total:.2f} is above min_score_to_keep"
        return None

    def _discard_reason(self, memory: Memory, score: MemoryScore, policy: CompactionPolicy) -> str | None:
        if policy.discard_stale and self._is_stale(memory, policy) and memory.importance < HIGH_IMPORTANCE_THRESHOLD:
            return "Discarded because memory is stale and low importance"
        if score.total < policy.min_score_to_keep:
            return f"Discarded because score {score.total:.2f} is below min_score_to_keep"
        return None

    def _is_stale(self, memory: Memory, policy: CompactionPolicy) -> bool:
        if policy.stale_after_days is None:
            return False
        updated_at = memory.updated_at
        if updated_at.tzinfo is None:
            updated_at = updated_at.replace(tzinfo=UTC)
        age_days = (datetime.now(UTC) - updated_at).days
        return age_days >= policy.stale_after_days

    def _apply_max_memories(
        self,
        *,
        kept: list[CompactionDecision],
        discarded: list[CompactionDecision],
        created: list[Memory],
        scores: dict[str, MemoryScore],
        policy: CompactionPolicy,
    ) -> tuple[list[CompactionDecision], list[CompactionDecision]]:
        if policy.max_memories is None:
            return kept, discarded

        after_count = len(kept) + len(created)
        if after_count <= policy.max_memories:
            return kept, discarded

        protected = {MemoryType.OPERATIONAL, MemoryType.PREFERENCE, *policy.preserve_memory_types}
        removable = [
            decision
            for decision in kept
            if decision.memory_id in scores and not self._decision_is_protected(decision, protected, policy)
        ]
        removable.sort(key=lambda decision: (decision.score_before, decision.memory_id))

        kept_by_id = {decision.memory_id: decision for decision in kept}
        for decision in removable:
            if len(kept_by_id) + len(created) <= policy.max_memories:
                break
            kept_by_id.pop(decision.memory_id, None)
            discarded.append(
                decision.model_copy(
                    update={
                        "decision": CompactionDecisionType.DISCARDED,
                        "reason": "Discarded because max_memories policy kept a smaller result set",
                    }
                )
            )

        return list(kept_by_id.values()), discarded

    def _decision_is_protected(
        self,
        decision: CompactionDecision,
        protected_types: set[MemoryType],
        policy: CompactionPolicy,
    ) -> bool:
        reason = decision.reason
        if "importance" in reason:
            return True
        if any(memory_type.value in reason for memory_type in protected_types):
            return True
        return any(tag in reason for tag in policy.preserve_tags)

    def _decision(
        self,
        memory: Memory,
        decision: CompactionDecisionType,
        reason: str,
        score: MemoryScore,
        *,
        related_memory_ids: list[str] | None = None,
        resulting_memory_id: str | None = None,
    ) -> CompactionDecision:
        return CompactionDecision(
            memory_id=memory.id,
            decision=decision,
            reason=reason,
            score_before=score.total,
            related_memory_ids=related_memory_ids or [],
            resulting_memory_id=resulting_memory_id,
        )

    def _build_diff(
        self,
        *,
        before_count: int,
        kept: list[CompactionDecision],
        merged: list[CompactionDecision],
        discarded: list[CompactionDecision],
        created: list[Memory],
    ) -> CompactionDiff:
        after_count = kept_after_count(kept=kept, created=created)
        reduction = (before_count - after_count) / before_count if before_count else 0.0
        stats = CompactionStats(
            before_count=before_count,
            after_count=after_count,
            kept_count=len(kept),
            merged_count=len(merged),
            discarded_count=len(discarded),
            created_count=len(created),
            estimated_reduction_ratio=round(max(reduction, 0.0), 6),
        )
        summary = (
            f"Compacted {before_count} memories into {after_count}: "
            f"kept {stats.kept_count}, merged {stats.merged_count}, "
            f"discarded {stats.discarded_count}, created {stats.created_count}."
        )
        return CompactionDiff(
            kept=kept, merged=merged, discarded=discarded, created=created, summary=summary, stats=stats
        )


def kept_after_count(*, kept: list[CompactionDecision], created: list[Memory]) -> int:
    """Return the number of memories that remain after compaction."""
    return len(kept) + len(created)


def _normalize_content(content: str) -> str:
    return " ".join(_tokens(content))


def _tokens(content: str) -> list[str]:
    return [token.lower() for token in TOKEN_PATTERN.findall(content)]


def _merge_metadata(group: list[Memory]) -> dict[str, Any]:
    merged: dict[str, Any] = {}
    for memory in group:
        for key, value in memory.metadata.items():
            if key not in merged:
                merged[key] = value
            elif merged[key] != value:
                merged[key] = _merge_metadata_value(merged[key], value)
    return merged


def _merge_metadata_value(existing: Any, new_value: Any) -> list[Any]:
    values = existing if isinstance(existing, list) else [existing]
    if new_value not in values:
        values.append(new_value)
    return values


def _merged_memory_type(group: list[Memory]) -> MemoryType:
    priority = [MemoryType.OPERATIONAL, MemoryType.PREFERENCE, MemoryType.SEMANTIC, MemoryType.EPISODIC]
    group_types = {memory.memory_type for memory in group}
    for memory_type in priority:
        if memory_type in group_types:
            return memory_type
    return group[0].memory_type


def _max_optional_datetime(values: Iterable[datetime | None]) -> datetime | None:
    datetimes = [value for value in values if isinstance(value, datetime)]
    return max(datetimes) if datetimes else None
