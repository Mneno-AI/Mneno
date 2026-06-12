from pathlib import Path

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


def test_cli_help_lists_commands() -> None:
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "init" in result.output
    assert "add" in result.output
    assert "search" in result.output
    assert "context" in result.output
    assert "recent" in result.output
    assert "status" in result.output


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
