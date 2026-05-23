"""Compaction foundations for Mneno."""

from mneno.compaction.base import MemoryCompactor
from mneno.compaction.diff import add_decision, create_empty_diff
from mneno.compaction.engine import CompactionEngine
from mneno.compaction.policies import CompactionPolicy

__all__ = ["CompactionEngine", "CompactionPolicy", "MemoryCompactor", "add_decision", "create_empty_diff"]
