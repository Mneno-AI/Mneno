"""Base retrieval interfaces."""

from __future__ import annotations

from typing import Protocol

from mneno.models import Memory


class MemoryRetriever(Protocol):
    """Protocol for retrieval implementations."""

    def search(self, query: str, *, limit: int = 5) -> list[Memory]:
        """Return memories matching a query."""
