"""Base storage interfaces."""

from __future__ import annotations

import builtins
from typing import Protocol

from mneno.models import Memory
from mneno.sessions.models import Session


class MemoryStore(Protocol):
    """Protocol for memory storage backends."""

    def add(self, memory: Memory) -> Memory:
        """Persist a memory."""

    def get(self, memory_id: str) -> Memory | None:
        """Return a memory by ID."""

    def list(self) -> list[Memory]:
        """Return all memories."""

    def update(self, memory: Memory) -> Memory:
        """Replace an existing memory."""

    def delete(self, memory_id: str) -> bool:
        """Delete a memory by ID."""

    def clear(self) -> None:
        """Delete all memories."""

    def add_session(self, session: Session) -> Session:
        """Persist a session."""

    def get_session(self, session_id: str) -> Session | None:
        """Return a session by ID."""

    def list_sessions(self) -> builtins.list[Session]:
        """Return all sessions."""

    def update_session(self, session: Session) -> Session:
        """Replace an existing session."""

    def delete_session(self, session_id: str) -> bool:
        """Delete a session by ID."""
