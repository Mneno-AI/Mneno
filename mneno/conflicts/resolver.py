"""Safe conflict resolution for memory lifecycle metadata."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from mneno.conflicts.policies import ConflictPolicy
from mneno.conflicts.reports import ConflictReport, ConflictType
from mneno.hierarchy.layers import MemoryLayer
from mneno.models import Memory, MemoryAuditEvent, MemoryStatus, utc_now


class ConflictResolutionResult(BaseModel):
    """Result of applying conflict reports to memory metadata."""

    model_config = ConfigDict(extra="forbid")

    new_memory: Memory
    updated_existing: list[Memory] = Field(default_factory=list)
    reports: list[ConflictReport] = Field(default_factory=list)
    actions: list[str] = Field(default_factory=list)


class ConflictResolver:
    """Apply conflict reports without deleting memories."""

    def resolve(
        self,
        new_memory: Memory,
        existing_memories: list[Memory],
        reports: list[ConflictReport],
        policy: ConflictPolicy | None = None,
    ) -> ConflictResolutionResult:
        """Resolve reports by updating statuses, relationship links, and audit events."""
        active_policy = policy or ConflictPolicy()
        by_id = {memory.id: memory for memory in existing_memories}
        updated_by_id: dict[str, Memory] = {}
        actions: list[str] = []
        current_new = new_memory

        for report in reports:
            existing = updated_by_id.get(report.existing_memory_id) or by_id.get(report.existing_memory_id)
            if existing is None:
                continue

            if report.conflict_type in {
                ConflictType.SUPERSESSION,
                ConflictType.PREFERENCE_CHANGE,
                ConflictType.OPERATIONAL_CHANGE,
            }:
                should_supersede = (
                    active_policy.auto_supersede_preferences or report.conflict_type is ConflictType.OPERATIONAL_CHANGE
                )
                if not should_supersede:
                    current_new, existing = self._audit_only(current_new, existing, report)
                    actions.append(f"kept_both:{existing.id}:{current_new.id}")
                else:
                    existing = self._supersede_existing(existing, current_new, report)
                    current_new = self._audit_new(current_new, report, event_type="superseded_existing")
                    actions.append(f"superseded_existing:{existing.id}:by:{current_new.id}")

            elif report.conflict_type is ConflictType.CONTRADICTION:
                if active_policy.mark_conflicts:
                    existing = self._mark_conflicted(existing, current_new, report)
                    current_new = self._mark_conflicted(current_new, existing, report)
                    actions.append(f"marked_conflicted:{existing.id}:{current_new.id}")
                else:
                    current_new, existing = self._audit_only(current_new, existing, report)
                    actions.append(f"reported_conflict:{existing.id}:{current_new.id}")

            elif report.conflict_type is ConflictType.DUPLICATE:
                if active_policy.auto_archive_duplicates:
                    existing = self._archive_existing(existing, current_new, report)
                    current_new = self._audit_new(current_new, report, event_type="archived_duplicate_existing")
                    actions.append(f"archived_duplicate:{existing.id}")
                else:
                    current_new, existing = self._audit_only(current_new, existing, report)
                    actions.append(f"reported_duplicate:{existing.id}:{current_new.id}")

            else:
                current_new, existing = self._audit_only(current_new, existing, report)
                actions.append(f"reported_conflict:{existing.id}:{current_new.id}")

            updated_by_id[existing.id] = existing

        return ConflictResolutionResult(
            new_memory=current_new,
            updated_existing=list(updated_by_id.values()),
            reports=reports,
            actions=actions,
        )

    def _supersede_existing(self, existing: Memory, new_memory: Memory, report: ConflictReport) -> Memory:
        return existing.model_copy(
            update={
                "status": MemoryStatus.SUPERSEDED,
                "superseded_by": new_memory.id,
                "updated_at": utc_now(),
                "audit": [
                    *existing.audit,
                    self._audit_event(
                        "superseded",
                        report,
                        related_memory_ids=[new_memory.id],
                        reason=f"Superseded by memory {new_memory.id}: {report.reason}",
                    ),
                ],
            }
        )

    def _archive_existing(self, existing: Memory, new_memory: Memory, report: ConflictReport) -> Memory:
        return existing.model_copy(
            update={
                "status": MemoryStatus.ARCHIVED,
                "layer": MemoryLayer.ARCHIVED,
                "updated_at": utc_now(),
                "audit": [
                    *existing.audit,
                    self._audit_event(
                        "archived",
                        report,
                        related_memory_ids=[new_memory.id],
                        reason=f"Archived as duplicate of memory {new_memory.id}: {report.reason}",
                    ),
                ],
            }
        )

    def _mark_conflicted(self, memory: Memory, related: Memory, report: ConflictReport) -> Memory:
        conflicts_with = [*memory.conflicts_with]
        if related.id not in conflicts_with:
            conflicts_with.append(related.id)
        return memory.model_copy(
            update={
                "status": MemoryStatus.CONFLICTED,
                "conflicts_with": conflicts_with,
                "updated_at": utc_now(),
                "audit": [
                    *memory.audit,
                    self._audit_event(
                        "conflicted",
                        report,
                        related_memory_ids=[related.id],
                        reason=f"Marked conflicted with memory {related.id}: {report.reason}",
                    ),
                ],
            }
        )

    def _audit_new(self, new_memory: Memory, report: ConflictReport, *, event_type: str) -> Memory:
        return new_memory.model_copy(
            update={
                "updated_at": utc_now(),
                "audit": [
                    *new_memory.audit,
                    self._audit_event(
                        event_type,
                        report,
                        related_memory_ids=[report.existing_memory_id],
                        reason=report.reason,
                    ),
                ],
            }
        )

    def _audit_only(self, new_memory: Memory, existing: Memory, report: ConflictReport) -> tuple[Memory, Memory]:
        updated_new = self._audit_new(new_memory, report, event_type="conflict_reported")
        updated_existing = existing.model_copy(
            update={
                "updated_at": utc_now(),
                "audit": [
                    *existing.audit,
                    self._audit_event(
                        "conflict_reported",
                        report,
                        related_memory_ids=[new_memory.id],
                        reason=report.reason,
                    ),
                ],
            }
        )
        return updated_new, updated_existing

    def _audit_event(
        self,
        event_type: str,
        report: ConflictReport,
        *,
        related_memory_ids: list[str],
        reason: str,
    ) -> MemoryAuditEvent:
        return MemoryAuditEvent(
            event_type=event_type,
            reason=reason,
            related_memory_ids=related_memory_ids,
            metadata={
                "conflict_id": report.conflict_id,
                "conflict_type": report.conflict_type.value,
                "severity": report.severity.value,
                "suggested_action": report.suggested_action.value,
                "evidence": report.evidence,
            },
        )
