# P1530 — rejected journal state is unavailable, not unchanged

Implemented and source-qualified. **Not independently reviewed or live-deployed.**
The owner postponed the physical-input test; these fixes neither require nor
substitute for that test. Native code/commit/tag pins, recording fields, readers'
ranking rules and thresholds, QC Build89 and historical stored verdicts stay held.

## Two confirmed reader defects

1. Early parser rejection of an input-setting change did not invalidate its old
   value. Later valid angles from the actual new setting could then be faulted
   against the stale scale. Missing/unrecoverable names could also leave the old
   model active. A format fault is not a valid model observation.
2. Rejected keyboard-observation state/count records could leave `kbdobserve1`
   reporting a whole-journal measured zero despite an unknown transition or lost
   count. The format fault did not make that measurement trustworthy.

The correction reuses existing interfaces. Each per-view setting dictionary is a
snapshot: a rejected named change becomes unknown until a later valid restoration;
known earlier comparisons remain. A missing name, including a quoted value in the
name slot, cannot identify which setting survived. Known unrelated setting names
are not used to hide valid angle comparisons. Independently finite raw-count
joins remain active, including real contradictory-count controls.

Unusable keyboard-observation records latch the existing partial/unavailable
state and withhold whole-journal key/nohandle totals. Valid measured zero, positive
counts and a known observation stop retain their three distinct answers. Existing
format/clock faults remain faults; no corrupt journal becomes acceptable. There
is no native/capture/writer/record-format change or newly inferred physical input,
identity, player verdict, calibration or enforcement.

## Acting controls and verification

- Final matched fixture against the untouched reader: **1090 checks,40 failures**.
  Corrected reader: **1090 checks, zero failures**, including **89 new assertions**.
- The setting-only correction independently reproduces **13 keyboard-coverage
  failures** before that correction. Both defects therefore have separate acting
  controls, not just an overall green test count.
- Setting loss excludes only the affected transitions. Earlier comparisons remain,
  valid restoration resumes judging, unrelated named changes do not hide checks,
  and an independent declared-profile counts mismatch still faults. Losing only
  elapsed-clock arithmetic does not discard a finite setting payload.
- Keyboard loss withholds whole-run measured totals while all19 independent finite
  angle/count intervals in each fixture still act. Valid zero and positive2/1
  remain measured; a valid observation stop remains partial, not corrupt.
- `python tools/test_reccheck.py`: **949 checks, zero failures**.
- `python tools/test_rcptcheck.py`: **800 checks, zero failures**.
- `python tools/test_journal_diagnostics.py`: **32 tests, zero failures**.
- All **134 retained input-journal hashes** match the captured cohort; parent and
  subject agree exactly on every fault, information field and note. **Three
  existing faulty files** stay faulty. Retained test/capture files are not human
  labels or hardware/calibration evidence.
- Current paired corpus: **568REC +183VIEW**. All751 input hashes and every
  per-file report are identical; **356 existing faults** remain unchanged. No
  old file or stored verdict was modified/regraded.
- Supported isolated `src/build.ps1 -NoDeploy -Jobs 8 -FteRoot <owned-engine>`:
  **three QC VMs, zero warnings**. Native code is unchanged, so the still-valid
  tagged native qualification is not repeated or claimed as new native testing.
- No LSP diagnostics recorded for the two edited Python files; actual tests/build
  above are the verification, not the LSP result.

## Preserved failed fixture predictions

Two initial fixture mistakes are retained, not hidden by product changes. A huge
positive clock delta does not reject an otherwise finite setting payload: the
existing reader correctly separates timing availability from angle/count checks.
That arm became an acting control of this unchanged behavior. A counts-mismatch
fixture initially omitted its declared P312 input profile, so its difference was
correctly a measured note rather than the expected declared-profile fault. Adding
that existing profile to the fixture restores the intended control without
changing reader policy. Full final-fixture parent/subject logs remain bound.

## Delivery limits

Publication is not independent review or deployment. The required verifier-source
review gate remains; no self-clear, old report reuse, silent external-provider
fallback, live install/lobby/backend action or maintenance gate. Native ledger is
documentation only and does not move the native commit/tag pins. New findings may
invalidate their exact dependencies, not every passed campaign. Physical input,
genuine labels, complete model/world coverage and trust/privacy/policy decisions
retain their separate gates. The deferred native/compiler/filewriter audit was
not resumed.
