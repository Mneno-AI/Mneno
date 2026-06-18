# Codex Instructions: Mneno Memory

You are working in a repository that uses Mneno for local project memory. Mneno is local-first, and the CLI is the
integration surface.

Mneno is not a notebook and not the source of truth. Use it to recover durable project context, then verify important
claims against repository files and current user instructions.

## Start Of Task

1. Run `mneno status`.
2. If a workspace exists, run `mneno context "<task>"`.
3. If context is weak, read the repository and run `mneno search "<specific topic>"`.
4. Use returned context as project memory, but verify against files when needed.

Use `mneno recent` only when a quick overview of recent active memories would help.

If `mneno status` says no workspace exists, do not run `mneno init` automatically. Tell the user to run `mneno init` in
the intended project root.

## During Work

- Use `mneno search "<topic>"` for narrow lookup before relying on prior decisions, bugs, benchmarks, or constraints.
- Prefer `mneno context "<task>"` for task-start framing and `mneno search "<specific topic>"` for follow-ups.
- Add memories at the end of a meaningful work unit, not after every small step.
- Do not add noisy memories for every file edit or temporary failed attempt.
- Never store secrets, API keys, tokens, credentials, sensitive personal data, huge logs, or generated code dumps.
- Prefer one concise, factual sentence with useful tags.

## Before Finishing

Store important decisions, bugs, root causes, constraints, and useful next steps:

```bash
mneno add "Codex agents should use Mneno context at task start and narrow search for specific prior decisions." \
  --tag codex --tag workflow --tag cli
```

Use `--importance` for important constraints, bugs, and decisions. Use `--type operational` for active constraints and
`--type preference` for user or product preferences.

## Example Workflow

```bash
mneno status
mneno context "continue Mneno development after LOCOMO and CLI feedback"
mneno search "LOCOMO selected_memory_ids zero recall"
mneno search "Cristian CLI MCP demo preference"
# Work in the repository and verify current files.
mneno add "Next Mneno demo should show Codex recovering LOCOMO findings and CLI feedback through local CLI context." \
  --type operational --tag demo --tag codex --tag cli --importance 0.9
```

## Positioning

- Mneno is local-first and does not require network access.
- Mneno uses the CLI first; MCP, cloud, and providers are not required for this workflow.
- Mneno is not grep: grep finds text, while Mneno builds an explainable context package from remembered project
  knowledge.
