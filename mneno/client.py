"""Public client for local Mneno memory operations."""

from __future__ import annotations

import builtins
from collections.abc import Iterable

from mneno.compaction.engine import CompactionEngine
from mneno.compaction.policies import CompactionPolicy
from mneno.context.budget import ContextBudget
from mneno.context.builder import ContextBuilder
from mneno.context.package import ContextPackage
from mneno.context.policies import ContextPolicy
from mneno.context.presets import ContextPreset, get_context_policy
from mneno.models import (
    AddMemoryRequest,
    CompactionDiff,
    Memory,
    MemoryPolicy,
    MemoryScore,
    MemorySearchResult,
    MemoryType,
    SearchMemoryRequest,
)
from mneno.scoring.temporal import TemporalMemoryScorer
from mneno.storage.memory import InMemoryMemoryStore


class MemoryClient:
    """Small synchronous SDK client backed by an in-memory local store."""

    def __init__(
        self,
        *,
        policy: MemoryPolicy | None = None,
        store: InMemoryMemoryStore | None = None,
        scorer: TemporalMemoryScorer | None = None,
        compactor: CompactionEngine | None = None,
        context_builder: ContextBuilder | None = None,
    ) -> None:
        self.policy = policy or MemoryPolicy()
        self.store = store or InMemoryMemoryStore()
        self.scorer = scorer or TemporalMemoryScorer(policy=self.policy)
        self.compactor = compactor or CompactionEngine(scorer=self.scorer)
        self.context_builder = context_builder or ContextBuilder(scorer=self.scorer)

    def add(
        self,
        content: str,
        *,
        memory_type: MemoryType | str = MemoryType.SEMANTIC,
        importance: float | None = None,
        metadata: dict[str, object] | None = None,
        source: str | None = None,
        tags: list[str] | None = None,
    ) -> Memory:
        """Add a memory to the local store."""
        request = AddMemoryRequest(
            content=content,
            memory_type=memory_type,
            importance=self.policy.default_importance if importance is None else importance,
            metadata=metadata or {},
            source=source,
            tags=tags or [],
        )
        memory = Memory(
            content=request.content,
            memory_type=request.memory_type,
            importance=request.importance,
            metadata=request.metadata,
            source=request.source,
            tags=request.tags,
        )
        return self.store.add(memory)

    def get(self, memory_id: str) -> Memory | None:
        """Return a memory by ID, if present."""
        return self.store.get(memory_id)

    def list(self) -> builtins.list[Memory]:
        """Return all stored memories in insertion order."""
        return self.store.list()

    def search(self, query: str, *, limit: int = 5) -> builtins.list[MemorySearchResult]:
        """Search local memories and return ranked, explainable results."""
        request = SearchMemoryRequest(query=query, limit=limit)
        scored: builtins.list[tuple[Memory, MemoryScore]] = []
        for memory in self.store.list():
            score = self.scorer.score(memory, query=request.query)
            scored.append((memory, score))

        scored.sort(key=lambda item: (item[1].total, item[0].updated_at, item[0].id), reverse=True)
        results = scored[: request.limit]
        self._record_access(memory.id for memory, _score in results)
        return [
            MemorySearchResult(memory=self.store.get(memory.id) or memory, score=score, rank=index)
            for index, (memory, score) in enumerate(results, start=1)
        ]

    def delete(self, memory_id: str) -> bool:
        """Delete a memory by ID."""
        return self.store.delete(memory_id)

    def clear(self) -> None:
        """Delete all memories."""
        self.store.clear()

    def preview_compaction(self, policy: CompactionPolicy | None = None) -> CompactionDiff:
        """Analyze compaction without mutating storage."""
        return self.compactor.compact(self.store.list(), policy=policy)

    def compact(self, policy: CompactionPolicy | None = None) -> CompactionDiff:
        """Compact current storage and return an explainable diff."""
        diff = self.preview_compaction(policy=policy)
        for decision in [*diff.discarded, *diff.merged]:
            self.store.delete(decision.memory_id)
        for memory in diff.created:
            self.store.add(memory)
        return diff

    def build_context(
        self,
        query: str,
        *,
        budget: int | ContextBudget | None = None,
        preset: ContextPreset | str | None = "balanced",
        policy: ContextPolicy | None = None,
        limit: int | None = None,
    ) -> ContextPackage:
        """Build an explainable context package for a query."""
        context_policy, policy_name, preset_name = self._resolve_context_policy(
            budget=budget,
            preset=preset,
            policy=policy,
        )
        package = self.context_builder.build(
            query=query,
            memories=self.store.list(),
            policy=context_policy,
            policy_name=policy_name,
            preset=preset_name,
            limit=limit,
        )
        self._record_access(item.memory_id for item in package.included)
        return package

    def _resolve_context_policy(
        self,
        *,
        budget: int | ContextBudget | None,
        preset: ContextPreset | str | None,
        policy: ContextPolicy | None,
    ) -> tuple[ContextPolicy, str | None, str | None]:
        if policy is not None:
            return policy, "custom", None
        if budget is not None:
            return ContextPolicy.from_budget(budget), "budget", None
        if preset is not None:
            context_policy = get_context_policy(preset)
            preset_name = ContextPreset(preset).value
            return context_policy, preset_name, preset_name
        context_policy = get_context_policy(ContextPreset.BALANCED)
        return context_policy, ContextPreset.BALANCED.value, ContextPreset.BALANCED.value

    def _record_access(self, memory_ids: Iterable[str]) -> None:
        for memory_id in memory_ids:
            self.store.record_access(memory_id)
