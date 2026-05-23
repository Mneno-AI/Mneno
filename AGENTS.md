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
- Do not introduce complex graph logic in the MVP.
- Do not make compaction behavior opaque.
- Do not add public APIs without documentation and tests.
- Do not broaden the package scope beyond Python-first SDK foundations.
