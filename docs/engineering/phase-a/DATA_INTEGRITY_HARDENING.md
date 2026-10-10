# Phase A data integrity hardening — 0.5.0

## Verdict and scope

**Phase A Core: PASS. Phase B readiness: GO for controlled local candidate-retrieval experiments.
Release readiness: READY for review and the existing release workflow, not published.**

A-10, A-11, A-12, A-13, and A-18 are closed for the documented built-in backend contracts. No unconditional guarantee is
made for custom implementations, noncooperating filesystem writers, power failure on arbitrary filesystems, or every
multi-call SDK operation. The current code introduces no retrieval algorithm, weight change, runtime dependency,
provider integration, storage envelope migration, or Mneno-Bench modification.

Discovery recorded a clean working tree on `phase-a-core-stabilization`, commit
`ffa0950` (`Stabilize core trust, persistence, and retrieval diagnostics for Phase A`). Starting package version: `0.4.1`.
Root `AGENTS.md`, `CONTRIBUTING.md`, documentation instructions, prior Phase A reports, storage protocols/models,
import/compaction callers, and their tests were inspected. This milestone keeps the target branch and published history.

## Minimal transaction contract

[`storage/transactions.py`](../../../mneno/storage/transactions.py) adds the optional, runtime-checkable
`AtomicMemoryStore` capability without enlarging the existing `MemoryStore` protocol. `transaction()` yields an isolated
store; callers mutate that yielded store. Normal exit validates and commits the complete memory/session snapshot once.
An exception before commit leaves the original committed state unchanged. Same-instance original-store mutation/nested use is rejected
on the in-memory/JSON implementations; SQLite callers must also use the yielded store rather than open another writer.

`atomic_transaction()` requires this capability before mutation. Unsupported custom stores raise `TypeError` for all
import modes, restore, and compaction. Individual custom-store add/get/search usage remains available. A custom backend
must actually implement isolation and rollback; structural protocol membership cannot certify its implementation.

This is deliberately a snapshot transaction, not a general transaction framework. Built-in batch operations stage all
memories and sessions. SQLite deletes/reinserts that snapshot inside one transaction. JSON rewrites the entire document.
These costs prioritize correctness; row-level write tracking and indexing are deferred.

## Backend guarantees

| Property | In-memory | JSON | SQLite | Custom stores |
| --- | --- | --- | --- | --- |
| Individual writes | Cooperating API calls serialized on instance `RLock` | Each mutation is a staged snapshot transaction | Existing statement transactions, including delete/session cleanup | Existing implementation's contract |
| Logical batch | Validated isolated maps swapped under lock | One complete staged snapshot, atomic rename | `BEGIN IMMEDIATE`, memory and session rows, one commit/rollback | Required explicit `transaction()` capability; otherwise rejected before mutation |
| Concurrency | Cooperating threads on one instance; separate stores are independent | Stable sidecar OS lock + SHA-256 snapshot revision; stale writes raise `StorageConflictError` | SQLite serializes batch writers; competing writes obey SQLite locks/timeouts | Must be documented and tested by implementer |
| Precommit failure | Original maps preserved, lock released | Original file/cache preserved; unique temp removed on ordinary failure; lock released | Rollback restores deleted/inserted rows and sessions | Capability must guarantee rollback |
| Restart/process exit | No process persistence | Last atomically published file is readable; OS lock released on process exit | SQLite journal/transaction recovery | Backend-specific |
| Crash durability | None | Temp file fsync before rename, parent fsync after rename on POSIX; filesystem/hardware limits apply | SQLite's existing default journal/synchronous settings; no new universal hardware guarantee | Backend-specific |
| Relationships | Import remapping/validation and compaction lineage staged with records | Same, persisted in envelope v1 | Same, persisted in schema v2 | Import logic validates; persistence guarantee belongs to capability |

### JSON commit and concurrency boundaries

[`JSONFileStorage._locked/transaction/_write`](../../../mneno/storage/json_file.py) locks a stable `<filename>.lock`
resource rather than the replaceable data inode. Paths are resolved so symlink aliases share the resource. POSIX uses
`fcntl.flock`; Windows uses `msvcrt` byte-range locking. No third-party runtime dependency is added. Lock files persist
and must not be removed while clients run. Windows contention can time out with a storage error.

The lock covers revision comparison, reload, staging, validation, serialization, temporary-file write/sync, rename, and
cache update. Reads reload under that lock. Two clients starting from one snapshot cannot silently overwrite each other:
a stale writer raises `StorageConflictError`. Read the latest snapshot, recompute the intended operation, then retry.
Standalone `update()` is still explicit whole-model replacement; use a staged transaction to derive updates from a
current record. Revision rejection is not automatic merging or a per-record version token.

**Rename is the commit boundary.** Every tested precommit failure preserves state A. After successful rename, the
complete B is committed. If parent-directory fsync fails, `StorageCommitError(committed=True)` reports that B is visible
but power-loss durability is uncertain. Callers must inspect state rather than assume A or blindly retry. Compaction's
failure trace also records `committed`, created IDs, and source IDs. Claiming rollback after successful rename would be
false. Postcommit directory-close errors also report `committed=True`. Windows has no portable directory fsync here. Advisory locks do not coordinate manual editors/noncooperating
writers; network-filesystem locking/rename behavior and sudden machine power loss were not certified.

An abrupt exit before rename may leave an unreferenced unique temporary file; it cannot become a committed snapshot on
a later write. The process-exit test verifies automatic lock release and preservation of the committed file.

## P0 closure evidence

### A-11 — atomic replacement/import/restore

Root cause: prevalidation was followed by `clear()` and individually committed inserts. A later write could lose A.
`io/importers.py:import_memories_from_payload` now parses before mutation and applies accepted records through one
transaction. In-memory stages a copied implementation and validates before the map transition. JSON publishes one
validated snapshot. SQLite `_replace_snapshot` runs inside one write transaction including sessions. Unsupported custom
stores fail before clear; no compensating-write rollback is attempted.

Evidence: original `test_replacement_storage_failure_preserves_original` now passes unchanged apart from removal of its
xfail marker. `test_replacement_repeated_and_reopened`, `test_transaction_rolls_back_after_multiple_staged_mutations`,
`test_transaction_revalidates_mutated_models_before_commit`, `test_sqlite_rollback_after_first_persistent_insert`,
`test_sqlite_real_constraint_failure_rolls_back`, JSON precommit/partial-write/sync/close tests, and custom-store rejection cover
validation, staged failure, actual SQL partial writes, file failure, cache ownership, lock release, success, and reopen.
**Closed**, subject to the explicit postcommit durability-error distinction above.

### A-18 — JSON independent/concurrent writers

Root cause: instance-local cached maps plus one shared temporary filename overwrote newer committed snapshots.
Revision checks, stable sidecar locks, refreshed reads, isolated staging, and unique temporary files replace that path.

Evidence: independent stale writers and session updates reject explicitly; two barrier-synchronized threads produce one
commit/one conflict. Two spawned processes execute eight synchronized rounds each, retrying after explicit conflicts;
all 16 memory/session pairs survive reopen with valid memberships and parseable JSON. Process exit before commit
preserves the original snapshot and releases the lock. File-sync, rename, serialization, and partial-temp-write faults
leave the committed snapshot intact and allow later writes. Symlink and same-instance reentrancy tests cover alias locks
and deadlock prevention. CLI JSON regressions verify that conflict errors follow the existing OSError path. **Closed** for cooperating local writers; SQLite remains preferred for concurrent applications.

### A-10 — collision and structural remapping

Root cause: memory/session identities were regenerated independently during insertion without rewriting references.
`_id_mapping` reserves all existing/incoming IDs before insertion. Append then rewrites memory IDs, primary session IDs,
session membership lists, `conflicts_with`, `superseded_by`, audit `related_memory_ids`, and the compaction-source
`metadata.source_memory_ids` convention. There are no separate parent/child/hierarchy graph IDs in the current model.
Opaque dataset/provenance IDs, audit conflict IDs, content, and arbitrary metadata are not rewritten.

No-collision imports keep IDs. Collisions use production UUIDs, with reserved-ID checks. Duplicate IDs within a payload
are rejected before commit. Self/cyclic references map together, including supported legacy empty-string IDs. References outside the incoming batch retain their
original IDs. Known inconsistent session membership rejects the entire batch; missing reverse membership is reconciled.
Legacy dangling historical links remain readable/importable with additive `ImportResult.warnings`; they are not erased
or fabricated. Malformed compaction lineage rejects safely. Invalid individual non-replacement items still contribute
`failed_count/errors`; all accepted items commit together. Runtime storage failure rolls back the accepted batch.

Evidence: original `test_append_collision_remaps_session_membership` now passes; parametrized memory/session/both/no
collision tests run on all backends with predictable UUID injection. Further tests cover repeated imports, lineage,
external references, dangling warnings, duplicate IDs, known inconsistencies, late session failure, and reopen.
**Closed**. Warnings preserve legacy evidence; they do not certify a historically closed relationship graph.

### A-13 — historical, atomic compaction

Root cause: source deletion lost audit/session/lifecycle provenance; multiple writes lacked one logical commit.
`MemoryClient.compact` now stages result creation, session updates, and source archival in one transaction. Sources retain
ID, content, metadata, source, prior audit, conflict/supersession fields, creation date, session membership, and sequence.
A `compaction_archived` audit event records time, reason, original status/layer/update time, effective policy, and resulting
ID. Results include source IDs and a `compaction_created` audit event with policy/time. Same-session results receive a new
sequence after the entire session; cross-session results retain lineage without inventing a primary session.

The engine only compacts the eligible active/conflicted view, excluding archived layers and superseded records. Conflicts
and one-sided conflict targets bypass merging/discard/caps. Repeated compaction does not recompact archived sources.
`discarded` remains the public decision label but means exclusion from the active view by archival. `list/get`, timelines,
backup/export retain history; default search/context continue excluding archives. Diff counts refer to the eligible view,
not physical rows. This is an intentional 0.5.0 compatibility change, not an attempt to pretend old deletion tests pass.
Those tests now assert the smaller active view **and** retained historical records.

Evidence: original failed-insert/trust tests, backend-parametrized history/session/reopen/visibility/repeat tests,
multi-group success/discard tests, first/later transition failure, commit failure after staging, cross-session history,
whole-session sequence, one-sided conflict protection, and postcommit JSON error trace tests. Commit events/mutation
traces are emitted only after commit; precommit failures end the trace with error without claiming successful mutation.
**Closed**. Compaction reduces active context rather than disk usage; archive retention management is deferred.

### A-12 — consistent datetime comparisons

Root cause: direct datetime tuple comparisons encountered mixed naive/aware values; SQLite text ordering was not instant
ordering. `_time.as_utc` interprets legacy naive dates as UTC and converts aware comparison keys to UTC. It does not mutate
stored timestamps. At datetime year-range boundaries where UTC conversion overflows, it retains the aware value;
Python aware comparison/subtraction still compares the correct instant. The helper reaches search, context score/recency ordering, existing semantic sorting, session memory
ordering, continuity, timeline, compaction best/oldest/access selection and staleness, scoring age arithmetic, hierarchy
age decisions, CLI recent/status ordering, SQLite list ordering, and trace duration subtraction. Existing score formulas
and weights are unchanged. Compaction adds ID tie-breaking after its pre-existing best-source signals.

Evidence: original `test_mixed_timezone_equal_score_retrieval` now passes. UTC/naive/+03/-05 equal instants exercise stable
IDs, search/context/timeline, semantic and session sorting, compaction, persistence/reopen, untouched serialized offsets,
legacy JSON dates, year-range boundary instants, and controlled malformed input validation. **Closed** for supported parsed timestamps.

## Exact changed files

- Storage: `mneno/storage/transactions.py`, `memory.py`, `json_file.py`, `sqlite.py`, `__init__.py`.
- Imports/compaction: `mneno/io/importers.py`, `mneno/client.py`, `mneno/compaction/engine.py`.
- Time comparisons: `mneno/_time.py`, `context/builder.py`, `retrieval/semantic.py`, `scoring/temporal.py`,
  `hierarchy/manager.py`, `sessions/manager.py`, `sessions/continuity.py`, `sessions/timeline.py`,
  `observability/recorder.py`, `cli/commands/recent.py`, `cli/commands/status.py` (also client/compaction/SQLite above).
- Regressions: `tests/test_data_integrity.py`, `test_phase_a.py`, `test_compaction.py`, `test_evaluation.py`, `test_storage.py`.
- Metadata/documentation: `pyproject.toml`, `README.md`, `docs/changelog/overview.mdx`, `docs/concepts/storage.mdx`,
  `docs/concepts/compaction.mdx`, and the seven Phase A report Markdown files (the six existing reports plus this report).

## Validation and environment

macOS 27.0.1 arm64; CPython 3.11.17; SQLite 3.53.1. The repository `.venv` is the supported environment. System Python
is not used for checks. `ensurepip` restored the missing dev-environment pip; isolated builds use Hatchling 1.32.4.
No runtime dependency declaration changed. No cloud/model provider was called; build tooling may resolve build dependencies.

| Command | Result | Failed / skipped / xfailed / warnings |
| --- | --- | --- |
| Starting `scripts/check.sh` | Ruff/format/mypy passed; 455 pytest passed | 0 / 0 / 3 strict xfails / no pytest warnings printed |
| `.venv/bin/pytest tests/test_data_integrity.py -q` | 111 new integrity/version/CLI cases passed | 0 / 0 / 0 / none printed |
| `.venv/bin/pytest tests/test_phase_a.py tests/test_io.py tests/test_compaction.py -q` during implementation | First run 96 passed, 1 failed at unfixed A-12; later fixed | Failure recorded, not presented as passing |
| Full `.venv/bin/pytest -q` during implementation | First full run 455 passed, 3 failed on old deletion-count contracts; after deliberate archival-contract changes 458 passed | Historical failures resolved with stronger active/history assertions |
| Final `scripts/check.sh` | Ruff lint/format, mypy 93 source files, 569 pytest passed | 0 / 0 / 0 / no pytest warnings printed |
| `git diff --check` | Passed | No whitespace errors |
| `.venv/bin/python -m build --outdir /tmp/mneno-phase-a-0.5.0-dist` | Sdist and wheel built | No build failure |
| `.venv/bin/python -m pip install --no-deps -e .` | Editable 0.5.0 metadata installed | No runtime dependency changes |
| `.venv/bin/python -m pip install --upgrade --no-deps --target /tmp/mneno-phase-a-0.5.0-wheel /tmp/mneno-phase-a-0.5.0-dist/mneno-0.5.0-py3-none-any.whl` | Installed-wheel SDK/CLI smoke target | Package import path checked outside checkout |
| `PYTHONPATH=/tmp/mneno-phase-a-0.4.1-wheel .venv/bin/python /tmp/mneno_phase_a_upgrade_fixture.py` | Old installed wheel created JSON/SQLite linked conflict/session fixtures | Source import path/version checked |
| `PYTHONPATH=/tmp/mneno-phase-a-0.5.0-wheel .venv/bin/python /tmp/mneno_phase_a_wheel_smoke.py` | Wheel version/SDK, both persisted upgrade fixtures, CLI JSON/version and five agent dry-runs | Local smoke only; no live coding-agent execution |

Tests use fault injection, barriers, spawned processes, and bounded joins, not timing sleeps. POSIX-specific directory
sync tests and symlink coverage ran on this machine. Windows, Linux, Python 3.12/3.13, network filesystems, actual power
failure, and Mintlify live rendering were not executed locally; CI retains its existing Python/Linux matrix. No new
performance measurements are claimed: `PERFORMANCE_BASELINE.md` retains the **0.4.1** measurements, not a 0.5.0 latency
promise. Snapshot validation/copying and retained history increase costs; correctness takes precedence here.

## Version ownership and release preparation

| Item | Evidence |
| --- | --- |
| Previous / selected version | 0.4.1 / 0.5.0 |
| Rationale | Pre-1.0 minor: durable archival changes compaction stored-count semantics; custom batch stores need atomic capability; diagnostics additive |
| Authoritative source | Static `[project].version` in `pyproject.toml`; Hatchling uses it |
| SDK / CLI | Installed SDK `importlib.metadata.version("mneno")`; CLI `get_version()` uses the same installed metadata; no independent `__version__` |
| Synchronized files | `pyproject.toml`, existing `docs/changelog/overview.mdx`, current report/docs compatibility statements |
| Historical versions | Existing changelog entries, old release tags, and initial-audit/performance results retained |
| Existing release convention | Local tags through v0.4.0; `release.yml` accepts v*.*.* and checks tag vs pyproject before existing PyPI workflow |
| Migration | None for JSON/export v1 or SQLite v2; adapt compaction count assumptions and custom batch implementations |
| Suggested tag | `v0.5.0` — not created or pushed |
| Publication | None: no PyPI publish, GitHub Release, release tag, deployment, or force-push |

The ordinary checks/build/wheel gates pass locally. Release readiness means this implementation is ready for review and
the established CI/release gates, not that unexecuted platform checks or publication have occurred.

## Remaining risks and first Phase B experiment

**P0:** No open blockers among these five within the documented supported guarantees. Arbitrary custom capabilities and
noncooperating writers are outside those guarantees, not silently downgraded to best-effort transactions.

**P1:** Snapshot batch cost/lock duration; retained-history growth; Windows locking unexecuted locally; whole-record updates
must be recomputed on conflict. Existing multi-call SDK add/lifecycle/session operations and separate export/backup reads
are not globally transactional merely because the store offers a transaction. In-memory models remain mutable under the
legacy individual-record API; use store methods rather than mutate shared returned models across threads. Prior provider
validation, trace allocation/retention, token-wrapper budget, and CLI findings remain in the debt register.

**P2:** Indexed lexical candidate generation, optional semantic persistence, reranker/provider validation improvements,
and larger performance work remain separate milestones. No LOCOMO metrics or recall improvement are claimed.

First measure 0.5.0 stage costs with fixed persisted state, reference time, policy, session, and access-state reset. Then
prototype an optional SQLite FTS5 candidate generator **in a future phase**, keeping existing scoring and lifecycle gates.
SQLite already exists and the historical 10k full-scan latency supports investigating indexing, but scan/deserialization,
trace, and persistence overhead must be separated before attributing gains to FTS/BM25. Compare candidate coverage and
ordered result parity before latency. Keep zero-query/Unicode/punctuation behavior, inactive visibility, conflict
warnings, transaction/index synchronization, stable IDs, and storage compatibility in the regression gates. Do not make
FTS availability or BM25 ranking mandatory, and do not promote a prototype without externally measured coverage evidence.
