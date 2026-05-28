"""Policies for hierarchical memory lifecycle management."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class LayerPolicy(BaseModel):
    """Policy controlling deterministic hierarchy evaluation."""

    model_config = ConfigDict(extra="forbid")

    short_term_ttl_days: int = Field(default=7, ge=0)
    working_ttl_days: int = Field(default=14, ge=0)
    episodic_ttl_days: int | None = Field(default=None, ge=0)
    semantic_ttl_days: int | None = Field(default=None, ge=0)
    operational_ttl_days: int | None = Field(default=None, ge=0)
    auto_promote: bool = True
    auto_demote: bool = True
    archive_stale: bool = True
    promotion_threshold: float = Field(default=0.75, ge=0.0, le=1.0)
    demotion_threshold: float = Field(default=0.25, ge=0.0, le=1.0)
