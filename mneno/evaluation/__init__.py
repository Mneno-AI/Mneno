"""Evaluation hooks and benchmark integration support."""

from mneno.evaluation.adapters import BenchmarkAdapter
from mneno.evaluation.benchmark import run_benchmark
from mneno.evaluation.export import (
    BENCHMARK_EXPORT_FORMAT,
    BENCHMARK_EXPORT_VERSION,
    build_benchmark_payload,
    export_benchmark_payload,
    export_benchmark_report,
)
from mneno.evaluation.metrics import (
    MetricResult,
    mean_reciprocal_rank,
    metric,
    precision_at_k,
    recall_at_k,
    reduction_ratio,
    token_efficiency_ratio,
)
from mneno.evaluation.reports import (
    CompactionEvaluationResult,
    ContextEvaluationResult,
    EvaluationReport,
    SearchEvaluationResult,
)

__all__ = [
    "BENCHMARK_EXPORT_FORMAT",
    "BENCHMARK_EXPORT_VERSION",
    "BenchmarkAdapter",
    "CompactionEvaluationResult",
    "ContextEvaluationResult",
    "EvaluationReport",
    "MetricResult",
    "SearchEvaluationResult",
    "build_benchmark_payload",
    "export_benchmark_payload",
    "export_benchmark_report",
    "mean_reciprocal_rank",
    "metric",
    "precision_at_k",
    "recall_at_k",
    "reduction_ratio",
    "run_benchmark",
    "token_efficiency_ratio",
]
