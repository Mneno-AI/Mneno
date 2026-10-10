"""Phase A regression coverage for trust, persistence, and retrieval boundaries."""

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import pytest

from mneno import MemoryClient
from mneno.compaction import CompactionPolicy
from mneno.context import ContextBuilder, ContextPolicy
from mneno.io import import_memories_from_payload
from mneno.models import Memory, MemoryStatus
from mneno.sessions import Session
from mneno.storage import InMemoryStorage, JSONFileStorage, SQLiteStorage


@pytest.fixture(params=["memory", "json", "sqlite"])
def storage(request: pytest.FixtureRequest, tmp_path: Path):
    if request.param == "json":
        return JSONFileStorage(tmp_path / "memories.json")
    if request.param == "sqlite":
        return SQLiteStorage(tmp_path / "memories.db")
    return InMemoryStorage()


def test_duplicate_id_does_not_overwrite(storage) -> None:
    original = storage.add(Memory(id="stable", content="Original evidence"))
    with pytest.raises(ValueError, match="already exists"):
        storage.add(Memory(id="stable", content="Replacement evidence"))
    assert storage.get(original.id) == original


def test_delete_removes_session_membership(storage) -> None:
    memory = storage.add(Memory(content="Evidence", session_id="session"))
    storage.add_session(Session(id="session", title="Session", memory_ids=[memory.id]))
    assert storage.delete(memory.id)
    assert storage.get_session("session").memory_ids == []


@pytest.mark.parametrize("invalid", [{"content": ""}, {"title": ""}, "duplicate"])
def test_replace_validates_before_clearing(storage, invalid) -> None:
    original = storage.add(Memory(content="Keep original"))
    payload = MemoryClient().export_json()
    if invalid == "duplicate":
        payload["memories"] = [original.model_dump(mode="json")] * 2
    elif "title" in invalid:
        payload["sessions"] = [invalid]
    else:
        payload["memories"] = [invalid]
    with pytest.raises(ValueError):
        import_memories_from_payload(storage, payload, mode="replace")
    assert storage.get(original.id) == original


@pytest.mark.parametrize("kind", ["operational", "preference"])
def test_contradiction_preserved_through_persistence_and_compaction(storage, kind) -> None:
    client = MemoryClient(storage=storage)
    first, second = (
        ("Current task is build the React UI.", "Current task is build the CLI.")
        if kind == "operational"
        else (
            "User wants a React UI for the current project implementation.",
            "User does not want a React UI for the current project implementation.",
        )
    )
    old = client.add(first, memory_type=kind, source="trusted-file")
    new = client.add(second, memory_type=kind, source="untrusted-note")
    assert client.get(old.id).status is MemoryStatus.CONFLICTED
    assert client.get(old.id).superseded_by is None
    assert client.get(old.id).conflicts_with == [new.id]
    if isinstance(storage, (JSONFileStorage, SQLiteStorage)):
        client = MemoryClient(storage=type(storage)(storage.path))
    client.compact(CompactionPolicy(min_score_to_keep=1.0, max_memories=1))
    assert {old.id, new.id} <= {memory.id for memory in client.list()}
    assert client.get(old.id).source == "trusted-file"
    assert client.get(new.id).source == "untrusted-note"
    context = client.build_context("React CLI project", budget=100)
    assert {old.id, new.id} <= {item.memory_id for item in context.included}
    assert "[CONFLICT WARNING]" in context.text


def test_operational_explicit_update_still_supersedes() -> None:
    client = MemoryClient()
    old = client.add("Current task is build the React UI.", memory_type="operational")
    new = client.add("Task changed to build the CLI.", memory_type="operational")
    assert client.get(old.id).superseded_by == new.id


def test_failed_json_write_does_not_leak_into_next_write(tmp_path: Path, monkeypatch) -> None:
    storage = JSONFileStorage(tmp_path / "memories.json")
    original = storage.add(Memory(content="Original"))
    replace = Path.replace
    with monkeypatch.context() as patch:

        def fail(*args, **kwargs):
            raise OSError("simulated disk failure")

        patch.setattr(Path, "replace", fail)
        with pytest.raises(OSError):
            storage.update(original.model_copy(update={"content": "Uncommitted"}))
    assert Path.replace is replace
    assert storage.get(original.id) == original
    storage.add(Memory(content="Next write"))
    assert JSONFileStorage(storage.path).get(original.id) == original


def test_sqlite_future_schema_not_downgraded(tmp_path: Path) -> None:
    path = tmp_path / "future.db"
    with sqlite3.connect(path) as connection:
        connection.execute("PRAGMA user_version = 999")
    with pytest.raises(ValueError, match="Unsupported SQLite schema"):
        SQLiteStorage(path)
    with sqlite3.connect(path) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 999


@pytest.mark.parametrize("limit", [0, -1])
def test_context_rejects_invalid_limit(limit) -> None:
    with pytest.raises(ValueError, match="limit"):
        MemoryClient().build_context("query", limit=limit)
    with pytest.raises(ValueError, match="limit"):
        ContextBuilder().build(query="query", memories=[], policy=ContextPolicy(max_tokens=10), limit=limit)


def test_equal_scores_stable_across_backends(storage, monkeypatch) -> None:
    import mneno.scoring.temporal as temporal

    class FixedDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime(2026, 1, 1, tzinfo=UTC)

    monkeypatch.setattr(temporal, "datetime", FixedDateTime)
    for identifier in ["a", "c", "b"]:
        storage.add(
            Memory(id=identifier, content="Python note", created_at=FixedDateTime.now(), updated_at=FixedDateTime.now())
        )
    client = MemoryClient(storage=storage)
    assert [result.memory.id for result in client.search("Python")] == ["c", "b", "a"]
    # Restore the persisted access state before comparing the distinct context pipeline.
    for memory in storage.list():
        storage.update(memory.model_copy(update={"access_count": 0, "last_accessed_at": None}))
    assert [
        item.memory_id
        for item in client.build_context("Python", policy=ContextPolicy(max_tokens=100, dedupe=False)).included
    ] == ["c", "b", "a"]


@pytest.mark.parametrize("query", ["東京", "café", "[.*]+", " ", "Python " * 10000])
def test_query_boundaries_and_json_results(query) -> None:
    client = MemoryClient(auto_detect_conflicts=False)
    client.add("Python café 東京 [.*]+")
    results = client.search(query)
    assert all(json.loads(result.model_dump_json())["memory"]["id"] == result.memory.id for result in results)
    assert client.build_context(query, budget=1).stats.used_tokens <= 1


def test_verified_metadata_is_not_correction_intent() -> None:
    client = MemoryClient()
    old = client.add("User prefers Python 3.10.", memory_type="preference")
    new = client.add("User prefers Python 3.11.", memory_type="preference", metadata={"verified": True})
    assert client.get(old.id).status is MemoryStatus.CONFLICTED
    assert client.get(old.id).conflicts_with == [new.id]


def test_resolver_does_not_trust_supersession_report_without_intent() -> None:
    from mneno.conflicts import ConflictAction, ConflictReport, ConflictResolver, ConflictSeverity, ConflictType

    old = Memory(content="Current task is build the React UI.", memory_type="operational")
    new = Memory(content="Current task is build the CLI.", memory_type="operational")
    report = ConflictReport(
        conflict_type=ConflictType.OPERATIONAL_CHANGE,
        severity=ConflictSeverity.MEDIUM,
        new_memory_id=new.id,
        existing_memory_id=old.id,
        reason="External report",
        suggested_action=ConflictAction.SUPERSEDE_EXISTING,
    )
    result = ConflictResolver().resolve(new, [old], [report])
    assert result.updated_existing[0].status is MemoryStatus.CONFLICTED
    assert result.updated_existing[0].superseded_by is None


def test_compaction_failed_insert_preserves_sources(monkeypatch) -> None:
    client = MemoryClient(auto_detect_conflicts=False)
    old = client.add("Python memory")
    new = client.add("Python memory")

    def fail(memory):
        raise OSError("disk full")

    monkeypatch.setattr(client.store, "add", fail)
    with pytest.raises(OSError):
        client.compact()
    assert {memory.id for memory in client.list()} == {old.id, new.id}


@pytest.mark.parametrize("operation", ["search", "build_context"])
def test_stage_trace_matches_result(operation) -> None:
    client = MemoryClient(trace_enabled=True, auto_detect_conflicts=False)
    visible = client.add("Python memory")
    inactive = client.store.add(Memory(content="Python archived", status=MemoryStatus.ARCHIVED))
    output = getattr(client, operation)("Python")
    trace = client.get_trace(client.last_trace_id)
    events = {event.event_type: event.data for event in trace.events}
    stage = events["candidate_filtering" if operation == "search" else "context_candidates"]
    assert set(stage["initial_candidate_ids"]) == {visible.id, inactive.id}
    assert stage["post_filter_candidate_ids"] == [visible.id]
    assert events["effective_retrieval_config"]["use_reranker"] is False
    if operation == "search":
        assert events["reranker_stage"]["initial_ranking_ids"] == [visible.id]
        assert events["ranking_completed"]["reranker_output_ids"] == []
        assert events["final_results_selected"]["memory_ids"] == [result.memory.id for result in output]
    else:
        assert events["context_ranking_completed"]["context_included_ids"] == [
            item.memory_id for item in output.included
        ]
        assert events["context_ranking_completed"]["reranker_input_ids"] == []
    assert "_retrieval_stages" not in (output.model_dump() if operation != "search" else {})
    json.dumps(client.export_trace(trace.id))


def test_content_preview_requires_explicit_opt_in() -> None:
    from mneno.observability import TraceRecorder

    for allow in [False, True]:
        recorder = TraceRecorder(include_memory_content=allow)
        client = MemoryClient(trace_recorder=recorder)
        client.add("Private Python note")
        client.search("Python")
        trace = recorder.get_trace(client.last_trace_id)
        event = next(event for event in trace.events if event.event_type == "score_calculated")
        assert event.data["content_preview"] == ("Private Python note" if allow else "[REDACTED]")


@pytest.mark.parametrize("command", ["search", "context"])
def test_cli_blank_json_is_parseable(command) -> None:
    from typer.testing import CliRunner

    from mneno.cli.app import app

    result = CliRunner().invoke(app, [command, " ", "--json"])
    assert result.exit_code == 1
    assert json.loads(result.stdout) == {"error": "Query must not be empty."}


@pytest.mark.parametrize("operation", ["search", "build_context"])
def test_failed_retrieval_trace_is_completed(operation) -> None:
    client = MemoryClient(trace_enabled=True)
    with pytest.raises(ValueError):
        getattr(client, operation)("query", limit=-1)
    trace = client.get_trace(client.last_trace_id)
    assert trace.status == "error"
    assert trace.completed_at is not None
    assert trace.events[-1].event_type == "operation_failed"
    assert "error_type" in trace.events[-1].data


def test_fixed_reference_time_replays_identical_persisted_state(storage) -> None:
    from mneno.scoring import TemporalMemoryScorer

    scorer = TemporalMemoryScorer(reference_time=datetime(2026, 1, 1, tzinfo=UTC))
    memories = [
        Memory(
            id=identifier,
            content=f"Python {identifier}",
            created_at=datetime(2025, 1, 1, tzinfo=UTC),
            updated_at=datetime(2025, 12, 1, tzinfo=UTC),
        )
        for identifier in ["a", "b"]
    ]
    for memory in memories:
        storage.add(memory)
    client = MemoryClient(storage=storage, scorer=scorer)
    first = [(result.memory.id, result.score.model_dump()) for result in client.search("Python")]
    for memory in memories:
        storage.update(memory)
    second = [(result.memory.id, result.score.model_dump()) for result in client.search("Python")]
    assert first == second


def test_failed_correction_insert_does_not_hide_old_memory(monkeypatch) -> None:
    client = MemoryClient(trace_enabled=True)
    old = client.add("User prefers Python 3.10.", memory_type="preference")

    def fail(memory):
        raise OSError("disk full")

    monkeypatch.setattr(client.store, "add", fail)
    with pytest.raises(OSError):
        client.add("User now prefers Python 3.11.", memory_type="preference")
    assert client.get(old.id).status is MemoryStatus.ACTIVE
    assert client.get(old.id).superseded_by is None
    trace = client.get_trace(client.last_trace_id)
    assert not any(event.event_type == "resolution_action_applied" for event in trace.events)


def test_compaction_preview_does_not_mutate_source_metadata() -> None:
    client = MemoryClient(auto_detect_conflicts=False)
    old = client.add("Python memory", metadata={"values": [1]})
    client.add("Python memory", metadata={"values": 2})
    client.preview_compaction()
    assert client.get(old.id).metadata == {"values": [1]}


@pytest.mark.xfail(strict=True, reason="A-10: append collision relationship remapping requires a separate import fix")
def test_append_collision_remaps_session_membership() -> None:
    client = MemoryClient(auto_detect_conflicts=False)
    session = client.create_session(title="Source session")
    original = client.add("Python note", session_id=session.id)
    import_memories_from_payload(client.store, client.export_json(), mode="append")
    copied = next(memory for memory in client.list() if memory.id != original.id)
    new_session = next(item for item in client.list_sessions() if item.id != session.id)
    assert copied.session_id == new_session.id
    assert new_session.memory_ids == [copied.id]


@pytest.mark.xfail(strict=True, reason="A-11: replacement import needs atomic backend batch support")
def test_replacement_storage_failure_preserves_original() -> None:
    class FailingStorage(InMemoryStorage):
        def add(self, memory):
            raise OSError("write unavailable")

    store = FailingStorage()
    original = InMemoryStorage.add(store, Memory(content="Original"))
    payload = MemoryClient().export_json()
    payload["memories"] = [Memory(content="Replacement").model_dump(mode="json")]
    with pytest.raises(OSError):
        import_memories_from_payload(store, payload, mode="replace")
    assert store.get(original.id) == original


@pytest.mark.xfail(strict=True, reason="A-12: mixed naive/aware timestamp sorting is not normalized")
def test_mixed_timezone_equal_score_retrieval() -> None:
    from mneno.scoring import TemporalMemoryScorer

    client = MemoryClient(scorer=TemporalMemoryScorer(reference_time=datetime(2026, 1, 1, tzinfo=UTC)))
    for identifier, timestamp in [("a", datetime(2025, 1, 1)), ("b", datetime(2025, 1, 1, tzinfo=UTC))]:
        client.store.add(Memory(id=identifier, content="Python", created_at=timestamp, updated_at=timestamp))
    assert [result.memory.id for result in client.search("Python")] == ["b", "a"]


def test_evaluate_search_archived_flag_does_not_count_superseded() -> None:
    client = MemoryClient()
    client.store.add(Memory(content="Python active"))
    client.store.add(Memory(content="Python archived", status=MemoryStatus.ARCHIVED))
    client.store.add(Memory(content="Python superseded", status=MemoryStatus.SUPERSEDED))
    report = client.evaluate_search("Python", include_archived=True)
    assert report.candidate_count == 2
    assert len(report.selected_memory_ids) == 2


def test_json_serialization_failure_restores_committed_state(tmp_path: Path) -> None:
    storage = JSONFileStorage(tmp_path / "memories.json")
    original = storage.add(Memory(content="Original"))
    with pytest.raises(ValueError):
        storage.update(original.model_copy(update={"metadata": {"unserializable": object()}}))
    assert storage.get(original.id) == original
    storage.add(Memory(content="Later write"))
    assert JSONFileStorage(storage.path).get(original.id) == original


@pytest.mark.parametrize("operation", ["search", "build_context"])
def test_enabled_reranker_stage_ids_follow_actual_order(operation) -> None:
    class ReverseReranker:
        name = "reverse-local-test"

        def rerank(self, query, documents):
            return list(reversed(range(len(documents))))

    client = MemoryClient(reranker_provider=ReverseReranker(), trace_enabled=True, auto_detect_conflicts=False)
    client.add("Python alpha")
    client.add("Python beta")
    output = getattr(client, operation)("Python")
    trace = client.get_trace(client.last_trace_id)
    events = {event.event_type: event.data for event in trace.events}
    if operation == "search":
        initial = events["reranker_stage"]["reranker_input_ids"]
        final = events["ranking_completed"]["reranker_output_ids"]
        assert final == [result.memory.id for result in output]
    else:
        initial = events["context_ranking_completed"]["reranker_input_ids"]
        final = events["context_ranking_completed"]["reranker_output_ids"]
        assert final == [item.memory_id for item in output.included]
    assert final == list(reversed(initial))


def test_provider_failure_trace_has_type_without_raw_exception_payload() -> None:
    class FailingReranker:
        name = "failing-local-test"

        def rerank(self, query, documents):
            raise RuntimeError("api_key=private")

    client = MemoryClient(reranker_provider=FailingReranker(), trace_enabled=True)
    client.add("Python alpha")
    with pytest.raises(RuntimeError):
        client.search("Python")
    trace = client.get_trace(client.last_trace_id)
    assert trace.status == "error"
    assert trace.events[-1].data == {"error_type": "RuntimeError"}
    assert "api_key=private" not in json.dumps(client.export_trace(trace.id))
