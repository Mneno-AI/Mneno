"""Show local Mneno workspace status."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Annotated

import typer
from pydantic import ValidationError

from mneno.cli.output import console, error, warning
from mneno.cli.version import get_version
from mneno.cli.workspace import WORKSPACE_NOT_FOUND_MESSAGE, Workspace, find_workspace, get_workspace_client

STATUS_NAMES = ("active", "archived", "superseded", "conflicted")
LAYER_NAMES = ("short_term", "working", "episodic", "semantic", "operational", "archived")


@dataclass(frozen=True)
class StatusCounts:
    """Memory and session totals for status output."""

    memories: int
    active: int
    archived: int
    superseded: int
    conflicted: int
    sessions: int


@dataclass(frozen=True)
class StatusLayers:
    """Memory counts grouped by hierarchy layer."""

    short_term: int
    working: int
    episodic: int
    semantic: int
    operational: int
    archived: int


@dataclass(frozen=True)
class StatusRecent:
    """Most recently updated memory information."""

    last_updated: str | None
    latest_memory: str | None


@dataclass(frozen=True)
class StatusVersion:
    """Workspace schema and installed package versions."""

    workspace: int
    mneno: str


@dataclass(frozen=True)
class StatusOutput:
    """Stable machine-readable workspace status."""

    workspace: str
    storage: str
    counts: StatusCounts
    layers: StatusLayers
    recent: StatusRecent
    version: StatusVersion


def status_command(
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Write machine-readable JSON."),
    ] = False,
) -> None:
    """Display workspace health, lifecycle counts, layers, and recent activity."""
    workspace_path = find_workspace()
    if workspace_path is None:
        if json_output:
            typer.echo(json.dumps({"error": WORKSPACE_NOT_FOUND_MESSAGE}))
        else:
            warning(WORKSPACE_NOT_FOUND_MESSAGE)
        raise typer.Exit(code=1)

    workspace = Workspace(workspace_path)
    try:
        output = _build_status(workspace)
    except (OSError, TypeError, ValidationError, ValueError) as exc:
        message = f"Unable to read Mneno workspace: {exc}"
        if json_output:
            typer.echo(json.dumps({"error": message}))
        else:
            error(message)
        raise typer.Exit(code=1) from exc

    if json_output:
        typer.echo(json.dumps(asdict(output), indent=2))
        return

    console.print("[bold]Workspace:[/bold]")
    console.print(f"  {output.workspace}", soft_wrap=True)
    console.print()
    console.print("[bold]Storage:[/bold]")
    console.print(f"  {output.storage.upper()}")
    console.print()
    console.print("[bold]Counts:[/bold]")
    console.print(f"  Memories: {output.counts.memories}")
    console.print(f"  Active: {output.counts.active}")
    console.print(f"  Archived: {output.counts.archived}")
    console.print(f"  Superseded: {output.counts.superseded}")
    console.print(f"  Conflicted: {output.counts.conflicted}")
    console.print(f"  Sessions: {output.counts.sessions}")
    console.print()
    console.print("[bold]Layers:[/bold]")
    for layer in LAYER_NAMES:
        console.print(f"  {layer}: {getattr(output.layers, layer)}")
    console.print()
    console.print("[bold]Recent:[/bold]")
    console.print(f"  Last updated: {output.recent.last_updated or '-'}")
    console.print(f"  Latest memory: {output.recent.latest_memory or '-'}")
    console.print()
    console.print("[bold]Version:[/bold]")
    console.print(f"  Workspace: {output.version.workspace}")
    console.print(f"  Mneno: {output.version.mneno}")

    if output.counts.memories == 0:
        console.print()
        console.print("No memories yet. Add one with:")
        console.print('  [bold]mneno add "Your first memory"[/bold]')


def _build_status(workspace: Workspace) -> StatusOutput:
    config = workspace.load_config()
    client = get_workspace_client(workspace.path)
    memories = client.list()
    sessions = client.list_sessions()
    status_counts = {name: 0 for name in STATUS_NAMES}
    layer_counts = {name: 0 for name in LAYER_NAMES}

    for memory in memories:
        status = _enum_value(getattr(memory, "status", None))
        layer = _enum_value(getattr(memory, "layer", None))
        if status in status_counts:
            status_counts[status] += 1
        if layer in layer_counts:
            layer_counts[layer] += 1

    latest = max(memories, key=_sort_time, default=None)
    return StatusOutput(
        workspace=str(workspace.path),
        storage=config.storage,
        counts=StatusCounts(
            memories=len(memories),
            active=status_counts["active"],
            archived=status_counts["archived"],
            superseded=status_counts["superseded"],
            conflicted=status_counts["conflicted"],
            sessions=len(sessions),
        ),
        layers=StatusLayers(**layer_counts),
        recent=StatusRecent(
            last_updated=_datetime_value(getattr(latest, "updated_at", None)),
            latest_memory=_string_value(getattr(latest, "content", None)),
        ),
        version=StatusVersion(workspace=config.version, mneno=get_version()),
    )


def _sort_time(memory: object) -> datetime:
    updated_at = getattr(memory, "updated_at", None)
    created_at = getattr(memory, "created_at", None)
    value = updated_at if isinstance(updated_at, datetime) else created_at
    if not isinstance(value, datetime):
        return datetime.min.replace(tzinfo=UTC)
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


def _enum_value(value: object) -> str | None:
    enum_value = getattr(value, "value", value)
    return enum_value if isinstance(enum_value, str) else None


def _datetime_value(value: object) -> str | None:
    return value.isoformat() if isinstance(value, datetime) else None


def _string_value(value: object) -> str | None:
    return value if isinstance(value, str) else None
