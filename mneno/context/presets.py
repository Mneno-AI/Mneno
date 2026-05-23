"""Built-in context policy presets."""

from __future__ import annotations

from enum import StrEnum

from mneno.context.policies import ContextPolicy
from mneno.models import MemoryType


class ContextPreset(StrEnum):
    """Built-in context policy presets."""

    CHEAP = "cheap"
    BALANCED = "balanced"
    HIGH_RECALL = "high_recall"
    AGENT_STATE = "agent_state"


def get_context_policy(preset: ContextPreset | str) -> ContextPolicy:
    """Return a context policy for a built-in preset."""
    try:
        resolved = ContextPreset(preset)
    except ValueError as exc:
        allowed = ", ".join(item.value for item in ContextPreset)
        raise ValueError(f"Unknown context preset '{preset}'. Expected one of: {allowed}") from exc

    if resolved is ContextPreset.CHEAP:
        return ContextPolicy(
            max_tokens=400,
            reserve_tokens=100,
            strategy="score",
            min_score=0.35,
            max_items=5,
            dedupe=True,
        )
    if resolved is ContextPreset.HIGH_RECALL:
        return ContextPolicy(
            max_tokens=2500,
            reserve_tokens=300,
            strategy="score",
            min_score=0.05,
            max_items=40,
            dedupe=True,
        )
    if resolved is ContextPreset.AGENT_STATE:
        return ContextPolicy(
            max_tokens=1000,
            reserve_tokens=200,
            strategy="importance",
            min_score=0.1,
            max_items=20,
            dedupe=True,
            preserve_memory_types=[MemoryType.OPERATIONAL, MemoryType.PREFERENCE],
        )
    return ContextPolicy(
        max_tokens=1200,
        reserve_tokens=200,
        strategy="score",
        min_score=0.15,
        max_items=15,
        dedupe=True,
    )
