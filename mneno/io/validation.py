"""Validation helpers for Mneno storage and export payloads."""

from __future__ import annotations

from typing import Any

STORAGE_FORMAT_VERSION = 1
EXPORT_FORMAT = "mneno.memory_export"
EXPORT_FORMAT_VERSION = 1


def validate_storage_payload(payload: dict[str, Any]) -> None:
    """Validate a JSON storage payload."""
    if "version" not in payload:
        raise ValueError("Invalid storage payload: missing version")
    if payload["version"] != STORAGE_FORMAT_VERSION:
        raise ValueError(f"Unsupported storage version: {payload['version']}")
    if "memories" not in payload:
        raise ValueError("Invalid storage payload: missing memories")
    if not isinstance(payload["memories"], list):
        raise ValueError("Invalid storage payload: memories must be a list")
    if "sessions" in payload and not isinstance(payload["sessions"], list):
        raise ValueError("Invalid storage payload: sessions must be a list")


def validate_export_payload(payload: dict[str, Any]) -> None:
    """Validate a memory export payload."""
    if payload.get("format") != EXPORT_FORMAT:
        raise ValueError(f"Unknown export format: {payload.get('format')}")
    if "version" not in payload:
        raise ValueError("Invalid export payload: missing version")
    if payload["version"] != EXPORT_FORMAT_VERSION:
        raise ValueError(f"Unsupported export version: {payload['version']}")
    if "memories" not in payload:
        raise ValueError("Invalid export payload: missing memories")
    if not isinstance(payload["memories"], list):
        raise ValueError("Invalid export payload: memories must be a list")
    if "sessions" in payload and not isinstance(payload["sessions"], list):
        raise ValueError("Invalid export payload: sessions must be a list")
