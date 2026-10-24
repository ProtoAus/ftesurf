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

## Review and delivery

The initial two independent source reviews completed; the predicate review's
arming blocker is implemented and natively reproduced/corrected. Both bounded
corrected-source reviews report no remaining blockers. The parent recomputed
the reviewed file's byte hash and it matches the frozen source; read-only
reviewers explicitly did not independently compute byte hashes. Reader checks
are reused across the arming-only delta because neither reader code nor
historical recording inputs were changed.

Delivered 2026-10-24 UTC: both Windows server DAT/LNO pairs at 10:36:43Z;
Pi's twelve lobbies verified at 10:59:20Z. Distinct public compositions preserve
the actual cohorts: Windows `b27a76f0` from pre-presence `c31ebc97`, Pi
`adecccc5` from compatible `7ebaca8b`. Both controls reproduce their actual
installed server predecessors byte-exactly; only the reviewed save module and
metadata change. The Pi candidate server equals the reviewed main artifact,
and its client remains byte-identical to the existing fleet.

The existing build-Pi entrypoint ran from the clean Pi composition with an
owned non-live Windows output sink and no force flag. All twelve actual UDP
rosters and directory rows were empty at the boundary. Stage/destination hashes
and ordinary .prev checks pass; earlier .prev history is retained. Twelve new
active service PIDs, twelve actual status replies and twelve directory rows
confirm fresh live bootstrap. The actual canonical serving native-clock witness,
not the superseded P958 snapshot, retained all eight native/reader dependency
hashes. No backend transaction was reused or changed. The Pi invocation did not
change either real Windows install.

Preserved: existing client/menu/native binaries, reader/backend, configuration,
player data and native pin/tag. No Build bump or public release. Owner HUD/ghost
acceptance and real cold/signed stage-posting acceptance remain unclaimed;
lextest.md has the small manual check. The separate older-save compatibility
array failure remains in BACKLOG.md. This patch does not complete the broader
project plan.
