from copy import deepcopy

from pytest import raises

from mneno import MemoryClient
from mneno.models import Memory
from mneno.providers.embedding import DummyEmbeddingProvider
from mneno.providers.exceptions import ProviderNotFoundError
from mneno.retrieval import SemanticRetriever
from mneno.retrieval.similarity import cosine_similarity, normalize_vector, safe_similarity
from mneno.storage import JSONFileStorage, SQLiteStorage


def test_cosine_similarity_identical_vectors() -> None:
    assert cosine_similarity([1.0, 0.0], [1.0, 0.0]) == 1.0


def test_cosine_similarity_orthogonal_vectors() -> None:
    assert cosine_similarity([1.0, 0.0], [0.0, 1.0]) == 0.0


def test_empty_vectors_are_safe() -> None:
    assert normalize_vector([]) == []
    assert safe_similarity([], []) == 0.0


def test_dimension_mismatch_raises_value_error() -> None:
    with raises(ValueError, match="Vector dimensions must match"):
        cosine_similarity([1.0], [1.0, 2.0])


def test_normalization_works() -> None:
    assert normalize_vector([3.0, 4.0]) == [0.6, 0.8]


def test_semantic_retriever_ranks_memories_with_dummy_provider() -> None:
    retriever = SemanticRetriever(DummyEmbeddingProvider(dimensions=16))
    target = Memory(content="AI memory SDK project")
    other = Memory(content="Italian food preference")

    results = retriever.rank("memory SDK project", [other, target])

    assert results[0].memory.id == target.id
    assert results[0].similarity >= results[1].similarity
    assert "embedding provider 'dummy'" in results[0].reason


def test_semantic_retriever_respects_top_k() -> None:
    retriever = SemanticRetriever(DummyEmbeddingProvider())
    memories = [Memory(content=f"Memory {index}") for index in range(3)]

    results = retriever.rank("Memory", memories, top_k=2)

    assert len(results) == 2
    assert [result.rank for result in results] == [1, 2]


def test_semantic_retriever_does_not_mutate_memories() -> None:
    retriever = SemanticRetriever(DummyEmbeddingProvider())
    memory = Memory(content="AI memory SDK project")
    before = deepcopy(memory)

    retriever.rank("memory SDK", [memory])

    assert memory == before


def test_semantic_retriever_without_provider_raises() -> None:
    retriever = SemanticRetriever()

    with raises(ProviderNotFoundError, match="embedding provider"):
        retriever.rank("query", [Memory(content="content")])


def test_default_search_still_works_without_provider() -> None:
    client = MemoryClient()
    memory = client.add("User is building Mneno, an SDK for memory.")

    results = client.search("memory SDK")

    assert results[0].memory.id == memory.id
    assert results[0].score.semantic_relevance is None


def test_search_use_semantic_false_uses_fallback() -> None:
    client = MemoryClient(embedding_provider=DummyEmbeddingProvider())
    memory = client.add("User is building Mneno, an SDK for memory.")

    results = client.search("memory SDK", use_semantic=False)

    assert results[0].memory.id == memory.id
    assert results[0].score.semantic_relevance is None


def test_search_use_semantic_true_requires_provider() -> None:
    client = MemoryClient()

    with raises(ProviderNotFoundError, match="Semantic search requires"):
        client.search("memory SDK", use_semantic=True)


def test_search_use_semantic_true_works_with_dummy_provider() -> None:
    client = MemoryClient(embedding_provider=DummyEmbeddingProvider(dimensions=16))
    target = client.add("User is building Mneno, an AI memory SDK.", importance=0.9)
    client.add("User likes Italian food.", importance=0.5)

    results = client.search("AI memory SDK project", use_semantic=True)

    assert results[0].memory.id == target.id
    assert results[0].score.semantic_relevance is not None


def test_search_auto_uses_provider_when_available() -> None:
    client = MemoryClient(embedding_provider=DummyEmbeddingProvider())
    client.add("User is building Mneno, an AI memory SDK.", importance=0.9)

    results = client.search("AI memory SDK")

    assert results[0].score.semantic_relevance is not None


def test_memory_search_result_includes_semantic_explanation() -> None:
    client = MemoryClient(embedding_provider=DummyEmbeddingProvider())
    client.add("User is building Mneno, an AI memory SDK.", importance=0.9)

    result = client.search("AI memory SDK", use_semantic=True)[0]

    assert any("Semantic similarity" in reason for reason in result.score.reasons)


def test_access_count_behavior_remains_correct() -> None:
    client = MemoryClient(embedding_provider=DummyEmbeddingProvider())
    memory = client.add("User is building Mneno, an AI memory SDK.", importance=0.9)

    client.search("AI memory SDK", use_semantic=True)

    stored = client.get(memory.id)
    assert stored is not None
    assert stored.access_count == 1
    assert stored.last_accessed_at is not None


def test_build_context_works_with_embedding_provider() -> None:
    client = MemoryClient(embedding_provider=DummyEmbeddingProvider())
    memory = client.add("User is building Mneno, an AI memory SDK.", importance=0.9)

    context = client.build_context("AI memory SDK")

    assert context.included[0].memory_id == memory.id


def test_build_context_still_works_without_embedding_provider() -> None:
    client = MemoryClient()
    memory = client.add("User is building Mneno, an AI memory SDK.", importance=0.9)

    context = client.build_context("AI memory SDK")

    assert context.included[0].memory_id == memory.id


def test_compact_behavior_is_not_broken() -> None:
    client = MemoryClient(embedding_provider=DummyEmbeddingProvider())
    client.add("User prefers Python.", memory_type="preference", importance=0.9)
    client.add("User prefers Python.", memory_type="semantic", importance=0.7)

    diff = client.compact()

    assert diff.created


def test_json_storage_does_not_persist_embeddings(tmp_path) -> None:  # type: ignore[no-untyped-def]
    client = MemoryClient(
        storage=JSONFileStorage(tmp_path / "memories.json"), embedding_provider=DummyEmbeddingProvider()
    )
    memory = client.add("User is building Mneno, an AI memory SDK.", importance=0.9)

    client.search("AI memory SDK", use_semantic=True)
    loaded = JSONFileStorage(tmp_path / "memories.json").get(memory.id)

    assert loaded is not None
    assert "embedding" not in loaded.metadata


def test_sqlite_storage_still_works_with_semantic_search(tmp_path) -> None:  # type: ignore[no-untyped-def]
    client = MemoryClient(storage=SQLiteStorage(tmp_path / "mneno.db"), embedding_provider=DummyEmbeddingProvider())
    memory = client.add("User is building Mneno, an AI memory SDK.", importance=0.9)

    results = client.search("AI memory SDK", use_semantic=True)

    assert results[0].memory.id == memory.id


def test_import_export_preserves_memories_without_embeddings(tmp_path) -> None:  # type: ignore[no-untyped-def]
    client = MemoryClient(embedding_provider=DummyEmbeddingProvider())
    memory = client.add("User is building Mneno, an AI memory SDK.", importance=0.9)
    export_path = tmp_path / "export.json"

    client.search("AI memory SDK", use_semantic=True)
    client.export_json(export_path)
    restored = MemoryClient()
    restored.import_json(export_path)

    loaded = restored.get(memory.id)
    assert loaded is not None
    assert "embedding" not in loaded.metadata
