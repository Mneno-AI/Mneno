"""Deterministic multi-session continuity helpers."""

from __future__ import annotations

import re

from pydantic import BaseModel, ConfigDict, Field

from mneno.models import Memory, MemoryStatus
from mneno.sessions.models import Session

TOKEN_PATTERN = re.compile(r"[a-zA-Z0-9]+")


class ContinuityResult(BaseModel):
    """Related sessions and memories for continuity across time."""

    model_config = ConfigDict(extra="forbid")

    related_sessions: list[Session] = Field(default_factory=list)
    relevant_memories: list[Memory] = Field(default_factory=list)
    continuity_summary: str = ""
    continuity_reasons: list[str] = Field(default_factory=list)


class ContinuityManager:
    """Find related sessions and memories using deterministic token overlap."""

    def find_related(
        self,
        query: str,
        *,
        sessions: list[Session],
        memories: list[Memory],
        limit: int = 5,
    ) -> ContinuityResult:
        """Return sessions and memories related to a query."""
        query_tokens = set(_tokens(query))
        scored: list[tuple[Session, float, str]] = []
        memories_by_session = _memories_by_session(memories)

        for session in sessions:
            if session.status == "archived":
                continue
            session_text = " ".join(
                [
                    session.title,
                    session.summary or "",
                    " ".join(session.tags),
                    " ".join(memory.content for memory in memories_by_session.get(session.id, [])),
                ]
            )
            overlap = _overlap(query_tokens, set(_tokens(session_text)))
            if overlap <= 0:
                continue
            scored.append((session, overlap, f"Matched related session by token overlap {overlap:.2f}"))

        scored.sort(key=lambda item: (item[1], item[0].updated_at, item[0].id), reverse=True)
        related_sessions = [session for session, _, _ in scored[:limit]]
        related_session_ids = {session.id for session in related_sessions}
        relevant_memories = [
            memory
            for memory in memories
            if memory.session_id in related_session_ids and memory.status is not MemoryStatus.ARCHIVED
        ]
        relevant_memories.sort(
            key=lambda memory: (
                memory.session_id or "",
                memory.sequence_index if memory.sequence_index is not None else 10**9,
                memory.created_at,
                memory.id,
            )
        )
        reasons = [reason for _, _, reason in scored[:limit]]
        summary = (
            f"Found {len(related_sessions)} related sessions and {len(relevant_memories)} continuity memories."
            if related_sessions
            else "Found no related sessions."
        )
        return ContinuityResult(
            related_sessions=related_sessions,
            relevant_memories=relevant_memories,
            continuity_summary=summary,
            continuity_reasons=reasons,
        )


def _memories_by_session(memories: list[Memory]) -> dict[str, list[Memory]]:
    by_session: dict[str, list[Memory]] = {}
    for memory in memories:
        if memory.session_id is None:
            continue
        by_session.setdefault(memory.session_id, []).append(memory)
    return by_session


def _tokens(text: str) -> list[str]:
    return [token.lower() for token in TOKEN_PATTERN.findall(text)]


def _overlap(query_tokens: set[str], content_tokens: set[str]) -> float:
    if not query_tokens or not content_tokens:
        return 0.0
    return len(query_tokens & content_tokens) / len(query_tokens)
