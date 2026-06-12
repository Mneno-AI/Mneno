import importlib
import json
from pathlib import Path
from typing import Any

from pytest import MonkeyPatch
from typer.testing import CliRunner

from mneno.cli.app import app

runner = CliRunner()


def initialize(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["init"])
    assert result.exit_code == 0


def add_memory(text: str, *options: str) -> None:
    result = runner.invoke(app, ["add", text, *options])
    assert result.exit_code == 0


def test_search_requires_workspace(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(app, ["search", "LOCOMO"])

    assert result.exit_code == 1
    assert "No Mneno workspace found. Run `mneno init`." in result.output


def test_search_returns_added_memory(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    initialize(tmp_path, monkeypatch)
    add_memory("LOCOMO exposed ranking issues", "--tag", "retrieval")

    result = runner.invoke(app, ["search", "LOCOMO"])

    assert result.exit_code == 0
    assert "Rank" in result.output
    assert "Score" in result.output
    assert "LOCOMO exposed ranking issues" in result.output
    assert "semantic" in result.output
    assert "active" in result.output


def test_search_respects_limit(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    initialize(tmp_path, monkeypatch)
    add_memory("Ranking alpha")
    add_memory("Ranking beta")
    add_memory("Ranking gamma")

    result = runner.invoke(app, ["search", "ranking", "--limit", "2", "--json"])
    payload = json.loads(result.output)

    assert result.exit_code == 0
    assert len(payload) == 2


def test_search_no_results(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    initialize(tmp_path, monkeypatch)

    result = runner.invoke(app, ["search", "LOCOMO"])

    assert result.exit_code == 0
    assert 'No memories found for query:\n"LOCOMO"' in result.output


def test_search_hides_stored_memories_with_zero_query_relevance(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    initialize(tmp_path, monkeypatch)
    add_memory("Yesterday I ate chocolate")
    add_memory("I want to become a skilled developer")

    result = runner.invoke(app, ["search", "pizza"])

    assert result.exit_code == 0
    assert 'No memories found for query:\n"pizza"' in result.output
    assert "chocolate" not in result.output
    assert "developer" not in result.output


def test_search_does_not_match_first_person_pronoun(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    initialize(tmp_path, monkeypatch)
    add_memory("Yesterday I ate chocolate")
    add_memory("I want to become a skilled developer")

    result = runner.invoke(app, ["search", "I hate"])

    assert result.exit_code == 0
    assert 'No memories found for query:\n"I hate"' in result.output


def test_search_json_output_has_stable_shape(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    initialize(tmp_path, monkeypatch)
    add_memory("LOCOMO exposed ranking issues", "--type", "operational", "--tag", "locomo")

    result = runner.invoke(app, ["search", "LOCOMO", "--json"])
    payload = json.loads(result.output)

    assert result.exit_code == 0
    assert isinstance(payload, list)
    assert len(payload) == 1
    assert set(payload[0]) == {
        "rank",
        "memory_id",
        "content",
        "score",
        "memory_type",
        "layer",
        "status",
        "tags",
        "reasons",
    }
    assert payload[0]["content"] == "LOCOMO exposed ranking issues"
    assert payload[0]["memory_type"] == "operational"
    assert payload[0]["status"] == "active"
    assert payload[0]["tags"] == ["locomo"]
    assert isinstance(payload[0]["score"], float)
    assert payload[0]["reasons"]


def test_search_include_flags_pass_through(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    initialize(tmp_path, monkeypatch)
    captured: dict[str, object] = {}

    class RecordingClient:
        def search(
            self,
            query: str,
            *,
            limit: int,
            include_inactive: bool,
            include_archived: bool,
            current_session_id: str | None,
        ) -> list[Any]:
            captured.update(
                query=query,
                limit=limit,
                include_inactive=include_inactive,
                include_archived=include_archived,
                current_session_id=current_session_id,
            )
            return []

    search_module = importlib.import_module("mneno.cli.commands.search")
    monkeypatch.setattr(search_module, "get_workspace_client", lambda _: RecordingClient())

    result = runner.invoke(
        app,
        ["search", "Python", "--include-inactive", "--include-archived", "--session", "session-123"],
    )

    assert result.exit_code == 0
    assert captured == {
        "query": "Python",
        "limit": 5,
        "include_inactive": True,
        "include_archived": True,
        "current_session_id": "session-123",
    }


def test_search_session_option_does_not_crash(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    initialize(tmp_path, monkeypatch)
    add_memory("Continue development on retrieval")

    result = runner.invoke(app, ["search", "continue development", "--session", "session-123", "--json"])
    payload = json.loads(result.output)

    assert result.exit_code == 0
    assert payload[0]["content"] == "Continue development on retrieval"


def test_search_displays_reasons_by_default(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    initialize(tmp_path, monkeypatch)
    add_memory("LOCOMO exposed ranking issues")

    result = runner.invoke(app, ["search", "LOCOMO"])

    assert result.exit_code == 0
    assert "Reasons for #1:" in result.output
    assert "Matched query term: locomo" in result.output


def test_search_reasons_do_not_duplicate_exact_normalized_terms(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    initialize(tmp_path, monkeypatch)
    add_memory("I want to be a Linus Torvalds skilled developer")

    result = runner.invoke(app, ["search", "Linus Torvalds"])

    assert result.exit_code == 0
    assert "Matched query term: torvalds" in result.output
    assert "Normalized query term match: torvald" not in result.output


def test_search_can_hide_reasons(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    initialize(tmp_path, monkeypatch)
    add_memory("LOCOMO exposed ranking issues")

    result = runner.invoke(app, ["search", "LOCOMO", "--no-show-reasons"])

    assert result.exit_code == 0
    assert "Reasons for #1:" not in result.output


def test_search_help_lists_supported_options() -> None:
    result = runner.invoke(app, ["search", "--help"])

    assert result.exit_code == 0
    assert "--limit" in result.output
    assert "--session" in result.output
    assert "--json" in result.output
    assert "Include archived" in result.output
    assert "other inactive" in result.output
    assert "Show scoring" in result.output
