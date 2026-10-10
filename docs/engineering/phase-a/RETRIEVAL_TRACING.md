# Retrieval tracing contract

## Existing architecture and compatibility

`observability/trace.py:OperationTrace` has id, operation, started/completed timestamps, duration_ms, events, status, summary, metadata. `events.py:TraceEvent` has event/trace ID, operation/type/timestamp/message, optional memory/session IDs, and structured data. `recorder.py:TraceRecorder` retains traces locally; `inspector.py:TraceInspector` filters and explains events. No network/export upload, OpenTelemetry, or persistent trace backend exists. Supplying a recorder enables tracing; otherwise tracing is disabled by default.

Search still returns `list[MemorySearchResult]`, with full Memory, MemoryScore, positive rank, optional original/reranked ranks/reason/name. Context still returns ContextPackage with included/excluded IDs/content/scalar score/estimated_tokens/reasons plus policy/stats/text/trace_id. Private context stage data never appears in public JSON. `client.last_trace_id` links search to its trace; context also returns trace_id. Parallel concurrent operations on one client are not supported by this last-trace association.

Single export: `{"format":"mneno.trace","version":1,"trace":{...}}`.
All-trace export: same format/version, `traces` list of raw trace objects.
Benchmark export (`evaluation/export.py`): `mneno.benchmark.result`, version 1, benchmark name/time/metrics/traces/metadata; embedded traces use single-trace envelopes. Pydantic JSON mode converts dates/enums. New event data is additive; no envelope/result version change. Consumers must allow unknown event types/data keys rather than infer a closed event enum.

## Supported stage reconstruction

| Event | Available identifiers/data | Interpretation |
| --- | --- | --- |
| operation_started / query_received | trace ID, operation, query, search limit; timestamp | Use trace ID as operation/query correlation ID. External evaluators should maintain their own benchmark query ID -> trace ID mapping |
| candidate_filtering (search) | initial_candidate_ids, post_filter_candidate_ids, excluded_memory_ids, stored_count, candidate_count | Full stored snapshot IDs, lifecycle-visible IDs, lifecycle exclusions; there is no lexical candidate-generation index |
| inactive_filtering_applied (search) | applied, include_archived/include_inactive, excluded_count | Exact visibility mode; skip/relaxed behavior explicit |
| context_candidates | initial_candidate_ids, post_filter_candidate_ids, candidate_count | Context lifecycle exclusions = initial minus post-filter; excluded ContextItems do not include lifecycle-filtered records |
| effective_retrieval_config | resolved limit, visibility, active/related session IDs, scoring policy, reference_time; search semantic/reranker booleans and scorer class; context policy and actual builder provider booleans | Capture normalized effective settings, not private provider objects or credentials. Layer/session constants documented in architecture audit |
| semantic_stage (search) | used | Existing configured scorer semantic usage. No vector cache/generation stage is fabricated |
| score_calculated / context_candidate_scored | memory/session IDs, supported external identity metadata, lexical/component/layer/status/session diagnostics | Reconstruct implemented scoring inputs; context score events describe final decision candidates rather than a real-time score-stage boundary |
| query_relevance_filtering (search) | applied/counts; per-ID retrieval_candidate_decision rank=None + exclusion_reason for zero relevance | Separate relevance eligibility from lifecycle filtering and final cutoff |
| reranker_stage (search) | used, initial_ranking_ids, reranker_input_ids | Complete pre-rerank ranking; when disabled, input IDs [] and used False |
| ranking_completed (search) | ranking_ids, reranker_output_ids | Complete final order before limit; when disabled, reranker output [] |
| retrieval_candidate_decision | memory ID, final rank, included, exclusion_reason, score data | Included vs ranked below limit vs zero relevance; final rank is after optional reranking |
| final_results_selected | memory_ids in result order | Authoritative search-selected IDs; score computed before access increments |
| context_ranking_completed | initial_ranking_ids, reranker_input_ids/output_ids, context_included_ids, excluded_memory_ids | Actual ContextBuilder sort and rerank order before optional candidate limit; disabled reranker arrays [] |
| context_item_included/excluded | memory ID, rank, included, exclusion_reason, estimated_tokens, score components | Distinguish budget, min-score, relevance, dedupe, max-items, and candidate limit exclusions |
| context_budget_calculated / context_stats | max/reserve/available/used/remaining tokens, candidate/included/excluded counts, policy | Whitespace content estimate contract, not exact model token count |
| access_count_updated | memory ID, persisted count | Retrieval mutates state; return memory payload contains post-access counters |
| operation_failed | error_type; status error, completed timestamp, duration | Search/context failures now finish traces and preserve exceptions; no raw provider payload/exception message copied |

Score diagnostics expose existing signals: recency/frequency/freshness/importance, content/metadata/combined lexical relevance, semantic and overall relevance, exact/normalized/metadata matched terms, phrase/substring flags, layer/status adjustments, current/continuity boosts, final score/reasons, pre-access count. Memory identity helpers expose internal ID and existing `dataset_memory_id`, `source_id`, `dataset_id`, `locomo_id`, `original_id` metadata where supplied. Core does not invent/validate a dataset mapping. Configured/custom scorer explanations are not independently verified by the default lexical diagnostic helper.

## Privacy and cost

Phase A preserves the existing content_preview key but redacts its value by default. Explicit opt-in:

```python
from mneno import MemoryClient
from mneno.observability import TraceRecorder

recorder = TraceRecorder(include_memory_content=True)
client = MemoryClient(trace_recorder=recorder)
```

This is a deliberate safer default: consumers expecting plaintext previews must opt in. It does not alter result content or storage. Structured credential keys and nested credential-like fields are redacted by the existing sanitizer; provider configuration is never dumped. Queries, matched terms, reasons, source IDs, user-supplied metadata, session titles, and other operation messages can still contain sensitive text. Redaction is not a general secret detector. Only controlled synthetic content was used in these reports.

Normal execution omits trace recording and now skips major unnecessary lexical recomputation for score-event construction, zero-relevance/result decision loops, and context diagnostic loops. Detailed tracing still records O(N) diagnostics, repeats some score metadata, copies event lists on append, and has no event/retention bound. Stage ID arrays are O(N); the 10k synthetic trace is ~31 MB. Clear traces between benchmark operations. [Performance](PERFORMANCE_BASELINE.md) quantifies overhead; no unmeasured claim of cheap detailed tracing is made.

## Failure categories an external evaluator can infer

| External category | Core evidence | Remaining qualification |
| --- | --- | --- |
| CANDIDATE_GENERATION_MISS | Expected ID absent from initial_candidate_ids | Current engine scans all stored records; absent evidence usually ingestion/ID mapping/store-state issue, not a lexical index miss |
| LIFECYCLE_FILTER_EXCLUSION | Initial ID absent from post_filter_candidate_ids; flags and prior store lifecycle snapshot | Search has exclusion IDs; context derives difference; exact per-record lifecycle predicate/reason must be joined to source snapshot |
| INITIAL_RANKING_MISS | Complete initial ranking vs cutoff/selection | Distinguish zero-relevance eligibility exclusion (rank None); before reranking there is no candidate cap |
| RERANKING_MISS | used True plus input/output arrays, final result decisions | Disabled reranker has empty arrays explicitly; do not label an absent stage a reranking failure |
| CONTEXT_BUDGET_EXCLUSION | context_item_excluded reason “budget exhausted”, estimated tokens and policy/stats | Other policy exclusions are separate; excluded records can precede later smaller included records |
| EVIDENCE_MAPPING_ERROR | Stored external identity metadata and external ingestion manifest | Core cannot prove expected evidence-ID mapping; Bench must own validation of external/internal IDs |
| EXTERNAL_PROVIDER_FAILURE | operation_failed error_type, last completed stage, provider booleans | Raw provider exceptions can be arbitrary types; no standardized provider_status success/failure envelope or exact active-failure stage yet |
| UNKNOWN | Incomplete/unsupported trace, custom component decisions, unresolved mapping | Do not infer missing stages from absent fields in older traces |

## Explicit missing observability

No separate query_id field is needed when Bench stores trace linkage, but Core cannot attach a benchmark-specific ID for it automatically. Per-stage perf_counter timings are not implemented: event timestamps and total duration provide only coarse chronology, and some events are retrospective. Reference_time None means per-memory wall time remains implicit; choose a fixed value for exact replay. Provider name/config is not fully normalized in effective config; selected rerank results contain provider names. Context failure during provider scoring/reranking lacks a dedicated provider-stage event. Non-retrieval operation exceptions can still leave running traces. Retention/event bounds, complete secret redaction, per-lifecycle reason events, and custom-scorer diagnostic contracts remain explicit follow-ups.

Executed tests: `tests/test_observability.py`, `test_evaluation.py`, and Phase A stage/result consistency, default preview privacy, failed trace completion, fixed-time replay. Both search/context disabled-reranker cases serialize to valid JSON. Existing reranking suites verify rank/score/provider metadata; no real provider/network test was run.
