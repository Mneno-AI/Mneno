"""Hierarchy transition helpers."""

from __future__ import annotations

from mneno.hierarchy.layers import MemoryLayer

PROMOTION_TARGETS: dict[MemoryLayer, MemoryLayer] = {
    MemoryLayer.SHORT_TERM: MemoryLayer.EPISODIC,
    MemoryLayer.EPISODIC: MemoryLayer.SEMANTIC,
}


DEMOTION_TARGETS: dict[MemoryLayer, MemoryLayer] = {
    MemoryLayer.WORKING: MemoryLayer.EPISODIC,
    MemoryLayer.EPISODIC: MemoryLayer.ARCHIVED,
    MemoryLayer.SHORT_TERM: MemoryLayer.ARCHIVED,
}


def is_valid_manual_transition(source: MemoryLayer, target: MemoryLayer) -> bool:
    """Return whether a manual layer transition is allowed."""
    if source == target:
        return False
    if source is MemoryLayer.ARCHIVED and target is not MemoryLayer.ARCHIVED:
        return True
    return target in set(MemoryLayer)


def is_promotional(source: MemoryLayer, target: MemoryLayer) -> bool:
    """Return whether target is considered a promotion from source."""
    order = {
        MemoryLayer.ARCHIVED: 0,
        MemoryLayer.SHORT_TERM: 1,
        MemoryLayer.EPISODIC: 2,
        MemoryLayer.SEMANTIC: 3,
        MemoryLayer.WORKING: 4,
        MemoryLayer.OPERATIONAL: 5,
    }
    return order[target] > order[source]
