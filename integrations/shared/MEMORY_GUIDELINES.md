# Memory Guidelines

Mneno memory should help future agents recover useful project context without reading every past interaction. Store
durable facts, decisions, constraints, preferences, and root causes. Avoid noisy traces of routine work.

Mneno is not the source of truth. It is an assistive memory layer. Agents should verify important claims against the
repository and current user instructions.

## Good Memories

Store:

- Architectural decisions.
- Benchmark findings.
- User or product preferences.
- Project constraints.
- Bugs and root causes.
- Roadmap decisions.
- "Do not do X before Y" constraints.
- Important command or workflow discoveries.
- Useful next steps for continuing a task.
- Failed attempts only when the root cause is durable and useful.

## Bad Memories

Do not store:

- Every file edit.
- Raw stack traces unless summarized.
- Large pasted logs.
- Temporary failed attempts.
- Secrets.
- Credentials.
- API keys or tokens.
- Sensitive personal data.
- Generated code dumps.
- Facts that are easily read from current files unless they explain a decision.
- Vague notes without future value.

## Memory Style

A good memory is:

- Concise.
- Factual.
- Durable.
- Clear about the project or context.
- Specific enough to avoid ambiguity.
- Tagged with useful domain labels.

Prefer one clear sentence over several low-value entries. Use a short paragraph only when needed.

The workspace is already project-local, so do not repeat the project name unless the memory would otherwise be
ambiguous. Local file paths are okay only when durable and useful.

Suggested tags:

- `architecture`
- `cli`
- `benchmark`
- `bug`
- `workflow`
- `demo`
- `constraint`
- `retrieval`
- `locomo`
- `decision`

Use `--importance` for important constraints, bugs, and decisions. Otherwise omit it. Use `--type operational` for
active task constraints and `--type preference` for user or product preferences. Most facts can use the default type.

For contradictions, write the new memory explicitly and carefully. Do not claim something is corrected, obsolete, or no
longer true unless the user or evidence clearly supports that.

## Examples

Good:

```bash
mneno add "LOCOMO zero recall was caused by Bench parsing selected_memory_ids incorrectly." \
  --tag locomo --tag benchmark --tag bug --importance 0.95
```

Good:

```bash
mneno add "Cristian prefers CLI integration over MCP for the first demo because MCP adds token overhead." \
  --type preference --tag cristian --tag cli --importance 0.9
```

Good:

```bash
mneno add "Do not work on BEAM before the Thursday demo; focus on agent integration and CLI usability." \
  --type operational --tag demo --tag constraint --importance 1.0
```

Bad:

```bash
mneno add "fixed stuff"
```

Bad:

```bash
mneno add "got error, trying another thing"
```

Bad:

```bash
mneno add "Edited integrations/codex/AGENTS.md and then changed a sentence in README."
```
