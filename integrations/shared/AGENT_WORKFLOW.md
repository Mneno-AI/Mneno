# Agent Workflow

Use this workflow when a coding agent works in a repository that uses Mneno for local project memory.

Mneno is local-first and does not require network access. The CLI is the integration surface. Mneno is not a notebook
and not the source of truth; it is an assistive memory layer for recovering durable project context. Verify important
claims against current files before acting.

## Before Starting Work

Run:

```bash
mneno status
mneno context "<current task>"
```

Use `mneno status` to confirm that the workspace exists, local storage is readable, memory counts are visible, and Mneno
is usable in this repository. If no workspace exists, do not initialize automatically; tell the user to run `mneno init`
in the intended project root.

Use `mneno context "<current task>"` to build a compact, explainable context package for the task before deep
implementation. Use `mneno recent` only when a quick overview of recent active memories would help:

```bash
mneno recent
```

If `mneno context "<current task>"` returns weak or irrelevant context, read the repository files and then use narrower
search queries.

## Searching For Prior Context

Use search for specific follow-up lookup, not broad discovery. When you need a prior decision, known bug, constraint,
benchmark finding, user preference, or workflow detail, run:

```bash
mneno search "<topic>"
```

Prefer exact or domain-specific queries:

```bash
mneno search "LOCOMO selected_memory_ids zero recall"
mneno search "Cristian CLI MCP demo preference"
```

Broad searches can be noisy. Do not assume search output is complete or correct.

## Adding Important Memories

Add memories at the end of a meaningful work unit, not after every small step. Store durable information with concise
wording and useful tags:

```bash
mneno add "<durable memory>" --tag project --tag topic
```

Good memory writes are usually one clear sentence. Use a short paragraph only when the extra context is necessary.

Use `--importance` for important constraints, bugs, and decisions:

```bash
mneno add "Do not work on BEAM before the Thursday demo; focus on agent integration and CLI usability." \
  --type operational --tag demo --tag constraint --importance 1.0
```

Use memory types only when obvious: `operational` for active tasks or constraints, `preference` for user or product
preferences, and the default for most durable facts.

## Continuing Previous Work

Before continuing a previous task, use one of these forms:

```bash
mneno context "continue <task>"
mneno context "<current task>"
```

Then search for specific missing details as needed:

```bash
mneno search "<specific prior decision or bug>"
```

## When Not To Store Memory

Do not store:

- Trivial implementation details.
- Temporary debugging noise.
- Secrets, API keys, tokens, credentials, or sensitive personal data.
- Huge logs.
- Generated code dumps.
- Raw stack traces unless they are summarized into a durable root cause.
- Facts that are easily read from current files unless they explain a durable decision.

## Operating Principles

- Mneno is local-first.
- No network is required for CLI use.
- The CLI is the current agent integration surface.
- Mneno is not grep; grep finds text, while Mneno builds an explainable context package from remembered project
  knowledge.
- Mneno is not MCP; the CLI keeps the first integration simple and low-overhead.
- Mneno is not a generic vector database; it is lifecycle-aware and explainable.
- Do not treat Mneno as always correct.
- Do not add memory for every file edit.
- Prefer concise durable memories with clear future value.
- Record useful next steps before stopping when they help future continuation.
