import json
from pathlib import Path

from mneno.cli.workspace import find_workspace, get_workspace_client, initialize_workspace


def test_find_workspace_in_current_directory(tmp_path: Path) -> None:
    workspace, _ = initialize_workspace(tmp_path)

    assert find_workspace(tmp_path) == workspace.path


def test_find_workspace_in_parent_directory(tmp_path: Path) -> None:
    workspace, _ = initialize_workspace(tmp_path)
    nested = tmp_path / "src" / "package"
    nested.mkdir(parents=True)

    assert find_workspace(nested) == workspace.path


def test_find_workspace_returns_none_when_missing(tmp_path: Path) -> None:
    assert find_workspace(tmp_path) is None


def test_initialize_workspace_creates_expected_structure(tmp_path: Path) -> None:
    workspace, created = initialize_workspace(tmp_path)

    assert created is True
    assert workspace.path == tmp_path / ".mneno"
    assert workspace.config_path.exists()
    assert json.loads(workspace.memories_path.read_text(encoding="utf-8")) == {
        "version": 1,
        "memories": [],
    }
    assert json.loads(workspace.sessions_path.read_text(encoding="utf-8")) == {
        "version": 1,
        "sessions": [],
    }
    assert workspace.load_config().workspace_name == tmp_path.name


def test_initialize_workspace_is_idempotent(tmp_path: Path) -> None:
    first, first_created = initialize_workspace(tmp_path)
    second, second_created = initialize_workspace(tmp_path)

    assert first_created is True
    assert second_created is False
    assert second == first


def test_initialize_workspace_preserves_existing_files(tmp_path: Path) -> None:
    workspace, _ = initialize_workspace(tmp_path)
    config_content = workspace.config_path.read_text(encoding="utf-8")
    memory_content = '{"version": 1, "memories": [{"id": "existing"}]}\n'
    session_content = '{"version": 1, "sessions": [{"id": "existing"}]}\n'
    workspace.memories_path.write_text(memory_content, encoding="utf-8")
    workspace.sessions_path.write_text(session_content, encoding="utf-8")

    initialize_workspace(tmp_path)

    assert workspace.config_path.read_text(encoding="utf-8") == config_content
    assert workspace.memories_path.read_text(encoding="utf-8") == memory_content
    assert workspace.sessions_path.read_text(encoding="utf-8") == session_content


def test_get_workspace_client_uses_json_storage_without_tracing(tmp_path: Path) -> None:
    workspace, _ = initialize_workspace(tmp_path)

    client = get_workspace_client(workspace.path)
    memory = client.add("Stored through workspace client.")

    assert client.trace_enabled is False
    assert client.trace_recorder is None
    assert [stored.id for stored in get_workspace_client(workspace.path).list()] == [memory.id]
