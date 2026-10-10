# Phase A engineering summary

## Completion milestone — 0.5.0

**Phase A Core: PASS. Phase B readiness: GO for controlled local retrieval experiments.
Release readiness: READY for review and the existing release workflow; not published.**

All five P0 blockers are resolved within the documented built-in storage contracts. Imports/restore and compaction use
staged atomic transactions; append collisions remap structural relationships; JSON coordinates cooperating writers and
rejects stale snapshots; compaction retains archived history; mixed datetime comparisons use UTC instant keys.
The three former strict xfails are ordinary passing regressions. Final checks: **569 passed, 0 failed, 0 skipped,
0 xfailed**, Ruff/format/mypy (93 source files), sdist/wheel, and installed-wheel SDK/CLI/version/upgrade smoke checks.

Version **0.4.1 → 0.5.0** reflects archival-count semantics and the required custom-store atomic batch capability.
JSON/export v1 and SQLite v2 remain readable without migration. Scoring formulas/weights and public retrieval schemas are
unchanged. No Bench changes, provider/model calls, retrieval algorithm, runtime dependency, or package publication.

[DATA_INTEGRITY_HARDENING.md](DATA_INTEGRITY_HARDENING.md) is the current completion evidence, exact validation commands,
backend guarantee matrix, compatibility guidance, remaining P1/P2 risks, and Phase B experiment recommendation. Supported
precommit failures preserve state; JSON post-rename sync errors explicitly report `committed=True`, not a fictitious
rollback. Windows/Linux/multiple-Python checks and actual power-loss tests remain unexecuted locally.

## Initial Phase A audit — historical 0.4.1 report

The following verdict/results describe the initial audit at `ffa0950`, before this completion milestone. Its open-blocker
statements and 455/3 test counts are historical, superseded by the evidence above.

## Executive verdict

**Phase A Core: PARTIAL. Phase B readiness: NO-GO for retrieval-engine changes.**

The repository now has a source-backed architecture/configuration audit, repaired trust/storage/diagnostic defects, replay controls, focused regressions, agent/CLI/package checks, and a bounded local performance baseline. Existing ranking formulas, weights, public result schemas, and storage envelopes are preserved. An unconditional PASS would be misleading: append-collision relationships, replacement failure atomicity, and mixed-timezone replay remain executable blockers. Compaction historical preservation and multi-writer JSON safety also remain source-confirmed risks.

This verdict permits focused stabilization follow-ups; it does not endorse adding a new retrieval engine before those prerequisites close. No Mneno-Bench changes, external model calls, benchmark-data modifications, new runtime dependency, retrieval algorithm, provider integration, cloud service, or CLI redesign occurred.

## Verified architecture

- Three built-in stores: in-memory dicts, whole-document cached JSON, JSON payloads in SQLite v2. All retain memory/session models; no lexical/vector index exists.
- Lifecycle/conflict/hierarchy are local heuristics and auditable model transitions. Explicit update intent is required for supersession. Conflicted evidence remains retrieval-eligible and is now protected from destructive compaction.
- SDK search scans visible memories, scores every candidate, applies session boosts, excludes zero relevance unless reranking, stable-sorts, optionally reranks all candidates, applies final limit, and persists access updates.
- Context is a separate strategy/policy pipeline; optional reranking precedes candidate limit/dedupe/min-score/max-items/content-word budget. SDK/CLI defaults differ and are documented.
- Scoring is weighted lexical/recency/importance/access/freshness, existing optional semantic max, then layer/status/session adjustments; no weights were tuned.
- Tracing remains optional local memory with v1 JSON exports. Stage IDs/config, score diagnostics, final decisions, and failed retrieval status now provide a documented evaluator interface.
- Typer CLI has eight commands plus version/help/completion options. Five shipped agent templates install local Markdown/skill references with overwrite refusal and safe CLI dry-run.

See [architecture audit](ARCHITECTURE_AUDIT.md) for actual symbols/call paths, formulas, storage contracts, module boundaries, packaging/dependencies/workflows, and developer-facing surfaces.

## Implemented changes and compatibility

| Files | Problem / implementation | Regression coverage | Compatibility impact |
| --- | --- | --- | --- |
| `mneno/conflicts/detector.py`, `resolver.py`; `tests/test_conflicts.py` | Operational claims needed correction intent; recognized contradictions were hidden by near-duplicate precedence; verified metadata/unchecked reports could supersede. Require intent, check contradictions first, recheck report intent | Persisted operational/preference contradictions; long negation; explicit changed-to; verified-only metadata; supplied report | Safer lifecycle outcome for unjustified supersession; existing explicit correction works; fixture now supplies actual intent |
| `mneno/compaction/engine.py` | Preserve conflict evidence through merge/discard/cap; copy source metadata lists during preview | Across backend/reopen and aggressive reduction; preview mutation test | Unresolved evidence can exceed max_memories intentionally; unaffected duplicate compaction remains supported |
| `mneno/client.py` add/compact | Insert new records before changing/deleting old records | Failed correction/compaction insertion preserves sources | Same success return types; partial multi-operation failures not certified atomic |
| `mneno/storage/memory.py`, `json_file.py`, `sqlite.py` | Reject in-memory ID overwrite; restore committed JSON cache on disk/serialization failure; clean deleted session membership; refuse future SQLite schema | Backend parity, failed JSON later write, serialization fault, future version | Existing storage envelopes unchanged; explicit update remains replacement path; newer databases refuse safely |
| `mneno/io/importers.py` | Validate complete replacement and duplicate IDs before clearing | Invalid memory/session/duplicate input across stores | Invalid replace raises and keeps original; append/other partial-success modes retained; valid failure atomicity remains blocker |
| `mneno/context/builder.py`, `package.py` | Reject nonpositive limit; retain private initial/reranker stage IDs | Limit tests; enabled/disabled rerank stage tests; private-field serialization check | Positive/None limit behavior and public schema unchanged |
| `mneno/scoring/temporal.py` | Optional fixed reference_time; use one clock value per score | Saved-state exact-score replay across stores | Additive keyword; default wall-clock decay and all formulas unchanged |
| `mneno/client.py` retrieval/evaluation | Effective config and complete stage IDs; finish failed retrieval traces; skip major inactive tracing recomputation; correct archived-only evaluation counts | Stage/result consistency, reverse local reranker, provider-error privacy, invalid retrieval completion, evaluation visibility | Trace additions only; existing SDK result types preserved |
| `mneno/observability/recorder.py` | Redact content previews unless include_memory_content=True | Default/opt-in trace JSON privacy | Deliberate safer default for preview content; existing key/type preserved; other sensitive text still possible |
| CLI `validation.py`, commands search/context | JSON blank-query error is parseable | CliRunner both commands, exit 1 | Existing JSON success schemas/commands unchanged; conventional Typer parse errors remain stderr |
| Public docs; `README.md`; engineering reports | Correct stale weights/context/storage descriptions; document new controls and limitations | Code snippet formatting via Ruff; source correspondence review | README change is only required code-block formatting under installed Ruff |
| `scripts/phase_a_baseline.py`, raw JSON | Reproducible bounded local measurements and assertions | Script executed twice; dataset/result-count/trace-status checks | Development-only artifact; no runtime dependency or SDK change |

All focused regressions are in `tests/test_phase_a.py`. It adds **54 passing cases and 3 strict expected-failure cases** to the 401 existing cases. Expected failures explicitly expose A-10/A-11/A-12 and are excluded from passing evidence.

## Remaining prioritized issues

**P0:** A-10 append collision reference remapping; A-11 atomic replacement/restore; A-12 timestamp-comparison normalization; A-13 non-conflicted compaction history/batch safety; A-18 JSON concurrent snapshots/writers. Three have executed strict xfail regressions; the latter two are source-confirmed architectural limitations. They require separate focused semantics/transaction work and are explicitly Phase A blockers rather than silently deferred readiness criteria.

**P1:** mutable cached models, continuity inactive visibility, content-only word budgeting, malformed identity/reference consistency, optional provider output validation, large detailed trace retention, some CLI human-output/error paths. Correctness scope and remediation evidence appear in [technical debt](TECHNICAL_DEBT.md).

**P2:** measured repeated scans/deserialization/access writes, optional lexical candidate index experiments, multilingual lexical normalization, session-bias studies, trace-cost optimization. No historical LOCOMO result was assumed reproducible or used as a tuning target.

## Executed validation

| Command | Suite / outcome | Passed | Failed | Skipped / expected failures | Warnings / qualification |
| --- | --- | ---: | ---: | --- | --- |
| `scripts/check.sh` initially | Stopped before tests: Ruff unavailable | — | Tool setup | — | Default system Python 3.9.6 below supported minimum |
| `.phase-a-venv/bin/pytest -q --ignore=tests/test_phase_a.py` initially | Existing suite before environment PATH correction | 400 | 1 | 0 | Demo failed because CLI executable absent from PATH; resolved with supported venv PATH |
| `.phase-a-venv/bin/pytest -q tests/test_phase_a.py` initial exploratory regressions | Pre-fix assertions | 12 | 22 | 0 | Includes 3 invalid test assumptions about context deduplication; corrected to explicit dedupe=False |
| `PATH="$PWD/.phase-a-venv/bin:$PATH" scripts/check.sh` intermediate | Ruff, format, mypy, pytest | 443, then 448, then 450 | 0 | 0 | Repeated only following actual changes; no pytest warnings printed |
| `scripts/check.sh` final supported `.venv` | Ruff lint + format, mypy (91 package files), all pytest suites | **455** | **0** | **0 skipped; 3 strict xfailed** | **No pytest warnings printed**; 458 total collected |
| `PATH="$PWD/.venv/bin:$PATH" python -m build` | Isolated Hatchling sdist and wheel | Build succeeds | 0 final | — | First build accidentally included audit-created temporary venv symlink; moved to standard ignored .venv, removed only audit-created environment, reran successfully |
| `PATH="$PWD/.phase-a-venv/bin:$PATH" python scripts/phase_a_baseline.py > docs/engineering/phase-a/performance-results.json` | Final recorded performance run | Assertions succeed | 0 | JSON 10k deliberately omitted | Script can now be rerun with `.venv/bin/python`; temporary phase venv removed |
| Installed-wheel isolated smoke via `.venv/bin/python` and `/tmp/mneno-phase-a-uv` | SDK add/search, template sources for all 5 agents; executable --version/init/status --json/setup-agent codex --dry-run | All assertions/exit checks succeed | 0 | — | Installed wheel tested from a temporary cwd outside checkout; no live third-party agents started |
| `git diff --check` | Whitespace/diff check | Clean | 0 | — | Initial clean working tree recorded; changes restricted to this repository |

Lint/format initially found a pre-existing README code-block formatting mismatch under Ruff 0.17.0; only those lines were formatted. Dev tools were installed from existing declared extras, with Python 3.11.17 downloaded through uv. Core never called an external provider. Python 3.12/3.13 CI jobs, Twine checks, Mintlify preview/link checking, real agent discovery, all OS variants, and external datasets were not executed. Build distribution smoke is not a substitute for the full CI matrix.

## Performance evidence

Five measured calls after warm-up per search/context/traced-search distribution; representative synthetic sizes 100/1k/10k. Final medians (milliseconds):

| Backend / size | Search | Context | Detailed traced search |
| --- | ---: | ---: | ---: |
| In-memory 100 | 1.43 | 1.61 | 6.06 |
| In-memory 1,000 | 14.78 | 15.82 | 67.28 |
| In-memory 10,000 | 176.60 | 195.47 | 1,105.80 |
| SQLite 10,000 | 554.42 | 425.45 | 1,492.87 |
| JSON 1,000 | 114.08 | 160.21 | 162.40 |

[Performance baseline](PERFORMANCE_BASELINE.md) includes full distributions, insertion observations, allocation estimates, trace sizes, host/runtime, raw samples and limitations. Model construction memory is not whole-process RSS. Baseline includes access persistence; it does not measure relevance quality or reproduce historical LOCOMO metrics.

## Core / Bench interface requirements

Bench should consume SDK MemorySearchResult ordered IDs/full scores/rank/rerank metadata, ContextPackage included/excluded IDs and reasons/policy/stats, and v1 trace/benchmark envelopes. Bind external query IDs to returned trace IDs; store an ingestion manifest of internal IDs to evidence IDs. Candidate lists, pre/post lifecycle IDs, initial ranking, reranker input/output, final result IDs and context decisions now allow supported-stage diagnosis. No Core dataset-specific failure classification exists.

Use identical saved states, fixed reference_time, actual resolved policy/session/providers, and explicit inactive flags. Account for pre-score vs post-access state and independent search/context defaults. Disabled reranker arrays are empty by contract. Do not count lifecycle exclusions as ContextPackage exclusions. Unknown fields/events must remain tolerated. Bench owns expected evidence mapping and task-specific metrics; no Bench files were modified.

Missing fields: precise stage timings, comprehensive provider-status/failure-stage labels, complete custom-scorer diagnostics, per-memory lifecycle exclusion reasons, and bounded retention. Do not infer unobserved failures from old/missing events. See [tracing contract](RETRIEVAL_TRACING.md).

## Definition-of-done evidence

| Criterion | Status / evidence |
| --- | --- |
| Architecture / real retrieval path / effective configuration | Complete: source inventory, pipeline/formulas, API/default differences |
| Determinism / stable result IDs | Partial: fixed-time valid-state replay and ID tie tests pass; mixed timezone/malformed identity remain blockers |
| Lifecycle / explicit correction / contradiction invariant | Passing regressions for default supported claims across storage; compaction/history/import limitations remain explicit |
| Storage consistency | Assessed and narrowly repaired; atomic replacement, relationship mapping, concurrent JSON remain blockers |
| Context selection / budget | Estimated content budget validated; model/formatted token limits not certified |
| Trace reconstruction / external diagnostic contract | Complete for documented supported stages; exact missing fields/costs/privacy documented |
| SDK / CLI / setup | Existing suites plus installed-wheel SDK/templates/CLI smoke pass; live agent hosts not executed |
| P0 defects | Repaired where narrowly scoped; five unresolved limitations explicitly marked blockers, three strict xfails |
| Regression tests / checks / build | 455 passed, 3 xfailed, lint/format/mypy/build successful |
| Performance baseline | Executed with raw data/methodology/limitations, feasible sizes only |
| Scope boundaries | No new retrieval algorithm, dependencies, external models, Bench or other repo modifications |
| Six reports / readiness recommendation | Complete: all six requested reports and NO-GO prerequisites |

## First recommended Phase B task

First close **atomic replacement and structural ID remapping** in focused compatibility-tested work; normalize timestamp comparison semantics before benchmarking. Define compaction history preservation and single-/multi-writer backend guarantees alongside those fixes. Keep storage/result envelopes stable and add fault-injection/backend-parity tests.

Then the first concrete efficient-local-retrieval task is a **stage-cost profile and candidate-coverage experiment on SQLite** using frozen snapshots and time. SQLite FTS5/BM25 is appropriate to evaluate because SQLite is present and full scans/deserialization cost ~0.55 seconds at 10k in this run. It is not yet justified as the automatic replacement: verify FTS5 support, Unicode/token/query semantics, lifecycle filters before candidate cutoff, stable tie IDs, update/delete/import synchronization, context preservation/limits, provider-stage inputs, and fallback behavior. Candidate pruning must retain explainability and adequate coverage before comparing latency or external recall. It will not fix JSON write amplification or trace-memory growth.
