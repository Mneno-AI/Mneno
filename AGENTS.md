# AGENTS.md

## Project Overview

Mneno is a Python-first SDK for AI memory. It is an anti-context-rot memory runtime for copilots, support agents,
internal AI tools, and long-running AI applications.

Mneno should maintain useful, compact, explainable, and verifiable context over time. It is not a generic memory store
and should not become a thin wrapper around provider APIs.

## Repository Structure

- `mneno/`: core Python package.
- `mneno/scoring/`: memory scoring interfaces and temporal scoring.
- `mneno/compaction/`: explainable compaction interfaces and diff templates.
- `mneno/retrieval/`: retrieval interfaces.
- `mneno/storage/`: storage interfaces and local in-memory storage.
- `mneno/policies/`: runtime policy configuration.
- `tests/`: pytest suite.
- `examples/`: runnable usage examples.
- `scripts/`: development, formatting, and test commands.
- `docs/`: project documentation.

## Development Setup

Use Python 3.11 or newer.

```bash
scripts/setup_dev.sh
```

The setup script uses `uv` when available and falls back to `pip` with a local virtual environment.

## Build, Lint, and Test Commands

```bash
scripts/format.sh
scripts/check.sh
scripts/test.sh
python -m build
```

`scripts/check.sh` must pass before a pull request is ready.

## Core APIs

The main public entrypoint is:

```python
from mneno import MemoryClient
```

The initial client supports local in-memory add and search operations. Public APIs must be documented and covered by
tests when they are added or changed.

## Import Patterns

- Prefer imports from stable package modules such as `mneno.models`, `mneno.storage`, and `mneno.scoring`.
- Keep `mneno.__init__` focused on the small public API surface.
- Do not import optional integrations from core modules.

## Coding Standards

- Python version is 3.11+.
- Use Pydantic v2 for models.
- Use Ruff for linting and formatting.
- Keep line length at 120 characters.
- Keep type hints precise and mypy-clean.
- Keep the core package lightweight.

## Architecture

Mneno core should provide:

- Memory models.
- Local memory storage interfaces.
- Scoring interfaces and lightweight scoring implementations.
- Explainable compaction diff structures.
- Policy configuration.

Integrations belong outside the core dependency path. Add optional extras later for LLM providers, embedding providers,
vector databases, graph databases, and persistence backends.

## Task Completion Guidelines

- Keep changes minimal and aligned with the repository structure.
- Add or update tests for public behavior.
- Run `scripts/check.sh` when practical.
- Update docs and examples when public APIs change.
- Preserve explainability in scoring and compaction behavior.

## Contributing Guidelines

- Open issues for substantial API or architecture changes.
- Keep pull requests focused.
- Explain user-facing behavior and migration impact.
- Avoid hidden provider assumptions.

## Pull Request Requirements

- Passing Ruff, mypy, and pytest checks.
- Tests for new public APIs.
- Documentation for new public behavior.
- No new heavyweight core dependencies.
- Clear explanation of memory scoring or compaction decisions when behavior changes.

## Do NOT

- Do not add LLM providers to core dependencies.
- Do not add embedding providers to core dependencies.
- Do not add vector DB or graph DB clients to core dependencies.
- Do not introduce complex graph logic in the MVP.
- Do not make compaction behavior opaque.
- Do not add public APIs without documentation and tests.
- Do not broaden the package scope beyond Python-first SDK foundations.
