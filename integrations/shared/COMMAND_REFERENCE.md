# Command Reference

These commands are the current CLI surface for coding-agent integrations. They operate on the local Mneno workspace,
typically stored under `.mneno/` in the project.

## `mneno init`

Use when starting Mneno in a repository that does not already have a local workspace.

Example:

```bash
mneno init
```

Output means the workspace files were created or already exist. After initialization, other commands can read and write
local memory.

Caution: agents should not run `mneno init` automatically unless the user explicitly asks. If no workspace exists, tell
the user to run `mneno init` in the intended project root.

## `mneno status`

Use at the start of a task to confirm workspace health and local storage state.

Example:

```bash
mneno status
```

Output shows whether Mneno can find the workspace, whether storage is readable, and summary counts that indicate Mneno
is usable in this repository.

Caution: if status reports that no workspace exists, do not initialize automatically. Ask the user or tell them to run
`mneno init`.

## `mneno recent`

Use when a quick overview of recent active memories would help.

Example:

```bash
mneno recent
```

Output lists recent memories with metadata such as lifecycle status and tags.

Caution: `recent` is optional. Recent memories are not necessarily the most relevant memories. Prefer `mneno context
"<current task>"` for task-start context and `mneno search` for narrow follow-up lookup.

## `mneno add`

Use at the end of a meaningful work unit when you discover durable information that should help future work.

Example:

```bash
mneno add "The CLI context command should remain deterministic and local-only." --tag cli --tag architecture
```

Output confirms the memory ID, type, importance, tags, and storage path.

Caution: do not add secrets, credentials, API keys, sensitive personal data, huge logs, generated code dumps, or trivial
implementation details. Prefer one concise sentence.

Use `--importance` for important constraints, bugs, and decisions:

```bash
mneno add "Do not work on BEAM before the Thursday demo; focus on agent integration and CLI usability." \
  --type operational --tag demo --tag constraint --importance 1.0
```

## `mneno search`

Use for narrow lookup when you need prior context about a specific topic, decision, bug, benchmark, user preference, or
workflow.

Example:

```bash
mneno search "context command deterministic local"
```

Output lists matching memories and scoring/explanation details.

Caution: search is mainly for narrow lookup, not broad discovery. Exact or domain-specific queries are safer. Do not
assume search output is always complete or correct; verify against repository files when needed.

## `mneno context`

Use at task start to build an explainable, budgeted context package for the current task.

Example:

```bash
mneno context "continue agent integration templates"
```

Output includes selected memory text, token budget stats, and inclusion reasons.

Caution: `context` is deterministic and local. It is not magic semantic understanding, and Mneno is not the source of
truth. Conflicting memories may appear with warnings or evidence. Verify important claims before acting.

If context is weak, read the repository and then run narrower searches:

```bash
mneno search "LOCOMO selected_memory_ids"
```
