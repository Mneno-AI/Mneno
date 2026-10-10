"""Memory import utilities."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal, TypeVar
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from mneno.io.validation import validate_export_payload
from mneno.models import Memory
from mneno.sessions.models import Session
from mneno.storage.base import MemoryStore
from mneno.storage.transactions import atomic_transaction

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
    warnings: list[str] = Field(default_factory=list)


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
    result = ImportResult()
    memories = _parse_records(payload.get("memories", []), Memory, "memories", mode, result)
    sessions = _parse_records(payload.get("sessions", []), Session, "sessions", mode, result)

    with atomic_transaction(storage) as staged:
        if mode == "replace":
            staged.clear()
        if mode == "append":
            memory_ids = _id_mapping([memory.id for memory in memories], {memory.id for memory in staged.list()})
            session_ids = _id_mapping(
                [session.id for session in sessions], {session.id for session in staged.list_sessions()}
            )
            memories = [_remap_memory(memory, memory_ids, session_ids) for memory in memories]
            sessions = [
                session.model_copy(
                    update={
                        "id": session_ids[session.id],
                        "memory_ids": [memory_ids.get(identifier, identifier) for identifier in session.memory_ids],
                    }
                )
                for session in sessions
            ]
        for memory in memories:
            _import_memory(staged, memory, mode=mode, result=result)
        for session in sessions:
            _import_session(staged, session, mode=mode, result=result)
        _check_relationships(staged, result)
    return result


Record = TypeVar("Record", bound=BaseModel)


def _parse_records(
    records: object, model: type[Record], key: str, mode: ImportMode, result: ImportResult
) -> list[Record]:
    if not isinstance(records, list):
        raise ValueError(f"Invalid export payload: {key} must be a list")
    parsed = []
    seen: set[str] = set()
    for index, record in enumerate(records):
        identifier = record.get("id") if isinstance(record, dict) else None
        if isinstance(identifier, str):
            if identifier in seen:
                raise ValueError(f"Duplicate {key} id in import: {identifier}")
            seen.add(identifier)
        try:
            parsed.append(model.model_validate(record))
        except ValidationError as exc:
            if mode == "replace":
                raise
            result.failed_count += 1
            result.errors.append(f"{key} at index {index} failed validation: {exc}")
    return parsed


def _id_mapping(incoming: list[str], existing: set[str]) -> dict[str, str]:
    reserved = existing | set(incoming)
    mapping = {}
    for identifier in incoming:
        replacement = identifier
        if identifier in existing:
            replacement = str(uuid4())
            while replacement in reserved:
                replacement = str(uuid4())
        reserved.add(replacement)
        mapping[identifier] = replacement
    return mapping


def _remap_memory(memory: Memory, memory_ids: dict[str, str], session_ids: dict[str, str]) -> Memory:
    metadata = dict(memory.metadata)
    # Only compaction's typed lineage is internal; arbitrary provenance metadata stays opaque.
    if memory.source == "compaction" and isinstance(metadata.get("source_memory_ids"), list):
        if not all(isinstance(identifier, str) for identifier in metadata["source_memory_ids"]):
            raise ValueError("Compaction lineage must contain memory ID strings")
        metadata["source_memory_ids"] = [
            memory_ids.get(identifier, identifier) for identifier in metadata["source_memory_ids"]
        ]
    return memory.model_copy(
        update={
            "id": memory_ids[memory.id],
            "session_id": session_ids.get(memory.session_id, memory.session_id)
            if memory.session_id is not None
            else None,
            "superseded_by": memory_ids.get(memory.superseded_by, memory.superseded_by)
            if memory.superseded_by is not None
            else None,
            "conflicts_with": [memory_ids.get(identifier, identifier) for identifier in memory.conflicts_with],
            "audit": [
                event.model_copy(
                    update={
                        "related_memory_ids": [
                            memory_ids.get(identifier, identifier) for identifier in event.related_memory_ids
                        ]
                    }
                )
                for event in memory.audit
            ],
            "metadata": metadata,
        }
    )


def _check_relationships(storage: MemoryStore, result: ImportResult) -> None:
    memories = {memory.id: memory for memory in storage.list()}
    sessions = {session.id: session for session in storage.list_sessions()}
    for memory in memories.values():
        if memory.session_id is not None:
            session = sessions.get(memory.session_id)
            if session is None:
                result.warnings.append(f"Memory {memory.id} references missing session {memory.session_id}")
            elif memory.id not in session.memory_ids:
                updated_session = session.model_copy(update={"memory_ids": [*session.memory_ids, memory.id]})
                storage.update_session(updated_session)
                sessions[session.id] = updated_session
        references = [
            *memory.conflicts_with,
            *[identifier for event in memory.audit for identifier in event.related_memory_ids],
        ]
        if memory.superseded_by is not None:
            references.append(memory.superseded_by)
        lineage = memory.metadata.get("source_memory_ids")
        if memory.source == "compaction" and isinstance(lineage, list):
            if not all(isinstance(identifier, str) for identifier in lineage):
                raise ValueError("Compaction lineage must contain memory ID strings")
            references.extend(lineage)
        for identifier in references:
            if identifier not in memories:
                result.warnings.append(f"Memory {memory.id} retains unresolved historical reference {identifier}")
    for session in sessions.values():
        for identifier in session.memory_ids:
            member = memories.get(identifier)
            if member is None:
                result.warnings.append(f"Session {session.id} retains missing historical memory {identifier}")
            elif member.session_id != session.id:
                raise ValueError(f"Inconsistent session membership: memory {identifier}, session {session.id}")


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

    storage.add(memory)
    result.imported_count += 1


def _import_session(storage: MemoryStore, session: Session, *, mode: ImportMode, result: ImportResult) -> None:
    existing = storage.get_session(session.id)
    if mode == "skip_existing" and existing is not None:
        result.skipped_session_count += 1
        return

    if mode == "overwrite" and existing is not None:
        storage.update_session(session)
        result.overwritten_session_count += 1
        return

    storage.add_session(session)
    result.imported_session_count += 1
