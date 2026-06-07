"""In-memory local trace recorder."""

from __future__ import annotations

import json
from typing import Any

from mneno.models import utc_now
from mneno.observability.events import TraceEvent
from mneno.observability.trace import CompletedTraceStatus, OperationTrace

_REDACTED = "[REDACTED]"
TRACE_EXPORT_FORMAT = "mneno.trace"
TRACE_EXPORT_VERSION = 1
_SENSITIVE_KEYS = {
    "api_key",
    "apikey",
    "authorization",
    "credential",
    "credentials",
    "password",
    "secret",
    "token",
}


class TraceRecorder:
    """Record local in-memory operation traces."""

    def __init__(self) -> None:
        self._traces: dict[str, OperationTrace] = {}

    def start_trace(self, operation: str, metadata: dict[str, Any] | None = None) -> OperationTrace:
        """Start and store a new operation trace."""
        trace = OperationTrace(operation=operation, metadata=_sanitize_data(metadata or {}))
        self._traces[trace.id] = trace
        self.add_event(
            trace.id,
            event_type="operation_started",
            message=f"Started {operation}",
            data={"metadata": trace.metadata},
        )
        return self._traces[trace.id]

    def add_event(
        self,
        trace_id: str,
        event_type: str,
        message: str,
        memory_id: str | None = None,
        session_id: str | None = None,
        data: dict[str, Any] | None = None,
    ) -> TraceEvent:
        """Append an event to a trace."""
        if trace_id not in self._traces:
            raise KeyError(f"Unknown trace_id: {trace_id}")
        trace = self._traces[trace_id]
        event = TraceEvent(
            trace_id=trace.id,
            operation=trace.operation,
            event_type=event_type,
            message=message,
            memory_id=memory_id,
            session_id=session_id,
            data=_sanitize_data(data or {}),
        )
        self._traces[trace.id] = trace.model_copy(update={"events": [*trace.events, event]})
        return event

    def end_trace(
        self,
        trace_id: str,
        status: CompletedTraceStatus = "success",
        summary: str | None = None,
    ) -> OperationTrace:
        """Complete a trace and calculate duration."""
        if trace_id not in self._traces:
            raise KeyError(f"Unknown trace_id: {trace_id}")
        trace = self._traces[trace_id]
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

    def export_trace(self, trace_id: str) -> dict[str, Any]:
        """Export one trace in the stable benchmark envelope."""
        trace = self.get_trace(trace_id)
        if trace is None:
            raise KeyError(f"Trace not found: {trace_id}")
        return build_trace_payload(trace)

    def export_all_traces(self) -> dict[str, Any]:
        """Export all traces in a stable benchmark envelope."""
        return {
            "format": TRACE_EXPORT_FORMAT,
            "version": TRACE_EXPORT_VERSION,
            "traces": [trace.model_dump(mode="json") for trace in self.list_traces()],
        }

    def export_trace_json(self, trace_id: str) -> str:
        """Export one trace as stable JSON."""
        return json.dumps(self.export_trace(trace_id), indent=2, sort_keys=True)

    def export_all_traces_json(self) -> str:
        """Export all traces as stable JSON."""
        return json.dumps(self.export_all_traces(), indent=2, sort_keys=True)


def _sanitize_data(data: dict[str, Any]) -> dict[str, Any]:
    return {key: _sanitize_value(key, value) for key, value in data.items()}


def _sanitize_value(key: str, value: Any) -> Any:
    normalized_key = key.lower().replace("-", "_")
    if normalized_key in _SENSITIVE_KEYS or normalized_key.endswith(("_secret", "_token", "_password")):
        return _REDACTED
    if isinstance(value, dict):
        return _sanitize_data(value)
    if isinstance(value, list):
        return [_sanitize_value("item", item) for item in value]
    if isinstance(value, tuple):
        return [_sanitize_value("item", item) for item in value]
    return value


def build_trace_payload(trace: OperationTrace) -> dict[str, Any]:
    """Build the stable envelope for one operation trace."""
    return {
        "format": TRACE_EXPORT_FORMAT,
        "version": TRACE_EXPORT_VERSION,
        "trace": trace.model_dump(mode="json"),
    }
