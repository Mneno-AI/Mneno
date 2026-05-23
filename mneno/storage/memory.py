"""In-memory local storage for the MVP SDK."""

from __future__ import annotations

from mneno.models import Memory, utc_now


class InMemoryMemoryStore:
    """Simple insertion-ordered in-memory memory store."""

    def __init__(self) -> None:
        self._memories: dict[str, Memory] = {}

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
        return self._memories.pop(memory_id, None) is not None

    def clear(self) -> None:
        self._memories.clear()

    def record_access(self, memory_id: str) -> Memory | None:
        memory = self.get(memory_id)
        if memory is None:
            return None

        now = utc_now()
        updated = memory.model_copy(update={"access_count": memory.access_count + 1, "last_accessed_at": now})
        self._memories[memory_id] = updated
        return updated


InMemoryStorage = InMemoryMemoryStore
