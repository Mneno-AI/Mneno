from pathlib import Path

from pytest import raises

from mneno import MemoryClient
from mneno.models import Memory, MemoryAuditEvent, MemoryLayer, MemoryStatus, MemoryType, utc_now
from mneno.storage import InMemoryStorage, JSONFileStorage, SQLiteStorage


def make_memory() -> Memory:
    return Memory(
        content="User prefers Python.",
        memory_type=MemoryType.PREFERENCE,
        metadata={"source": "test"},
        importance=0.9,
        access_count=2,
        last_accessed_at=utc_now(),
        source="unit-test",
        tags=["Python", "Preference"],
        status=MemoryStatus.CONFLICTED,
        conflicts_with=["other-memory"],
        layer=MemoryLayer.WORKING,
        promotion_count=1,
        retention_score=0.9,
        audit=[
            MemoryAuditEvent(
                event_type="conflicted",
                reason="Test conflict",
                related_memory_ids=["other-memory"],
                metadata={"conflict_id": "conflict-1"},
            )
        ],
    )


def assert_memory_preserved(memory: Memory, loaded: Memory) -> None:
    assert loaded.id == memory.id
    assert loaded.content == memory.content
    assert loaded.memory_type is memory.memory_type
    assert loaded.metadata == memory.metadata
    assert loaded.created_at == memory.created_at
    assert loaded.updated_at == memory.updated_at
    assert loaded.importance == memory.importance
    assert loaded.access_count == memory.access_count
    assert loaded.last_accessed_at == memory.last_accessed_at
    assert loaded.source == memory.source
    assert loaded.tags == ["python", "preference"]
    assert loaded.status is memory.status
    assert loaded.superseded_by == memory.superseded_by
    assert loaded.conflicts_with == memory.conflicts_with
    assert loaded.audit == memory.audit
    assert loaded.layer is memory.layer
    assert loaded.promotion_count == memory.promotion_count
    assert loaded.demotion_count == memory.demotion_count
    assert loaded.retention_score == memory.retention_score


def test_in_memory_storage_alias_still_works() -> None:
    storage = InMemoryStorage()
    memory = storage.add(make_memory())

    assert storage.get(memory.id) == memory


def test_json_storage_starts_empty_if_file_does_not_exist(tmp_path: Path) -> None:
    storage = JSONFileStorage(tmp_path / "missing" / "memories.json")

    assert storage.list() == []


def test_json_storage_creates_file_on_add_and_persists_across_instances(tmp_path: Path) -> None:
    path = tmp_path / "memories.json"
    storage = JSONFileStorage(path)
    memory = storage.add(make_memory())

    assert path.exists()
    loaded = JSONFileStorage(path).get(memory.id)

    assert loaded is not None
    assert_memory_preserved(memory, loaded)


def test_json_storage_get_list_update_delete_and_clear(tmp_path: Path) -> None:
    storage = JSONFileStorage(tmp_path / "memories.json")
    memory = storage.add(make_memory())
    updated = memory.model_copy(update={"content": "User strongly prefers Python."})

    assert storage.get(memory.id) == memory
    assert storage.list() == [memory]
    assert storage.update(updated) == updated
    assert storage.get(memory.id) == updated
    assert storage.delete(memory.id) is True
    assert storage.delete(memory.id) is False
    assert storage.list() == []

    storage.add(make_memory())
    storage.clear()

    assert storage.list() == []


def test_json_storage_invalid_json_raises_value_error(tmp_path: Path) -> None:
    path = tmp_path / "memories.json"
    path.write_text("{invalid", encoding="utf-8")

    with raises(ValueError, match="Invalid JSON storage file"):
        JSONFileStorage(path)


def test_json_storage_empty_file_is_safe(tmp_path: Path) -> None:
    path = tmp_path / "memories.json"
    path.write_text("", encoding="utf-8")

    storage = JSONFileStorage(path)

    assert storage.list() == []


def test_json_storage_parent_directory_created_automatically(tmp_path: Path) -> None:
    path = tmp_path / "nested" / "data" / "memories.json"
    storage = JSONFileStorage(path)
    storage.add(make_memory())

    assert path.exists()


def test_json_storage_duplicate_id_raises_value_error(tmp_path: Path) -> None:
    storage = JSONFileStorage(tmp_path / "memories.json")
    memory = storage.add(make_memory())

    with raises(ValueError, match="Memory already exists"):
        storage.add(memory)


def test_sqlite_storage_creates_db_automatically(tmp_path: Path) -> None:
    path = tmp_path / "mneno.db"
    storage = SQLiteStorage(path)

    assert path.exists()
    assert storage.list() == []


def test_sqlite_storage_persists_across_instances(tmp_path: Path) -> None:
    path = tmp_path / "mneno.db"
    memory = SQLiteStorage(path).add(make_memory())
    loaded = SQLiteStorage(path).get(memory.id)

    assert loaded is not None
    assert_memory_preserved(memory, loaded)


def test_sqlite_storage_get_list_update_delete_and_clear(tmp_path: Path) -> None:
    storage = SQLiteStorage(tmp_path / "mneno.db")
    memory = storage.add(make_memory())
    updated = memory.model_copy(update={"content": "User strongly prefers Python."})

    assert storage.get(memory.id) == memory
    assert storage.list() == [memory]
    assert storage.update(updated) == updated
    assert storage.get(memory.id) == updated
    assert storage.delete(memory.id) is True
    assert storage.delete(memory.id) is False
    assert storage.list() == []

    storage.add(make_memory())
    storage.clear()

    assert storage.list() == []


def test_sqlite_storage_multiple_memories_work(tmp_path: Path) -> None:
    storage = SQLiteStorage(tmp_path / "mneno.db")
    first = storage.add(Memory(content="First memory."))
    second = storage.add(Memory(content="Second memory."))

    assert [memory.id for memory in storage.list()] == [first.id, second.id]


def test_sqlite_storage_duplicate_id_raises_value_error(tmp_path: Path) -> None:
    storage = SQLiteStorage(tmp_path / "mneno.db")
    memory = storage.add(make_memory())

    with raises(ValueError, match="Memory already exists"):
        storage.add(memory)


def test_memory_client_with_json_storage_can_add_search_and_build_context(tmp_path: Path) -> None:
    client = MemoryClient(storage=JSONFileStorage(tmp_path / "memories.json"))
    memory = client.add("User prefers Python.", importance=0.9)

    assert client.search("Python")[0].memory.id == memory.id
    assert client.build_context("Python").included[0].memory_id == memory.id


def test_memory_client_with_sqlite_storage_can_add_search_and_build_context(tmp_path: Path) -> None:
    client = MemoryClient(storage=SQLiteStorage(tmp_path / "mneno.db"))
    memory = client.add("User prefers Python.", importance=0.9)

    assert client.search("Python")[0].memory.id == memory.id
    assert client.build_context("Python").included[0].memory_id == memory.id


def test_compaction_works_with_json_storage(tmp_path: Path) -> None:
    client = MemoryClient(storage=JSONFileStorage(tmp_path / "memories.json"))
    client.add("User prefers Python.", memory_type="preference", importance=0.9)
    client.add("User prefers Python.", memory_type="semantic", importance=0.7)

    diff = client.compact()

    assert diff.created
    assert len(client.list()) == 1


def test_compaction_works_with_sqlite_storage(tmp_path: Path) -> None:
    client = MemoryClient(storage=SQLiteStorage(tmp_path / "mneno.db"))
    client.add("User prefers Python.", memory_type="preference", importance=0.9)
    client.add("User prefers Python.", memory_type="semantic", importance=0.7)

    diff = client.compact()

    assert diff.created
    assert len(client.list()) == 1


def test_default_in_memory_client_behavior_still_works() -> None:
    client = MemoryClient()
    memory = client.add("User prefers Python.", importance=0.9)

    assert client.get(memory.id) == memory
    assert client.search("Python")


def test_memory_client_rejects_storage_and_store_together(tmp_path: Path) -> None:
    with raises(ValueError, match="Use either storage or store"):
        MemoryClient(storage=JSONFileStorage(tmp_path / "memories.json"), store=InMemoryStorage())
