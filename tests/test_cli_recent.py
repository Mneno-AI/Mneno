import json
from pathlib import Path

from pytest import MonkeyPatch
from typer.testing import CliRunner

from mneno.cli.app import app
from mneno.cli.workspace import get_workspace_client
from mneno.hierarchy import MemoryLayer
from mneno.models import MemoryStatus

runner = CliRunner()


def initialize(tmp_path: Path, monkeypatch: MonkeyPatch) -> Path:
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["init"])
    assert result.exit_code == 0
    return tmp_path / ".mneno"


def add_memory(text: str, *options: str) -> None:
    result = runner.invoke(app, ["add", text, *options])
    assert result.exit_code == 0


def test_recent_requires_workspace(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(app, ["recent"])

    assert result.exit_code == 1
    assert "No Mneno workspace found. Run `mneno init`." in result.output


def test_recent_returns_added_memories_newest_first(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    initialize(tmp_path, monkeypatch)
    add_memory("First memory", "--tag", "first")
    add_memory("Second memory", "--tag", "second")

    result = runner.invoke(app, ["recent"])

    assert result.exit_code == 0
    assert "Recent memories" in result.output
    assert result.output.index("Second memory") < result.output.index("First memory")
    assert "Type: semantic" in result.output
    assert "Layer: semantic" in result.output
    assert "Status: active" in result.output
    assert "Tags: second" in result.output
    assert "Updated:" in result.output
    assert "Created:" in result.output


def test_recent_respects_limit(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    initialize(tmp_path, monkeypatch)
    add_memory("First memory")
    add_memory("Second memory")
    add_memory("Third memory")

    result = runner.invoke(app, ["recent", "--limit", "2", "--json"])
    payload = json.loads(result.output)

    assert result.exit_code == 0
    assert len(payload) == 2
    assert [item["content"] for item in payload] == ["Third memory", "Second memory"]


def test_recent_json_output_has_stable_shape(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    initialize(tmp_path, monkeypatch)
    add_memory("LOCOMO exposed ranking issues", "--type", "operational", "--tag", "locomo")

    result = runner.invoke(app, ["recent", "--json"])
    payload = json.loads(result.output)

    assert result.exit_code == 0
    assert len(payload) == 1
    assert set(payload[0]) == {
        "memory_id",
        "content",
        "memory_type",
        "layer",
        "status",
        "tags",
        "created_at",
        "updated_at",
    }
    assert payload[0]["content"] == "LOCOMO exposed ranking issues"
    assert payload[0]["memory_type"] == "operational"
    assert payload[0]["layer"] == "operational"
    assert payload[0]["status"] == "active"
    assert payload[0]["tags"] == ["locomo"]
    assert payload[0]["created_at"]
    assert payload[0]["updated_at"]


def test_recent_excludes_inactive_and_archived_by_default(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    workspace_path = initialize(tmp_path, monkeypatch)
    client = get_workspace_client(workspace_path)
    active = client.add("Active memory")
    archived = client.add("Archived memory")
    superseded = client.add("Superseded memory")
    client.store.update(archived.model_copy(update={"status": MemoryStatus.ARCHIVED, "layer": MemoryLayer.ARCHIVED}))
    client.store.update(superseded.model_copy(update={"status": MemoryStatus.SUPERSEDED}))

    result = runner.invoke(app, ["recent", "--json"])
    payload = json.loads(result.output)

    assert result.exit_code == 0
    assert [item["memory_id"] for item in payload] == [active.id]


def test_recent_include_flags_expand_lifecycle_results(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    workspace_path = initialize(tmp_path, monkeypatch)
    client = get_workspace_client(workspace_path)
    active = client.add("Active memory")
    archived = client.add("Archived memory")
    superseded = client.add("Superseded memory")
    client.store.update(archived.model_copy(update={"status": MemoryStatus.ARCHIVED, "layer": MemoryLayer.ARCHIVED}))
    client.store.update(superseded.model_copy(update={"status": MemoryStatus.SUPERSEDED}))

    archived_result = runner.invoke(app, ["recent", "--include-archived", "--json"])
    inactive_result = runner.invoke(app, ["recent", "--include-inactive", "--json"])
    archived_payload = json.loads(archived_result.output)
    inactive_payload = json.loads(inactive_result.output)

    assert archived_result.exit_code == 0
    assert {item["memory_id"] for item in archived_payload} == {active.id, archived.id}
    assert inactive_result.exit_code == 0
    assert {item["memory_id"] for item in inactive_payload} == {active.id, archived.id, superseded.id}


def test_recent_empty_workspace_is_safe(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    initialize(tmp_path, monkeypatch)

    human = runner.invoke(app, ["recent"])
    json_result = runner.invoke(app, ["recent", "--json"])

    assert human.exit_code == 0
    assert "No memories found." in human.output
    assert json.loads(json_result.output) == []


def test_recent_help_lists_supported_options() -> None:
    result = runner.invoke(app, ["recent", "--help"])

    assert result.exit_code == 0
    assert "--limit" in result.output
    assert "--json" in result.output
    assert "archived memories" in result.output
    assert "inactive memories" in result.output
