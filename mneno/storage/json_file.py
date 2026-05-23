"""JSON file storage backend for local persistence."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from mneno.io.validation import STORAGE_FORMAT_VERSION, validate_storage_payload
from mneno.models import Memory


class JSONFileStorage:
    """Persist all memories in one human-readable JSON file."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._memories: dict[str, Memory] = self._load()

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
        self._write()

    def _load(self) -> dict[str, Memory]:
        if not self.path.exists():
            return {}

        raw = self.path.read_text(encoding="utf-8")
        if not raw.strip():
            return {}

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
        return loaded

    def _write(self) -> None:
        payload: dict[str, Any] = {
            "version": STORAGE_FORMAT_VERSION,
            "memories": [memory.model_dump(mode="json") for memory in self._memories.values()],
        }
        temp_path = self.path.with_name(f"{self.path.name}.tmp")
        temp_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        temp_path.replace(self.path)
