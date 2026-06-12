"""Add a memory to the local Mneno workspace."""

from __future__ import annotations

from typing import Annotated

import typer
from pydantic import ValidationError

from mneno.cli.output import console, error, success, warning
from mneno.cli.workspace import WORKSPACE_NOT_FOUND_MESSAGE, Workspace, find_workspace, get_workspace_client
from mneno.models import MemoryType


def parse_metadata(values: list[str]) -> dict[str, str]:
    """Parse repeatable ``key=value`` metadata options."""
    metadata: dict[str, str] = {}
    for value in values:
        key, separator, metadata_value = value.partition("=")
        if not separator or not key.strip():
            raise ValueError("Metadata must use key=value format.")
        metadata[key.strip()] = metadata_value
    return metadata


def add_command(
    text: Annotated[str, typer.Argument(help="Memory text to store.")],
    memory_type: Annotated[
        MemoryType,
        typer.Option("--type", "-t", help="Memory type."),
    ] = MemoryType.SEMANTIC,
    importance: Annotated[
        float,
        typer.Option("--importance", "-i", min=0.0, max=1.0, help="Memory importance from 0 to 1."),
    ] = 0.5,
    tags: Annotated[
        list[str] | None,
        typer.Option("--tag", help="Tag to attach. Repeat for multiple tags."),
    ] = None,
    session_id: Annotated[
        str | None,
        typer.Option("--session", help="Existing session ID to attach."),
    ] = None,
    metadata_values: Annotated[
        list[str] | None,
        typer.Option("--metadata", help="Metadata in key=value format. Repeat for multiple fields."),
    ] = None,
) -> None:
    """Add a memory using Mneno Core and local JSON storage."""
    workspace_path = find_workspace()
    if workspace_path is None:
        warning(WORKSPACE_NOT_FOUND_MESSAGE)
        raise typer.Exit(code=1)

    try:
        metadata = parse_metadata(metadata_values or [])
    except ValueError as exc:
        error(str(exc))
        raise typer.Exit(code=2) from exc
    core_metadata: dict[str, object] = dict(metadata)

    workspace = Workspace(workspace_path)
    try:
        client = get_workspace_client(workspace.path)
        memory = client.add(
            text,
            memory_type=memory_type,
            importance=importance,
            tags=tags,
            metadata=core_metadata,
            session_id=session_id,
        )
    except (KeyError, OSError, ValidationError, ValueError) as exc:
        error(f"Unable to add memory: {exc}")
        raise typer.Exit(code=1) from exc

    success("Memory added")
    console.print()
    console.print("[bold]ID:[/bold]")
    console.print(f"  {memory.id}")
    console.print()
    console.print("[bold]Type:[/bold]")
    console.print(f"  {memory.memory_type.value}")
    console.print()
    console.print("[bold]Importance:[/bold]")
    console.print(f"  {memory.importance:.2f}")
    console.print()
    console.print("[bold]Tags:[/bold]")
    console.print(f"  {', '.join(memory.tags) if memory.tags else '(none)'}")
    console.print()
    console.print("[bold]Storage:[/bold]")
    console.print(f"  {workspace.memories_path}", soft_wrap=True)
