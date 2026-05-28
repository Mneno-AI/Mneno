"""Timeline reconstruction for session memories."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from mneno.hierarchy.layers import MemoryLayer
from mneno.models import Memory, MemoryStatus, utc_now


class TimelineEvent(BaseModel):
    """A deterministic timeline event derived from a memory."""

    model_config = ConfigDict(extra="forbid")

    memory_id: str
    session_id: str | None = None
    timestamp: datetime
    content: str
    layer: MemoryLayer
    status: MemoryStatus
    event_type: str = "memory"
    sequence_index: int | None = None
    reason: str = Field(min_length=1)


class Timeline(BaseModel):
    """Ordered memory timeline across one or more sessions."""

    model_config = ConfigDict(extra="forbid")

    events: list[TimelineEvent] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=utc_now)
    session_ids: list[str] = Field(default_factory=list)
    summary: str = ""
    trace_id: str | None = None


class TimelineBuilder:
    """Build deterministic memory timelines."""

    def build(self, memories: list[Memory], *, session_ids: list[str] | None = None) -> Timeline:
        """Reconstruct a stable ordered memory timeline."""
        allowed_session_ids = set(session_ids or [])
        filtered = [
            memory
            for memory in memories
            if not allowed_session_ids or (memory.session_id is not None and memory.session_id in allowed_session_ids)
        ]
        ordered = sorted(
            filtered,
            key=lambda memory: (
                memory.created_at,
                memory.session_id or "",
                memory.sequence_index if memory.sequence_index is not None else 10**9,
                memory.id,
            ),
        )
        events = [self._event(memory) for memory in ordered]
        timeline_session_ids = session_ids or sorted(
            {event.session_id for event in events if event.session_id is not None}
        )
        return Timeline(
            events=events,
            session_ids=timeline_session_ids,
            summary=_timeline_summary(events),
        )

    def _event(self, memory: Memory) -> TimelineEvent:
        ordering_reason = (
            "Ordered by created_at, session_id, sequence_index, and memory_id"
            if memory.sequence_index is not None
            else "Ordered by created_at, session_id, and memory_id because sequence_index is unset"
        )
        return TimelineEvent(
            memory_id=memory.id,
            session_id=memory.session_id,
            timestamp=memory.created_at,
            content=memory.content,
            layer=memory.layer,
            status=memory.status,
            event_type="memory",
            sequence_index=memory.sequence_index,
            reason=ordering_reason,
        )


def _timeline_summary(events: list[TimelineEvent]) -> str:
    if not events:
        return "Timeline contains 0 events."
    session_count = len({event.session_id for event in events if event.session_id is not None})
    return f"Timeline contains {len(events)} events across {session_count} sessions."
