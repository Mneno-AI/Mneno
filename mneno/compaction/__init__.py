"""Compaction foundations for Mneno."""

from mneno.compaction.base import MemoryCompactor
from mneno.compaction.diff import create_empty_diff

__all__ = ["MemoryCompactor", "create_empty_diff"]
