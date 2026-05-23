# Mneno

Mneno is a Python SDK for developers building copilots, support agents, internal AI tools, and long-running AI
applications.

It is not just a memory store. Mneno is an anti-context-rot memory runtime: it keeps context useful, compact,
explainable, and verifiable as an application runs over time.

## Why Context Rot Matters

Long-running AI systems accumulate stale facts, duplicated notes, noisy transcripts, and vague summaries. That context
eventually makes retrieval worse, not better. Mneno is being built around scoring, compaction, and explainable diffs so
developers can see what memory was kept, merged, discarded, and why.

## Quickstart

```bash
pip install mneno
```

For local development:

```bash
scripts/setup_dev.sh
```

## Example Usage

```python
from mneno import MemoryClient

client = MemoryClient()
client.add(
    "The user is building Mneno, a Python SDK for explainable AI memory.",
    memory_type="semantic",
    importance=0.9,
    tags=["project", "mneno"],
)

results = client.search("What is the user building?")

for result in results:
    print(result.memory.content)
    print(result.score.total)
    print(result.score.reasons)
```

## Core Concepts

- **Memory scoring**: rank memories by recency, relevance, importance, and freshness signals.
- **Explainable retrieval**: search returns ranked `MemorySearchResult` objects with score components and reasons.
- **Auto-compaction**: preserve key claims when context gets too large or noisy.
- **Explainable memory diff**: show what was kept, merged, discarded, and why.
- **Semantic graph**: future relationship-aware retrieval layer, outside the MVP core.

## Auto-Compaction With Explainable Diff

Mneno can preview or apply deterministic local compaction. It does not call an LLM yet. The current engine keeps
preserved memory types, merges simple duplicates, discards stale low-value memories, and returns an inspectable diff.

```python
from mneno import MemoryClient
from mneno.compaction import CompactionPolicy

client = MemoryClient()

client.add("User prefers Python.", memory_type="preference", importance=0.9)
client.add("User prefers Python.", memory_type="semantic", importance=0.7)
client.add("Small talk from old session.", importance=0.1)

diff = client.preview_compaction()

print(diff.summary)
print(diff.stats)

diff = client.compact(policy=CompactionPolicy())

for decision in diff.discarded:
    print(decision.reason)
```

Use `preview_compaction()` to inspect decisions without mutating storage. Use `compact()` to apply the diff to the
local in-memory store.

## Build Explainable Context

Mneno can build a deterministic context package for prompt injection. It retrieves local memories, scores them, fits
them inside an approximate token budget, and explains what was included or excluded.

```python
from mneno import MemoryClient

client = MemoryClient()
client.add("User is building Mneno.", importance=0.9)
client.add("User prefers Python 3.11.", importance=0.8)

context = client.build_context("What is the user building?", budget=50)

print(context.text)

for item in context.included:
    print(item.reason)
```

The current budget uses a local approximate token estimator based on whitespace splitting. No tokenizer, LLM, embedding,
or external service is required.

## Policy-Driven Context Building

Use presets for common cost and recall profiles:

```python
context = client.build_context("What matters now?", preset="cheap")
context = client.build_context("What matters now?", preset="high_recall")
context = client.build_context("What is the current agent state?", preset="agent_state")
```

Use a custom policy when you need explicit control:

```python
from mneno.context import ContextPolicy

custom = ContextPolicy(
    max_tokens=800,
    reserve_tokens=100,
    min_score=0.25,
    strategy="importance",
)

context = client.build_context("What matters now?", policy=custom)
```

Available presets:

- `cheap`: smallest useful context, optimized for cost.
- `balanced`: default quality/cost tradeoff.
- `high_recall`: includes more context to avoid missing useful memories.
- `agent_state`: prioritizes operational state, goals, constraints, and preferences.

## Roadmap

- In-memory MVP storage and scoring.
- Explainable compaction runtime.
- Optional persistence backends.
- Optional embedding and vector database integrations.
- Semantic graph experiments as opt-in extensions.

## License

Apache-2.0
