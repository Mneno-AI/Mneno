"""Search memories in the local Mneno workspace."""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import asdict, dataclass
from inspect import signature
from typing import Annotated, Any, cast

import typer
from pydantic import ValidationError
from rich.table import Table

from mneno import MemoryClient
from mneno.cli.output import console, error, warning
from mneno.cli.workspace import WORKSPACE_NOT_FOUND_MESSAGE, find_workspace, get_workspace_client


@dataclass(frozen=True)
class SearchOutputItem:
    """Stable CLI representation of a Core search result."""

    rank: int | str
    memory_id: str
    content: str
    score: float | str
    memory_type: str
    layer: str
    status: str
    tags: list[str]
    reasons: list[str]


def search_command(
    query: Annotated[str, typer.Argument(help="Query used to rank local memories.")],
    limit: Annotated[
        int,
        typer.Option("--limit", "-l", min=1, help="Maximum number of results."),
    ] = 5,
    include_inactive: Annotated[
        bool,
        typer.Option("--include-inactive", help="Include superseded and other inactive memories."),
    ] = False,
    include_archived: Annotated[
        bool,
        typer.Option("--include-archived", help="Include archived memories."),
    ] = False,
    session_id: Annotated[
        str | None,
        typer.Option("--session", help="Current session ID used for session-aware ranking."),
    ] = None,
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Write machine-readable JSON."),
    ] = False,
    show_reasons: Annotated[
        bool,
        typer.Option("--show-reasons/--no-show-reasons", help="Show scoring reasons in terminal output."),
    ] = True,
) -> None:
    """Search local memories using Mneno Core scoring."""
    workspace_path = find_workspace()
    if workspace_path is None:
        if json_output:
            typer.echo(json.dumps({"error": WORKSPACE_NOT_FOUND_MESSAGE}))
        else:
            warning(WORKSPACE_NOT_FOUND_MESSAGE)
        raise typer.Exit(code=1)

    try:
        client = get_workspace_client(workspace_path)
        results, session_supported = _search_client(
            client,
            query=query,
            limit=limit,
            include_inactive=include_inactive,
            include_archived=include_archived,
            session_id=session_id,
        )
    except (OSError, TypeError, ValidationError, ValueError) as exc:
        if json_output:
            typer.echo(json.dumps({"error": f"Unable to search memories: {exc}"}))
        else:
            error(f"Unable to search memories: {exc}")
        raise typer.Exit(code=1) from exc

    items = [_normalize_result(result) for result in results if _has_query_relevance(result)]
    if json_output:
        typer.echo(json.dumps([asdict(item) for item in items], indent=2))
        return

    if session_id is not None and not session_supported:
        warning("This Mneno Core version does not support session-aware search; continuing without --session.")

    if not items:
        console.print("No memories found for query:")
        console.print(f'"{query}"')
        return

    table = Table(show_header=True, header_style="bold")
    table.add_column("Rank", justify="right")
    table.add_column("Score", justify="right")
    table.add_column("Type")
    table.add_column("Layer")
    table.add_column("Status")
    table.add_column("Memory")
    for item in items:
        score = f"{item.score:.3f}" if isinstance(item.score, float) else item.score
        table.add_row(
            str(item.rank),
            score,
            item.memory_type,
            item.layer,
            item.status,
            item.content,
        )
    console.print(table)

    if show_reasons:
        for item in items:
            if not item.reasons:
                continue
            console.print()
            console.print(f"[bold]Reasons for #{item.rank}:[/bold]")
            for reason in item.reasons:
                console.print(f"- {reason}")


def _search_client(
    client: MemoryClient,
    *,
    query: str,
    limit: int,
    include_inactive: bool,
    include_archived: bool,
    session_id: str | None,
) -> tuple[list[Any], bool]:
    parameters = signature(client.search).parameters
    search_options: dict[str, object] = {
        "limit": limit,
        "include_inactive": include_inactive,
        "include_archived": include_archived,
    }
    session_supported = "current_session_id" in parameters
    if session_supported:
        search_options["current_session_id"] = session_id
    search = cast(Callable[..., list[Any]], client.search)
    return list(search(query, **search_options)), session_supported


def _normalize_result(result: object) -> SearchOutputItem:
    memory = getattr(result, "memory", None)
    score = getattr(result, "score", None)
    return SearchOutputItem(
        rank=_integer_or_placeholder(getattr(result, "rank", None)),
        memory_id=_string_or_placeholder(getattr(memory, "id", None)),
        content=_string_or_placeholder(getattr(memory, "content", None)),
        score=_float_or_placeholder(getattr(score, "total", None)),
        memory_type=_enum_value_or_placeholder(getattr(memory, "memory_type", None)),
        layer=_enum_value_or_placeholder(getattr(memory, "layer", None)),
        status=_enum_value_or_placeholder(getattr(memory, "status", None)),
        tags=_string_list(getattr(memory, "tags", None)),
        reasons=_string_list(getattr(score, "reasons", None)),
    )


def _has_query_relevance(result: object) -> bool:
    """Hide known zero-relevance results while preserving compatibility with older result models."""
    score = getattr(result, "score", None)
    relevance = getattr(score, "relevance", None)
    if not isinstance(relevance, (int, float)) or isinstance(relevance, bool):
        return True
    return relevance > 0


def _string_or_placeholder(value: object) -> str:
    return value if isinstance(value, str) else "-"


def _integer_or_placeholder(value: object) -> int | str:
    return value if isinstance(value, int) and not isinstance(value, bool) else "-"


def _float_or_placeholder(value: object) -> float | str:
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else "-"


def _enum_value_or_placeholder(value: object) -> str:
    enum_value = getattr(value, "value", value)
    return enum_value if isinstance(enum_value, str) else "-"


def _string_list(value: object) -> list[str]:
    if not isinstance(value, (list, tuple)):
        return []
    return [item for item in value if isinstance(item, str)]
