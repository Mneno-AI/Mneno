# Gemini CLI Instructions: Mneno Memory

This repository uses Mneno for local project memory. The CLI is the integration surface, and no network access is
required for normal memory use.

Mneno is not a notebook and not the source of truth. It is an assistive memory layer for coding agents.

## Start Of Task

Run:

```bash
mneno status
mneno context "<current task>"
```

If context is weak, read the repository and then run `mneno search "<specific topic>"`. Use `mneno recent` only when a
quick overview of recent memories would help.

Do not run `mneno init` automatically. If no workspace exists, tell the user to run `mneno init` in the intended project
root.

Use the returned context as a compact memory summary. Verify important details against repository files.

## During Work

- Use `mneno search "<topic>"` for narrow lookup before relying on prior decisions, bugs, benchmarks, or constraints.
- Use `mneno add "<durable memory>" --tag ...` at the end of a meaningful work unit.
- Do not spam memory writes or record every file edit.
- Never store secrets, credentials, API keys, sensitive personal data, huge logs, or generated code dumps.

## Before Finishing

Store important decisions, root causes, constraints, and next steps that should survive into future sessions.

Example:

```bash
mneno add "Gemini CLI agents should use Mneno context at task start and narrow search for specific prior context." \
  --tag gemini-cli --tag workflow --tag cli
```
