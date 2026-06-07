"""Public client for local Mneno memory operations."""

from __future__ import annotations

import builtins
from collections.abc import Iterable
from pathlib import Path
from time import perf_counter
from typing import Any, Literal

from mneno.compaction.engine import CompactionEngine
from mneno.compaction.policies import CompactionPolicy
from mneno.conflicts import (
    AddMemoryResult,
    ConflictAction,
    ConflictDetector,
    ConflictPolicy,
    ConflictReport,
    ConflictResolver,
    ConflictSeverity,
    ConflictType,
)
from mneno.context.budget import ContextBudget
from mneno.context.builder import ContextBuilder
from mneno.context.package import ContextPackage
from mneno.context.policies import ContextPolicy
from mneno.context.presets import ContextPreset, get_context_policy
from mneno.evaluation import (
    CompactionEvaluationResult,
    ContextEvaluationResult,
    EvaluationReport,
    MetricResult,
    SearchEvaluationResult,
    build_benchmark_payload,
    context_utilization_ratio,
    mean_reciprocal_rank,
    metric,
    precision_at_k,
    recall_at_k,
    reduction_ratio,
    token_efficiency_ratio,
)
from mneno.extraction import DeterministicMemoryExtractor, ExtractionResult, LLMMemoryExtractor
from mneno.hierarchy.layers import MemoryLayer
from mneno.hierarchy.manager import HierarchyEvaluationResult, HierarchyManager
from mneno.hierarchy.policies import LayerPolicy
from mneno.hierarchy.transitions import is_promotional, is_valid_manual_transition
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
    MemoryStatus,
    MemoryType,
    SearchMemoryRequest,
    utc_now,
)
from mneno.observability import (
    TRACE_EXPORT_FORMAT,
    TRACE_EXPORT_VERSION,
    CompletedTraceStatus,
    OperationTrace,
    TraceRecorder,
)
from mneno.providers.embedding import EmbeddingProvider
from mneno.providers.exceptions import ProviderNotFoundError
from mneno.providers.llm import LLMProvider
from mneno.providers.reranker import RerankerProvider
from mneno.retrieval.rerank import RerankingEngine
from mneno.scoring.temporal import TemporalMemoryScorer
from mneno.sessions import ContinuityManager, ContinuityResult, Session, SessionManager, Timeline
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
        llm_provider: LLMProvider | None = None,
        conflict_policy: ConflictPolicy | None = None,
        auto_detect_conflicts: bool = True,
        layer_policy: LayerPolicy | None = None,
        hierarchy_manager: HierarchyManager | None = None,
        session_manager: SessionManager | None = None,
        continuity_manager: ContinuityManager | None = None,
        active_session_id: str | None = None,
        trace_enabled: bool = False,
        trace_recorder: TraceRecorder | None = None,
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
        self.llm_provider = llm_provider
        self.conflict_policy = conflict_policy or ConflictPolicy()
        self.auto_detect_conflicts = auto_detect_conflicts
        self.conflict_detector = ConflictDetector()
        self.conflict_resolver = ConflictResolver()
        self.layer_policy = layer_policy or LayerPolicy()
        self.hierarchy_manager = hierarchy_manager or HierarchyManager()
        self.session_manager = session_manager or SessionManager()
        self.continuity_manager = continuity_manager or ContinuityManager()
        self.active_session_id = active_session_id
        self.trace_enabled = trace_enabled or trace_recorder is not None
        self.trace_recorder = trace_recorder or (TraceRecorder() if self.trace_enabled else None)
        self.last_trace_id: str | None = None
        self.scorer = scorer or TemporalMemoryScorer(policy=self.policy, embedding_provider=embedding_provider)
        self.compactor = compactor or CompactionEngine(scorer=self.scorer, llm_provider=llm_provider)
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
        tags: builtins.list[str] | None = None,
        layer: MemoryLayer | str | None = None,
        session_id: str | None = None,
    ) -> Memory:
        """Add a memory to the local store."""
        return self.add_with_report(
            content,
            memory_type=memory_type,
            importance=importance,
            metadata=metadata,
            source=source,
            tags=tags,
            layer=layer,
            session_id=session_id,
        ).memory

    def add_with_report(
        self,
        content: str,
        *,
        memory_type: MemoryType | str = MemoryType.SEMANTIC,
        importance: float | None = None,
        metadata: dict[str, object] | None = None,
        source: str | None = None,
        tags: builtins.list[str] | None = None,
        layer: MemoryLayer | str | None = None,
        session_id: str | None = None,
    ) -> AddMemoryResult:
        """Add a memory and return conflict reports and resolution actions."""
        trace = self._start_trace("add", metadata={"memory_type": str(memory_type), "session_id": session_id})
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
            layer=MemoryLayer(layer) if layer is not None else None,
            session_id=session_id,
        )
        if session_id is not None:
            session = self._require_session(session_id)
            _, memory = self.session_manager.add_memory_to_session(session, memory)
            self._trace_event(
                trace,
                event_type="session_attachment_prepared",
                message=f"Prepared memory for session {session_id}",
                session_id=session_id,
                data={"sequence_index": memory.sequence_index},
            )
        reports: builtins.list[ConflictReport] = []
        actions: builtins.list[str] = []
        if self.auto_detect_conflicts:
            self._trace_event(trace, event_type="conflict_detection_started", message="Conflict detection started")
            existing = self._active_existing_memories()
            for existing_memory in existing:
                self._trace_event(
                    trace,
                    event_type="memory_compared",
                    message=f"Compared new memory with memory {existing_memory.id}",
                    memory_id=existing_memory.id,
                    data={"new_memory_id": memory.id},
                )
            reports = self.conflict_detector.detect(memory, existing, policy=self.conflict_policy)
            for report in reports:
                self._trace_event(
                    trace,
                    event_type="conflict_report_generated",
                    message=report.reason,
                    memory_id=report.existing_memory_id,
                    data={"conflict_type": report.conflict_type.value, "new_memory_id": report.new_memory_id},
                )
            resolution = self.conflict_resolver.resolve(memory, existing, reports, policy=self.conflict_policy)
            memory = resolution.new_memory
            actions = resolution.actions
            for action in actions:
                self._trace_event(trace, event_type="resolution_action_applied", message=action)
                self._trace_event(trace, event_type="conflict_resolution_action", message=action)
            for updated in resolution.updated_existing:
                self.store.update(updated)
                if updated.audit:
                    self._trace_event(
                        trace,
                        event_type="audit_event_added",
                        message=updated.audit[-1].reason,
                        memory_id=updated.id,
                        data={"audit_event_type": updated.audit[-1].event_type},
                    )

        stored = self.store.add(memory)
        if reports and stored.audit:
            self._trace_event(
                trace,
                event_type="audit_event_added",
                message=stored.audit[-1].reason,
                memory_id=stored.id,
                data={"audit_event_type": stored.audit[-1].event_type},
            )
        self._trace_event(
            trace,
            event_type="memory_added",
            message="Memory added to storage",
            memory_id=stored.id,
            session_id=stored.session_id,
            data={"layer": stored.layer.value, "status": stored.status.value},
        )
        if session_id is not None:
            stored = self._attach_stored_memory_to_session(stored, session_id, trace=trace)
        trace_id = self._end_trace(trace, summary=f"Added memory {stored.id}")
        return AddMemoryResult(memory=stored, conflict_reports=reports, resolution_actions=actions, trace_id=trace_id)

    def get(self, memory_id: str) -> Memory | None:
        """Return a memory by ID, if present."""
        return self.store.get(memory_id)

    def list(self) -> builtins.list[Memory]:
        """Return all stored memories in insertion order."""
        return self.store.list()

    def list_by_layer(self, layer: MemoryLayer | str) -> builtins.list[Memory]:
        """Return memories in a specific hierarchy layer."""
        target_layer = MemoryLayer(layer)
        return [memory for memory in self.store.list() if memory.layer is target_layer]

    def create_session(
        self,
        *,
        title: str,
        metadata: dict[str, object] | None = None,
        tags: builtins.list[str] | None = None,
        summary: str | None = None,
        make_active: bool = True,
    ) -> Session:
        """Create and persist a memory session."""
        trace = self._start_trace("session_create", metadata={"title": title})
        session = self.session_manager.create_session(title=title, metadata=metadata, tags=tags, summary=summary)
        stored = self.store.add_session(session)
        if make_active:
            self.active_session_id = stored.id
        self._trace_event(
            trace,
            event_type="session_created",
            message=f"Created session {stored.id}",
            session_id=stored.id,
            data={"title": stored.title, "make_active": make_active},
        )
        self._end_trace(trace, summary=f"Created session {stored.id}")
        return stored

    def get_session(self, session_id: str) -> Session | None:
        """Return a session by ID."""
        return self.store.get_session(session_id)

    def list_sessions(self) -> builtins.list[Session]:
        """Return all sessions."""
        return self.store.list_sessions()

    def close_session(self, session_id: str, *, summary: str | None = None) -> Session:
        """Close a session and persist its deterministic summary."""
        trace = self._start_trace("session_update", metadata={"action": "close", "session_id": session_id})
        session = self._require_session(session_id)
        memories = self.list_session_memories(session_id)
        resolved_summary = summary if summary is not None else self.session_manager.summarize_session(session, memories)
        updated = self.session_manager.close_session(session, summary=resolved_summary)
        if self.active_session_id == session_id:
            self.active_session_id = None
        stored = self.store.update_session(updated)
        self._trace_event(
            trace,
            event_type="session_closed",
            message=f"Closed session {session_id}",
            session_id=session_id,
            data={"memory_count": len(memories)},
        )
        self._end_trace(trace, summary=f"Closed session {session_id}")
        return stored

    def archive_session(self, session_id: str) -> Session:
        """Archive a session without deleting its memories."""
        trace = self._start_trace("session_update", metadata={"action": "archive", "session_id": session_id})
        session = self._require_session(session_id)
        updated = self.session_manager.archive_session(session)
        if self.active_session_id == session_id:
            self.active_session_id = None
        stored = self.store.update_session(updated)
        self._trace_event(
            trace,
            event_type="session_archived",
            message=f"Archived session {session_id}",
            session_id=session_id,
        )
        self._end_trace(trace, summary=f"Archived session {session_id}")
        return stored

    def add_memory_to_session(self, memory_id: str, session_id: str) -> Memory:
        """Attach an existing memory to a primary session."""
        trace = self._start_trace(
            "session_update", metadata={"action": "attach_memory", "memory_id": memory_id, "session_id": session_id}
        )
        memory = self._require_memory(memory_id)
        self._require_session(session_id)
        attached = self._attach_stored_memory_to_session(memory, session_id, trace=trace)
        self._end_trace(trace, summary=f"Attached memory {memory_id} to session {session_id}")
        return attached

    def list_session_memories(self, session_id: str) -> builtins.list[Memory]:
        """Return memories attached to a session in sequence order."""
        session = self._require_session(session_id)
        return self.session_manager.list_session_memories(session, self.store.list())

    def build_timeline(self, *, session_ids: builtins.list[str] | None = None) -> Timeline:
        """Build a deterministic memory timeline."""
        trace = self._start_trace("timeline_build", metadata={"session_ids": session_ids or []})
        timeline = self.session_manager.build_timeline(self.store.list(), session_ids=session_ids)
        for event in timeline.events:
            self._trace_event(
                trace,
                event_type="timeline_event_ordered",
                message=event.reason,
                memory_id=event.memory_id,
                session_id=event.session_id,
                data={"sequence_index": event.sequence_index, "timestamp": event.timestamp.isoformat()},
            )
        self._trace_event(
            trace,
            event_type="timeline_built",
            message=f"Built timeline with {len(timeline.events)} events",
            data={"event_count": len(timeline.events), "session_ids": timeline.session_ids},
        )
        trace_id = self._end_trace(trace, summary=timeline.summary)
        return timeline.model_copy(update={"trace_id": trace_id})

    def find_related_sessions(self, query: str, *, limit: int = 5) -> ContinuityResult:
        """Find related sessions and continuity memories for a query."""
        trace = self._start_trace("session_context", metadata={"query": query, "limit": limit, "mode": "continuity"})
        result = self.continuity_manager.find_related(
            query,
            sessions=self.store.list_sessions(),
            memories=self.store.list(),
            limit=limit,
        )
        for session in result.related_sessions:
            self._trace_event(
                trace,
                event_type="related_session_found",
                message=f"Related session found: {session.title}",
                session_id=session.id,
            )
        self._end_trace(trace, summary=result.continuity_summary)
        return result

    def get_session_context(
        self,
        session_id: str,
        query: str,
        *,
        budget: int | ContextBudget | None = None,
        preset: ContextPreset | str | None = "balanced",
        policy: ContextPolicy | None = None,
        limit: int | None = None,
    ) -> ContextPackage:
        """Build context for a session with continuity explanations."""
        trace = self._start_trace("session_context", metadata={"session_id": session_id, "query": query})
        self._require_session(session_id)
        package = self.build_context(
            query,
            budget=budget,
            preset=preset,
            policy=policy,
            limit=limit,
            current_session_id=session_id,
        )
        self._trace_event(
            trace,
            event_type="session_context_built",
            message=f"Built session context for session {session_id}",
            session_id=session_id,
            data={"included_count": len(package.included), "context_trace_id": package.trace_id},
        )
        trace_id = self._end_trace(trace, summary=f"Built session context for {session_id}")
        return package.model_copy(update={"trace_id": trace_id})

    def evaluate_hierarchy(self, policy: LayerPolicy | None = None) -> HierarchyEvaluationResult:
        """Evaluate hierarchy transitions and persist updated memories safely."""
        trace = self._start_trace("hierarchy_evaluation", metadata={"memory_count": len(self.store.list())})
        self._trace_event(trace, event_type="hierarchy_evaluation_started", message="Hierarchy evaluation started")
        result = self.hierarchy_manager.evaluate(self.store.list(), policy=policy or self.layer_policy)
        categorized = [
            ("promoted", result.promoted),
            ("demoted", result.demoted),
            ("archived", result.archived),
            ("unchanged", result.unchanged),
        ]
        for transition, memories in categorized:
            for memory in memories:
                self._trace_event(
                    trace,
                    event_type="retention_score_calculated",
                    message=f"Retention score calculated for memory {memory.id}",
                    memory_id=memory.id,
                    data={"retention_score": memory.retention_score, "layer": memory.layer.value},
                )
                self._trace_event(
                    trace,
                    event_type=transition,
                    message=f"Memory {memory.id} was {transition}",
                    memory_id=memory.id,
                    data={"layer": memory.layer.value},
                )
                if transition != "unchanged" and memory.audit:
                    self._trace_event(
                        trace,
                        event_type="audit_event_added",
                        message=memory.audit[-1].reason,
                        memory_id=memory.id,
                        data={"audit_event_type": memory.audit[-1].event_type},
                    )
                self.store.update(memory)
        for action in result.actions:
            self._trace_event(trace, event_type="hierarchy_transition", message=action)
        trace_id = self._end_trace(trace, summary=f"Hierarchy evaluated {len(self.store.list())} memories")
        return result.model_copy(update={"trace_id": trace_id})

    def promote_memory(self, memory_id: str, target_layer: MemoryLayer | str) -> Memory:
        """Manually promote a memory to a target layer with audit history."""
        trace = self._start_trace("hierarchy_evaluation", metadata={"manual": "promote", "memory_id": memory_id})
        memory = self._require_memory(memory_id)
        resolved_target = MemoryLayer(target_layer)
        if not is_valid_manual_transition(memory.layer, resolved_target):
            raise ValueError(f"Invalid hierarchy transition from {memory.layer.value} to {resolved_target.value}")
        if not is_promotional(memory.layer, resolved_target):
            raise ValueError(f"Target layer {resolved_target.value} is not a promotion from {memory.layer.value}")
        updated = self.hierarchy_manager.transition_memory(
            memory,
            resolved_target,
            reason=f"Manually promoted from {memory.layer.value} to {resolved_target.value}",
        )
        stored = self.store.update(updated)
        self._trace_event(
            trace,
            event_type="hierarchy_transition",
            message=f"Promoted memory {memory_id} to {resolved_target.value}",
            memory_id=memory_id,
            data={"from_layer": memory.layer.value, "to_layer": resolved_target.value},
        )
        self._end_trace(trace, summary=f"Promoted memory {memory_id}")
        return stored

    def demote_memory(self, memory_id: str, target_layer: MemoryLayer | str) -> Memory:
        """Manually demote a memory to a target layer with audit history."""
        trace = self._start_trace("hierarchy_evaluation", metadata={"manual": "demote", "memory_id": memory_id})
        memory = self._require_memory(memory_id)
        resolved_target = MemoryLayer(target_layer)
        if not is_valid_manual_transition(memory.layer, resolved_target):
            raise ValueError(f"Invalid hierarchy transition from {memory.layer.value} to {resolved_target.value}")
        if is_promotional(memory.layer, resolved_target):
            raise ValueError(f"Target layer {resolved_target.value} is not a demotion from {memory.layer.value}")
        updated = self.hierarchy_manager.transition_memory(
            memory,
            resolved_target,
            reason=f"Manually demoted from {memory.layer.value} to {resolved_target.value}",
        )
        stored = self.store.update(updated)
        self._trace_event(
            trace,
            event_type="hierarchy_transition",
            message=f"Demoted memory {memory_id} to {resolved_target.value}",
            memory_id=memory_id,
            data={"from_layer": memory.layer.value, "to_layer": resolved_target.value},
        )
        self._end_trace(trace, summary=f"Demoted memory {memory_id}")
        return stored

    def detect_conflicts(self, memory: Memory | str) -> builtins.list[ConflictReport]:
        """Detect conflicts for a memory object or temporary content string without mutating storage."""
        trace = self._start_trace("conflict_detection", metadata={"temporary": isinstance(memory, str)})
        self._trace_event(trace, event_type="conflict_detection_started", message="Conflict detection started")
        candidate = Memory(content=memory) if isinstance(memory, str) else memory
        existing = [stored for stored in self._active_existing_memories() if stored.id != candidate.id]
        for existing_memory in existing:
            self._trace_event(
                trace,
                event_type="memory_compared",
                message=f"Compared candidate with memory {existing_memory.id}",
                memory_id=existing_memory.id,
                data={"candidate_memory_id": candidate.id},
            )
        reports = self.conflict_detector.detect(candidate, existing, policy=self.conflict_policy)
        for report in reports:
            self._trace_event(
                trace,
                event_type="conflict_report_generated",
                message=report.reason,
                memory_id=report.existing_memory_id,
                data={"conflict_type": report.conflict_type.value, "new_memory_id": report.new_memory_id},
            )
        self._end_trace(trace, summary=f"Detected {len(reports)} conflicts")
        return reports

    def list_conflicts(self) -> builtins.list[ConflictReport]:
        """Return conflict reports reconstructed from stored memory audit events."""
        reports: builtins.list[ConflictReport] = []
        seen: set[str] = set()
        for memory in self.store.list():
            for event in memory.audit:
                conflict_id = event.metadata.get("conflict_id")
                conflict_type = event.metadata.get("conflict_type")
                severity = event.metadata.get("severity")
                suggested_action = event.metadata.get("suggested_action")
                if not isinstance(conflict_id, str):
                    continue
                if not isinstance(conflict_type, str):
                    continue
                if not isinstance(severity, str):
                    continue
                if not isinstance(suggested_action, str):
                    continue
                if conflict_id in seen:
                    continue
                related_id = event.related_memory_ids[0] if event.related_memory_ids else memory.id
                reports.append(
                    ConflictReport(
                        conflict_id=conflict_id,
                        conflict_type=ConflictType(conflict_type),
                        severity=ConflictSeverity(severity),
                        new_memory_id=related_id if event.event_type in {"superseded", "archived"} else memory.id,
                        existing_memory_id=memory.id if event.event_type in {"superseded", "archived"} else related_id,
                        reason=event.reason,
                        evidence=_metadata_list(event.metadata.get("evidence")),
                        suggested_action=ConflictAction(suggested_action),
                        created_at=event.timestamp,
                    )
                )
                seen.add(conflict_id)
        return reports

    def search(
        self,
        query: str,
        *,
        limit: int = 10,
        use_semantic: bool | None = None,
        use_reranker: bool | None = None,
        include_inactive: bool = False,
        include_archived: bool = False,
        current_session_id: str | None = None,
    ) -> builtins.list[MemorySearchResult]:
        """Search local memories and return ranked, explainable results."""
        trace = self._start_trace("search", metadata={"query": query, "limit": limit})
        self._trace_event(
            trace,
            event_type="query_received",
            message="Search query received",
            data={"query": query, "limit": limit},
        )
        request = SearchMemoryRequest(query=query, limit=limit)
        should_use_semantic = self._should_use_semantic(use_semantic)
        should_use_reranker = self._should_use_reranker(use_reranker)
        all_memory_count = len(self.store.list())
        self._trace_event(
            trace,
            event_type="memories_loaded",
            message=f"Loaded {all_memory_count} memories",
            data={"memory_count": all_memory_count},
        )
        searchable_memories = self._searchable_memories(include_inactive=include_inactive or include_archived)
        self._trace_event(
            trace,
            event_type="inactive_filtering_applied",
            message="Inactive memory filtering skipped"
            if include_inactive or include_archived
            else "Archived and superseded memories excluded",
            data={
                "applied": not (include_inactive or include_archived),
                "excluded_count": all_memory_count - len(searchable_memories),
            },
        )
        self._trace_event(
            trace,
            event_type="candidate_filtering",
            message=f"Filtered {len(searchable_memories)} searchable memories from {all_memory_count} stored memories",
            data={"candidate_count": len(searchable_memories), "stored_count": all_memory_count},
        )
        self._trace_event(
            trace,
            event_type="semantic_stage",
            message="Semantic stage used" if should_use_semantic else "Semantic stage skipped",
            data={"used": should_use_semantic},
        )
        scored: builtins.list[tuple[Memory, MemoryScore]] = []
        active_session_id = current_session_id or self.active_session_id
        session_matches = (
            sum(memory.session_id == active_session_id for memory in searchable_memories)
            if active_session_id is not None
            else 0
        )
        self._trace_event(
            trace,
            event_type="session_boost_stage",
            message="Session boost used" if session_matches else "Session boost skipped",
            session_id=active_session_id,
            data={"used": session_matches > 0, "boosted_candidate_count": session_matches},
        )
        for memory in searchable_memories:
            score = self.scorer.score(memory, query=request.query, use_semantic=should_use_semantic)
            if active_session_id is not None and memory.session_id == active_session_id:
                score = self._boost_session_score(score, "Memory belongs to active session")
                self._trace_event(
                    trace,
                    event_type="session_boost_applied",
                    message="Applied active-session score boost",
                    memory_id=memory.id,
                    session_id=active_session_id,
                    data={"boost": 0.1},
                )
            if memory.status is MemoryStatus.CONFLICTED:
                score = score.model_copy(update={"reasons": [*score.reasons, "Memory is marked conflicted"]})
            self._trace_event(
                trace,
                event_type="score_calculated",
                message=f"Score {score.total:.3f} calculated for memory {memory.id}",
                memory_id=memory.id,
                session_id=memory.session_id,
                data={
                    "total": score.total,
                    "relevance": score.relevance,
                    "importance": score.importance,
                    "recency": score.recency,
                    "frequency": score.frequency,
                    "freshness": score.freshness,
                    "semantic_relevance": score.semantic_relevance,
                    "reasons": score.reasons,
                },
            )
            scored.append((memory, score))

        scored.sort(
            key=lambda item: (
                item[1].total,
                item[0].session_id == active_session_id if active_session_id is not None else False,
                item[0].updated_at,
                item[0].id,
            ),
            reverse=True,
        )
        candidates = [
            MemorySearchResult(memory=memory, score=score, rank=index)
            for index, (memory, score) in enumerate(scored, start=1)
        ]
        self._trace_event(
            trace,
            event_type="reranker_stage",
            message="Reranker used" if should_use_reranker else "Reranker skipped",
            data={"used": should_use_reranker},
        )
        ranked = self.reranking_engine.rerank(request.query, candidates) if should_use_reranker else candidates
        results = ranked[: request.limit]
        self._trace_event(
            trace,
            event_type="final_results_selected",
            message=f"Selected {len(results)} final search results",
            data={"memory_ids": [result.memory.id for result in results]},
        )
        self._record_access((result.memory.id for result in results), trace=trace)
        output = [
            result.model_copy(update={"memory": self.store.get(result.memory.id) or result.memory})
            for result in results
        ]
        self._end_trace(trace, summary=f"Search returned {len(output)} results")
        return output

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

    def _should_use_llm(self, use_llm: bool | None) -> bool:
        if use_llm is True and self.llm_provider is None:
            raise ProviderNotFoundError("LLM-assisted operation requires an LLM provider")
        if use_llm is False:
            return False
        return self.llm_provider is not None

    def delete(self, memory_id: str) -> bool:
        """Delete a memory by ID."""
        return self.store.delete(memory_id)

    def clear(self) -> None:
        """Delete all memories."""
        self.store.clear()

    def get_trace(self, trace_id: str) -> OperationTrace | None:
        """Return a recorded trace by ID."""
        if self.trace_recorder is None:
            return None
        return self.trace_recorder.get_trace(trace_id)

    def list_traces(self) -> builtins.list[OperationTrace]:
        """Return recorded traces."""
        if self.trace_recorder is None:
            return []
        return self.trace_recorder.list_traces()

    def clear_traces(self) -> None:
        """Clear recorded traces."""
        if self.trace_recorder is not None:
            self.trace_recorder.clear()
        self.last_trace_id = None

    def export_trace(self, trace_id: str) -> dict[str, Any]:
        """Export one trace as a stable benchmark-friendly dictionary."""
        if self.trace_recorder is None:
            raise KeyError(f"Trace not found: {trace_id}")
        return self.trace_recorder.export_trace(trace_id)

    def export_all_traces(self) -> dict[str, Any]:
        """Export all traces as stable benchmark-friendly dictionaries."""
        if self.trace_recorder is None:
            return {"format": TRACE_EXPORT_FORMAT, "version": TRACE_EXPORT_VERSION, "traces": []}
        return self.trace_recorder.export_all_traces()

    def evaluate_search(
        self,
        query: str,
        *,
        relevant_memory_ids: builtins.list[str] | None = None,
        limit: int = 10,
        use_semantic: bool | None = None,
        use_reranker: bool | None = None,
        include_inactive: bool = False,
        include_archived: bool = False,
        current_session_id: str | None = None,
    ) -> SearchEvaluationResult:
        """Run search and return a standardized local evaluation result."""
        before_trace_id = self.last_trace_id
        started = perf_counter()
        candidate_count = len(self._searchable_memories(include_inactive=include_inactive or include_archived))
        results = self.search(
            query,
            limit=limit,
            use_semantic=use_semantic,
            use_reranker=use_reranker,
            include_inactive=include_inactive,
            include_archived=include_archived,
            current_session_id=current_session_id,
        )
        latency_ms = _elapsed_ms(started)
        trace_ids = self._new_trace_ids(before_trace_id)
        trace_event_count = self._trace_event_count(trace_ids)
        decision_count = candidate_count
        selected_ids = [result.memory.id for result in results]
        relevant_ids = relevant_memory_ids or []
        metrics = [
            metric("retrieval_precision", precision_at_k(relevant_ids, selected_ids, limit)),
            metric("retrieval_recall", recall_at_k(relevant_ids, selected_ids, limit)),
            metric("retrieval_mrr", mean_reciprocal_rank(relevant_ids, selected_ids)),
            metric("latency_ms", latency_ms, unit="ms"),
            metric("memories_scanned", candidate_count, unit="count"),
            metric("memories_selected", len(selected_ids), unit="count"),
            metric("trace_event_count", trace_event_count, unit="count"),
            metric("decision_count", decision_count, unit="count"),
        ]
        return SearchEvaluationResult(
            query=query,
            result_count=len(selected_ids),
            candidate_count=candidate_count,
            latency_ms=latency_ms,
            trace_id=trace_ids[-1] if trace_ids else None,
            metrics=metrics,
            selected_memory_ids=selected_ids,
            relevant_memory_ids=relevant_ids,
            memories_scanned=candidate_count,
            explainability_event_count=trace_event_count,
            trace_ids=trace_ids,
            metadata={"limit": limit},
        )

    def evaluate_context(
        self,
        query: str,
        *,
        budget: int | ContextBudget | None = 1200,
        preset: ContextPreset | str | None = "balanced",
        policy: ContextPolicy | None = None,
        limit: int | None = None,
        relevant_memory_ids: builtins.list[str] | None = None,
        include_inactive: bool = False,
        include_archived: bool = False,
        current_session_id: str | None = None,
    ) -> ContextEvaluationResult:
        """Build context and return a standardized local evaluation result."""
        before_trace_id = self.last_trace_id
        started = perf_counter()
        package = self.build_context(
            query,
            budget=budget,
            preset=preset,
            policy=policy,
            limit=limit,
            include_inactive=include_inactive,
            include_archived=include_archived,
            current_session_id=current_session_id,
        )
        latency_ms = _elapsed_ms(started)
        trace_ids = self._new_trace_ids(before_trace_id)
        trace_event_count = self._trace_event_count(trace_ids)
        inclusion_reason_count = len(package.included)
        exclusion_reason_count = len(package.excluded)
        decision_count = inclusion_reason_count + exclusion_reason_count
        included_ids = [item.memory_id for item in package.included]
        relevant_ids = relevant_memory_ids or []
        context_relevance = recall_at_k(relevant_ids, included_ids, len(included_ids)) if relevant_ids else 0.0
        original_tokens = sum(item.estimated_tokens for item in package.included) + sum(
            item.estimated_tokens for item in package.excluded
        )
        metrics = [
            metric("context_token_count", package.stats.used_tokens, unit="tokens"),
            metric("context_relevance_score", context_relevance),
            metric(
                "token_efficiency_ratio",
                token_efficiency_ratio(original_tokens, package.stats.used_tokens),
            ),
            metric(
                "context_utilization_ratio",
                context_utilization_ratio(package.stats.used_tokens, package.stats.available_tokens),
            ),
            metric("latency_ms", latency_ms, unit="ms"),
            metric("memories_scanned", package.stats.total_candidates, unit="count"),
            metric("memories_selected", len(included_ids), unit="count"),
            metric("trace_event_count", trace_event_count, unit="count"),
            metric("decision_count", decision_count, unit="count"),
            metric("inclusion_reason_count", inclusion_reason_count, unit="count"),
            metric("exclusion_reason_count", exclusion_reason_count, unit="count"),
        ]
        return ContextEvaluationResult(
            query=query,
            included_count=len(package.included),
            excluded_count=len(package.excluded),
            estimated_tokens=package.stats.used_tokens,
            budget=package.stats.available_tokens,
            latency_ms=latency_ms,
            trace_id=trace_ids[-1] if trace_ids else None,
            metrics=metrics,
            included_memory_ids=included_ids,
            excluded_memory_ids=[item.memory_id for item in package.excluded],
            candidate_count=package.stats.total_candidates,
            explainability_event_count=trace_event_count,
            trace_ids=trace_ids,
            metadata={"policy_name": package.policy_name, "preset": package.preset},
        )

    def evaluate_compaction(
        self,
        policy: CompactionPolicy | None = None,
        *,
        use_llm: bool | None = None,
        apply: bool = False,
    ) -> CompactionEvaluationResult:
        """Run compaction evaluation, previewing by default to avoid mutation."""
        before_trace_id = self.last_trace_id
        started = perf_counter()
        diff = (
            self.compact(policy=policy, use_llm=use_llm)
            if apply
            else self.preview_compaction(policy=policy, use_llm=use_llm)
        )
        latency_ms = _elapsed_ms(started)
        trace_ids = self._new_trace_ids(before_trace_id)
        trace_event_count = self._trace_event_count(trace_ids)
        compaction_decision_count = len(diff.kept) + len(diff.merged) + len(diff.discarded)
        compacted_reduction_ratio = reduction_ratio(diff.stats.before_count, diff.stats.after_count)
        metrics = [
            metric("compaction_reduction_ratio", compacted_reduction_ratio),
            metric("compaction_information_retention", _information_retention(diff), unit="ratio"),
            metric("latency_ms", latency_ms, unit="ms"),
            metric("memories_scanned", diff.stats.before_count, unit="count"),
            metric("memories_selected", diff.stats.after_count, unit="count"),
            metric("trace_event_count", trace_event_count, unit="count"),
            metric("decision_count", compaction_decision_count, unit="count"),
            metric("compaction_decision_count", compaction_decision_count, unit="count"),
        ]
        return CompactionEvaluationResult(
            before_count=diff.stats.before_count,
            after_count=diff.stats.after_count,
            reduction_ratio=compacted_reduction_ratio,
            latency_ms=latency_ms,
            trace_id=trace_ids[-1] if trace_ids else None,
            metrics=metrics,
            kept_count=diff.stats.kept_count,
            merged_count=diff.stats.merged_count,
            discarded_count=diff.stats.discarded_count,
            created_count=diff.stats.created_count,
            explainability_event_count=trace_event_count,
            trace_ids=trace_ids,
            metadata={"applied": apply, "summary": diff.summary},
        )

    def build_evaluation_report(
        self,
        *,
        benchmark_name: str,
        metrics: builtins.list[MetricResult],
        trace_ids: builtins.list[str] | None = None,
        summary: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> EvaluationReport:
        """Build a standardized evaluation report."""
        return EvaluationReport(
            benchmark_name=benchmark_name,
            metrics=metrics,
            trace_ids=trace_ids or [],
            summary=summary,
            metadata=metadata or {},
        )

    def export_benchmark_result(
        self,
        report: EvaluationReport,
        *,
        include_traces: bool = True,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Export an evaluation report in the stable Mneno Bench format."""
        traces = []
        if include_traces and self.trace_recorder is not None:
            traces = [
                trace for trace_id in report.trace_ids if (trace := self.trace_recorder.get_trace(trace_id)) is not None
            ]
        return build_benchmark_payload(report, traces=traces, metadata=metadata)

    def preview_compaction(
        self, policy: CompactionPolicy | None = None, *, use_llm: bool | None = None
    ) -> CompactionDiff:
        """Analyze compaction without mutating storage."""
        trace = self._start_trace("preview_compaction", metadata={"memory_count": len(self.store.list())})
        active_policy = policy or self.compactor.policy
        self._trace_event(
            trace,
            event_type="compaction_policy_selected",
            message="Compaction policy selected",
            data=active_policy.model_dump(mode="json"),
        )
        diff = self.compactor.compact(self.store.list(), policy=policy, use_llm=self._should_use_llm(use_llm))
        self._trace_compaction_decisions(trace, diff)
        trace_id = self._end_trace(trace, summary=diff.summary)
        return diff.model_copy(update={"trace_id": trace_id})

    def compact(self, policy: CompactionPolicy | None = None, *, use_llm: bool | None = None) -> CompactionDiff:
        """Compact current storage and return an explainable diff."""
        trace = self._start_trace("compact", metadata={"memory_count": len(self.store.list())})
        active_policy = policy or self.compactor.policy
        self._trace_event(
            trace,
            event_type="compaction_policy_selected",
            message="Compaction policy selected",
            data=active_policy.model_dump(mode="json"),
        )
        diff = self.compactor.compact(self.store.list(), policy=policy, use_llm=self._should_use_llm(use_llm))
        self._trace_compaction_decisions(trace, diff)
        for decision in [*diff.discarded, *diff.merged]:
            self.store.delete(decision.memory_id)
            self._trace_event(
                trace,
                event_type="storage_mutation",
                message=f"Deleted compacted memory {decision.memory_id}",
                memory_id=decision.memory_id,
            )
        for memory in diff.created:
            self.store.add(memory)
            self._trace_event(
                trace,
                event_type="storage_mutation",
                message=f"Added compacted memory {memory.id}",
                memory_id=memory.id,
            )
        trace_id = self._end_trace(trace, summary=diff.summary)
        return diff.model_copy(update={"trace_id": trace_id})

    def extract_memories(self, text: str, *, use_llm: bool | None = None) -> ExtractionResult:
        """Extract structured memories from raw text."""
        trace = self._start_trace("extraction", metadata={"use_llm": use_llm})
        self._trace_event(trace, event_type="extraction_started", message="Memory extraction started")
        should_use_llm = self._should_use_llm(use_llm)
        self._trace_event(
            trace,
            event_type="llm_extractor_stage",
            message="LLM extractor used" if should_use_llm else "LLM extractor skipped",
            data={"used": should_use_llm},
        )
        if should_use_llm:
            if self.llm_provider is None:
                raise ProviderNotFoundError("LLM-assisted operation requires an LLM provider")
            result = LLMMemoryExtractor(self.llm_provider).extract(text)
        else:
            self._trace_event(
                trace,
                event_type="deterministic_extractor_used",
                message="Deterministic extractor used",
            )
            result = DeterministicMemoryExtractor().extract(text)
        for error in result.errors:
            self._trace_event(
                trace,
                event_type="extraction_validation_error",
                message=error,
            )
        self._trace_event(
            trace,
            event_type="extraction_completed",
            message=f"Extracted {len(result.extracted)} memories",
            data={"mode": result.mode, "errors": result.errors},
        )
        trace_id = self._end_trace(trace, summary=f"Extracted {len(result.extracted)} memories")
        return result.model_copy(update={"trace_id": trace_id})

    def add_from_text(
        self, text: str, *, use_llm: bool | None = None, session_id: str | None = None
    ) -> ExtractionResult:
        """Extract memories from text and add valid extracted memories to storage."""
        trace = self._start_trace("extraction", metadata={"add_from_text": True, "session_id": session_id})
        result = self.extract_memories(text, use_llm=use_llm)
        extracted = []
        for item in result.extracted:
            memory = self.add(
                item.content,
                memory_type=item.memory_type,
                importance=item.importance,
                metadata=item.metadata,
                tags=item.tags,
                session_id=session_id,
            )
            self._trace_event(
                trace,
                event_type="extracted_memory_added",
                message=f"Added extracted memory {memory.id}",
                memory_id=memory.id,
                session_id=session_id,
            )
            extracted.append(item.model_copy(update={"memory_id": memory.id}))
        trace_id = self._end_trace(trace, summary=f"Added {len(extracted)} extracted memories")
        return result.model_copy(update={"extracted": extracted, "trace_id": trace_id})

    def export_json(self, path: str | Path | None = None) -> dict[str, Any]:
        """Export all memories to a JSON payload and optionally write it to disk."""
        return export_memories(self.store.list(), path, sessions=self.store.list_sessions())

    def import_json(self, path: str | Path, *, mode: ImportMode = "append") -> ImportResult:
        """Import memories from a Mneno JSON export file."""
        return import_memories_from_json(self.store, path, mode=mode)

    def backup(self, path: str | Path | None = None) -> Path:
        """Create a timestamped JSON backup of current memories."""
        return backup_memories(self.store.list(), path, sessions=self.store.list_sessions())

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
        include_inactive: bool = False,
        include_archived: bool = False,
        current_session_id: str | None = None,
    ) -> ContextPackage:
        """Build an explainable context package for a query."""
        trace = self._start_trace("build_context", metadata={"query": query, "preset": str(preset)})
        self._trace_event(
            trace,
            event_type="query_received",
            message="Context query received",
            data={"query": query},
        )
        context_policy, policy_name, preset_name = self._resolve_context_policy(
            budget=budget,
            preset=preset,
            policy=policy,
        )
        self._trace_event(
            trace,
            event_type="context_policy_selected",
            message=f"Selected context policy {policy_name}",
            data={
                "policy_name": policy_name,
                "preset": preset_name,
                "available_tokens": context_policy.available_tokens,
                "max_tokens": context_policy.max_tokens,
            },
        )
        self._trace_event(
            trace,
            event_type="context_budget_calculated",
            message=f"Calculated context budget of {context_policy.available_tokens} available tokens",
            data={
                "max_tokens": context_policy.max_tokens,
                "reserve_tokens": context_policy.reserve_tokens,
                "available_tokens": context_policy.available_tokens,
            },
        )
        memories = self._searchable_memories(include_inactive=include_inactive or include_archived)
        self._trace_event(
            trace,
            event_type="context_candidates",
            message=f"Context builder received {len(memories)} candidate memories",
            data={"candidate_count": len(memories)},
        )
        package = self.context_builder.build(
            query=query,
            memories=memories,
            policy=context_policy,
            policy_name=policy_name,
            preset=preset_name,
            limit=limit,
            active_session_id=current_session_id or self.active_session_id,
        )
        for included_item in package.included:
            self._trace_event(
                trace,
                event_type="context_candidate_scored",
                message=f"Context score {included_item.score:.3f} calculated for memory {included_item.memory_id}",
                memory_id=included_item.memory_id,
                data={"score": included_item.score, "estimated_tokens": included_item.estimated_tokens},
            )
            self._trace_event(
                trace,
                event_type="context_item_included",
                message=included_item.reason,
                memory_id=included_item.memory_id,
                data={"score": included_item.score, "estimated_tokens": included_item.estimated_tokens},
            )
        for excluded_item in package.excluded:
            self._trace_event(
                trace,
                event_type="context_candidate_scored",
                message=f"Context score {excluded_item.score:.3f} calculated for memory {excluded_item.memory_id}",
                memory_id=excluded_item.memory_id,
                data={"score": excluded_item.score, "estimated_tokens": excluded_item.estimated_tokens},
            )
            self._trace_event(
                trace,
                event_type="context_item_excluded",
                message=excluded_item.reason,
                memory_id=excluded_item.memory_id,
                data={"score": excluded_item.score, "estimated_tokens": excluded_item.estimated_tokens},
            )
            if "duplicate content" in excluded_item.reason:
                self._trace_event(
                    trace,
                    event_type="duplicate_removed",
                    message=excluded_item.reason,
                    memory_id=excluded_item.memory_id,
                )
            if "budget exhausted" in excluded_item.reason:
                self._trace_event(
                    trace,
                    event_type="budget_exhausted",
                    message=excluded_item.reason,
                    memory_id=excluded_item.memory_id,
                    data={"available_tokens": package.stats.available_tokens},
                )
        self._trace_event(
            trace,
            event_type="context_stats",
            message="Context package stats calculated",
            data=package.stats.model_dump(mode="json"),
        )
        self._record_access((item.memory_id for item in package.included), trace=trace)
        trace_id = self._end_trace(trace, summary=f"Built context with {len(package.included)} memories")
        return package.model_copy(update={"trace_id": trace_id})

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

    def _active_existing_memories(self) -> builtins.list[Memory]:
        return [
            memory
            for memory in self.store.list()
            if memory.status not in {MemoryStatus.SUPERSEDED, MemoryStatus.ARCHIVED}
            and memory.layer is not MemoryLayer.ARCHIVED
        ]

    def _searchable_memories(self, *, include_inactive: bool) -> builtins.list[Memory]:
        if include_inactive:
            return self.store.list()
        return [
            memory
            for memory in self.store.list()
            if memory.status not in {MemoryStatus.SUPERSEDED, MemoryStatus.ARCHIVED}
            and memory.layer is not MemoryLayer.ARCHIVED
        ]

    def _require_memory(self, memory_id: str) -> Memory:
        memory = self.store.get(memory_id)
        if memory is None:
            raise KeyError(f"Memory not found: {memory_id}")
        return memory

    def _require_session(self, session_id: str) -> Session:
        session = self.store.get_session(session_id)
        if session is None:
            raise KeyError(f"Session not found: {session_id}")
        return session

    def _attach_stored_memory_to_session(
        self, memory: Memory, session_id: str, *, trace: OperationTrace | None = None
    ) -> Memory:
        session = self._require_session(session_id)
        updated_session, updated_memory = self.session_manager.add_memory_to_session(session, memory)
        self.store.update_session(updated_session)
        stored = self.store.update(updated_memory)
        self._trace_event(
            trace,
            event_type="memory_attached_to_session",
            message=f"Attached memory {memory.id} to session {session_id}",
            memory_id=memory.id,
            session_id=session_id,
            data={"sequence_index": stored.sequence_index},
        )
        return stored

    def _boost_session_score(self, score: MemoryScore, reason: str) -> MemoryScore:
        return score.model_copy(update={"total": min(score.total + 0.1, 1.0), "reasons": [*score.reasons, reason]})

    def _record_access(self, memory_ids: Iterable[str], *, trace: OperationTrace | None = None) -> None:
        for memory_id in memory_ids:
            memory = self.store.get(memory_id)
            if memory is None:
                continue
            updated = memory.model_copy(update={"access_count": memory.access_count + 1, "last_accessed_at": utc_now()})
            self.store.update(updated)
            self._trace_event(
                trace,
                event_type="access_count_updated",
                message=f"Updated access count for memory {memory_id}",
                memory_id=memory_id,
                data={"access_count": updated.access_count},
            )

    def _new_trace_ids(self, before_trace_id: str | None) -> builtins.list[str]:
        if self.trace_recorder is None:
            return []
        traces = self.trace_recorder.list_traces()
        if before_trace_id is None:
            return [trace.id for trace in traces]
        ids = [trace.id for trace in traces]
        if before_trace_id not in ids:
            return ids
        return ids[ids.index(before_trace_id) + 1 :]

    def _trace_event_count(self, trace_ids: builtins.list[str]) -> int:
        if self.trace_recorder is None:
            return 0
        return sum(len(trace.events) for trace_id in trace_ids if (trace := self.trace_recorder.get_trace(trace_id)))

    def _start_trace(self, operation: str, *, metadata: dict[str, Any] | None = None) -> OperationTrace | None:
        if not self.trace_enabled or self.trace_recorder is None:
            return None
        trace = self.trace_recorder.start_trace(operation, metadata=metadata)
        self.last_trace_id = trace.id
        return trace

    def _trace_event(
        self,
        trace: OperationTrace | None,
        *,
        event_type: str,
        message: str,
        memory_id: str | None = None,
        session_id: str | None = None,
        data: dict[str, Any] | None = None,
    ) -> None:
        if not self.trace_enabled or self.trace_recorder is None or trace is None:
            return
        self.trace_recorder.add_event(
            trace.id,
            event_type=event_type,
            message=message,
            memory_id=memory_id,
            session_id=session_id,
            data=data,
        )

    def _end_trace(
        self, trace: OperationTrace | None, *, summary: str | None = None, status: CompletedTraceStatus = "success"
    ) -> str | None:
        if not self.trace_enabled or self.trace_recorder is None or trace is None:
            return None
        completed = self.trace_recorder.end_trace(trace.id, status=status, summary=summary)
        self.last_trace_id = completed.id
        return completed.id

    def _trace_compaction_decisions(self, trace: OperationTrace | None, diff: CompactionDiff) -> None:
        for decision in [*diff.kept, *diff.merged, *diff.discarded]:
            self._trace_event(
                trace,
                event_type="memory_evaluated",
                message=f"Evaluated memory {decision.memory_id} for compaction",
                memory_id=decision.memory_id,
                data={"score": decision.score_before},
            )
            self._trace_event(
                trace,
                event_type="compaction_decision",
                message=decision.reason,
                memory_id=decision.memory_id,
                data={
                    "decision": decision.decision.value,
                    "score_before": decision.score_before,
                    "related_memory_ids": decision.related_memory_ids,
                    "resulting_memory_id": decision.resulting_memory_id,
                },
            )
        self._trace_event(
            trace,
            event_type="compaction_stats",
            message="Compaction stats calculated",
            data=diff.stats.model_dump(mode="json"),
        )


def _metadata_list(value: object) -> builtins.list[str]:
    if isinstance(value, list):
        return [str(item) for item in value]
    return []


def _elapsed_ms(started: float) -> float:
    return round(max((perf_counter() - started) * 1000.0, 0.0), 3)


def _information_retention(diff: CompactionDiff) -> float:
    if diff.stats.before_count == 0:
        return 1.0
    retained = diff.stats.kept_count + diff.stats.created_count
    return min(retained / diff.stats.before_count, 1.0)
