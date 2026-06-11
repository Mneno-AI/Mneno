import pytest

from mneno import MemoryClient
from mneno.hierarchy import LayerPolicy
from mneno.observability import TraceInspector, TraceRecorder


def test_trace_recorder_start_add_event_end_get_list_clear() -> None:
    recorder = TraceRecorder()
    trace = recorder.start_trace("search", metadata={"query": "Python"})

    assert trace.status == "running"
    assert trace.events[0].event_type == "operation_started"
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


def test_trace_recorder_unknown_trace_id_raises_clear_error() -> None:
    recorder = TraceRecorder()

    with pytest.raises(KeyError, match="Unknown trace_id: missing"):
        recorder.add_event("missing", "event", "Message")


def test_trace_recorder_redacts_sensitive_structured_data() -> None:
    recorder = TraceRecorder()
    trace = recorder.start_trace("search", metadata={"api_key": "secret-value"})
    recorder.add_event(trace.id, "provider", "Provider used", data={"nested": {"access_token": "token-value"}})

    stored = recorder.get_trace(trace.id)

    assert stored is not None
    assert stored.metadata["api_key"] == "[REDACTED]"
    assert stored.events[-1].data["nested"]["access_token"] == "[REDACTED]"


def test_client_tracing_disabled_by_default() -> None:
    client = MemoryClient()
    client.add("User prefers Python.")
    client.search("Python")

    assert client.last_trace_id is None
    assert client.list_traces() == []


def test_client_uses_supplied_trace_recorder() -> None:
    recorder = TraceRecorder()
    client = MemoryClient(trace_recorder=recorder)

    client.add("Recorded by supplied recorder.")

    assert client.trace_recorder is recorder
    assert client.trace_enabled
    assert recorder.list_traces()


def test_tracing_enabled_records_search_trace() -> None:
    client = MemoryClient(trace_enabled=True)
    memory = client.add("User prefers Python.", importance=0.9)

    client.search("Python")
    trace = client.get_trace(client.last_trace_id or "")

    assert trace is not None
    assert trace.operation == "search"
    assert any(event.event_type == "query_received" for event in trace.events)
    assert any(event.event_type == "memories_loaded" for event in trace.events)
    assert any(event.event_type == "candidate_filtering" for event in trace.events)
    assert any(event.event_type == "score_calculated" and event.memory_id == memory.id for event in trace.events)
    assert any(event.event_type == "final_results_selected" for event in trace.events)


def test_search_trace_includes_score_breakdown_identity_rank_and_decision() -> None:
    client = MemoryClient(trace_enabled=True, auto_detect_conflicts=False)
    included = client.add(
        "Python memory SDK.",
        metadata={
            "dataset_memory_id": "dialog-1",
            "source_id": "source-1",
            "dataset_id": "dataset-1",
            "locomo_id": "locomo-1",
            "original_id": "original-1",
        },
    )
    excluded = client.add("Office chair inventory.")

    client.search("Python memory SDK", limit=1)
    trace = client.get_trace(client.last_trace_id or "")

    assert trace is not None
    score_event = next(
        event for event in trace.events if event.event_type == "score_calculated" and event.memory_id == included.id
    )
    assert score_event.data["internal_memory_id"] == included.id
    assert score_event.data["dataset_memory_id"] == "dialog-1"
    assert score_event.data["source_id"] == "source-1"
    assert score_event.data["dataset_id"] == "dataset-1"
    assert score_event.data["locomo_id"] == "locomo-1"
    assert score_event.data["original_id"] == "original-1"
    assert score_event.data["keyword_relevance_component"] > 0
    assert score_event.data["exact_query_terms"] == ["memory", "python", "sdk"]
    assert score_event.data["phrase_match"] is True
    assert "recency_component" in score_event.data
    assert "hierarchy_layer_adjustment" in score_event.data
    decisions = [event for event in trace.events if event.event_type == "retrieval_candidate_decision"]
    assert any(
        event.memory_id == included.id and event.data["rank"] == 1 and event.data["included"] for event in decisions
    )
    assert any(
        event.memory_id == excluded.id
        and not event.data["included"]
        and "exceeds limit" in event.data["exclusion_reason"]
        for event in decisions
    )


def test_search_trace_records_session_boost() -> None:
    client = MemoryClient(trace_enabled=True)
    session = client.create_session(title="Active work")
    memory = client.add("Current session memory.", session_id=session.id)

    client.search("session", current_session_id=session.id)
    trace = client.get_trace(client.last_trace_id or "")

    assert trace is not None
    assert any(event.event_type == "session_boost_stage" and event.data["used"] for event in trace.events)
    assert any(event.event_type == "session_boost_applied" and event.memory_id == memory.id for event in trace.events)


def test_tracing_enabled_records_build_context_trace_and_trace_id() -> None:
    client = MemoryClient(trace_enabled=True)
    client.add("User prefers Python.", importance=0.9)

    context = client.build_context("Python", budget=50)
    trace = client.get_trace(context.trace_id or "")

    assert context.trace_id == client.last_trace_id
    assert trace is not None
    assert trace.operation == "build_context"
    assert any(event.event_type == "context_policy_selected" for event in trace.events)
    assert any(event.event_type == "context_budget_calculated" for event in trace.events)
    assert any(event.event_type == "context_candidate_scored" for event in trace.events)
    assert any(event.event_type == "context_stats" for event in trace.events)


def test_context_trace_includes_rank_score_breakdown_and_exclusion_reason() -> None:
    client = MemoryClient(trace_enabled=True, auto_detect_conflicts=False)
    included = client.add("Python memory SDK.", metadata={"source_id": "source-1"})
    excluded = client.add("Office chair inventory.", importance=1.0)

    context = client.build_context("Python memory SDK", budget=3)
    trace = client.get_trace(context.trace_id or "")

    assert trace is not None
    scored = [event for event in trace.events if event.event_type == "context_candidate_scored"]
    included_event = next(event for event in scored if event.memory_id == included.id)
    excluded_event = next(event for event in scored if event.memory_id == excluded.id)
    assert included_event.data["source_id"] == "source-1"
    assert included_event.data["rank"] == 1
    assert included_event.data["included"] is True
    assert included_event.data["score_reasons"]
    assert excluded_event.data["included"] is False
    assert excluded_event.data["exclusion_reason"] == "Excluded because budget exhausted"


def test_context_trace_records_duplicate_and_budget_exclusions() -> None:
    client = MemoryClient(trace_enabled=True)
    client.add("Duplicate context memory.", importance=0.9)
    client.add("Duplicate context memory.", importance=0.8)
    client.add("This memory cannot fit into one token.", importance=0.7)

    duplicate_context = client.build_context("memory", budget=100)
    duplicate_trace = client.get_trace(duplicate_context.trace_id or "")
    context = client.build_context("memory", budget=1)
    trace = client.get_trace(context.trace_id or "")

    assert duplicate_trace is not None
    assert any(event.event_type == "duplicate_removed" for event in duplicate_trace.events)
    assert trace is not None
    assert any(event.event_type == "budget_exhausted" for event in trace.events)


def test_tracing_enabled_records_compact_trace_and_trace_id() -> None:
    client = MemoryClient(trace_enabled=True)
    client.add("User prefers Python.", importance=0.9)
    client.add("User prefers Python.", importance=0.8)

    diff = client.compact()
    trace = client.get_trace(diff.trace_id or "")

    assert diff.trace_id == client.last_trace_id
    assert trace is not None
    assert trace.operation == "compact"
    assert any(event.event_type == "memory_evaluated" for event in trace.events)
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
    assert any(event.event_type == "promoted" and event.memory_id == memory.id for event in trace.events)
    assert any(event.event_type == "audit_event_added" and event.memory_id == memory.id for event in trace.events)
    assert any(event.event_type == "hierarchy_transition" for event in trace.events)


def test_conflict_trace_includes_reports() -> None:
    client = MemoryClient(trace_enabled=True)
    client.add("User prefers Python 3.10.", memory_type="preference")

    result = client.add_with_report("User now prefers Python 3.11.", memory_type="preference")
    trace = client.get_trace(result.trace_id or "")

    assert trace is not None
    assert any(event.event_type == "conflict_report_generated" for event in trace.events)
    assert any(event.event_type == "resolution_action_applied" for event in trace.events)
    assert any(event.event_type == "audit_event_added" for event in trace.events)
    assert any(event.event_type == "conflict_resolution_action" for event in trace.events)


def test_extraction_trace_records_extractor_mode() -> None:
    client = MemoryClient(trace_enabled=True)

    result = client.extract_memories("The user prefers deterministic local tools.")
    trace = client.get_trace(result.trace_id or "")

    assert trace is not None
    assert any(event.event_type == "extraction_started" for event in trace.events)
    assert any(event.event_type == "deterministic_extractor_used" for event in trace.events)
    assert any(event.event_type == "llm_extractor_stage" and not event.data["used"] for event in trace.events)


def test_session_and_timeline_traces_include_session_events() -> None:
    client = MemoryClient(trace_enabled=True)
    session = client.create_session(title="Timeline")
    memory = client.add("Timeline memory.", session_id=session.id)

    timeline = client.build_timeline(session_ids=[session.id])
    trace = client.get_trace(timeline.trace_id or "")

    assert client.get_trace(client.list_traces()[0].id) is not None
    assert trace is not None
    assert any(event.event_type == "timeline_event_ordered" and event.memory_id == memory.id for event in trace.events)
    assert any(event.event_type == "timeline_built" for event in trace.events)


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
    recorder.add_event(
        trace.id,
        event_type="score_calculated",
        message="Score calculated",
        memory_id="memory-1",
        session_id="session-1",
    )
    completed = recorder.end_trace(trace.id, summary="Search done")
    inspector = TraceInspector()

    assert "search trace" in inspector.summarize_trace(completed)
    assert inspector.filter_events(completed, event_type="score_calculated")
    assert inspector.filter_events(completed, memory_id="memory-1")
    assert inspector.filter_events(completed, session_id="session-1")
    assert inspector.explain_memory_decision(completed, "memory-1") == ["Score calculated"]

    exported = inspector.export_trace_json(completed)
    assert exported["id"] == completed.id
    assert isinstance(exported["started_at"], str)
