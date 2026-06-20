from pathlib import Path
from subprocess import run

from pytest import MonkeyPatch
from typer.testing import CliRunner

from mneno.cli.app import app, get_version

runner = CliRunner()


def test_cli_without_command_shows_help() -> None:
    result = runner.invoke(app)

    assert result.exit_code == 0
    assert "Mneno CLI" in result.output
    assert "Available Commands" in result.output
    assert "init" in result.output
    assert "add" in result.output
    assert "search" in result.output
    assert "context" in result.output
    assert "recent" in result.output
    assert "status" in result.output
    assert "setup-agent" in result.output
    assert "completion" in result.output


def test_cli_help_lists_commands() -> None:
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "init" in result.output
    assert "add" in result.output
    assert "search" in result.output
    assert "context" in result.output
    assert "recent" in result.output
    assert "status" in result.output
    assert "setup-agent" in result.output
    assert "completion" in result.output


def test_cli_completion_generates_shell_scripts() -> None:
    expected_markers = {
        "bash": "complete -o default -F _mneno_completion mneno",
        "zsh": "compdef _mneno_completion mneno",
        "fish": "complete --command mneno",
        "powershell": "Register-ArgumentCompleter -Native -CommandName mneno",
        "pwsh": "Register-ArgumentCompleter -Native -CommandName mneno",
    }

    for shell, marker in expected_markers.items():
        result = runner.invoke(app, ["completion", shell])

        assert result.exit_code == 0
        assert marker in result.output
        assert "_MNENO_COMPLETE" not in result.output
        assert "complete_bash" not in result.output


def test_cli_bash_completion_suggests_matching_subcommands_without_running_mneno() -> None:
    generated = runner.invoke(app, ["completion", "bash"])
    assert generated.exit_code == 0
    script = (
        generated.output
        + "\nCOMP_WORDS=(mneno se); COMP_CWORD=1; _mneno_completion; "
        + "printf '%s\\n' \"${COMPREPLY[@]}\""
    )

    completed = run(
        ["bash", "-c", script],
        check=True,
        capture_output=True,
        text=True,
    )

    assert completed.stdout.splitlines() == ["search", "setup-agent"]


def test_cli_bash_completion_suggests_option_values() -> None:
    generated = runner.invoke(app, ["completion", "bash"])
    assert generated.exit_code == 0
    script = (
        generated.output
        + "\nCOMP_WORDS=(mneno add --type s); COMP_CWORD=3; _mneno_completion; "
        + "printf '%s\\n' \"${COMPREPLY[@]}\""
    )

    completed = run(
        ["bash", "-c", script],
        check=True,
        capture_output=True,
        text=True,
    )

    assert completed.stdout.splitlines() == ["semantic"]


def test_cli_version() -> None:
    result = runner.invoke(app, ["--version"])

    assert result.exit_code == 0
    assert result.output.strip() == f"Mneno {get_version()}"


def test_cli_init_creates_workspace_and_is_idempotent(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)

    first = runner.invoke(app, ["init"])
    second = runner.invoke(app, ["init"])

    assert first.exit_code == 0
    assert "Initialized Mneno workspace" in first.output
    assert (tmp_path / ".mneno" / "config.json").exists()
    assert second.exit_code == 0
    assert "Workspace already exists" in second.output


def test_cli_init_reports_regular_file_workspace_collision(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".mneno").write_text("not a directory", encoding="utf-8")

    result = runner.invoke(app, ["init"])

    assert result.exit_code == 1
    assert "Cannot initialize workspace: .mneno exists and is not a directory." in result.output
    assert "Traceback" not in result.output


def test_cli_status_shows_empty_workspace(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    runner.invoke(app, ["init"])

    result = runner.invoke(app, ["status"])

    assert result.exit_code == 0
    assert str(tmp_path / ".mneno") in result.output
    assert "Storage:" in result.output
    assert "JSON" in result.output
    assert "Memories:" in result.output
    assert "Sessions:" in result.output
    assert "Version:" in result.output


def test_cli_status_reports_missing_workspace(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(app, ["status"])

    assert result.exit_code == 1
    assert "No Mneno workspace found. Run `mneno init`." in result.output
