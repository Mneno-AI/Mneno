"""Memory export utilities."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from mneno.io.validation import EXPORT_FORMAT, EXPORT_FORMAT_VERSION
from mneno.models import Memory, utc_now


def build_export_payload(memories: list[Memory]) -> dict[str, Any]:
    """Build a stable JSON-serializable memory export payload."""
    return {
        "format": EXPORT_FORMAT,
        "version": EXPORT_FORMAT_VERSION,
        "exported_at": utc_now().isoformat(),
        "memory_count": len(memories),
        "memories": [memory.model_dump(mode="json") for memory in memories],
    }


def write_json_payload(path: str | Path, payload: dict[str, Any]) -> Path:
    """Write a JSON payload atomically where reasonable."""
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = output_path.with_name(f"{output_path.name}.tmp")
    temp_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temp_path.replace(output_path)
    return output_path


def export_memories(memories: list[Memory], path: str | Path | None = None) -> dict[str, Any]:
    """Export memories to a payload and optionally write it to disk."""
    payload = build_export_payload(memories)
    if path is not None:
        write_json_payload(path, payload)
    return payload
