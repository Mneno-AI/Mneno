# AGENTS.md

## Project Overview

Mneno is a Python-first SDK for AI memory. It is an anti-context-rot memory runtime for copilots, support agents,
internal AI tools, and long-running AI applications.

Mneno should maintain useful, compact, explainable, and verifiable context over time. It is not a generic memory store
and should not become a thin wrapper around provider APIs.

## Repository Structure

- `mneno/`: core Python package.
- `mneno/scoring/`: memory scoring interfaces and temporal scoring.
- `mneno/compaction/`: explainable compaction interfaces and diff templates.
- `mneno/conflicts/`: deterministic conflict detection, reports, and safe resolution policies.
- `mneno/hierarchy/`: memory layer definitions, retention policies, and lifecycle transition management.
- `mneno/observability/`: local trace models, in-memory recorder, and inspector utilities.
- `mneno/evaluation/`: deterministic metrics, benchmark adapters, operation reports, and stable export helpers.
- `mneno/retrieval/`: retrieval interfaces.
- `mneno/storage/`: storage interfaces and local in-memory storage.
- `mneno/providers/`: provider protocols, dummy local providers, and provider registry.
- `mneno/policies/`: runtime policy configuration.
- `tests/`: pytest suite.
- `examples/`: runnable usage examples.
- `scripts/`: development, formatting, and test commands.
- `docs/`: project documentation.

## Development Setup

Use Python 3.11 or newer.

```bash
scripts/setup_dev.sh
```

The setup script uses `uv` when available and falls back to `pip` with a local virtual environment.

## Build, Lint, and Test Commands

```bash
scripts/format.sh
scripts/check.sh
scripts/test.sh
python -m build
```

`scripts/check.sh` must pass before a pull request is ready.

## Core APIs

The main public entrypoint is:

```python
from mneno import MemoryClient
```

The initial client supports local in-memory add and search operations. Public APIs must be documented and covered by
tests when they are added or changed.

## Phase 2 Provider Architecture

Phase 2 introduces provider and plugin interfaces while keeping Mneno deterministic and local by default.

Provider goals:

- Keep Mneno provider agnostic.
- Avoid vendor lock-in.
- Keep integrations modular and replaceable.
- Prepare for embeddings, reranking, and LLM-assisted compaction without adding real providers to core.
- Preserve the existing deterministic fallback behavior.

Provider contracts live in `mneno/providers/`:

- `EmbeddingProvider`
- `LLMProvider`
- `RerankerProvider`
- `ProviderRegistry`

Dummy providers may exist in core only when they are deterministic, local-only, and used for tests/examples. Real
providers such as OpenAI, Anthropic, Cohere, HuggingFace, LiteLLM, Ollama, vector databases, graph databases, and cloud
services must be optional integrations outside the core dependency path.

## Semantic Retrieval Phase

Semantic retrieval is provider-based and optional. When an `EmbeddingProvider` is configured, Mneno may compute query
and memory embeddings at search time and use cosine similarity as an additional explainable relevance signal.

Fallback rules:

- If no embedding provider is configured, existing deterministic keyword/scoring retrieval remains the default.
- `use_semantic=False` must force deterministic fallback behavior.
- `use_semantic=True` must raise a clear provider error when no embedding provider exists.
- Context building may benefit from semantic scoring when the configured scorer has an embedding provider.

Current constraints:

- Embeddings are computed at search time.
- Embeddings are not persisted in JSON or SQLite storage.
- No vector indexes, vector caches, vector databases, or graph retrieval are part of core yet.
- No real provider dependencies or network calls are allowed in core.

## Reranking Architecture

Retrieval is staged:

1. Candidate generation through deterministic scoring and optional semantic retrieval.
2. Optional second-stage reranking through `RerankerProvider`.

Reranking rules:

- Reranker providers must remain optional.
- If no reranker provider is configured, retrieval must behave as before.
- `use_reranker=False` must force the non-reranked path.
- `use_reranker=True` must raise a clear provider error when no reranker provider exists.
- Reranking must preserve score objects and add explainability metadata such as original rank, reranked rank, provider
  name, and reason.
- Context building may use reranking when a reranker provider is configured, but policy and budget behavior must remain
  intact.

Do not add Cohere, Jina, HuggingFace, OpenAI, or other reranker dependencies to core. Real rerankers belong in optional
provider packages or extras.

## Extraction Architecture

Mneno supports deterministic and optional LLM-assisted memory extraction.

Extraction rules:

- Deterministic extraction is the default fallback and must not require provider configuration.
- LLM-assisted extraction must use the `LLMProvider` interface only.
- No real LLM dependencies or network calls belong in core.
- All LLM outputs must be parsed as structured data and validated with Pydantic models.
- Invalid LLM output must produce explicit errors; do not silently treat it as successful extraction.
- `add_from_text` may add valid extracted memories even when other extracted items fail validation.

LLM-assisted compaction rules:

- LLMs must not decide destructive memory deletion.
- Deterministic compaction policy decides keep, merge, and discard decisions.
- LLMs may only improve merged memory wording for groups already selected by deterministic merge logic.
- If LLM merge output is invalid, fall back to deterministic merged content or report the issue clearly.
- Compaction diffs must remain explainable.

## Conflict Detection And Memory Lifecycle

Mneno memories have lifecycle statuses:

- `active`: normal retrieval candidate.
- `superseded`: retained for audit/history but replaced by a newer memory.
- `archived`: retained but excluded from default retrieval.
- `conflicted`: retained with explicit conflict links and audit history.

Conflict detection philosophy:

- Conflict detection must be deterministic, local-only, and explainable by default.
- Reports must include a clear reason, evidence, severity, type, and suggested action.
- Prefer conservative heuristics over opaque inference.
- Optional LLM hooks may be prepared through provider interfaces, but LLMs must not be required for conflict detection
  or memory resolution.
- No real provider dependencies, network calls, vector databases, graph databases, or heavyweight NLP dependencies
  belong in core conflict detection.

Safe resolution behavior:

- Never delete memories automatically.
- Preserve audit history when marking memories as superseded, archived, or conflicted.
- Superseding a memory should set `superseded_by` and add audit events to both the old and new memory.
- Contradictions should link memories with `conflicts_with` and add audit events.
- Duplicate handling may archive only when policy explicitly allows it; default behavior is report/audit only.
- Old memory payloads without status, conflict links, or audit events must keep loading with safe defaults.
- Search and context building should prefer active memories by default and exclude archived or superseded memories unless
  an explicit inactive-inclusion option is used.

## Hierarchical Memory Organization

Mneno organizes memories into lifecycle-aware layers:

- `short_term`: transient session memories, low durability, likely to be archived or compacted quickly.
- `working`: current active task state, goals, constraints, and immediate reasoning context.
- `episodic`: session/project history, interactions, and temporal events.
- `semantic`: durable facts, preferences, and stable user/project knowledge.
- `operational`: instructions, constraints, system state, and active workflows.
- `archived`: inactive historical memories retained for audit and normally excluded from retrieval.

Hierarchy philosophy:

- Layer behavior must be deterministic and local-first.
- Promotion, demotion, and archival must be explainable and auditable.
- Retention should use transparent signals: importance, access count, recency, memory type, status, and current layer.
- Archival is preferred over deletion. Do not silently delete memories during hierarchy evaluation.
- Operational memories should be preserved unless an explicit policy says they are stale.
- Frequently useful short-term memories may be promoted to episodic; high-retention episodic memories may be promoted to
  semantic.
- Stale working memories may demote to episodic; stale or low-retention temporary memories may archive.

Lifecycle-aware retrieval:

- Default retrieval and context building should prioritize `operational`, `working`, and `semantic` memories.
- `archived` and `superseded` memories should be excluded by default and only included through explicit options.
- Search and context explanations should mention meaningful layer influence when it affects inclusion or ranking.
- Layer metadata and transition audit history must remain compatible with JSON, SQLite, import/export, backup, and
  restore.

## Sessions And Timeline Support

Sessions are lightweight temporal groupings for memories:

- A memory has one primary `session_id` for now.
- `sequence_index` orders memories within a session.
- Sessions have active, closed, and archived statuses.
- Sessions organize continuity; they are not graph memory. Future graph memory should remain a separate design.

Session philosophy:

- Session support must be deterministic, local-first, and lightweight.
- Sessions should preserve temporal order and help reconstruct what happened across time.
- Session summaries should be deterministic unless an explicit provider-backed summarizer is added later.
- Closing or archiving a session must not delete memories.
- Import/export, backup/restore, JSON storage, and SQLite storage must preserve sessions and memory session metadata.

Timeline reconstruction:

- Timelines should sort deterministically by timestamp, session id, sequence index, and memory id.
- Timeline events must explain ordering decisions.
- Timelines should support one session or multiple sessions without external services.

Continuity behavior:

- Related sessions should be found with deterministic local relevance signals such as token overlap.
- Archived sessions should not be treated as active continuity sources by default.
- Session-aware retrieval/context may boost current-session memories and explain that boost.
- Context building should mention session continuity when active-session membership affects inclusion.

## Observability And Tracing

Mneno observability is local, optional, and deterministic.

Rules:

- Tracing must be disabled by default.
- Core tracing must not use external services, OpenTelemetry, network calls, or heavyweight dependencies.
- Traces should stay in memory unless an explicit future storage/export design is added.
- Every complex decision should be traceable when tracing is enabled: scoring, retrieval filtering, semantic usage,
  reranking, context inclusion/exclusion, compaction decisions, hierarchy transitions, conflict reports/resolution,
  extraction, session actions, and timeline ordering.
- Trace messages and data must be explainable and stable enough for tests.
- Do not put API keys, secrets, credentials, or raw provider payloads in trace data by default.
- Prefer structured event data over opaque text blobs.
- Tracing must remain backward compatible with existing public return types.

## Evaluation And Benchmark Integration

Mneno Bench support is local-first benchmark plumbing, not bundled benchmark data.

Rules:

- Evaluation must be deterministic and structural unless a future explicit evaluator provider is introduced.
- Do not add external benchmark dependencies, online telemetry, uploads, network calls, or hosted services to core.
- Export schemas must be stable and versioned.
- Operation evaluation reports should be serializable and include metrics, operation metadata, timing, counts, and trace
  references where available.
- Metrics should remain simple and explainable: precision@k, recall@k, MRR, token efficiency, reduction ratio, latency,
  scanned/selected counts, and trace event counts.
- Benchmark adapters should use the `BenchmarkAdapter` protocol so LOCOMO, LongMemEval, BEAM, and Mneno Bench
  integrations can live outside core.
- Trace export for benchmarks must remain local and must not include secrets or raw provider payloads by default.

## Import Patterns

- Prefer imports from stable package modules such as `mneno.models`, `mneno.storage`, and `mneno.scoring`.
- Keep `mneno.__init__` focused on the small public API surface.
- Do not import optional integrations from core modules.

## Coding Standards

- Python version is 3.11+.
- Use Pydantic v2 for models.
- Use Ruff for linting and formatting.
- Keep line length at 120 characters.
- Keep type hints precise and mypy-clean.
- Keep the core package lightweight.

## Architecture

Mneno core should provide:

- Memory models.
- Local memory storage interfaces.
- Scoring interfaces and lightweight scoring implementations.
- Explainable compaction diff structures.
- Policy configuration.
- Provider protocols and a lightweight registry.

Integrations belong outside the core dependency path. Add optional extras later for LLM providers, embedding providers,
vector databases, graph databases, and persistence backends.

## Task Completion Guidelines

- Keep changes minimal and aligned with the repository structure.
- Add or update tests for public behavior.
- Run `scripts/check.sh` when practical.
- Update docs and examples when public APIs change.
- Preserve explainability in scoring and compaction behavior.

## Contributing Guidelines

- Open issues for substantial API or architecture changes.
- Keep pull requests focused.
- Explain user-facing behavior and migration impact.
- Avoid hidden provider assumptions.

## Pull Request Requirements

- Passing Ruff, mypy, and pytest checks.
- Tests for new public APIs.
- Documentation for new public behavior.
- No new heavyweight core dependencies.
- No network calls in core provider code.
- Clear explanation of memory scoring or compaction decisions when behavior changes.

## Do NOT

- Do not add LLM providers to core dependencies.
- Do not add embedding providers to core dependencies.
- Do not add reranker providers to core dependencies.
- Do not add network calls to core provider contracts or dummy providers.
- Do not add vector DB or graph DB clients to core dependencies.
- Do not persist embeddings in storage until a versioned embedding cache/index design exists.
- Do not create vendor-specific abstractions in core.
- Do not make providers mandatory for local memory, compaction, retrieval, or context building.
- Do not let LLMs make destructive memory lifecycle decisions.
- Do not accept unvalidated LLM structured output.
- Do not introduce complex graph logic in the MVP.
- Do not make compaction behavior opaque.
- Do not add public APIs without documentation and tests.
- Do not broaden the package scope beyond Python-first SDK foundations.
