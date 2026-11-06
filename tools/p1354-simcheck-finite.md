# P1354 — non-finite comparison output is unavailable

## Problem

The real reader can complete an80-opportunity comparison while its optional
recording tickrate is NaN or infinite. SQLite `INSERT OR IGNORE` silently drops
the NaN observation because a required numeric column becomesNULL; infinite
values can instead be stored even though the existing admin projection cannot
use them. Neither path reported the existing per-pair availability failure.

An initial whole-batch-loss hypothesis was **disproved**: the valid peer survives
NaN omission. Original probe/failed prediction and owned test-fixture failures
are retained; the actual problem is not described as transactional corruption.

## Change

Before building a compared observation, require `match`, `cover` and both tickrate
values to be finite. Non-finite output raises into the existing per-pair failure
path, remains unmeasured and reports `pair_failed`; it is not a fabricated skip,
zero score, malformed-player finding or clean result. Other finite peers continue.

No reader/parser, recording/capture/schema, first-winner, transaction, identity,
history, threshold, verdict, badge, ranking, native pin/tag or QC Build change.
This adds no tickrate range/equality rule: finite differing, zero, negative and
very large rates retain their previous comparison behavior. Historical rows are
not rewritten or automatically remeasured. Genuine SQL failures retain existing
whole-flush rollback rather than being swallowed as a pair failure.

## Verified source

- Untreated production fails23 assertions across the10new test cases. Real
  positive/invalid-header comparisons act with80opportunities; they are not
  replaced with canned comparison results.
- Focused Windows69tests pass, including pair faults, atomic flush, captured-source
  preservation, source reservation and P1352 cursor retirement.
- Removing only the finite guard makes the real-NaN unavailable-counter test fail.
- Both orders/sides, NaN/infinity/decimal overflow spellings, all four float output
  fields, finite-mismatch/legacy-rate controls, actual collector-step diagnostics,
  admission accounting and reopen/preservation checks are covered.
- A real finite zero-match comparison retains its76opportunities and measured
  zero. Its initial test incorrectly demanded80, then referenced an absent reader
  constant; those original fixture failures remain separate from product results.
- Original parser/sources/old observation stay unchanged, independent writers act
  during real comparison, and a deliberate SQLite trigger still rolls back the
  entire short flush. No live collection or player data is used by these tests.

ARM regression, independent clean-source review, publication and guarded backend
cutover are pending. A passing source test is not a live-delivery claim. This is
one finite availability/metadata-correctness repair, not a hard total resource,
fleet-completeness, nonparticipant, authenticity, hardware or enforcement proof.
