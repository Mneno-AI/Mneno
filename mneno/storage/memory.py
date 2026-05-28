"""In-memory local storage for the MVP SDK."""

from __future__ import annotations

import builtins

from mneno.models import Memory, utc_now
from mneno.sessions.models import Session


class InMemoryMemoryStore:
    """Simple insertion-ordered in-memory memory store."""

    def __init__(self) -> None:
        self._memories: dict[str, Memory] = {}
        self._sessions: dict[str, Session] = {}

    def add(self, memory: Memory) -> Memory:
        self._memories[memory.id] = memory
        return memory

    def get(self, memory_id: str) -> Memory | None:
        return self._memories.get(memory_id)

    def list(self) -> list[Memory]:
        return list(self._memories.values())

    def update(self, memory: Memory) -> Memory:
        if memory.id not in self._memories:
            raise KeyError(f"Memory not found: {memory.id}")
        self._memories[memory.id] = memory
        return self._memories[memory.id]

    def delete(self, memory_id: str) -> bool:
        deleted = self._memories.pop(memory_id, None) is not None
        if deleted:
            self._sessions = {
                session_id: session.model_copy(
                    update={"memory_ids": [stored_id for stored_id in session.memory_ids if stored_id != memory_id]}
                )
                for session_id, session in self._sessions.items()
            }
        return deleted

    def clear(self) -> None:
        self._memories.clear()
        self._sessions.clear()

    def add_session(self, session: Session) -> Session:
        if session.id in self._sessions:
            raise ValueError(f"Session already exists: {session.id}")
        self._sessions[session.id] = session
        return session

    def get_session(self, session_id: str) -> Session | None:
        return self._sessions.get(session_id)

    def list_sessions(self) -> builtins.list[Session]:
        return list(self._sessions.values())

    def update_session(self, session: Session) -> Session:
        if session.id not in self._sessions:
            raise KeyError(f"Session not found: {session.id}")
        self._sessions[session.id] = session
        return self._sessions[session.id]

    def delete_session(self, session_id: str) -> bool:
        return self._sessions.pop(session_id, None) is not None

    def record_access(self, memory_id: str) -> Memory | None:
        memory = self.get(memory_id)
        if memory is None:
            return None

        now = utc_now()
        updated = memory.model_copy(update={"access_count": memory.access_count + 1, "last_accessed_at": now})
        self._memories[memory_id] = updated
        return updated


InMemoryStorage = InMemoryMemoryStore
