"""Policy model for context building."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator

from mneno.context.budget import ContextBudget, ContextBudgetStrategy
from mneno.models import MemoryType, normalize_tags


class ContextPolicy(BaseModel):
    """Controls deterministic context building behavior."""

    model_config = ConfigDict(extra="forbid")

    max_tokens: int = Field(gt=0)
    reserve_tokens: int = Field(default=0, ge=0)
    strategy: ContextBudgetStrategy = "score"
    min_score: float = Field(default=0.0, ge=0.0, le=1.0)
    max_items: int | None = Field(default=None, gt=0)
    dedupe: bool = True
    preserve_memory_types: list[MemoryType] = Field(default_factory=list)
    preserve_tags: list[str] = Field(default_factory=list)
    include_score_reasons: bool = True

    @model_validator(mode="after")
    def validate_available_tokens(self) -> ContextPolicy:
        """Ensure reserve tokens do not consume the whole budget."""
        if self.reserve_tokens >= self.max_tokens:
            raise ValueError("reserve_tokens must be smaller than max_tokens")
        self.preserve_tags = normalize_tags(self.preserve_tags)
        return self

    @property
    def available_tokens(self) -> int:
        """Return the budget available for memory text."""
        return self.max_tokens - self.reserve_tokens

    @classmethod
    def from_budget(cls, budget: int | ContextBudget) -> ContextPolicy:
        """Build a context policy from the backward-compatible budget API."""
        if isinstance(budget, int):
            return cls(max_tokens=budget, min_score=0.05)
        return cls(
            max_tokens=budget.max_tokens,
            reserve_tokens=budget.reserve_tokens,
            strategy=budget.strategy,
            min_score=0.05,
        )
