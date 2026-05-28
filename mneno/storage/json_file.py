"""JSON file storage backend for local persistence."""

from __future__ import annotations

import builtins
import json
from pathlib import Path
from typing import Any

from mneno.io.validation import STORAGE_FORMAT_VERSION, validate_storage_payload
from mneno.models import Memory
from mneno.sessions.models import Session


class JSONFileStorage:
    """Persist all memories in one human-readable JSON file."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._memories: dict[str, Memory]
        self._sessions: dict[str, Session]
        self._memories, self._sessions = self._load()

    def add(self, memory: Memory) -> Memory:
        if memory.id in self._memories:
            raise ValueError(f"Memory already exists: {memory.id}")
        self._memories[memory.id] = memory
        self._write()
        return memory

    def get(self, memory_id: str) -> Memory | None:
        return self._memories.get(memory_id)

    def list(self) -> list[Memory]:
        return list(self._memories.values())

    def update(self, memory: Memory) -> Memory:
        if memory.id not in self._memories:
            raise KeyError(f"Memory not found: {memory.id}")
        self._memories[memory.id] = memory
        self._write()
        return memory

    def delete(self, memory_id: str) -> bool:
        deleted = self._memories.pop(memory_id, None) is not None
        if deleted:
            self._write()
        return deleted

    def clear(self) -> None:
        self._memories.clear()
        self._sessions.clear()
        self._write()

    def add_session(self, session: Session) -> Session:
        if session.id in self._sessions:
            raise ValueError(f"Session already exists: {session.id}")
        self._sessions[session.id] = session
        self._write()
        return session

    def get_session(self, session_id: str) -> Session | None:
        return self._sessions.get(session_id)

    def list_sessions(self) -> builtins.list[Session]:
        return list(self._sessions.values())

    def update_session(self, session: Session) -> Session:
        if session.id not in self._sessions:
            raise KeyError(f"Session not found: {session.id}")
        self._sessions[session.id] = session
        self._write()
        return session

    def delete_session(self, session_id: str) -> bool:
        deleted = self._sessions.pop(session_id, None) is not None
        if deleted:
            self._write()
        return deleted

    def _load(self) -> tuple[dict[str, Memory], dict[str, Session]]:
        if not self.path.exists():
            return {}, {}

        raw = self.path.read_text(encoding="utf-8")
        if not raw.strip():
            return {}, {}

        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON storage file: {self.path}") from exc

        if not isinstance(payload, dict):
            raise ValueError(f"Invalid JSON storage file format: {self.path}")
        validate_storage_payload(payload)

        loaded: dict[str, Memory] = {}
        for item in payload["memories"]:
            memory = Memory.model_validate(item)
            if memory.id in loaded:
                raise ValueError(f"Duplicate memory id in JSON storage file: {memory.id}")
            loaded[memory.id] = memory

        sessions: dict[str, Session] = {}
        for item in payload.get("sessions", []):
            session = Session.model_validate(item)
            if session.id in sessions:
                raise ValueError(f"Duplicate session id in JSON storage file: {session.id}")
            sessions[session.id] = session
        return loaded, sessions

    def _write(self) -> None:
        payload: dict[str, Any] = {
            "version": STORAGE_FORMAT_VERSION,
            "memories": [memory.model_dump(mode="json") for memory in self._memories.values()],
            "sessions": [session.model_dump(mode="json") for session in self._sessions.values()],
        }
        temp_path = self.path.with_name(f"{self.path.name}.tmp")
        temp_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        temp_path.replace(self.path)
