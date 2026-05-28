import json
from pathlib import Path

from pytest import MonkeyPatch, raises

from mneno import MemoryClient
from mneno.io import ImportResult, validate_export_payload, validate_storage_payload
from mneno.models import Memory, MemoryAuditEvent, MemoryLayer, MemoryStatus, MemoryType, utc_now
from mneno.storage import JSONFileStorage, SQLiteStorage


def make_memory() -> Memory:
    return Memory(
        content="User prefers Python.",
        memory_type=MemoryType.PREFERENCE,
        metadata={"source": "io-test"},
        importance=0.9,
        access_count=3,
        last_accessed_at=utc_now(),
        source="test",
        tags=["python", "preference"],
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


def write_export(path: Path, memories: list[Memory]) -> None:
    payload = MemoryClient(storage=None).export_json()
    payload["memory_count"] = len(memories)
    payload["memories"] = [memory.model_dump(mode="json") for memory in memories]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def assert_memory_preserved(expected: Memory, actual: Memory) -> None:
    assert actual.id == expected.id
    assert actual.content == expected.content
    assert actual.memory_type is expected.memory_type
    assert actual.metadata == expected.metadata
    assert actual.created_at == expected.created_at
    assert actual.updated_at == expected.updated_at
    assert actual.importance == expected.importance
    assert actual.access_count == expected.access_count
    assert actual.last_accessed_at == expected.last_accessed_at
    assert actual.source == expected.source
    assert actual.tags == expected.tags
    assert actual.status is expected.status
    assert actual.superseded_by == expected.superseded_by
    assert actual.conflicts_with == expected.conflicts_with
    assert actual.audit == expected.audit
    assert actual.layer is expected.layer
    assert actual.promotion_count == expected.promotion_count
    assert actual.demotion_count == expected.demotion_count
    assert actual.retention_score == expected.retention_score


def test_import_result_is_public() -> None:
    assert ImportResult().imported_count == 0


def test_export_json_returns_dict_when_no_path() -> None:
    client = MemoryClient()
    memory = client.add("User prefers Python.", importance=0.9)

    payload = client.export_json()

    assert payload["format"] == "mneno.memory_export"
    assert payload["version"] == 1
    assert payload["memory_count"] == 1
    assert payload["memories"][0]["id"] == memory.id
    assert payload["exported_at"]


def test_export_json_writes_file_and_creates_parent_directories(tmp_path: Path) -> None:
    client = MemoryClient()
    client.add("User prefers Python.", importance=0.9)
    path = tmp_path / "exports" / "memories.json"

    payload = client.export_json(path)
    written = json.loads(path.read_text(encoding="utf-8"))

    assert path.exists()
    assert written == payload


def test_export_json_preserves_all_memory_fields() -> None:
    client = MemoryClient()
    memory = make_memory()
    client.store.add(memory)

    payload = client.export_json()
    loaded = Memory.model_validate(payload["memories"][0])

    assert_memory_preserved(memory, loaded)


def test_export_empty_storage_works() -> None:
    payload = MemoryClient().export_json()

    assert payload["memory_count"] == 0
    assert payload["memories"] == []


def test_import_append_adds_memories_and_generates_new_id_for_conflict(tmp_path: Path) -> None:
    existing = make_memory()
    imported = existing.model_copy()
    path = tmp_path / "memories.json"
    write_export(path, [imported])
    client = MemoryClient()
    client.store.add(existing)

    result = client.import_json(path, mode="append")

    assert result.imported_count == 1
    assert len(client.list()) == 2
    assert len({memory.id for memory in client.list()}) == 2


def test_import_replace_clears_existing_storage(tmp_path: Path) -> None:
    imported = make_memory()
    path = tmp_path / "memories.json"
    write_export(path, [imported])
    client = MemoryClient()
    client.add("Old memory.")

    result = client.import_json(path, mode="replace")

    assert result.imported_count == 1
    assert client.list() == [imported]


def test_import_skip_existing_keeps_existing_memory(tmp_path: Path) -> None:
    existing = make_memory()
    path = tmp_path / "memories.json"
    write_export(path, [existing])
    client = MemoryClient()
    client.store.add(existing)

    result = client.import_json(path, mode="skip_existing")

    assert result.skipped_count == 1
    assert result.imported_count == 0
    assert client.list() == [existing]


def test_import_overwrite_replaces_existing_memory(tmp_path: Path) -> None:
    existing = make_memory()
    imported = existing.model_copy(update={"content": "User strongly prefers Python."})
    path = tmp_path / "memories.json"
    write_export(path, [imported])
    client = MemoryClient()
    client.store.add(existing)

    result = client.import_json(path, mode="overwrite")

    assert result.overwritten_count == 1
    loaded = client.get(existing.id)
    assert loaded is not None
    assert loaded.content == "User strongly prefers Python."


def test_import_invalid_format_raises_value_error(tmp_path: Path) -> None:
    path = tmp_path / "bad.json"
    path.write_text(json.dumps({"format": "other", "version": 1, "memories": []}), encoding="utf-8")

    with raises(ValueError, match="Unknown export format"):
        MemoryClient().import_json(path)


def test_import_unsupported_version_raises_value_error(tmp_path: Path) -> None:
    path = tmp_path / "bad.json"
    path.write_text(
        json.dumps({"format": "mneno.memory_export", "version": 999, "memories": []}),
        encoding="utf-8",
    )

    with raises(ValueError, match="Unsupported export version"):
        MemoryClient().import_json(path)


def test_import_partially_invalid_memories_reports_errors(tmp_path: Path) -> None:
    valid = make_memory()
    path = tmp_path / "mixed.json"
    write_export(path, [valid])
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["memories"].append({"id": "bad", "content": ""})
    payload["memory_count"] = 2
    path.write_text(json.dumps(payload), encoding="utf-8")

    result = MemoryClient().import_json(path)

    assert result.imported_count == 1
    assert result.failed_count == 1
    assert result.errors


def test_imported_memories_are_searchable_after_import(tmp_path: Path) -> None:
    memory = make_memory()
    path = tmp_path / "memories.json"
    write_export(path, [memory])
    client = MemoryClient()

    client.import_json(path)

    assert client.search("Python")[0].memory.id == memory.id


def test_backup_creates_default_backup_path(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    client = MemoryClient()
    client.add("User prefers Python.", importance=0.9)

    path = client.backup()

    assert path.parent == Path("backups")
    assert path.name.startswith("mneno-backup-")
    assert path.exists()


def test_backup_custom_path_works(tmp_path: Path) -> None:
    client = MemoryClient()
    client.add("User prefers Python.", importance=0.9)
    path = tmp_path / "custom" / "backup.json"

    result_path = client.backup(path)

    assert result_path == path
    assert path.exists()


def test_restore_replace_works(tmp_path: Path) -> None:
    backup_client = MemoryClient()
    memory = backup_client.add("User prefers Python.", importance=0.9)
    path = backup_client.backup(tmp_path / "backup.json")
    restore_client = MemoryClient()
    restore_client.add("Old memory.")

    result = restore_client.restore(path)

    assert result.imported_count == 1
    assert restore_client.list() == [memory]


def test_restore_append_works(tmp_path: Path) -> None:
    backup_client = MemoryClient()
    memory = backup_client.add("User prefers Python.", importance=0.9)
    path = backup_client.backup(tmp_path / "backup.json")
    restore_client = MemoryClient()
    existing = restore_client.add("Old memory.")

    result = restore_client.restore(path, mode="append")

    assert result.imported_count == 1
    assert {item.id for item in restore_client.list()} == {existing.id, memory.id}


def test_backup_restore_preserves_all_memory_fields(tmp_path: Path) -> None:
    memory = make_memory()
    client = MemoryClient()
    client.store.add(memory)
    path = client.backup(tmp_path / "backup.json")
    restored = MemoryClient()

    restored.restore(path)

    loaded = restored.get(memory.id)
    assert loaded is not None
    assert_memory_preserved(memory, loaded)


def test_json_storage_rejects_invalid_version(tmp_path: Path) -> None:
    path = tmp_path / "memories.json"
    path.write_text(json.dumps({"version": 999, "memories": []}), encoding="utf-8")

    with raises(ValueError, match="Unsupported storage version"):
        JSONFileStorage(path)


def test_json_storage_rejects_missing_memories_field(tmp_path: Path) -> None:
    path = tmp_path / "memories.json"
    path.write_text(json.dumps({"version": 1}), encoding="utf-8")

    with raises(ValueError, match="missing memories"):
        JSONFileStorage(path)


def test_json_storage_empty_file_still_safe(tmp_path: Path) -> None:
    path = tmp_path / "memories.json"
    path.write_text("", encoding="utf-8")

    assert JSONFileStorage(path).list() == []


def test_export_validation_rejects_unknown_format() -> None:
    with raises(ValueError, match="Unknown export format"):
        validate_export_payload({"format": "unknown", "version": 1, "memories": []})


def test_export_validation_rejects_unsupported_version() -> None:
    with raises(ValueError, match="Unsupported export version"):
        validate_export_payload({"format": "mneno.memory_export", "version": 2, "memories": []})


def test_storage_validation_rejects_missing_version() -> None:
    with raises(ValueError, match="missing version"):
        validate_storage_payload({"memories": []})


def test_io_works_with_json_storage(tmp_path: Path) -> None:
    client = MemoryClient(storage=JSONFileStorage(tmp_path / "memories.json"))
    memory = client.add("User prefers Python.", importance=0.9)
    export_path = tmp_path / "export.json"

    client.export_json(export_path)
    restored = MemoryClient(storage=JSONFileStorage(tmp_path / "restored.json"))
    restored.import_json(export_path)

    assert restored.search("Python")[0].memory.id == memory.id


def test_io_works_with_sqlite_storage(tmp_path: Path) -> None:
    client = MemoryClient(storage=SQLiteStorage(tmp_path / "mneno.db"))
    memory = client.add("User prefers Python.", importance=0.9)
    export_path = tmp_path / "export.json"

    client.export_json(export_path)
    restored = MemoryClient(storage=SQLiteStorage(tmp_path / "restored.db"))
    restored.import_json(export_path)

    assert restored.search("Python")[0].memory.id == memory.id


def test_imported_memories_can_be_compacted(tmp_path: Path) -> None:
    first = Memory(content="User prefers Python.", memory_type=MemoryType.PREFERENCE, importance=0.9)
    second = Memory(content="User prefers Python.", memory_type=MemoryType.SEMANTIC, importance=0.7)
    path = tmp_path / "memories.json"
    write_export(path, [first, second])
    client = MemoryClient()

    client.import_json(path)
    diff = client.compact()

    assert diff.created


def test_imported_memories_can_build_context(tmp_path: Path) -> None:
    memory = make_memory()
    path = tmp_path / "memories.json"
    write_export(path, [memory])
    client = MemoryClient()

    client.import_json(path)
    context = client.build_context("Python")

    assert context.included[0].memory_id == memory.id
