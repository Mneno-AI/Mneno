"""Stable local benchmark export utilities."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from mneno.evaluation.metrics import MetricResult
from mneno.evaluation.reports import EvaluationReport
from mneno.observability.recorder import build_trace_payload
from mneno.observability.trace import OperationTrace

BENCHMARK_EXPORT_FORMAT = "mneno.benchmark.result"
BENCHMARK_EXPORT_VERSION = 1


class BenchmarkExport(BaseModel):
    """Versioned benchmark result consumed by Mneno Bench."""

    model_config = ConfigDict(extra="forbid")

    format: Literal["mneno.benchmark.result"] = "mneno.benchmark.result"
    version: Literal[1] = 1
    benchmark: str = Field(min_length=1)
    created_at: datetime
    metrics: list[MetricResult] = Field(default_factory=list)
    traces: list[dict[str, Any]] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-compatible benchmark payload."""
        return self.model_dump(mode="json")

    def to_json(self) -> str:
        """Return stable benchmark JSON text."""
        return json.dumps(self.to_dict(), indent=2, sort_keys=True)


def export_evaluation_report(report: EvaluationReport) -> dict[str, Any]:
    """Export an evaluation report as a JSON-compatible dictionary."""
    return report.to_dict()


def export_evaluation_report_json(report: EvaluationReport) -> str:
    """Export an evaluation report as stable JSON text."""
    return report.to_json()


def export_benchmark_result(
    report: EvaluationReport,
    *,
    traces: list[OperationTrace] | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Export an evaluation report in the versioned Mneno Bench schema."""
    combined_metadata = {**report.metadata, **(metadata or {})}
    payload = BenchmarkExport(
        benchmark=report.benchmark_name,
        created_at=report.created_at,
        metrics=report.metrics,
        traces=[build_trace_payload(trace) for trace in traces or []],
        metadata=combined_metadata,
    )
    return payload.to_dict()


def export_benchmark_result_json(
    report: EvaluationReport,
    *,
    traces: list[OperationTrace] | None = None,
    metadata: dict[str, Any] | None = None,
) -> str:
    """Export an evaluation report as stable benchmark JSON text."""
    return json.dumps(export_benchmark_result(report, traces=traces, metadata=metadata), indent=2, sort_keys=True)


def build_benchmark_payload(
    report: EvaluationReport,
    *,
    traces: list[OperationTrace] | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a stable JSON-serializable benchmark payload."""
    return export_benchmark_result(report, traces=traces, metadata=metadata)


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
