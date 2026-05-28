"""Operation trace models."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from mneno.models import utc_now
from mneno.observability.events import TraceEvent

TraceStatus = Literal["success", "error"]


class OperationTrace(BaseModel):
    """A local trace for one Mneno operation."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(default_factory=lambda: str(uuid4()))
    operation: str
    started_at: datetime = Field(default_factory=utc_now)
    completed_at: datetime | None = None
    duration_ms: float | None = Field(default=None, ge=0.0)
    events: list[TraceEvent] = Field(default_factory=list)
    status: TraceStatus = "success"
    summary: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
