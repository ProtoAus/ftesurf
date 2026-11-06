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

## Actual publication and delivery

**Deployed6November2026 at20:16:38UTC.** Public source and serving generation
`bf9c7b306bce2c8f538fcf13cc0c3be48e719005`; engine journal
`d3dfefb21231d28761ff56a23cfe99f7caec780b`.

Two differently-lensed independent reviews of the clean frozen source found no
blockers. ARM270unitcases/0skips and68standalone checks pass, with all1301supplied
Git-source files exact before/after. Reader949checks pass; stable548REC/178VIEW
corpus retains351existing faults, with reader/heldmeta identical to prefeature.
These are invocation totals, not whole-product or unique authored coverage.

The existing guarded84-file generation route changed only `simcheck.py`; the
other83frozen runtime files and separately bound reader stayed unchanged. Both
actual CLOSED primary/rollback candidates ran real80-opportunity NaN/infinity
controls, existing authentication/source guards and six acted guard negatives.
Cutover preserved44schemas, eightidentity-table digests and protectednonchurn
counts;156bound-file checks pass. Fourcron routes and the managed importer are
rebound. Realhealth is good, primaryOPEN/fallbackCLOSED. The shared installer input
was restored exactly and its reservation removed.

Ten tests then passed against the actual installed module using only owned
synthetic SQLite/files, not production collection/history. The original source-
provenance literal refusal and missing launcher-digest alias remain recorded.
The alias was recovered from the ORIGINAL captured156-file map, not a refreshed
preimage; same archive and four original CLOSED fence/manifest bytes stayed exact
through guarded stage completion, without reinitialization. ARM's pre-execution
inherited-setgid refusal remains recorded; only four UID/inode/OWNER-bound owned
directories had that bit cleared, with no access widening or source mutation.

Required runtime: `/srv/nvme/agent-work/ac-next-20261106T1916Z-01a1/runtime`, with
primary `state/` and installed namespace pins. Keep the same root's
`rollback-runtime`/CLOSED `control/` for exact predecessor9b6cb7c0 current-data
rollback. These are active dependencies, not disposable scratch. The historical
private DB backup is NOT a restore input. No lobby/game/native/VM/Build/release
was changed by this backend deployment.

This is finite-output availability validation, not a general type/range or
reader-contract validator. Finite legacy rates can still be unprojectable by the
admin UI, as before. No full resource/fleet/nonparticipant/authenticity/hardware
or enforcement proof, threshold decision or historical rewrite is claimed.
