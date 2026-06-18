# Mneno Agent Integrations

This directory contains starter templates for using Mneno inside coding agents. The templates are documentation only:
they do not add providers, cloud services, MCP servers, retrieval changes, or new Mneno Core behavior.

Mneno is a local-first memory and context engine for coding agents. It is not a notebook and not the source of truth.
Agents use it to recover durable project context, then verify important claims against the repository.

For agent integrations, the CLI is the integration surface:

- `mneno init`
- `mneno status`
- `mneno recent`
- `mneno context "<task>"`
- `mneno search "<topic>"`
- `mneno add "<durable memory>" --tag ...`

## Why No MCP Yet

Mneno avoids MCP in this step to keep the integration simple, inspectable, and portable across Codex, Claude Code,
Cursor, Gemini CLI, Windsurf, and similar tools. Any coding agent that can run shell commands can use the CLI without a
network service, background daemon, cloud account, or provider dependency.

MCP may come later, but it is not required for the first useful workflow. The current value is that a coding agent can
recover project context locally with low overhead.

## Directory Layout

- `shared/`: reusable workflow, memory-writing, and CLI reference docs.
- `codex/`: Codex-style `AGENTS.md` template.
- `claude-code/`: Claude Code-style `SKILL.md` template.
- `cursor/`: Cursor-style `AGENTS.md` template.
- `gemini-cli/`: Gemini CLI-style `AGENTS.md` template.
- `windsurf/`: Windsurf-style `AGENTS.md` template.

## Manual Usage

Copy the template for your agent into the target project and optionally copy the shared docs for reference:

```bash
cp integrations/codex/AGENTS.md ./AGENTS.md
cp -r integrations/shared ./.mneno/agent-docs
```

For another agent, replace `codex/AGENTS.md` with the matching template path.

Before using these instructions in a project, initialize Mneno if the project does not already have a workspace:

```bash
mneno init
```

Agents should not run `mneno init` automatically unless the user explicitly asks. If `mneno status` cannot find a
workspace, the agent should tell the user to run `mneno init` in the intended project root.

Have the coding agent start each task with:

```bash
mneno status
mneno context "<current task>"
```

Use `mneno recent` only when a quick overview of recent memories would help.

## Agent Workflow Summary

1. Run `mneno status`.
2. If the workspace exists, run `mneno context "<current task>"`.
3. If context is weak, read the repository and run `mneno search "<specific topic>"` for narrow follow-ups.
4. Work normally and verify important memory against files.
5. At the end of a meaningful work unit, store one concise durable memory if there is something future agents should
   remember.

Useful memories include architecture decisions, benchmark findings, root causes, product preferences, constraints, and
next steps. Do not store secrets, credentials, huge logs, generated code dumps, or routine file edits.

Mneno stores project-local data under `.mneno/`; treat that as local memory, not as a public knowledge base.

## Thursday Demo Path

For the first demo, use the Codex template as the primary path and Claude Code as a secondary path. The demo should show
a coding agent using CLI commands to recover LOCOMO findings, Cristian's CLI feedback, current constraints, and one
useful next step without MCP, cloud, providers, or a server setup.

Example seed memories for the demo:

```bash
mneno add "LOCOMO zero recall was caused by Bench parsing selected_memory_ids incorrectly." \
  --tag locomo --tag benchmark --tag bug --importance 0.95
mneno add "Mneno recall improved to 0.258 after benchmark normalization." \
  --tag locomo --tag benchmark --tag retrieval --importance 0.85
mneno add "Keyword baseline is still stronger than Mneno on LOCOMO retrieval-only." \
  --tag locomo --tag benchmark --tag retrieval --importance 0.85
mneno add "Cristian prefers CLI integration over MCP for the first demo because MCP adds token overhead." \
  --type preference --tag cristian --tag cli --importance 0.9
mneno add "Do not work on BEAM before the Thursday demo; focus on agent integration and CLI usability." \
  --type operational --tag demo --tag constraint --importance 1.0
```

Then the agent demo can run:

```bash
mneno status
mneno context "continue Mneno development after LOCOMO and CLI feedback"
mneno search "LOCOMO selected_memory_ids zero recall"
mneno search "Cristian CLI MCP demo preference"
```

## Future Setup Command

A future command such as `mneno setup-agent` may copy the right template and shared docs automatically. Until then,
manual copying keeps the behavior explicit and easy to review.
