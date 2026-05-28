"""Session models for temporal memory organization."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator

from mneno.models import normalize_tags, utc_now

SessionStatus = Literal["active", "closed", "archived"]


class Session(BaseModel):
    """A lightweight temporal grouping for memories."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(default_factory=lambda: str(uuid4()))
    title: str = Field(min_length=1)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    metadata: dict[str, Any] = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list)
    memory_ids: list[str] = Field(default_factory=list)
    summary: str | None = None
    status: SessionStatus = "active"

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, tags: list[str]) -> list[str]:
        """Normalize session tags."""
        return normalize_tags(tags)
