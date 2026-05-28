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

## Persistent Storage

Mneno defaults to in-memory storage for tests, demos, and short-lived processes. For local persistence, use JSON file or
SQLite storage.

```python
from mneno import MemoryClient
from mneno.storage import JSONFileStorage, SQLiteStorage

client = MemoryClient(storage=JSONFileStorage("data/memories.json"))
client.add("User prefers Python.", importance=0.9)

client = MemoryClient(storage=SQLiteStorage("data/mneno.db"))
client.add("User is building Mneno.", importance=0.95)
```

Use:

- `InMemoryStorage` for tests and demos.
- `JSONFileStorage` for simple local development and human-readable files.
- `SQLiteStorage` for durable local apps and larger memory sets.

External database adapters will come later as optional integrations.

## Import, Export, Backup, And Restore

Mneno exports memories with a versioned JSON format. Backups are normal export files, and import validation prevents
silent corruption from unknown formats or unsupported versions.

```python
from mneno import MemoryClient

client = MemoryClient()
client.add("User prefers Python.", importance=0.9)

payload = client.export_json()

client.export_json("exports/memories.json")

backup_path = client.backup()

client.restore("backups/mneno-backup-20260101-120000.json")

client.import_json("exports/memories.json", mode="skip_existing")
```

Import modes:

- `append`: add imported memories; conflicting IDs are copied with new IDs.
- `replace`: clear current storage first, then import.
- `skip_existing`: keep existing memories with matching IDs.
- `overwrite`: replace existing memories with imported memories of the same ID.

Cloud sync is future work. The current import/export tools are local and deterministic.

## Conflict Detection And Memory Resolution

Mneno detects simple contradictions, duplicates, and superseding facts with deterministic local heuristics. It never
deletes memories automatically. Resolution updates lifecycle metadata, records audit events, and keeps conflict reports
explainable.

```python
from mneno import MemoryClient

client = MemoryClient()

client.add("User prefers Python 3.10.", memory_type="preference")

result = client.add_with_report(
    "User now prefers Python 3.11.",
    memory_type="preference",
)

for report in result.conflict_reports:
    print(report.conflict_type, report.reason)

active = client.search("What Python version does the user prefer?")
```

Memory statuses are `active`, `superseded`, `archived`, and `conflicted`. Superseded and archived memories are excluded
from default retrieval and context building; pass `include_inactive=True` to inspect them. Audit history preserves why a
memory changed status, which memory caused the change, and the evidence behind the report.

## Hierarchical Memory Organization

Mneno organizes memories into cognitive layers so short-lived notes, working state, durable knowledge, and operational
instructions can age and retrieve differently.

Layers:

- `short_term`: transient session memories with low durability.
- `working`: current task state, immediate goals, and active constraints.
- `episodic`: session or project history and temporal events.
- `semantic`: durable factual knowledge and stable user/project information.
- `operational`: instructions, constraints, system state, and active workflows.
- `archived`: inactive historical memories, preserved but excluded by default.

```python
from mneno import MemoryClient

client = MemoryClient()

client.add(
    "Current task: build benchmark UI.",
    memory_type="operational",
)

client.evaluate_hierarchy()

operational = client.list_by_layer("operational")
```

Retrieval is lifecycle-aware: operational, working, and semantic memories receive priority; archived and superseded
memories are excluded unless you pass `include_archived=True` or `include_inactive=True`. Frequently useful memories can
be promoted, stale temporary memories can be archived, and every transition is recorded in audit history. Mneno archives
instead of silently deleting.

## Sessions And Timelines

Sessions group memories into temporal units so long-running applications can reconstruct what happened in one session
or across multiple sessions. A memory belongs to one primary session for now; richer graph-style linking is future work.

```python
from mneno import MemoryClient

client = MemoryClient()

session = client.create_session(
    title="Mneno benchmark platform work",
)

client.add(
    "Implemented Step 14 timeline support.",
    session_id=session.id,
)

timeline = client.build_timeline(
    session_ids=[session.id],
)

for event in timeline.events:
    print(event.content)
```

Session-aware retrieval boosts the active session so current work stays visible. Use `get_session_context()` to build
context for one session, `find_related_sessions()` to recover continuity across related sessions, and
`build_timeline()` to reconstruct deterministic event order from timestamps and per-session sequence indexes. Sessions,
timeline metadata, and memory session links are preserved by JSON storage, SQLite storage, import/export, backup, and
restore.

## Observability And Tracing

Mneno includes optional local tracing for debugging retrieval, context building, compaction, hierarchy transitions,
conflicts, extraction, sessions, and timelines. Tracing is disabled by default, uses only in-memory storage, and does not
send events to external services.

```python
from mneno import MemoryClient

client = MemoryClient(trace_enabled=True)

client.add("User prefers Python.")
client.search("Python")

trace = client.get_trace(client.last_trace_id)

for event in trace.events:
    print(event.operation, event.message)
```

Use `client.list_traces()` and `client.clear_traces()` to inspect or reset local traces. `TraceInspector` can summarize
traces, filter events by memory or event type, explain a memory decision, and export a trace as JSON. Traces are intended
for developer debugging and avoid external tracing dependencies.

## Evaluation And Benchmark Integration

Mneno exposes local evaluation hooks for future Mneno Bench adapters. The SDK does not include benchmark datasets,
online telemetry, or external evaluation dependencies; it provides stable report models, deterministic structural
metrics, trace export, and benchmark payload helpers.

```python
from mneno import MemoryClient

client = MemoryClient(trace_enabled=True)

client.add("The user is building Mneno.", importance=0.9)

report = client.evaluate_context(
    query="What is the user building?",
)

print(report.metrics)
```

Evaluation helpers cover retrieval precision/recall/MRR, token efficiency, compaction reduction, structural retention,
latency, scanned/selected memory counts, and trace event counts. Use `evaluate_search()`, `evaluate_context()`, and
`evaluate_compaction()` to create serializable operation reports. Use `export_benchmark_result()` to produce the stable
Mneno Bench payload:

```json
{
  "format": "mneno.benchmark.result",
  "version": 1,
  "benchmark": "synthetic",
  "metrics": [],
  "traces": [],
  "metadata": {}
}
```

External LOCOMO, LongMemEval, BEAM, or Mneno Bench adapters can implement `BenchmarkAdapter` without changing core SDK
behavior.

## Provider Architecture

Mneno is provider-agnostic. The core runtime remains deterministic and local by default, while Phase 2 introduces
stable plugin contracts for future integrations.

Current provider interfaces:

- `EmbeddingProvider`
- `LLMProvider`
- `RerankerProvider`
- `ProviderRegistry`

No real OpenAI, Anthropic, Cohere, HuggingFace, vector database, graph database, or network provider is included in
core. Future integrations should be optional adapters that implement these contracts.

```python
from mneno.providers import ProviderRegistry
from mneno.providers.embedding import DummyEmbeddingProvider

registry = ProviderRegistry()
registry.register_embedding("dummy", DummyEmbeddingProvider())

provider = registry.get_embedding("dummy")
vectors = provider.embed(["User prefers Python."])
```

The dummy providers are deterministic and local-only. They exist for tests, examples, and adapter development.

## Semantic Retrieval With Providers

Mneno can optionally use an `EmbeddingProvider` to add semantic relevance to search and context building. The default
behavior remains deterministic keyword/scoring retrieval when no provider is configured.

No real external providers are included in core yet. Future integrations can implement the `EmbeddingProvider`
protocol without changing Mneno's local runtime.

```python
from mneno import MemoryClient
from mneno.providers.embedding import DummyEmbeddingProvider

client = MemoryClient(
    embedding_provider=DummyEmbeddingProvider(),
)

client.add("User is building Mneno, an SDK for explainable AI memory.", importance=0.9)
client.add("User likes Italian food.", importance=0.5)

results = client.search(
    "AI memory SDK project",
    use_semantic=True,
)

for result in results:
    print(result.memory.content)
    print(result.score.total)
    print(result.score.reasons)
```

Use `use_semantic=False` to force deterministic fallback search even when an embedding provider is configured. Mneno
computes embeddings at search time for now; embedding caches, vector indexes, and vector database adapters are future
work.

## Reranker-Powered Retrieval

Mneno can optionally apply a second-stage reranker after candidate generation. Candidate generation still uses the
deterministic scorer and, when configured, optional semantic relevance. The reranker only reorders candidates and adds
explainable reranking metadata.

No external reranker integrations are included in core. Future providers can implement `RerankerProvider`.

```python
from mneno import MemoryClient
from mneno.providers.reranker import DummyRerankerProvider

client = MemoryClient(
    reranker_provider=DummyRerankerProvider(),
)

client.add("User is building Mneno, an AI memory SDK.", importance=0.5)
client.add("Unrelated high-priority note.", importance=1.0)

results = client.search(
    "AI memory SDK",
    use_reranker=True,
)

for result in results:
    print(result.memory.content)
    print(result.original_rank)
    print(result.reranked_rank)
    print(result.rerank_reason)
```

Use `use_reranker=False` to skip reranking even when a provider is configured. If `use_reranker=True` is passed without
a provider, Mneno raises a clear provider error.

## Memory Extraction

Mneno can extract structured memories from raw text. The default extractor is deterministic and local: it uses simple
heuristics to identify durable facts, preferences, goals, constraints, and project information.

```python
from mneno import MemoryClient

client = MemoryClient()

result = client.extract_memories(
    "The user is building Mneno. They prefer Python 3.11."
)

for memory in result.extracted:
    print(memory.content, memory.memory_type, memory.reason)

client.add_from_text(
    "The user is building Mneno. They prefer Python 3.11."
)
```

## LLM-Assisted Extraction

LLM usage is optional. Mneno core does not include real provider dependencies; future adapters can implement
`LLMProvider` to connect any model. Deterministic extraction remains the fallback.

```python
from mneno import MemoryClient
from mneno.providers.llm import DummyLLMProvider

client = MemoryClient(llm_provider=DummyLLMProvider())

result = client.extract_memories(
    "The user is building Mneno. They prefer Python 3.11.",
    use_llm=True,
)
```

LLM-assisted compaction is intentionally limited: deterministic policy still decides what to keep, merge, or discard.
The LLM may only improve merged memory wording for groups already selected by the deterministic engine.

## Roadmap

- In-memory MVP storage and scoring.
- Explainable compaction runtime.
- Optional persistence backends.
- Optional embedding and vector database integrations.
- Semantic graph experiments as opt-in extensions.

## License

Apache-2.0
