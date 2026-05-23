from datetime import timedelta

from mneno import MemoryClient
from mneno.models import Memory, utc_now
from mneno.scoring.temporal import calculate_memory_score


def test_keyword_overlap_increases_relevance() -> None:
    memory = Memory(content="The user is building Mneno, an explainable AI memory SDK.")

    score = calculate_memory_score(memory, query="explainable memory SDK")

    assert score.relevance > 0
    assert score.total > 0


def test_recent_memory_scores_higher_than_old_memory() -> None:
    recent = Memory(content="Recent memory", updated_at=utc_now())
    old = Memory(content="Old memory", updated_at=utc_now() - timedelta(days=90))

    recent_score = calculate_memory_score(recent, query="")
    old_score = calculate_memory_score(old, query="")

    assert recent_score.recency > old_score.recency


def test_client_add_and_search() -> None:
    client = MemoryClient()
    memory = client.add("The user is building Mneno, an SDK for explainable AI memory.")

    results = client.search("What SDK is the user building?")

    assert results
    assert results[0].id == memory.id
    assert client.get(memory.id)
    assert client.get(memory.id).access_count == 1  # type: ignore[union-attr]
