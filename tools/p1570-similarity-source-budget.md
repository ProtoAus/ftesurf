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

**Delivered 15 November 2026 at 14:39:54 UTC; independently read back at
14:48:17 UTC.** The guarded transition admitted the new primary only after
qualifying a compatible fallback against the actual current database first.
This was one runtime-file change (`simcheck.py`), not a blanket upgrade to later
main. All 85 runtime files in each role and their sealed controls match the
inspected packet. Six readers and the actually selected native image are unchanged.

Both CLOSED roles admitted health checks and refused the two ordinary-request
controls with 503. Their full database snapshots match the drained baseline:
schema 26, all 46 table counts/content digests, eight identity digests, objects,
queues and the same database inode. After OPEN, preservation checks are
schema/object/inode-only; ordinary writers are no longer claimed frozen.

Independent postflight confirms the accepted primary actor, actual namespace
and six-reader resolution, exact canonical launcher/seven stubs, active importer
and HTTP 200 health/lobby-directory responses. Four scheduled routes are rebound;
every other crontab byte is preserved and all seven temporary holds are gone.
The controller exited and released its leases. Compatible rollback source and
CLOSED state are retained; recovery requires the existing guarded current-data
procedure, never an old database restore, stale grant or activation replay.

P1570 is backend-only: no Windows/QC/native swap, lobby restart, capture/default,
retention, ranking or enforcement change. Native commit/tag and qcbuild89 were
not changed by this delivery. The controlled 80-move discriminator above remains
a fixture result, not a new real-player recording, calibration measurement or
completion of a broader research criterion.
