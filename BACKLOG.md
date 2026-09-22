# BACKLOG.md

Open bugs and follow-ups that someone found and did not fix. One entry each:
what, where, how to check it, where it came from. Add what you find and leave;
delete the entry in the commit that fixes it. A "Known" paragraph in
ENGINE_PATCHES.md is a record, not a to-do -- put the item here as well.

## Ranking integrity

- **A prespeed start-box load still arms CLEAN on the 6 regions where `%.4f`
  rounding hides the zone** -- Patch 435 answered the velocity where Build 47's
  gate can fire (`tools/census/startdest.py`: 29 of 35 shipped regions with an
  authored teleDestPos), and on the other 6 -- 3 maps, bhop_eazy,
  kz_bkz_goldbhop_v2, surf_friday -- SV_ZoneStartAt answers -1, so neither the
  gate nor Patch 435's row-speed condition is reached. THERE THE HOP IS THE
  ROUTE, and only on a non-bhop mode: `cfg/test/p435mode.cfg`
  (`python tools/p435pre.py --arm mode`) measures a prespeed load + `+jump` with
  `sv_gamemode surf` arming at z 106.9 against a slab bottom of 64.03125 and
  reading `arm zone 0`, `practice 0`, `class: clean`. `cfg/test/p435hop.cfg`
  (`--arm shipped`) measures the same gesture in bhop mode NOT laundering: the
  jump starts the run from the restored ARMED state and SV_TimerTryArm's
  `run_t_bhopjump` branch refuses to arm an attempt already RUNNING. The backlog
  entry this replaces claimed the hop beat the rounding everywhere; that is now
  measured false on bhop maps and true on the rest. The fix has to answer the
  velocity where the gate cannot see it: either zero the inherited speed at a
  start-box placement under a TOLERANT box test (body AND the hold's
  `rec_sl_holdvel`, or the release hands it straight back), or a load-scoped mark
  SV_TimerArm refuses to launder while it stands -- cleared by the body being
  slow, NOT while `rec_sl_hold`, and never at SV_TimerArm itself, because on a
  surf map flying into a start box arms you clean at speed by design (Patch 415's
  essay) and a speed test there would taint every honest re-entry.
  sv_timer.qc SV_TimerTryArm / SV_TimerArm, sv_saveloc.qc SV_SaveLocLoad.
  Patch 435.
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
