import json
from pathlib import Path

from pytest import MonkeyPatch
from rich.text import Text
from typer.testing import CliRunner

from mneno.cli.app import app
from mneno.storage import JSONFileStorage

runner = CliRunner()


def initialize(tmp_path: Path, monkeypatch: MonkeyPatch) -> Path:
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["init"])
    assert result.exit_code == 0
    return tmp_path / ".mneno" / "memories.json"


def load_memories(path: Path) -> list[dict[str, object]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    memories = payload["memories"]
    assert isinstance(memories, list)
    return memories


def test_add_requires_workspace(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(app, ["add", "LOCOMO exposed ranking issues"])

    assert result.exit_code == 1
    assert "No Mneno workspace found. Run `mneno init`." in result.output


def test_add_creates_memory_in_workspace_storage(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    storage_path = initialize(tmp_path, monkeypatch)

    result = runner.invoke(app, ["add", "LOCOMO exposed ranking issues"])
    memories = JSONFileStorage(storage_path).list()

    assert result.exit_code == 0
    assert "Memory added" in result.output
    assert str(storage_path) in result.output
    assert len(memories) == 1
    assert memories[0].content == "LOCOMO exposed ranking issues"


def test_add_supports_memory_type(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    storage_path = initialize(tmp_path, monkeypatch)

    result = runner.invoke(app, ["add", "User prefers Python 3.11", "--type", "preference"])
    memory = JSONFileStorage(storage_path).list()[0]

    assert result.exit_code == 0
    assert memory.memory_type.value == "preference"
    assert "preference" in result.output


def test_add_supports_importance(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    storage_path = initialize(tmp_path, monkeypatch)

    result = runner.invoke(app, ["add", "Important memory", "--importance", "0.9"])
    memory = JSONFileStorage(storage_path).list()[0]

    assert result.exit_code == 0
    assert memory.importance == 0.9
    assert "0.90" in result.output


def test_add_supports_repeatable_tags(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    storage_path = initialize(tmp_path, monkeypatch)

    result = runner.invoke(app, ["add", "Tagged memory", "--tag", "Project", "--tag", "Python"])
    memory = JSONFileStorage(storage_path).list()[0]

    assert result.exit_code == 0
    assert memory.tags == ["project", "python"]
    assert "project, python" in result.output


def test_add_supports_repeatable_metadata(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    storage_path = initialize(tmp_path, monkeypatch)

    result = runner.invoke(
        app,
        [
            "add",
            "LOCOMO failed due to ranking",
            "--metadata",
            "source=locomo",
            "--metadata",
            "priority=high",
        ],
    )
    memory = JSONFileStorage(storage_path).list()[0]

    assert result.exit_code == 0
    assert memory.metadata == {"source": "locomo", "priority": "high"}


def test_add_rejects_invalid_metadata(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    storage_path = initialize(tmp_path, monkeypatch)

    result = runner.invoke(app, ["add", "Invalid metadata", "--metadata", "source"])

    assert result.exit_code == 2
    assert "Metadata must use key=value format." in result.output
    assert JSONFileStorage(storage_path).list() == []


def test_status_count_updates_after_add(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    initialize(tmp_path, monkeypatch)
    runner.invoke(app, ["add", "First memory"])

    result = runner.invoke(app, ["status"])

    assert result.exit_code == 0
    assert "Memories: 1" in result.output


def test_memory_persists_across_command_invocations(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    storage_path = initialize(tmp_path, monkeypatch)

    first = runner.invoke(app, ["add", "First memory"])
    second = runner.invoke(app, ["add", "Second memory"])
    memories = JSONFileStorage(storage_path).list()

    assert first.exit_code == 0
    assert second.exit_code == 0
    assert [memory.content for memory in memories] == ["First memory", "Second memory"]


def test_add_keeps_workspace_json_valid(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    storage_path = initialize(tmp_path, monkeypatch)

    result = runner.invoke(app, ["add", "Valid JSON memory", "--metadata", "source=cli"])
    memories = load_memories(storage_path)

    assert result.exit_code == 0
    assert len(memories) == 1
    assert memories[0]["content"] == "Valid JSON memory"
    assert json.loads(storage_path.read_text(encoding="utf-8"))["version"] == 1


def test_add_help_lists_supported_options() -> None:
    result = runner.invoke(app, ["add", "--help"])
    output = Text.from_ansi(result.output).plain

    assert result.exit_code == 0
    assert "--type" in output
    assert "--importance" in output
    assert "--tag" in output
    assert "--session" in output
    assert "--metadata" in output
