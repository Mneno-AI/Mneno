from datetime import timedelta

from mneno import MemoryClient
from mneno.hierarchy import MemoryLayer
from mneno.models import Memory, MemorySearchResult, MemoryStatus, utc_now
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

    assert [result.memory.id for result in results] == [relevant.id]


def test_search_excludes_zero_relevance_memories_without_recording_access() -> None:
    client = MemoryClient()
    unrelated = client.add("Yesterday I ate chocolate.")

    results = client.search("pizza")
    stored = client.get(unrelated.id)

    assert results == []
    assert stored is not None
    assert stored.access_count == 0
    assert stored.last_accessed_at is None


def test_exact_query_match_receives_clear_boost_and_reason() -> None:
    exact = calculate_memory_score(Memory(content="Python runtime."), query="Python")
    unrelated = calculate_memory_score(Memory(content="TypeScript runtime."), query="Python")

    assert exact.relevance > unrelated.relevance
    assert exact.total > unrelated.total
    assert "Matched query term: python" in exact.reasons


def test_query_relevance_outweighs_importance_for_unrelated_memory() -> None:
    relevant = calculate_memory_score(Memory(content="Python memory SDK.", importance=0.0), query="Python memory SDK")
    important_noise = calculate_memory_score(
        Memory(content="Office chair inventory.", importance=1.0), query="Python memory SDK"
    )

    assert relevant.total > important_noise.total


def test_inactive_status_penalties_remain_strong_and_explainable() -> None:
    active = calculate_memory_score(Memory(content="Python memory SDK."), query="Python memory SDK")
    archived = calculate_memory_score(
        Memory(content="Python memory SDK.", status=MemoryStatus.ARCHIVED), query="Python memory SDK"
    )
    superseded = calculate_memory_score(
        Memory(content="Python memory SDK.", status=MemoryStatus.SUPERSEDED), query="Python memory SDK"
    )

    assert active.total > archived.total
    assert active.total > superseded.total
    assert "Archived memory penalty applied" in archived.reasons
    assert "Superseded memory penalty applied" in superseded.reasons


def test_layer_priority_still_affects_score() -> None:
    operational = calculate_memory_score(
        Memory(content="Current Python task.", layer=MemoryLayer.OPERATIONAL), query="Python task"
    )
    episodic = calculate_memory_score(
        Memory(content="Current Python task.", layer=MemoryLayer.EPISODIC), query="Python task"
    )

    assert operational.total > episodic.total
    assert "Operational layer retrieval boost applied" in operational.reasons


def test_lexical_matching_normalizes_case_punctuation_and_simple_plurals() -> None:
    punctuation = calculate_memory_score(Memory(content="The Python SDK is local."), query="PYTHON, SDK?")
    plural = calculate_memory_score(Memory(content="A durable memory runtime."), query="memories")

    assert punctuation.relevance > 0.9
    assert plural.relevance > 0
    assert "Normalized query term match: memory" in plural.reasons


def test_stopwords_do_not_dilute_query_relevance() -> None:
    with_stopwords = calculate_memory_score(Memory(content="Python is preferred."), query="What is the Python?")
    without_stopwords = calculate_memory_score(Memory(content="Python is preferred."), query="Python")

    assert with_stopwords.relevance == without_stopwords.relevance


def test_first_person_pronoun_is_not_a_query_match() -> None:
    score = calculate_memory_score(Memory(content="I want to become a skilled developer."), query="I hate")

    assert score.relevance == 0
    assert not any("query term: i" in reason for reason in score.reasons)


def test_short_phrase_overlap_beats_scattered_terms_and_keyword_stuffing() -> None:
    phrase = calculate_memory_score(Memory(content="Python memory SDK."), query="Python memory SDK")
    scattered = calculate_memory_score(
        Memory(content="Python filler memory repeated filler SDK Python Python."), query="Python memory SDK"
    )

    assert phrase.relevance > scattered.relevance
    assert "Short query phrase match" in phrase.reasons


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
