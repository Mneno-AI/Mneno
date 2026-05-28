"""Memory hierarchy layers."""

from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mneno.models import MemoryType


class MemoryLayer(StrEnum):
    """Cognitive memory layers used for lifecycle-aware retrieval."""

    SHORT_TERM = "short_term"
    WORKING = "working"
    EPISODIC = "episodic"
    SEMANTIC = "semantic"
    OPERATIONAL = "operational"
    ARCHIVED = "archived"


def infer_layer(memory_type: MemoryType | str) -> MemoryLayer:
    """Infer a default layer from a memory type."""
    from mneno.models import MemoryType

    resolved_type = MemoryType(memory_type)
    if resolved_type is MemoryType.OPERATIONAL:
        return MemoryLayer.OPERATIONAL
    if resolved_type in {MemoryType.PREFERENCE, MemoryType.SEMANTIC}:
        return MemoryLayer.SEMANTIC
    if resolved_type is MemoryType.EPISODIC:
        return MemoryLayer.EPISODIC
    return MemoryLayer.EPISODIC


LAYER_PRIORITY: dict[MemoryLayer, int] = {
    MemoryLayer.OPERATIONAL: 6,
    MemoryLayer.WORKING: 5,
    MemoryLayer.SEMANTIC: 4,
    MemoryLayer.EPISODIC: 3,
    MemoryLayer.SHORT_TERM: 2,
    MemoryLayer.ARCHIVED: 1,
}


LAYER_SCORE_ADJUSTMENT: dict[MemoryLayer, float] = {
    MemoryLayer.OPERATIONAL: 0.12,
    MemoryLayer.WORKING: 0.08,
    MemoryLayer.SEMANTIC: 0.04,
    MemoryLayer.EPISODIC: 0.0,
    MemoryLayer.SHORT_TERM: -0.02,
    MemoryLayer.ARCHIVED: -0.5,
}
