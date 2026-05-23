from mneno import MemoryClient, MemorySearchResult


def test_import_memory_client() -> None:
    assert MemoryClient is not None
    assert MemorySearchResult is not None
