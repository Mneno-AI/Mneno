"""Trace event models."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from mneno.models import utc_now


class TraceEvent(BaseModel):
    """A single local trace event."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(default_factory=lambda: str(uuid4()))
    trace_id: str
    operation: str
    event_type: str
    timestamp: datetime = Field(default_factory=utc_now)
    message: str = Field(min_length=1)
    memory_id: str | None = None
    session_id: str | None = None
    data: dict[str, Any] = Field(default_factory=dict)
