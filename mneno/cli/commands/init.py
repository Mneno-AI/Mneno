"""Initialize a local Mneno workspace."""

from __future__ import annotations

import typer

from mneno.cli.output import console, error, info, success
from mneno.cli.workspace import initialize_workspace


def init_command() -> None:
    """Create the local workspace structure without replacing existing data."""
    try:
        workspace, created = initialize_workspace()
    except ValueError as exc:
        error(str(exc))
        raise typer.Exit(code=1) from exc

    if created:
        success("Initialized Mneno workspace")
    else:
        info("Workspace already exists")

    console.print()
    console.print("[bold]Location:[/bold]")
    console.print(workspace.path, soft_wrap=True)
