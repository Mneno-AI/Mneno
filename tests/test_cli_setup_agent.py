from pathlib import Path

import pytest
from pytest import MonkeyPatch
from typer.testing import CliRunner

from mneno.cli.app import app

runner = CliRunner()


@pytest.mark.parametrize(
    ("agent", "agent_file", "expected_text"),
    [
        ("codex", Path("AGENTS.md"), "Codex Instructions: Mneno Memory"),
        ("claude-code", Path(".mneno") / "skills" / "mneno-memory" / "SKILL.md", "Mneno Memory"),
        ("cursor", Path("AGENTS.md"), "Cursor Instructions: Mneno Memory"),
        ("gemini-cli", Path("AGENTS.md"), "Gemini CLI Instructions: Mneno Memory"),
        ("windsurf", Path("AGENTS.md"), "Windsurf Instructions: Mneno Memory"),
    ],
)
def test_setup_agent_installs_supported_agents(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
    agent: str,
    agent_file: Path,
    expected_text: str,
) -> None:
    initialize(tmp_path, monkeypatch)

    result = runner.invoke(app, ["setup-agent", agent])

    assert result.exit_code == 0
    assert "Installed Mneno agent integration" in result.output
    assert f"  {agent}" in result.output
    assert str(agent_file).replace("\\", "/") in result.output
    assert (tmp_path / agent_file).exists()
    assert expected_text in (tmp_path / agent_file).read_text(encoding="utf-8")
    assert_shared_docs_installed(tmp_path)


def test_setup_agent_requires_workspace(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(app, ["setup-agent", "codex"])

    assert result.exit_code == 1
    assert "No Mneno workspace found. Run `mneno init`." in result.output
    assert not (tmp_path / "AGENTS.md").exists()


def test_setup_agent_rejects_unknown_agent(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    initialize(tmp_path, monkeypatch)

    result = runner.invoke(app, ["setup-agent", "unknown"])
    normalized_output = " ".join(result.output.split())

    assert result.exit_code == 1
    assert "Unsupported agent 'unknown'." in result.output
    assert "codex, claude-code, cursor, gemini-cli, windsurf" in normalized_output


def test_setup_agent_protects_existing_agents_file(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    initialize(tmp_path, monkeypatch)
    agents_file = tmp_path / "AGENTS.md"
    agents_file.write_text("custom instructions", encoding="utf-8")

    result = runner.invoke(app, ["setup-agent", "codex"])

    assert result.exit_code == 1
    assert "File already exists:" in result.output
    assert "AGENTS.md" in result.output
    assert "Use --force to overwrite." in result.output
    assert agents_file.read_text(encoding="utf-8") == "custom instructions"


def test_setup_agent_protects_existing_claude_skill(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    initialize(tmp_path, monkeypatch)
    skill_file = tmp_path / ".mneno" / "skills" / "mneno-memory" / "SKILL.md"
    skill_file.parent.mkdir(parents=True)
    skill_file.write_text("custom skill", encoding="utf-8")

    result = runner.invoke(app, ["setup-agent", "claude-code"])

    assert result.exit_code == 1
    assert "File already exists:" in result.output
    assert ".mneno/skills/mneno-memory/SKILL.md" in result.output
    assert "Use --force to overwrite." in result.output
    assert skill_file.read_text(encoding="utf-8") == "custom skill"


def test_setup_agent_claude_skill_has_valid_frontmatter_and_routes_to_agent_docs(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    initialize(tmp_path, monkeypatch)

    result = runner.invoke(app, ["setup-agent", "claude-code"])
    skill_file = tmp_path / ".mneno" / "skills" / "mneno-memory" / "SKILL.md"
    content = skill_file.read_text(encoding="utf-8")
    lines = content.splitlines()

    assert result.exit_code == 0
    assert content.startswith("---\n")
    assert lines[0] == "---"
    assert lines[1] == "name: mneno-memory"
    assert lines[2].startswith("description:")
    assert lines[3] == "---"
    assert skill_file.parent.name == "mneno-memory"
    assert "references/AGENT_WORKFLOW.md" in content
    assert "references/COMMAND_REFERENCE.md" in content
    assert "references/MEMORY_GUIDELINES.md" in content
    assert "mneno context" in content
    assert "mneno search" in content
    assert "mneno add" in content
    assert_skill_references_installed(skill_file.parent)


def test_setup_agent_force_overwrites_existing_files(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    initialize(tmp_path, monkeypatch)
    agents_file = tmp_path / "AGENTS.md"
    agents_file.write_text("custom instructions", encoding="utf-8")

    result = runner.invoke(app, ["setup-agent", "codex", "--force"])

    assert result.exit_code == 0
    assert "Installed Mneno agent integration" in result.output
    assert "Codex Instructions: Mneno Memory" in agents_file.read_text(encoding="utf-8")
    assert_shared_docs_installed(tmp_path)


def test_setup_agent_dry_run_reports_files_without_writing(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    initialize(tmp_path, monkeypatch)

    result = runner.invoke(app, ["setup-agent", "codex", "--dry-run"])

    assert result.exit_code == 0
    assert "Would create:" in result.output
    assert "AGENTS.md" in result.output
    assert ".mneno/agent-docs/AGENT_WORKFLOW.md" in result.output
    assert ".mneno/agent-docs/MEMORY_GUIDELINES.md" in result.output
    assert ".mneno/agent-docs/COMMAND_REFERENCE.md" in result.output
    assert not (tmp_path / "AGENTS.md").exists()
    assert not (tmp_path / ".mneno" / "agent-docs").exists()


def test_setup_agent_help_lists_supported_options() -> None:
    result = runner.invoke(app, ["setup-agent", "--help"])

    assert result.exit_code == 0
    assert "Install Mneno agent integration templates into the current repository." in result.output
    assert "--force" in result.output
    assert "--dry-run" in result.output


def initialize(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["init"])
    assert result.exit_code == 0


def assert_shared_docs_installed(tmp_path: Path) -> None:
    docs = tmp_path / ".mneno" / "agent-docs"
    workflow = docs / "AGENT_WORKFLOW.md"
    guidelines = docs / "MEMORY_GUIDELINES.md"
    commands = docs / "COMMAND_REFERENCE.md"

    assert workflow.exists()
    assert guidelines.exists()
    assert commands.exists()
    assert "Agent Workflow" in workflow.read_text(encoding="utf-8")
    assert "Memory Guidelines" in guidelines.read_text(encoding="utf-8")
    assert "Command Reference" in commands.read_text(encoding="utf-8")


def assert_skill_references_installed(skill_path: Path) -> None:
    references = skill_path / "references"
    workflow = references / "AGENT_WORKFLOW.md"
    guidelines = references / "MEMORY_GUIDELINES.md"
    commands = references / "COMMAND_REFERENCE.md"

    assert workflow.exists()
    assert guidelines.exists()
    assert commands.exists()
    assert "Agent Workflow" in workflow.read_text(encoding="utf-8")
    assert "Memory Guidelines" in guidelines.read_text(encoding="utf-8")
    assert "Command Reference" in commands.read_text(encoding="utf-8")
