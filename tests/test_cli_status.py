import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from pytest import MonkeyPatch
from typer.testing import CliRunner

from mneno.cli.app import app, get_version
from mneno.cli.workspace import get_workspace_client
from mneno.hierarchy import MemoryLayer
from mneno.models import MemoryStatus

runner = CliRunner()


def initialize(tmp_path: Path, monkeypatch: MonkeyPatch) -> Path:
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["init"])
    assert result.exit_code == 0
    return tmp_path / ".mneno"


def test_status_empty_workspace_has_enhanced_zero_state(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    initialize(tmp_path, monkeypatch)

    result = runner.invoke(app, ["status"])

    assert result.exit_code == 0
    assert "Counts:" in result.output
    assert "Memories: 0" in result.output
    assert "Active: 0" in result.output
    assert "Sessions: 0" in result.output
    assert "Layers:" in result.output
    assert "semantic: 0" in result.output
    assert "Recent:" in result.output
    assert "Last updated: -" in result.output
    assert "Latest memory: -" in result.output
    assert "Workspace: 1" in result.output
    assert f"Mneno: {get_version()}" in result.output
    assert "No memories yet. Add one with:" in result.output
    assert 'mneno add "Your first memory"' in result.output


def test_status_counts_layers_sessions_and_latest_memory(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    workspace_path = initialize(tmp_path, monkeypatch)
    client = get_workspace_client(workspace_path)
    base_time = datetime(2026, 6, 12, 10, 0, tzinfo=UTC)
    short = client.add("Short-term memory")
    working = client.add("Working memory")
    episodic = client.add("Episodic memory")
    conflicted = client.add("Conflicted memory")
    operational = client.add("Operational memory")
    archived = client.add("Archived memory")
    superseded = client.add("Latest superseded memory")
    client.store.update(short.model_copy(update={"layer": MemoryLayer.SHORT_TERM, "updated_at": base_time}))
    client.store.update(
        working.model_copy(update={"layer": MemoryLayer.WORKING, "updated_at": base_time + timedelta(minutes=1)})
    )
    client.store.update(
        episodic.model_copy(update={"layer": MemoryLayer.EPISODIC, "updated_at": base_time + timedelta(minutes=2)})
    )
    client.store.update(
        conflicted.model_copy(
            update={"status": MemoryStatus.CONFLICTED, "updated_at": base_time + timedelta(minutes=3)}
        )
    )
    client.store.update(
        operational.model_copy(
            update={"layer": MemoryLayer.OPERATIONAL, "updated_at": base_time + timedelta(minutes=4)}
        )
    )
    client.store.update(
        archived.model_copy(
            update={
                "status": MemoryStatus.ARCHIVED,
                "layer": MemoryLayer.ARCHIVED,
                "updated_at": base_time + timedelta(minutes=5),
            }
        )
    )
    client.store.update(
        superseded.model_copy(
            update={"status": MemoryStatus.SUPERSEDED, "updated_at": base_time + timedelta(minutes=6)}
        )
    )
    client.create_session(title="Demo session")

    result = runner.invoke(app, ["status"])

    assert result.exit_code == 0
    assert "Memories: 7" in result.output
    assert "Active: 4" in result.output
    assert "Archived: 1" in result.output
    assert "Superseded: 1" in result.output
    assert "Conflicted: 1" in result.output
    assert "Sessions: 1" in result.output
    assert "short_term: 1" in result.output
    assert "working: 1" in result.output
    assert "episodic: 1" in result.output
    assert "semantic: 2" in result.output
    assert "operational: 1" in result.output
    assert "archived: 1" in result.output
    assert "Last updated: 2026-06-12T10:06:00+00:00" in result.output
    assert "Latest memory: Latest superseded memory" in result.output


def test_status_json_output_has_stable_shape(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    initialize(tmp_path, monkeypatch)
    runner.invoke(app, ["add", "LOCOMO exposed ranking issues"])

    result = runner.invoke(app, ["status", "--json"])
    payload = json.loads(result.output)

    assert result.exit_code == 0
    assert set(payload) == {"workspace", "storage", "counts", "layers", "recent", "version"}
    assert payload["storage"] == "json"
    assert payload["counts"] == {
        "memories": 1,
        "active": 1,
        "archived": 0,
        "superseded": 0,
        "conflicted": 0,
        "sessions": 0,
    }
    assert payload["layers"] == {
        "short_term": 0,
        "working": 0,
        "episodic": 0,
        "semantic": 1,
        "operational": 0,
        "archived": 0,
    }
    assert payload["recent"]["last_updated"] is not None
    assert payload["recent"]["latest_memory"] == "LOCOMO exposed ranking issues"
    assert payload["version"] == {"workspace": 1, "mneno": get_version()}


def test_status_missing_workspace_json_is_machine_readable(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(app, ["status", "--json"])

    assert result.exit_code == 1
    assert json.loads(result.output) == {"error": "No Mneno workspace found. Run `mneno init`."}


def test_status_help_lists_json_option() -> None:
    result = runner.invoke(app, ["status", "--help"])

    assert result.exit_code == 0
    assert "--json" in result.output
    assert "machine-readable JSON" in result.output
