# P1361 — cooperative pending-source selection boundary

## Status

Implemented, independently reviewed, published, source-qualified on Windows and
ARM, and delivered to the NanoPi backend. Owner authenticated and executed the
reviewed guarded namespace installation and primary cutover. Fresh read-only
completion audit at 7 November 2026 09:25:46 UTC binds the actual namespace receipt
to the current process PID/birth/CWD and verifies the live material, OPEN health,
cron/importer source and current-data preservation. P1359's reader pair remains
unchanged. Source qualification, synthetic startup and actual delivery are
separate evidence; no native-engine or whole-fleet claim follows.

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
from these source results. Actual delivery is recorded below; fallback runtime
material was qualified, but a production fallback was not invoked or claimed.

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
- P1359's owner-authenticated reader update was verified at 07:02:30 UTC. The
  subsequent P1361 qualification and delivery below required their OWN acting
  startup controls and fresh actual-process authorization, not a forwarded P1359
  token or an inferred pass from assembly/host-only probes.

## Exact-package qualification and actual delivery — 7 November 2026

- Both exact candidate and current-core fallback profiles started as real CLOSED
  synthetic candidates. Schema26, health/listener, inventory/playstats and protected
  source-route authentication/CSRF/site controls acted. Each profile passed13
  explicit-reader cases, accepted a receipt, reopened OPEN and drained CLOSED.
  All owned processes/listeners and synthetic temporary files were cleaned up.
  Original dependency/refusal and observer failures remain separately recorded;
  the later continuation does not relabel the failed aggregate or claim
  continuously immutable history for an exactly restored evidence file.
- Independent operator review found and corrected interrupted-closer cleanup and
  canonical metadata binding defects before execution. Thirteen narrow final-source
  control-flow/metadata-CAS falsifiers passed; these are NOT application integration
  tests. Actual noninteractive namespace preflight correctly refused missing sudo
  authentication BEFORE holds, shared ingress or DB access. It was not bypassed.
- Owner authenticated, installed the guarded namespace configuration and executed
  the primary backend cutover. The operation actually closed/drained the selected
  predecessor, stopped known actors, promoted owned canonical bindings, started
  the CLOSED candidate and accepted its actual process/namespace/data receipt
  before reopening. Normal launcher, four cron routes and importer were then bound
  to the selected primary source. No lobbies were restarted and no P1359 reader
  files were replaced by this backend-only operation.
- Fresh completion audit at 09:25:46 UTC: current primary process PID/birth/CWD and
  invocation match its production and actual default-reader namespace receipts;
  all158 bound files, runtime84, external3, control pins and actual process-view
  hashes match. Both runtime homes/control pins are read-only where required;
  state/control/data/log directories remain writable. Admission OPEN, health OK,
  canonical normal launcher and all four cron/importer source bindings verified.
- SAME CURRENT database: schema26, all44 table keys, original file identity and
  eight identity-table digests preserved across the cutover; allowed live-presence
  churn remains distinct. Fresh readback still matches the cutover identity
  digests. No old database restoration, new comparison policy or history rewrite.
- Namespace shared ingress was exactly restored, its reservation removed, and
  collector/activation/sweep resources released. No failure/recovery artifact or
  active owned closer remains. The live runtime, namespace guard roots and rollback
  material are retained as production infrastructure, not disposable scratch.

These checks verify this primary delivery, not hard deadlines, general resource
bounds, latency improvement, new hardware coverage, calibration, verdict policy
or complete anti-cheat coverage. The128 ARM source cases,13-per-profile synthetic
reader cases and actual primary namespace/data acceptance retain their own scopes.
