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
  (`--arm shipped`) tried to measure the same gesture in bhop mode and DID NOT
  DEMONSTRATE it: its own control (H3, the at-rest save loaded and jumped) came
  back tainted, which is verbatim that cfg's `FALSIFIED IF`, because on
  bhop_eazy's shipped zones no start-box load arms clean at all -- the rounding
  above. So on a bhop-mode map the question is OPEN. The mechanism that would
  answer it is readable in the code (SV_TimerTryArm's `run_t_bhopjump` branch
  refuses to arm an attempt already RUNNING, so the jump starts the run from the
  restored ARMED state instead of arming it) but it is not measured, and the
  entry this replaces claimed the hop beat the rounding EVERYWHERE, which is
  false only for the surf-mode half. A SOUND ARM is p435hop's gestures in bhop
  mode with `cfg/test/p435.zones.json` staged so the control can arm clean -- the
  same fixture p435pre and p441void use -- or one of the 6 exposed regions'
  own maps. `tools/p435pre.py --arm shipped` now exits 1 with NOT DEMONSTRATED
  rather than grading H3 against the failed reading (Patch 441). The fix has to answer the
  velocity where the gate cannot see it: either zero the inherited speed at a
  start-box placement under a TOLERANT box test (body AND the hold's
  `rec_sl_holdvel`, or the release hands it straight back), or a load-scoped mark
  SV_TimerArm refuses to launder while it stands -- cleared by the body being
  slow, NOT while `rec_sl_hold`, and never at SV_TimerArm itself, because on a
  surf map flying into a start box arms you clean at speed by design (Patch 415's
  essay) and a speed test there would taint every honest re-entry.
  PATCH 442 CLOSED THE VERTICAL HALF of the gate's blindness, which is not the
  same as closing this: SL_RowSpeed measured horizontal speed only, so a save
  taken MID-JUMP inside a start box (vz +302, nothing horizontal) read as at rest
  and laundered -- measured both ways, `cfg/test/p442jump.cfg`. The gate can no
  longer be told a rising body is at rest, and `sl_list` no longer prints such a
  row as `0 u/s standing`. A load carrying speed still hands that speed back, as
  a segmented run, so the placement answer above is still the open item.
  AND PATCH 443 CLOSED THE GROUND HALF, also not the same as closing this: the gate
  now asks whether the row was standing on anything (SL_RowGrounded, the mover's own
  probe plus its quadrant retry), so a body hanging at rest inside the slab no longer
  arms clean. All three gate on the ROW; none of them answers the question this entry
  asks, which is what the PLACEMENT should do with a speed the gate has decided not to
  launder. sv_timer.qc SV_TimerTryArm / SV_TimerArm, sv_saveloc.qc SV_SaveLocLoad,
  SL_RowSpeed, SL_RowGrounded. Patch 435, part-closed by 442 and 443.
- **`sl_save` IS NOT REFUSED UNDER THE REPLAY PIN, so an at-rest row can be
  manufactured anywhere in mid-air.** `SV_SaveLocCreate` refuses a save under
  `run_pmhold` (spectate, sv_saveloc.qc:2354) and under `rec_sl_hold` (the save-lock
  hold, :2362, Patch 428 round 6) and NOT under `rec_wt_hold` -- and the replay pin is
  the same freeze: `SV_WatchHold` sets MOVETYPE_NONE and zeroes velocity (:3051-3055),
  which that function's own table states beside the save-lock hold's identical line.
  `rec_watch` is a plain client stringcmd with no check that a replay is even open
  (sv_player.qc:945). So `cmd rec_watch 1; cmd sl_save; cmd rec_watch 0` on ONE bind,
  pressed while airborne, writes `velocity 0.0000 0.0000 0.0000` beside a mid-air
  origin: Patch 435's speed gate reads that row as at rest.
  WHAT IT IS ACTUALLY WORTH, checked after the review ranked it first, because the
  review read round 1 of Patch 443 and the answer changed under it: the airborne half
  is now refused by SL_RowGrounded, so the row buys a clean arm only where the placed
  body is also STANDING on something inside a start slab -- which is a position the
  player could have walked to. What is left is not free height, it is a row that LIES:
  `state.txt` asserts velocity 0 for a body that was moving, so the row's own evidence
  is false, `sl_list` prints it as `0 u/s standing`, and Patch 435's gate is being
  answered by the pin rather than by the save. Still worth the one line -- the same
  refusal `rec_sl_hold` already has, and `SV_GhostSet` needs nothing (:3085 says why) --
  and worth an arm, because "the gate that stops it is a DIFFERENT patch's" is the kind
  of load-bearing accident this file exists to write down. Patch 443 review, cheater
  lens, with the worth re-derived here.
- **`SV_TimerFrame`'s no-zone-tests guard misses the replay pin too.** It guards
  `e.rec_sl_hold` (sv_timer.qc:12370) and `e.rec_gh_on` (:12377) and not
  `rec_wt_hold`, so the occupancy scan can produce an ARM EDGE on a body frozen by
  `rec_watch` -- SV_TimerArm, which zeroes run_t_flags. The Patch 428 round 6 comment
  at that site applies verbatim, one pin over: fall into a start box, pin on the entry
  packet, hang there with the clock frozen for as long as you like, unpin and fall from
  rest. `SV_WatchRelease` (sv_saveloc.qc:3004-3020) restores only the movetype and
  never hands velocity back, unlike SV_SaveLocRelease, so this is worth the hang
  rather than a speed. Same review.
- **The hopped-start rule's forgiveness is PRICED, not free, and one box re-entry
  launders it completely.** `run_rearmhop` takes `run_t_hopped` back after 0.25 s of
  ground dwell (sv_timer.qc:10141), which at `sv_friction 4` costs about a third of the
  chain's speed -- so a chain re-arms clean at some speed rather than none. And leaving
  the start box and re-entering it calls SV_TimerArm (:11691 -> :10373), which zeroes
  run_t_flags, run_t_hopped and run_t_jumps and touches `.velocity` not at all:
  chain to speed, step out, step back in, walk out clean and fast.
  SV_SaveLocPickInZone's own essay already names the re-entry arm ("on a surf map
  re-entering one while running ARMS you outright"). Pre-existing and independent of
  saves, and it bounds what Patch 443's startok half buys. Same review.
- **The retry placement is a second copy of the start-box velocity restore, with no
  gate on it at all.** `SV_SaveApplyState`'s retry branch places the body from the
  file's `origin`/`velocity` (sv_saveloc.qc:1194-1210) and restores the flags
  verbatim (:1395) -- no SV_TimerStitched, no SL_RowSpeed test, no SV_ZoneStartAt
  test, no `sl_voided` check, no demoted re-scan. Patch 442 hardened SL_RowSpeed,
  which has exactly one caller: the SV_SaveLocLoad gate. So: re-enter your own start
  box while RUNNING (with `run_rearmstops 1` SV_TimerTryArm re-arms without zeroing
  velocity), `retry` there, and the restart hands back ARMED + clean + that velocity,
  up to `sv_maxvelocity`. Prespeed injection into a clean armed attempt, repeatable.
  Its only brake is that `retry` refuses with more than one player on the lobby.
  Patch 441 review. STILL OPEN AFTER PATCH 443, and narrower by one clause: that patch
  turned the hopped-start rule back on for the restored ARM, so the chain the entry
  above describes is judged now -- but this entry is about the VELOCITY the placement
  hands back, which no gate on the retry path reads at all. The rule does not speak to
  a player who never jumps.
- **SL_RowGrounded's three residuals, and one of them is that a refusal leaves no
  artifact.** Patch 443 closed the airborne-row hole (the gate asked about SPEED and
  never about SUPPORT); what it does NOT do is the mover's last two steps. The probe
  grants a `func_slide` plane, which CategorizePosition demotes (engine
  pm_source.c:2119), and it grants a landing Patch 176 can refuse outright (:2131) --
  both fail-open, so they are a cheater's lens rather than a player's. Against that, an
  honest save wedged at rest on a ramp too steep to stand on keeps its taint, and the
  refusal is recorded ONLY in a dprint: nothing in `run_t_flags`, nothing in the save
  event stream, so a player who loses a rank to it leaves nothing a reviewer can read
  and the HUD shows `segmented` with no reason. A one-line `sprint` when the gate
  refuses on support alone would close the last one. sv_saveloc.qc SL_RowGrounded.
  Patch 443 review.
  THE func_slide ONE IS CONFIRMED FROM THE ENGINE SIDE, and it is worth knowing that
  someone already thought about it: engine world.c's forced-contents path deliberately
  excludes slide skins so that "every server-side trace (QC traceline/tracebox, THE
  SAVE-LOC FLOOR PROBE, run_eyeinfo)" does not fall through a slide brush -- so the
  probe is MEANT to hit it. The mover then declines a slide plane as ground
  (pm_source.c:2119), which this does not, so a flat slide (nz 1.0, no acceleration
  along it) or any `disablegravity` slide is a genuine at-rest airborne position the
  probe certifies. `func_slide` is `func_brush` -> SOLID_BSP and `pm_slide 1` ships.
  The height is normally reachable anyway, so the payoff is small; it is the one case
  where "at rest, probe says standing, mover says airborne" is constructible today.
  ALSO INVISIBLE THE OTHER WAY, from round 3: the first-jump forgiveness prints only
  under `developer`, so a rank KEPT because the rule declined to judge leaves no
  artifact either -- the mirror image of the refusal above. The `phase:` line in
  `cmd timer` has three free varargs slots and is where both belong.
- **The save-state LOADER never calls `SV_SaveOriginSane`, and a NaN origin passes
  every zone test.** Only the `!r` picker validates (sv_saveloc.qc SV_SaveLocPickInZone);
  `SV_SaveLocPlace` does `setorigin(e, rec_sl_org[r])` on whatever the row holds, and
  that function's own essay says a NaN satisfies every comparison a zone test makes.
  Patch 443's SL_RowGrounded is now a SECOND consumer of that unvalidated vector -- a
  tracebox from a NaN origin answers nothing useful. Gated by file ownership (a lobby's
  save root is server-side, and a listen server's times do not reach the public board),
  so it is hardening rather than a live hole; the fix is one call at the placement, the
  same one the picker already makes. Patch 443 review, round 3.
- **`sl_replay`'s taint does not survive the next arm, and it has no resume guard.**
  Patch 441 round 2 added SV_TimerPractice at the gesture so the command's safety is
  local rather than inherited from the cheatwatch blocks. It covers the attempt in
  progress only: SV_TimerArm re-derives the class from the level (sv_timer.qc:10566)
  and the retry/Multi-Session restores put back the saved flags, so `sl_replay` then
  `!r` clears it -- the same scope every other taint has, but the comment claims
  more. `SV_SaveLocReplay` also lacks the `run_ms_phase` refusal SV_SaveLocLoad has
  (sv_saveloc.qc:2299), so it can taint a run mid-resume. Patch 441 review.
- **`SV_RetryPoint` ignores `SV_RecDestream`'s return, so a failed destream writes a
  retry point that claims nothing was being recorded.** SV_RecDestream reads a
  streamed run's part file back into a buffer and returns FALSE -- after calling
  SV_RecDiscard -- when it cannot. SV_RetryPoint discards that answer and writes
  `state.txt` anyway, with TF_RECORDING clear and `reclines 0`, so none of Patch
  441's three clauses can see that this run WAS recording: with `rec_enable 0` the
  retry then carries a clean, rankable, RUNNING attempt across the restart with no
  recording. The fix is at the call (refuse the retry, or void the run) or by carrying
  "was recording" in the `rec_retry_armed` cvar the arming flag already travels in.
  Needs a stream -- a lobby, or `rec_stream 1` on a listen server, which is what
  would make it measurable. sv_saveloc.qc SV_RetryPoint, sv_timer.qc:5573.
  Patch 441 review, round 4.
- **`reclines` IS NOT EVIDENCE THE PREFIX FILE EXISTS, and nothing that reads it
  knows.** SV_RecWritePrefix returns its line count after `fopen`+`buf_writefile`+
  `fclose`, and QC cannot see any of those fail: the engine's PF_fopen allocates a
  MEMORY BUFFER for the write modes and the bytes leave at fclose, unchecked. Proved
  by staging a DIRECTORY on the retry slot's `run.rec` path -- the log shows the
  `fopen` succeeding, no `timer: cannot write` line, the directory still a directory
  at exit, and `reclines` positive in the state file with no prefix anywhere
  (`cfg/test/p441retryw.cfg`). So `SV_RecWritePrefix`'s `if (fh < 0)` branch is
  effectively unreachable for a filesystem fault, and every reader that treats
  `reclines > 0` as "there is a file" is trusting a count written before the bytes
  left the process -- Patch 426's reasoning about mark-0 saves, a verifier pairing a
  state file with a recording, and any future predicate tempted by `mark`. The fix
  wants the writer to confirm the file (a `fsize` of the path after fclose, or a
  `recbytes` it checks) before it reports a count. sv_timer.qc SV_RecWritePrefix,
  engine PF_fopen. Patch 441 round 6.
- **TF_RECORDING can be left set with no recorder behind it.**
  SV_RecRewindStream's two cold-failure exits destroy the old recorder and return
  FALSE without clearing the bit, and SV_RecClose early-returns on `!SV_RecLive`
  without clearing it either. Inside SV_SaveApplyState both arms discard, so it is
  always reconciled there -- but SV_MsRecAttach's buffer branch returns without a
  discard, leaving a RUNNING run with the bit set and no recorder, and a later
  `retry` then writes that stale bit into its state file where Patch 441's third
  clause reads it. The void is still right in substance there (evidence really was
  lost, a session earlier), so this is "right for the wrong reason" rather than a
  false accusation -- but the bit is being trusted as a fact about now.
  sv_timer.qc SV_RecRewindStream, SV_RecClose; sv_resume.qc SV_MsRecAttach.
  Patch 441 review, round 5.
- **The cancel message names the wrong reason for a run that never had a recording.**
  Patch 441's clause 1 cancels a RUNNING attempt with no recorder on a server that
  records -- deliberately, and even when the run never had one (armed while
  rec_enable was 0, the operator turns it on, the player loads). The player then
  reads `run cancelled (the save's recording could not be restored)`, which asserts
  something false: there was none to restore. One string, two causes. The fix is a
  second reason word at the SV_TimerVoid call, and it touches what seven arms grade,
  which is why it is here rather than done. sv_saveloc.qc, the failed-rewind branch.
  Patch 441 review, round 5.
- **`sl_list` prints the row speed as `%4.0f`, so the arming boundary is invisible.**
  A row carrying 0.6 u/s prints `1 u/s` and arms; one carrying 1.4 prints `1 u/s`
  and does not (SL_ARM_SPEED is 1). Patch 442 widened this column to the whole
  vector, which is what makes it worth reading at all -- and then it rounds away the
  one distinction a player would use it for. One decimal, or print the row's arming
  answer beside it. sv_saveloc.qc SV_SaveLocList. Patch 442 review.
- **The void's "leave the box and enter it" is satisfiable by the velocity the
  same load restores.** Patch 441 re-scans the occupancy latches after a failed
  rewind so a cancelled run does not come back armed; the remedy assumes the
  player has to travel. A save taken just OUTSIDE a start box with its velocity
  pointed in gives `zs_az = -1` at the re-scan and an arm edge on the next tick as
  the body coasts in -- a clean arm, then the clock starts on the way out at the
  saved speed. Reachable without any void at all (load a non-RUNNING save outside
  the box), so it is not new, but the patch's stated remedy is weaker than "you
  must walk". sv_saveloc.qc SV_SaveApplyState's void branch. Patch 441 review.
- **The Multi-Session resume continues a RUNNING run with no recorder, under a
  flag that is not a taint.** `SV_SaveApplyState` returns at `if (retry == 2)`
  BEFORE the failed-rewind branch Patch 434/441 guard, and `run_ms_norec` leaves
  the attempt running while marking it only TF_MULTISESSION -- which sh_defs.qc
  and surfd both state is not a class, not in FS_RunClass or TF_UNCERT, and not
  read by surfd's `style_of`/`certifiable`. So a clean run whose `.rec` stops at
  the pause can rank. The size trigger (`run_resume_recmb` 512 MB) is out of
  reach; the live route is the copy-failure branch. Same absence decision as
  Patch 441's, resolved the other way, in code 441's own reasoning covers.
  AND THE BUFFER PATH HAS ITS OWN: `SV_MsRecAttach`'s `if (!ok) return;` after
  SV_RecRewind leaves a restored TS_RUNNING run with no recorder and no void, since
  SV_SaveApplyState returns at `retry == 2` before the branch Patches 434 and 441
  guard. `run_ms_norec` is the only thing standing there. Named by the fourth
  review round. sv_resume.qc:531-537, 573, 678. Patch 441 review.
- **At `run_zone_hull 2` + `run_zone_hull_live 1`, Patch 441's latch re-scan uses
  the PRE-load hull.** It passes `SV_RunHullMaxs(e)`, i.e. `e.maxs`, but
  SV_SaveLocPlace only sets `run_forceduck` -- the engine applies it in the next
  pmove -- so the re-scanned latch and the next tick's scan can disagree by the
  17-unit stand/duck difference, which is an arm edge, which is the laundering
  back. Inert at the shipped defaults (occupancy is a point test there and the
  hull arguments are ignored), so this is a note against those two cvars being
  turned on, not a live hole. sv_saveloc.qc SV_SaveApplyState. Patch 441 review.
- **Map triggers still touch a held (save-lock) body.** The engine skips touches
  only for `run_pmhold`; push-once triggers are spent for everyone, and every
  other trigger that writes velocity does so into a body nobody is steering. The
  timer ignores it since Patch 428 round 6, the side effects remain.
  PARTLY CLOSED BY READING, NOT BY A MEASUREMENT ON DISK: the func_bhop dwell
  the entry named should not fire on a held body (a save-lock hold is
  MOVETYPE_NONE, the mover runs PM_NONE for it, PM_NONE clears FL_ONGROUND and
  nothing writes .groundentity again, so SV_BhopFrame reads `ground 0` on every
  held frame and the dwell never arms). That chain is checkable in the sources
  cited below. THE MEASUREMENT IS NOT REPRODUCIBLE, though, and the entry said it
  was: the one-shot print it quotes (`bhop frame first: ground 0 isbhop 0
  movetype 0 slheld 1`) exists nowhere in `src/` -- it was instrumentation that
  did not survive the patch -- and the only instance of that print anywhere in
  ftesurf/logs reads `movetype 3 slheld 0` (p439svAO.log:143), i.e. an unheld
  walking body, not a held one. To close it for real: put the dprint back in
  SV_BhopFrame behind `developer`, drive p439cl.cfg's route, and grade the line. The half that is
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

## Harness coverage

- **A failed rewind on a LOBBY is untested, AND BUILD 66 AND PATCH 434 DISAGREE
  ABOUT IT.** Patch 434's void and Patch 441's latch re-scan are measured only on
  a listen server (`p434rew.cfg`, `p441void.cfg`), where the recording is
  buffered in QC strings. A lobby STREAMS, and there SV_RecRewind refuses at
  `if (e.rec_rec_stream) return FALSE` (sv_timer.qc:5967) whenever the save
  carried no snapshot -- whose own BUILD 66 comment says "the run carries on
  recording from where it is; it just does not rejoin the saved prefix". Patch
  434's branch then discards that recording (fclose + fremove of the part file)
  and Patch 441 voids the run with it. One of the two is wrong and the difference
  is a cancelled lobby run.
  HOW LIVE, NARROWED BY READING (2026-09-26, while closing Patch 443; the entry
  said "live since the 434-438 deploy" and that is wider than the code allows).
  The BUILD 66 refusal is reached only when the save carried NO stream snapshot --
  `sb = rs_bytes` is 0, i.e. no `recbytes` key -- because a save WITH one goes to
  SV_RecRewindStream instead. SV_RecSnapshot returns 0 in five cases, and four are
  not live: no file handle, nothing recorded yet, `!checkbuiltin(fcopyrange)` (this
  fork HAS it, engine pr_cmds.c:12471), a part file over FS_RECCOPY_MAX (256 MB,
  out of reach like the Multi-Session 512 MB trigger), and a failed buf_create. So
  on a healthy lobby a mid-run save always carries a snapshot. What IS reachable is
  a save written by a PRE-375 build, which has no `recbytes` key at all, and a
  snapshot skipped for one of those five reasons. ALSO CHECKED AND SOUND: the
  queued-copy race the Patch 441 comment implies ("a positive count for a copy it
  has only QUEUED") cannot reach a load -- SV_RecRewindStream calls SV_RecCopyFlush
  before it reads anything (sv_timer.qc:5706). The arm is still worth building, for
  the pre-375 save and to settle which of the two behaviours is right.
  MEASURABLE LOCALLY:
  `rec_stream 1` forces streaming off a lobby (sv_timer.qc SV_RecStreams), so an
  arm can drive it on a listen server -- which is also what makes this a to-do
  rather than a guess. Both reviewers of Patch 441 named it independently.
  sv_saveloc.qc SV_SaveApplyState (the `SV_RecRewind` else branch),
  sv_timer.qc:5546 SV_RecWritePrefix / SV_RecSnapshot. Patch 441.
- **A load the server REFUSED still tells the client to reload its sidecar.**
  SV_SaveLocLoad prints `save: the state file could not be read` and falls
  through: the body has already been placed, no rewind was attempted, and
  `SV_SaveLocEvent(e, SLOP_LOADED, id)` is still sent. The client then truncates
  its live `.view` to that slot's remembered mark, so the sidecar gets a hole
  with no `resume` record in the `.rec` to explain the jump. Reachable through
  the TOCTOU Patch 428 r1 documents (the identity check reads the file, the apply
  re-opens it). The fix wants the refusal BEFORE the placement, which is what r1
  set out to do, and an arm that produces the race. sv_saveloc.qc SV_SaveLocLoad,
  cl_replay.qc Rec_ViewLoaded. Patch 441 review.
## Cosmetic / low

- The replay line's alpha ramps from 1 to the `ahead` alpha across the one sample
  segment after the playhead instead of stepping (cl_lines.qc Line_Feed).

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
