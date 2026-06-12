"""Mneno CLI application and command registration."""

from __future__ import annotations

from typing import Annotated

import typer

from mneno.cli.commands import COMMANDS
from mneno.cli.version import get_version


def version_callback(show_version: bool) -> None:
    """Print the package version before command processing."""
    if show_version:
        typer.echo(f"Mneno {get_version()}")
        raise typer.Exit()


app = typer.Typer(
    name="mneno",
    help="Mneno CLI",
    invoke_without_command=True,
    rich_markup_mode="rich",
)


@app.callback()
def main(
    context: typer.Context,
    version_option: Annotated[
        bool,
        typer.Option(
            "--version",
            callback=version_callback,
            help="Show the installed Mneno version and exit.",
            is_eager=True,
        ),
    ] = False,
) -> None:
    """Manage a local Mneno workspace."""
    if context.invoked_subcommand is None and not version_option:
        typer.echo(context.get_help())


for command in COMMANDS:
    app.command(name=command.name, help=command.help, rich_help_panel="Available Commands")(command.callback)
