# Mneno Memory

Use this skill when working in a repository that uses Mneno for local project memory.

Mneno is local-first. Use the CLI; do not assume a network service, cloud backend, provider, or MCP server exists.
Mneno is an assistive memory layer, not a notebook and not the source of truth.

## When To Use

- At the start of a task, to recover relevant project memory.
- For narrow lookup before relying on prior decisions, bugs, benchmarks, or constraints.
- After a meaningful work unit reveals durable information that should help future agents.
- Before finishing, to store important decisions, root causes, constraints, or next steps.

## Commands

```bash
mneno status
mneno context "<task>"
mneno recent
mneno search "<topic>"
mneno add "<durable memory>" --tag ...
```

Start with `mneno status`, then `mneno context "<task>"`. Use `mneno recent` only for a quick overview. Use
`mneno search "<specific topic>"` for narrow follow-ups.

## Examples

```bash
mneno status
mneno context "continue Mneno development after LOCOMO and CLI feedback"
mneno search "Cristian CLI MCP demo preference"
mneno add "Claude Code can use Mneno through local CLI commands without MCP for the first agent integration demo." \
  --tag claude-code --tag integrations --tag cli
```

## Safety Rules

- Verify important Mneno output against repository files when needed.
- Do not run `mneno init` automatically; if no workspace exists, tell the user to run it in the intended project root.
- Never store secrets, API keys, tokens, credentials, or sensitive personal data.
- Do not store huge logs, generated code dumps, or raw stack traces.
- Do not add memories for every file edit.
- Do not use broad search as discovery when a specific query is possible.

## Memory Writing Policy

Write one concise, factual, durable, tagged memory at the end of a meaningful work unit. Good memories include
architecture decisions, benchmark findings, root causes, user or product preferences, workflow discoveries, and "do not
do X before Y" constraints. Use `--importance` for important constraints, bugs, and decisions.
