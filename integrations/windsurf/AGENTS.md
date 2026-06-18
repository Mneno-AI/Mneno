# Windsurf Instructions: Mneno Memory

This repository uses Mneno for local project memory. Use the Mneno CLI directly; do not assume MCP, cloud services,
providers, or network access.

Mneno is not a notebook and not the source of truth. Use it to recover durable project context, then verify important
claims against current files.

## Start Of Task

Run:

```bash
mneno status
mneno context "<current task>"
```

If context is weak, read the repository and then run `mneno search "<specific topic>"`. Use `mneno recent` only when a
quick overview of recent active memories would help.

Do not run `mneno init` automatically. If no workspace exists, tell the user to run `mneno init` in the intended project
root.

Treat the returned context as local project memory, but verify important claims against current files.

## During Work

- Run `mneno search "<topic>"` only for narrow lookup before depending on prior context.
- Add durable discoveries at the end of a meaningful work unit with `mneno add "<memory>" --tag ...`.
- Keep memory writes concise, factual, and useful.
- Do not store secrets, credentials, API keys, sensitive personal data, huge logs, generated code dumps, or temporary
  debugging noise.

## Before Finishing

Store important decisions, root causes, constraints, and next steps that should help a future agent continue.

Example:

```bash
mneno add "Windsurf agents should use Mneno context for task-start memory and avoid broad search unless necessary." \
  --tag windsurf --tag workflow --tag cli
```
