from datetime import timedelta
from pathlib import Path

from mneno import MemoryClient
from mneno.hierarchy import HierarchyManager, LayerPolicy, MemoryLayer
from mneno.models import Memory, MemoryStatus, MemoryType, utc_now
from mneno.scoring.temporal import TemporalMemoryScorer
from mneno.storage import JSONFileStorage, SQLiteStorage


def test_manager_promotes_frequently_accessed_short_term_memory() -> None:
    memory = Memory(content="Useful session note.", layer=MemoryLayer.SHORT_TERM, access_count=5, importance=0.4)

    result = HierarchyManager().evaluate([memory])

    assert result.promoted[0].layer is MemoryLayer.EPISODIC
    assert result.promoted[0].promotion_count == 1
    assert result.promoted[0].audit
    assert result.actions


def test_manager_promotes_high_importance_episodic_memory() -> None:
    memory = Memory(content="Important project event.", layer=MemoryLayer.EPISODIC, importance=0.9)

    result = HierarchyManager().evaluate([memory])

    assert result.promoted[0].layer is MemoryLayer.SEMANTIC
    assert "high retention score" in result.promoted[0].audit[-1].reason


def test_manager_archives_stale_short_term_memory() -> None:
    memory = Memory(
        content="Old temporary note.",
        layer=MemoryLayer.SHORT_TERM,
        updated_at=utc_now() - timedelta(days=10),
    )

    result = HierarchyManager().evaluate([memory], policy=LayerPolicy(short_term_ttl_days=7))

    assert result.archived[0].layer is MemoryLayer.ARCHIVED
    assert result.archived[0].status is MemoryStatus.ARCHIVED
    assert result.archived[0].audit[-1].event_type == "archived"


def test_manager_preserves_operational_memory_without_ttl() -> None:
    memory = Memory(
        content="Current workflow instruction.",
        memory_type=MemoryType.OPERATIONAL,
        updated_at=utc_now() - timedelta(days=100),
        importance=0.1,
    )

    result = HierarchyManager().evaluate([memory])

    assert result.unchanged[0].layer is MemoryLayer.OPERATIONAL
    assert result.archived == []


def test_manager_does_not_delete_memories() -> None:
    memories = [
        Memory(content="Old temporary note.", layer=MemoryLayer.SHORT_TERM, updated_at=utc_now() - timedelta(days=10)),
        Memory(content="Important note.", layer=MemoryLayer.EPISODIC, importance=0.9),
    ]

    result = HierarchyManager().evaluate(memories)

    assert len(result.promoted + result.demoted + result.archived + result.unchanged) == len(memories)


def test_client_evaluate_hierarchy_persists_updates() -> None:
    client = MemoryClient()
    memory = client.add("Useful session note.", layer="short_term", importance=0.4)
    client.store.update(memory.model_copy(update={"access_count": 5}))

    result = client.evaluate_hierarchy()
    stored = client.get(memory.id)

    assert result.promoted
    assert stored is not None
    assert stored.layer is MemoryLayer.EPISODIC
    assert stored.audit


def test_client_manual_promote_and_demote_work() -> None:
    client = MemoryClient()
    memory = client.add("Session event.", layer="episodic")

    promoted = client.promote_memory(memory.id, "semantic")
    demoted = client.demote_memory(memory.id, "episodic")

    assert promoted.layer is MemoryLayer.SEMANTIC
    assert demoted.layer is MemoryLayer.EPISODIC
    assert demoted.promotion_count == 1
    assert demoted.demotion_count == 1
    assert len(demoted.audit) == 2


def test_client_list_by_layer() -> None:
    client = MemoryClient()
    semantic = client.add("Stable fact.", layer="semantic")
    client.add("Current task.", layer="working")

    assert client.list_by_layer("semantic") == [semantic]


def test_retrieval_prioritizes_operational_and_working_layers() -> None:
    client = MemoryClient()
    client.add("Python note.", layer="episodic", importance=0.1)
    operational = client.add("Python instruction.", layer="operational", importance=0.1)

    results = client.search("Python", limit=2)

    assert results[0].memory.id == operational.id
    assert any("Operational layer retrieval boost" in reason for reason in results[0].score.reasons)


def test_archived_memories_excluded_by_default_and_included_when_requested() -> None:
    client = MemoryClient()
    archived = client.add("Archived Python note.", layer="archived")
    active = client.add("Active Python note.", layer="semantic")

    default_ids = {result.memory.id for result in client.search("Python", limit=10)}
    archived_ids = {result.memory.id for result in client.search("Python", limit=10, include_archived=True)}

    assert active.id in default_ids
    assert archived.id not in default_ids
    assert archived.id in archived_ids


def test_layer_weighting_affects_ranking() -> None:
    scorer = TemporalMemoryScorer()
    episodic = Memory(content="Python", layer=MemoryLayer.EPISODIC, importance=0.5)
    working = Memory(content="Python", layer=MemoryLayer.WORKING, importance=0.5)

    assert scorer.score(working, query="Python").total > scorer.score(episodic, query="Python").total


def test_context_explanations_include_layer_reasons() -> None:
    client = MemoryClient()
    memory = client.add("Current task: build benchmark UI.", layer="operational")

    context = client.build_context("benchmark UI")

    assert context.included[0].memory_id == memory.id
    assert "operational layer has high retrieval priority" in context.included[0].reason


def test_build_context_excludes_archived_by_default_and_includes_when_requested() -> None:
    client = MemoryClient()
    archived = client.add("Archived Python note.", layer="archived")
    active = client.add("Active Python note.", layer="semantic")

    default = client.build_context("Python", budget=50)
    with_archived = client.build_context("Python", budget=50, include_archived=True)

    assert {item.memory_id for item in default.included} == {active.id}
    assert {archived.id, active.id}.issubset({item.memory_id for item in with_archived.included})


def test_json_storage_preserves_layers(tmp_path: Path) -> None:
    path = tmp_path / "memories.json"
    client = MemoryClient(storage=JSONFileStorage(path))
    memory = client.add("Current task.", layer="working")
    client.promote_memory(memory.id, "operational")

    loaded = JSONFileStorage(path).get(memory.id)

    assert loaded is not None
    assert loaded.layer is MemoryLayer.OPERATIONAL
    assert loaded.audit


def test_sqlite_storage_preserves_layers(tmp_path: Path) -> None:
    path = tmp_path / "mneno.db"
    client = MemoryClient(storage=SQLiteStorage(path))
    memory = client.add("Current task.", layer="working")
    client.promote_memory(memory.id, "operational")

    loaded = SQLiteStorage(path).get(memory.id)

    assert loaded is not None
    assert loaded.layer is MemoryLayer.OPERATIONAL
    assert loaded.audit


def test_import_export_preserves_layers(tmp_path: Path) -> None:
    client = MemoryClient()
    memory = client.add("Current task.", layer="working")
    client.promote_memory(memory.id, "operational")
    export_path = tmp_path / "export.json"

    client.export_json(export_path)
    restored = MemoryClient()
    restored.import_json(export_path)

    loaded = restored.get(memory.id)
    assert loaded is not None
    assert loaded.layer is MemoryLayer.OPERATIONAL
    assert loaded.audit


def test_backup_restore_preserves_layers(tmp_path: Path) -> None:
    client = MemoryClient()
    memory = client.add("Current task.", layer="working")
    client.promote_memory(memory.id, "operational")
    backup_path = client.backup(tmp_path / "backup.json")

    restored = MemoryClient()
    restored.restore(backup_path)

    loaded = restored.get(memory.id)
    assert loaded is not None
    assert loaded.layer is MemoryLayer.OPERATIONAL
    assert loaded.audit
