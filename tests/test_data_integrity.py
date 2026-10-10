"""Failure-boundary and relationship regressions for Phase A completion."""

import json
import multiprocessing
import os
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path
from threading import Barrier

import pytest

from mneno import MemoryClient
from mneno._time import as_utc
from mneno.compaction import CompactionPolicy
from mneno.io import import_memories_from_payload
from mneno.models import Memory, MemoryAuditEvent, MemoryStatus
from mneno.scoring import TemporalMemoryScorer
from mneno.sessions import Session, TimelineBuilder
from mneno.storage import InMemoryStorage, JSONFileStorage, SQLiteStorage, StorageCommitError, StorageConflictError
from mneno.storage.transactions import atomic_transaction


@pytest.fixture(params=["memory", "json", "sqlite"])
def store(request, tmp_path):
    return {
        "memory": lambda: InMemoryStorage(),
        "json": lambda: JSONFileStorage(tmp_path / "records.json"),
        "sqlite": lambda: SQLiteStorage(tmp_path / "records.db"),
    }[request.param]()


def reopen(store):
    return type(store)(store.path) if hasattr(store, "path") else store


def snapshot(store):
    return (
        sorted((memory.model_dump(mode="json") for memory in store.list()), key=lambda item: item["id"]),
        sorted((session.model_dump(mode="json") for session in store.list_sessions()), key=lambda item: item["id"]),
    )


def payload(memories, sessions=()):
    exported = MemoryClient().export_json()
    exported["memories"] = [memory.model_dump(mode="json") for memory in memories]
    exported["sessions"] = [session.model_dump(mode="json") for session in sessions]
    return exported


def test_replacement_repeated_and_reopened(store):
    store.add(Memory(id="old", content="Original", session_id="old-session"))
    store.add_session(Session(id="old-session", title="Original", memory_ids=["old"]))
    new = Memory(id="new", content="Replacement", session_id="new-session")
    session = Session(id="new-session", title="Replacement", memory_ids=["new"])
    for _ in range(2):
        result = import_memories_from_payload(store, payload([new], [session]), mode="replace")
        assert (result.imported_count, result.imported_session_count) == (1, 1)
        assert snapshot(reopen(store)) == ([new.model_dump(mode="json")], [session.model_dump(mode="json")])


def test_transaction_rolls_back_after_multiple_staged_mutations(store):
    original = store.add(Memory(id="original", content="Original", session_id="session"))
    store.add_session(Session(id="session", title="Original", memory_ids=[original.id]))
    before = snapshot(store)
    with pytest.raises(OSError, match="later write"), atomic_transaction(store) as staged:
        staged.clear()
        staged.add(Memory(content="First replacement"))
        staged.add_session(Session(title="First replacement"))
        raise OSError("later write")
    assert snapshot(store) == before
    assert snapshot(reopen(store)) == before
    store.add(Memory(content="Lock released"))


def test_transaction_revalidates_mutated_models_before_commit(store):
    original = store.add(Memory(content="Original"))
    with pytest.raises(ValueError), atomic_transaction(store) as staged:
        staged.update(original.model_copy(update={"content": ""}))
    assert reopen(store).get(original.id) == original


def test_staged_objects_cannot_mutate_committed_memory_state():
    store = InMemoryStorage()
    with store.transaction() as staged:
        memory = staged.add(Memory(content="Committed", metadata={"values": [1]}))
    memory.metadata["values"].append(2)
    assert store.get(memory.id).metadata == {"values": [1]}


def test_sqlite_rollback_after_first_persistent_insert(tmp_path, monkeypatch):
    store = SQLiteStorage(tmp_path / "records.db")
    original = store.add(Memory(id="old", content="Original", session_id="session"))
    store.add_session(Session(id="session", title="Original", memory_ids=[original.id]))
    before = snapshot(store)

    # Avoid initialization's PRAGMA write while the test owns BEGIN IMMEDIATE.
    def fail(connection, staged):
        connection.execute("DELETE FROM memories")
        connection.execute("DELETE FROM sessions")
        first = staged.list()[0]
        connection.execute(
            "INSERT INTO memories VALUES (?, ?, ?, ?)",
            (first.id, first.model_dump_json(), first.created_at.isoformat(), first.updated_at.isoformat()),
        )
        with sqlite3.connect(store.path) as reader:
            assert [row[0] for row in reader.execute("SELECT id FROM memories")] == ["old"]
        raise OSError("after first SQL insert")

    monkeypatch.setattr(store, "_replace_snapshot", fail)
    with pytest.raises(OSError):
        import_memories_from_payload(store, payload([Memory(content="Replacement")]), mode="replace")
    assert snapshot(reopen(store)) == before


def test_sqlite_real_constraint_failure_rolls_back(tmp_path):
    store = SQLiteStorage(tmp_path / "records.db")
    store.add(Memory(id="old", content="Original"))
    with sqlite3.connect(store.path) as connection:
        connection.execute(
            "CREATE TRIGGER fail_insert BEFORE INSERT ON memories WHEN NEW.id = 'fail' "
            "BEGIN SELECT RAISE(ABORT, 'injected failure'); END"
        )
    before = snapshot(store)
    with pytest.raises(sqlite3.IntegrityError, match="injected failure"):
        import_memories_from_payload(
            store, payload([Memory(id="first", content="First"), Memory(id="fail", content="Fail")]), mode="replace"
        )
    assert snapshot(reopen(store)) == before


@pytest.mark.parametrize("boundary", ["file_sync", "rename", "serialization"])
def test_json_precommit_failure_restores_cache_and_file(tmp_path, monkeypatch, boundary):
    store = JSONFileStorage(tmp_path / "records.json")
    store.add(Memory(id="old", content="Original"))
    before = snapshot(store)
    original_bytes = store.path.read_bytes()
    with monkeypatch.context() as patch:

        def fail(*args, **kwargs):
            raise OSError("injected failure")

        if boundary == "file_sync":
            patch.setattr(os, "fsync", fail)
        elif boundary == "rename":
            patch.setattr(Path, "replace", fail)
        replacement = Memory(content="Replacement", metadata={"bad": object()} if boundary == "serialization" else {})
        with pytest.raises((OSError, ValueError)), store.transaction() as staged:
            staged.clear()
            staged.add(replacement)
            staged.add_session(Session(title="Replacement"))
    assert store.path.read_bytes() == original_bytes
    assert snapshot(store) == before
    assert snapshot(reopen(store)) == before
    assert not list(tmp_path.glob("*.tmp"))
    store.add(Memory(content="Subsequent write"))


@pytest.mark.skipif(os.name == "nt", reason="Directory fsync is POSIX-specific")
def test_json_postcommit_sync_error_reports_complete_committed_state(tmp_path, monkeypatch):
    store = JSONFileStorage(tmp_path / "records.json")
    store.add(Memory(id="old", content="Original"))
    real_fsync = os.fsync
    calls = 0

    def fail_directory_sync(fd):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("directory sync unavailable")
        real_fsync(fd)

    with monkeypatch.context() as patch:
        patch.setattr(os, "fsync", fail_directory_sync)
        with pytest.raises(StorageCommitError) as error:
            import_memories_from_payload(store, payload([Memory(id="new", content="Replacement")]), mode="replace")
    assert error.value.committed is True
    assert [memory.id for memory in store.list()] == ["new"]
    assert [memory.id for memory in reopen(store).list()] == ["new"]
    store.add(Memory(content="Lock released"))


def test_custom_backend_fails_before_any_import_mutation():
    class LegacyStore:
        def __init__(self):
            self.backend = InMemoryStorage()

        def __getattr__(self, name):
            if name == "transaction":
                raise AttributeError(name)
            return getattr(self.backend, name)

    store = LegacyStore()
    store.add(Memory(id="old", content="Original"))
    for mode in ["replace", "append", "overwrite", "skip_existing"]:
        with pytest.raises(TypeError, match="atomic"):
            import_memories_from_payload(store, payload([Memory(content="Replacement")]), mode=mode)
        assert [memory.id for memory in store.list()] == ["old"]
    client = MemoryClient(storage=store)
    with pytest.raises(TypeError, match="atomic"):
        client.compact()
    assert [memory.id for memory in store.list()] == ["old"]


@pytest.mark.parametrize("collisions", ["memory", "session", "both", "none"])
def test_import_remaps_relationships_together(store, monkeypatch, collisions):
    if collisions in {"memory", "both"}:
        store.add(Memory(id="a", content="Existing"))
    if collisions in {"session", "both"}:
        store.add_session(Session(id="session", title="Existing"))
    generated = iter(["new-a", "new-session"])
    monkeypatch.setattr("mneno.io.importers.uuid4", lambda: next(generated))
    a = Memory(
        id="a",
        content="Evidence A",
        session_id="session",
        status=MemoryStatus.CONFLICTED,
        conflicts_with=["b", "a"],
        superseded_by="b",
        metadata={"dataset_id": "a"},
        audit=[MemoryAuditEvent(event_type="conflict", reason="Evidence", related_memory_ids=["b"])],
    )
    b = Memory(id="b", content="Evidence B", session_id="session", conflicts_with=["a"])
    result = import_memories_from_payload(
        store, payload([a, b], [Session(id="session", title="Import", memory_ids=["a", "b"])])
    )
    assert result.imported_count == 2
    assert not result.warnings
    imported = next(memory for memory in reopen(store).list() if memory.content == "Evidence A")
    linked = store.get("b")
    imported_session = store.get_session(imported.session_id)
    assert set(imported_session.memory_ids) == {imported.id, linked.id}
    assert linked.session_id == imported_session.id
    assert imported.conflicts_with == [linked.id, imported.id]
    assert linked.conflicts_with == [imported.id]
    assert imported.superseded_by == linked.id
    assert imported.audit[0].related_memory_ids == [linked.id]
    assert imported.metadata["dataset_id"] == "a"


def test_repeated_imports_and_compaction_lineage_remapping(store):
    first = Memory(id="a", content="Original")
    second = Memory(
        id="b", content="Summary", source="compaction", metadata={"source_memory_ids": ["a"], "external_id": "a"}
    )
    exported = payload([first, second])
    for _ in range(3):
        import_memories_from_payload(store, exported)
    memories = reopen(store).list()
    assert len(memories) == 6
    originals = {memory.id for memory in memories if memory.content == "Original"}
    summaries = [memory for memory in memories if memory.content == "Summary"]
    assert {memory.metadata["source_memory_ids"][0] for memory in summaries} == originals
    assert all(memory.metadata["external_id"] == "a" for memory in summaries)


@pytest.mark.parametrize("kind", ["memory", "session"])
def test_duplicate_incoming_ids_rejected_without_mutation(store, kind):
    store.add(Memory(content="Original"))
    before = snapshot(store)
    memory = Memory(id="duplicate", content="Evidence")
    session = Session(id="duplicate", title="Evidence")
    exported = payload(
        [memory, memory] if kind == "memory" else [memory], [session, session] if kind == "session" else []
    )
    with pytest.raises(ValueError, match="Duplicate"):
        import_memories_from_payload(store, exported)
    assert snapshot(reopen(store)) == before


def test_dangling_historical_links_preserved_with_warning(store):
    memory = Memory(content="Legacy evidence", conflicts_with=["external-missing"], session_id="missing-session")
    result = import_memories_from_payload(store, payload([memory]))
    assert result.imported_count == 1
    assert len(result.warnings) == 2
    assert reopen(store).get(memory.id) == memory


def test_reference_to_existing_session_is_reconciled(store):
    store.add_session(Session(id="session", title="Existing"))
    memory = Memory(id="new", content="Imported", session_id="session")
    import_memories_from_payload(store, payload([memory]))
    assert reopen(store).get_session("session").memory_ids == [memory.id]


def test_inconsistent_known_session_membership_rolls_back(store):
    store.add(Memory(content="Original"))
    before = snapshot(store)
    memory = Memory(id="new", content="Import", session_id="one")
    with pytest.raises(ValueError, match="Inconsistent session"):
        import_memories_from_payload(store, payload([memory], [Session(id="two", title="Wrong", memory_ids=["new"])]))
    assert snapshot(reopen(store)) == before


def test_import_late_storage_failure_rolls_back_all_records(store, monkeypatch):
    store.add(Memory(content="Original"))
    before = snapshot(store)

    def fail(self, session):
        raise OSError("session insertion failed")

    monkeypatch.setattr(InMemoryStorage, "add_session", fail)
    with pytest.raises(OSError):
        import_memories_from_payload(store, payload([Memory(content="New")], [Session(title="New")]))
    assert snapshot(reopen(store)) == before


def test_compaction_history_sessions_visibility_and_repeat(store):
    client = MemoryClient(storage=store, auto_detect_conflicts=False)
    session = client.create_session(title="History")
    old_a = client.add("Python memory", source="file-a", session_id=session.id, metadata={"evidence": "A"})
    old_b = client.add("Python memory", source="file-b", session_id=session.id, metadata={"evidence": "B"})
    store.update(
        old_a.model_copy(
            update={
                "audit": [
                    MemoryAuditEvent(
                        event_type="original_event", reason="Historical evidence", related_memory_ids=[old_b.id]
                    )
                ],
                "promotion_count": 2,
                "demotion_count": 1,
                "last_promoted_at": datetime(2025, 1, 1),
            }
        )
    )
    before = {memory.id: memory for memory in client.list()}
    diff = client.compact()
    assert (diff.stats.before_count, diff.stats.after_count) == (2, 1)
    reopened = reopen(store)
    result = reopened.get(diff.created[0].id)
    assert result == diff.created[0]
    assert set(result.metadata["source_memory_ids"]) == {old_a.id, old_b.id}
    assert result.audit[-1].event_type == "compaction_created"
    assert set(result.audit[-1].related_memory_ids) == {old_a.id, old_b.id}
    assert result.session_id == session.id
    assert set(reopened.get_session(session.id).memory_ids) == {old_a.id, old_b.id, result.id}
    for identifier in [old_a.id, old_b.id]:
        source = reopened.get(identifier)
        assert source.status is MemoryStatus.ARCHIVED
        assert source.content == before[identifier].content
        assert source.source == before[identifier].source
        assert source.metadata == before[identifier].metadata
        assert source.session_id == session.id
        assert source.audit[:-1] == before[identifier].audit
        assert source.promotion_count == before[identifier].promotion_count
        assert source.demotion_count == before[identifier].demotion_count
        assert source.last_promoted_at == before[identifier].last_promoted_at
        assert source.audit[-1].metadata["previous_updated_at"] == before[identifier].updated_at.isoformat()
        assert source.audit[-1].related_memory_ids == [result.id]
        assert "policy" in source.audit[-1].metadata
        assert source.superseded_by is None
    client = MemoryClient(storage=reopened, auto_detect_conflicts=False)
    assert [item.memory.id for item in client.search("Python")] == [result.id]
    assert [item.memory_id for item in client.build_context("Python").included] == [result.id]
    assert len(client.build_timeline(session_ids=[session.id]).events) == 3
    repeated = client.compact()
    assert not repeated.created and not repeated.discarded and not repeated.merged
    assert len(client.list()) == 3


@pytest.mark.parametrize("failure_at", [1, 3])
def test_compaction_multiple_groups_transition_failure_rolls_back(store, monkeypatch, failure_at):
    client = MemoryClient(storage=store, auto_detect_conflicts=False, trace_enabled=True)
    for content in ["Python note", "Python note", "Garden plants", "Garden plants"]:
        client.add(content)
    before = snapshot(store)
    update = InMemoryStorage.update
    calls = 0

    def fail(self, memory):
        nonlocal calls
        calls += 1
        if calls == failure_at:
            raise OSError("transition failed")
        return update(self, memory)

    monkeypatch.setattr(InMemoryStorage, "update", fail)
    with pytest.raises(OSError):
        client.compact()
    assert snapshot(reopen(store)) == before
    trace = client.get_trace(client.last_trace_id)
    assert trace.status == "error"
    assert not any(event.event_type == "compaction_committed" for event in trace.events)


def test_compaction_multiple_groups_success_and_discard_history(store):
    client = MemoryClient(storage=store, auto_detect_conflicts=False)
    for content in ["Python note", "Python note", "Garden plants", "Garden plants"]:
        client.add(content)
    lone = client.add("Single unique low importance", importance=0)
    diff = client.compact(CompactionPolicy(min_score_to_keep=1, max_memories=2))
    assert len(diff.created) == 2
    assert lone.id in {decision.memory_id for decision in diff.discarded}
    assert len(reopen(store).list()) == 7
    assert reopen(store).get(lone.id).audit[-1].event_type == "compaction_archived"
    assert reopen(store).get(lone.id).audit[-1].related_memory_ids == []


def test_compaction_protects_one_sided_conflict_evidence(store):
    store.add(Memory(id="a", content="Python", conflicts_with=["b"], status=MemoryStatus.CONFLICTED))
    store.add(Memory(id="b", content="Python"))
    diff = MemoryClient(storage=store).compact(CompactionPolicy(min_score_to_keep=1, max_memories=1))
    assert not diff.created and not diff.discarded
    assert reopen(store).get("b").status is MemoryStatus.ACTIVE


def test_json_independent_stale_writers_reject_and_retry(tmp_path):
    first = JSONFileStorage(tmp_path / "records.json")
    second = JSONFileStorage(first.path)
    original = first.add(Memory(id="a", content="Writer A"))
    with pytest.raises(StorageConflictError):
        second.add(Memory(id="b", content="Writer B"))
    assert reopen(first).get(original.id) == original
    assert {memory.id for memory in second.list()} == {"a"}
    second.add(Memory(id="b", content="Writer B"))
    assert {memory.id for memory in reopen(first).list()} == {"a", "b"}


def test_json_stale_session_update_rejected(tmp_path):
    first = JSONFileStorage(tmp_path / "records.json")
    session = first.add_session(Session(id="session", title="Original"))
    second = JSONFileStorage(first.path)
    first.update_session(session.model_copy(update={"summary": "Committed update"}))
    with pytest.raises(StorageConflictError):
        second.update_session(session.model_copy(update={"summary": "Stale update"}))
    assert second.get_session(session.id).summary == "Committed update"


def test_json_simultaneous_threads_from_same_snapshot(tmp_path):
    path = tmp_path / "records.json"
    barrier = Barrier(2)

    def write(identifier):
        storage = JSONFileStorage(path)
        barrier.wait(timeout=10)
        try:
            storage.add(Memory(id=identifier, content=identifier))
            return "committed"
        except StorageConflictError:
            return "conflict"

    with ThreadPoolExecutor(max_workers=2) as workers:
        results = list(workers.map(write, ["a", "b"]))
    assert sorted(results) == ["committed", "conflict"]
    assert len(JSONFileStorage(path).list()) == 1
    json.loads(path.read_text())


def _json_process_writer(path, identifier, barrier, results):
    try:
        storage = JSONFileStorage(path)
        conflicts = 0
        for index in range(8):
            storage.list()
            barrier.wait(timeout=15)
            for _ in range(20):
                try:
                    with storage.transaction() as staged:
                        memory_id = f"{identifier}-{index}"
                        session_id = f"session-{identifier}-{index}"
                        staged.add(Memory(id=memory_id, content=memory_id, session_id=session_id))
                        staged.add_session(Session(id=session_id, title=session_id, memory_ids=[memory_id]))
                    break
                except StorageConflictError:
                    conflicts += 1
                    storage.list()
            else:
                raise AssertionError("Retry budget exhausted")
            barrier.wait(timeout=15)
        results.put((identifier, "success", conflicts))
    except Exception as error:
        results.put((identifier, type(error).__name__, str(error)))


def test_json_repeated_multiprocess_writes_preserve_memories_and_sessions(tmp_path):
    context = multiprocessing.get_context("spawn")
    barrier = context.Barrier(2)
    results = context.Queue()
    path = tmp_path / "records.json"
    processes = [
        context.Process(target=_json_process_writer, args=(path, identifier, barrier, results))
        for identifier in ["a", "b"]
    ]
    try:
        for process in processes:
            process.start()
        for process in processes:
            process.join(timeout=30)
        assert all(process.exitcode == 0 for process in processes)
        messages = [results.get(timeout=5) for _ in processes]
        assert all(message[1] == "success" for message in messages), messages
        assert sum(message[2] for message in messages) >= 8
        storage = JSONFileStorage(path)
        assert len(storage.list()) == 16
        assert len(storage.list_sessions()) == 16
        for memory in storage.list():
            assert storage.get_session(memory.session_id).memory_ids == [memory.id]
        assert len(json.loads(path.read_text())["memories"]) == 16
        assert not list(tmp_path.glob("*.tmp"))
    finally:
        for process in processes:
            if process.is_alive():
                process.terminate()
                process.join(timeout=5)
        results.close()
        results.join_thread()


def test_json_same_instance_reentrancy_rejected_without_deadlock(tmp_path):
    store = JSONFileStorage(tmp_path / "records.json")
    with store.transaction() as staged:
        staged.add(Memory(content="Staged"))
        with pytest.raises(RuntimeError, match="staged"):
            store.list()
    assert len(store.list()) == 1


def mixed_memories():
    instants = [
        datetime(2025, 1, 1),
        datetime(2025, 1, 1, tzinfo=UTC),
        datetime(2025, 1, 1, 3, tzinfo=timezone(timedelta(hours=3))),
        datetime(2024, 12, 31, 19, tzinfo=timezone(timedelta(hours=-5))),
    ]
    return [
        Memory(id=identifier, content="Python note", created_at=instant, updated_at=instant, last_accessed_at=instant)
        for identifier, instant in zip(["a", "b", "c", "d"], instants, strict=True)
    ]


def test_timezone_equal_instants_search_context_timeline_and_reopen(store):
    originals = mixed_memories()
    for memory in originals:
        store.add(memory)
    store = reopen(store)
    for original in originals:
        assert store.get(original.id).created_at.isoformat() == original.created_at.isoformat()
    client = MemoryClient(storage=store, scorer=TemporalMemoryScorer(reference_time=datetime(2026, 1, 1, tzinfo=UTC)))
    assert [item.memory.id for item in client.search("Python")] == ["d", "c", "b", "a"]
    for memory in originals:
        store.update(memory)
    from mneno.context import ContextPolicy

    assert [
        item.memory_id
        for item in client.build_context("Python", policy=ContextPolicy(max_tokens=100, dedupe=False)).included
    ] == ["d", "c", "b", "a"]
    timeline = TimelineBuilder().build(originals)
    assert [event.memory_id for event in timeline.events] == ["a", "b", "c", "d"]
    assert [event.timestamp.isoformat() for event in timeline.events] == [
        memory.created_at.isoformat() for memory in originals
    ]


def test_timezone_compaction_ordering_and_serialized_history(store):
    for memory in mixed_memories():
        store.add(memory)
    diff = MemoryClient(storage=reopen(store), auto_detect_conflicts=False).compact()
    assert len(diff.created) == 1
    result = reopen(store).get(diff.created[0].id)
    assert as_utc(result.created_at) == datetime(2025, 1, 1, tzinfo=UTC)
    assert as_utc(result.last_accessed_at) == datetime(2025, 1, 1, tzinfo=UTC)
    for memory in mixed_memories():
        assert reopen(store).get(memory.id).created_at.isoformat() == memory.created_at.isoformat()


def test_timezone_semantic_and_session_ordering():
    from mneno.providers import DummyEmbeddingProvider
    from mneno.retrieval.semantic import SemanticRetriever
    from mneno.sessions import ContinuityManager, SessionManager

    memories = [memory.model_copy(update={"session_id": "session"}) for memory in mixed_memories()]
    assert [result.memory.id for result in SemanticRetriever(DummyEmbeddingProvider()).rank("Python", memories)] == [
        "d",
        "c",
        "b",
        "a",
    ]
    session = Session(id="session", title="Python", memory_ids=[memory.id for memory in memories])
    assert [memory.id for memory in SessionManager().list_session_memories(session, memories)] == ["a", "b", "c", "d"]
    other = session.model_copy(update={"id": "other", "updated_at": datetime(2025, 1, 1)})
    session = session.model_copy(update={"updated_at": datetime(2025, 1, 1, tzinfo=UTC)})
    related = ContinuityManager().find_related("Python", sessions=[other, session], memories=memories)
    assert [item.id for item in related.related_sessions] == ["session", "other"]


@pytest.mark.parametrize("value", ["not-a-date", "2025-99-99"])
def test_malformed_timestamp_import_preserves_committed_state(store, value):
    store.add(Memory(content="Original"))
    before = snapshot(store)
    exported = payload([Memory(content="New")])
    exported["memories"][0]["created_at"] = value
    with pytest.raises(ValueError):
        import_memories_from_payload(store, exported, mode="replace")
    assert snapshot(reopen(store)) == before


def test_legacy_json_timestamps_load_without_migration(tmp_path):
    path = tmp_path / "legacy.json"
    path.write_text(
        json.dumps(
            {
                "version": 1,
                "memories": [
                    {
                        "id": "legacy",
                        "content": "Python",
                        "created_at": "2025-01-01T00:00:00",
                        "updated_at": "2025-01-01T00:00:00+02:00",
                    }
                ],
            }
        )
    )
    store = JSONFileStorage(path)
    before = path.read_bytes()
    result = MemoryClient(storage=store).search("Python")[0]
    assert result.memory.id == "legacy"
    assert store.get("legacy").created_at.tzinfo is None
    assert json.loads(path.read_text())["version"] == 1
    assert before != path.read_bytes()  # Access metadata changed, not the envelope or timestamp convention.


def test_memory_original_mutations_and_nested_transaction_rejected():
    store = InMemoryStorage()
    store.add(Memory(id="old", content="Original"))
    with store.transaction() as staged:
        with pytest.raises(RuntimeError, match="staged"):
            store.clear()
        with pytest.raises(RuntimeError, match="staged"), store.transaction():
            pass
        assert store.get("old") is not None
        staged.add(Memory(id="new", content="New"))
    assert {memory.id for memory in store.list()} == {"old", "new"}


def test_compaction_commit_failure_preserves_sources_and_sessions(store, monkeypatch):
    client = MemoryClient(storage=store, auto_detect_conflicts=False, trace_enabled=True)
    session = client.create_session(title="Evidence")
    client.add("Python", session_id=session.id)
    client.add("Python", session_id=session.id)
    before = snapshot(store)
    with monkeypatch.context() as patch:
        if isinstance(store, JSONFileStorage):

            def fail(*args, **kwargs):
                raise OSError("commit failed")

            patch.setattr(Path, "replace", fail)
        elif isinstance(store, SQLiteStorage):

            def fail(connection, staged):
                connection.execute("DELETE FROM memories")
                connection.execute("DELETE FROM sessions")
                raise OSError("commit failed")

            patch.setattr(store, "_replace_snapshot", fail)
        else:

            def fail(self):
                raise OSError("commit failed")

            patch.setattr(InMemoryStorage, "_validated_snapshot", fail)
        with pytest.raises(OSError):
            client.compact()
    assert snapshot(reopen(store)) == before
    trace = client.get_trace(client.last_trace_id)
    assert trace.status == "error"
    assert not any(event.event_type == "compaction_committed" for event in trace.events)


def test_compaction_across_sessions_keeps_history(store):
    client = MemoryClient(storage=store, auto_detect_conflicts=False)
    first = client.create_session(title="First")
    second = client.create_session(title="Second")
    a = client.add("Python", session_id=first.id)
    b = client.add("Python", session_id=second.id)
    diff = client.compact()
    assert diff.created[0].session_id is None
    assert reopen(store).get_session(first.id).memory_ids == [a.id]
    assert reopen(store).get_session(second.id).memory_ids == [b.id]
    assert {memory.id for memory in client.list()} == {a.id, b.id, diff.created[0].id}


def test_json_symlink_paths_share_writer_lock_and_revision(tmp_path):
    path = tmp_path / "records.json"
    first = JSONFileStorage(path)
    alias = tmp_path / "alias.json"
    try:
        alias.symlink_to(path)
    except OSError:
        pytest.skip("Symlinks unavailable on this platform")
    second = JSONFileStorage(alias)
    assert first.path == second.path
    first.add(Memory(content="Committed"))
    with pytest.raises(StorageConflictError):
        second.add(Memory(content="Stale"))
    assert len(second.list()) == 1


def _json_crash_before_commit(path):
    storage = JSONFileStorage(path)
    with storage.transaction() as staged:
        staged.clear()
        staged.add(Memory(content="Never committed"))
        os._exit(23)


def test_json_process_exit_releases_lock_and_retains_snapshot(tmp_path):
    store = JSONFileStorage(tmp_path / "records.json")
    original = store.add(Memory(content="Original"))
    process = multiprocessing.get_context("spawn").Process(target=_json_crash_before_commit, args=(store.path,))
    process.start()
    try:
        process.join(timeout=15)
        assert process.exitcode == 23
        assert reopen(store).get(original.id) == original
        store.add(Memory(content="Writer after crash"))
        assert len(reopen(store).list()) == 2
    finally:
        if process.is_alive():
            process.terminate()
            process.join(timeout=5)


def test_json_partial_temporary_write_does_not_replace_committed_snapshot(tmp_path, monkeypatch):
    import tempfile

    store = JSONFileStorage(tmp_path / "records.json")
    store.add(Memory(content="Original"))
    before = store.path.read_bytes()
    create = tempfile.NamedTemporaryFile

    class PartialWrite:
        def __init__(self, *args, **kwargs):
            self.output = create(*args, **kwargs)

        def __enter__(self):
            return self

        def __exit__(self, *args):
            self.output.close()

        @property
        def name(self):
            return self.output.name

        def write(self, text):
            self.output.write(text[: len(text) // 2])
            self.output.flush()
            raise OSError("partial temporary write")

    with monkeypatch.context() as patch:
        patch.setattr(tempfile, "NamedTemporaryFile", PartialWrite)
        with pytest.raises(OSError, match="partial"):
            store.add(Memory(content="Uncommitted"))
    assert store.path.read_bytes() == before
    assert len(reopen(store).list()) == 1
    assert not list(tmp_path.glob("*.tmp"))
    store.add(Memory(content="Retry"))


def test_compaction_result_sequence_follows_entire_session(store):
    client = MemoryClient(storage=store, auto_detect_conflicts=False)
    session = client.create_session(title="History")
    client.add("Python", session_id=session.id)
    client.add("Python", session_id=session.id)
    separate = client.add("Unique operational constraint", memory_type="operational", session_id=session.id)
    diff = client.compact()
    assert diff.created[0].sequence_index == separate.sequence_index + 1
    assert len({memory.sequence_index for memory in client.list_session_memories(session.id)}) == 4


def test_import_malformed_lineage_rolls_back(store):
    store.add(Memory(content="Original"))
    before = snapshot(store)
    malformed = Memory(content="Summary", source="compaction", metadata={"source_memory_ids": [{}]})
    with pytest.raises(ValueError, match="lineage"):
        import_memories_from_payload(store, payload([malformed]))
    assert snapshot(reopen(store)) == before


def test_authoritative_version_matches_installed_sdk_and_cli():
    import tomllib
    from importlib.metadata import version

    from typer.testing import CliRunner

    from mneno.cli.app import app
    from mneno.cli.version import get_version

    expected = tomllib.loads((Path(__file__).resolve().parents[1] / "pyproject.toml").read_text())["project"]["version"]
    assert version("mneno") == get_version() == expected
    result = CliRunner().invoke(app, ["--version"])
    assert result.exit_code == 0
    assert expected in result.stdout


@pytest.mark.skipif(os.name == "nt", reason="Directory fsync is POSIX-specific")
def test_compaction_postcommit_sync_failure_trace_reports_actual_commit(tmp_path, monkeypatch):
    store = JSONFileStorage(tmp_path / "records.json")
    client = MemoryClient(storage=store, trace_enabled=True, auto_detect_conflicts=False)
    first = client.add("Python")
    second = client.add("Python")
    fsync = os.fsync
    count = 0

    def fail(fd):
        nonlocal count
        count += 1
        if count == 2:
            raise OSError("directory synchronization failed")
        fsync(fd)

    with monkeypatch.context() as patch:
        patch.setattr(os, "fsync", fail)
        with pytest.raises(StorageCommitError):
            client.compact()
    trace = client.get_trace(client.last_trace_id)
    event = next(event for event in trace.events if event.event_type == "operation_failed")
    assert event.data["committed"] is True
    assert set(event.data["source_ids"]) == {first.id, second.id}
    assert len(event.data["created_ids"]) == 1
    assert store.get(event.data["created_ids"][0]) is not None
    assert store.get(first.id).status is MemoryStatus.ARCHIVED
    assert trace.status == "error"
    json.dumps(client.export_trace(trace.id))


@pytest.mark.parametrize("command,method", [("search", "search"), ("context", "build_context")])
def test_cli_json_concurrency_error_remains_parseable(tmp_path, monkeypatch, command, method):
    from typer.testing import CliRunner

    from mneno.cli.app import app

    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    assert runner.invoke(app, ["init"]).exit_code == 0

    def fail(*args, **kwargs):
        raise StorageConflictError("JSON snapshot changed; refresh and retry")

    monkeypatch.setattr(MemoryClient, method, fail)
    result = runner.invoke(app, [command, "Python", "--json"])
    assert result.exit_code == 1
    assert "snapshot changed" in json.loads(result.stdout)["error"]


def test_import_nullable_references_do_not_discard_supported_empty_ids(store):
    memory = Memory(id="", content="Legacy empty ID", session_id="", conflicts_with=[""], superseded_by="")
    session = Session(id="", title="Legacy session", memory_ids=[""])
    store.add(memory)
    store.add_session(session)
    result = import_memories_from_payload(store, payload([memory], [session]))
    assert not result.warnings
    copied = next(item for item in reopen(store).list() if item.id != "")
    copied_session = store.get_session(copied.session_id)
    assert copied.session_id != ""
    assert copied_session.memory_ids == [copied.id]
    assert copied.conflicts_with == [copied.id]
    assert copied.superseded_by == copied.id


@pytest.mark.skipif(os.name == "nt", reason="Directory descriptor cleanup is POSIX-specific")
def test_json_postcommit_directory_close_failure_reports_commit(tmp_path, monkeypatch):
    store = JSONFileStorage(tmp_path / "records.json")
    store.add(Memory(id="old", content="Original"))
    close = os.close

    def fail(fd):
        close(fd)
        raise OSError("directory close failed")

    with monkeypatch.context() as patch:
        patch.setattr(os, "close", fail)
        with pytest.raises(StorageCommitError) as error:
            import_memories_from_payload(store, payload([Memory(id="new", content="New")]), mode="replace")
    assert error.value.committed is True
    assert [memory.id for memory in store.list()] == ["new"]
    assert [memory.id for memory in reopen(store).list()] == ["new"]


def test_datetime_range_boundaries_remain_comparable_and_readable(store):
    instants = [
        datetime(1, 1, 1, tzinfo=timezone(timedelta(hours=2))),
        datetime(1, 1, 1, 1, tzinfo=timezone(timedelta(hours=3))),
        datetime(9999, 12, 31, 23, tzinfo=timezone(timedelta(hours=-2))),
        datetime(9999, 12, 31, 22, tzinfo=timezone(timedelta(hours=-3))),
    ]
    for identifier, instant in zip(["a", "b", "c", "d"], instants, strict=True):
        store.add(Memory(id=identifier, content="Python", created_at=instant, updated_at=instant))
    client = MemoryClient(
        storage=reopen(store), scorer=TemporalMemoryScorer(reference_time=datetime(2026, 1, 1, tzinfo=UTC))
    )
    assert [item.memory.id for item in client.search("Python")] == ["d", "c", "b", "a"]
    assert [event.memory_id for event in client.build_timeline().events] == ["a", "b", "c", "d"]
    for identifier, instant in zip(["a", "b", "c", "d"], instants, strict=True):
        assert reopen(store).get(identifier).created_at.isoformat() == instant.isoformat()
