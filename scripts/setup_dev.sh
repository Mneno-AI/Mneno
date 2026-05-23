#!/usr/bin/env bash
set -euo pipefail

if command -v uv >/dev/null 2>&1; then
  uv venv --python 3.11
  uv pip install -e ".[dev]"
  uv run pre-commit install
else
  python3.11 -m venv .venv
  . .venv/bin/activate
  python -m pip install --upgrade pip
  python -m pip install -e ".[dev]"
  pre-commit install
fi
