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

## Roadmap

- In-memory MVP storage and scoring.
- Explainable compaction runtime.
- Optional persistence backends.
- Optional embedding and vector database integrations.
- Semantic graph experiments as opt-in extensions.

## License

Apache-2.0
