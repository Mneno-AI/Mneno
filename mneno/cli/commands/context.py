"""Build an explainable context package from a local Mneno workspace."""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import asdict, dataclass
from inspect import signature
from typing import Annotated, Any, cast

import typer
from pydantic import ValidationError

from mneno import MemoryClient
from mneno.cli.output import console, error, warning
from mneno.cli.workspace import WORKSPACE_NOT_FOUND_MESSAGE, find_workspace, get_workspace_client
from mneno.context import ContextPolicy, ContextPreset, get_context_policy


@dataclass(frozen=True)
class ContextOutputItem:
    """Stable CLI representation of one context inclusion decision."""

    memory_id: str
    content: str
    score: float | str
    estimated_tokens: int | str
    reason: str


@dataclass(frozen=True)
class ContextOutputStats:
    """Stable CLI context statistics."""

    max_tokens: int | str
    available_tokens: int | str
    used_tokens: int | str
    remaining_tokens: int | str
    included_count: int | str
    excluded_count: int | str


@dataclass(frozen=True)
class ContextOutputPackage:
    """Stable machine-readable context package."""

    query: str
    text: str
    preset: str
    stats: ContextOutputStats
    included: list[ContextOutputItem]
    excluded: list[ContextOutputItem]


def context_command(
    query: Annotated[str, typer.Argument(help="Query used to build the context package.")],
    budget: Annotated[
        int,
        typer.Option("--budget", "-b", min=1, help="Maximum context token budget."),
    ] = 1200,
    preset: Annotated[
        ContextPreset,
        typer.Option("--preset", help="Context selection preset."),
    ] = ContextPreset.BALANCED,
    session_id: Annotated[
        str | None,
        typer.Option("--session", help="Current session ID used for continuity-aware context."),
    ] = None,
    include_inactive: Annotated[
        bool,
        typer.Option("--include-inactive", help="Include superseded and other inactive memories."),
    ] = False,
    include_archived: Annotated[
        bool,
        typer.Option("--include-archived", help="Include archived memories."),
    ] = False,
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Write machine-readable JSON."),
    ] = False,
    show_excluded: Annotated[
        bool,
        typer.Option("--show-excluded", help="Show memories excluded from the context package."),
    ] = False,
) -> None:
    """Build context using Mneno Core and local JSON storage."""
    workspace_path = find_workspace()
    if workspace_path is None:
        if json_output:
            typer.echo(json.dumps({"error": WORKSPACE_NOT_FOUND_MESSAGE}))
        else:
            warning(WORKSPACE_NOT_FOUND_MESSAGE)
        raise typer.Exit(code=1)

    try:
        client = get_workspace_client(workspace_path)
        package, session_supported = _build_context(
            client,
            query=query,
            budget=budget,
            preset=preset,
            include_inactive=include_inactive,
            include_archived=include_archived,
            session_id=session_id,
        )
    except (OSError, TypeError, ValidationError, ValueError) as exc:
        message = f"Unable to build context: {exc}"
        if json_output:
            typer.echo(json.dumps({"error": message}))
        else:
            error(message)
        raise typer.Exit(code=1) from exc

    output = _normalize_package(package, query=query, preset=preset.value)
    if json_output:
        typer.echo(json.dumps(asdict(output), indent=2))
        return

    if session_id is not None and not session_supported:
        warning("This Mneno Core version does not support session-aware context; continuing without --session.")

    console.print("[bold]Context[/bold]")
    console.print("-------")
    console.print(output.text)
    console.print()
    console.print("[bold]Stats[/bold]")
    console.print("-----")
    console.print(f"Used tokens: {output.stats.used_tokens} / {output.stats.max_tokens}")
    console.print(f"Remaining tokens: {output.stats.remaining_tokens}")
    console.print(f"Included: {output.stats.included_count}")
    console.print(f"Excluded: {output.stats.excluded_count}")

    if output.included:
        console.print()
        console.print("[bold]Included because:[/bold]")
        for index, item in enumerate(output.included, start=1):
            console.print(f"{index}. {item.content}")
            console.print(f"   ID: {item.memory_id}")
            console.print(f"   - {item.reason}")

    if show_excluded and output.excluded:
        console.print()
        console.print("[bold]Excluded:[/bold]")
        for index, item in enumerate(output.excluded, start=1):
            console.print(f"{index}. {item.content}")
            console.print(f"   ID: {item.memory_id}")
            console.print(f"   - {item.reason}")


def _build_context(
    client: MemoryClient,
    *,
    query: str,
    budget: int,
    preset: ContextPreset,
    include_inactive: bool,
    include_archived: bool,
    session_id: str | None,
) -> tuple[Any, bool]:
    parameters = signature(client.build_context).parameters
    context_options: dict[str, object] = {}
    if "policy" in parameters:
        context_options["policy"] = _context_policy(preset, budget=budget)
    else:
        if "budget" in parameters:
            context_options["budget"] = budget
        if "preset" in parameters:
            context_options["preset"] = preset.value
    if "include_inactive" in parameters:
        context_options["include_inactive"] = include_inactive
    if "include_archived" in parameters:
        context_options["include_archived"] = include_archived
    session_supported = "current_session_id" in parameters
    if session_supported:
        context_options["current_session_id"] = session_id
    build_context = cast(Callable[..., Any], client.build_context)
    return build_context(query, **context_options), session_supported


def _context_policy(preset: ContextPreset, *, budget: int) -> ContextPolicy:
    preset_policy = get_context_policy(preset)
    payload = preset_policy.model_dump()
    payload.update(max_tokens=budget, reserve_tokens=0)
    return ContextPolicy.model_validate(payload)


def _normalize_package(package: object, *, query: str, preset: str) -> ContextOutputPackage:
    stats = getattr(package, "stats", None)
    return ContextOutputPackage(
        query=_string_or_default(getattr(package, "query", None), query),
        text=_string_or_default(getattr(package, "text", None), "Relevant memories:"),
        preset=preset,
        stats=ContextOutputStats(
            max_tokens=_integer_or_placeholder(getattr(stats, "max_tokens", None)),
            available_tokens=_integer_or_placeholder(getattr(stats, "available_tokens", None)),
            used_tokens=_integer_or_placeholder(getattr(stats, "used_tokens", None)),
            remaining_tokens=_integer_or_placeholder(getattr(stats, "remaining_tokens", None)),
            included_count=_integer_or_placeholder(getattr(stats, "included_count", None)),
            excluded_count=_integer_or_placeholder(getattr(stats, "excluded_count", None)),
        ),
        included=[_normalize_item(item, preset=preset) for item in _object_list(getattr(package, "included", None))],
        excluded=[_normalize_item(item, preset=preset) for item in _object_list(getattr(package, "excluded", None))],
    )


def _normalize_item(item: object, *, preset: str) -> ContextOutputItem:
    reason = _string_or_placeholder(getattr(item, "reason", None))
    return ContextOutputItem(
        memory_id=_string_or_placeholder(getattr(item, "memory_id", None)),
        content=_string_or_placeholder(getattr(item, "content", None)),
        score=_float_or_placeholder(getattr(item, "score", None)),
        estimated_tokens=_integer_or_placeholder(getattr(item, "estimated_tokens", None)),
        reason=reason.replace("context policy 'custom'", f"context preset '{preset}'"),
    )


def _string_or_default(value: object, default: str) -> str:
    return value if isinstance(value, str) else default


def _string_or_placeholder(value: object) -> str:
    return _string_or_default(value, "-")


def _integer_or_placeholder(value: object) -> int | str:
    return value if isinstance(value, int) and not isinstance(value, bool) else "-"


def _float_or_placeholder(value: object) -> float | str:
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else "-"


def _object_list(value: object) -> list[object]:
    return list(value) if isinstance(value, (list, tuple)) else []
