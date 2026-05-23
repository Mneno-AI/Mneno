from datetime import timedelta

from mneno import MemoryClient
from mneno.compaction import CompactionPolicy
from mneno.models import CompactionDecisionType, Memory, MemoryType, utc_now


def test_preview_compaction_does_not_mutate_storage() -> None:
    client = MemoryClient()
    first = client.add("User prefers Python.", memory_type="preference", importance=0.9)
    second = client.add("User prefers Python.", memory_type="semantic", importance=0.7)

    diff = client.preview_compaction()

    assert diff.merged
    assert [memory.id for memory in client.list()] == [first.id, second.id]


def test_compact_mutates_storage_for_merged_memories() -> None:
    client = MemoryClient()
    first = client.add("User prefers Python.", memory_type="preference", importance=0.9, tags=["language"])
    second = client.add("User prefers Python.", memory_type="semantic", importance=0.7, tags=["python"])

    diff = client.compact()
    stored = client.list()

    assert len(diff.created) == 1
    assert len(stored) == 1
    assert stored[0].id == diff.created[0].id
    assert first.id not in {memory.id for memory in stored}
    assert second.id not in {memory.id for memory in stored}


def test_high_importance_memories_are_kept() -> None:
    client = MemoryClient()
    memory = client.add("Critical project constraint.", memory_type="semantic", importance=0.95)

    diff = client.preview_compaction()

    assert [decision.memory_id for decision in diff.kept] == [memory.id]
    assert "importance 0.95" in diff.kept[0].reason


def test_operational_and_preference_memories_are_preserved() -> None:
    client = MemoryClient()
    operational = client.add("Current task is compaction.", memory_type="operational", importance=0.1)
    preference = client.add("User prefers Python.", memory_type="preference", importance=0.1)

    diff = client.preview_compaction()

    kept_ids = {decision.memory_id for decision in diff.kept}
    assert operational.id in kept_ids
    assert preference.id in kept_ids
    assert all("preserved by policy" in decision.reason for decision in diff.kept)


def test_low_score_stale_memory_is_discarded() -> None:
    client = MemoryClient()
    stale = Memory(
        content="Small talk from old session.",
        memory_type=MemoryType.EPISODIC,
        importance=0.1,
        created_at=utc_now() - timedelta(days=400),
        updated_at=utc_now() - timedelta(days=400),
    )
    client.store.add(stale)

    diff = client.preview_compaction()

    assert [decision.memory_id for decision in diff.discarded] == [stale.id]
    assert "stale" in diff.discarded[0].reason


def test_duplicate_memories_are_merged() -> None:
    client = MemoryClient()
    first = client.add("Mneno prevents context rot.", memory_type="semantic", importance=0.8)
    second = client.add("Mneno prevents context rot.", memory_type="semantic", importance=0.6)

    diff = client.preview_compaction()

    assert {decision.memory_id for decision in diff.merged} == {first.id, second.id}
    assert all(decision.decision is CompactionDecisionType.MERGED for decision in diff.merged)
    assert len(diff.created) == 1
    assert diff.created[0].content.startswith("Merged memory:")


def test_near_duplicate_memories_are_merged() -> None:
    client = MemoryClient()
    first = client.add("Mneno prevents context rot for long running AI apps.", memory_type="semantic", importance=0.8)
    second = client.add("Mneno prevents context rot for long-running AI applications.", importance=0.7)

    diff = client.preview_compaction()

    assert {decision.memory_id for decision in diff.merged} == {first.id, second.id}


def test_merged_memory_preserves_metadata_tags_and_access_count() -> None:
    client = MemoryClient()
    first = client.add(
        "User prefers Python.",
        memory_type="preference",
        importance=0.9,
        metadata={"source": "chat", "confidence": "high"},
        tags=["user", "python"],
    )
    second = client.add(
        "User prefers Python.",
        memory_type="semantic",
        importance=0.7,
        metadata={"source": "ticket", "scope": "language"},
        tags=["preference", "python"],
    )
    client.store.update(first.model_copy(update={"access_count": 2}))
    client.store.update(second.model_copy(update={"access_count": 3}))

    diff = client.preview_compaction()
    merged = diff.created[0]

    assert merged.importance == 0.9
    assert merged.memory_type is MemoryType.PREFERENCE
    assert merged.tags == ["preference", "python", "user"]
    assert merged.access_count == 5
    assert set(merged.metadata["source_memory_ids"]) == {first.id, second.id}
    assert set(merged.metadata["source"]) == {"chat", "ticket"}
    assert merged.metadata["scope"] == "language"


def test_compaction_diff_stats_are_correct() -> None:
    client = MemoryClient()
    client.add("User prefers Python.", memory_type="preference", importance=0.9)
    client.add("User prefers Python.", memory_type="semantic", importance=0.7)
    client.store.add(
        Memory(
            content="Small talk from old session.",
            memory_type=MemoryType.EPISODIC,
            importance=0.1,
            created_at=utc_now() - timedelta(days=400),
            updated_at=utc_now() - timedelta(days=400),
        )
    )

    diff = client.preview_compaction()

    assert diff.stats.before_count == 3
    assert diff.stats.after_count == 1
    assert diff.stats.merged_count == 2
    assert diff.stats.discarded_count == 1
    assert diff.stats.created_count == 1
    assert diff.stats.estimated_reduction_ratio == 0.666667
    assert diff.summary


def test_compaction_decision_reasons_are_not_empty() -> None:
    client = MemoryClient()
    client.add("Important memory", importance=0.9)
    client.add("Important memory", importance=0.8)

    diff = client.preview_compaction()
    decisions = [*diff.kept, *diff.merged, *diff.discarded]

    assert decisions
    assert all(decision.reason for decision in decisions)


def test_default_policy_is_safe() -> None:
    policy = CompactionPolicy()

    assert MemoryType.OPERATIONAL in policy.preserve_memory_types
    assert MemoryType.PREFERENCE in policy.preserve_memory_types
    assert policy.merge_duplicates is True
    assert policy.discard_stale is True
    assert policy.min_score_to_keep <= 0.25


def test_custom_policy_changes_behavior() -> None:
    client = MemoryClient()
    first = client.add("User prefers Python.", memory_type="preference", importance=0.9)
    second = client.add("User prefers Python.", memory_type="semantic", importance=0.7)

    diff = client.preview_compaction(policy=CompactionPolicy(merge_duplicates=False))

    assert diff.merged == []
    assert diff.created == []
    assert {decision.memory_id for decision in diff.kept} == {first.id, second.id}
