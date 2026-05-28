import json

from mneno import (
    EvaluationReport,
    MemoryClient,
    MetricResult,
    build_benchmark_payload,
    mean_reciprocal_rank,
    precision_at_k,
    recall_at_k,
    reduction_ratio,
    token_efficiency_ratio,
)
from mneno.evaluation import BENCHMARK_EXPORT_FORMAT, BenchmarkAdapter, run_benchmark


def test_precision_recall_mrr_reduction_and_token_efficiency() -> None:
    retrieved = ["a", "b", "c"]
    relevant = ["b", "c", "d"]

    assert precision_at_k(retrieved, relevant, 2) == 0.5
    assert recall_at_k(retrieved, relevant, 3) == 2 / 3
    assert mean_reciprocal_rank(retrieved, relevant) == 0.5
    assert reduction_ratio(10, 4) == 0.6
    assert token_efficiency_ratio(25, 100) == 0.25


def test_evaluation_report_serializes_stably() -> None:
    report = EvaluationReport(
        id="report-1",
        benchmark_name="synthetic",
        metrics=[MetricResult(name="latency_ms", value=1.25, unit="ms")],
        trace_ids=["trace-1"],
        summary="Done",
        metadata={"case": "unit"},
    )
    payload = report.model_dump(mode="json")

    assert payload["id"] == "report-1"
    assert payload["benchmark_name"] == "synthetic"
    assert payload["metrics"][0]["name"] == "latency_ms"
    assert json.dumps(payload, sort_keys=True)


def test_benchmark_payload_schema_is_stable() -> None:
    report = EvaluationReport(
        id="report-1",
        benchmark_name="synthetic",
        metrics=[MetricResult(name="retrieval_precision", value=1.0, unit="ratio")],
        trace_ids=[],
    )

    payload = build_benchmark_payload(report, metadata={"suite": "unit"})

    assert payload["format"] == BENCHMARK_EXPORT_FORMAT
    assert payload["version"] == 1
    assert payload["benchmark"] == "synthetic"
    assert payload["metrics"][0]["name"] == "retrieval_precision"
    assert payload["traces"] == []
    assert payload["metadata"] == {"suite": "unit"}


def test_client_evaluate_search_generates_metrics_and_trace_ids() -> None:
    client = MemoryClient(trace_enabled=True)
    memory = client.add("User prefers Python.", importance=0.9)
    client.add("Unrelated note.", importance=0.1)

    result = client.evaluate_search("Python", relevant_memory_ids=[memory.id], limit=2)

    metrics = {metric.name: metric.value for metric in result.metrics}
    assert result.selected_memory_ids
    assert metrics["retrieval_precision"] >= 0.5
    assert metrics["retrieval_recall"] == 1.0
    assert metrics["retrieval_mrr"] == 1.0
    assert metrics["memories_scanned"] == 2
    assert result.trace_ids


def test_client_evaluate_context_generates_metrics_and_trace_ids() -> None:
    client = MemoryClient(trace_enabled=True)
    memory = client.add("User is building Mneno.", importance=0.9)

    result = client.evaluate_context("What is the user building?", relevant_memory_ids=[memory.id], budget=50)

    metrics = {metric.name: metric.value for metric in result.metrics}
    assert result.included_memory_ids == [memory.id]
    assert metrics["context_token_count"] > 0
    assert metrics["context_relevance_score"] == 1.0
    assert "token_efficiency_ratio" in metrics
    assert result.trace_ids


def test_client_evaluate_compaction_generates_metrics_without_mutating_by_default() -> None:
    client = MemoryClient(trace_enabled=True)
    client.add("User prefers Python.", importance=0.9)
    client.add("User prefers Python.", importance=0.8)

    result = client.evaluate_compaction()

    metrics = {metric.name: metric.value for metric in result.metrics}
    assert result.before_count == 2
    assert result.after_count == 1
    assert len(client.list()) == 2
    assert metrics["compaction_reduction_ratio"] == 0.5
    assert "compaction_information_retention" in metrics
    assert result.trace_ids


def test_client_evaluate_compaction_can_apply_mutation() -> None:
    client = MemoryClient(trace_enabled=True)
    client.add("User prefers Python.", importance=0.9)
    client.add("User prefers Python.", importance=0.8)

    result = client.evaluate_compaction(apply=True)

    assert result.after_count == 1
    assert len(client.list()) == 1


def test_trace_export_and_benchmark_export_work() -> None:
    client = MemoryClient(trace_enabled=True)
    memory = client.add("User prefers Python.", importance=0.9)
    result = client.evaluate_search("Python", relevant_memory_ids=[memory.id])
    report = client.build_evaluation_report(
        benchmark_name="synthetic",
        metrics=result.metrics,
        trace_ids=result.trace_ids,
        summary="Search eval",
    )

    exported_trace = client.export_trace(result.trace_ids[0])
    exported_traces = client.export_all_traces()
    benchmark_payload = client.export_benchmark_result(report)

    assert exported_trace["id"] == result.trace_ids[0]
    assert exported_traces
    assert benchmark_payload["format"] == "mneno.benchmark.result"
    assert benchmark_payload["benchmark"] == "synthetic"
    assert benchmark_payload["traces"]


class DummyBenchmarkAdapter:
    name = "dummy"

    def __init__(self) -> None:
        self.client: MemoryClient | None = None

    def prepare(self, client: MemoryClient) -> None:
        self.client = client
        client.add("Benchmark memory.")

    def run(self) -> EvaluationReport:
        assert self.client is not None
        result = self.client.evaluate_search("Benchmark")
        return self.client.build_evaluation_report(
            benchmark_name=self.name,
            metrics=result.metrics,
            trace_ids=result.trace_ids,
            summary="Dummy benchmark complete",
        )


def test_benchmark_adapter_protocol_and_runner() -> None:
    client = MemoryClient(trace_enabled=True)
    adapter: BenchmarkAdapter = DummyBenchmarkAdapter()

    report = run_benchmark(adapter, client)

    assert report.benchmark_name == "dummy"
    assert report.metrics
    assert client.list()
