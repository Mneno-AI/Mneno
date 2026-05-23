"""Storage primitives for Mneno."""

from mneno.storage.base import MemoryStore
from mneno.storage.memory import InMemoryMemoryStore

__all__ = ["InMemoryMemoryStore", "MemoryStore"]
