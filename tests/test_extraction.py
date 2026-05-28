from mneno import ExtractedMemory, ExtractionResult, MemoryClient
from mneno.extraction import DeterministicMemoryExtractor, LLMMemoryExtractor
from mneno.models import MemoryType
from mneno.providers.exceptions import ProviderNotFoundError
from mneno.providers.llm import DummyLLMProvider


class InvalidJSONLLMProvider:
    name = "invalid-json"

    def generate(
        self,
        prompt: str,
        *,
        system_prompt: str | None = None,
        temperature: float = 0.0,
        max_tokens: int | None = None,
    ) -> str:
        return "not json"


class InvalidMemoryTypeLLMProvider:
    name = "invalid-memory-type"

    def generate(
        self,
        prompt: str,
        *,
        system_prompt: str | None = None,
        temperature: float = 0.0,
        max_tokens: int | None = None,
    ) -> str:
        return '[{"content":"Bad memory","memory_type":"bad","importance":0.5,"tags":[],"metadata":{},"reason":"bad"}]'


def test_extracted_memory_model_is_public() -> None:
    item = ExtractedMemory(content="User prefers Python.", memory_type="preference", importance=0.8, reason="test")

    assert item.memory_type is MemoryType.PREFERENCE
    assert item.tags == []


def test_deterministic_extractor_extracts_semantic_memories() -> None:
    result = DeterministicMemoryExtractor().extract("The user is building Mneno, a Python SDK.")

    assert result.mode == "deterministic"
    assert result.extracted[0].memory_type is MemoryType.SEMANTIC
    assert "durable factual claim" in result.extracted[0].reason


def test_deterministic_extractor_detects_preferences() -> None:
    result = DeterministicMemoryExtractor().extract("The user prefers Python 3.11.")

    assert result.extracted[0].memory_type is MemoryType.PREFERENCE
    assert result.extracted[0].importance == 0.8


def test_deterministic_extractor_detects_operational_memories() -> None:
    result = DeterministicMemoryExtractor().extract("Current task must finish Step 11 by the deadline.")

    assert result.extracted[0].memory_type is MemoryType.OPERATIONAL
    assert result.extracted[0].importance == 0.75


def test_deterministic_extractor_ignores_trivial_lines() -> None:
    result = DeterministicMemoryExtractor().extract("\nHi.\nOK.\nThe user likes concise summaries.")

    assert len(result.extracted) == 1
    assert result.extracted[0].memory_type is MemoryType.PREFERENCE


def test_deterministic_extractor_output_is_deterministic() -> None:
    text = "The user prefers Python. The current goal is to finish Mneno."
    first = DeterministicMemoryExtractor().extract(text)
    second = DeterministicMemoryExtractor().extract(text)

    assert first == second


def test_llm_extractor_uses_dummy_provider_and_parses_json() -> None:
    result = LLMMemoryExtractor(DummyLLMProvider()).extract("The user is building Mneno. They prefer Python 3.11.")

    assert result.mode == "llm"
    assert result.provider_name == "dummy"
    assert result.prompt_version == "mneno.memory_extraction.v1"
    assert len(result.extracted) == 2
    assert result.errors == []


def test_llm_extractor_handles_invalid_json_gracefully() -> None:
    result = LLMMemoryExtractor(InvalidJSONLLMProvider()).extract("The user prefers Python.")

    assert result.extracted == []
    assert result.errors


def test_llm_extractor_validates_memory_type() -> None:
    result = LLMMemoryExtractor(InvalidMemoryTypeLLMProvider()).extract("Bad memory")

    assert result.extracted == []
    assert result.errors


def test_extract_memories_default_uses_deterministic_without_provider() -> None:
    result = MemoryClient().extract_memories("The user prefers Python.")

    assert result.mode == "deterministic"


def test_extract_memories_auto_uses_llm_when_provider_exists() -> None:
    result = MemoryClient(llm_provider=DummyLLMProvider()).extract_memories("The user is building Mneno.")

    assert result.mode == "llm"
    assert result.provider_name == "dummy"


def test_extract_memories_use_llm_true_requires_provider() -> None:
    try:
        MemoryClient().extract_memories("The user prefers Python.", use_llm=True)
    except ProviderNotFoundError as exc:
        assert "LLM-assisted operation requires" in str(exc)
        return

    raise AssertionError("Expected missing LLM provider to fail")


def test_add_from_text_adds_deterministic_extracted_memories() -> None:
    client = MemoryClient()

    result = client.add_from_text("The user prefers Python. The current task must finish Step 11.")

    assert result.mode == "deterministic"
    assert len(client.list()) == len(result.extracted)
    assert all(item.memory_id is not None for item in result.extracted)


def test_add_from_text_adds_llm_extracted_memories() -> None:
    client = MemoryClient(llm_provider=DummyLLMProvider())

    result = client.add_from_text("The user is building Mneno. They prefer Python 3.11.")

    assert result.mode == "llm"
    assert len(client.list()) == 2
    assert all(item.memory_id is not None for item in result.extracted)


def test_extraction_errors_do_not_crash_valid_imports() -> None:
    client = MemoryClient(llm_provider=InvalidMemoryTypeLLMProvider())

    result = client.add_from_text("Bad memory", use_llm=True)

    assert result.errors
    assert client.list() == []


def test_extraction_result_model_is_public() -> None:
    result = ExtractionResult(source_text="source", mode="deterministic")

    assert result.extracted == []


def test_deterministic_compaction_still_works() -> None:
    client = MemoryClient()
    client.add("User prefers Python.", memory_type="preference", importance=0.9)
    client.add("User prefers Python.", memory_type="semantic", importance=0.7)

    diff = client.compact(use_llm=False)

    assert diff.created[0].content.startswith("Merged memory:")


def test_compaction_use_llm_true_requires_provider() -> None:
    client = MemoryClient()

    try:
        client.compact(use_llm=True)
    except ProviderNotFoundError as exc:
        assert "LLM-assisted operation requires" in str(exc)
        return

    raise AssertionError("Expected missing LLM provider to fail")


def test_llm_assisted_merge_content_can_be_used() -> None:
    client = MemoryClient(llm_provider=DummyLLMProvider())
    client.add("User prefers Python.", memory_type="preference", importance=0.9)
    client.add("User prefers Python.", memory_type="semantic", importance=0.7)

    diff = client.preview_compaction(use_llm=True)

    assert diff.created[0].content.startswith("LLM merged memory:")
    assert diff.merged[0].reason


def test_llm_compaction_invalid_json_falls_back_to_deterministic_content() -> None:
    client = MemoryClient(llm_provider=InvalidJSONLLMProvider())
    client.add("User prefers Python.", memory_type="preference", importance=0.9)
    client.add("User prefers Python.", memory_type="semantic", importance=0.7)

    diff = client.preview_compaction(use_llm=True)

    assert diff.created[0].content.startswith("Merged memory:")
