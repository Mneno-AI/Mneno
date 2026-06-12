import json
from datetime import UTC
from pathlib import Path

from pydantic import ValidationError
from pytest import raises

from mneno.cli.config import WorkspaceConfig


def test_workspace_config_save_and_load(tmp_path: Path) -> None:
    path = tmp_path / "config.json"
    config = WorkspaceConfig(workspace_name="example")

    config.save(path)
    loaded = WorkspaceConfig.load(path)

    assert loaded == config
    assert loaded.created_at.tzinfo == UTC
    assert json.loads(path.read_text(encoding="utf-8"))["storage"] == "json"


def test_workspace_config_validation_rejects_unknown_storage(tmp_path: Path) -> None:
    path = tmp_path / "config.json"
    path.write_text(
        json.dumps(
            {
                "version": 1,
                "storage": "sqlite",
                "created_at": "2026-06-12T00:00:00Z",
                "workspace_name": "example",
            }
        ),
        encoding="utf-8",
    )

    with raises(ValidationError):
        WorkspaceConfig.load(path)


def test_workspace_config_validation_rejects_extra_fields() -> None:
    with raises(ValidationError):
        WorkspaceConfig.model_validate(
            {
                "workspace_name": "example",
                "unexpected": True,
            }
        )
