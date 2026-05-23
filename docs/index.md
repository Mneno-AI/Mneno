# Mneno

Mneno is a Python-first memory layer for AI agents and AI applications. It is designed to maintain useful,
compact, explainable, and verifiable context over time.

Mneno is not a vector database or a chat transcript archive. It is a local memory runtime that treats memory as
structured knowledge and retrieves only the pieces that are useful for the current task.

## Quickstart

```python
from mneno import MemoryClient

client = MemoryClient()
client.add(
    "The user is building Mneno, a Python SDK for explainable AI memory.",
    memory_type="semantic",
    importance=0.9,
    tags=["project", "mneno"],
)
client.add(
    "The current task is to build the first local memory engine.",
    memory_type="operational",
    importance=0.8,
    tags=["task", "mvp"],
)

results = client.search("What is the user building?")

for result in results:
    print(result.rank)
    print(result.memory.content)
    print(result.score.total)
    print(result.score.reasons)
```

## Core Concepts

### Memory

A memory is a durable unit of useful context. It is intentionally more structured than plain text.

```python
memory = client.add(
    "The user prefers concise implementation summaries.",
    memory_type="preference",
    importance=0.8,
    source="conversation",
    tags=["user", "style"],
    metadata={"scope": "documentation"},
)
```

Each memory includes:

- `id`: stable memory identifier.
- `content`: human-readable memory content.
- `memory_type`: one of `episodic`, `semantic`, `operational`, or `preference`.
- `metadata`: caller-provided structured metadata.
- `created_at` and `updated_at`: timezone-aware UTC timestamps.
- `importance`: caller-provided value from `0.0` to `1.0`.
- `access_count`: number of times the memory was returned from search.
- `last_accessed_at`: timestamp updated when search retrieves the memory.
- `source`: optional source label.
- `tags`: normalized lowercase labels.

### Memory Types

- `episodic`: conversation or task history.
- `semantic`: stable facts or extracted claims.
- `operational`: current goals, constraints, or task state.
- `preference`: user or agent preferences.

## Searching

`MemoryClient.search()` scores every local memory, sorts by total score descending, updates access tracking for returned
memories, and returns explainable result objects.

```python
results = client.search("What SDK is the user building?", limit=3)

for result in results:
    assert result.rank >= 1
    assert result.memory.content
    assert 0.0 <= result.score.total <= 1.0
```

Search returns `MemorySearchResult` objects:

- `memory`: the retrieved `Memory`.
- `score`: an explainable `MemoryScore`.
- `rank`: 1-based rank after sorting.

## Scoring

The current scorer is deterministic and dependency-free. It does not use embeddings or external AI calls.

The score includes:

- `relevance`: simple keyword overlap between the query and memory text, tags, type, and source.
- `importance`: the caller-provided importance value.
- `recency`: how recently the memory was updated.
- `frequency`: normalized access count.
- `freshness`: age penalty based on creation time.

Example score reasons:

```python
[
    "Matched query term: building",
    "Matched query term: user",
    "High importance memory",
    "Recently updated",
]
```

These explanations are part of the public behavior. Future scoring improvements should preserve inspectable score
components and reasons.

## Local Storage

The default storage backend is in-memory only. It is useful for tests, examples, and early SDK integration work.

```python
memory = client.add("Mneno stores structured memories.", memory_type="semantic")

same_memory = client.get(memory.id)
all_memories = client.list()
deleted = client.delete(memory.id)
client.clear()
```

The in-memory backend does not persist across process restarts. Durable storage providers should be added later as
optional integrations, not core dependencies.

## Auto-Compaction

Compaction reduces noisy or duplicated memory while preserving an explainable audit trail. This is a deterministic local
engine; it does not use LLM summarization, embeddings, vector search, or graph logic.

```python
from mneno import MemoryClient
from mneno.compaction import CompactionPolicy

client = MemoryClient()
client.add("User prefers Python.", memory_type="preference", importance=0.9)
client.add("User prefers Python.", memory_type="semantic", importance=0.7)
client.add("Small talk from old session.", memory_type="episodic", importance=0.1)

diff = client.preview_compaction()

print(diff.summary)
print(diff.stats)

for decision in diff.merged:
    print(decision.memory_id, decision.reason)
```

`preview_compaction()` does not mutate storage. `compact()` applies the diff:

```python
diff = client.compact(policy=CompactionPolicy())

for decision in diff.discarded:
    print(decision.reason)
```

The diff includes:

- `kept`: memory decisions that remain unchanged.
- `merged`: memories replaced by consolidated memories.
- `discarded`: memories removed from storage.
- `created`: consolidated memories created by merge decisions.
- `summary`: human-readable operation summary.
- `stats`: before/after counts and estimated reduction ratio.

The default policy is conservative:

- preserve `operational` memories.
- preserve `preference` memories.
- preserve high-importance memories.
- merge exact or near duplicates.
- discard stale low-importance memories.

Custom policies can adjust thresholds and preservation rules:

```python
policy = CompactionPolicy(
    min_score_to_keep=0.35,
    preserve_tags=["project"],
    merge_duplicates=True,
)

diff = client.preview_compaction(policy=policy)
```

## Request Models

The public client validates inputs through Pydantic v2 request models:

- `AddMemoryRequest`
- `SearchMemoryRequest`

You can use the models directly when you want validation before calling the client.

```python
from mneno import AddMemoryRequest

request = AddMemoryRequest(
    content="Mneno is Python-first.",
    memory_type="semantic",
    importance=0.9,
)
```

## MVP Scope

- In-memory local storage.
- Pydantic v2 models.
- Deterministic scoring with keyword-overlap relevance.
- Ranked, explainable search results.
- Explainable compaction diff structures.
- Deterministic auto-compaction with explainable decisions.

Provider integrations, vector databases, semantic graph storage, and LLM-based compaction will be optional
extensions later.

## Development

Set up the development environment:

```bash
scripts/setup_dev.sh
```

Run formatting, linting, typing, and tests:

```bash
scripts/format.sh
scripts/check.sh
scripts/test.sh
```

Build the package after setup:

```bash
python -m build
```

If the virtual environment is not activated, use:

```bash
.venv/bin/python -m build
```

## Current Non-Goals

- No LLM provider integrations in core.
- No embedding provider integrations in core.
- No vector database or graph database dependencies in core.
- No cloud sync or API server.
- No async API until there is a clear need.

The next major local-runtime milestone is auto-compaction with explainable diffs.
