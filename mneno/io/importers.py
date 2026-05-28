"""Memory import utilities."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from mneno.io.validation import validate_export_payload
from mneno.models import Memory
from mneno.sessions.models import Session
from mneno.storage.base import MemoryStore

ImportMode = Literal["append", "replace", "skip_existing", "overwrite"]


class ImportResult(BaseModel):
    """Result details for a memory import operation."""

    model_config = ConfigDict(extra="forbid")

    imported_count: int = Field(default=0, ge=0)
    skipped_count: int = Field(default=0, ge=0)
    overwritten_count: int = Field(default=0, ge=0)
    imported_session_count: int = Field(default=0, ge=0)
    skipped_session_count: int = Field(default=0, ge=0)
    overwritten_session_count: int = Field(default=0, ge=0)
    failed_count: int = Field(default=0, ge=0)
    errors: list[str] = Field(default_factory=list)


def load_export_payload(path: str | Path) -> dict[str, object]:
    """Load and validate a memory export JSON file."""
    input_path = Path(path)
    try:
        payload = json.loads(input_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid export JSON file: {input_path}") from exc

    if not isinstance(payload, dict):
        raise ValueError(f"Invalid export payload in {input_path}: expected object")
    validate_export_payload(payload)
    return payload


def import_memories_from_payload(
    storage: MemoryStore,
    payload: dict[str, object],
    *,
    mode: ImportMode = "append",
) -> ImportResult:
    """Import memories from a validated export payload into storage."""
    if mode not in {"append", "replace", "skip_existing", "overwrite"}:
        raise ValueError("import mode must be 'append', 'replace', 'skip_existing', or 'overwrite'")
    validate_export_payload(payload)
    if mode == "replace":
        storage.clear()

    result = ImportResult()
    memories = payload["memories"]
    if not isinstance(memories, list):
        raise ValueError("Invalid export payload: memories must be a list")

    for index, raw_memory in enumerate(memories):
        try:
            memory = Memory.model_validate(raw_memory)
            _import_memory(storage, memory, mode=mode, result=result)
        except ValidationError as exc:
            result.failed_count += 1
            result.errors.append(f"Memory at index {index} failed validation: {exc}")
        except (KeyError, ValueError) as exc:
            result.failed_count += 1
            result.errors.append(f"Memory at index {index} failed import: {exc}")

    sessions = payload.get("sessions", [])
    if not isinstance(sessions, list):
        raise ValueError("Invalid export payload: sessions must be a list")
    for index, raw_session in enumerate(sessions):
        try:
            session = Session.model_validate(raw_session)
            _import_session(storage, session, mode=mode, result=result)
        except ValidationError as exc:
            result.failed_count += 1
            result.errors.append(f"Session at index {index} failed validation: {exc}")
        except (KeyError, ValueError) as exc:
            result.failed_count += 1
            result.errors.append(f"Session at index {index} failed import: {exc}")
    return result


def import_memories_from_json(storage: MemoryStore, path: str | Path, *, mode: ImportMode = "append") -> ImportResult:
    """Import memories from an export JSON file into storage."""
    return import_memories_from_payload(storage, load_export_payload(path), mode=mode)


def _import_memory(storage: MemoryStore, memory: Memory, *, mode: ImportMode, result: ImportResult) -> None:
    existing = storage.get(memory.id)
    if mode == "skip_existing" and existing is not None:
        result.skipped_count += 1
        return

    if mode == "overwrite" and existing is not None:
        storage.update(memory)
        result.overwritten_count += 1
        return

    if mode == "append" and existing is not None:
        memory = _copy_with_new_id(storage, memory)

    storage.add(memory)
    result.imported_count += 1


def _copy_with_new_id(storage: MemoryStore, memory: Memory) -> Memory:
    copied = memory
    while storage.get(copied.id) is not None:
        copied = memory.model_copy(update={"id": str(uuid4())})
    return copied


def _import_session(storage: MemoryStore, session: Session, *, mode: ImportMode, result: ImportResult) -> None:
    existing = storage.get_session(session.id)
    if mode == "skip_existing" and existing is not None:
        result.skipped_session_count += 1
        return

    if mode == "overwrite" and existing is not None:
        storage.update_session(session)
        result.overwritten_session_count += 1
        return

    if mode == "append" and existing is not None:
        session = _copy_session_with_new_id(storage, session)

    storage.add_session(session)
    result.imported_session_count += 1


def _copy_session_with_new_id(storage: MemoryStore, session: Session) -> Session:
    copied = session
    while storage.get_session(copied.id) is not None:
        copied = session.model_copy(update={"id": str(uuid4())})
    return copied
