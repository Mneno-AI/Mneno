"""Optional atomic batch capability for storage backends."""

from contextlib import AbstractContextManager
from typing import Protocol, runtime_checkable

from mneno.storage.base import MemoryStore


class StorageConflictError(OSError):
    """The committed JSON snapshot changed; refresh and retry the operation."""


class StorageCommitError(OSError):
    """A complete snapshot committed, but a subsequent filesystem step failed."""

    committed = True


@runtime_checkable
class AtomicMemoryStore(Protocol):
    """Yield an isolated store and commit it once, only on successful exit."""

    def transaction(self) -> AbstractContextManager[MemoryStore]: ...


def atomic_transaction(storage: MemoryStore) -> AbstractContextManager[MemoryStore]:
    """Require explicit atomic support rather than attempting compensating writes."""
    if not isinstance(storage, AtomicMemoryStore):
        raise TypeError("This operation requires a storage backend with atomic transaction support")
    return storage.transaction()
