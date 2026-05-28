"""Stable local benchmark export utilities."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from mneno.evaluation.reports import EvaluationReport
from mneno.observability.trace import OperationTrace

BENCHMARK_EXPORT_FORMAT = "mneno.benchmark.result"
BENCHMARK_EXPORT_VERSION = 1


def build_benchmark_payload(
    report: EvaluationReport,
    *,
    traces: list[OperationTrace] | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a stable JSON-serializable benchmark payload."""
    exported_traces = traces or []
    return {
        "format": BENCHMARK_EXPORT_FORMAT,
        "version": BENCHMARK_EXPORT_VERSION,
        "benchmark": report.benchmark_name,
        "report": report.model_dump(mode="json"),
        "metrics": [metric.model_dump(mode="json") for metric in report.metrics],
        "trace_ids": report.trace_ids,
        "traces": [trace.model_dump(mode="json") for trace in exported_traces],
        "metadata": metadata or {},
    }


def export_benchmark_payload(payload: dict[str, Any], path: str | Path | None = None) -> dict[str, Any]:
    """Optionally write a benchmark payload and return it."""
    if path is not None:
        output_path = Path(path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = output_path.with_name(f"{output_path.name}.tmp")
        temp_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        temp_path.replace(output_path)
    return payload


def export_benchmark_report(
    report: EvaluationReport,
    *,
    traces: list[OperationTrace] | None = None,
    metadata: dict[str, Any] | None = None,
    path: str | Path | None = None,
) -> dict[str, Any]:
    """Build and optionally write a benchmark report payload."""
    return export_benchmark_payload(build_benchmark_payload(report, traces=traces, metadata=metadata), path)
