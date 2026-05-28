import json

from mneno import MemoryClient
from mneno.hierarchy import LayerPolicy
from mneno.observability import TraceInspector, TraceRecorder


def test_trace_recorder_start_add_event_end_get_list_clear() -> None:
    recorder = TraceRecorder()
    trace = recorder.start_trace("search", metadata={"query": "Python"})

    event = recorder.add_event(trace.id, event_type="candidate_count", message="Found candidates", data={"count": 2})
    completed = recorder.end_trace(trace.id, summary="Done")

    assert event.trace_id == trace.id
    assert completed.completed_at is not None
    assert completed.duration_ms is not None
    assert completed.status == "success"
    assert recorder.get_trace(trace.id) == completed
    assert recorder.list_traces() == [completed]

    recorder.clear()

    assert recorder.list_traces() == []


def test_trace_recorder_error_status() -> None:
    recorder = TraceRecorder()
    trace = recorder.start_trace("search")

    completed = recorder.end_trace(trace.id, status="error", summary="Failed")

    assert completed.status == "error"
    assert completed.summary == "Failed"


def test_client_tracing_disabled_by_default() -> None:
    client = MemoryClient()
    client.add("User prefers Python.")
    client.search("Python")

    assert client.last_trace_id is None
    assert client.list_traces() == []


def test_tracing_enabled_records_search_trace() -> None:
    client = MemoryClient(trace_enabled=True)
    memory = client.add("User prefers Python.", importance=0.9)

    client.search("Python")
    trace = client.get_trace(client.last_trace_id or "")

    assert trace is not None
    assert trace.operation == "search"
    assert any(event.event_type == "candidate_filtering" for event in trace.events)
    assert any(event.event_type == "score_calculated" and event.memory_id == memory.id for event in trace.events)
    assert any(event.event_type == "final_results_selected" for event in trace.events)


def test_tracing_enabled_records_build_context_trace_and_trace_id() -> None:
    client = MemoryClient(trace_enabled=True)
    client.add("User prefers Python.", importance=0.9)

    context = client.build_context("Python", budget=50)
    trace = client.get_trace(context.trace_id or "")

    assert context.trace_id == client.last_trace_id
    assert trace is not None
    assert trace.operation == "build_context"
    assert any(event.event_type == "context_policy_selected" for event in trace.events)
    assert any(event.event_type == "context_stats" for event in trace.events)


def test_tracing_enabled_records_compact_trace_and_trace_id() -> None:
    client = MemoryClient(trace_enabled=True)
    client.add("User prefers Python.", importance=0.9)
    client.add("User prefers Python.", importance=0.8)

    diff = client.compact()
    trace = client.get_trace(diff.trace_id or "")

    assert diff.trace_id == client.last_trace_id
    assert trace is not None
    assert trace.operation == "compact"
    assert any(event.event_type == "compaction_decision" for event in trace.events)
    assert any(event.event_type == "compaction_stats" for event in trace.events)


def test_trace_id_on_extraction_hierarchy_and_timeline_results() -> None:
    client = MemoryClient(trace_enabled=True)
    session = client.create_session(title="Trace session")

    extraction = client.add_from_text("The user is building Mneno.", session_id=session.id)
    hierarchy = client.evaluate_hierarchy(policy=LayerPolicy(auto_promote=False, auto_demote=False))
    timeline = client.build_timeline(session_ids=[session.id])

    assert extraction.trace_id is not None
    assert hierarchy.trace_id is not None
    assert timeline.trace_id is not None
    assert client.get_trace(timeline.trace_id) is not None


def test_hierarchy_trace_includes_transition_events() -> None:
    client = MemoryClient(trace_enabled=True)
    memory = client.add("Useful short-term memory.", layer="short_term")
    client.store.update(memory.model_copy(update={"access_count": 5}))

    result = client.evaluate_hierarchy()
    trace = client.get_trace(result.trace_id or "")

    assert trace is not None
    assert any(event.event_type == "retention_score_calculated" for event in trace.events)
    assert any(event.event_type == "hierarchy_transition" for event in trace.events)


def test_conflict_trace_includes_reports() -> None:
    client = MemoryClient(trace_enabled=True)
    client.add("User prefers Python 3.10.", memory_type="preference")

    result = client.add_with_report("User now prefers Python 3.11.", memory_type="preference")
    trace = client.get_trace(result.trace_id or "")

    assert trace is not None
    assert any(event.event_type == "conflict_report_generated" for event in trace.events)
    assert any(event.event_type == "conflict_resolution_action" for event in trace.events)


def test_session_and_timeline_traces_include_session_events() -> None:
    client = MemoryClient(trace_enabled=True)
    session = client.create_session(title="Timeline")
    memory = client.add("Timeline memory.", session_id=session.id)

    timeline = client.build_timeline(session_ids=[session.id])
    trace = client.get_trace(timeline.trace_id or "")

    assert client.get_trace(client.list_traces()[0].id) is not None
    assert trace is not None
    assert any(event.event_type == "timeline_event_ordered" and event.memory_id == memory.id for event in trace.events)


def test_last_trace_id_updates_and_clear_traces() -> None:
    client = MemoryClient(trace_enabled=True)
    client.add("User prefers Python.")
    first_trace_id = client.last_trace_id
    client.search("Python")

    assert client.last_trace_id != first_trace_id
    assert client.list_traces()

    client.clear_traces()

    assert client.last_trace_id is None
    assert client.list_traces() == []


def test_trace_inspector_summary_filters_explain_and_export() -> None:
    recorder = TraceRecorder()
    trace = recorder.start_trace("search")
    recorder.add_event(trace.id, event_type="score_calculated", message="Score calculated", memory_id="memory-1")
    completed = recorder.end_trace(trace.id, summary="Search done")
    inspector = TraceInspector()

    assert "search trace" in inspector.summarize_trace(completed)
    assert inspector.filter_events(completed, event_type="score_calculated")
    assert inspector.filter_events(completed, memory_id="memory-1")
    assert "Score calculated" in inspector.explain_memory_decision(completed, "memory-1")

    exported = inspector.export_trace_json(completed)
    assert json.loads(exported)["id"] == completed.id
