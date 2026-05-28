from datetime import timedelta
from pathlib import Path

from mneno import MemoryClient, Session, TimelineBuilder
from mneno.models import Memory, MemoryLayer, utc_now
from mneno.sessions import ContinuityManager, SessionManager
from mneno.storage import JSONFileStorage, SQLiteStorage


def test_create_session() -> None:
    client = MemoryClient()

    session = client.create_session(title="Mneno benchmark platform work", tags=["Mneno"])

    assert session.id
    assert session.title == "Mneno benchmark platform work"
    assert session.tags == ["mneno"]
    assert session.status == "active"
    assert client.get_session(session.id) == session


def test_add_memories_to_session_assigns_sequence_order() -> None:
    client = MemoryClient()
    session = client.create_session(title="Session")

    first = client.add("First event.", session_id=session.id)
    second = client.add("Second event.", session_id=session.id)
    memories = client.list_session_memories(session.id)

    assert [memory.id for memory in memories] == [first.id, second.id]
    assert [memory.sequence_index for memory in memories] == [0, 1]
    stored_session = client.get_session(session.id)
    assert stored_session is not None
    assert stored_session.memory_ids == [first.id, second.id]


def test_attach_existing_memory_to_session() -> None:
    client = MemoryClient()
    memory = client.add("Existing memory.")
    session = client.create_session(title="Session")

    attached = client.add_memory_to_session(memory.id, session.id)

    assert attached.session_id == session.id
    assert attached.sequence_index == 0
    assert client.list_session_memories(session.id) == [attached]


def test_close_and_archive_session() -> None:
    client = MemoryClient()
    session = client.create_session(title="Session")
    client.add("Session memory.", session_id=session.id)

    closed = client.close_session(session.id)
    archived = client.archive_session(session.id)

    assert closed.status == "closed"
    assert closed.summary is not None
    assert archived.status == "archived"


def test_session_manager_summarizes_deterministically() -> None:
    manager = SessionManager()
    session = manager.create_session(title="Session")
    memories = [Memory(content="First deterministic memory.")]

    summary = manager.summarize_session(session, memories)

    assert summary == "Session: 1 memories. First memory: First deterministic memory."


def test_timeline_reconstructs_ordered_events() -> None:
    session = Session(title="Timeline session", id="session")
    later = Memory(
        id="later",
        content="Later event.",
        session_id=session.id,
        sequence_index=1,
        created_at=utc_now() + timedelta(seconds=1),
    )
    earlier = Memory(
        id="earlier",
        content="Earlier event.",
        session_id=session.id,
        sequence_index=0,
        created_at=utc_now(),
    )

    timeline = TimelineBuilder().build([later, earlier], session_ids=[session.id])

    assert [event.memory_id for event in timeline.events] == ["earlier", "later"]
    assert timeline.session_ids == [session.id]
    assert timeline.summary == "Timeline contains 2 events across 1 sessions."
    assert all(event.reason for event in timeline.events)


def test_timeline_supports_multi_session_ordering() -> None:
    first = Memory(id="a", content="A.", session_id="one", sequence_index=0, created_at=utc_now())
    second = Memory(
        id="b",
        content="B.",
        session_id="two",
        sequence_index=0,
        created_at=utc_now() + timedelta(seconds=1),
    )

    timeline = TimelineBuilder().build([second, first], session_ids=["one", "two"])

    assert [event.session_id for event in timeline.events] == ["one", "two"]
    assert timeline.session_ids == ["one", "two"]


def test_client_build_timeline() -> None:
    client = MemoryClient()
    session = client.create_session(title="Session")
    memory = client.add("Implemented Step 14 timeline support.", session_id=session.id)

    timeline = client.build_timeline(session_ids=[session.id])

    assert timeline.events[0].memory_id == memory.id
    assert timeline.events[0].content == "Implemented Step 14 timeline support."


def test_continuity_finds_related_sessions() -> None:
    client = MemoryClient()
    related = client.create_session(title="Mneno benchmark platform work", tags=["benchmark"], make_active=False)
    client.add("Benchmark UI work continued.", session_id=related.id)
    client.create_session(title="Unrelated billing task", make_active=False)

    result = client.find_related_sessions("benchmark UI")

    assert [session.id for session in result.related_sessions] == [related.id]
    assert result.relevant_memories
    assert result.continuity_reasons
    assert "related sessions" in result.continuity_summary


def test_continuity_skips_archived_sessions() -> None:
    client = MemoryClient()
    session = client.create_session(title="Mneno benchmark platform work")
    client.archive_session(session.id)

    result = client.find_related_sessions("benchmark")

    assert result.related_sessions == []


def test_active_session_memories_are_prioritized_in_search() -> None:
    client = MemoryClient()
    old_session = client.create_session(title="Old", make_active=False)
    active_session = client.create_session(title="Active", make_active=True)
    client.add("Python task note.", session_id=old_session.id, importance=0.2)
    active = client.add("Python active note.", session_id=active_session.id, importance=0.2)

    results = client.search("Python")

    assert results[0].memory.id == active.id
    assert any("active session" in reason for reason in results[0].score.reasons)


def test_context_mentions_active_session_continuity() -> None:
    client = MemoryClient()
    session = client.create_session(title="Active")
    memory = client.add("Benchmark UI state.", session_id=session.id)

    context = client.get_session_context(session.id, "Benchmark UI")

    assert context.included[0].memory_id == memory.id
    assert "active session" in context.included[0].reason


def test_add_from_text_attaches_extracted_memories_to_session() -> None:
    client = MemoryClient()
    session = client.create_session(title="Extraction")

    result = client.add_from_text("The user is building Mneno. They prefer Python 3.11.", session_id=session.id)
    memories = client.list_session_memories(session.id)

    assert result.extracted
    assert memories
    assert all(memory.session_id == session.id for memory in memories)
    assert [memory.sequence_index for memory in memories] == list(range(len(memories)))


def test_json_storage_preserves_sessions(tmp_path: Path) -> None:
    path = tmp_path / "memories.json"
    client = MemoryClient(storage=JSONFileStorage(path))
    session = client.create_session(title="Persistent session")
    memory = client.add("Stored memory.", session_id=session.id)

    loaded = JSONFileStorage(path)

    assert loaded.get_session(session.id) == client.get_session(session.id)
    stored_memory = loaded.get(memory.id)
    assert stored_memory is not None
    assert stored_memory.session_id == session.id


def test_sqlite_storage_preserves_sessions(tmp_path: Path) -> None:
    path = tmp_path / "mneno.db"
    client = MemoryClient(storage=SQLiteStorage(path))
    session = client.create_session(title="Persistent session")
    memory = client.add("Stored memory.", session_id=session.id)

    loaded = SQLiteStorage(path)

    assert loaded.get_session(session.id) == client.get_session(session.id)
    stored_memory = loaded.get(memory.id)
    assert stored_memory is not None
    assert stored_memory.session_id == session.id


def test_import_export_preserves_sessions(tmp_path: Path) -> None:
    client = MemoryClient()
    session = client.create_session(title="Exported session")
    memory = client.add("Exported memory.", session_id=session.id)
    export_path = tmp_path / "export.json"

    payload = client.export_json(export_path)
    restored = MemoryClient()
    restored.import_json(export_path)

    assert payload["session_count"] == 1
    assert restored.get_session(session.id) == client.get_session(session.id)
    loaded = restored.get(memory.id)
    assert loaded is not None
    assert loaded.session_id == session.id


def test_backup_restore_preserves_sessions(tmp_path: Path) -> None:
    client = MemoryClient()
    session = client.create_session(title="Backup session")
    memory = client.add("Backup memory.", session_id=session.id)
    backup_path = client.backup(tmp_path / "backup.json")

    restored = MemoryClient()
    restored.restore(backup_path)

    assert restored.get_session(session.id) == client.get_session(session.id)
    loaded = restored.get(memory.id)
    assert loaded is not None
    assert loaded.session_id == session.id


def test_archived_session_does_not_block_memory_retrieval() -> None:
    client = MemoryClient()
    session = client.create_session(title="Archived session")
    memory = client.add("Archived session memory.", session_id=session.id, layer=MemoryLayer.SEMANTIC)
    client.archive_session(session.id)

    results = client.search("Archived session memory")

    assert results[0].memory.id == memory.id


def test_continuity_manager_direct_use() -> None:
    manager = ContinuityManager()
    session = Session(id="session", title="Mneno timeline")
    memory = Memory(content="Timeline reconstruction.", session_id=session.id)

    result = manager.find_related("timeline", sessions=[session], memories=[memory])

    assert result.related_sessions == [session]
    assert result.relevant_memories == [memory]
