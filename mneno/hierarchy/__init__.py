"""Hierarchical memory organization."""

from mneno.hierarchy.layers import LAYER_PRIORITY, LAYER_SCORE_ADJUSTMENT, MemoryLayer, infer_layer
from mneno.hierarchy.policies import LayerPolicy
from mneno.hierarchy.transitions import DEMOTION_TARGETS, PROMOTION_TARGETS

__all__ = [
    "DEMOTION_TARGETS",
    "HierarchyEvaluationResult",
    "HierarchyManager",
    "LAYER_PRIORITY",
    "LAYER_SCORE_ADJUSTMENT",
    "LayerPolicy",
    "MemoryLayer",
    "PROMOTION_TARGETS",
    "infer_layer",
]


def __getattr__(name: str) -> object:
    if name in {"HierarchyEvaluationResult", "HierarchyManager"}:
        from mneno.hierarchy.manager import HierarchyEvaluationResult, HierarchyManager

        return {"HierarchyEvaluationResult": HierarchyEvaluationResult, "HierarchyManager": HierarchyManager}[name]
    raise AttributeError(name)
