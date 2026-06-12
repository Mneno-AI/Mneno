import os
import subprocess
from pathlib import Path


def test_demo_script_exists_is_executable_and_contains_expected_commands() -> None:
    script = Path(__file__).parents[1] / "scripts" / "demo_cli.sh"
    content = script.read_text(encoding="utf-8")

    assert script.exists()
    assert os.access(script, os.X_OK)
    assert "mktemp -d" in content
    assert "Mneno Core found ranking issues in LOCOMO." in content
    assert "Candidate coverage is around 80%" in content
    assert "The next priority is improving ranking and session-aware retrieval." in content
    assert "--tag continue" in content
    assert "--tag development" in content
    assert 'run_demo "Inspect recent memories" recent' in content
    assert 'run_demo "Search with explanations" search "LOCOMO ranking"' in content
    assert 'run_demo "Build context" context "continue development"' in content
    assert 'run_demo "Inspect workspace status" status' in content


def test_demo_script_runs_without_touching_repository_workspace() -> None:
    repository = Path(__file__).parents[1]
    script = repository / "scripts" / "demo_cli.sh"
    repository_workspace = repository / ".mneno"
    environment = {**os.environ, "PATH": f"{repository / '.venv' / 'bin'}:{os.environ['PATH']}"}

    result = subprocess.run(
        [str(script)],
        cwd=repository,
        env=environment,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "Mneno CLI Demo" in result.stdout
    assert "Recent memories" in result.stdout
    assert "LOCOMO" in result.stdout
    assert "Relevant memories:\n- The next priority is improving ranking and session-aware retrieval." in result.stdout
    assert "Counts:" in result.stdout
    assert "Memories: 3" in result.stdout
    assert "Demo complete. Workspace retained at:" in result.stdout
    assert not repository_workspace.exists()
