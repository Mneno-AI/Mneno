"""Public client for local Mneno memory operations."""

from __future__ import annotations

import builtins
from collections.abc import Iterable
from pathlib import Path
from typing import Any, Literal

from mneno.compaction.engine import CompactionEngine
from mneno.compaction.policies import CompactionPolicy
from mneno.context.budget import ContextBudget
from mneno.context.builder import ContextBuilder
from mneno.context.package import ContextPackage
from mneno.context.policies import ContextPolicy
from mneno.context.presets import ContextPreset, get_context_policy
from mneno.io.backup import backup_memories, restore_memories
from mneno.io.export import export_memories
from mneno.io.importers import ImportMode, ImportResult, import_memories_from_json
from mneno.models import (
    AddMemoryRequest,
    CompactionDiff,
    Memory,
    MemoryPolicy,
    MemoryScore,
    MemorySearchResult,
    MemoryType,
    SearchMemoryRequest,
    utc_now,
)
from mneno.providers.embedding import EmbeddingProvider
from mneno.providers.exceptions import ProviderNotFoundError
from mneno.providers.reranker import RerankerProvider
from mneno.retrieval.rerank import RerankingEngine
from mneno.scoring.temporal import TemporalMemoryScorer
from mneno.storage.base import MemoryStore
from mneno.storage.memory import InMemoryMemoryStore


class MemoryClient:
    """Small synchronous SDK client backed by an in-memory local store."""

    def __init__(
        self,
        *,
        policy: MemoryPolicy | None = None,
        storage: MemoryStore | None = None,
        store: MemoryStore | None = None,
        embedding_provider: EmbeddingProvider | None = None,
        reranker_provider: RerankerProvider | None = None,
        scorer: TemporalMemoryScorer | None = None,
        compactor: CompactionEngine | None = None,
        context_builder: ContextBuilder | None = None,
    ) -> None:
        if storage is not None and store is not None:
            raise ValueError("Use either storage or store, not both")
        self.policy = policy or MemoryPolicy()
        self.store = storage or store or InMemoryMemoryStore()
        self.embedding_provider = embedding_provider
        self.reranker_provider = reranker_provider
        self.scorer = scorer or TemporalMemoryScorer(policy=self.policy, embedding_provider=embedding_provider)
        self.compactor = compactor or CompactionEngine(scorer=self.scorer)
        self.reranking_engine = RerankingEngine(reranker_provider=reranker_provider)
        self.context_builder = context_builder or ContextBuilder(
            scorer=self.scorer,
            reranker_provider=reranker_provider,
        )

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

    def search(
        self,
        query: str,
        *,
        limit: int = 10,
        use_semantic: bool | None = None,
        use_reranker: bool | None = None,
    ) -> builtins.list[MemorySearchResult]:
        """Search local memories and return ranked, explainable results."""
        request = SearchMemoryRequest(query=query, limit=limit)
        should_use_semantic = self._should_use_semantic(use_semantic)
        should_use_reranker = self._should_use_reranker(use_reranker)
        scored: builtins.list[tuple[Memory, MemoryScore]] = []
        for memory in self.store.list():
            score = self.scorer.score(memory, query=request.query, use_semantic=should_use_semantic)
            scored.append((memory, score))

        scored.sort(key=lambda item: (item[1].total, item[0].updated_at, item[0].id), reverse=True)
        candidates = [
            MemorySearchResult(memory=memory, score=score, rank=index)
            for index, (memory, score) in enumerate(scored, start=1)
        ]
        ranked = self.reranking_engine.rerank(request.query, candidates) if should_use_reranker else candidates
        results = ranked[: request.limit]
        self._record_access(result.memory.id for result in results)
        return [
            result.model_copy(update={"memory": self.store.get(result.memory.id) or result.memory})
            for result in results
        ]

    def _should_use_semantic(self, use_semantic: bool | None) -> bool:
        if use_semantic is True and self.embedding_provider is None:
            raise ProviderNotFoundError("Semantic search requires an embedding provider")
        if use_semantic is False:
            return False
        return self.embedding_provider is not None

    def _should_use_reranker(self, use_reranker: bool | None) -> bool:
        if use_reranker is True and self.reranker_provider is None:
            raise ProviderNotFoundError("Reranking requires a reranker provider")
        if use_reranker is False:
            return False
        return self.reranker_provider is not None

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

    def export_json(self, path: str | Path | None = None) -> dict[str, Any]:
        """Export all memories to a JSON payload and optionally write it to disk."""
        return export_memories(self.store.list(), path)

    def import_json(self, path: str | Path, *, mode: ImportMode = "append") -> ImportResult:
        """Import memories from a Mneno JSON export file."""
        return import_memories_from_json(self.store, path, mode=mode)

    def backup(self, path: str | Path | None = None) -> Path:
        """Create a timestamped JSON backup of current memories."""
        return backup_memories(self.store.list(), path)

    def restore(self, path: str | Path, *, mode: Literal["replace", "append"] = "replace") -> ImportResult:
        """Restore memories from a backup JSON file."""
        return restore_memories(self.store, path, mode=mode)

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
            memory = self.store.get(memory_id)
            if memory is None:
                continue
            updated = memory.model_copy(update={"access_count": memory.access_count + 1, "last_accessed_at": utc_now()})
            self.store.update(updated)
