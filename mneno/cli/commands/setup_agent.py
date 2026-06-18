"""Install Mneno agent integration templates."""

from __future__ import annotations

from typing import Annotated

import typer

from mneno.cli.integrations import (
    SUPPORTED_AGENTS,
    ExistingTargetError,
    install_agent_template,
    plan_agent_installation,
)
from mneno.cli.output import console, error, success, warning
from mneno.cli.workspace import WORKSPACE_NOT_FOUND_MESSAGE, find_workspace


def setup_agent_command(
    agent: Annotated[
        str,
        typer.Argument(help=f"Agent to configure. Supported: {', '.join(SUPPORTED_AGENTS)}."),
    ],
    force: Annotated[
        bool,
        typer.Option("--force", "-f", help="Overwrite existing integration files."),
    ] = False,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Show files that would be created without writing them."),
    ] = False,
) -> None:
    """Install Mneno agent integration templates into the current repository."""
    workspace_path = find_workspace()
    if workspace_path is None:
        warning(WORKSPACE_NOT_FOUND_MESSAGE)
        raise typer.Exit(code=1)

    try:
        plan = plan_agent_installation(agent, workspace_path)
        if dry_run:
            _print_dry_run(plan.display_paths)
            return
        installed = install_agent_template(agent, workspace_path, force=force)
    except ExistingTargetError as exc:
        _print_existing_files(exc.display_paths)
        raise typer.Exit(code=1) from exc
    except (FileNotFoundError, OSError, ValueError) as exc:
        error(str(exc))
        raise typer.Exit(code=1) from exc

    success("Installed Mneno agent integration")
    console.print()
    console.print("[bold]Agent:[/bold]")
    console.print(f"  {installed.agent}")
    console.print()
    console.print("[bold]Created:[/bold]")
    for path in installed.display_paths:
        console.print(f"  {path}")


def _print_dry_run(paths: tuple[str, ...]) -> None:
    console.print("[bold]Would create:[/bold]")
    for path in paths:
        console.print(f"  {path}")


def _print_existing_files(paths: tuple[str, ...]) -> None:
    error("File already exists:")
    for path in paths:
        console.print(f"  {path}")
    console.print()
    console.print("Use --force to overwrite.")
