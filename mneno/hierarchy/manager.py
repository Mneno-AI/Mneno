"""Deterministic hierarchical memory lifecycle manager."""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict, Field

from mneno.hierarchy.layers import MemoryLayer, infer_layer
from mneno.hierarchy.policies import LayerPolicy
from mneno.hierarchy.transitions import DEMOTION_TARGETS, PROMOTION_TARGETS, is_promotional
from mneno.models import Memory, MemoryAuditEvent, MemoryStatus, MemoryType, utc_now


class HierarchyEvaluationResult(BaseModel):
    """Result of evaluating memory layer transitions."""

    model_config = ConfigDict(extra="forbid")

    promoted: list[Memory] = Field(default_factory=list)
    demoted: list[Memory] = Field(default_factory=list)
    archived: list[Memory] = Field(default_factory=list)
    unchanged: list[Memory] = Field(default_factory=list)
    actions: list[str] = Field(default_factory=list)
    trace_id: str | None = None


class HierarchyManager:
    """Evaluate and apply deterministic memory hierarchy transitions."""

    def evaluate(
        self,
        memories: list[Memory],
        policy: LayerPolicy | None = None,
    ) -> HierarchyEvaluationResult:
        """Evaluate promotion, demotion, and archive transitions for memories."""
        active_policy = policy or LayerPolicy()
        promoted: list[Memory] = []
        demoted: list[Memory] = []
        archived: list[Memory] = []
        unchanged: list[Memory] = []
        actions: list[str] = []

        for memory in memories:
            normalized = self.assign_initial_layer(memory)
            retention_score = self.compute_retention_score(normalized)
            normalized = normalized.model_copy(update={"retention_score": retention_score})

            transition = self._transition(normalized, active_policy, retention_score)
            if transition is None:
                unchanged.append(normalized)
                continue

            target_layer, reason = transition
            updated = self.transition_memory(normalized, target_layer, reason=reason)
            if target_layer is MemoryLayer.ARCHIVED:
                archived.append(updated)
                actions.append(f"archived:{memory.id}:{reason}")
            elif is_promotional(normalized.layer, target_layer):
                promoted.append(updated)
                actions.append(f"promoted:{memory.id}:{normalized.layer.value}:to:{target_layer.value}")
            else:
                demoted.append(updated)
                actions.append(f"demoted:{memory.id}:{normalized.layer.value}:to:{target_layer.value}")

        return HierarchyEvaluationResult(
            promoted=promoted,
            demoted=demoted,
            archived=archived,
            unchanged=unchanged,
            actions=actions,
        )

    def assign_initial_layer(self, memory: Memory) -> Memory:
        """Assign an inferred layer when a memory has no explicit layer metadata."""
        if memory.layer is MemoryLayer.ARCHIVED or memory.status is MemoryStatus.ARCHIVED:
            return memory.model_copy(update={"layer": MemoryLayer.ARCHIVED})
        return memory.model_copy(update={"layer": memory.layer or infer_layer(memory.memory_type)})

    def compute_retention_score(self, memory: Memory) -> float:
        """Compute a deterministic retention score from importance, use, recency, and type."""
        access_component = min(memory.access_count / 10.0, 1.0)
        recency_component = _recency_component(memory.updated_at)
        type_component = _type_component(memory.memory_type)
        score = memory.importance * 0.45 + access_component * 0.35 + recency_component * 0.15 + type_component * 0.05
        return round(min(max(score, 0.0), 1.0), 6)

    def transition_memory(self, memory: Memory, target_layer: MemoryLayer | str, *, reason: str) -> Memory:
        """Return a copy of memory transitioned to target_layer with an audit event."""
        resolved_target = MemoryLayer(target_layer)
        now = utc_now()
        updates: dict[str, object] = {
            "layer": resolved_target,
            "updated_at": now,
            "audit": [
                *memory.audit,
                MemoryAuditEvent(
                    event_type=_event_type(memory.layer, resolved_target),
                    reason=reason,
                    related_memory_ids=[],
                    metadata={
                        "from_layer": memory.layer.value,
                        "to_layer": resolved_target.value,
                        "retention_score": memory.retention_score,
                    },
                ),
            ],
        }

        if resolved_target is MemoryLayer.ARCHIVED:
            updates["status"] = MemoryStatus.ARCHIVED
        elif memory.status is MemoryStatus.ARCHIVED:
            updates["status"] = MemoryStatus.ACTIVE

        if is_promotional(memory.layer, resolved_target):
            updates["promotion_count"] = memory.promotion_count + 1
            updates["last_promoted_at"] = now
        else:
            updates["demotion_count"] = memory.demotion_count + 1
            updates["last_demoted_at"] = now

        return memory.model_copy(update=updates)

    def _transition(
        self,
        memory: Memory,
        policy: LayerPolicy,
        retention_score: float,
    ) -> tuple[MemoryLayer, str] | None:
        if memory.status in {MemoryStatus.SUPERSEDED, MemoryStatus.ARCHIVED} or memory.layer is MemoryLayer.ARCHIVED:
            return None

        stale_reason = self._stale_reason(memory, policy)
        if stale_reason is not None and policy.archive_stale:
            if memory.layer in {MemoryLayer.SHORT_TERM, MemoryLayer.WORKING}:
                return MemoryLayer.ARCHIVED, stale_reason
            if memory.layer is MemoryLayer.EPISODIC and retention_score <= policy.demotion_threshold:
                return MemoryLayer.ARCHIVED, stale_reason
            if memory.layer is not MemoryLayer.OPERATIONAL and self._ttl_days(memory.layer, policy) is not None:
                return MemoryLayer.ARCHIVED, stale_reason

        if policy.auto_promote:
            promotion = self._promotion(memory, policy, retention_score)
            if promotion is not None:
                return promotion

        if policy.auto_demote:
            demotion = self._demotion(memory, policy, retention_score)
            if demotion is not None:
                return demotion

        return None

    def _promotion(
        self,
        memory: Memory,
        policy: LayerPolicy,
        retention_score: float,
    ) -> tuple[MemoryLayer, str] | None:
        if memory.layer is MemoryLayer.OPERATIONAL:
            return None
        if memory.layer is MemoryLayer.SHORT_TERM and (
            memory.access_count >= 3 or retention_score >= policy.promotion_threshold
        ):
            return MemoryLayer.EPISODIC, "Promoted short-term memory due to frequent use or high retention score"
        if memory.layer is MemoryLayer.EPISODIC and (
            memory.importance >= 0.85 or retention_score >= policy.promotion_threshold
        ):
            return MemoryLayer.SEMANTIC, "Promoted episodic memory to semantic due to high retention score"
        if memory.memory_type is MemoryType.PREFERENCE and memory.layer is not MemoryLayer.SEMANTIC:
            return MemoryLayer.SEMANTIC, "Promoted stable preference memory to semantic layer"
        target = PROMOTION_TARGETS.get(memory.layer)
        if target is not None and retention_score >= policy.promotion_threshold:
            return target, f"Promoted from {memory.layer.value} due to retention score {retention_score:.2f}"
        return None

    def _demotion(
        self,
        memory: Memory,
        policy: LayerPolicy,
        retention_score: float,
    ) -> tuple[MemoryLayer, str] | None:
        if memory.layer is MemoryLayer.OPERATIONAL:
            return None
        if memory.layer is MemoryLayer.WORKING and self._is_stale(memory, policy.working_ttl_days):
            return MemoryLayer.EPISODIC, "Demoted working memory after inactivity"
        if retention_score > policy.demotion_threshold:
            return None
        target = DEMOTION_TARGETS.get(memory.layer)
        if target is not None:
            return target, f"Demoted from {memory.layer.value} due to low retention score {retention_score:.2f}"
        return None

    def _stale_reason(self, memory: Memory, policy: LayerPolicy) -> str | None:
        ttl_days = self._ttl_days(memory.layer, policy)
        if ttl_days is None or not self._is_stale(memory, ttl_days):
            return None
        return f"Archived stale {memory.layer.value} memory after {ttl_days} days"

    def _ttl_days(self, layer: MemoryLayer, policy: LayerPolicy) -> int | None:
        if layer is MemoryLayer.SHORT_TERM:
            return policy.short_term_ttl_days
        if layer is MemoryLayer.WORKING:
            return policy.working_ttl_days
        if layer is MemoryLayer.EPISODIC:
            return policy.episodic_ttl_days
        if layer is MemoryLayer.SEMANTIC:
            return policy.semantic_ttl_days
        if layer is MemoryLayer.OPERATIONAL:
            return policy.operational_ttl_days
        return None

    def _is_stale(self, memory: Memory, ttl_days: int) -> bool:
        updated_at = memory.updated_at
        if updated_at.tzinfo is None:
            updated_at = updated_at.replace(tzinfo=UTC)
        return (datetime.now(UTC) - updated_at).days >= ttl_days


def _recency_component(updated_at: datetime) -> float:
    if updated_at.tzinfo is None:
        updated_at = updated_at.replace(tzinfo=UTC)
    age_days = max((datetime.now(UTC) - updated_at).total_seconds(), 0.0) / (24 * 60 * 60)
    return max(1.0 - (age_days / 90.0), 0.0)


def _type_component(memory_type: MemoryType) -> float:
    if memory_type is MemoryType.OPERATIONAL:
        return 1.0
    if memory_type is MemoryType.PREFERENCE:
        return 0.8
    if memory_type is MemoryType.SEMANTIC:
        return 0.7
    return 0.4


def _event_type(source: MemoryLayer, target: MemoryLayer) -> str:
    if target is MemoryLayer.ARCHIVED:
        return "archived"
    if is_promotional(source, target):
        return "promoted"
    return "demoted"
