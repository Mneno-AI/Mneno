"""Shared CLI input validation helpers."""

from __future__ import annotations

import typer

from mneno.cli.output import error


def reject_blank(value: str, *, message: str) -> None:
    """Exit with a CLI-owned error when a required text argument is blank."""
    if value.strip():
        return
    error(message)
    raise typer.Exit(code=1)
