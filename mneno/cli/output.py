"""Consistent Rich output helpers for CLI commands."""

from __future__ import annotations

from rich.console import Console
from rich.text import Text

console = Console()
error_console = Console(stderr=True)


def success(message: str) -> None:
    """Print a successful operation message."""
    console.print(Text.assemble(("✓ ", "bold green"), message))


def error(message: str) -> None:
    """Print an error message."""
    error_console.print(Text.assemble(("✗ ", "bold red"), message))


def warning(message: str) -> None:
    """Print a warning message."""
    console.print(Text.assemble(("! ", "bold yellow"), message))


def info(message: str) -> None:
    """Print an informational message."""
    console.print(Text.assemble(("i ", "bold blue"), message))
