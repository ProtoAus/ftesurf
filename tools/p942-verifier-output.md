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
- Publication: pending exact inspected commits. Deployment: pending a guarded
  immutable-runtime handoff; replacing the unused canonical script is not delivery.
