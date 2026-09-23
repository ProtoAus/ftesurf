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
  only for `run_pmhold`; push-once triggers are spent for everyone, and every
  other trigger that writes velocity does so into a body nobody is steering. The
  timer ignores it since Patch 428 round 6, the side effects remain.
  MEASURED AND PARTLY CLOSED: the func_bhop dwell the entry named does NOT fire
  on a held body (a save-lock hold is MOVETYPE_NONE, the mover runs PM_NONE for
  it, PM_NONE clears FL_ONGROUND and nothing writes .groundentity again, so
  SV_BhopFrame reads `ground 0` on every held frame and the dwell never arms --
  `cfg/test/p439cl.cfg`'s route measured it, and the one-shot print it needed is
  `bhop frame first: ground 0 isbhop 0 movetype 0 slheld 1`). The half that is
  still open is the triggers a HELD body is already touching, and the
  push-once spend: those need the engine's `run_pmhold`-style skip to cover a
  save-lock hold too, which is an engine change.
  sv_entities.qc SV_BhopFrame, engine sv_user.c:8097 (MOVETYPE_NONE -> PM_NONE),
  sv_user.c:8887 (.groundentity written only when pmove.onground).
  Patch 428 review.

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
  other HUD text was shadowed when that was written (HUD_Text drew plain).
  Patch 440 gave the mono face an optional ring and shadow of its own, so the
  sentence is history rather than a contrast; the cost note stands.
  The shadow costs ~1.5 us a row (a second drawstring, measured 2.0 -> 3.5 us for
  62 chars).

- **Console notify on screen tints unrelated HUD text to the console's ^7 white
  when that text is drawn in extra passes.** engine/gl/gl_font.c's font batch
  colour meeting engine/client/console.c's Con_DrawNotify.  Found by Patch 440's
  arm (cfg/test/p440font.cfg, tools/p440font.py): with notify up (con_notifytime's
  default 3) and hud_font_outline 1 or 2, the speedometer's 48 px Bebas zero drew
  at (224,226,234) -- consolecolours[15], engine/client/console.c:181 -- with
  identical glyph coverage, 410 changed pixels, while every other Bebas and
  Roboto block in the frame stayed put; the same arm with `con_notifytime 0`
  grades 0.  Needs all three at once: notify on screen, this patch's extra
  drawstring passes, and a busy HUD -- a speed-only and a speed+mapinfo cfg never
  showed it, the full arm (debug + timer + energy + mapinfo) always did.  The
  mod's own harness therefore sets con_notifytime 0.  FALSIFIER: delete that line
  from p440font.cfg and grade the SPEED region -- 410 changed pixels in states
  1/2, 0 with it.  First read as glyph-atlas corruption from a second baked font
  slot; withdrawn in sh_font.qc's Patch 440 essay and in the arm's RESULT block.
  Patch 440.

- `Server permissions deny downloading file "package/maps/<map>.bsp"` on joins:
  the server advertises the map's BSP as a package and SV_AllowDownload refuses
  non-pk3 packages. The advertising side was not traced.
- A QW (engine) spectator receives the tracked player's cursor-save stats
  (STAT_FS_SLORG/SLANG, Patch 430) -- no more than the live position it watches.
- The release packet's ticks count as frozen (SV_TimerFreezeFrame); held runs are
  practice, so no board is affected.
