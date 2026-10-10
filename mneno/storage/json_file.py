"""Atomic JSON snapshots with cooperating-writer locking and stale-write rejection."""

from __future__ import annotations

import builtins
import json
import os
import sys
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from hashlib import sha256
from pathlib import Path
from threading import RLock, get_ident

from mneno.io.validation import STORAGE_FORMAT_VERSION, validate_storage_payload
from mneno.models import Memory
from mneno.sessions.models import Session
from mneno.storage.memory import InMemoryMemoryStore
from mneno.storage.transactions import StorageCommitError, StorageConflictError


class JSONFileStorage:
    """Persist snapshots; stale writers must refresh with a read before retrying."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path).resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = RLock()
        self._transaction_owner: int | None = None
        with self._locked():
            self._refresh()

    @contextmanager
    def _locked(self) -> Iterator[None]:
        if self._transaction_owner == get_ident():
            raise RuntimeError("Use the staged store inside a JSON transaction")
        # Lock a stable sidecar: replacing the data file must not replace the lock inode.
        with self._lock, self.path.with_name(self.path.name + ".lock").open("a+b") as lock_file:
            if sys.platform == "win32":
                import msvcrt

                if lock_file.seek(0, os.SEEK_END) == 0:
                    lock_file.write(b"0")
                    lock_file.flush()
                lock_file.seek(0)
                msvcrt.locking(lock_file.fileno(), msvcrt.LK_LOCK, 1)
            else:
                import fcntl

                fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                if sys.platform == "win32":
                    lock_file.seek(0)
                    msvcrt.locking(lock_file.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)

    def _revision(self) -> bytes:
        return sha256(self.path.read_bytes() if self.path.exists() else b"").digest()

    def _refresh(self) -> None:
        self._memories, self._sessions = self._load()
        self._committed_revision = self._revision()

    @contextmanager
    def transaction(self) -> Iterator[InMemoryMemoryStore]:
        """Reject stale snapshots, then stage and commit one complete batch under lock."""
        with self._locked():
            if self._revision() != self._committed_revision:
                raise StorageConflictError("JSON snapshot changed; read the latest state and retry")
            self._refresh()
            staged = InMemoryMemoryStore()
            staged._memories = {key: value.model_copy(deep=True) for key, value in self._memories.items()}
            staged._sessions = {key: value.model_copy(deep=True) for key, value in self._sessions.items()}
            self._transaction_owner = get_ident()
            try:
                yield staged
                self._write(staged)
            finally:
                self._transaction_owner = None

    def add(self, memory: Memory) -> Memory:
        with self.transaction() as staged:
            staged.add(memory)
        return memory

    def get(self, memory_id: str) -> Memory | None:
        with self._locked():
            self._refresh()
            memory = self._memories.get(memory_id)
            return memory.model_copy(deep=True) if memory is not None else None

    def list(self) -> list[Memory]:
        with self._locked():
            self._refresh()
            return [memory.model_copy(deep=True) for memory in self._memories.values()]

    def update(self, memory: Memory) -> Memory:
        with self.transaction() as staged:
            staged.update(memory)
        return memory

    def delete(self, memory_id: str) -> bool:
        with self.transaction() as staged:
            deleted = staged.delete(memory_id)
        return deleted

    def clear(self) -> None:
        with self.transaction() as staged:
            staged.clear()

    def add_session(self, session: Session) -> Session:
        with self.transaction() as staged:
            staged.add_session(session)
        return session

    def get_session(self, session_id: str) -> Session | None:
        with self._locked():
            self._refresh()
            session = self._sessions.get(session_id)
            return session.model_copy(deep=True) if session is not None else None

    def list_sessions(self) -> builtins.list[Session]:
        with self._locked():
            self._refresh()
            return [session.model_copy(deep=True) for session in self._sessions.values()]

    def update_session(self, session: Session) -> Session:
        with self.transaction() as staged:
            staged.update_session(session)
        return session

    def delete_session(self, session_id: str) -> bool:
        with self.transaction() as staged:
            deleted = staged.delete_session(session_id)
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

    def _write(self, staged: InMemoryMemoryStore) -> None:
        memories, sessions = staged._validated_snapshot()
        payload = {
            "version": STORAGE_FORMAT_VERSION,
            "memories": [memory.model_dump(mode="json") for memory in memories.values()],
            "sessions": [session.model_dump(mode="json") for session in sessions.values()],
        }
        serialized = json.dumps(payload, indent=2, sort_keys=True) + "\n"
        revision = sha256(serialized.encode("utf-8")).digest()
        committed = False
        temporary: Path | None = None
        directory_fd = os.open(self.path.parent, os.O_RDONLY) if sys.platform != "win32" else None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=self.path.parent,
                prefix=self.path.name + ".",
                suffix=".tmp",
                delete=False,
            ) as output:
                temporary = Path(output.name)
                output.write(serialized)
                output.flush()
                os.fsync(output.fileno())
            temporary.replace(self.path)
            committed = True
            # Rename is the commit boundary. A later sync failure cannot undo a committed snapshot.
            temporary = None
            self._memories, self._sessions = memories, sessions
            self._committed_revision = revision
            if directory_fd is not None:
                try:
                    os.fsync(directory_fd)
                except OSError as exc:
                    raise StorageCommitError("Snapshot committed, but directory synchronization failed") from exc
        finally:
            if directory_fd is not None:
                try:
                    os.close(directory_fd)
                except OSError as exc:
                    if committed:
                        raise StorageCommitError("Snapshot committed, but directory close failed") from exc
                    raise
            if temporary is not None:
                temporary.unlink(missing_ok=True)
