# Local performance baseline

## Environment and scope

Executed on macOS-27.0.1-arm64-arm-64bit, Apple M5 Pro (15 logical CPUs), Python 3.11.17, arm64. Synthetic local records only; no external benchmark/model/provider calls. Versions: Pydantic 2.14.0, Typer 0.27.3, Rich 14.3.4, pytest 9.1.1, Ruff 0.17.0, mypy 2.4.0. Host activity, power mode, and physical RAM were not controlled/measured.

## Methodology

`scripts/phase_a_baseline.py` populates separate temporary in-memory, SQLite, and JSON stores. Each record has a stable synthetic ID, a short Python/SQLite sentence, project tag, importance .5, no session. Public search uses query `Python SQLite`, limit 10; context uses int budget 120. Auto conflict detection is disabled for population; store insertion is measured separately from public SDK insertion. One warm-up precedes five timed calls per operation. Report median and min–max; raw samples are in [performance-results.json](performance-results.json). These are descriptive distributions, not statistically reliable tail-latency estimates.

Timed retrieval includes persisted access-count updates. Repeated calls mutate access state, as real SDK operations do; datasets/state are not reset between timed repetitions. Detailed tracing clears retained traces before each traced search and includes that clear in its measurement. Search/context without tracing run first. The synthetic uniform relevance distribution exercises all-record scoring and cutoff handling, not realistic relevance quality. No time is spent exporting JSON inside the traced-search latency; export size is measured afterward.

Store population is a single measured population, not a repeated throughput distribution; interpret throughput as an indicative setup observation. Public SDK add of 100 records has five repeated batches with default conflict detection. `tracemalloc` measures peak Python allocation while constructing the models only, outside latency measurement; it is not whole-process RSS, trace/store memory, or SQLite native allocation.

## Retrieval measurements

| Backend | Memories | Search ms median [min–max] | Context ms median [min–max] | Traced search ms median [min–max] | Trace/search ratio |
| --- | ---: | ---: | ---: | ---: | ---: |
| memory | 100 | 1.43 [1.42–1.51] | 1.61 [1.58–2.00] | 6.06 [6.01–6.23] | 4.23x |
| sqlite | 100 | 9.53 [7.18–11.01] | 8.54 [8.13–10.51] | 12.09 [11.92–12.61] | 1.27x |
| json | 100 | 11.71 [11.47–12.21] | 16.79 [16.63–17.05] | 16.49 [16.30–16.55] | 1.41x |
| memory | 1,000 | 14.78 [14.50–14.82] | 15.82 [15.74–16.18] | 67.28 [63.90–73.51] | 4.55x |
| sqlite | 1,000 | 33.80 [33.62–43.48] | 32.29 [31.36–39.49] | 84.86 [84.38–90.22] | 2.51x |
| json | 1,000 | 114.08 [107.32–116.65] | 160.21 [154.92–160.82] | 162.40 [155.64–163.07] | 1.42x |
| memory | 10,000 | 176.60 [152.65–177.67] | 195.47 [190.15–201.31] | 1105.80 [1088.01–1148.56] | 6.26x |
| sqlite | 10,000 | 554.42 [462.88–575.42] | 425.45 [412.90–511.94] | 1492.87 [1439.25–1532.51] | 2.69x |

## Persistence population and diagnostic size

| Backend | Memories | Store population ms | Records/second | Model construction peak MiB | Events/search | Trace JSON MiB |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| memory | 100 | 0.97 | 102832 | 0.22 | 222 | 0.30 |
| sqlite | 100 | 32.09 | 3116 | 0.22 | 222 | 0.30 |
| json | 100 | 62.65 | 1596 | 0.22 | 222 | 0.30 |
| memory | 1,000 | 9.53 | 104914 | 2.12 | 2,022 | 2.94 |
| sqlite | 1,000 | 338.34 | 2956 | 2.12 | 2,022 | 2.95 |
| json | 1,000 | 4748.33 | 211 | 2.12 | 2,022 | 2.97 |
| memory | 10,000 | 111.97 | 89312 | 21.26 | 20,022 | 29.61 |
| sqlite | 10,000 | 3268.16 | 3060 | 21.26 | 20,022 | 29.72 |

Public SDK default add, 100-record batches: **176.61 [175.92–264.09] ms**, median implied throughput 566 records/second. This includes automatic conflict comparisons and is not comparable to raw store insertion.

## Interpretation and limits

- In-memory untraced search grows approximately with collection size; SQLite adds full payload deserialization and repeated list reads. There is no lexical index candidate pruning. These measurements justify investigating scan-stage cost, not changing scoring weights.
- JSON file rewrite per insertion and selected-memory access update dominates at 1,000 records. JSON at 10,000 was deliberately omitted to bound whole-document write amplification. Memory/SQLite both ran at 10,000.
- Detailed tracing is costly and unbounded. At 10,000 records it emits 20,022 events and roughly 31 MB decimal of serialized diagnostics. Recorder event-list copying is a source-confirmed quadratic append pattern; this run does not isolate its share of total cost.
- No context-with-tracing distribution, multi-session workload, conflict-heavy large insertion run, concurrent writer test, cold-start distribution, exact LLM-token comparison, whole-process RSS profile, disk-failure performance, or large external benchmark was measured.
- The first preliminary run preceded the optional fixed-time scorer and final diagnostics fixes. The checked-in raw measurements were rerun with the stabilized scorer/client. All result-count/store-count/trace-status assertions executed. Retrieval time remains default wall clock; this is a latency baseline, not a byte-identical replay experiment.

## First Phase B performance investigation

After the integrity/replay blockers close, profile full-store loads, continuity reads, scoring/tokenization, sorting, access persistence, and trace recording separately on identical saved snapshots. SQLite FTS5 with BM25 is a plausible optional local candidate generator because SQLite already exists and full scans cost hundreds of milliseconds at 10k. It will not solve JSON write amplification, transaction gaps, Unicode semantics, or trace overhead. Preserve default fallback, lifecycle/session metadata, ID mapping, scoring explanations, candidate coverage, provider-stage behavior, and updates/import synchronization. Verify FTS5 availability per supported Python SQLite build before committing to it. No FTS/BM25 code or readiness claim is made in Phase A.
