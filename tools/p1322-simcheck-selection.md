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
  Linux Python3.11 runs the same217cases with0failures/errors/skips. Separate
  legacy similarity scripts exit0 on both hosts with the same module bytes.
- New controls cover large source and peer selection, exact old-query order across
 48source/peer cursor/limit combinations, negative and deleted cursor positions,
  reverse stored-pair exclusion, actual low-budget second-range interruption with
  no partial result/advance, no unnecessary wrap, and legacy read-only schema.
- The prior peer-cap fixture depended on the removed full sort to exhaust its
  allowance. It now uses genuinely sparse eligibility and an actual readable
  selected peer: the same budget still interrupts, and its high-budget real-reader
  positive still measures80opportunities. Neither gate nor allowance was relaxed.
- Fresh reader949checks/0failures. Current corpus546records retains344faulted
  records and7faulted views: NOTclean. Prior545record/168view bytes unchanged;
  the one new real record was actually parsed clean. No player file writes.

Initial test-fixture API/required-column/cursor-argument errors and a script-only
module discovery error are retained, not product failures or passing controls.
The initial reader observer deadline120s expired; the same source completed949/0
in136.6s under300s with direct private log capture. Initial Linux verification
packaging omitted the reader's existing heldmeta dependency; supplying that exact
committed dependency made the same source217/0/0. No failure regraded as pass.

## Delivery — 5 November 2026

Both fresh independent source/evidence reviews completed without findings. Public
feature publication b5e688ca preserves concurrent published work. Actual qualified
backend source `55370fb603c326af1f23791b65399e79d7184f5d` (published branch
`backend-gen-p1322`) applies ONLY this exact module delta to the previous actual
live966781a4 base. Main's unrelated work was NOT deployed, and the two previously
inherited sealed modules remain frozen inherited bytes, never added to public Git.

- Both actual frozen84-file primary and same-data fallback cohorts qualified in
  CLOSED fences with real fixture gunicorn processes, core schema26, six negative
  controls and correct accepted-OPEN/drained-CLOSED lifecycle.
- At12:38:28UTC the guarded backend-only cutover accepted the primary. Only
  simcheck.py changes; the other83runtime files, three control/config files and
  three declared external origins remain exact. Four cron routes rebound and
  foreground MOMrequests is active. Old fence CLOSED/new primary OPEN/fallback
  CLOSED. No game program, native image or lobby restart.
- Existing44table schema/nonchurn counts and eight identity-table hashes preserved
  at the closed cutover boundary, including existing event/activity/inventory
  components. Consistent1,358,684,160-byte historical private backup retained;
  fallback uses the SAME live database. No old data restoration or schema upgrade.
- Actual service namespace verified: five immutable pins and both runtimes RO;
  state/data/log roots RW; create/fsync/rename/unlink preflight passed. The existing
  protected installer restored the shared ingress and released only its own token.
  No maintenance reservation remains. Keep the active runtime root while any
  namespace/launcher/cron/process references it: it is NOT disposable scratch.
- Read-only12:38:33UTC audit verified156bound files/origins, declared route remaps,
  exact runtime/control/external closure and healthy primary. Initial health had
  one discovered lobby during startup; at12:40:34UTC fresh direct health reports
  ok=true/lobbies12 and all12actual lobby units are active. No healthy redeploy.
- Normal collector follow-up verifies all four exact-generation cron bindings;
  two existing logs had post-cutover writes. No extra collector/receipt job or
  raw capture was manually run. This is not a live50000-row performance result or
  complete fleet pair-coverage claim.

The first packaging precheck rejected inherited setgid directory mode2700 against
its exact0700contract. Only the verified owned, not-yet-live top directory was
set0700; no recursive permission change or predecessor change. An initial receipt
readback used the wrong filename after a SUCCESSFUL namespace install; the actual
producer's namespace-complete/attempt records proved restoration/release. Neither
failure was bypassed, called a pass, or followed by a repeat healthy installation.

No unchanged-byte claim is made for an unrecorded default env-file preimage.
Work reservation, global hard limits, snapshot consistency, freshness/legacy
remeasurement, wider calibration and the deferred general writer audit remain
separate open work; this patch completes only the bounded-selection gap above.
