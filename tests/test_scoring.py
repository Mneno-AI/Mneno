from datetime import timedelta

from mneno import MemoryClient
from mneno.models import Memory, MemorySearchResult, utc_now
from mneno.scoring.temporal import calculate_memory_score


def test_keyword_overlap_increases_relevance() -> None:
    memory = Memory(content="The user is building Mneno, an explainable AI memory SDK.")

    score = calculate_memory_score(memory, query="explainable memory SDK")

    assert score.relevance > 0
    assert score.total > 0
    assert "Matched query term: explainable" in score.reasons


def test_recent_memory_scores_higher_than_old_memory() -> None:
    recent = Memory(content="Recent memory", updated_at=utc_now())
    old = Memory(content="Old memory", updated_at=utc_now() - timedelta(days=90))

    recent_score = calculate_memory_score(recent, query="")
    old_score = calculate_memory_score(old, query="")

    assert recent_score.recency > old_score.recency


def test_client_add_and_search() -> None:
    client = MemoryClient()
    memory = client.add(
        "The user is building Mneno, an SDK for explainable AI memory.",
        memory_type="semantic",
        importance=0.9,
        tags=["project", "mneno"],
    )

    results = client.search("What SDK is the user building?")

    assert results
    assert isinstance(results[0], MemorySearchResult)
    assert results[0].memory.id == memory.id
    assert results[0].rank == 1
    assert results[0].score.total > 0
    assert results[0].score.reasons
    stored = client.get(memory.id)
    assert stored is not None
    assert stored.access_count == 1
    assert stored.last_accessed_at is not None


def test_client_get_by_id() -> None:
    client = MemoryClient()
    memory = client.add("Mneno stores structured memories.", memory_type="semantic")

    assert client.get(memory.id) == memory
    assert client.get("missing") is None


def test_score_ordering_prefers_relevant_important_memory() -> None:
    client = MemoryClient()
    relevant = client.add("Mneno is a Python SDK for explainable AI memory.", importance=0.9, tags=["mneno"])
    client.add("The office has a blue chair.", importance=0.1, tags=["office"])

    results = client.search("Python SDK Mneno", limit=2)

    assert [result.memory.id for result in results][0] == relevant.id
    assert results[0].score.total >= results[1].score.total


def test_client_delete() -> None:
    client = MemoryClient()
    memory = client.add("Temporary memory")

    assert client.delete(memory.id) is True
    assert client.get(memory.id) is None
    assert client.delete(memory.id) is False


def test_client_clear() -> None:
    client = MemoryClient()
    client.add("First memory")
    client.add("Second memory")

    client.clear()

    assert client.list() == []
