from pathlib import Path

from mneno import MemoryClient
from mneno.conflicts import ConflictDetector, ConflictPolicy, ConflictResolver
from mneno.conflicts.reports import ConflictType
from mneno.models import Memory, MemoryStatus, MemoryType
from mneno.storage import JSONFileStorage, SQLiteStorage


def test_detector_detects_exact_duplicate() -> None:
    existing = Memory(content="User prefers Python.")
    new = Memory(content="  User prefers Python. ")

    reports = ConflictDetector().detect(new, [existing])

    assert reports[0].conflict_type is ConflictType.DUPLICATE
    assert reports[0].reason
    assert reports[0].evidence
    assert reports[0].suggested_action.value == "keep_both"


def test_detector_detects_near_duplicate() -> None:
    existing = Memory(content="Mneno prevents context rot for long running AI apps.")
    new = Memory(content="Mneno prevents context rot for long-running AI applications.")

    reports = ConflictDetector().detect(new, [existing])

    assert reports[0].conflict_type is ConflictType.DUPLICATE
    assert "token overlap" in reports[0].reason


def test_detector_detects_preference_change() -> None:
    existing = Memory(content="User prefers Python 3.10.", memory_type=MemoryType.PREFERENCE)
    new = Memory(content="User prefers Python 3.11.", memory_type=MemoryType.PREFERENCE)

    reports = ConflictDetector().detect(new, [existing])

    assert reports[0].conflict_type is ConflictType.PREFERENCE_CHANGE
    assert reports[0].reason
    assert reports[0].evidence


def test_detector_detects_negation_contradiction() -> None:
    existing = Memory(content="User wants a React UI.", memory_type=MemoryType.PREFERENCE)
    new = Memory(content="User does not want a React UI.", memory_type=MemoryType.PREFERENCE)

    reports = ConflictDetector().detect(new, [existing])

    assert reports[0].conflict_type is ConflictType.CONTRADICTION
    assert reports[0].severity.value == "high"


def test_detector_detects_now_prefers_supersession() -> None:
    existing = Memory(content="User prefers Python 3.10.", memory_type=MemoryType.PREFERENCE)
    new = Memory(content="User now prefers Python 3.11.", memory_type=MemoryType.PREFERENCE)

    reports = ConflictDetector().detect(new, [existing])

    assert reports[0].conflict_type is ConflictType.SUPERSESSION
    assert reports[0].suggested_action.value == "supersede_existing"


def test_detector_detects_operational_change() -> None:
    existing = Memory(content="Current task is build the React UI.", memory_type=MemoryType.OPERATIONAL)
    new = Memory(content="Current task is build the CLI.", memory_type=MemoryType.OPERATIONAL)

    reports = ConflictDetector().detect(new, [existing])

    assert reports[0].conflict_type is ConflictType.OPERATIONAL_CHANGE


def test_detector_does_not_false_conflict_unrelated_memories() -> None:
    existing = Memory(content="User prefers concise explanations.", memory_type=MemoryType.PREFERENCE)
    new = Memory(content="The project uses SQLite storage.", memory_type=MemoryType.SEMANTIC)

    assert ConflictDetector().detect(new, [existing]) == []


def test_resolver_supersession_marks_old_memory_superseded() -> None:
    existing = Memory(content="User prefers Python 3.10.", memory_type=MemoryType.PREFERENCE)
    new = Memory(content="User now prefers Python 3.11.", memory_type=MemoryType.PREFERENCE)
    reports = ConflictDetector().detect(new, [existing])

    result = ConflictResolver().resolve(new, [existing], reports)
    updated = result.updated_existing[0]

    assert updated.status is MemoryStatus.SUPERSEDED
    assert updated.superseded_by == new.id
    assert updated.audit
    assert result.new_memory.audit
    assert result.actions


def test_resolver_contradiction_marks_conflicts_with() -> None:
    existing = Memory(content="User wants a React UI.", memory_type=MemoryType.PREFERENCE)
    new = Memory(content="User does not want a React UI.", memory_type=MemoryType.PREFERENCE)
    reports = ConflictDetector().detect(new, [existing])

    result = ConflictResolver().resolve(new, [existing], reports)
    updated = result.updated_existing[0]

    assert updated.status is MemoryStatus.CONFLICTED
    assert result.new_memory.status is MemoryStatus.CONFLICTED
    assert new.id in updated.conflicts_with
    assert existing.id in result.new_memory.conflicts_with


def test_resolver_duplicate_does_not_delete_or_archive_by_default() -> None:
    existing = Memory(content="User prefers Python.")
    new = Memory(content="User prefers Python.")
    reports = ConflictDetector().detect(new, [existing])

    result = ConflictResolver().resolve(new, [existing], reports)

    assert result.updated_existing[0].status is MemoryStatus.ACTIVE
    assert result.new_memory.status is MemoryStatus.ACTIVE


def test_resolver_can_archive_duplicate_when_policy_allows() -> None:
    existing = Memory(content="User prefers Python.")
    new = Memory(content="User prefers Python.")
    policy = ConflictPolicy(auto_archive_duplicates=True)
    reports = ConflictDetector().detect(new, [existing], policy=policy)

    result = ConflictResolver().resolve(new, [existing], reports, policy=policy)

    assert result.updated_existing[0].status is MemoryStatus.ARCHIVED


def test_client_add_still_works() -> None:
    client = MemoryClient()
    memory = client.add("User prefers Python.", memory_type="preference")

    assert client.get(memory.id) == memory


def test_client_add_with_report_returns_reports() -> None:
    client = MemoryClient()
    client.add("User prefers Python 3.10.", memory_type="preference")

    result = client.add_with_report("User now prefers Python 3.11.", memory_type="preference")

    assert result.memory.status is MemoryStatus.ACTIVE
    assert result.conflict_reports
    assert result.resolution_actions


def test_client_auto_detect_conflicts_can_be_disabled() -> None:
    client = MemoryClient(auto_detect_conflicts=False)
    old = client.add("User prefers Python 3.10.", memory_type="preference")
    client.add("User now prefers Python 3.11.", memory_type="preference")

    stored_old = client.get(old.id)
    assert stored_old is not None
    assert stored_old.status is MemoryStatus.ACTIVE


def test_client_updated_preference_supersedes_old_preference() -> None:
    client = MemoryClient()
    old = client.add("User prefers Python 3.10.", memory_type="preference")
    new = client.add("User now prefers Python 3.11.", memory_type="preference")

    stored_old = client.get(old.id)
    assert stored_old is not None
    assert stored_old.status is MemoryStatus.SUPERSEDED
    assert stored_old.superseded_by == new.id


def test_client_detect_conflicts_accepts_content_string() -> None:
    client = MemoryClient()
    client.add("User prefers Python 3.10.", memory_type="preference")

    reports = client.detect_conflicts("User now prefers Python 3.11.")

    assert reports[0].conflict_type is ConflictType.SUPERSESSION


def test_client_list_conflicts_derived_from_audit() -> None:
    client = MemoryClient()
    client.add("User prefers Python 3.10.", memory_type="preference")
    client.add("User now prefers Python 3.11.", memory_type="preference")

    reports = client.list_conflicts()

    assert reports
    assert reports[0].reason


def test_search_excludes_superseded_by_default_and_include_inactive_restores_it() -> None:
    client = MemoryClient()
    old = client.add("User prefers Python 3.10.", memory_type="preference", importance=1.0)
    new = client.add("User now prefers Python 3.11.", memory_type="preference", importance=0.1)

    default_ids = {result.memory.id for result in client.search("Python", limit=10)}
    inactive_ids = {result.memory.id for result in client.search("Python", limit=10, include_inactive=True)}

    assert old.id not in default_ids
    assert new.id in default_ids
    assert {old.id, new.id}.issubset(inactive_ids)


def test_build_context_excludes_archived_and_superseded_by_default() -> None:
    client = MemoryClient()
    active = client.add("User now prefers Python 3.11.", memory_type="preference", importance=0.8)
    client.store.add(Memory(content="Archived Python note.", status=MemoryStatus.ARCHIVED, importance=1.0))
    client.store.add(Memory(content="Superseded Python note.", status=MemoryStatus.SUPERSEDED, importance=1.0))

    context = client.build_context("Python", budget=50)

    assert [item.memory_id for item in context.included] == [active.id]


def test_build_context_include_inactive_includes_inactive_memories() -> None:
    client = MemoryClient()
    active = client.add("User now prefers Python 3.11.", memory_type="preference", importance=0.8)
    archived = Memory(content="Archived Python note.", status=MemoryStatus.ARCHIVED, importance=1.0)
    client.store.add(archived)

    context = client.build_context("Python", budget=50, include_inactive=True)

    assert {item.memory_id for item in context.included} == {active.id, archived.id}


def test_json_storage_preserves_conflict_metadata(tmp_path: Path) -> None:
    path = tmp_path / "memories.json"
    client = MemoryClient(storage=JSONFileStorage(path))
    old = client.add("User prefers Python 3.10.", memory_type="preference")
    client.add("User now prefers Python 3.11.", memory_type="preference")

    loaded = JSONFileStorage(path).get(old.id)

    assert loaded is not None
    assert loaded.status is MemoryStatus.SUPERSEDED
    assert loaded.audit


def test_sqlite_storage_preserves_conflict_metadata(tmp_path: Path) -> None:
    path = tmp_path / "mneno.db"
    client = MemoryClient(storage=SQLiteStorage(path))
    old = client.add("User prefers Python 3.10.", memory_type="preference")
    client.add("User now prefers Python 3.11.", memory_type="preference")

    loaded = SQLiteStorage(path).get(old.id)

    assert loaded is not None
    assert loaded.status is MemoryStatus.SUPERSEDED
    assert loaded.audit


def test_import_export_preserves_conflict_metadata(tmp_path: Path) -> None:
    client = MemoryClient()
    old = client.add("User prefers Python 3.10.", memory_type="preference")
    client.add("User now prefers Python 3.11.", memory_type="preference")
    export_path = tmp_path / "export.json"

    client.export_json(export_path)
    restored = MemoryClient()
    restored.import_json(export_path)

    loaded = restored.get(old.id)
    assert loaded is not None
    assert loaded.status is MemoryStatus.SUPERSEDED
    assert loaded.audit
