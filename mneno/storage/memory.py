"""In-memory local storage for the MVP SDK."""

from __future__ import annotations

import builtins
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from copy import copy
from functools import wraps
from threading import RLock, get_ident
from typing import ParamSpec, TypeVar, cast

from mneno.models import Memory, utc_now
from mneno.sessions.models import Session

P = ParamSpec("P")
T = TypeVar("T")


def _locked(method: Callable[P, T]) -> Callable[P, T]:
    @wraps(method)
    def call(*args: P.args, **kwargs: P.kwargs) -> T:
        storage = cast(InMemoryMemoryStore, args[0])
        with storage._lock:
            if storage._transaction_owner == get_ident() and method.__name__ not in {
                "get",
                "list",
                "get_session",
                "list_sessions",
            }:
                raise RuntimeError("Use the staged store inside a memory transaction")
            return method(*args, **kwargs)

    return call


class InMemoryMemoryStore:
    """Simple insertion-ordered in-memory memory store."""

    def __init__(self) -> None:
        self._memories: dict[str, Memory] = {}
        self._sessions: dict[str, Session] = {}
        self._lock = RLock()
        self._transaction_owner: int | None = None

    @contextmanager
    def transaction(self) -> Iterator[InMemoryMemoryStore]:
        """Stage a batch privately; a failed batch leaves the original state intact."""
        with self._lock:
            if self._transaction_owner is not None:
                raise RuntimeError("Use the staged store inside a memory transaction")
            staged = copy(self)
            staged._lock = RLock()
            staged._transaction_owner = None
            staged._memories = {key: value.model_copy(deep=True) for key, value in self._memories.items()}
            staged._sessions = {key: value.model_copy(deep=True) for key, value in self._sessions.items()}
            self._transaction_owner = get_ident()
            try:
                yield staged
                self._memories, self._sessions = staged._validated_snapshot()
            finally:
                self._transaction_owner = None

    def _validated_snapshot(self) -> tuple[dict[str, Memory], dict[str, Session]]:
        memories = {
            key: Memory.model_validate(value.model_dump()).model_copy(deep=True)
            for key, value in self._memories.items()
        }
        sessions = {
            key: Session.model_validate(value.model_dump()).model_copy(deep=True)
            for key, value in self._sessions.items()
        }
        if any(key != value.id for key, value in memories.items()) or any(
            key != value.id for key, value in sessions.items()
        ):
            raise ValueError("Snapshot record identity changed without a matching storage key")
        return memories, sessions

    @_locked
    def add(self, memory: Memory) -> Memory:
        if memory.id in self._memories:
            raise ValueError(f"Memory already exists: {memory.id}")
        self._memories[memory.id] = memory
        return memory

    @_locked
    def get(self, memory_id: str) -> Memory | None:
        return self._memories.get(memory_id)

    @_locked
    def list(self) -> list[Memory]:
        return list(self._memories.values())

    @_locked
    def update(self, memory: Memory) -> Memory:
        if memory.id not in self._memories:
            raise KeyError(f"Memory not found: {memory.id}")
        self._memories[memory.id] = memory
        return self._memories[memory.id]

    @_locked
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

    @_locked
    def clear(self) -> None:
        self._memories.clear()
        self._sessions.clear()

    @_locked
    def add_session(self, session: Session) -> Session:
        if session.id in self._sessions:
            raise ValueError(f"Session already exists: {session.id}")
        self._sessions[session.id] = session
        return session

    @_locked
    def get_session(self, session_id: str) -> Session | None:
        return self._sessions.get(session_id)

    @_locked
    def list_sessions(self) -> builtins.list[Session]:
        return list(self._sessions.values())

    @_locked
    def update_session(self, session: Session) -> Session:
        if session.id not in self._sessions:
            raise KeyError(f"Session not found: {session.id}")
        self._sessions[session.id] = session
        return self._sessions[session.id]

    @_locked
    def delete_session(self, session_id: str) -> bool:
        return self._sessions.pop(session_id, None) is not None

    @_locked
    def record_access(self, memory_id: str) -> Memory | None:
        memory = self.get(memory_id)
        if memory is None:
            return None

        now = utc_now()
        updated = memory.model_copy(update={"access_count": memory.access_count + 1, "last_accessed_at": now})
        self._memories[memory_id] = updated
        return updated


InMemoryStorage = InMemoryMemoryStore
