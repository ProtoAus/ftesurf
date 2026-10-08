# Owner observation follow-ups — P595, P596, P597

These are SURFD-only display/read improvements. They do not change detectors,
thresholds, scoring, identity policy, verdicts, ranking, or evidence writers.
Engine/QC/Build pins and shipped game artifacts remain unchanged.

## Changes and acted controls

- **P595 / `45559b1`:** acquire one sentinel beyond the 200 displayed verifier
  attempts; additive owner-only limit/more metadata and truthful partial summaries.
  Actual authenticated API, SQL acquisition and executed template controls cover
  0/199/200/201/400 attempts, ordering, an omitted current attempt, anonymous401,
  unchanged history and public board. The current/public verdict query is separate
  and unchanged. No total-count scan or pagination.
- **P596 / `4c2d894`:** duplicate decoded JSON object keys make stored journal/counts
  projections unavailable, at every nesting level. Text/BLOB and escaped-equivalent
  key cases cover both projections; valid zero, empty metrics and no-records remain
  distinct. Byte caps and typed allowlists persist; stored observations/verdicts do
  not change and historical review does not invoke the source reader.
- **P597 / `a8d6169`:** the optional similarity table probe shares the existing
  cumulative owned SQL allowance with PRAGMA/history. A real one-step interruption
  acts before later reads, clears the owned handler, reports read_limit rather than
  missing, and recovers an 80-opportunity stored observation under the default.
  Borrowed callbacks remain untouched; unrelated I/O remains an error.

Independent fresh read-only review found no source issues. It reviewed frozen
diffs and parent-supplied evidence, not a Git/hash/deployment attestation. Its two
predecessor-proof qualifications were addressed in test-only `38eb243`: execute
the actual old inline summary rather than fail at an absent helper, and assert
journal/counts duplicate cases independently. Production bytes did not change.
Actual predecessor reds: history seven assertions/subcases, duplicate projections
20 text/BLOB subcases, initial-probe two assertions. Subject focused tests pass
with warnings treated as errors. Existing actual receipt/counts Node controls pass.

## Reproduction and full proof

From the inspected tree:

```text
python -W error surfd/test_admin_verdict_history.py
python -W error surfd/test_admin_metric_duplicates.py
python -W error surfd/test_admin_similarity_probe.py
python -W error surfd/test_admin_similarity_budget.py
python surfd/test_admin_metrics.py
python surfd/test_verifier_counts.py
python tools/test_reccheck.py
```

Frozen `38eb243400dad89df04a44f2fe18daaae4262ad1` has 58 standalone SURFD
programs on Windows: 57 pass; only test_admin fails the same two UDP/amplification
assertions reproduced on untouched `4f066479`. Argument-required test_momindex is
not a standalone pass. Exact-commit Linux stage has 59 passing programs, including
reccheck. Recorder: 306 checks, zero failures. The same captured local REC/view
corpus has identical predecessor/subject fault observations; no blocked reads.
HID was inventoried only. Legacy fixture warnings are not a warning-clean full
suite; the new focused suites are warning-clean. No QC/native build was needed.

## Verified deployment

Only these exact-commit runtime files shipped to the Pi:

```text
surfd/admin.py
surfd/templates/admin_run.html
```

The complete test-only harness stays in an isolated exact-commit control stage;
it is not partly installed as standalone tests. Installed checks assert actual
production module paths and read the actual installed template. Twenty-two tests
pass, four Node-dependent skips; Windows Node controls actually execute.

The frozen surfd-deploy script lacks the proposed staging-only parameters: that
request failed before any remote work. An inspected minimal adaptation uses its
canonical `/tmp/surfd-sweep.lock`, under-lock predecessor/support checks, exact Git
archive hashes, mode600 SQLite/file rollback copies and atomic two-file swaps.
A stable read snapshot plus a 90-second backup deadline prevents heartbeat churn
from restarting the backup indefinitely; snapshot release precedes fresh
preservation reads. The first timed-out backup was aborted before swaps, retained
and explicitly marked incomplete. A wrong private probe cookie name and missing
Pi-kernel task/children interface were corrected in the private procedure only.
The latter attempt restored the exact predecessor files; portable parentage is
used for worker replacement proof.

An installed legacy counts test crossed a clock second and failed only on board
`t`. Restored predecessor reproduces this under a deterministic advancing clock;
the same test passes with a stable clock. Only that isolated fixture's clock is
frozen, with no production/legacy-test source repair. This follow-up remains in
BACKLOG. Failed deployment attempts and rollback evidence remain private.

**Final installed verification: 2026-10-08T13:59:52Z.** Owned master retained,
worker replaced, health12, authenticated actual-worker API, anonymous401, selected
history rows and public board unchanged, retained production support/config/game
progs/reader bytes unchanged. Destination hashes match the pinned runtime blobs;
rollback files and completed mode600 database backup remain. No Windows, engine,
progs, reader, config, collector, release or live synthetic-data swap.

## Limits

Not whole-request time/RSS/I/O bounds; not calibration, backfill, authenticity,
new field samples, human browser layout or any new detection/enforcement claim.
Private plan, logs, corpus, failed controls and provenance stay in the private tree.
Human-only acceptance is in lextest.md. Shared peer source and indexes were not
staged, reverted, stashed or deployed.
