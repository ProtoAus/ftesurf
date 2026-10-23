# Patch 942 — unambiguous verifier output attribution

## Problem

The sweeper selected the last `VERIFY` result for a path. Repeated or conflicting
results could therefore select a terminal verdict and counts from an ambiguous
attempt instead of reporting unavailable verification.

## Change

A second result for the same path latches a retryable `ERROR`, with unknown ticks
and no counts observation. Further results cannot reset that state. A distinct
companion path remains independent. Existing ERROR budgets, explicit rechecks,
owner review and historical-verdict policy are unchanged.

No engine, QC, recording format, collector, schema, retention, threshold or access
change. Native commit/tag pins do not move. This is output attribution only, not
immutable engine-input binding or hostile-host change-and-restore protection.

## Verified

- Seven new tests against published QC `5992a5ef`: 17 failing subcases, including
  conflicting and repeated identical outcomes, counts binding and abandon promotion.
- Corrected identity/source/finish/counts suites: 38 tests, zero failures.
- Unique-path companion and ordinary retry controls positively invoke the runner.
- Sweep, board and replay-ledger boundary suites pass. Reader unit suite: 864
  checks, zero failures. Corpus remains 419 recordings, 283 faulted files: the
  unchanged reader matches the retained pre-patch floor; no new reader faults.
- Existing `build.ps1 -Jobs 8 -NoDeploy`: all three VMs, zero warnings. The initial
  missing-compiler failure is retained; the supported PATH compiler lookup fixed
  the environment without a source/tool change or touching either install.
- Independent correctness and evidence reports identify no findings. The evidence
  child's final tool-profile status failed; its complete saved audit was recovered
  and reviewed, not represented as a clean workflow or independent test execution.
- Published QC `f01d7283` / engine documentation `a1d0d8e0a`. Delivered
  2026-10-23 06:40:24 UTC; verified 06:40:27 UTC through the existing guarded
  immutable-runtime handoff. Of 80 runtime files, 79 stayed byte-identical;
  only `sweep.py` changed. The fresh worker also witnesses that module's origin.
- Old runtime CLOSED and drained; new runtime OPEN. All 12 lobbies healthy,
  with the same game-process identities/native/readers; AI remains inactive.
  Eight canonical bindings and four guarded cron routes match; the importer
  has a fresh, observed process epoch and exact new admission descriptor.
- Actual scheduled verifier route exits 0; predecessor CLOSED route refuses.
  This is entrypoint reachability, not an invented extra parser-control pass.
- Initial 512-page online backup restarted under live WAL writes and hit its
  45-second deadline BEFORE staging, signalling, closing web or swapping files.
  Failure retained. The existing shipper's whole-step API completed the SAME
  owned target in 9.517 seconds within that bound; mode0600/schema20/quick_check
  and exact-byte controls pass. Independently cleared phase continuation reused
  that snapshot, without a second copy, restore, guard bypass or failed-live retry.
- P941 landed separately while delivery was in progress; its source was not
  implicitly shipped by P942. No Windows game artifacts were replaced by this
  backend-only deployment. Future reader/native/progs changes must coordinate
  the frozen worker witness, not silently invalidate its dependency pins.
