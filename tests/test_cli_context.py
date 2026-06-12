import importlib
import json
from pathlib import Path
from typing import Any

from pytest import MonkeyPatch
from typer.testing import CliRunner

from mneno.cli.app import app
from mneno.context import ContextPolicy

runner = CliRunner()


def initialize(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["init"])
    assert result.exit_code == 0


def add_memory(text: str, *options: str) -> str:
    result = runner.invoke(app, ["add", text, *options])
    assert result.exit_code == 0
    return result.output.split("ID:\n  ", maxsplit=1)[1].splitlines()[0]


def test_context_requires_workspace(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(app, ["context", "continue development"])

    assert result.exit_code == 1
    assert "No Mneno workspace found. Run `mneno init`." in result.output


def test_context_works_after_add(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    initialize(tmp_path, monkeypatch)
    memory_id = add_memory("LOCOMO exposed ranking issues")

    result = runner.invoke(app, ["context", "LOCOMO ranking"])

    assert result.exit_code == 0
    assert "Context" in result.output
    assert "Relevant memories:" in result.output
    assert "LOCOMO exposed ranking issues" in result.output
    assert "Stats" in result.output
    assert "Used tokens:" in result.output
    assert "Included: 1" in result.output
    assert "Included because:" in result.output
    assert memory_id in result.output


def test_context_respects_budget(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    initialize(tmp_path, monkeypatch)
    add_memory("LOCOMO ranking issue one")
    add_memory("LOCOMO ranking issue two")

    result = runner.invoke(app, ["context", "LOCOMO ranking", "--budget", "4", "--json"])
    payload = json.loads(result.output)

    assert result.exit_code == 0
    assert payload["stats"]["max_tokens"] == 4
    assert payload["stats"]["used_tokens"] <= 4
    assert payload["stats"]["remaining_tokens"] >= 0
    assert payload["stats"]["included_count"] == 1
    assert payload["stats"]["excluded_count"] == 1


def test_context_json_output_has_stable_shape(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    initialize(tmp_path, monkeypatch)
    add_memory("LOCOMO exposed ranking issues", "--tag", "retrieval")

    result = runner.invoke(app, ["context", "LOCOMO", "--preset", "balanced", "--json"])
    payload = json.loads(result.output)

    assert result.exit_code == 0
    assert set(payload) == {"query", "text", "preset", "stats", "included", "excluded"}
    assert payload["query"] == "LOCOMO"
    assert payload["preset"] == "balanced"
    assert "LOCOMO exposed ranking issues" in payload["text"]
    assert set(payload["stats"]) == {
        "max_tokens",
        "available_tokens",
        "used_tokens",
        "remaining_tokens",
        "included_count",
        "excluded_count",
    }
    assert set(payload["included"][0]) == {
        "memory_id",
        "content",
        "score",
        "estimated_tokens",
        "reason",
    }
    assert "context preset 'balanced'" in payload["included"][0]["reason"]
    assert "context policy 'custom'" not in payload["included"][0]["reason"]


def test_context_show_excluded_displays_reasons(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    initialize(tmp_path, monkeypatch)
    add_memory("LOCOMO ranking issue cannot fit")

    result = runner.invoke(app, ["context", "LOCOMO ranking", "--budget", "1", "--show-excluded"])

    assert result.exit_code == 0
    assert "Excluded:" in result.output
    assert "LOCOMO ranking issue cannot fit" in result.output
    assert "Excluded because budget exhausted" in result.output


def test_context_excludes_unrelated_memories_from_balanced_context(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    initialize(tmp_path, monkeypatch)
    add_memory("Yesterday I ate chocolate")
    add_memory("I want to become a skilled developer")
    add_memory("Developing a project presentation")

    result = runner.invoke(app, ["context", "chocolate", "--show-excluded"])

    assert result.exit_code == 0
    context_text = result.output.split("Stats", maxsplit=1)[0]
    assert "Yesterday I ate chocolate" in context_text
    assert "skilled developer" not in context_text
    assert "project presentation" not in context_text
    assert result.output.count("Excluded because query relevance is zero") == 2


def test_context_session_option_does_not_crash(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    initialize(tmp_path, monkeypatch)
    add_memory("Continue development on retrieval")

    result = runner.invoke(app, ["context", "continue development", "--session", "session-123", "--json"])
    payload = json.loads(result.output)

    assert result.exit_code == 0
    assert payload["included"][0]["content"] == "Continue development on retrieval"


def test_context_flags_and_composed_policy_pass_through(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    initialize(tmp_path, monkeypatch)
    captured: dict[str, object] = {}

    class EmptyStats:
        max_tokens = 25
        available_tokens = 25
        used_tokens = 0
        remaining_tokens = 25
        included_count = 0
        excluded_count = 0

    class EmptyPackage:
        query = "Python"
        text = "Relevant memories:"
        stats = EmptyStats()
        included: list[object] = []
        excluded: list[object] = []

    class RecordingClient:
        def build_context(
            self,
            query: str,
            *,
            policy: ContextPolicy,
            include_inactive: bool,
            include_archived: bool,
            current_session_id: str | None,
        ) -> Any:
            captured.update(
                query=query,
                policy=policy,
                include_inactive=include_inactive,
                include_archived=include_archived,
                current_session_id=current_session_id,
            )
            return EmptyPackage()

    context_module = importlib.import_module("mneno.cli.commands.context")
    monkeypatch.setattr(context_module, "get_workspace_client", lambda _: RecordingClient())

    result = runner.invoke(
        app,
        [
            "context",
            "Python",
            "--budget",
            "25",
            "--preset",
            "high_recall",
            "--include-inactive",
            "--include-archived",
            "--session",
            "session-123",
        ],
    )

    assert result.exit_code == 0
    assert captured["query"] == "Python"
    assert captured["include_inactive"] is True
    assert captured["include_archived"] is True
    assert captured["current_session_id"] == "session-123"
    policy = captured["policy"]
    assert isinstance(policy, ContextPolicy)
    assert policy.max_tokens == 25
    assert policy.reserve_tokens == 0
    assert policy.min_score == 0.05
    assert policy.max_items == 40


def test_context_session_degrades_for_older_core_api(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    initialize(tmp_path, monkeypatch)

    class EmptyStats:
        max_tokens = 1200
        available_tokens = 1200
        used_tokens = 0
        remaining_tokens = 1200
        included_count = 0
        excluded_count = 0

    class EmptyPackage:
        query = "Python"
        text = "Relevant memories:"
        stats = EmptyStats()
        included: list[object] = []
        excluded: list[object] = []

    class OlderClient:
        def build_context(self, query: str, *, policy: ContextPolicy) -> Any:
            return EmptyPackage()

    context_module = importlib.import_module("mneno.cli.commands.context")
    monkeypatch.setattr(context_module, "get_workspace_client", lambda _: OlderClient())

    result = runner.invoke(app, ["context", "Python", "--session", "session-123"])

    assert result.exit_code == 0
    assert "does not support session-aware context" in result.output


def test_context_help_lists_supported_options() -> None:
    result = runner.invoke(app, ["context", "--help"])

    assert result.exit_code == 0
    assert "--budget" in result.output
    assert "--preset" in result.output
    assert "--session" in result.output
    assert "--json" in result.output
    assert "Include archived" in result.output
    assert "other inactive" in result.output
    assert "Show memories" in result.output
