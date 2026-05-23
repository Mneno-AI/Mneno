# Contributing to Mneno

Mneno is Python-first and targets Python 3.11+. The core SDK should remain lightweight, well typed, and easy to inspect.

## Development Setup

```bash
scripts/setup_dev.sh
```

If `uv` is available, the setup script uses it. Otherwise it falls back to `python3.11 -m venv` and `pip`.

## Checks

```bash
scripts/check.sh
```

This runs Ruff, mypy, and pytest. Use `scripts/format.sh` before opening a pull request.

## Contribution Guidelines

- Keep public APIs documented and tested.
- Use Pydantic v2 for models.
- Use Ruff for linting and formatting.
- Do not add LLM providers, embedding providers, vector DBs, or graph DBs to core dependencies.
- Add integrations later through optional extras.
- Preserve explainability in memory scoring and compaction behavior.
