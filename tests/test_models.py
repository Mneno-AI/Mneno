from pydantic import ValidationError

from mneno.models import CompactionDiff, Memory, MemoryPolicy, MemoryType


def test_memory_defaults() -> None:
    memory = Memory(content="The user is building Mneno.")

    assert memory.id
    assert memory.memory_type is MemoryType.FACT
    assert memory.metadata == {}
    assert memory.importance == 0.5
    assert memory.access_count == 0


def test_memory_rejects_invalid_importance() -> None:
    try:
        Memory(content="Invalid", importance=2.0)
    except ValidationError:
        return

    raise AssertionError("Memory should reject importance outside 0..1")


def test_compaction_diff_template() -> None:
    diff = CompactionDiff(kept=["a"], merged=["b"], discarded=["c"], reasons={"c": "obsolete"})

    assert diff.kept == ["a"]
    assert diff.merged == ["b"]
    assert diff.discarded == ["c"]
    assert diff.reasons["c"] == "obsolete"


def test_memory_policy_defaults() -> None:
    policy = MemoryPolicy()

    assert policy.default_importance == 0.5
    assert policy.max_context_memories == 20
