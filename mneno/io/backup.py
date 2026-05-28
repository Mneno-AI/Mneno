"""Backup and restore helpers."""

from __future__ import annotations

from pathlib import Path

from mneno.io.export import export_memories
from mneno.io.importers import ImportMode, ImportResult, import_memories_from_json
from mneno.models import Memory, utc_now
from mneno.sessions.models import Session
from mneno.storage.base import MemoryStore


def default_backup_path() -> Path:
    """Return a timestamped default backup path."""
    timestamp = utc_now().strftime("%Y%m%d-%H%M%S")
    return Path("backups") / f"mneno-backup-{timestamp}.json"


def backup_memories(
    memories: list[Memory],
    path: str | Path | None = None,
    *,
    sessions: list[Session] | None = None,
) -> Path:
    """Write a backup export and return its path."""
    backup_path = Path(path) if path is not None else default_backup_path()
    export_memories(memories, backup_path, sessions=sessions)
    return backup_path


def restore_memories(storage: MemoryStore, path: str | Path, *, mode: ImportMode = "replace") -> ImportResult:
    """Restore memories from a backup file."""
    if mode not in {"replace", "append"}:
        raise ValueError("restore mode must be 'replace' or 'append'")
    return import_memories_from_json(storage, path, mode=mode)
