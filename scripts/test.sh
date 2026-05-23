#!/usr/bin/env bash
set -euo pipefail

if command -v pytest >/dev/null 2>&1; then
  pytest
elif [ -x ".venv/bin/pytest" ]; then
  .venv/bin/pytest
elif command -v uv >/dev/null 2>&1; then
  uv run --extra dev pytest
else
  echo "error: pytest is not installed. Run scripts/setup_dev.sh first." >&2
  exit 127
fi
