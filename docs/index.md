# Mneno

Mneno is a Python-first memory layer for AI agents and AI applications. It is designed to maintain useful,
compact, explainable, and verifiable context over time.

## Quickstart

```python
from mneno import MemoryClient

client = MemoryClient()
client.add("The user is building Mneno, an SDK for explainable AI memory.")
results = client.search("What is the user building?")
```

## MVP Scope

- In-memory local storage.
- Pydantic v2 models.
- Temporal scoring with keyword-overlap relevance.
- Explainable compaction diff structures.

Provider integrations, vector databases, semantic graph storage, and LLM-based compaction will be optional
extensions later.
