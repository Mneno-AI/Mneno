"""Evaluation hooks and benchmark integration support."""

from mneno.evaluation.adapters import BenchmarkAdapter
from mneno.evaluation.benchmark import run_benchmark
from mneno.evaluation.export import (
    BENCHMARK_EXPORT_FORMAT,
    BENCHMARK_EXPORT_VERSION,
    BenchmarkExport,
    build_benchmark_payload,
    export_benchmark_payload,
    export_benchmark_report,
    export_benchmark_result,
    export_benchmark_result_json,
    export_evaluation_report,
    export_evaluation_report_json,
)
from mneno.evaluation.metrics import (
    MetricResult,
    context_utilization_ratio,
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
    "BenchmarkExport",
    "CompactionEvaluationResult",
    "ContextEvaluationResult",
    "EvaluationReport",
    "MetricResult",
    "SearchEvaluationResult",
    "build_benchmark_payload",
    "context_utilization_ratio",
    "export_benchmark_result",
    "export_benchmark_result_json",
    "export_benchmark_payload",
    "export_benchmark_report",
    "export_evaluation_report",
    "export_evaluation_report_json",
    "mean_reciprocal_rank",
    "metric",
    "precision_at_k",
    "recall_at_k",
    "reduction_ratio",
    "run_benchmark",
    "token_efficiency_ratio",
]
