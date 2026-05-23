"""Vector similarity utilities for local semantic retrieval."""

from __future__ import annotations

import math


def normalize_vector(vector: list[float]) -> list[float]:
    """Return a unit-normalized vector, or an empty vector for zero input."""
    if not vector:
        return []
    magnitude = math.sqrt(sum(value * value for value in vector))
    if magnitude == 0:
        return [0.0 for _value in vector]
    return [value / magnitude for value in vector]


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Calculate cosine similarity for same-dimension vectors."""
    if len(a) != len(b):
        raise ValueError("Vector dimensions must match")
    if not a or not b:
        return 0.0

    normalized_a = normalize_vector(a)
    normalized_b = normalize_vector(b)
    if not any(normalized_a) or not any(normalized_b):
        return 0.0
    return sum(left * right for left, right in zip(normalized_a, normalized_b, strict=True))


def safe_similarity(a: list[float], b: list[float]) -> float:
    """Return cosine similarity mapped to 0..1, safely handling empty vectors."""
    if not a or not b:
        return 0.0
    similarity = cosine_similarity(a, b)
    return round((max(min(similarity, 1.0), -1.0) + 1.0) / 2.0, 6)
