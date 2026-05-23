#!/usr/bin/env bash
set -euo pipefail

run_tool() {
  local tool="$1"
  shift

  if command -v "$tool" >/dev/null 2>&1; then
    "$tool" "$@"
  elif [ -x ".venv/bin/$tool" ]; then
    ".venv/bin/$tool" "$@"
  elif command -v uv >/dev/null 2>&1; then
    uv run --extra dev "$tool" "$@"
  else
    echo "error: $tool is not installed. Run scripts/setup_dev.sh first." >&2
    exit 127
  fi
}

run_tool ruff check .
run_tool ruff format --check .
run_tool mypy
run_tool pytest
