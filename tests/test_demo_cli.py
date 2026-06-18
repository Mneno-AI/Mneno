import os
import subprocess
import sys
import tempfile
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
    environment = _demo_environment(repository)

    if os.name == "nt":
        result = _run_demo_with_python(repository, environment)
    else:
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


def _demo_environment(repository: Path) -> dict[str, str]:
    virtualenv_bin = repository / ".venv" / ("Scripts" if os.name == "nt" else "bin")
    return {
        **os.environ,
        "PATH": f"{virtualenv_bin}{os.pathsep}{os.environ['PATH']}",
        "PYTHONIOENCODING": "utf-8",
        "PYTHONUTF8": "1",
    }


def _run_demo_with_python(repository: Path, environment: dict[str, str]) -> subprocess.CompletedProcess[str]:
    demo_dir = Path(tempfile.mkdtemp(prefix="mneno-cli-demo."))
    stdout: list[str] = ["Mneno CLI Demo\n", f"Local workspace: {demo_dir / '.mneno'}\n"]
    stderr: list[str] = []
    returncode = 0

    commands = [
        ("Initialize", ["init"]),
        (
            "Add LOCOMO finding",
            [
                "add",
                "Mneno Core found ranking issues in LOCOMO.",
                "--tag",
                "locomo",
                "--tag",
                "retrieval",
                "--importance",
                "0.8",
            ],
        ),
        (
            "Add diagnosis",
            [
                "add",
                "Candidate coverage is around 80%, so candidate generation is not the main bottleneck.",
                "--tag",
                "locomo",
                "--tag",
                "diagnosis",
                "--importance",
                "0.9",
            ],
        ),
        (
            "Add roadmap",
            [
                "add",
                "The next priority is improving ranking and session-aware retrieval.",
                "--tag",
                "roadmap",
                "--tag",
                "retrieval",
                "--tag",
                "continue",
                "--tag",
                "development",
                "--importance",
                "0.9",
            ],
        ),
        ("Inspect recent memories", ["recent"]),
        ("Search with explanations", ["search", "LOCOMO ranking"]),
        ("Build context", ["context", "continue development"]),
        ("Inspect workspace status", ["status"]),
    ]

    for title, arguments in commands:
        stdout.append(f"\n{title}\n")
        stdout.append(f"$ mneno {' '.join(arguments)}\n")
        result = subprocess.run(
            [sys.executable, "-c", "from mneno.cli.app import app; app()", *arguments],
            cwd=demo_dir,
            env={**environment, "PYTHONPATH": str(repository)},
            text=True,
            encoding="utf-8",
            capture_output=True,
            check=False,
        )
        stdout.append(result.stdout)
        stderr.append(result.stderr)
        if result.returncode != 0:
            returncode = result.returncode
            break

    stdout.append(f"\nDemo complete. Workspace retained at: {demo_dir}\n")
    return subprocess.CompletedProcess(
        args=["python-demo"],
        returncode=returncode,
        stdout="".join(stdout),
        stderr="".join(stderr),
    )
