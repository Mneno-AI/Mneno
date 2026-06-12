#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

if command -v mneno >/dev/null 2>&1; then
  MNENO=(mneno)
elif [ -x "$REPO_ROOT/.venv/bin/mneno" ]; then
  MNENO=("$REPO_ROOT/.venv/bin/mneno")
else
  echo "error: mneno is not installed. Run scripts/setup_dev.sh first." >&2
  exit 127
fi

DEMO_DIR="$(mktemp -d "${TMPDIR:-/tmp}/mneno-cli-demo.XXXXXX")"
cd "$DEMO_DIR"

run_demo() {
  local title="$1"
  shift
  printf '\n\033[1m%s\033[0m\n' "$title"
  printf '$ mneno'
  printf ' %q' "$@"
  printf '\n'
  "${MNENO[@]}" "$@"
}

printf '\033[1mMneno CLI Demo\033[0m\n'
printf 'Local workspace: %s\n' "$DEMO_DIR/.mneno"

run_demo "Initialize" init
run_demo \
  "Add LOCOMO finding" \
  add \
  "Mneno Core found ranking issues in LOCOMO." \
  --tag locomo \
  --tag retrieval \
  --importance 0.8
run_demo \
  "Add diagnosis" \
  add \
  "Candidate coverage is around 80%, so candidate generation is not the main bottleneck." \
  --tag locomo \
  --tag diagnosis \
  --importance 0.9
run_demo \
  "Add roadmap" \
  add \
  "The next priority is improving ranking and session-aware retrieval." \
  --tag roadmap \
  --tag retrieval \
  --tag continue \
  --tag development \
  --importance 0.9
run_demo "Inspect recent memories" recent
run_demo "Search with explanations" search "LOCOMO ranking"
run_demo "Build context" context "continue development"
run_demo "Inspect workspace status" status

printf '\nDemo complete. Workspace retained at: %s\n' "$DEMO_DIR"
