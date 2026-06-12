"""Local workspace creation, discovery, and inspection."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from mneno import MemoryClient
from mneno.cli.config import WorkspaceConfig
from mneno.storage import JSONFileStorage

WORKSPACE_DIRECTORY = ".mneno"
WORKSPACE_NOT_FOUND_MESSAGE = "No Mneno workspace found. Run `mneno init`."
CONFIG_FILENAME = "config.json"
MEMORIES_FILENAME = "memories.json"
SESSIONS_FILENAME = "sessions.json"
WORKSPACE_FORMAT_VERSION = 1


@dataclass(frozen=True)
class Workspace:
    """Paths and read operations for a discovered Mneno workspace."""

    path: Path

    @property
    def config_path(self) -> Path:
        return self.path / CONFIG_FILENAME

    @property
    def memories_path(self) -> Path:
        return self.path / MEMORIES_FILENAME

    @property
    def sessions_path(self) -> Path:
        return self.path / SESSIONS_FILENAME

    def load_config(self) -> WorkspaceConfig:
        """Load the workspace configuration."""
        return WorkspaceConfig.load(self.config_path)

    def memory_count(self) -> int:
        """Return the number of records in the memory document."""
        return _record_count(self.memories_path, "memories")

    def session_count(self) -> int:
        """Return the number of records in the session document."""
        return _record_count(self.sessions_path, "sessions")


def find_workspace(start: str | Path | None = None) -> Path | None:
    """Find the nearest ``.mneno`` directory from a path up to the filesystem root."""
    current = Path.cwd() if start is None else Path(start)
    current = current.resolve()
    if current.is_file():
        current = current.parent

    for directory in (current, *current.parents):
        candidate = directory / WORKSPACE_DIRECTORY
        if candidate.is_dir():
            return candidate
    return None


def initialize_workspace(directory: str | Path | None = None) -> tuple[Workspace, bool]:
    """Create missing workspace files in a directory without replacing existing files."""
    root = (Path.cwd() if directory is None else Path(directory)).resolve()
    workspace = Workspace(root / WORKSPACE_DIRECTORY)
    created = not workspace.path.exists()
    workspace.path.mkdir(parents=True, exist_ok=True)

    if not workspace.config_path.exists():
        WorkspaceConfig(workspace_name=root.name).save(workspace.config_path)
    _write_json_if_missing(
        workspace.memories_path,
        {"version": WORKSPACE_FORMAT_VERSION, "memories": []},
    )
    _write_json_if_missing(
        workspace.sessions_path,
        {"version": WORKSPACE_FORMAT_VERSION, "sessions": []},
    )
    return workspace, created


def get_workspace_client(workspace_path: Path) -> MemoryClient:
    """Create a Core client backed by a workspace's JSON storage file."""
    workspace = Workspace(workspace_path)
    workspace.load_config()
    return MemoryClient(storage=JSONFileStorage(workspace.memories_path))


def _write_json_if_missing(path: Path, payload: dict[str, Any]) -> None:
    try:
        with path.open("x", encoding="utf-8") as file:
            json.dump(payload, file, indent=2, sort_keys=True)
            file.write("\n")
    except FileExistsError:
        pass


def _record_count(path: Path, key: str) -> int:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Invalid workspace document: {path}")
    if payload.get("version") != WORKSPACE_FORMAT_VERSION:
        raise ValueError(f"Unsupported workspace document version: {path}")
    records = payload.get(key)
    if not isinstance(records, list):
        raise ValueError(f"Invalid workspace document: {path}")
    return len(records)
