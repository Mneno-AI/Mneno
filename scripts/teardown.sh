#!/usr/bin/env bash
set -euo pipefail

rm -rf \
  .coverage \
  .mypy_cache \
  .pytest_cache \
  .ruff_cache \
  .venv \
  build \
  dist \
  htmlcov \
  *.egg-info
