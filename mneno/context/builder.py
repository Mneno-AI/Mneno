"""Deterministic explainable context builder."""

from __future__ import annotations

from dataclasses import dataclass

from mneno.context.budget import estimate_tokens
from mneno.context.package import ContextItem, ContextPackage, ContextStats, ExcludedContextItem
from mneno.context.policies import ContextPolicy
from mneno.models import Memory, MemoryScore
from mneno.scoring.temporal import TemporalMemoryScorer


@dataclass(frozen=True)
class _Candidate:
    memory: Memory
    score: MemoryScore
    estimated_tokens: int


class ContextBuilder:
    """Build context packages from scored memories."""

    def __init__(self, *, scorer: TemporalMemoryScorer | None = None) -> None:
        self.scorer = scorer or TemporalMemoryScorer()

    def build(
        self,
        *,
        query: str,
        memories: list[Memory],
        policy: ContextPolicy,
        policy_name: str | None = None,
        preset: str | None = None,
        limit: int | None = None,
    ) -> ContextPackage:
        """Build an explainable context package from candidate memories."""
        all_candidates = [
            _Candidate(
                memory=memory,
                score=self.scorer.score(memory, query=query),
                estimated_tokens=estimate_tokens(memory.content),
            )
            for memory in memories
        ]
        sorted_candidates = self._sort_candidates(all_candidates, strategy=policy.strategy)
        candidates = sorted_candidates[:limit] if limit is not None else sorted_candidates
        excluded = [
            self._exclude(candidate, "Excluded because not selected by policy")
            for candidate in sorted_candidates[len(candidates) :]
        ]

        included: list[ContextItem] = []
        used_tokens = 0
        included_content: set[str] = set()
        candidate_count_after_filter = 0

        for candidate in candidates:
            normalized_content = _normalize_content(candidate.memory.content)
            is_preserved = self._is_preserved(candidate.memory, policy)
            if policy.dedupe and normalized_content in included_content:
                excluded.append(self._exclude(candidate, "Excluded because duplicate content already included"))
                continue

            if candidate.score.total < policy.min_score and not is_preserved:
                excluded.append(
                    self._exclude(
                        candidate,
                        f"Excluded because score {candidate.score.total:.2f} is below min_score {policy.min_score:.2f}",
                    )
                )
                continue

            candidate_count_after_filter += 1
            if policy.max_items is not None and len(included) >= policy.max_items:
                excluded.append(self._exclude(candidate, "Excluded because max_items reached"))
                continue

            if used_tokens + candidate.estimated_tokens > policy.available_tokens:
                excluded.append(self._exclude(candidate, "Excluded because budget exhausted"))
                continue

            used_tokens += candidate.estimated_tokens
            included_content.add(normalized_content)
            included.append(self._include(candidate, policy=policy, policy_name=policy_name, preset=preset))

        stats = ContextStats(
            max_tokens=policy.max_tokens,
            reserve_tokens=policy.reserve_tokens,
            available_tokens=policy.available_tokens,
            used_tokens=used_tokens,
            remaining_tokens=policy.available_tokens - used_tokens,
            included_count=len(included),
            excluded_count=len(excluded),
            total_candidates=len(all_candidates),
            policy_name=policy_name,
            preset=preset,
            min_score=policy.min_score,
            max_items=policy.max_items,
            strategy=policy.strategy,
            candidate_count_before_filter=len(all_candidates),
            candidate_count_after_filter=candidate_count_after_filter,
        )
        return ContextPackage(
            query=query,
            text=_format_context_text(included),
            policy_name=policy_name,
            policy=policy,
            preset=preset,
            included=included,
            excluded=excluded,
            stats=stats,
        )

    def _sort_candidates(self, candidates: list[_Candidate], *, strategy: str) -> list[_Candidate]:
        if strategy == "recency":
            return sorted(
                candidates, key=lambda item: (item.memory.updated_at, item.score.total, item.memory.id), reverse=True
            )
        if strategy == "importance":
            return sorted(
                candidates, key=lambda item: (item.memory.importance, item.score.total, item.memory.id), reverse=True
            )
        return sorted(
            candidates, key=lambda item: (item.score.total, item.memory.updated_at, item.memory.id), reverse=True
        )

    def _include(
        self,
        candidate: _Candidate,
        *,
        policy: ContextPolicy,
        policy_name: str | None,
        preset: str | None,
    ) -> ContextItem:
        preserved_tags = sorted(set(candidate.memory.tags) & set(policy.preserve_tags))
        if candidate.memory.memory_type in policy.preserve_memory_types:
            reason = f"Included because preserved memory type '{candidate.memory.memory_type.value}' fits within budget"
        elif preserved_tags:
            reason = f"Included because preserved tag '{preserved_tags[0]}' fits within budget"
        else:
            reason = "Included because highest score within budget"
        label = preset or policy_name
        if label is not None:
            reason = f"{reason} for context policy '{label}'"
        if policy.include_score_reasons and candidate.score.reasons:
            reason = f"{reason}; {candidate.score.reasons[0]}"
        return ContextItem(
            memory_id=candidate.memory.id,
            content=candidate.memory.content,
            score=candidate.score.total,
            estimated_tokens=candidate.estimated_tokens,
            reason=reason,
        )

    def _is_preserved(self, memory: Memory, policy: ContextPolicy) -> bool:
        return memory.memory_type in policy.preserve_memory_types or bool(set(memory.tags) & set(policy.preserve_tags))

    def _exclude(self, candidate: _Candidate, reason: str) -> ExcludedContextItem:
        return ExcludedContextItem(
            memory_id=candidate.memory.id,
            content=candidate.memory.content,
            score=candidate.score.total,
            estimated_tokens=candidate.estimated_tokens,
            reason=reason,
        )


def _format_context_text(included: list[ContextItem]) -> str:
    if not included:
        return "Relevant memories:"
    lines = ["Relevant memories:"]
    lines.extend(f"- {item.content}" for item in included)
    return "\n".join(lines)


def _normalize_content(content: str) -> str:
    return " ".join(content.lower().split())
