"""Session management helpers."""

from __future__ import annotations

from mneno.models import Memory, utc_now
from mneno.sessions.models import Session
from mneno.sessions.timeline import Timeline, TimelineBuilder


class SessionManager:
    """Manage lightweight session records and session-memory ordering."""

    def create_session(
        self,
        *,
        title: str,
        metadata: dict[str, object] | None = None,
        tags: list[str] | None = None,
        summary: str | None = None,
    ) -> Session:
        """Create an active session model."""
        return Session(title=title, metadata=metadata or {}, tags=tags or [], summary=summary)

    def close_session(self, session: Session, *, summary: str | None = None) -> Session:
        """Return a closed session with an optional deterministic summary."""
        return session.model_copy(
            update={
                "status": "closed",
                "summary": summary if summary is not None else session.summary,
                "updated_at": utc_now(),
            }
        )

    def archive_session(self, session: Session) -> Session:
        """Return an archived session."""
        return session.model_copy(update={"status": "archived", "updated_at": utc_now()})

    def add_memory_to_session(
        self, session: Session, memory: Memory, *, sequence_index: int | None = None
    ) -> tuple[Session, Memory]:
        """Attach a memory to a primary session and assign sequence ordering."""
        resolved_index = sequence_index if sequence_index is not None else len(session.memory_ids)
        memory_ids = [*session.memory_ids]
        if memory.id not in memory_ids:
            memory_ids.append(memory.id)
        updated_session = session.model_copy(update={"memory_ids": memory_ids, "updated_at": utc_now()})
        updated_memory = memory.model_copy(update={"session_id": session.id, "sequence_index": resolved_index})
        return updated_session, updated_memory

    def list_session_memories(self, session: Session, memories: list[Memory]) -> list[Memory]:
        """Return memories attached to a session in deterministic sequence order."""
        session_memory_ids = set(session.memory_ids)
        attached = [memory for memory in memories if memory.id in session_memory_ids or memory.session_id == session.id]
        return sorted(
            attached,
            key=lambda memory: (
                memory.sequence_index if memory.sequence_index is not None else 10**9,
                memory.created_at,
                memory.id,
            ),
        )

    def summarize_session(self, session: Session, memories: list[Memory]) -> str:
        """Create a deterministic summary from session memories."""
        if not memories:
            return f"{session.title}: 0 memories."
        first = memories[0].content
        return f"{session.title}: {len(memories)} memories. First memory: {first}"

    def build_timeline(self, memories: list[Memory], *, session_ids: list[str] | None = None) -> Timeline:
        """Build a timeline from memories."""
        return TimelineBuilder().build(memories, session_ids=session_ids)
