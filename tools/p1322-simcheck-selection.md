# P1322 - bounded store-only similarity selection

## Problem and scope

The collector rotated eligible replay IDs using `ORDER BY (id > cursor) DESC,id`.
Even a one-row admission could require sorting the full eligible set before any
file comparison. A finite synthetic50,000-row control exhausted the unchanged
default1,000,000 selected-read VM allowance with no admitted source, comparison or
stored result. The same database/reader with a larger SQL allowance ACTED with
an80-opportunity comparison; absence of work was not inferred from silence.

Source and peer selection now read the ascending ID range above the cursor, then
only the remaining lower/equal wrap. The two ID ranges are disjoint and preserve
the original rotation, eligibility, limit and pair-orientation exclusions. A wrap
read interruption returns no partial selection. SQLite read budget ownership,
progress-handler cleanup, the pre-comparison transaction boundary, short flush and
observed buffer hashes are unchanged. Separate selection reads are NOT a coherent
snapshot, work reservation or completion record.

Backend only. No new index/table/schema, native/API/pin/tag/Build, game program,
evidence format, raw collection, threshold, default allowance, badge, tier or
ranking change. No claim of a global hard time/RSS bound, unique concurrent work,
complete pair coverage, source freshness/legacy remeasurement or calibration.

## Verification

- Frozen old source: finite selection default allowance ACTUALLY stops before
  any file resolution/admission/result; high-allowance actual reader positive.
- Fixed source: same default allowance reaches the identical real80-opportunity
  pair. An independent SQLite writer commits during comparison, outside a read
  transaction. Exact compared-buffer hash capture and orientation preserved.
-217unittest cases run,0failures/errors,4known Windows SQLite/platform skips;
  separate legacy similarity script exits0 on the same unchanged source.
- New controls cover large source and peer selection, exact old-query order across
 48source/peer cursor/limit combinations, negative and deleted cursor positions,
  reverse stored-pair exclusion, actual low-budget second-range interruption with
  no partial result/advance, no unnecessary wrap, and legacy read-only schema.
- The prior peer-cap fixture depended on the removed full sort to exhaust its
  allowance. It now uses genuinely sparse eligibility and an actual readable
  selected peer: the same budget still interrupts, and its high-budget native
  positive still measures80opportunities. Neither gate nor allowance was relaxed.
- Fresh reader949checks/0failures. Current corpus546records retains344faulted
  records and7faulted views: NOTclean. Prior545record/168view bytes unchanged;
  the one new real record was actually parsed clean. No player file writes.

Initial test-fixture API/required-column/cursor-argument errors and a script-only
module discovery error are retained, not product failures or passing controls.
The initial reader observer deadline120s expired; the same source completed949/0
in136.6s under300s with direct private log capture. No timeout regraded as pass.

## Delivery state

Implementation and local qualification complete. Independent clean-commit reviews,
Linux/runtime qualification and actual guarded backend-only deployment are separate
steps; no deployment claimed by this initial note. Use the current collectors84
family on its actual installed base; do not ship main's unrelated work or add
previously inherited sealed modules to public Git. Keep a same-database fallback.
