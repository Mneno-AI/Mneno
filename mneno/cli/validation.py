"""Shared CLI input validation helpers."""

from __future__ import annotations

import json

import typer

from mneno.cli.output import error


def reject_blank(value: str, *, message: str, json_output: bool = False) -> None:
    """Exit with a CLI-owned error when a required text argument is blank."""
    if value.strip():
        return
    if json_output:
        typer.echo(json.dumps({"error": message}))
    else:
        error(message)
    raise typer.Exit(code=1)
