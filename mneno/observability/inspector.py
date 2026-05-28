"""Developer helpers for inspecting traces."""

from __future__ import annotations

import json

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

    def explain_memory_decision(self, trace: OperationTrace, memory_id: str) -> str:
        """Explain all trace events related to a memory."""
        events = self.filter_events(trace, memory_id=memory_id)
        if not events:
            return f"No trace events found for memory {memory_id}."
        messages = [event.message for event in events]
        return f"Memory {memory_id}: " + " | ".join(messages)

    def filter_events(
        self,
        trace: OperationTrace,
        *,
        event_type: str | None = None,
        memory_id: str | None = None,
    ) -> list[TraceEvent]:
        """Filter trace events by event type and/or memory ID."""
        events = trace.events
        if event_type is not None:
            events = [event for event in events if event.event_type == event_type]
        if memory_id is not None:
            events = [event for event in events if event.memory_id == memory_id]
        return events

    def export_trace_json(self, trace: OperationTrace) -> str:
        """Export a trace as stable JSON."""
        return json.dumps(trace.model_dump(mode="json"), indent=2, sort_keys=True)
