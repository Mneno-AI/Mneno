from pydantic import ValidationError

from mneno.models import (
    AddMemoryRequest,
    CompactionDecision,
    CompactionDecisionType,
    CompactionDiff,
    Memory,
    MemoryAuditEvent,
    MemoryLayer,
    MemoryPolicy,
    MemoryScore,
    MemorySearchResult,
    MemoryStatus,
    MemoryType,
    utc_now,
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
    assert memory.status is MemoryStatus.ACTIVE
    assert memory.superseded_by is None
    assert memory.conflicts_with == []
    assert memory.audit == []
    assert memory.layer is MemoryLayer.SEMANTIC
    assert memory.promotion_count == 0
    assert memory.demotion_count == 0
    assert memory.last_promoted_at is None
    assert memory.last_demoted_at is None
    assert memory.retention_score is None
    assert memory.session_id is None
    assert memory.sequence_index is None


def test_memory_default_layer_assignment_by_type() -> None:
    assert Memory(content="Current task.", memory_type="operational").layer is MemoryLayer.OPERATIONAL
    assert Memory(content="User prefers Python.", memory_type="preference").layer is MemoryLayer.SEMANTIC
    assert Memory(content="Stable fact.", memory_type="semantic").layer is MemoryLayer.SEMANTIC
    assert Memory(content="Session event.", memory_type="episodic").layer is MemoryLayer.EPISODIC


def test_old_style_memory_payload_loads_with_lifecycle_defaults() -> None:
    memory = Memory.model_validate({"content": "Old serialized memory."})

    assert memory.status is MemoryStatus.ACTIVE
    assert memory.superseded_by is None
    assert memory.conflicts_with == []
    assert memory.audit == []
    assert memory.layer is MemoryLayer.SEMANTIC
    assert memory.session_id is None
    assert memory.sequence_index is None


def test_memory_audit_event_serializes_and_deserializes() -> None:
    event = MemoryAuditEvent(
        event_type="superseded",
        timestamp=utc_now(),
        reason="Updated preference",
        related_memory_ids=["new"],
        metadata={"conflict_id": "conflict-1"},
    )
    memory = Memory(content="User prefers Python 3.10.", audit=[event], status=MemoryStatus.SUPERSEDED)
    loaded = Memory.model_validate(memory.model_dump(mode="json"))

    assert loaded.status is MemoryStatus.SUPERSEDED
    assert loaded.audit[0].event_type == "superseded"
    assert loaded.audit[0].metadata == {"conflict_id": "conflict-1"}


def test_memory_hierarchy_metadata_serializes_and_deserializes() -> None:
    memory = Memory(
        content="Current working state.",
        layer=MemoryLayer.WORKING,
        promotion_count=1,
        demotion_count=2,
        last_promoted_at=utc_now(),
        last_demoted_at=utc_now(),
        retention_score=0.8,
    )
    loaded = Memory.model_validate(memory.model_dump(mode="json"))

    assert loaded.layer is MemoryLayer.WORKING
    assert loaded.promotion_count == 1
    assert loaded.demotion_count == 2
    assert loaded.last_promoted_at == memory.last_promoted_at
    assert loaded.last_demoted_at == memory.last_demoted_at
    assert loaded.retention_score == 0.8


def test_memory_session_metadata_serializes_and_deserializes() -> None:
    memory = Memory(content="Session memory.", session_id="session-1", sequence_index=3)
    loaded = Memory.model_validate(memory.model_dump(mode="json"))

    assert loaded.session_id == "session-1"
    assert loaded.sequence_index == 3


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
