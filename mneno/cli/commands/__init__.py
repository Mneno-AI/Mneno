"""Built-in Mneno CLI commands."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from mneno.cli.commands.add import add_command
from mneno.cli.commands.context import context_command
from mneno.cli.commands.init import init_command
from mneno.cli.commands.recent import recent_command
from mneno.cli.commands.search import search_command
from mneno.cli.commands.status import status_command


@dataclass(frozen=True)
class Command:
    """A command registered by the root CLI application."""

    name: str
    help: str
    callback: Callable[..., None]


COMMANDS = (
    Command(name="init", help="Initialize a local Mneno workspace.", callback=init_command),
    Command(name="add", help="Add a memory to the local workspace.", callback=add_command),
    Command(name="search", help="Search memories in the local workspace.", callback=search_command),
    Command(name="context", help="Build an explainable context package.", callback=context_command),
    Command(name="recent", help="Show recently updated workspace memories.", callback=recent_command),
    Command(name="status", help="Show local Mneno workspace information.", callback=status_command),
)

__all__ = ["COMMANDS", "Command"]
