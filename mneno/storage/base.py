"""Base storage interfaces."""

from __future__ import annotations

from typing import Protocol

from mneno.models import Memory


class MemoryStore(Protocol):
    """Protocol for memory storage backends."""

    def add(self, memory: Memory) -> Memory:
        """Persist a memory."""

    def get(self, memory_id: str) -> Memory | None:
        """Return a memory by ID."""

    def list(self) -> list[Memory]:
        """Return all memories."""
