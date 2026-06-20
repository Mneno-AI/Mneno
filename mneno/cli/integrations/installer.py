"""Install Mneno agent integration templates into a workspace."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from mneno.cli.integrations.templates import SHARED_DOCS, SKILL_SOURCE, get_agent_template, integration_templates_root


@dataclass(frozen=True)
class TemplateFile:
    """One template copy operation."""

    source: Path
    target: Path
    display_path: str


@dataclass(frozen=True)
class InstallationPlan:
    """Resolved installation plan for an agent template."""

    agent: str
    files: tuple[TemplateFile, ...]

    @property
    def display_paths(self) -> tuple[str, ...]:
        return tuple(file.display_path for file in self.files)


class ExistingTargetError(FileExistsError):
    """Raised when an installation target exists and force mode is disabled."""

    def __init__(self, display_paths: tuple[str, ...]) -> None:
        self.display_paths = display_paths
        super().__init__(", ".join(display_paths))


def plan_agent_installation(agent: str, workspace_path: Path) -> InstallationPlan:
    """Build an installation plan for an agent and workspace."""
    template_root = integration_templates_root()
    template = get_agent_template(agent)
    repository_root = workspace_path.parent

    skill_file = template.skill_target / "SKILL.md"
    files = [
        TemplateFile(
            source=template_root / SKILL_SOURCE,
            target=repository_root / skill_file,
            display_path=_display_path(skill_file),
        )
    ]
    if template.instructions_source is not None and template.instructions_target is not None:
        files.insert(
            0,
            TemplateFile(
                source=template_root / template.instructions_source,
                target=repository_root / template.instructions_target,
                display_path=_display_path(template.instructions_target),
            ),
        )
    for filename in SHARED_DOCS:
        target = Path(".mneno") / "agent-docs" / filename
        files.append(
            TemplateFile(
                source=template_root / "shared" / filename,
                target=repository_root / target,
                display_path=_display_path(target),
            )
        )
        reference_target = template.skill_target / "references" / filename
        files.append(
            TemplateFile(
                source=template_root / "shared" / filename,
                target=repository_root / reference_target,
                display_path=_display_path(reference_target),
            )
        )
    return InstallationPlan(agent=agent, files=tuple(files))


def install_agent_template(
    agent: str,
    workspace_path: Path,
    *,
    force: bool = False,
    dry_run: bool = False,
) -> InstallationPlan:
    """Install an agent template into the workspace's repository."""
    plan = plan_agent_installation(agent, workspace_path)
    existing = tuple(file.display_path for file in plan.files if file.target.exists())
    if existing and not force:
        raise ExistingTargetError(existing)

    if dry_run:
        return plan

    for file in plan.files:
        file.target.parent.mkdir(parents=True, exist_ok=True)
        file.target.write_text(file.source.read_text(encoding="utf-8"), encoding="utf-8")
    return plan


def _display_path(path: Path) -> str:
    return path.as_posix()
