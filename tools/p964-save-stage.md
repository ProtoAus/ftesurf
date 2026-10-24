# Patch 964: restored running-stage cursor

## Problem and source change

`SV_TimerSpawn` clears `run_st_seg`. `SV_SaveApplyState` restores a saved
running leg, but its old reopen condition read that cleared, previous cursor.
A successful retry on a fresh entity could therefore keep no stage slice open.

The loader now tests restored timer state and segment bounds, then calls the
existing `SV_StageOpen` after the existing retry/resume append. Dirty, stitch
and cheat restoration stays beneath that call. There is no new recording format
or change to clean/practice eligibility.

Independent review found a newly reachable persistent-arm regression: the
packet stage-arm resolver excludes segment zero and stage-only runs, whereas
`SV_StageOpen` arms every opened slice. As ordinary run start does, the loader
now clears that arm flag for those two already-running contexts. Later segments
of full-track runs retain normal packet-resolved arming.

## Verified scope

- Existing NoDeploy/Jobs8 build: server, client and menu, zero compiler warnings.
- Actual dedicated native QC executes production save parsing, restore and
  stage-open code. The old predicate successfully restores but leaves the
  fresh entity's stage cursor unset. The candidate opens its restored segment
  with its anchor after an acting production retry-append call.
- The initial candidate's arming regression was reproduced, not merely inferred.
  Native before/after checks cover later full-track stage, opening leg, and
  stage-only run. The correction retains arming for the first and clears it for
  the latter two; all three restored segments and post-append anchors are checked.
- Recorder rewind and writes are acting test stubs, not real recording IO.
  These checks are NOT cold reconstruction, native movement, signed receipts,
  posted stages, network-client behavior, or human HUD/ghost acceptance.
- Reader suite: 924 checks, zero failed. Normal runs corpus: 430 recordings,
  294 pre-existing faulty files, matching the documented baseline. Reader source
  is unchanged. The corpus is not claimed clean or historically reclassified.
- The earlier 90-second suite timeout is retained, not counted as a pass; the
  same suite completed under an adequate limit. A separate broader sweep stopped
  on a protected existing save prefix. Nothing was removed or called clean;
  save-prefix coverage is not claimed by the successful runs-only sweep.

## Pending delivery gates

The initial two independent source reviews completed; the predicate review's
arming blocker is implemented and natively reproduced/corrected. Both bounded
corrected-source reviews report no remaining blockers. The parent recomputed
the reviewed file's byte hash and it matches the frozen source; read-only
reviewers explicitly did not independently compute byte hashes. Reader checks
are reused across the arming-only delta because neither reader code nor
historical recording inputs were changed.

No live deployment, owner acceptance, Build bump or public release is claimed.
The native commit/tag pin is unchanged. The separate older-save compatibility
array failure is tracked in BACKLOG.md, not silently included in this fix.
The broader project plan is not marked complete by this individual patch.
