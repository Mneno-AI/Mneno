"""Generate fast, shell-native completion scripts for the Mneno CLI."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Annotated, Protocol, cast

import typer

from mneno.cli.integrations import SUPPORTED_AGENTS


class CompletionShell(StrEnum):
    """Shells supported by Mneno's completion generator."""

    BASH = "bash"
    ZSH = "zsh"
    FISH = "fish"
    POWERSHELL = "powershell"
    PWSH = "pwsh"


@dataclass(frozen=True)
class CommandCompletion:
    """Static completion metadata for one command."""

    options: tuple[str, ...]
    option_values: dict[str, tuple[str, ...]]
    positional_values: tuple[str, ...]


@dataclass(frozen=True)
class CompletionData:
    """Completion metadata derived from the registered Click command tree."""

    commands: tuple[str, ...]
    root_options: tuple[str, ...]
    command_data: dict[str, CommandCompletion]


class _Command(Protocol):
    params: list[object]


class _CommandGroup(_Command, Protocol):
    def list_commands(self, context: object) -> list[str]: ...

    def get_command(self, context: object, name: str) -> _Command | None: ...


def completion_command(
    context: typer.Context,
    shell: Annotated[
        CompletionShell,
        typer.Argument(help="Shell to generate completion for."),
    ],
) -> None:
    """Write a sourceable, shell-native completion script to standard output."""
    data = _collect_completion_data(context)
    renderers = {
        CompletionShell.BASH: _render_bash,
        CompletionShell.ZSH: _render_zsh,
        CompletionShell.FISH: _render_fish,
        CompletionShell.POWERSHELL: _render_powershell,
        CompletionShell.PWSH: _render_powershell,
    }
    typer.echo(renderers[shell](data))


def _collect_completion_data(context: typer.Context) -> CompletionData:
    parent = context.parent
    if parent is None:  # pragma: no cover - Typer always provides this
        raise RuntimeError("Unable to inspect the root Mneno command.")

    group = cast(_CommandGroup, parent.command)
    command_data: dict[str, CommandCompletion] = {}
    command_names = tuple(group.list_commands(parent))
    for name in command_names:
        command = group.get_command(parent, name)
        if command is None:  # pragma: no cover - list_commands only returns registered commands
            continue
        command_data[name] = _inspect_command(command)

    command_data["setup-agent"] = CommandCompletion(
        options=command_data["setup-agent"].options,
        option_values=command_data["setup-agent"].option_values,
        positional_values=SUPPORTED_AGENTS,
    )
    return CompletionData(
        commands=command_names,
        root_options=_option_names(group),
        command_data=command_data,
    )


def _inspect_command(command: _Command) -> CommandCompletion:
    option_values: dict[str, tuple[str, ...]] = {}
    positional_values: tuple[str, ...] = ()
    for parameter in command.params:
        values = _choice_values(parameter)
        options = _parameter_options(parameter)
        if options and values:
            for option in options:
                option_values[option] = values
        elif values:
            positional_values = values

    return CommandCompletion(
        options=_option_names(command),
        option_values=option_values,
        positional_values=positional_values,
    )


def _option_names(command: _Command) -> tuple[str, ...]:
    options = tuple(option for parameter in command.params for option in _parameter_options(parameter))
    return options if "--help" in options else (*options, "--help")


def _parameter_options(parameter: object) -> tuple[str, ...]:
    options = getattr(parameter, "opts", None)
    secondary_options = getattr(parameter, "secondary_opts", None)
    if not isinstance(options, Sequence) or isinstance(options, str):
        return ()
    if not isinstance(secondary_options, Sequence) or isinstance(secondary_options, str):
        return ()
    return tuple(str(option) for option in (*options, *secondary_options))


def _choice_values(parameter: object) -> tuple[str, ...]:
    parameter_type = getattr(parameter, "type", None)
    choices = getattr(parameter_type, "choices", None)
    if not isinstance(choices, Sequence) or isinstance(choices, str):
        return ()
    return tuple(str(choice) for choice in choices)


def _render_bash(data: CompletionData) -> str:
    root_candidates = " ".join((*data.commands, *data.root_options))
    command_cases = "\n".join(_bash_command_case(name, spec) for name, spec in data.command_data.items())
    return f"""_mneno_completion() {{
    local current="${{COMP_WORDS[COMP_CWORD]}}"
    local previous="${{COMP_WORDS[COMP_CWORD-1]}}"
    local command="${{COMP_WORDS[1]}}"
    local candidates

    if (( COMP_CWORD == 1 )); then
        candidates="{root_candidates}"
    else
        case "$command" in
{command_cases}
        esac
    fi

    COMPREPLY=( $(compgen -W "$candidates" -- "$current") )
}}

complete -o default -F _mneno_completion mneno"""


def _bash_command_case(name: str, spec: CommandCompletion) -> str:
    option_cases = "\n".join(
        f'                {option}) candidates="{" ".join(values)}" ;;' for option, values in spec.option_values.items()
    )
    positional = " ".join(spec.positional_values)
    options = " ".join(spec.options)
    fallback = f"{positional} {options}".strip()
    candidate_selection = (
        f"""            case "$previous" in
{option_cases}
                *) candidates="{fallback}" ;;
            esac"""
        if option_cases
        else f'            candidates="{fallback}"'
    )
    return f"""            {name})
{candidate_selection}
                ;;"""


def _render_zsh(data: CompletionData) -> str:
    root_candidates = " ".join((*data.commands, *data.root_options))
    command_cases = "\n".join(_zsh_command_case(name, spec) for name, spec in data.command_data.items())
    return f"""#compdef mneno

_mneno_completion() {{
    local current="${{words[CURRENT]}}"
    local previous="${{words[CURRENT-1]}}"
    local command="${{words[2]}}"
    local -a candidates

    if (( CURRENT == 2 )); then
        candidates=({root_candidates})
    else
        case "$command" in
{command_cases}
        esac
    fi

    compadd -- "${{candidates[@]}}"
}}

compdef _mneno_completion mneno"""


def _zsh_command_case(name: str, spec: CommandCompletion) -> str:
    option_cases = "\n".join(
        f"                {option}) candidates=({' '.join(values)}) ;;" for option, values in spec.option_values.items()
    )
    fallback = " ".join((*spec.positional_values, *spec.options))
    candidate_selection = (
        f"""            case "$previous" in
{option_cases}
                *) candidates=({fallback}) ;;
            esac"""
        if option_cases
        else f"            candidates=({fallback})"
    )
    return f"""            {name})
{candidate_selection}
                ;;"""


def _render_fish(data: CompletionData) -> str:
    lines = ["complete --command mneno --no-files"]
    for command in data.commands:
        lines.append(f"complete --command mneno --condition __fish_use_subcommand --arguments {command}")
    for option in data.root_options:
        lines.append(_fish_option(option, "__fish_use_subcommand"))
    for command, spec in data.command_data.items():
        condition = f"'__fish_seen_subcommand_from {command}'"
        for option in spec.options:
            values = spec.option_values.get(option, ())
            lines.append(_fish_option(option, condition, values))
        if spec.positional_values:
            joined_values = " ".join(spec.positional_values)
            lines.append(f"complete --command mneno --condition {condition} --arguments '{joined_values}'")
    return "\n".join(lines)


def _fish_option(option: str, condition: str, values: tuple[str, ...] = ()) -> str:
    flag = f"--long-option {option[2:]}" if option.startswith("--") else f"--short-option {option[1:]}"
    arguments = f" --arguments '{' '.join(values)}' --require-parameter" if values else ""
    return f"complete --command mneno --condition {condition} {flag}{arguments}"


def _render_powershell(data: CompletionData) -> str:
    commands = _powershell_array(data.commands)
    root_candidates = _powershell_array((*data.commands, *data.root_options))
    cases = "\n".join(_powershell_command_case(name, spec) for name, spec in data.command_data.items())
    return f"""Register-ArgumentCompleter -Native -CommandName mneno -ScriptBlock {{
    param($wordToComplete, $commandAst, $cursorPosition)

    $elements = @($commandAst.CommandElements | ForEach-Object {{ $_.Extent.Text }})
    $commands = {commands}
    $command = if ($elements.Count -gt 1) {{ $elements[1] }} else {{ '' }}
    $previous = if ($elements.Count -gt 1) {{ $elements[$elements.Count - 2] }} else {{ '' }}

    if ($commands -notcontains $command -or ($elements.Count -eq 2 -and $wordToComplete -eq $command)) {{
        $candidates = {root_candidates}
    }} else {{
        switch ($command) {{
{cases}
        }}
    }}

    $candidates |
        Where-Object {{ $_ -like "$wordToComplete*" }} |
        ForEach-Object {{ [System.Management.Automation.CompletionResult]::new($_, $_, 'ParameterValue', $_) }}
}}"""


def _powershell_command_case(name: str, spec: CommandCompletion) -> str:
    fallback = _powershell_array((*spec.positional_values, *spec.options))
    value_cases = "\n".join(
        f"                    '{option}' {{ $candidates = {_powershell_array(values)}; break }}"
        for option, values in spec.option_values.items()
    )
    if not value_cases:
        return f"            '{name}' {{ $candidates = {fallback} }}"
    return f"""            '{name}' {{
                switch ($previous) {{
{value_cases}
                    default {{ $candidates = {fallback} }}
                }}
            }}"""


def _powershell_array(values: tuple[str, ...]) -> str:
    return "@(" + ", ".join(f"'{value}'" for value in values) + ")"
