"""Initialize a local Mneno workspace."""

from __future__ import annotations

from mneno.cli.output import console, info, success
from mneno.cli.workspace import initialize_workspace


def init_command() -> None:
    """Create the local workspace structure without replacing existing data."""
    workspace, created = initialize_workspace()

    if created:
        success("Initialized Mneno workspace")
    else:
        info("Workspace already exists")

    console.print()
    console.print("[bold]Location:[/bold]")
    console.print(workspace.path, soft_wrap=True)
