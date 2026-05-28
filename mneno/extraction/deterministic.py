"""Deterministic local memory extraction."""

from __future__ import annotations

import re

from mneno.extraction.base import ExtractedMemory, ExtractionResult
from mneno.models import MemoryType

SPLIT_PATTERN = re.compile(r"(?:\n+|(?<=[.!?])\s+)")
PREFERENCE_TERMS = ("prefers", "likes", "wants", "doesn't like", "does not like")
OPERATIONAL_TERMS = ("task", "todo", "goal", "must", "deadline", "constraint")


class DeterministicMemoryExtractor:
    """Extract simple durable memories with local heuristics."""

    def extract(self, text: str) -> ExtractionResult:
        """Extract structured memories without an LLM."""
        extracted: list[ExtractedMemory] = []
        for candidate in _candidate_claims(text):
            memory_type = _classify(candidate)
            extracted.append(
                ExtractedMemory(
                    content=candidate,
                    memory_type=memory_type,
                    importance=_importance(candidate, memory_type),
                    tags=_tags(candidate, memory_type),
                    metadata={"extractor": "deterministic"},
                    reason=_reason(memory_type),
                )
            )
        return ExtractionResult(source_text=text, mode="deterministic", extracted=extracted)


def _candidate_claims(text: str) -> list[str]:
    claims: list[str] = []
    for part in SPLIT_PATTERN.split(text):
        claim = part.strip(" \t\r\n-")
        if not claim:
            continue
        if len(claim.split()) < 3 or len(claim) < 12:
            continue
        claims.append(claim)
    return claims


def _classify(text: str) -> MemoryType:
    lowered = text.lower()
    if any(term in lowered for term in PREFERENCE_TERMS):
        return MemoryType.PREFERENCE
    if any(term in lowered for term in OPERATIONAL_TERMS):
        return MemoryType.OPERATIONAL
    return MemoryType.SEMANTIC


def _importance(text: str, memory_type: MemoryType) -> float:
    lowered = text.lower()
    if memory_type is MemoryType.PREFERENCE:
        return 0.8
    if memory_type is MemoryType.OPERATIONAL:
        return 0.75
    if "mneno" in lowered or "project" in lowered:
        return 0.8
    return 0.6


def _tags(text: str, memory_type: MemoryType) -> list[str]:
    tags = [memory_type.value]
    lowered = text.lower()
    if "mneno" in lowered:
        tags.append("mneno")
    if "project" in lowered:
        tags.append("project")
    return tags


def _reason(memory_type: MemoryType) -> str:
    if memory_type is MemoryType.PREFERENCE:
        return "Detected preference language in source text."
    if memory_type is MemoryType.OPERATIONAL:
        return "Detected task, goal, constraint, or deadline language in source text."
    return "Detected durable factual claim in source text."
