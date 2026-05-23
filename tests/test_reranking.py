from mneno import MemoryClient
from mneno.context import ContextPolicy
from mneno.models import Memory, MemoryScore, MemorySearchResult
from mneno.providers.embedding import DummyEmbeddingProvider
from mneno.providers.exceptions import ProviderNotFoundError, ProviderValidationError
from mneno.providers.reranker import DummyRerankerProvider
from mneno.retrieval import RerankingEngine


class DuplicateIndexReranker:
    name = "duplicate"

    def rerank(self, query: str, documents: list[str]) -> list[int]:
        return [0, 0]


class OutOfRangeReranker:
    name = "out-of-range"

    def rerank(self, query: str, documents: list[str]) -> list[int]:
        return [len(documents)]


class PartialReranker:
    name = "partial"

    def rerank(self, query: str, documents: list[str]) -> list[int]:
        return [1]


def make_result(content: str, *, rank: int, total: float = 0.5) -> MemorySearchResult:
    memory = Memory(content=content)
    score = MemoryScore(
        memory_id=memory.id,
        total=total,
        relevance=total,
        importance=memory.importance,
        recency=1.0,
        frequency=0.0,
        freshness=1.0,
    )
    return MemorySearchResult(memory=memory, score=score, rank=rank)


def test_reranking_engine_without_provider_returns_results_unchanged() -> None:
    results = [make_result("Python memory", rank=1)]

    assert RerankingEngine().rerank("Python", results) == results


def test_reranking_engine_provider_reorders_results() -> None:
    results = [
        make_result("Unrelated note", rank=1),
        make_result("Python memory SDK", rank=2),
    ]

    reranked = RerankingEngine(DummyRerankerProvider()).rerank("Python SDK", results)

    assert reranked[0].memory.content == "Python memory SDK"
    assert reranked[0].original_rank == 2
    assert reranked[0].reranked_rank == 1
    assert reranked[0].reranker_name == "dummy"
    assert reranked[0].rerank_reason == "Reranked by provider 'dummy'"


def test_reranking_engine_top_k_only_reranks_prefix() -> None:
    results = [
        make_result("Unrelated note", rank=1),
        make_result("Python memory SDK", rank=2),
        make_result("SDK Python second", rank=3),
    ]

    reranked = RerankingEngine(DummyRerankerProvider()).rerank("Python SDK", results, top_k=2)

    assert [result.memory.content for result in reranked] == [
        "Python memory SDK",
        "Unrelated note",
        "SDK Python second",
    ]


def test_reranking_engine_duplicate_indices_raise_validation_error() -> None:
    results = [make_result("First", rank=1), make_result("Second", rank=2)]

    try:
        RerankingEngine(DuplicateIndexReranker()).rerank("query", results)  # type: ignore[arg-type]
    except ProviderValidationError as exc:
        assert "duplicate index" in str(exc)
        return

    raise AssertionError("Expected duplicate reranker indices to fail")


def test_reranking_engine_out_of_range_indices_raise_validation_error() -> None:
    results = [make_result("First", rank=1)]

    try:
        RerankingEngine(OutOfRangeReranker()).rerank("query", results)  # type: ignore[arg-type]
    except ProviderValidationError as exc:
        assert "out of range" in str(exc)
        return

    raise AssertionError("Expected out-of-range reranker indices to fail")


def test_reranking_engine_partial_index_list_appends_remaining_results() -> None:
    results = [
        make_result("First", rank=1),
        make_result("Second", rank=2),
        make_result("Third", rank=3),
    ]

    reranked = RerankingEngine(PartialReranker()).rerank("query", results)  # type: ignore[arg-type]

    assert [result.memory.content for result in reranked] == ["Second", "First", "Third"]


def test_client_search_works_unchanged_without_reranker() -> None:
    client = MemoryClient()
    strong = client.add("Unrelated architecture note.", importance=1.0)
    client.add("Python SDK memory.", importance=0.1)

    results = client.search("Python")

    assert results[0].memory.id == strong.id
    assert results[0].rerank_reason is None


def test_client_search_use_reranker_false_skips_provider() -> None:
    client = MemoryClient(reranker_provider=DummyRerankerProvider())
    strong = client.add("Unrelated architecture note.", importance=1.0)
    client.add("Python SDK memory.", importance=0.1)

    results = client.search("Python", use_reranker=False)

    assert results[0].memory.id == strong.id
    assert results[0].rerank_reason is None


def test_client_search_use_reranker_true_requires_provider() -> None:
    client = MemoryClient()

    try:
        client.search("Python", use_reranker=True)
    except ProviderNotFoundError as exc:
        assert "Reranking requires" in str(exc)
        return

    raise AssertionError("Expected reranking without provider to fail")


def test_client_search_use_reranker_true_reranks_with_dummy_provider() -> None:
    client = MemoryClient(reranker_provider=DummyRerankerProvider())
    client.add("Unrelated architecture note.", importance=1.0)
    target = client.add("Python SDK memory.", importance=0.1)

    results = client.search("Python", use_reranker=True)

    assert results[0].memory.id == target.id
    assert results[0].original_rank is not None
    assert results[0].reranked_rank == 1
    assert results[0].rerank_reason == "Reranked by provider 'dummy'"


def test_client_search_auto_reranks_when_provider_exists() -> None:
    client = MemoryClient(reranker_provider=DummyRerankerProvider())
    client.add("Unrelated architecture note.", importance=1.0)
    target = client.add("Python SDK memory.", importance=0.1)

    results = client.search("Python")

    assert results[0].memory.id == target.id
    assert results[0].reranker_name == "dummy"


def test_access_count_increments_only_for_final_reranked_results() -> None:
    client = MemoryClient(reranker_provider=DummyRerankerProvider())
    excluded = client.add("Unrelated architecture note.", importance=1.0)
    included = client.add("Python SDK memory.", importance=0.1)

    results = client.search("Python", limit=1, use_reranker=True)

    assert [result.memory.id for result in results] == [included.id]
    included_after = client.get(included.id)
    excluded_after = client.get(excluded.id)
    assert included_after is not None
    assert excluded_after is not None
    assert included_after.access_count == 1
    assert excluded_after.access_count == 0


def test_semantic_and_reranker_can_work_together() -> None:
    client = MemoryClient(
        embedding_provider=DummyEmbeddingProvider(),
        reranker_provider=DummyRerankerProvider(),
    )
    client.add("Unrelated architecture note.", importance=1.0)
    target = client.add("Python AI memory SDK.", importance=0.1)

    results = client.search("Python memory SDK", use_semantic=True, use_reranker=True)

    assert results[0].memory.id == target.id
    assert results[0].score.semantic_relevance is not None
    assert results[0].rerank_reason is not None


def test_deterministic_fallback_and_reranker_can_work_together() -> None:
    client = MemoryClient(reranker_provider=DummyRerankerProvider())
    client.add("Unrelated architecture note.", importance=1.0)
    target = client.add("Python SDK memory.", importance=0.1)

    results = client.search("Python", use_semantic=False, use_reranker=True)

    assert results[0].memory.id == target.id
    assert results[0].score.semantic_relevance is None


def test_build_context_works_with_reranker() -> None:
    client = MemoryClient(reranker_provider=DummyRerankerProvider())
    client.add("Unrelated architecture note.", importance=1.0)
    target = client.add("Python SDK memory.", importance=0.1)

    context = client.build_context("Python")

    assert context.included[0].memory_id == target.id


def test_build_context_works_without_reranker() -> None:
    client = MemoryClient()
    memory = client.add("Python SDK memory.", importance=0.9)

    context = client.build_context("Python")

    assert context.included[0].memory_id == memory.id


def test_context_reasons_mention_reranking_when_used() -> None:
    client = MemoryClient(reranker_provider=DummyRerankerProvider())
    client.add("Unrelated architecture note.", importance=1.0)
    client.add("Python SDK memory.", importance=0.1)

    context = client.build_context("Python")

    assert "Reranked by provider 'dummy'" in context.included[0].reason


def test_context_policy_behavior_remains_unchanged() -> None:
    client = MemoryClient(reranker_provider=DummyRerankerProvider())
    client.add("Python SDK memory.", importance=0.9)
    client.add("Python extra memory.", importance=0.8)

    context = client.build_context("Python", policy=ContextPolicy(max_tokens=100, max_items=1))

    assert len(context.included) == 1
    assert any(item.reason == "Excluded because max_items reached" for item in context.excluded)
