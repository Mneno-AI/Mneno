"""Base extraction models and interfaces."""

from __future__ import annotations

from typing import Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, field_validator

from mneno.models import MemoryType, normalize_tags

ExtractionMode = Literal["deterministic", "llm"]


class ExtractedMemory(BaseModel):
    """A structured memory extracted from raw text."""

    model_config = ConfigDict(extra="forbid")

    content: str = Field(min_length=1)
    memory_type: MemoryType = MemoryType.SEMANTIC
    importance: float = Field(ge=0.0, le=1.0)
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    reason: str = Field(min_length=1)
    memory_id: str | None = None

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, tags: list[str]) -> list[str]:
        """Normalize extracted memory tags."""
        return normalize_tags(tags)


class ExtractionResult(BaseModel):
    """Result details for a memory extraction operation."""

    model_config = ConfigDict(extra="forbid")

    source_text: str
    mode: ExtractionMode
    extracted: list[ExtractedMemory] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    provider_name: str | None = None
    prompt_version: str | None = None
    trace_id: str | None = None


class MemoryExtractor(Protocol):
    """Protocol for memory extraction implementations."""

    def extract(self, text: str) -> ExtractionResult:
        """Extract structured memories from text."""
