"""Developer helpers for inspecting traces."""

from __future__ import annotations

from typing import Any

from mneno.observability.events import TraceEvent
from mneno.observability.trace import OperationTrace


class TraceInspector:
    """Inspect and summarize local operation traces."""

    def summarize_trace(self, trace: OperationTrace) -> str:
        """Return a concise summary for a trace."""
        duration = f"{trace.duration_ms:.3f}ms" if trace.duration_ms is not None else "incomplete"
        return (
            f"{trace.operation} trace {trace.id} finished with {trace.status} in {duration}; "
            f"{len(trace.events)} events."
        )

    def explain_memory_decision(self, trace: OperationTrace, memory_id: str) -> list[str]:
        """Return messages from all trace events related to a memory."""
        events = self.filter_events(trace, memory_id=memory_id)
        return [event.message for event in events]

    def filter_events(
        self,
        trace: OperationTrace,
        event_type: str | None = None,
        memory_id: str | None = None,
        session_id: str | None = None,
    ) -> list[TraceEvent]:
        """Filter trace events by event type and/or memory ID."""
        events = trace.events
        if event_type is not None:
            events = [event for event in events if event.event_type == event_type]
        if memory_id is not None:
            events = [event for event in events if event.memory_id == memory_id]
        if session_id is not None:
            events = [event for event in events if event.session_id == session_id]
        return events

    def export_trace_json(self, trace: OperationTrace) -> dict[str, Any]:
        """Export a trace as a stable JSON-compatible dictionary."""
        return trace.model_dump(mode="json")
