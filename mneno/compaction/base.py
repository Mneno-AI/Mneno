"""Base compaction interfaces."""

from __future__ import annotations

from typing import Protocol

from mneno.compaction.policies import CompactionPolicy
from mneno.models import CompactionDiff, Memory


class MemoryCompactor(Protocol):
    """Protocol for future explainable memory compaction strategies."""

    def compact(self, memories: list[Memory], *, policy: CompactionPolicy | None = None) -> CompactionDiff:
        """Compact memories and return an explainable diff."""
