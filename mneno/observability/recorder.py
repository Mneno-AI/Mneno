"""In-memory local trace recorder."""

from __future__ import annotations

import json
from typing import Any

from mneno.models import utc_now
from mneno.observability.events import TraceEvent
from mneno.observability.trace import OperationTrace, TraceStatus


class TraceRecorder:
    """Record local in-memory operation traces."""

    def __init__(self) -> None:
        self._traces: dict[str, OperationTrace] = {}
        self._active_trace_id: str | None = None

    def start_trace(self, operation: str, metadata: dict[str, Any] | None = None) -> OperationTrace:
        """Start and store a new operation trace."""
        trace = OperationTrace(operation=operation, metadata=metadata or {})
        self._traces[trace.id] = trace
        self._active_trace_id = trace.id
        self.add_event(
            trace.id,
            event_type="operation_started",
            message=f"Started {operation}",
            data={"metadata": trace.metadata},
        )
        return trace

    def add_event(
        self,
        trace_id: str | None = None,
        *,
        event_type: str,
        message: str,
        memory_id: str | None = None,
        session_id: str | None = None,
        data: dict[str, Any] | None = None,
    ) -> TraceEvent:
        """Append an event to a trace."""
        resolved_trace_id = trace_id or self._active_trace_id
        if resolved_trace_id is None or resolved_trace_id not in self._traces:
            raise KeyError("No active trace")
        trace = self._traces[resolved_trace_id]
        event = TraceEvent(
            trace_id=trace.id,
            operation=trace.operation,
            event_type=event_type,
            message=message,
            memory_id=memory_id,
            session_id=session_id,
            data=data or {},
        )
        self._traces[trace.id] = trace.model_copy(update={"events": [*trace.events, event]})
        return event

    def end_trace(
        self,
        trace_id: str | None = None,
        *,
        status: TraceStatus = "success",
        summary: str | None = None,
    ) -> OperationTrace:
        """Complete a trace and calculate duration."""
        resolved_trace_id = trace_id or self._active_trace_id
        if resolved_trace_id is None or resolved_trace_id not in self._traces:
            raise KeyError("No active trace")
        trace = self._traces[resolved_trace_id]
        completed_at = utc_now()
        duration_ms = (completed_at - trace.started_at).total_seconds() * 1000.0
        completed = trace.model_copy(
            update={
                "completed_at": completed_at,
                "duration_ms": round(max(duration_ms, 0.0), 3),
                "status": status,
                "summary": summary,
            }
        )
        self._traces[trace.id] = completed
        if self._active_trace_id == trace.id:
            self._active_trace_id = None
        return completed

    def get_trace(self, trace_id: str) -> OperationTrace | None:
        """Return a trace by ID."""
        return self._traces.get(trace_id)

    def list_traces(self) -> list[OperationTrace]:
        """Return traces in start order."""
        return list(self._traces.values())

    def clear(self) -> None:
        """Clear all recorded traces."""
        self._traces.clear()
        self._active_trace_id = None

    def export_trace(self, trace_id: str) -> dict[str, Any]:
        """Export one trace as a stable dictionary."""
        trace = self.get_trace(trace_id)
        if trace is None:
            raise KeyError(f"Trace not found: {trace_id}")
        return trace.model_dump(mode="json")

    def export_all_traces(self) -> list[dict[str, Any]]:
        """Export all traces as stable dictionaries."""
        return [trace.model_dump(mode="json") for trace in self.list_traces()]

    def export_trace_json(self, trace_id: str) -> str:
        """Export one trace as stable JSON."""
        return json.dumps(self.export_trace(trace_id), indent=2, sort_keys=True)

    def export_all_traces_json(self) -> str:
        """Export all traces as stable JSON."""
        return json.dumps(self.export_all_traces(), indent=2, sort_keys=True)
