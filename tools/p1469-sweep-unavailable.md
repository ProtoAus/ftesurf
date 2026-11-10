# P1469 — failed similarity collection is unavailable in the sweep summary

## Problem / change

`surfd/sweep.py:similarity_step` already prints setup/collector exceptions to
stderr. Its returned empty note, however, left the normal per-tick summary
indistinguishable from an intentionally disabled or uneventful similarity step.
This was not absence of all diagnostics.

The exception branch now returns its existing zero counts plus the fixed note:

    sims unavailable: collection failed (coverage not measured)

The existing main loop appends that note normally. The stderr diagnostic and
exception handling remain. Intentional disable still returns an empty note.
No schema, parser, evidence, score, verdict, threshold, scheduling, resource
allowance, enforcement, native pin/tag or QC Build change. No claim of stronger
whole-pass time/RSS/I/O bounds, measured coverage, calibration or detection.

## Verified

Existing `python -B surfd/test_simcheck.py`, in an isolated fixture:

- A real SQLite authorizer refuses the wrapper's attempted busy-timeout owner
  setup. Its callback proves the setup was attempted; no mocked collection
  result or silent-path pass.
- The failed step reports unavailable, preserves stderr, and stores no
  comparison or changed verdict. Explicit zero-pair disable remains silent and
  attempts no owner SQL.
- Clearing only the fixture refusal lets the SAME pending real pair actually
  parse, compare and store through the wrapper; busy-timeout restoration and
  unchanged verdicts are checked.
- Original production source completed with exactly the predicted returned-note
  assertion failure; subject **all79 checks pass on Windows and all79 on
  NanoPi Linux/Python3.11**. Linux ran the standard Git archive of inspected
  source `10df58b127e2a948475c8632d6d971d3e4923aa3` at03:11:58 UTC10Nov2026,
  archive SHA256 `6889fccf493b5032a74405df185e8cab702947c8d0740528abcec49bf20bd44f`.
  The suite also covers normal cron-summary reporting and comparisons without
  a write lock.
- The first incomplete new control exposed Python3.10's authorizer API behavior;
  it is retained as a failed control, not counted as the completed baseline.

## Delivery status and limits

Implemented and Windows/Linux-verified; the tested source is published with this
record. **Not live yet.** Do not modify
an accepted immutable runtime or bypass its source/namespace/admission checks
for this small reporting change. A later qualified backend generation must keep
CURRENT-data preservation and a conservative rollback path. The existing healthy
backend/lobbies must not be replayed or restarted merely to refresh this record.

This patch is independent of the paused broader native/compiler audit and of
local GUI fixture ownership; neither restriction was worked around. The prior
P1447/P1448 Windows copies are now hash-verified in both installs; actual client
and human checks remain separately pending, not inferred from these unit tests.
