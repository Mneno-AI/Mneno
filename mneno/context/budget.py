"""Context budget configuration and token estimation."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

ContextBudgetStrategy = Literal["score", "recency", "importance"]


class ContextBudget(BaseModel):
    """Backward-compatible budget configuration for context building."""

    model_config = ConfigDict(extra="forbid")

    max_tokens: int = Field(gt=0)
    reserve_tokens: int = Field(default=0, ge=0)
    strategy: ContextBudgetStrategy = "score"

    @model_validator(mode="after")
    def validate_available_tokens(self) -> ContextBudget:
        """Ensure reserve tokens do not consume the whole budget."""
        if self.reserve_tokens >= self.max_tokens:
            raise ValueError("reserve_tokens must be smaller than max_tokens")
        return self

    @property
    def available_tokens(self) -> int:
        """Return the budget available for memory text."""
        return self.max_tokens - self.reserve_tokens


def estimate_tokens(text: str) -> int:
    """Estimate tokens locally without tokenizer dependencies."""
    return max(1, len(text.split()))
