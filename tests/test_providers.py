import socket

from pytest import MonkeyPatch, raises

from mneno.providers import (
    DummyEmbeddingProvider,
    DummyLLMProvider,
    DummyRerankerProvider,
    EmbeddingProvider,
    LLMProvider,
    ProviderAlreadyRegisteredError,
    ProviderNotFoundError,
    ProviderRegistry,
    ProviderValidationError,
    RerankerProvider,
)


class InvalidProvider:
    name = "invalid"


def test_provider_registration_and_lookup() -> None:
    registry = ProviderRegistry()
    provider = DummyEmbeddingProvider()

    registry.register_embedding("dummy", provider)

    assert registry.get_embedding("dummy") is provider


def test_duplicate_registration_raises_clear_error() -> None:
    registry = ProviderRegistry()
    registry.register_embedding("dummy", DummyEmbeddingProvider())

    with raises(ProviderAlreadyRegisteredError, match="embedding provider already registered"):
        registry.register_embedding("dummy", DummyEmbeddingProvider())


def test_missing_provider_raises_clear_error() -> None:
    registry = ProviderRegistry()

    with raises(ProviderNotFoundError, match="embedding provider not found"):
        registry.get_embedding("missing")


def test_invalid_provider_registration_raises_validation_error() -> None:
    registry = ProviderRegistry()

    with raises(ProviderValidationError, match="Invalid embedding provider"):
        registry.register_embedding("invalid", InvalidProvider())  # type: ignore[arg-type]


def test_dummy_embedding_provider_is_deterministic() -> None:
    provider = DummyEmbeddingProvider(dimensions=4)

    first = provider.embed(["Mneno memory", "Another memory"])
    second = provider.embed(["Mneno memory", "Another memory"])

    assert first == second
    assert len(first) == 2
    assert len(first[0]) == 4
    assert first[0] != first[1]


def test_dummy_embedding_provider_validation() -> None:
    with raises(ProviderValidationError, match="dimensions"):
        DummyEmbeddingProvider(dimensions=0)


def test_dummy_reranker_provider_is_deterministic() -> None:
    provider = DummyRerankerProvider()
    documents = ["unrelated note", "agent memory runtime", "memory agent context"]

    first = provider.rerank("agent memory", documents)
    second = provider.rerank("agent memory", documents)

    assert first == second
    assert first == [1, 2, 0]


def test_dummy_llm_provider_is_deterministic() -> None:
    provider = DummyLLMProvider()

    first = provider.generate("Summarize memory.", system_prompt="System", temperature=0.0)
    second = provider.generate("Summarize memory.", system_prompt="System", temperature=0.0)

    assert first == second
    assert first == "System | Dummy response: Summarize memory."


def test_dummy_llm_provider_validation() -> None:
    provider = DummyLLMProvider()

    with raises(ProviderValidationError, match="prompt"):
        provider.generate("")


def test_registry_isolation_between_provider_types() -> None:
    registry = ProviderRegistry()
    embedding = DummyEmbeddingProvider()
    llm = DummyLLMProvider()
    reranker = DummyRerankerProvider()

    registry.register_embedding("dummy", embedding)
    registry.register_llm("dummy", llm)
    registry.register_reranker("dummy", reranker)

    assert registry.get_embedding("dummy") is embedding
    assert registry.get_llm("dummy") is llm
    assert registry.get_reranker("dummy") is reranker


def test_protocol_compatibility() -> None:
    assert isinstance(DummyEmbeddingProvider(), EmbeddingProvider)
    assert isinstance(DummyLLMProvider(), LLMProvider)
    assert isinstance(DummyRerankerProvider(), RerankerProvider)


def test_provider_imports_work() -> None:
    assert ProviderRegistry is not None
    assert EmbeddingProvider is not None
    assert LLMProvider is not None
    assert RerankerProvider is not None


def test_dummy_providers_do_not_make_network_calls(monkeypatch: MonkeyPatch) -> None:
    def fail_socket(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("network calls are not allowed")

    monkeypatch.setattr(socket, "socket", fail_socket)

    DummyEmbeddingProvider().embed(["Mneno"])
    DummyLLMProvider().generate("Mneno")
    DummyRerankerProvider().rerank("Mneno", ["Mneno memory"])
