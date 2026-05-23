"""SQLite storage backend for local persistence."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from mneno.models import Memory

SCHEMA_VERSION = 1


class SQLiteStorage:
    """Persist memories in a local SQLite database."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def add(self, memory: Memory) -> Memory:
        try:
            with self._connect() as connection:
                connection.execute(
                    """
                    INSERT INTO memories (id, payload, created_at, updated_at)
                    VALUES (?, ?, ?, ?)
                    """,
                    (
                        memory.id,
                        _serialize_memory(memory),
                        memory.created_at.isoformat(),
                        memory.updated_at.isoformat(),
                    ),
                )
        except sqlite3.IntegrityError as exc:
            raise ValueError(f"Memory already exists: {memory.id}") from exc
        return memory

    def get(self, memory_id: str) -> Memory | None:
        with self._connect() as connection:
            row = connection.execute("SELECT payload FROM memories WHERE id = ?", (memory_id,)).fetchone()
        if row is None:
            return None
        return _deserialize_memory(row["payload"])

    def list(self) -> list[Memory]:
        with self._connect() as connection:
            rows = connection.execute("SELECT payload FROM memories ORDER BY created_at, id").fetchall()
        return [_deserialize_memory(row["payload"]) for row in rows]

    def update(self, memory: Memory) -> Memory:
        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE memories
                SET payload = ?, created_at = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    _serialize_memory(memory),
                    memory.created_at.isoformat(),
                    memory.updated_at.isoformat(),
                    memory.id,
                ),
            )
        if cursor.rowcount == 0:
            raise KeyError(f"Memory not found: {memory.id}")
        return memory

    def delete(self, memory_id: str) -> bool:
        with self._connect() as connection:
            cursor = connection.execute("DELETE FROM memories WHERE id = ?", (memory_id,))
        return cursor.rowcount > 0

    def clear(self) -> None:
        with self._connect() as connection:
            connection.execute("DELETE FROM memories")

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS memories (
                  id TEXT PRIMARY KEY,
                  payload TEXT NOT NULL,
                  created_at TEXT NOT NULL,
                  updated_at TEXT NOT NULL
                )
                """
            )
            connection.execute("CREATE INDEX IF NOT EXISTS idx_memories_created_at ON memories(created_at)")
            connection.execute("CREATE INDEX IF NOT EXISTS idx_memories_updated_at ON memories(updated_at)")

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        return connection


def _serialize_memory(memory: Memory) -> str:
    return json.dumps(memory.model_dump(mode="json"), sort_keys=True)


def _deserialize_memory(payload: str) -> Memory:
    return Memory.model_validate(json.loads(payload))
