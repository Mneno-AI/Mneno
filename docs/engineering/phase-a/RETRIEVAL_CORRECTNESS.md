# Retrieval correctness and reproducibility

## Completion assessment — 0.5.0

The mixed-timezone blocker A-12 is repaired: `_time.as_utc` compares naive-as-UTC and aware-as-UTC instants without rewriting
stored representations. Search/context preserve existing score and ID tie keys; existing semantic, session, timeline,
compaction, hierarchy, SQLite ordering, CLI, and trace-duration comparisons use the same convention. Offset/legacy/reopen
and malformed-input tests passed. Fixed persisted state, reference time, configuration, and deterministic providers
remain required: searches still record access and ordinary wall time still advances.

A-10/A-11/A-13/A-18 are also closed through structural import mapping, explicit staged transactions, retained compaction
history, and safe JSON writer coordination. Default inactive filtering/conflict warnings remain intact. Compaction stats
now describe its eligible view; physical records include archived sources. Custom import/restore/compaction stores need
atomic capability. Historical dangling links are preserved with `ImportResult.warnings`; known membership contradictions
reject the batch. Storage envelopes remain unchanged.

All three prior xfails now pass as normal tests. Full validation: **569 passed, 0 failed/skipped/xfailed**.
[DATA_INTEGRITY_HARDENING.md](DATA_INTEGRITY_HARDENING.md) records fault boundaries, tests, compatibility and release gates.
No scoring formulas, weights, normalization, or retrieval algorithms were changed.

## Initial correctness report — historical 0.4.1

The following assessment and coverage counts describe the pre-completion audit. Its timezone/import/transaction blockers
are retained as historical evidence and superseded above.

## Verdict

Default local retrieval is explainable and uses stable ID tie-breaking. A fixed saved state, fixed scoring time, fixed policy/session configuration, and deterministic providers reproduce IDs and scores. Unconditional determinism is **not certified**: mixed timezone records fail tied sorting (A-12), queries update access state, and custom providers may be nondeterministic. No scoring weight, lexical normalization rule, or retrieval algorithm was changed.

## Effective configuration

| Entry point | Defaults and overrides | Selection semantics |
| --- | --- | --- |
| SDK `MemoryClient.search` | limit 10; semantic/reranker None -> configured provider; explicit False disables, explicit True without provider errors; both inactive flags False; current_session_id falls back to client active ID | Full visible scan; score + session boost; zero relevance excluded unless reranker used; full ranking then limit |
| CLI search | limit 5; --include-inactive/--include-archived/--session; JSON/reasons options | Same SDK engine; JSON-backed fresh client without providers or tracing |
| SDK build_context | policy > budget > preset; balanced default; no candidate limit; same visibility/session flags | Separate ContextBuilder; provider-configured scorer/reranker enabled; no per-request disable switches |
| SDK explicit int budget | min_score .05, reserve 0, score strategy, dedupe True, no max_items | Bypasses preset defaults |
| CLI context | budget 1200 default, balanced preset; builds custom preset policy with budget override and reserve **0** | Different from SDK balanced reserve **200**; min_score/max_items inherited from preset |
| `SemanticRetriever.rank` | optional top_k, positive if supplied; embedding provider mandatory | Separate utility, not SDK search path; similarity + layer clamp then layer/date/ID tie keys |
| `RerankingEngine.rerank` | top_k None = every candidate; absent provider leaves input unchanged | Provider index ordering, omitted candidates appended; preserve score objects, attach rank/provider metadata |
| `evaluate_search` / `evaluate_context` | Wrap corresponding SDK arguments | Time operations, expose selected/candidate/trace counts; Phase A fixes archived-only count mismatch |

`MemoryPolicy` defaults: importance .5; scoring weights recency .15, importance .20, access .10, relevance .50, freshness .05; half-life 30 days; freshness decay 180 days. `max_context_memories=20` exists but does not cap search/build_context: ContextPolicy controls actual context caps. No environment variables tune retrieval. Layer/status/session constants and continuity limit 5 are implicit fixed implementation settings; effective trace config exposes resolved policy/provider booleans/current and related session IDs and scoring time, not a new configuration framework.

Presets (`context/presets.py:get_context_policy`):

| Preset | Max/reserve/available | Min score / max items | Strategy / preservation |
| --- | --- | --- | --- |
| cheap | 400/100/300 | .35/5 | score, dedupe |
| balanced | 1200/200/1000 | .15/15 | score, dedupe |
| high_recall | 2500/300/2200 | .05/40 | score, dedupe |
| agent_state | 1000/200/800 | .10/20 | importance, preserve operational/preference, dedupe |

## Replaying a saved state

```python
from datetime import UTC, datetime
from mneno import MemoryClient
from mneno.scoring import TemporalMemoryScorer
from mneno.storage import JSONFileStorage

scorer = TemporalMemoryScorer(reference_time=datetime(2026, 1, 1, tzinfo=UTC))
client = MemoryClient(storage=JSONFileStorage("isolated-replay.json"), scorer=scorer, trace_enabled=True)
results = client.search("Python", use_semantic=False, use_reranker=False)
```

`reference_time` is additive and optional; None preserves wall-clock aging. A naive reference time is interpreted as UTC, consistent with scoring's existing naive-memory interpretation. `calculate_memory_score` accepts the same optional keyword. Capture/restore original access counts or reload an isolated original snapshot between operations; do not compare a second search on a mutated live state as an identical experiment. The configured default ContextBuilder shares this scorer. Trace IDs, timestamps, durations, UUID creation, export timestamps, and last_accessed_at are not byte-identical replay fields.

Search ordering is descending `(total, current_session_match, updated_at, memory_id)`. Context score strategy is descending `(total, layer_priority, updated_at, memory_id)`; recency/importance strategies deliberately use different first keys. Stable ID tie-breaking is present; unify these keys only if a later behavior requirement demands it. Session boosts use mutually exclusive current/related paths; active missing/unknown session ID in retrieval simply finds no match, while add with unknown session raises KeyError.

## Visibility and trust

Both public retrieval entry points exclude superseded and archived status plus archived layer by default. include_archived restores archived memories/layers while still excluding superseded; include_inactive restores all. Conflicted records stay eligible with reasons/warnings. Zero relevance does not become positive merely because a session boost exists. Reranking intentionally disables the zero-relevance gate, changing candidate eligibility as well as order.

Phase A repairs operational automatic supersession, near-duplicate precedence over recognized contradiction, verified-metadata update intent, externally supplied supersession reports without intent, and conflicted compaction deletion. Explicit correction remains supported. Sources and reciprocal links persist across JSON/SQLite reopen. Budget-limited context may still omit conflict evidence explicitly; no promise is made that every linked record always fits.

Ordinary compaction and append-collision imports remain history/relationship blockers. Hierarchy can still archive stale conflicted records according to explicit layer policy. Heuristic update cues are not independent verification of source authority; memory contents remain untrusted claims.

## Boundary evidence matrix

| Condition | Evidence | Assessment |
| --- | --- | --- |
| Empty store | `tests/test_scoring.py`, `test_context.py`, CLI empty-workspace suites | Controlled empty results/packages |
| Empty query | SearchMemoryRequest min_length; CLI blank query tests; context allows empty query | SDK search empty string errors; whitespace search yields no local relevance; CLI rejects both; context empty remains supported |
| Duplicate content | conflict duplicate tests, context dedupe tests, Phase A equal-score test | Search retains duplicates; context defaults dedupe; contradictions checked before near-duplicate fallback |
| Equal ranking | Phase A `test_equal_scores_stable_across_backends`, fixed-time replay | IDs/order and scores verified across all backends; context ordering test explicitly disables dedupe |
| Missing metadata | `tests/test_models.py`, Phase A boundary memories without metadata | Safe model defaults; absent external evidence mapping remains evaluator responsibility |
| Long/Unicode/special query | Phase A `test_query_boundaries_and_json_results` | No crash, parseable results, tiny estimated budget honored; **does not certify multilingual relevance** |
| Large collection | Executed performance baseline 100/1k/10k, script result-count assertions | Full scan supported, no synthetic recall claim |
| Archived/superseded | `test_conflicts.py`, `test_hierarchy.py`, archived-only evaluation-count regression | Default exclusions and explicit inclusion tested |
| Conflicting/corrected | `test_conflicts.py`, Phase A persisted operational/preference/verified/report tests | Both sides visible with warnings absent update intent; explicit changed-to correction tested |
| Session absence/cross-session | `tests/test_sessions.py`, `test_cli_search.py`, `test_cli_context.py` | Current-session and continuity defaults exercised; A-20 continuity visibility limitation remains |
| Small budget/max_items/dedupe | `tests/test_context.py`, Phase A boundary tests | Greedy content word-estimate enforcement; not full formatted/model token enforcement |
| Zero/negative limit | Existing search request tests; Phase A context tests | Positive search and optional context limits validated |
| Corrupted persisted records | `tests/test_storage.py`, `test_io.py`, future SQLite schema regression | Invalid JSON/model/envelope errors; incomplete identity/reference integrity validation remains A-22 |
| After update | `tests/test_storage.py` update/get/search behavior, Phase A JSON failed-write test | No vector cache/index to invalidate; new content is read from authoritative store |
| Trace/result serialization | observability/evaluation/CLI suites and Phase A stage tests | Public IDs/ranks/scores stable; new private context attributes excluded from dump |

## Changes and limits

Every meaningful Phase A fix has focused regression coverage in `tests/test_phase_a.py`; the operational-change fixture in `tests/test_conflicts.py` now supplies explicit changed-to intent. Three unresolved desired-behavior regressions are **strict xfails**: append relationship mapping (A-10), replacement failure atomicity (A-11), mixed-timezone sorting (A-12). They are visible blockers, not passing tests or quietly skipped requirements.

The historical LOCOMO values supplied in the request were not reproduced; no benchmark questions/datasets or NVIDIA provider were used. Phase B must first close integrity/replay blockers, then evaluate retrieval quality with snapshots, fixed time, exact configuration, and external-ID mapping.
