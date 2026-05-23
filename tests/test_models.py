from pydantic import ValidationError

from mneno.models import (
    AddMemoryRequest,
    CompactionDecision,
    CompactionDecisionType,
    CompactionDiff,
    Memory,
    MemoryPolicy,
    MemoryScore,
    MemorySearchResult,
    MemoryType,
)


def test_memory_defaults() -> None:
    memory = Memory(content="The user is building Mneno.")

    assert memory.id
    assert memory.memory_type is MemoryType.SEMANTIC
    assert memory.metadata == {}
    assert memory.importance == 0.5
    assert memory.access_count == 0
    assert memory.last_accessed_at is None
    assert memory.source is None
    assert memory.tags == []


def test_memory_accepts_structured_fields() -> None:
    memory = Memory(
        content="The user prefers concise explanations.",
        memory_type="preference",
        source="conversation",
        tags=["User", "Preference", "user"],
    )

    assert memory.memory_type is MemoryType.PREFERENCE
    assert memory.source == "conversation"
    assert memory.tags == ["user", "preference"]


def test_memory_rejects_invalid_importance() -> None:
    try:
        Memory(content="Invalid", importance=2.0)
    except ValidationError:
        return

    raise AssertionError("Memory should reject importance outside 0..1")


def test_add_memory_request_validates_memory_type() -> None:
    request = AddMemoryRequest(content="Stable project fact", memory_type="semantic")

    assert request.memory_type is MemoryType.SEMANTIC

    try:
        AddMemoryRequest(content="Invalid type", memory_type="fact")
    except ValidationError:
        return

    raise AssertionError("AddMemoryRequest should reject unsupported memory types")


def test_memory_search_result_requires_positive_rank() -> None:
    memory = Memory(content="Mneno is Python-first.")
    score = MemoryScore(
        memory_id=memory.id,
        total=1.0,
        relevance=1.0,
        importance=1.0,
        recency=1.0,
        frequency=0.0,
        freshness=1.0,
    )

    try:
        MemorySearchResult(memory=memory, score=score, rank=0)
    except ValidationError:
        return

    raise AssertionError("MemorySearchResult should reject non-positive ranks")


def test_compaction_diff_template() -> None:
    memory = Memory(content="Mneno is Python-first.")
    decision = CompactionDecision(
        memory_id=memory.id,
        decision=CompactionDecisionType.KEPT,
        reason="Kept because memory type 'semantic' is useful",
        score_before=0.8,
    )
    diff = CompactionDiff(kept=[decision], summary="Kept one memory")

    assert diff.kept == [decision]
    assert diff.merged == []
    assert diff.discarded == []
    assert diff.summary == "Kept one memory"


def test_memory_policy_defaults() -> None:
    policy = MemoryPolicy()

    assert policy.default_importance == 0.5
    assert policy.max_context_memories == 20
