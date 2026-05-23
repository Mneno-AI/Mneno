"""Base scoring interfaces."""

from __future__ import annotations

from typing import Protocol

from mneno.models import Memory, MemoryScore


class MemoryScorer(Protocol):
    """Protocol for memory scoring strategies."""

    def score(self, memory: Memory, *, query: str = "", use_semantic: bool = True) -> MemoryScore:
        """Score a memory for an optional query."""
