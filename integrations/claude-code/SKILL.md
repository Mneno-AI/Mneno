---
name: mneno-memory
description: Use when working in a repository that uses Mneno for local project memory through the CLI, including task-start context recovery, narrow memory search, and storing durable project facts before stopping work.
---

# Mneno Memory

Use this skill when the repository has a `.mneno/` workspace and the task may depend on prior project context.

## Start of task

1. Run `mneno status`.
2. Run `mneno context "<current task>"`.
3. Verify important claims against repository files before acting.

## During work

- Use `mneno search "<specific topic>"` for narrow follow-up lookup.
- Do not use Mneno for broad vague discovery.
- Do not assume Mneno is the source of truth.

## Before stopping

Store one or more durable memories only if useful:

```bash
mneno add "..." --tag ...
```

Store:

- Decisions.
- Root causes.
- Constraints.
- Benchmark findings.
- Next steps.

Do not store:

- Secrets.
- Credentials.
- Huge logs.
- Routine edits.
- Generated code dumps.

## References

Load only the reference needed for the current task:

- Read `references/AGENT_WORKFLOW.md` when the task is continuing prior work or the Mneno workflow is unclear.
- Read `references/COMMAND_REFERENCE.md` before using unfamiliar CLI options or interpreting command output.
- Read `references/MEMORY_GUIDELINES.md` before storing memories or choosing tags.
