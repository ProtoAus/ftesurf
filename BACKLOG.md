# BACKLOG.md

Open bugs and follow-ups that someone found and did not fix. One entry each:
what, where, how to check it, where it came from. Add what you find and leave;
delete the entry in the commit that fixes it. A "Known" paragraph in
ENGINE_PATCHES.md is a record, not a to-do -- put the item here as well.

## Ranking integrity

- **Patch 415's start-box prespeed hole is wider than its essay says.** Loading
  an idle/armed save that carries speed in a start box re-arms it (Build 47) with
  the save's speed. The essay claims 37 of 48 regions fail safe on `%.4f`
  rounding; a hop beats that (first scan sets the latch -1, the hop lifts the
  point into the zone, SV_TimerArm clears the load's taint). Falsifier:
  bhop_eazy, armed save with speed, load, `+jump`, `cmd timer` -> `armed,
  practice 0`. sv_saveloc.qc SV_SaveLocLoad (the Build 47 gate). Patch 428 review.
- **A FINISHED save in the next stage's box keeps it as its pending arm**, so
  leaving the box after a load is a clean stage run at the saved speed, reusable.
  SV_SaveWriteState writes `pendarm`, SV_SaveApplyState restores it. Patch 428 review.
- **A running save whose rewind fails still resumes its clock, recording
  dropped** -- a stream prefix over SV_RecSnapshot's 256 MB cap, or a failed copy
  step. The fix is to end the run in SV_SaveApplyState's failed-rewind branch,
  which is Patch 426's -- give it its own patch and run p426ccl/p426cl/p426dcl.
  Patch 428 review.
- **Map triggers still touch a held (save-lock) body.** The engine skips touches
  only for `run_pmhold`; a func_bhop dwell fires OnActivate and writes a `bhop`
  warp record, push-once triggers are spent for everyone. The timer ignores it
  since Patch 428 round 6, the side effects remain. Patch 428 review.

## Performance

- **A 999-save rescan is synchronous: 157 ms on the Pi** (profile_ssqc,
  p428cl). Once per player per map, plus once per reconnect with another
  certificate -- alternating two certificates with 999 saves each is a
  player-ordered stall. Half is the directory walk (one search_begin), so the
  fix is an index file or an incremental scan, not a tweak. sv_saveloc.qc
  SV_SaveLocScanBlk.
- **A 999-row delete-all takes ~5 s** (~3.5 ms per row on the Pi: FS_Remove
  re-walks every search path to update the name hash). It sweeps 2 rows a frame
  and is harmless, just slow. Engine fs.c FS_RebuildFSHash_Update.
- **A save-state rewind reloads the `.view` with buf_loadfile** (cl_replay.qc,
  the reattach after a rewind): VFS_GETS reads a byte per VFS_READ and Windows
  maps only files up to 5 MB (fs_win32.c:480), so a sidecar past 5 MB (~28 min of
  run at 2.93 KB/s) stalls ~2 s per MB.  Evidence code: Watch_BufLoad's fgets
  form drops every `\r` where VFS_GETS drops one, so swapping it needs its own
  review.  The engine fix (a buffered VFS_GETS) helps every caller.  Patch 431.

## Features / releases

- **Patch 427's client half is not in a release.** Clients quote `download`;
  until players update, the lobbies' server half is what lets them join maps
  with spaced sound names. Ships with the next `release.ps1 -Bump patch`.
- **Only `2` is drawn early (Patch 430).** 3/4/5/6 move the cursor and load in
  one server step and their target row is not published; the release after a
  hold still waits a round trip for the server's unfreeze (the second `prederr`
  line on each load).

## Cosmetic / low

- A board line's stage window (cl_watch.qc Watch_LineJobWindow) differs from the
  replay's (Watch_WindowFind) on a file with no `stagepost` for the stage: it takes
  the LAST `stage seg` record where the replay takes the one before the first
  `stage seg+1`.  Rows with Online_RowLeg > 0 always have one; only old files
  opened another way can differ.  Patch 433 review.
- The replay line's alpha ramps from 1 to the `ahead` alpha across the one sample
  segment after the playhead instead of stepping (cl_lines.qc Line_Feed).
- cl_chat.qc Chat_Draw says its shadow is "like the rest of the HUD's text"; no
  other HUD text is shadowed (HUD_Text draws plain).  The shadow costs ~1.5 us a
  row (a second drawstring, measured 2.0 -> 3.5 us for 62 chars).

- `Server permissions deny downloading file "package/maps/<map>.bsp"` on joins:
  the server advertises the map's BSP as a package and SV_AllowDownload refuses
  non-pk3 packages. The advertising side was not traced.
- A QW (engine) spectator receives the tracked player's cursor-save stats
  (STAT_FS_SLORG/SLANG, Patch 430) -- no more than the live position it watches.
- The release packet's ticks count as frozen (SV_TimerFreezeFrame); held runs are
  practice, so no board is affected.
