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
client.add("The user is building Mneno, an SDK for explainable AI memory.")
results = client.search("What is the user building?")

for memory in results:
    print(memory.content)
```

## Core Concepts

- **Memory scoring**: rank memories by recency, relevance, importance, and freshness signals.
- **Auto-compaction**: preserve key claims when context gets too large or noisy.
- **Explainable memory diff**: show what was kept, merged, discarded, and why.
- **Semantic graph**: future relationship-aware retrieval layer, outside the MVP core.

## Roadmap

- In-memory MVP storage and scoring.
- Explainable compaction runtime.
- Optional persistence backends.
- Optional embedding and vector database integrations.
- Semantic graph experiments as opt-in extensions.

## License

Apache-2.0
