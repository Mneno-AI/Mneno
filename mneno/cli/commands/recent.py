"""Show recently updated memories from a local Mneno workspace."""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Annotated

import typer
from pydantic import ValidationError

from mneno.cli.output import console, error, warning
from mneno.cli.workspace import WORKSPACE_NOT_FOUND_MESSAGE, find_workspace, get_workspace_client

CONTENT_PREVIEW_LENGTH = 100


@dataclass(frozen=True)
class RecentOutputItem:
    """Stable CLI representation of a recent memory."""

    memory_id: str
    content: str
    memory_type: str
    layer: str
    status: str
    tags: list[str]
    created_at: str
    updated_at: str


def recent_command(
    limit: Annotated[
        int,
        typer.Option("--limit", "-l", min=1, help="Maximum number of recent memories."),
    ] = 10,
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Write machine-readable JSON."),
    ] = False,
    include_inactive: Annotated[
        bool,
        typer.Option("--include-inactive", help="Include superseded and all other inactive memories."),
    ] = False,
    include_archived: Annotated[
        bool,
        typer.Option("--include-archived", help="Include archived memories but not superseded memories."),
    ] = False,
) -> None:
    """List memories by most recent update time."""
    workspace_path = find_workspace()
    if workspace_path is None:
        if json_output:
            typer.echo(json.dumps({"error": WORKSPACE_NOT_FOUND_MESSAGE}))
        else:
            warning(WORKSPACE_NOT_FOUND_MESSAGE)
        raise typer.Exit(code=1)

    try:
        memories = get_workspace_client(workspace_path).list()
        filtered = _filter_memories(
            memories,
            include_inactive=include_inactive,
            include_archived=include_archived,
        )
        recent = sorted(filtered, key=_sort_time, reverse=True)[:limit]
        items = [_normalize_memory(memory) for memory in recent]
    except (OSError, TypeError, ValidationError, ValueError) as exc:
        message = f"Unable to list recent memories: {exc}"
        if json_output:
            typer.echo(json.dumps({"error": message}))
        else:
            error(message)
        raise typer.Exit(code=1) from exc

    if json_output:
        typer.echo(json.dumps([asdict(item) for item in items], indent=2))
        return

    console.print("[bold]Recent memories[/bold]")
    if not items:
        console.print()
        console.print("No memories found.")
        return

    for index, item in enumerate(items, start=1):
        console.print()
        console.print(f"[bold]{index}. {_preview(item.content)}[/bold]")
        console.print(f"   Updated: {item.updated_at}")
        console.print(f"   Created: {item.created_at}")
        console.print(f"   Type: {item.memory_type}")
        console.print(f"   Layer: {item.layer}")
        console.print(f"   Status: {item.status}")
        console.print(f"   Tags: {', '.join(item.tags) if item.tags else '(none)'}")


def _filter_memories(
    memories: Sequence[object],
    *,
    include_inactive: bool,
    include_archived: bool,
) -> list[object]:
    if include_inactive:
        return list(memories)

    filtered: list[object] = []
    for memory in memories:
        status = _enum_value(getattr(memory, "status", None))
        layer = _enum_value(getattr(memory, "layer", None))
        if status == "superseded":
            continue
        if not include_archived and (status == "archived" or layer == "archived"):
            continue
        filtered.append(memory)
    return filtered


def _sort_time(memory: object) -> datetime:
    updated_at = getattr(memory, "updated_at", None)
    created_at = getattr(memory, "created_at", None)
    value = updated_at if isinstance(updated_at, datetime) else created_at
    if not isinstance(value, datetime):
        return datetime.min.replace(tzinfo=UTC)
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


def _normalize_memory(memory: object) -> RecentOutputItem:
    return RecentOutputItem(
        memory_id=_string_or_placeholder(getattr(memory, "id", None)),
        content=_string_or_placeholder(getattr(memory, "content", None)),
        memory_type=_enum_value_or_placeholder(getattr(memory, "memory_type", None)),
        layer=_enum_value_or_placeholder(getattr(memory, "layer", None)),
        status=_enum_value_or_placeholder(getattr(memory, "status", None)),
        tags=_string_list(getattr(memory, "tags", None)),
        created_at=_datetime_or_placeholder(getattr(memory, "created_at", None)),
        updated_at=_datetime_or_placeholder(getattr(memory, "updated_at", None)),
    )


def _preview(content: str) -> str:
    clean = " ".join(content.split())
    if len(clean) <= CONTENT_PREVIEW_LENGTH:
        return clean
    return f"{clean[: CONTENT_PREVIEW_LENGTH - 3].rstrip()}..."


def _string_or_placeholder(value: object) -> str:
    return value if isinstance(value, str) else "-"


def _enum_value(value: object) -> str | None:
    enum_value = getattr(value, "value", value)
    return enum_value if isinstance(enum_value, str) else None


def _enum_value_or_placeholder(value: object) -> str:
    return _enum_value(value) or "-"


def _datetime_or_placeholder(value: object) -> str:
    return value.isoformat() if isinstance(value, datetime) else "-"


def _string_list(value: object) -> list[str]:
    if not isinstance(value, (list, tuple)):
        return []
    return [item for item in value if isinstance(item, str)]
