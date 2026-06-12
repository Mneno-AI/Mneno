"""Typed configuration for local Mneno workspaces."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class WorkspaceConfig(BaseModel):
    """Versioned settings stored in ``.mneno/config.json``."""

    model_config = ConfigDict(extra="forbid")

    version: Literal[1] = 1
    storage: Literal["json"] = "json"
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    workspace_name: str = Field(min_length=1)

    @classmethod
    def load(cls, path: str | Path) -> WorkspaceConfig:
        """Load and validate a workspace configuration file."""
        return cls.model_validate_json(Path(path).read_text(encoding="utf-8"))

    def save(self, path: str | Path) -> None:
        """Write this configuration as stable, human-readable JSON."""
        config_path = Path(path)
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(self.model_dump_json(indent=2) + "\n", encoding="utf-8")
