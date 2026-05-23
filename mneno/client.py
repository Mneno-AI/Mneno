"""Public client for local Mneno memory operations."""

from __future__ import annotations

import builtins
from collections.abc import Iterable

from mneno.models import Memory, MemoryPolicy, MemoryScore, MemoryType
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
    ) -> None:
        self.policy = policy or MemoryPolicy()
        self.store = store or InMemoryMemoryStore()
        self.scorer = scorer or TemporalMemoryScorer(policy=self.policy)

    def add(
        self,
        content: str,
        *,
        memory_type: MemoryType = MemoryType.FACT,
        importance: float | None = None,
        metadata: dict[str, object] | None = None,
    ) -> Memory:
        """Add a memory to the local store."""
        memory = Memory(
            content=content,
            memory_type=memory_type,
            importance=self.policy.default_importance if importance is None else importance,
            metadata=metadata or {},
        )
        return self.store.add(memory)

    def get(self, memory_id: str) -> Memory | None:
        """Return a memory by ID, if present."""
        return self.store.get(memory_id)

    def list(self) -> builtins.list[Memory]:
        """Return all stored memories in insertion order."""
        return self.store.list()

    def search(self, query: str, *, limit: int = 5) -> builtins.list[Memory]:
        """Search local memories with lightweight keyword-overlap scoring."""
        ranked = self.search_with_scores(query, limit=limit)
        return [memory for memory, _score in ranked]

    def search_with_scores(self, query: str, *, limit: int = 5) -> builtins.list[tuple[Memory, MemoryScore]]:
        """Search local memories and include explainable score components."""
        scored: builtins.list[tuple[Memory, MemoryScore]] = []
        for memory in self.store.list():
            score = self.scorer.score(memory, query=query)
            if score.total > 0:
                scored.append((memory, score))

        scored.sort(key=lambda item: item[1].total, reverse=True)
        results = scored[:limit]
        self._record_access(memory.id for memory, _score in results)
        return [(self.store.get(memory.id) or memory, score) for memory, score in results]

    def _record_access(self, memory_ids: Iterable[str]) -> None:
        for memory_id in memory_ids:
            self.store.record_access(memory_id)
