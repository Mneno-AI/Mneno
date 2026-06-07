import json

from mneno import (
    BenchmarkExport,
    EvaluationReport,
    MemoryClient,
    MetricResult,
    build_benchmark_payload,
    context_utilization_ratio,
    export_benchmark_result,
    export_benchmark_result_json,
    export_evaluation_report,
    export_evaluation_report_json,
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

    assert precision_at_k(relevant, retrieved, 2) == 0.5
    assert recall_at_k(relevant, retrieved, 3) == 2 / 3
    assert mean_reciprocal_rank(relevant, retrieved) == 0.5
    assert reduction_ratio(10, 4) == 0.6
    assert token_efficiency_ratio(100, 25) == 0.75
    assert context_utilization_ratio(25, 100) == 0.25


def test_metric_helpers_handle_empty_inputs() -> None:
    assert precision_at_k([], [], 5) == 0.0
    assert recall_at_k([], [], 5) == 0.0
    assert mean_reciprocal_rank([], []) == 0.0
    assert reduction_ratio(0, 0) == 0.0
    assert token_efficiency_ratio(0, 0) == 0.0
    assert context_utilization_ratio(0, 0) == 0.0


def test_evaluation_report_serializes_stably() -> None:
    report = EvaluationReport(
        id="report-1",
        benchmark_name="synthetic",
        metrics=[MetricResult(name="latency_ms", value=1.25, unit="ms")],
        trace_ids=["trace-1"],
        summary="Done",
        metadata={"case": "unit"},
    )
    payload = report.to_dict()

    assert payload["id"] == "report-1"
    assert payload["benchmark_name"] == "synthetic"
    assert payload["metrics"][0]["name"] == "latency_ms"
    assert json.loads(report.to_json()) == payload
    assert export_evaluation_report(report) == payload
    assert json.loads(export_evaluation_report_json(report)) == payload

    metric_result = report.metrics[0]
    assert json.loads(metric_result.to_json()) == metric_result.to_dict()


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
    assert payload["created_at"] == report.to_dict()["created_at"]
    assert payload["metrics"][0]["name"] == "retrieval_precision"
    assert payload["traces"] == []
    assert payload["metadata"] == {"suite": "unit"}

    model = BenchmarkExport.model_validate(payload)
    assert model.to_dict() == payload
    assert json.loads(model.to_json()) == payload


def test_benchmark_export_dict_and_json_are_stable() -> None:
    report = EvaluationReport(
        id="report-1",
        benchmark_name="synthetic",
        metrics=[MetricResult(name="retrieval_precision", value=1, unit="ratio")],
        metadata={"dataset": "local"},
    )

    payload = export_benchmark_result(report, metadata={"run": "unit"})
    json_payload = json.loads(export_benchmark_result_json(report, metadata={"run": "unit"}))

    assert payload == json_payload
    assert payload["metadata"] == {"dataset": "local", "run": "unit"}


def test_client_evaluate_search_generates_metrics_and_trace_ids() -> None:
    client = MemoryClient(trace_enabled=True)
    memory = client.add("User prefers Python.", importance=0.9)
    client.add("Unrelated note.", importance=0.1)

    result = client.evaluate_search("Python", relevant_memory_ids=[memory.id], limit=2)

    metrics = {metric.name: metric.value for metric in result.metrics}
    assert result.result_count == len(result.selected_memory_ids)
    assert result.trace_id == result.trace_ids[-1]
    assert result.selected_memory_ids
    assert metrics["retrieval_precision"] >= 0.5
    assert metrics["retrieval_recall"] == 1.0
    assert metrics["retrieval_mrr"] == 1.0
    assert metrics["memories_scanned"] == 2
    assert metrics["decision_count"] == 2
    assert result.trace_ids
    assert json.loads(result.to_json()) == result.to_dict()


def test_client_evaluate_context_generates_metrics_and_trace_ids() -> None:
    client = MemoryClient(trace_enabled=True)
    memory = client.add("User is building Mneno.", importance=0.9)

    result = client.evaluate_context("What is the user building?", relevant_memory_ids=[memory.id], budget=50)

    metrics = {metric.name: metric.value for metric in result.metrics}
    assert result.included_count == 1
    assert result.excluded_count == 0
    assert result.estimated_tokens == result.token_count
    assert result.budget == 50
    assert result.trace_id == result.trace_ids[-1]
    assert result.included_memory_ids == [memory.id]
    assert metrics["context_token_count"] > 0
    assert metrics["context_relevance_score"] == 1.0
    assert "token_efficiency_ratio" in metrics
    assert "context_utilization_ratio" in metrics
    assert metrics["inclusion_reason_count"] == 1
    assert metrics["exclusion_reason_count"] == 0
    assert result.trace_ids
    assert json.loads(result.to_json()) == result.to_dict()


def test_client_evaluate_context_allows_empty_context_with_relevance_labels() -> None:
    client = MemoryClient(trace_enabled=True)
    memories = [
        client.add(
            f"Operational memory number {index}",
            memory_type="operational" if index < 4 else "semantic",
        )
        for index in range(10)
    ]

    for budget in (2, 3):
        result = client.evaluate_context(
            "What memories are available?",
            budget=budget,
            limit=4,
            relevant_memory_ids=[memories[0].id],
        )

        metrics = {metric.name: metric.value for metric in result.metrics}
        assert result.included_count == 0
        assert result.excluded_count == 10
        assert result.estimated_tokens == 0
        assert metrics["context_relevance_score"] == 0.0
        assert metrics["context_utilization_ratio"] == 0.0
        assert result.trace_id is not None


def test_client_evaluate_compaction_generates_metrics_without_mutating_by_default() -> None:
    client = MemoryClient(trace_enabled=True)
    client.add("User prefers Python.", importance=0.9)
    client.add("User prefers Python.", importance=0.8)

    result = client.evaluate_compaction()

    metrics = {metric.name: metric.value for metric in result.metrics}
    assert result.before_count == 2
    assert result.after_count == 1
    assert result.reduction_ratio == 0.5
    assert result.trace_id == result.trace_ids[-1]
    assert len(client.list()) == 2
    assert metrics["compaction_reduction_ratio"] == 0.5
    assert "compaction_information_retention" in metrics
    assert metrics["compaction_decision_count"] == 2
    assert result.trace_ids
    assert json.loads(result.to_json()) == result.to_dict()


def test_evaluation_wrappers_work_without_tracing() -> None:
    client = MemoryClient()
    client.add("User is building Mneno.")

    search = client.evaluate_search("Mneno")
    context = client.evaluate_context("Mneno", budget=50)
    compaction = client.evaluate_compaction()

    assert search.trace_id is None
    assert context.trace_id is None
    assert compaction.trace_id is None
    assert {metric.name: metric.value for metric in search.metrics}["trace_event_count"] == 0


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

    assert exported_trace["format"] == "mneno.trace"
    assert exported_trace["version"] == 1
    assert exported_trace["trace"]["id"] == result.trace_ids[0]
    assert exported_traces["format"] == "mneno.trace"
    assert exported_traces["version"] == 1
    assert exported_traces["traces"]
    assert benchmark_payload["format"] == "mneno.benchmark.result"
    assert benchmark_payload["benchmark"] == "synthetic"
    assert benchmark_payload["traces"]
    assert benchmark_payload["traces"][0]["format"] == "mneno.trace"


def test_trace_exports_are_repeatable() -> None:
    client = MemoryClient(trace_enabled=True)
    client.add("Stable trace export.")

    trace_id = client.last_trace_id or ""

    assert client.export_trace(trace_id) == client.export_trace(trace_id)
    assert client.export_all_traces() == client.export_all_traces()


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

    assert isinstance(adapter, BenchmarkAdapter)
    report = run_benchmark(adapter, client)

    assert report.benchmark_name == "dummy"
    assert report.metrics
    assert client.list()
