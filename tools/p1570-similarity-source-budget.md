# P1570 — useful owned similarity work before unused source selection

## Outcome

A store-only collector with a small selected SQL allowance can now complete an
otherwise reachable first comparison instead of spending its allowance first on
source rows it will not use. This adds no detector, clean-human assertion,
calibration, ranking, enforcement, capture/default or retention policy.

P1491 already bounded peer prefetch by remaining pair allowance. This is a
separate source-selection issue, demonstrated against the published production
wrapper and real reader; it is not a reason to restore a larger peer window.

## Bounded change

Only the already-owned collector uses the internal deferred source iterator.
It reads scheduling metadata once, prioritizes proven eligible recovery and
walks ascending upper and disjoint lower/wrap ranges around a fixed anchor.
The requested source cap stays independent of remaining pair attempts, so an
unavailable recording can leave room for a later measurable source.

Admission is checked before asking for another source (which performs SQL),
after selection, and between iterator reads. A failed eligibility query does
not clear unproven recovery. A late source read/lock/time stop preserves actual
prior measured commits. Zero IDs are not absence sentinels.

Generic pending lists/counts, direct comparisons and their windows are unchanged.
This is current-eligibility iteration, not a snapshot of a whole moving cohort.
Selected-read limits remain cooperative; no global hard time, RSS, kernel I/O or
full-fleet fairness guarantee follows.

## Verification

- The matched actual wrapper case retains its real reader and normal measured
  pair/capture. Old production exhausts the selected SQL allowance before the
  first comparison; the subject stores the expected 80-move comparison.
- Later unresolved-source opportunities, source and peer rotation/recovery,
  zero-ID, removed/completed recovery, interrupted selection, stale-marker
  handling, late SQL/time/lock stops, connection ownership, idle/timeout
  restoration and generic direct-window controls act.
- Targeted Windows programs pass. Final Linux qualification is **197 checks,
  zero skips/failures**, including six typed SQLite/POSIX cases. These counts
  include inherited tests and are not a unique coverage percentage.
- A new test initially pinned Windows CRLF fixture capture bytes and failed on
  Linux LF input after the valid comparison. That failure remains failed.
  The corrected test independently hashes/sizes both authored files before the
  collector call and compares the complete expected capture mapping; it neither
  normalizes input bytes nor substitutes an observed platform hash. The changed
  BudgetCLI bank passes 5/5 on both platforms, and old production still fails the
  discriminator. Unchanged program evidence was reused, not rerun for a count.
- Independent frozen-source and test-portability delta reviews found no P1/P2.
  No native build/selftest, real recording capture or detector calibration was
  performed. Evidence grammar and the six ordinary reader modules are unchanged.

## Publication / delivery

Implementation and scoped qualification are complete; **live backend delivery
is pending**. P1570 is backend-only: native commit/tag and qcbuild89 stay pinned.
There is no Windows/QC/native swap or lobby restart required for this source fix.

Use the existing guarded generation contract, based on the actual current live
source/dependencies, not an older generation snapshot or an in-place copy. Park
ksfimport and both momgrab cron routes before the final busy check, only for the
short actual transition interval; preserve and restore the exact owned entries.
Keep source/actor/namespace, recorder/resume/data and compatible rollback checks.
A passing source bank or patch reservation does not prove installed/live behavior.
Record actual destination hashes, resident behavior and UTC only after admission.
