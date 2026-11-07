# P1361 — cooperative pending-source selection boundary

## Status

Implemented, independently reviewed, published and source-qualified on Windows
and ARM. Live backend installation remains pending; the actual-process namespace
authentication gate is not waived. This does not supersede P1359's separately
qualified reader artifacts or its pending NanoPi installation. No live helper,
backend, service, gate, namespace configuration or data was changed by this patch's
source qualification or immutable-package preparation.

## Problem and change

The existing cooperative elapsed budget starts before reader preparation. The
collector already refuses new row/pair admission after that budget expires, but
still entered pending-source SQL after preparation or admitted cursor retirement
had consumed it. This is demonstrated unnecessary new selection work; no false
comparison, hard-runtime violation or production outage was demonstrated.

After preparation/retirement, recheck the SAME existing budget before entering
pending-source selection. If unavailable, initialize an empty local selection and
continue normal final diagnostic assembly. Do not return early: already-admitted
retirement can commit and must still be reported. Skipping selection must not
clear unfinished-source recovery or advance source/peer positions.

Standalone read-only `pending()` remains unchanged. A later fresh pass can still
recover and compare the retained source. Existing elapsed diagnostics, SQL-read
budget ownership, pair limits, defaults and scheduling eligibility are unchanged.

## Acting control and candidate evidence

- Before production editing, three focused tests ran on the pristine published
  implementation: the fresh positive passed and exactly two intended negative
  delegate/eligible-SQL assertions failed, with zero loader errors.
- Fresh clock100/deadline101 entered the actual pending delegate, issued eligible
  SQLite selection, and stored a real-reader80-opportunity comparison. The clock
  is a deterministic ordering control, not a latency measurement.
- Expiry during reader loading and during REAL admitted cursor retirement both
  crossed to102. Untouched code entered the actual delegate and eligible SELECT
  in each arm. The candidate enters neither, retaining the existing explicit
  cooperative time-limit diagnostic and zero newly attempted comparisons.
- The retirement arm actually deletes an orphan and commits its maintenance
  checkpoint. Reopen proves that completed work survived while old complete
  observation/capture tuples, replay metadata and scheduling/recovery positions
  were retained. The following fresh pass compares the remaining pair with80
  opportunities, preserves the prior pair and clears only completed recovery.
  Synthetic raw recording bytes remain unchanged.
- Windows Python3.10: 128 unit cases run,126 pass and two existing POSIX-only
  controls skip; zero failures/errors. Banks cover elapsed/in-flight flush,
  retirement, reservation/crash recovery, selected SQL budgets, ownership,
  atomic flush, collection, ingestion, skip codes, CLI defaults and overlap.
- ARM aarch64 Python3.11: the SAME two banks run79+49 cases, all128 pass with
  no skips. All192 input-source hashes match after qualification and the owned
  synthetic temporary root is empty. These are source tests, not production
  namespace acceptance or a whole-backend/fleet proof.

From `surfd`, use the existing import-safe unit banks, not discovery over
standalone executable test scripts:

```text
python -B -m unittest -v test_simcheck_cursor_retirement test_simcheck_time test_simcheck_source_reservation test_simcheck_sql_sources test_simcheck_sql_peers test_simcheck_sql_summary test_simcheck_ownership test_simcheck_atomic_flush
python -B -m unittest -v test_simcheck_collection test_simcheck_budget_cli test_simcheck_ingestion test_simcheck_codes test_simcheck_overlap
```

## Limits and delivery boundary

This is one observed cooperative admission boundary, NOT a hard deadline,
preemption of SQL/native work, total RSS/I/O bound, source-cardinality bound or
complete/fair fleet coverage. Schema/preparation and work already entered can
finish after the deadline. No numerical latency/performance improvement is
claimed from fake monotonic time.

No schema, capture/evidence format, clock-model expansion, stored-history rewrite,
comparison/threshold/default/ranking/enforcement policy, reader, native source,
pin/tag, VM or QC Build change. The backend artifact must come from the exact
reviewed inspected source, preserve the guarded runtime's current-data rollback,
and separately prove destination hashes and actual current-process bindings.
Do not ship a peer-containing dirty canonical tree or infer live installation
from these source results. Deployment will be recorded here when completed.

## Publication and immutable preparation — 7 November 2026

- Public implementation: `fb7ed790505cfdb9a232f777d3f7eda9c4c5fbe6`;
  engine ledger: `6f883904a63cd5b4324a72a634b6d3304e29fc5d`. Independent final
  code/evidence/public-claims review clears the frozen bytes with no blocker.
  Validated product and regression-test hashes remain identical after rebasing
  over unrelated published documentation. The exact owned cfg reservation was
  retired only after the patch heading was published.
- A private immutable collectors84-v1 runtime package is assembled with exactly
  `simcheck.py` changed and all other83 runtime hashes preserved. Two inherited
  frozen source files intentionally remain at the serving profile's older
  versions; newer public files are not silently substituted. This follows the
  existing code-only frozen-runtime-plus-reviewed-delta procedure, not wholesale
  deployment of the current public checkout.
- Package assembly is NOT exact-package CLOSED-cohort, service, namespace or
  live-current-data qualification. No PIDs, closures, clocks or authorizations
  are frozen into the immutable package; those must be observed at the actual
  execution boundary. Preparation must not leave maintenance gates held.
- The required actual namespace authentication still blocks live cutover. This
  record does not infer a live pass, deployment or recovery qualification from
  source tests, independent review, package assembly or a host-only probe.
