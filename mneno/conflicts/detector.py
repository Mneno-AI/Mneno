"""Deterministic local conflict detection."""

from __future__ import annotations

import re
from dataclasses import dataclass

from mneno.conflicts.policies import ConflictPolicy
from mneno.conflicts.reports import ConflictAction, ConflictReport, ConflictSeverity, ConflictType
from mneno.models import Memory, MemoryType

TOKEN_PATTERN = re.compile(r"[a-zA-Z0-9]+")
UPDATE_CUES = ("now", "changed to", "no longer", "instead", "replaced by")
OPERATIONAL_KEYS = ("task", "goal", "constraint", "requirement", "priority")


@dataclass(frozen=True)
class _PreferenceClaim:
    verb: str
    value: str
    negated: bool
    update_cue: bool


@dataclass(frozen=True)
class _OperationalClaim:
    key: str
    value: str
    update_cue: bool


class ConflictDetector:
    """Detect contradictions, supersessions, duplicates, and simple operational changes."""

    def detect(
        self,
        new_memory: Memory,
        existing_memories: list[Memory],
        policy: ConflictPolicy | None = None,
    ) -> list[ConflictReport]:
        """Compare a new memory against existing memories and return explainable reports."""
        active_policy = policy or ConflictPolicy()
        reports: list[ConflictReport] = []
        for existing in existing_memories:
            if existing.id == new_memory.id:
                continue
            report = self._detect_pair(new_memory, existing, active_policy)
            if report is not None:
                reports.append(report)
        return reports

    def _detect_pair(
        self,
        new_memory: Memory,
        existing_memory: Memory,
        policy: ConflictPolicy,
    ) -> ConflictReport | None:
        duplicate = self._duplicate_report(new_memory, existing_memory, policy)
        if duplicate is not None:
            return duplicate

        preference = self._preference_report(new_memory, existing_memory, policy)
        if preference is not None:
            return preference

        operational = self._operational_report(new_memory, existing_memory)
        if operational is not None:
            return operational

        return None

    def _duplicate_report(
        self,
        new_memory: Memory,
        existing_memory: Memory,
        policy: ConflictPolicy,
    ) -> ConflictReport | None:
        if not policy.detect_duplicates:
            return None

        new_normalized = _normalize(new_memory.content)
        existing_normalized = _normalize(existing_memory.content)
        if not new_normalized or not existing_normalized:
            return None

        if new_normalized == existing_normalized:
            return ConflictReport(
                conflict_type=ConflictType.DUPLICATE,
                severity=ConflictSeverity.LOW,
                new_memory_id=new_memory.id,
                existing_memory_id=existing_memory.id,
                reason="New memory exactly duplicates an existing normalized memory.",
                evidence=[f"normalized_content={new_normalized}"],
                suggested_action=(
                    ConflictAction.ARCHIVE_EXISTING if policy.auto_archive_duplicates else ConflictAction.KEEP_BOTH
                ),
            )

        overlap = _jaccard(_tokens(new_normalized), _tokens(existing_normalized))
        if overlap >= policy.similarity_threshold:
            return ConflictReport(
                conflict_type=ConflictType.DUPLICATE,
                severity=ConflictSeverity.LOW,
                new_memory_id=new_memory.id,
                existing_memory_id=existing_memory.id,
                reason=f"New memory is a near duplicate of an existing memory by token overlap {overlap:.2f}.",
                evidence=[
                    f"new={new_memory.content}",
                    f"existing={existing_memory.content}",
                    f"token_overlap={overlap:.2f}",
                ],
                suggested_action=(
                    ConflictAction.ARCHIVE_EXISTING if policy.auto_archive_duplicates else ConflictAction.KEEP_BOTH
                ),
            )
        return None

    def _preference_report(
        self,
        new_memory: Memory,
        existing_memory: Memory,
        policy: ConflictPolicy,
    ) -> ConflictReport | None:
        if not policy.detect_preference_changes:
            return None

        new_claim = _preference_claim(new_memory.content)
        existing_claim = _preference_claim(existing_memory.content)
        if new_claim is None or existing_claim is None:
            return None

        same_object = _normalize(new_claim.value) == _normalize(existing_claim.value)
        values_overlap = _jaccard(_tokens(new_claim.value), _tokens(existing_claim.value))
        same_domain = values_overlap > 0.0 or new_claim.update_cue or existing_claim.update_cue

        if policy.detect_negations and same_object and new_claim.negated != existing_claim.negated:
            return ConflictReport(
                conflict_type=ConflictType.CONTRADICTION,
                severity=ConflictSeverity.HIGH,
                new_memory_id=new_memory.id,
                existing_memory_id=existing_memory.id,
                reason=f"New memory negates an existing {existing_claim.verb} preference.",
                evidence=[f"new={new_memory.content}", f"existing={existing_memory.content}"],
                suggested_action=ConflictAction.MARK_CONFLICTED,
            )

        if new_claim.negated != existing_claim.negated:
            return None

        if new_claim.value != existing_claim.value and same_domain:
            conflict_type = ConflictType.SUPERSESSION if new_claim.update_cue else ConflictType.PREFERENCE_CHANGE
            severity = ConflictSeverity.MEDIUM if new_claim.update_cue else ConflictSeverity.LOW
            return ConflictReport(
                conflict_type=conflict_type,
                severity=severity,
                new_memory_id=new_memory.id,
                existing_memory_id=existing_memory.id,
                reason=(
                    "New memory appears to supersede an existing preference."
                    if new_claim.update_cue
                    else "New memory records a different preference from an existing memory."
                ),
                evidence=[
                    f"new_{new_claim.verb}={new_claim.value}",
                    f"existing_{existing_claim.verb}={existing_claim.value}",
                ],
                suggested_action=(
                    ConflictAction.SUPERSEDE_EXISTING if policy.auto_supersede_preferences else ConflictAction.KEEP_BOTH
                ),
            )
        return None

    def _operational_report(self, new_memory: Memory, existing_memory: Memory) -> ConflictReport | None:
        new_claim = _operational_claim(new_memory.content)
        existing_claim = _operational_claim(existing_memory.content)
        if new_claim is None or existing_claim is None:
            return None
        if new_claim.key != existing_claim.key:
            return None
        if _normalize(new_claim.value) == _normalize(existing_claim.value):
            return None

        operational_type = (
            new_memory.memory_type is MemoryType.OPERATIONAL or existing_memory.memory_type is MemoryType.OPERATIONAL
        )
        if not operational_type and not (new_claim.update_cue or existing_claim.update_cue):
            return None

        return ConflictReport(
            conflict_type=ConflictType.OPERATIONAL_CHANGE,
            severity=ConflictSeverity.MEDIUM,
            new_memory_id=new_memory.id,
            existing_memory_id=existing_memory.id,
            reason=f"New memory changes the current operational {new_claim.key}.",
            evidence=[
                f"new_{new_claim.key}={new_claim.value}",
                f"existing_{existing_claim.key}={existing_claim.value}",
            ],
            suggested_action=ConflictAction.SUPERSEDE_EXISTING,
        )


def _preference_claim(content: str) -> _PreferenceClaim | None:
    text = _clean_text(content)
    negation_pattern = r"\b(?:does not|doesn't|do not|don't|no longer)\s+"
    negation_pattern += r"(?:prefer|prefers|like|likes|want|wants)\b"
    negated = bool(re.search(negation_pattern, text))
    update_cue = any(cue in text for cue in UPDATE_CUES)

    patterns = [
        r"\b(?:now\s+)?(?P<verb>prefer|prefers|like|likes|want|wants)\s+(?P<value>.+)$",
        (
            r"\b(?:does not|doesn't|do not|don't|no longer)\s+"
            r"(?P<verb>prefer|prefers|like|likes|want|wants)\s+(?P<value>.+)$"
        ),
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match is None:
            continue
        value = _trim_value(match.group("value"))
        if value:
            return _PreferenceClaim(
                verb=_canonical_verb(match.group("verb")),
                value=value,
                negated=negated,
                update_cue=update_cue,
            )
    return None


def _operational_claim(content: str) -> _OperationalClaim | None:
    text = _clean_text(content)
    update_cue = any(cue in text for cue in UPDATE_CUES)
    for key in OPERATIONAL_KEYS:
        patterns = [
            rf"\bcurrent\s+{key}\s+(?:is|=|:)\s+(?P<value>.+)$",
            rf"\b{key}\s+(?:is|=|:|changed to|now is)\s+(?P<value>.+)$",
        ]
        for pattern in patterns:
            match = re.search(pattern, text)
            if match is None:
                continue
            value = _trim_value(match.group("value"))
            if value:
                return _OperationalClaim(key=key, value=value, update_cue=update_cue)
    return None


def _clean_text(content: str) -> str:
    return content.strip().lower().rstrip(".!?")


def _trim_value(value: str) -> str:
    value = value.strip().rstrip(".!?")
    value = re.sub(r"\s+instead$", "", value)
    return value.strip()


def _canonical_verb(verb: str) -> str:
    if verb in {"prefer", "prefers"}:
        return "prefer"
    if verb in {"like", "likes"}:
        return "like"
    return "want"


def _normalize(content: str) -> str:
    return " ".join(_tokens(content))


def _tokens(content: str) -> list[str]:
    return [token.lower() for token in TOKEN_PATTERN.findall(content)]


def _jaccard(first: list[str], second: list[str]) -> float:
    first_tokens = set(first)
    second_tokens = set(second)
    if not first_tokens or not second_tokens:
        return 0.0
    return len(first_tokens & second_tokens) / len(first_tokens | second_tokens)
