"""Template metadata for CLI agent integrations."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AgentTemplate:
    """Source and destination metadata for one agent template."""

    name: str
    skill_target: Path
    instructions_source: Path | None = None
    instructions_target: Path | None = None


SUPPORTED_AGENTS = ("codex", "claude-code", "cursor", "gemini-cli", "windsurf")

AGENT_TEMPLATES: dict[str, AgentTemplate] = {
    "codex": AgentTemplate(
        name="codex",
        skill_target=Path(".agents") / "skills" / "mneno-memory",
        instructions_source=Path("codex") / "AGENTS.md",
        instructions_target=Path("AGENTS.md"),
    ),
    "claude-code": AgentTemplate(
        name="claude-code",
        skill_target=Path(".claude") / "skills" / "mneno-memory",
    ),
    "cursor": AgentTemplate(
        name="cursor",
        skill_target=Path(".agents") / "skills" / "mneno-memory",
        instructions_source=Path("cursor") / "AGENTS.md",
        instructions_target=Path("AGENTS.md"),
    ),
    "gemini-cli": AgentTemplate(
        name="gemini-cli",
        skill_target=Path(".agents") / "skills" / "mneno-memory",
        instructions_source=Path("gemini-cli") / "AGENTS.md",
        instructions_target=Path("AGENTS.md"),
    ),
    "windsurf": AgentTemplate(
        name="windsurf",
        skill_target=Path(".agents") / "skills" / "mneno-memory",
        instructions_source=Path("windsurf") / "AGENTS.md",
        instructions_target=Path("AGENTS.md"),
    ),
}

SKILL_SOURCE = Path("shared") / "mneno-memory" / "SKILL.md"

SHARED_DOCS = (
    "AGENT_WORKFLOW.md",
    "MEMORY_GUIDELINES.md",
    "COMMAND_REFERENCE.md",
)


def integration_templates_root() -> Path:
    """Return the repository or installed package root that contains integration templates."""
    root = Path(__file__).resolve().parents[3] / "integrations"
    if not root.is_dir():
        raise FileNotFoundError(f"Mneno integration templates were not found: {root}")
    return root


def get_agent_template(agent: str) -> AgentTemplate:
    """Return template metadata for a supported agent."""
    try:
        return AGENT_TEMPLATES[agent]
    except KeyError as exc:
        supported = ", ".join(SUPPORTED_AGENTS)
        raise ValueError(f"Unsupported agent '{agent}'. Supported agents: {supported}.") from exc
