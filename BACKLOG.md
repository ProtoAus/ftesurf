# BACKLOG.md

Open bugs and follow-ups that someone found and did not fix. One entry each:
what, where, how to check it, where it came from. Add what you find and leave;
delete the entry in the commit that fixes it. A "Known" paragraph in
ENGINE_PATCHES.md is a record, not a to-do -- put the item here as well.

## Ranking integrity

- **A HOST-SIDE INABILITY TO VERIFY IS RECORDED PERMANENTLY AGAINST THE PLAYER'S
  RUN.** `pm_verify` answers PASS / HOLD / REFUSE, and REFUSE is documented as
  "cannot say, never a judgement on the run" -- but `surfd/sweep.py:236-238` sets
  `checked = 1` on any non-ERROR verdict while `pending()` (`:86-96`) selects
  `checked = 0`, so **a REFUSE is terminal**. The only retryable outcome is
  ERROR, which the engine cannot emit: it is produced solely by `sweep.py:270`'s
  "no VERIFY line" fallback. So verdicts that are genuinely about THIS HOST --
  Patch 463's `this server cannot state its own zone pin` and `this server's zone
  pin is too long to read`, and anything else describing the verifier rather than
  the run -- stick to the run for good, one admin click each to undo
  (`admin.py:1577`). Two things are needed: a verdict class `sweep` will retry,
  and a bulk re-check (there is none in this tree, which is also what makes
  Patch 463's fix prospective-only). This is the Patch 421/422 third-verdict
  shape one level out: the word is right and the plumbing collapses it.
  Found by Patch 463's evidence reviewer.
  **MEASURED 2026-09-28 AFTER THE DEPLOY: THERE IS NOTHING TO REPAIR, and the
  claim that there was is withdrawn.** The live board has 72 verdicts -- 49 PASS,
  21 REFUSE, 1 HOLD, 1 ERROR -- and **0 of the REFUSEs mention zones**. All 21 are
  unrelated and correct: 10 `a stage restart`, 9 `not exact: no seed or no full
  pin`, 1 `no input trace`, 1 `a ghost window`. So Patch 463 rescues no historical
  run, because none was ever refused for the reason it fixes; the deploy notes
  saying it "helps runs from now on and not the ones it would have rescued"
  overstated a backlog that does not exist. The DEFECT is still real and still
  worth fixing -- a host-side verdict sticking permanently to a player's run is
  wrong whether or not it has happened yet -- but it is not urgent, and a bulk
  re-check built today would have nothing to chew on. Measured against
  `/srv/nvme/surfd/data/surfd.db` on the Pi, not inferred.
- **`pm_verify` reads a QC return value through a `globalvars_t *` fetched BEFORE the
  call that produces it.** `sv_ccmds.c:5365` takes `pr_globals = PR_globals(...)`,
  `:5369` runs `PR_ExecuteProgram(svprogfuncs, fpin)`, and `:5370` reads
  `G_INT(OFS_RETURN)` through the pointer from before — while the sibling `else`
  branch at `:5384` deliberately RE-FETCHES it before use. If the re-fetch exists
  because the pointer can go stale across `PR_ExecuteProgram` (a progs reload or a
  realloc of the globals block), then the zone pin is read through a stale pointer
  and `SV_VerifyZonePin`'s answer is whatever was at that address. If it does not,
  one of the two is superstition and should say so. Either way the two lines
  disagree about the same rule, four lines apart. Dates to Patch 349
  (`dcd166259`, 2026-09-18) and is untouched by Patch 463; found by that patch's
  control-flow reviewer as out of scope. Needs its own round -- it is the
  verifier.
- **FIXED IN CODE, STILL GATED ON A DEPLOY, AND THE ALREADY-REFUSED ROWS DO NOT
  REPAIR THEMSELVES.** Engine Patch 463 (`0022cd190`) compares the fields instead
  of the path, so the 543 zone mirrors are unblocked as soon as the fleet runs it.
  Two things that are NOT done and do not happen by themselves:
  (1) `build.ps1 -Pi` restarts all 12 lobbies, so the deploy is the user's call;
  (2) deploying repairs nothing retroactively. `surfd/sweep.py:236-238` sets
  `checked = 1` on any non-ERROR verdict and `pending()` (`:86-96`) selects
  `checked = 0`, so a REFUSE is terminal. Every run already refused for this
  reason keeps its REFUSE until somebody issues the per-run `recheck`
  (`surfd/admin.py:1577-1579`), one at a time through the admin UI. **There is no
  bulk re-check in this tree**, and writing one is the missing half of this fix.
  Found by Patch 463's evidence reviewer.
- ~~**`pm_verify`'s zone pin includes the SOURCE DIRECTORY, so moving a byte-identical
  zone table from `online/` to `local/` refuses every existing recording for that
  map.**~~ Fixed by Patch 463; kept for the measurement, which is the reason the
  mirror was held. `sv_ccmds.c:5264` built `zbuf = "<zonesrc> <zonecrc> <zonerule>"` and
  `strcmp`s it against `SV_VerifyZonePin`'s answer; a mismatch sets
  `refuse = "a different zone table or rule"` and returns before replaying a tick
  (`:5267-5271`). But `zonecrc` is already a hash of the BUILT table -- type,
  track, seg, cp, z-band and every point at `%.3f` (`Zone_Hash`, sh_zones.qc:264)
  -- so the table is pinned twice and the second pin is a PATH. Two directories
  holding the same bytes are the same table, and saying otherwise is a false
  refusal on an honest run: the maximum-severity verdict for a file that is
  correct. Same shape as Patch 421's two-verdict angle check.
  THIS IS LOAD-BEARING FOR THE ZONE WORK. `tools/zoneinstall.py` can donate a
  zone file to the 66 builds that have none (done -- none of them could be timed
  before, so no recording exists to invalidate; measured, 0 of 66 carry BSP timer
  triggers), but it CANNOT mirror the other 543 maps into the editable folder
  until this is fixed, because every one of them currently records
  `zonesrc online` and 265 local recordings plus the fleet's corpus would stop
  verifying. Fix: compare `zonecrc` and `zonerule`, report `zonesrc` alongside as
  information. Touches the verifier, so it needs the independent review AGENTS.md
  requires before deploy. Note `local` already occurs in the wild -- Momentum's
  own install ships 14 files in its `zones/local`, which FTE's VFS resolves on
  that same path.
- **CONFIRMED BY MEASUREMENT: a pre-446 map could have made the server broadcast
  `rcon_password`. THE FLEET'S RCON KEY SHOULD BE ROTATED — an operator action, not a
  code one.** `Cmd_ExpandCvar` interpolates `$cvar` into the text AFTER the Cbuf split,
  so it can never start a second command (Patch 446 closed that class separately); what
  it does is expand a cvar INTO an allow-listed `say`. Round 7 read this in the engine
  and could not close it. `tools/p447dollar.py` + `cfg/test/p447dollar.cfg` now do, with
  two canaries so the real secret is never involved: a no-flags cvar and
  `rcon_password` holding `CANARY447RCON`. **On the pre-446 control BOTH EXPANDED** —
  so expansion happens at that exec level and the `CVAR_NOUNSAFEEXPAND` guard does NOT
  bite, because it tests `Cmd_IsInsecure()` against an exec level that is still 0 when
  the expansion runs. On a 446 build the command is refused and the question cannot be
  asked. qwprogs AB1F10EBDD196A3E fixed / 1F000116DB26CD5A control.
  **IMPACT:** the fleet has a real 48-character `rcon_password` in
  `game/ftesurf/cfg/lobby_local.cfg` (checked as a length, never printed), mtime
  2026-09-12, so there was a live secret behind the door. The door closed on the fleet
  at 2026-09-27 00:29:40 UTC when 446 deployed.
  **MEASURED MITIGATION:** 0 of 1438 shipped `Command` rows contain `$` or `%`
  (`tools/census/iocmd.py`), so nothing in the installed corpus exploited it — a crafted
  map would have had to be installed on the server first, which is not something a player
  can do. So this is "a live secret was reachable by a map for an unknown window" and not
  "the password leaked".
  **WHAT IS STILL OPEN HERE IS NOT CODE.** Rotating the key is the operator's call and no
  tool in this repo touches credentials. Worth doing on the reasoning that the window
  cannot be bounded from below: `lobby_local.cfg` predates every build in this series.
- **`tools/census/bsplib.py`'s `parse_ents` returns a dict, so every census that counts
  entity OUTPUTS has been under-counting.** A dict keeps only the LAST value of a
  repeated key and Source entities repeat output keys routinely. Round 7 measured the
  damage on two tools: `iocmd.py` saw 737 `Command` rows where the sound parse sees 1438,
  and `togglesolid.py` saw 184 maps with an Enable/Disable/Toggle output where the sound
  parse sees 226 — and that second one **overturned its own published conclusion** (grade
  3 went from 0 to 1). `parse_ents_pairs`/`read_pairs` now exist beside it and both tools
  use them. A second, independent bug travels with it: those tools split the I/O record
  on `,`, and VBSP >= v25 uses 0x1B ESC — `sv_entities.qc` picks the separator per value,
  the tools did not, and 144 of 1438 rows on 34 maps were invisible. Round 7, lens B.
  **THE REST OF THE DIRECTORY WAS THEN CHECKED AND IS CLEAN, so what remains is one
  file.** `onjumpstart.py` has neither bug — it builds its own pair list
  (`[v for k, v in kv if k == 'OnJump']`) and regex-searches the value for
  `basevelocity` instead of splitting it, so a separator it never uses cannot mislead
  it. `pushcensus.py`, `pushtilt.py`, `sscensus.py`, `sscount.py`, `ssd1.py` and
  `startdest.py` read only single-valued keys (classname, model, origin, spawnflags),
  for which a dict is the correct shape. `onjumpstart.py`'s remaining fragility was
  measured rather than left as a suspicion: it matches `k == 'OnJump'` case-SENSITIVELY
  and without a trim, where VBSP guarantees neither, so a differently-cased key would
  have been skipped and under-counted its "ZERO overlapping a start zone" result in the
  reassuring direction. **Scanned the raw entity lumps of all 1316 bsps: 1381 `OnJump`
  keys and EVERY ONE is spelled exactly `OnJump`** — no case variants, no leading space.
  So the match is sound on this corpus and the whole directory is now accounted for.
  Nothing is open here; the entry stays as the record of what was checked and how,
  because the next census written in this directory needs to know both bugs existed.
- **And on a LISTEN server, map I/O can reach `ClientCommand` after all — and it can
  destroy data, not just grief.** The server's own `say` is registered only
  `if (isDedicated)` (engine `server/sv_ccmds.c`), so on a listen server
  `localcmd("say !r\n")` runs the CLIENT's `CL_Say_f`, which forwards as that player's
  chat and reaches `SV_ZoneChatCommand`. **This falsifies the absolute claim** that map
  data cannot press `!r`, which AGENTS.md and Patch 445's own essays stated; all are
  corrected to the narrower true fact (`localcmd` cannot reach `ClientCommand` on a
  DEDICATED server, which is what the lobbies are). PATCH 446 DOES NOT NARROW THIS: a
  bare `say !…` needs no separator, so it still passes. `!r` itself buys a cheater
  nothing (the forced reset zeroes velocity and voids the run, and a listen server cannot
  submit to the board), but the bang table in `sv_player.qc` also holds **`!discard`,
  which destroys the player's parked Multi-Session run**, and `!rtv`/`!extend`, which
  cast the local player's vote. That is data loss on a server the victim operates.
  Round 6 lens B; extended in round 7.
- **THE CHEAPEST PRESPEED ROUTE IS UNTOUCHED BY THE HOPPED-START RULE, and the entry
  below over-claimed what Patch 445 narrowed.** The taint block is gated on
  `!run_t_startok`, and `run_t_startok` latches ~1 s after leaving the box or on the
  first ramp contact while RUNNING. After that no hop is judged at all, and a hop taken
  while RUNNING goes to `SV_TimerPractice`, whose three writes are ALL cleared by
  `SV_TimerArm`. So: leave the box cleanly, touch a ramp, bhop to any speed **outside**
  the box, re-enter the box (on a surf map `run_t_bhopjump` is FALSE so the arm is
  immediate and has no velocity gate), leave. `run_t_hopped` is never set, the arm
  launders the rest, and the run is clean, ranked and at full prespeed. Patch 445 raises
  the price of the in-box jump route to "`!r` and lose all your speed", which makes this
  one comparatively cheaper. Round 6, lens B; CONFIRMED in code, not measured. **Test:**
  drive it and read `cmd timer`'s `hopped 0` + `class: clean` after the second start.
- **Scope, stated because it bounds every entry in this family: the whole hopped-start
  rule is INERT on bhop-mode maps.** `cfg/lobby/mode_bhop.cfg` sets `run_starthop 0` —
  hopping out of the start is the sport there — and `SV_TimerMapInit` applies it from the
  map's own metadata, including on a listen server. That is roughly half the roster, and
  it means Patch 445 changes nothing for those maps. Round 6, lens B.
- **FOUR SHIPPED TRACKS HAVE AN END REGION THAT OVERLAPS THEIR OWN START, so a finish
  there should read as a CANCEL and the track cannot be completed at all.** MEASURED by
  `tools/census/endnearstart.py` over all 537 zone files: `agtricks` main,
  `surf_flyin_fortress` main, `surf_ethereal` b1 and `surf_quirky` b9 have an END whose
  prism is identical to or nested inside their segment-0 START, both polygons
  axis-aligned so the figure is exact (flyin_fortress' END is the same rectangle 0.011 u
  shorter; agtricks' is a 128x128 END inside an 1856x704 START). A fifth,
  `surf_pools` b2, is an AABB artefact — its rotated polygons do not actually overlap.
  MECHANISM, read but NOT run: in `SV_TimerFrame` the occupancy step runs BEFORE the
  event dispatch, so re-entering the START while `TS_RUNNING` reaches `SV_TimerTryArm`,
  and `run_rearmstops 1` (the shipped default) re-arms and prints "run cancelled (back in
  the start)". The dispatch then finds the state is no longer `TS_RUNNING` and
  `SV_TimerEvent` returns. FTESurf also ignores an END's `filtername` — nothing in `src/`
  reads that key — so the region loads unfiltered even where the mapper meant it not to.
  A map-caused denial: on those tracks no time can ever be set. Found by Patch 448's
  round 8 while checking whether the finish clear was reachable there; it is not, which is
  incidentally good for 448 and bad for the player. **Next step is to drive one of the
  four and read whether the cancel line appears** — the geometry and the control flow are
  established, the live behaviour is not.
- **A hopped-start tag survives a VOID, though no longer a finish.** Patch 448 fixed the
  finish half and **Patch 454 fixed 448's argument**: the finish no longer clears the tag
  outright — it ARMS a forgiveness that is taken once the player is grounded at or below
  `sv_maxspeed`, because `endnearstart.py` measured 12 shipped tracks whose END sits within
  64 u of their own START (4 overlapping, `surf_summer` main at 64) where 448's "the trip
  costs something" was false. So the clear cannot carry speed whatever the geometry.
  **The above-`sv_maxspeed` refusal is UNMEASURED** — every headless gesture walks at or
  below it, so the arm only ever exercises the YES branch. It needs a human finishing fast
  on one of those tracks, and `tools/p448fin.py` says so in block capitals.
  **WHAT REMAINS IS THE VOID PATH.** A cancel zone or a fall-off `trigger_teleport` goes
  through `SV_TimerVoid` → `SV_TimerIdle`, which deliberately does not clear (it is
  map-reachable, which is the whole reason 445 took the clear out of there) — so an
  attempt abandoned rather than finished still carries the tag into the next one. On the
  66 maps whose own reset teleport IS that path, that is the honest population.
  Unlike the finish, a void has no "you traversed the map" argument available: a cancel
  zone can sit next to a start box, so clearing there could carry a chain's speed. The
  shape that would work is a clear gated on the void having moved the player somewhere a
  chain's speed cannot survive, which is a harder predicate than 448 needed and wants its
  own patch. Round 6 lens C; finish half closed by 448.
- **Nothing on the client knows about the tag.** No `STAT_FS_*` carries `run_t_hopped`;
  the HUD's taint word comes from `STAT_FS_TIMERFLAGS` alone and `TF_PRACTICE` is not set
  until `SV_TimerStart`, so a player standing ARMED with the tag up reads `ready`. Round
  6 added a chat reminder on each later fluffed start, which is a mitigation and not a
  fix: the state is still invisible between attempts. A stat bit, or the `phase:` line's
  free varargs slots, is the shape. Round 6, lenses A and C.
- **The `.rec` records no trace of the hopped start, and the tag can now predate the
  recording by minutes.** There is no hopped/jumps/reason key anywhere in the grammar,
  the taint chain runs BEFORE `SV_RecOpen` by design, and the pre-start pad ring is 256
  samples ≈ 3.84 s. Under build 21 the tag could not outlive its arm, so residual
  `TF_PRACTICE` implied "the hop happened in this attempt"; it now means "at some point
  since the last `!r`, respawn or map change". **A reviewer at `/admin/runs` can see a
  practice-residual run whose recording contains no jump anywhere**, with nothing in the
  evidence supporting the class — which is CLAUDE.md's "a check that cannot measure must
  say so" and the file says nothing. An additive `.rec` record at the set costs no version
  bump. Round 6, lenses B and C. Also stale on the same account: `cl_timer.qc` and
  `sh_defs.qc` both claim bare practice has "exactly one live cause", and bare
  `TF_PRACTICE` is filed under the `stitched` chip, so the browser labels a hopped start
  "a save state was used".
- **A false hopped tag is no longer self-limiting, and there are more ways to earn one
  than the rule's comments admit.** The trigger is a `velocity_z` edge with a dwell test,
  and the dwell reads 0 whenever `run_t_groundsec` is 0 — which `pm_autobunny` guarantees
  for a held jump. Pre-445 a false tag healed at the next arm or after 0.25 s grounded;
  now it kills every subsequent run on the map until `!r`. **And `!r` itself does not
  reliably clear it: pressing it while still holding +jump re-tags within a tick**, so
  the one remedy fails for the gesture most likely to have caused the problem. Unmarked
  or under-marked upward-velocity writers found while checking this, all reachable while
  ARMED in a start box: `trigger_teleport` VelocityMode 3 (marks nothing and strips
  FL_ONGROUND without `run_pushlift`), `trigger_push` SF_PUSH_ONCE (the upward clip lands
  on the next command, after `run_pushed` is cleared), `trigger_setspeed` (marks only
  when `vel_z > 140`), Patch 409's stated residual, and a plain standable slope
  deflecting horizontal speed upward with no pad involved. Round 6, lens B. This is the
  blind-dwell entry below with teeth; fix it at the placement, and note that two earlier
  attempts at it failed review.
- **`SV_TimerMapInit`'s per-player loop is dead code.** `find(p, classname, "player")`
  matches nothing on a map change or `map_restart`: `SV_SpawnServer` runs `PR_Deinit` and
  re-allocates every client edict blank, and `classname = "player"` is assigned only
  inside `PutClientInServer`, which runs after the zone load the loop hangs off. So the
  `SV_TimerIdle(p)` and recorder resets in it never run. Harmless today (the edict is
  blank anyway) but the loop's comment asserts the opposite — "the player entity outlives
  a map change on a listen server" — and Patch 445 added a call into it on that premise
  before round 6 removed it. Pre-existing. The engine's `preserveplayers` path needs a
  `ClientReEnter` global this progs does not define. Round 6, lens A.

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
- **CROSSING THE SEAM BETWEEN TWO ADJACENT START REGIONS RE-ARMS SILENTLY, and 21
  shipped maps have such a seam.** `SV_ZoneOcc` is a POINT test at the shipped
  `run_zone_hull 1` while the start test `SV_ZoneIn` is the HULL, and the arm scan runs
  AFTER the start test in the same packet -- so on two abutting or overlapping arm-able
  regions, crossing the boundary flips `run_t_azone`, SV_TimerTryArm fires (its bhop
  guard needs TS_RUNNING/TS_FINISHED, so it does not stop this), SV_TimerArm zeroes
  `run_t_flags`, `run_t_hopped` and `run_t_jumps` and re-derives dirty from the current
  movetype -- and the clock CANNOT start, because the start test used the old armzone
  whose hull the body is still inside. Nothing is printed: SV_TimerClassSay needs
  TS_RUNNING. So a bhop chain that loops across a seam has its hopped-start taint
  cleared on every crossing. MEASURED over the 537 shipped zone files by simulating
  `az` and Zone_BoxInside: **21 maps** with a same-(track, segment) pair.
  **RE-MEASURED BY A COMMITTED TOOL IN ROUND 7** -- `tools/census/startrearm.py`, an
  independent census written because this number was quoted in deployed source and had
  no tool behind it. The 21 reproduces EXACTLY. The sub-count in this entry did not:
  it said 15 START/START and **it is 18** -- all fifteen named are real, and it missed
  df_cavernish, surf_gradient and surf_lt_omnific. Full split: 18 START/START, 5
  STAGE/STAGE, overlapping on the 2 maps that have both (21 = 18 + 5 - 2), plus 10
  further maps that touch only ACROSS legs (30 maps with any touching pair, 57 pairs).
  surf_gradient has all three kinds, which is why the old bucketing undercounted.
  surf_tequila's main start is four trapezoids tiling one frame, sharing three diagonal
  seams; a crossing keeps the hull straddling for 32 units, which is two packets below
  ~1000 u/s. The fix wants the arm scan to refuse a re-arm that changes nothing a
  player did -- an `az` flip between two regions of the same track and segment is not
  an arm -- or the hull test both sides. `sv_zones.qc`'s "SV_TimerArm is idempotent
  while armed" is the comment that stopped being true. sv_timer.qc SV_TimerArm,
  SV_TimerTryArm, the occupancy scan. Patch 443 review, round 4, cheater lens.
  **PATCH 445 TOOK THE HOPPED-START HALF OUT OF THIS**, which is the half that was worth
  anything to a cheater: the arm no longer clears `run_t_hopped`, so a chain looping
  across a seam stays tagged and only `!r` (velocity zeroed) forgives it. The silent
  re-arm itself is UNCHANGED and still zeroes `run_t_flags` and `run_t_jumps`, so this
  entry stays open on its own terms -- the seam is still a re-arm nobody asked for.
- **66 maps' own velocity-keeping teleports land inside a START region, which re-arms
  at whatever speed you arrive with.** `trigger_teleport_touch` with `VelocityMode`
  absent or 0 KEEPS velocity (a plain CS:S map has no such key), strips FL_ONGROUND,
  and calls SV_TimerWarped, which empties the 3.8 s pre-start padding ring -- the only
  trace of the approach that would have reached the `.rec`. Arriving from outside, the
  next scan is an `az` edge, so SV_TimerArm launders as in the entry above. MEASURED
  over 535 zoned BSPs (52,879 trigger_teleport entities): 66 maps have at least one
  velocity-keeping non-landmark teleport whose destination lies inside a START region.
  **RE-MEASURED BY `tools/census/startrearm.py` IN ROUND 7 and reproduces exactly**,
  including the 52,879: of those, 455 are landmark, 46,229 have a VelocityMode set, 6,195
  are velocity-keeping candidates, 148 have an unresolvable destination, and 1,616 land
  inside a START region across those 66 maps. The 46,229 exclusions are why the answer is
  66 and not 500 -- most shipped teleports DO set a mode, so this number tracks a mapper
  convention and wants re-running when the corpus changes
  -- surf_pantheon 197, bhop_4tele 257, surf_suburbia 204, surf_valpect 90,
  surf_tibet 69, surf_dynasty 60, surf_ambient 34, surf_ecosystem 17, surf_gradient 19,
  surf_wahey 6. Gesture: chain to speed anywhere, take the map's own reset teleport,
  arrive in the start box at full speed ARMED and laundered, leave. No cvars, no
  restriction on other players. Same review.
  **PATCH 445 NARROWED THIS THE SAME WAY** and it matters more here, because a teleport
  is the one path that carries the speed AND used to carry the forgiveness: the arm no
  longer clears `run_t_hopped`, so a chain built before the teleport is still tagged on
  arrival. What survives untouched is everything else -- the velocity, the stripped
  FL_ONGROUND, the emptied padding ring and the `run_t_flags` zeroing -- so a player who
  builds speed WITHOUT hopping (a ramp clip, a push) still arrives clean and fast. The
  entry stands; only the hop-chain variant of it is closed.
- **A ramp-clipped hop is neither counted nor judged.** `run_rampcontact` suppresses
  `jumped` in SV_TimerJumpWatch, so a hop whose rise came from a ramp clip never
  reaches the hopped-start test AND never increments `run_t_jumps`. On a start box with
  a ramp in it -- which is the shape of a surf start -- a player can build speed with
  clips the rule cannot see. Pre-existing and independent of saves; found while
  checking whether a count-based rule could replace the dwell, which it cannot for this
  reason among others. sv_timer.qc SV_TimerJumpWatch, the `jumped` edge. Same review.
- **A box re-entry still launders `run_t_flags`, though no longer the hopped start.**
  FIXED IN PART BY PATCH 445, and what remains is narrower than the entry it replaces.
  Leaving the start box and re-entering it calls SV_TimerArm (SV_TimerTryArm ->
  SV_TimerArm), which touches `.velocity` not at all -- so "chain to speed, step out,
  step back in, walk out fast" still works. What it no longer does is come out CLEAN:
  445 took `run_t_hopped` out of the arm's clear list, so the hop taint survives a
  re-entry and only `!r` (which zeroes velocity) takes it back. `run_t_flags` is still
  zeroed, so any TF_PRACTICE from another source is still laundered by the same edge --
  that is the 46-field overreach entry below rather than a hopped-start bug.
  SV_SaveLocPickInZone's own essay names the re-entry arm ("on a surf map re-entering
  one while running ARMS you outright"). Patch 443 round-4 review; narrowed by 445.
  **ROUND 6 CORRECTED THE NARROWING CLAIM IN THIS ENTRY, WHICH WAS OVER-STATED.** It is
  true only when the chain happens INSIDE the box while ARMED. Done outside the box --
  which is where anyone builds real speed, and which `run_t_startok` makes unjudgeable
  after about a second -- `run_t_hopped` is never set at all, and the re-entry still
  launders everything. See the "cheapest prespeed route" entry at the top of this
  section: that is the gesture people actually use, and 445 does not touch it.
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
  Patch 441 review. **STILL OPEN, AND IT IS NOW THE FIRST THING TO CLOSE IN THIS
  FAMILY.** The previous version of this line said Patch 443 "turned the hopped-start
  rule back on for the restored ARM, so the chain the entry above describes is judged
  now" -- FALSE, round 4 withdrew that half and `SV_SaveApplyState` still sets
  `run_t_startok = TRUE` for every restore. Patch 445 then closed the OTHER two
  prerequisites the withdrawal named (the save format carries `hopped`, and an arm no
  longer forgives), which leaves this entry as the single remaining reason judging a
  restored arm is pointless: the velocity the placement hands back is read by no gate
  on the retry path at all, and the rule does not speak to a player who never jumps.
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
  (Both engine citations above had drifted and are corrected in the source: the
  func_slide demotion is `pm_source.c:2102`, not :2119.)
- **AND IN PRODUCTION THAT dprint DOES NOT EXIST, so neither a refusal nor a GRANT is
  observable on the fleet.** `dprint` prints only when `developer` is set and
  `default.cfg` never sets it, so SL_RowGrounded's one and only record of what it
  decided is absent on all twelve lobbies. The same two-valued return also GRANTS the
  laundering, so every "cannot see" that resolves TRUE is an unlogged grant of a clean
  rankable attempt. This is the worst of the probe's residuals because it defeats the
  remedy for all the others -- you cannot audit a check whose output is compiled out by
  configuration. A `SV_CensusAdd`-style counter, or the `sprint` the entry above wants,
  would make it readable; the third verdict below is the real fix. Patch 443 round 5,
  lens B. sv_saveloc.qc SL_RowGrounded's dprint.
- **SL_RowGrounded has TWO verdicts where CLAUDE.md requires THREE, and this is the
  entry the rest of its family reduces to.** Embedded, a NaN row origin, a
  `SOLID_BSPTRIGGER` support, a floor deleted by `World_PortalCSG`, a brush disabled
  since the save was taken, and every moved movevar all collapse to the same `FALSE`.
  The repo's own lesson (Patch 421's angle check, 422's absent receipt, 424 twice) is
  that the fix is never a better threshold, it is the third answer -- here "the row
  cannot be judged", which must neither grant nor refuse. Note the polarity differs
  from 421's: this check's two-valued failure GRANTS rather than accuses, so the cost
  is a laundered run instead of a false fault. Patch 443 round 5, lens B.
- **`MOVE_NOMONSTERS` includes `SOLID_PORTAL`, and `World_PortalCSG` can delete the
  world's floor hit.** A row standing on real floor inside a portal's CSG volume reads
  `frac 1.000` and is refused -- a false refuse, conservative, but a distinct fourth
  way for the probe to mean "could not see" while saying "no". Also: the trace's content
  mask is selected from the passed entity's own solidity, so the call is correct only
  because a player is `SOLID_SLIDEBOX`; nothing in the signature says so, and a future
  caller handing it a non-player entity gets a different mask with no diagnostic. Both
  named in the source now. Patch 443 round 5, lens B. sv_saveloc.qc SL_RowGrounded.
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
- **The Build 47 gate's forced edge is a LATCH OF UNBOUNDED LIFETIME, not an edge, and
  the arm it authorises happens to a DIFFERENT BODY.** `run_t_azone = -1` is written
  after five conditions evaluated at load time against a body at rest. On a bare
  `sl_load` the arm lands next tick, which is what four paragraphs of the gate's essay
  describe. THE SHIPPING CLIENT DOES NOT SEND A BARE `sl_load`: `cl_saveloc.qc` sends
  `sl_load` and `sl_hold` together on one keypress, the hold re-places the origin every
  tick under `MOVETYPE_NONE`, so the latch sits there for as long as the key is held and
  the arm fires on the tick after the RELEASE -- after `SV_SaveLocRelease` has handed the
  saved velocity back. So the gate certifies "at rest, in a start box, standing" and
  then launders an attempt belonging to a moving body an arbitrary time later. Patch 435
  is where this wants fixing, not 443: the gate should re-ask at the moment it acts, or
  refuse to survive a hold. Patch 443 round 5, lens C. sv_saveloc.qc SV_SaveLocLoad.
- **The gate's `!= TS_RUNNING` admits `TS_FINISHED`, so loading a finished save in a
  start box ARMS OVER THE RESULT.** `SV_SaveApplyState` treats FINISHED deliberately and
  says so -- "there is nothing left to continue, only a result to look at" -- and the
  Build 47 gate one function later does not: its state test excludes only TS_RUNNING, so
  a restored FINISHED state passes, the edge is forced, and SV_TimerArm re-arms, taking
  `run_t_startseg`, `run_t_state` and the rest with it. The finishing time the save was
  taken to keep is replaced by a fresh armed attempt. The `run_t_bhopjump` branch in
  SV_TimerTryArm guards `TS_RUNNING || TS_FINISHED` together, which is what the gate's
  test should have matched. TRACED IN CODE, NOT MEASURED -- no arm loads a FINISHED save
  at a start box today, and that is the first thing to build. Patch 443 round 5.
- **The gate borrows 46 fields to clear five.** Its essay said "all six fields" and
  argued that reusing SV_TimerArm beats a parallel clear because the part is small.
  SV_TimerArm writes **46 distinct fields** (counted over its body: 25 `run_t_*`, 12
  `run_st_*`, the rest), so a load at rest in a start box runs all of them and only
  about five are what the gate is for. The conclusion still holds -- a parallel clear
  would drift -- but for the opposite reason, and the overreach is real: the arm also
  resets the stage machine, the checkpoint high-water mark, the PB lookup and the tick
  counters for a gesture whose whole claim is that you have not started yet. A narrow
  `SV_TimerLaunderStartLoad` that names its five is the shape; it needs the drift risk
  answered, which is why this is an entry and not a patch. Patch 443 round 5, lens C.
- **`SV_RecDiscard` has already thrown the recording away before the deferred arm clears
  `TF_RECORDING` for it.** Both run on the load path, in that order, so the arm clears a
  flag describing a buffer that no longer exists. Consistent today only by accident of
  ordering -- and `SV_SaveApplyState` already reads `wasrec` one function up precisely
  because this hazard bites there. An invariant that holds by ordering is a landmine:
  anything that moves the arm earlier, or the discard later, leaves the HUD claiming a
  recording with no buffer. Named at the gate now. Patch 443 round 5, lens C.
- **A togglable `SOLID_BSP` brush whose box reaches a start zone is a FAIL-OPEN, and
  ONE SHIPPED MAP IS A CANDIDATE.** `SL_RowGrounded` traces the world as it is at LOAD
  time and the save records nothing about the world at WRITE time, so: hover one unit
  above where a disabled brush's top face will be, inside a start slab, save at the
  apex, let the map's own button fire the `Enable`, load. The probe finds `nz 1.000` at
  `frac ~0`, grants, and the forced arm launders.
  **THE "NO SHIPPED MAP HAS ONE" CLAIM THIS ENTRY CARRIED IS WITHDRAWN.** It came from
  `tools/census/togglesolid.py`, and round 7 found that tool had the same two parser
  bugs as `iocmd.py`: it took a dict from `bsplib.parse_ents` (which keeps only the LAST
  value of a repeated key, and Source entities repeat output keys routinely) and assumed
  a comma separator where VBSP >= v25 uses 0x1B ESC. Both under-count, i.e. both made
  the census read more reassuring than the corpus warranted. Sound re-run, same 1316
  bsps / 535 zoned: **grade 3 (contained) is 1** -- `surf_legends`, `func_brush` named
  `health_small3`, reached by an Enable/Disable/Toggle output, contained in a start zone,
  overlap volume 4608. The self-check moved with it: 226 maps carry such an output (was
  184) and 276 brush entities are named by one (was 88).
  IT IS A CANDIDATE, NOT A FINDING: containment survives the AABB problem but does not
  show the brush's top face sits at a standable height inside the slab, that the Enable
  is reachable without the map's cooperation, or that a save can be taken at rest above
  it. **The next step is a live check on surf_legends** and it has not been done.
  The other grade-2 row is still the AABB trap in person -- `surf_hourglass`'s skybox
  shell, box spanning the whole map with its faces ~16000 u away. Patch 443 round 5,
  lens B; census corrected in round 7.
- **The save still carries no MOVER STATE and no MOVEVAR SNAPSHOT, though it now proves
  its BSP.** Patch 450 added `mapcrc` from `infokey(world, "*mapcrc")` and made the Build
  47 arm gate require a positive match, with three verdicts (no crc / wrong crc / proved)
  and a different message for each — measured both sides, `cfg/test/p450map.cfg`: the
  control laundered a save from a different bsp, the fixed build refuses it and still
  accepts a save taken on this install. **`map` stays write-only on purpose now**: the crc
  subsumes it, and one rule spelled twice is how they drift.
  **WHAT IS STILL MISSING FROM THE FORMAT:** the state of every mover at write time (a
  door or platform the row was standing on may be elsewhere now — the same family as the
  togglable-brush entry above), and the five movevars `SL_RowGrounded` judges a row with,
  which are pinned within an install but not across the write→read boundary a save is
  designed to cross. The crc closes the "different bytes under the same name" case; it
  says nothing about the same bytes in a different STATE.
- **The probe's five movevars are pinned within an install but NOT across the save's
  write -> read boundary.** All five are in `pms_lockedmovevars` under
  `pm_lockmovement 1`, so they are genuinely locked live -- but the canonical value is
  whatever `default.cfg` said at boot, and a save is explicitly designed to outlive
  installs. A `state.txt` written under the 72/54 hull FTESurf shipped up to build 40 is
  probed today with 62/45, and the row is judged by a rule the mover that wrote it never
  ran. The save would have to carry the five, which is the same "the format is missing a
  field" shape as the two entries above. Patch 443 round 5, lens B.
- **The dwell the hopped-start rule grades is BLIND after any placement into a fresh
  edict, and this is a LIVE defect rather than one the withdrawal avoided.**
  `run_t_groundsec` is 0 after a `retry` (the progs are re-initialised) and after an arm
  (SV_TimerArm deliberately does not reset it), and under `pm_autobunny` with the button
  held QC never observes `FL_ONGROUND` at all -- so the dwell reads 0, which means "a
  jump already taken". It was recorded as a reason Patch 443's withdrawn half was
  unsafe; round 5 showed it is reachable through the KEPT half too. Today it decides
  nothing only because the rule is off for a restored arm, so it sits one `startok` away
  from accusing an honest player of the one gesture the rule exists to permit. Fix it
  where it is caused -- at the placement -- not by widening the rule. Patch 443 round 5.
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
  THE SPLIT IS THE PREDICATE'S OWN CLAUSES, and the ARM ALREADY EXISTS -- both traced
  2026-09-26 so the work is a rewrite and not an investigation. `hadrec` or
  `retry && (flg & TF_RECORDING)` means a recorder really was there, so "could not be
  restored" is true; `SV_RecEnabled()` ALONE means the server records and this attempt
  never held one, which is the false case. Compute it once into a local and the void
  picks its word from that -- and the predicate becomes readable, which it is not now.
  cfg/test/p441twice.cfg's S2 is exactly the false case and already grades the string:
  measured, it prints `run cancelled (the save's recording could not be restored)`
  beside `recording 0` on an attempt restored a moment earlier that never held a
  recorder in this session. Nine cfgs and three drivers quote the string
  (p434rew.py, p439smoke.py, p441void.py's CANCEL), so the mechanical half is updating
  them to match either word and grading WHICH one at S2.
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

- **`SV_TrigPending`'s touch-bitfield clause goes blind above edict 32, and the fleet is
  configured at exactly 32.** `bit` is built only for `n < 32` and left 0 otherwise, so
  `(vbsp_touch_in | vbsp_touch_seen | vbsp_touch_out) & bit` tests `x & 0` and silently
  never fires (sv_entities.qc, `SV_TrigPending`). The `vbsp_touch_who` and `vbsp_iodelay`
  clauses still work, so the predicate DEGRADES rather than dying -- and the iodelay clause
  is the one covering the 0.06-0.09 s OnEndTouch window. `cfg/lobby/lobby.cfg` sets
  `sv_playerslots 32`: client edicts are 1..32, so `n` is 0..31 and every player is inside
  the mask today with EXACTLY zero headroom. Raise that for one event and player 33 loses
  the touch half of the test. It became a ranking concern in Patch 455, which made a
  forgiveness depend on the predicate; before that it only gated spectate entry. Fix is
  either a second word for 32..63 or a per-entity scan instead of a mask; the cheap
  mitigation is a refusal to raise `sv_playerslots` past 32 without doing the first.
  Found by a reviewer on 455 round 3, verified against the source and the cfg.

- **`run_t_hopsaid` IS ONE LATCH FOR TWO REMINDERS, and every site that clears it has to
  choose which one it is wrong about.** It suppresses both the hopped-start reminder and the
  `run_t_dirty` reminder. The ZONE_END arm deliberately leaves it alone, because clearing it
  re-opened a message about a taint the finish does not forgive (see the field's own
  comment); `SV_TimerForgiveHop` clears it, because that IS a forgiveness; and Patch 455's
  take clears it for the same reason as ForgiveHop. So the tree is self-consistent only
  because each site reasoned separately, and the next site will have to as well. The real
  fix is two latches -- the two reminders are about different taints and should not share a
  bit. Small, and it wants its own patch rather than being folded into a gate change. Cited
  by 455's take-site comment, which is why this entry exists.
- **A plugin's cvar flags are still masked down to CVAR_ARCHIVE for everything except
  CVAR_CHEAT and CVAR_SEMICHEAT.** Patch 460 widened `Plug_Cvar_GetNVFDG`'s `flags&1` to
  the restrictive flags only, because those can nothing but refuse a change. Still
  discarded, in the hl2 plugin alone: **`CVAR_SHADERSYSTEM` 25 times, `CVAR_MAPLATCH` 14,
  `CVAR_NOSAVE` 6, `CVAR_RENDERERLATCH` once.** So 14 cvars that say they latch to a map
  load do not, and 25 that say a change flushes shaders do not. `mod_hl2.c:1480` reasons
  at length about `hl2_propcollision` being MAPLATCH and it never was; `cl_gfx.qc`'s `*`
  "needs a reload" convention is the mod compensating for that on its own side.
  **Why it was not done in 460:** a MAPLATCH set stops updating the cvar's value until a
  reload, so every menu row over one would redraw the number the user did not choose --
  the exact confusion `Gfx_Inert` exists to prevent. It needs its own patch and its own
  pass over those 39 rows, not a line in a collision fix. `engine/common/plugin.c`,
  `PLUG_CVAR_FLAGS`.
- **`sv_prop_collision` is still a client-side desync vector, and it cannot be fixed the
  way the hl2 cvars were.** It picks the collision SHAPE at trace time -- mesh, convex
  hull or box -- and `pmovetst.c:402` reads it with `Cvar_Get("sv_prop_collision", "2",
  CVAR_SERVERINFO, ...)` on BOTH sides, so the client traces against its own local value.
  The comment there says "cvar is synced to the client, so both sides pick the same mode"
  and **that is not true**: there is no generic serverinfo-to-cvar path in this engine.
  `CL_CheckServerInfo` reads named keys one at a time into `movevars` (`cl_main.c:3310+`),
  and `sv_prop_collision` is not one of them. Today both sides agree only because
  `default.cfg` and `defaultuser.cfg` both say 1.
  `CVAR_CHEAT` is NOT the fix here: it force-sets to the REGISTRATION default, which is 2,
  and FTESurf wants 1 (mode 2 has no Source hulls and falls back to a box). A `set` in a
  config does not change a default -- `CVAR_CONFIGDEFAULT` is defined and nothing ever
  assigns it -- and the engine is shared with nettest, which wants the 2.
  **The fix is `movevars`**, the mechanism this engine already uses for every other
  "the client must use the server's value" case (`pm_slide`, `pm_maxvelocity`, and the
  note at `cl_main.c:3327` about `sv_maxvelocity` desyncing by construction until it
  became serverinfo). Add the mode to `movevars`, set it server-side from the cvar and
  client-side from serverinfo, and read `movevars` in `pmovetst.c` -- then the client's own
  cvar cannot affect its prediction at all, which is stronger than a cheat latch.
  Not measured live: no run has yet been made with the two sides deliberately disagreeing.

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

- **A segment's air percentage still reads over 100% when the energy came in
  HORIZONTALLY (Patch 464).** `Seq_Push` divides the row's energy change by
  `seg_emax`, and build 89 made that bound the total: a running high-water mark
  adds any rise the flat-air ceiling cannot explain to the ceiling itself, so a
  booster or an unseen hop is neutral rather than a 400% row. What it bounds is
  the row's OWN energy, which is the right quantity, and the simulator at
  `<scratchpad>/hopsim3.py` shows 0 rows over 100% across perfect, sloppy,
  autobunny and boosted flights with the sloppy rows byte-identical to build 88.
  The gap left: the rule fires on the frame the energy arrives, so a push whose
  gain is spread thin enough to stay under one tick of ceiling per frame is
  invisible to it -- measured at 10175 of 17021 impossible ticks under a single
  unit of height across 300 .rec files. Those are individually noise and could
  sum on a long conveyor. The fix wants the excess attributed per TICK rather
  than per rendered frame, which means the server, which is where
  `run_basevelocity` already lives.
- **Ramp rows are not graded at all, which on a surf map is most of the column.**
  `seq_pct` is `-1` for `SEG_RAMP` by design -- the flat-air ceiling does not
  describe a plane, and `Strafe_PlaneBest`/`Strafe_CScale` (which do) are not
  wired into the segment ceiling. Worth doing, and it is a SEPARATE job from the
  over-100% work above: walking 300 .rec files tick by tick, the recorder's ramp
  bit appears on NONE of the 17021 impossible ticks, so a plane-aware ceiling
  would not have moved a single over-100% row. It would give surf players a
  number where they currently get a dash. Same blocker as the trainer entry
  below: the normal and the pre-clip velocity at the right cadence.
- **The strafe trainer grades flat air only, so on a surf map it is blind
  exactly where the map is (Patch 462).** `hud_trainer` scores each strafe with
  `Strafe_Quality(rate, Strafe_IdealTurn(...))`, which is the FREE-AIR ideal. On
  a ramp the ideal is `Strafe_IdealTurnPlane` instead -- a different function of
  the plane normal, measured in `sh_strafe.qc` at 55.2% of the flat ideal at
  `wn +0.8` and 16.8% at `-0.8`, so reusing the flat number overstates the target
  by between 1.8x and 6x. Rather than grade a ramp against the wrong target,
  `Trn_InputFrame` counts a ramp tick into the strafe's DURATION and not into its
  grade (`trn_s_gdur` is the divisor) and the coach line says "on a ramp -- the
  bar grades that". Correct, and it means a surf player's rows are mostly
  ungraded. The blocker is cadence, not maths: the trainer samples per usercmd in
  `CSQC_Input_Frame`, and the plane normal there is `STAT_FS_RAMPCONTACT`/
  `STAT_FS_RAMPNORM`, a snapshot behind, while `HUD_DrawStrafe` also needs the
  PRE-CLIP velocity to go with it. Either establish that those are good enough at
  input cadence (measure it -- do not assume, the whole reason speed comes from
  the stat is that prediction jitters by a tick), or move the per-tick grade to
  the server where the normal is exact and send the finished per-strafe record.
  Bhop maps, which is what it was asked for, are unaffected.
- **`tools/mapmeta.py`'s `MAPDIRS` omits the Momentum install -- the FIRST and
  largest mount -- so the tier alias pass has never considered most of the
  library.** `ftesurf/fs_addons.txt` mounts `Momentum Mod Playtest/momentum`,
  then cstrike, then hl2, earlier winning. `MAPDIRS` (`mapmeta.py:159-163`) lists
  only `ftesurf/maps` (4 BSPs), cstrike (1084) and hl2 (79), so
  `installed_maps()` returns **1165 of the 1419 names the engine can load** and
  every one of Momentum's 1316 is invisible to `alias_rows()`. Harmless for the
  case it was written for (Momentum's own maps carry real leaderboard rows and
  need no alias) and wrong for anything asking "which builds of this map can be
  loaded". Patch 463's variant work needed the real set and added
  `mounted_maps(momentum)` beside it rather than widening `MAPDIRS`, because
  widening it changes which tiers get aliased and that deserves its own
  measurement. Do that measurement, then collapse the two.
- **Re-running `tools/mapmeta.py` LOSES DATA, measured 2026-09-28.** A
  regeneration over an existing `ftesurf/data/mapmeta.txt` dropped the
  `surf_strike` row entirely -- tier 5, `sugg`, thumbnail
  `b0a5f058-ca96-4f9c-a75a-543efaf3c326`, and the map is installed in BOTH the
  Momentum and cstrike mounts -- and blanked page/cell on 8 rows that still
  exist: `bhop_aperture_kinetic_lab`, `bhop_arcturus`, `bhop_cooksassistant`,
  `bhop_greenbox`, `bhop_greybox`, `bhop_peribox`, `bhop_tealbox`,
  `df_maroonbox`. So `keep_atlas` does not carry forward everything it should,
  and something in `build()` is not stable across runs. 2271 meta rows before,
  2294 after, 1 lost. The run that found this was reverted from its backup rather
  than shipped, so the table on disk is the pre-run one -- which means the
  `variant` rows `write()` now emits are NOT in it yet, and generating them needs
  this fixed first. The module docstring already warns that `--report` used to
  mutate its input; this is the same class one level down.
- **Patch 427's client half is not in a release.** Clients quote `download`;
  until players update, the lobbies' server half is what lets them join maps
  with spaced sound names. Ships with the next `release.ps1 -Bump patch`.
- **Only `2` is drawn early (Patch 430).** 3/4/5/6 move the cursor and load in
  one server step and their target row is not published; the release after a
  hold still waits a round trip for the server's unfreeze (the second `prederr`
  line on each load).
- **IN-GAME MAP DOWNLOAD, A "NEW" BADGE, AND A 6-HOURLY UPSTREAM SCAN -- asked
  for 2026-09-28, surveyed and NOT started.** Three decisions were taken with the
  operator at survey time: the button fetches **from the Pi, which fetches through
  to Momentum's CDN and keeps its copy** (so the Pi stays the authority on which
  build is canonical); the scan **polls the Momentum API every 6 hours**; and the
  KSF Google Drive is **a map source beyond what is on disk** (its share link is
  still needed -- nothing in this repo or in `wrlines` knows the Drive exists).
  What follows is the survey, because most of the pipeline is already built and
  the parts that are missing are not the parts the request names.

  **THE REQUEST'S KSF PREMISE IS INVERTED: EVERY KSF MAP IS ALREADY HERE.** 55
  `_ksf` BSPs across the Momentum and CS:S mounts, **0 missing**. 26 already run
  on DONATED zones -- `tools/census/zonefit.py` graded a donor build FIT on frame
  and destinations, `tools/zoneinstall.py` installed it, and
  `ftesurf/maps/zones/manifest.txt` records all 26 as `donation` (25 FIT, 1
  NO-DESTS). Of the 29 unzoned, exactly **2 are recoverable by that same path
  today** (`surf_derpis_ksf`, `surf_lullaby_ksf` -- their base builds are zoned
  and installed); the other 27 have no zoned base anywhere on disk. And
  `ksf.surf`'s API is players and records only (`wr_ksf.h:65,70,74` -- search,
  bestrecords), with **no map list and no zone data**. So the KSF gap is ZONES,
  and KSF cannot supply them; a downloader answers a question nobody asked.

  **THE MAP LIST CANNOT SHOW A MAP YOU DO NOT HAVE, AND THAT IS ONE LINE.** The
  library IS the filesystem: `m_main.qc:1668` is
  `search_begin("maps/*.bsp", SB_FULLPACKAGEPATH|SB_ALLOWDUPES|SB_NAMESORT)`, and
  `m_main.qc:1257-1259` throws metadata away for anything unmounted
  (`continue; // metadata for a map that is not mounted`). That `continue` is what
  hides **1551 of `data/mapmeta.txt`'s 2271 rows** -- the download button's entire
  audience. The 639 listed maps with no metadata (`m_main.qc:280`, of 1334 listed)
  are a DIFFERENT gap: they are visible and untiered, not invisible.

  **THE ROW'S RIGHT EDGE IS FULL -- the button needs space taken, not found.** The
  PB time is right-aligned at `rp_x + rs_x - 8 - mtw` (`m_main.qc:4402-4414`),
  reserves its width even when blank (`"--:--.---"`, `:4413`, deliberately so the
  headcount does not jump while scrolling, `:4394-4400`), widens by a
  `"^9lobby  ^7"` prefix (`:4409`), and vertically straddles both text bands, which
  `m_main.qc:4435-4439` says outright: a second right-aligned item "would draw
  through the time". The two centralised places to buy room are the `mtw`/`mpopw`
  anchors (`:4414`, `:4448`) plus the `ui_fit_text` budget (`:4464`), or the 36 px
  tier gutter (`rp_x+90` to `rp_x+126`).

  **THE DOWNLOAD ALREADY FAILS TODAY, WITH A LOGGED LINE** -- see the existing
  entry on `Server permissions deny downloading file "package/maps/<map>.bsp"`.
  The fleet sets no `allow_download*` at all and runs engine defaults, which are
  permissive (`allow_download 1`, `allow_download_maps 1`, `sv_main.c:89,95`), so
  the refusal is not a policy knob: the server advertises the BSP as a PACKAGE and
  `SV_AllowDownload` refuses non-pk3 packages. Under that sits the real veto --
  `SV_LocateDownload` (`sv_user.c:4215-4249`) denies any file in an
  `SPF_COPYPROTECTED` searchpath, which is what a Steam-mounted `momentum/` is.
  The engine already carries the opt-out, `sv_allow_download_anything` (nettest
  Patch 37, `sv_main.c:108`, `sv_user.c:3967-3977`, `:4219-4221`), default 0 and
  set nowhere here -- and it is a `sv-rel` patch, so it is DEAD in a stale server
  binary. `sv_dlURL` is `CVAR_SERVERINFO` (`fs.c:330`) and empty everywhere.

  **ZONES ARE NEVER SENT TO A CLIENT, so a downloaded map arrives untimeable** --
  no `precache_file` anywhere in `src/server/*.qc`. The good news is that
  `SV_AllowDownload`'s `maps/` gate is a PREFIX, so `maps/zones/online/<map>.json`
  is already permitted BY NAME under `allow_download_maps 1`, and Patch 463 made
  the zone pin compare fields rather than the path, so a downloader may write to
  either `local/` or `online/` without refusing recordings. BSP and zone must
  travel as an atomic pair for the same reason `mapsync.py:15-21` gives.

  **WHAT IS ALREADY ON THE PI, read from the host 2026-09-28 and not in this
  repo.** `sites-enabled/` holds `fastdl`, `mom.conf`, `momcdn.conf`,
  `nettest-dl.conf`, `filebrowsers.conf`, `play.proto.bar.conf`. `fastdl` is real
  but is SVEN CO-OP's (`:8082`, root `/srv/nvme/Archives/SvenBackup/...`, serving
  `.bsp` out of `.bsp.gz` with `Content-Encoding: gzip` -- a working recipe worth
  copying). **`momcdn.proto.bar` terminates TLS and proxies `127.0.0.1:9000`,
  which is a live MinIO** (`Server: MinIO`, region `us-west-1`). **`mom.proto.bar`
  serves a clone of the Momentum monorepo at `/root/mom`** with `/api/` proxied to
  `127.0.0.1:1245`. Do not overstate this: the API on 1245 is **DOWN**, socket.io
  on 9132 is down, `STORAGE_BUCKET_NAME=momtest` is still the template default and
  every bucket answers 403 -- it is an unfinished local-dev deployment, not a
  running CDN. But the hard part (public hostname, cert, object store) exists.
  Disk: 458 G, **77 G free** (83% used); `mapsync.py`'s `HEADROOM_GB` is 5.
  Consequence for the chosen design: a self-hosted Momentum API would make the
  6-hourly poll hit the operator's OWN server, which is a materially different
  proposition from polling `api.momentum-mod.org`, and is worth settling first.

  **WHAT A DOWNLOAD COSTS, measured on the 1316-BSP install:** 45.0 GB total,
  median **23.1 MB**, mean 35.0, p90 76.9, max 494.6; 78% exceed 10 MB and 5.9%
  exceed 100 MB. The Pi serves 12 live lobbies off one home uplink, so
  concurrency and rate need a ceiling before this is switched on -- `ftesurf.nginx:37-72`
  already has the shape (`limit_rate_after 512k; limit_rate 2m`).

  **THE "NEW" SIGNAL: DO NOT USE `dataTimestamp`, OR NORMALISE IT FIRST.** Zone
  files carry one, and it is read by NOTHING today, so this is a prospective trap
  rather than a live bug. Measured: Momentum's own `zones/online/` is 537 files,
  524 in milliseconds and **13 in SECONDS** (2.4%); this library's 609 hold 15 such.
  Read as ms they date to **1970-01**, i.e. a badge or sort keyed on that field
  ranks them permanently oldest and a "newer than last scan" scanner never fires
  on them -- the silent direction. A guess that these were the hand-authored files
  was FALSIFIED: Momentum's own `zones/local/` is 14 files and all 14 are
  milliseconds, so the inconsistency is UPSTREAM in API-sourced data and will keep
  arriving. The robust answer needs no upstream date at all: record first-seen
  ourselves, append-only, on each scan.

  **AND THE TIMER IS BLOCKED ON A KNOWN DEFECT** -- see the entry above on
  `tools/mapmeta.py` losing rows across a regeneration. A 6-hourly job that
  regenerates `data/mapmeta.txt` would run a generator already measured to drop a
  row and blank 8 rows' page/cell, unattended, four times a day. Fix idempotency
  first; the falsifier is free (run it twice, diff must be empty).

  **STAGING, cheapest and most-blocked first.** (1) make `mapmeta.py`
  regeneration lossless -- gates everything on a timer. (2) the two recoverable
  KSF zones, via the existing `zoneinstall.py` path, no new code. (3) emit rows for
  catalogued-but-absent maps and relax the `m_main.qc:1257` `continue`, so the
  1551 become visible as unavailable -- the lobby cell's `"^1not installed"`
  treatment (`m_main.qc:4211-4227`, and the cell is deliberately unclickable in
  that state, `:4245-4247`) is the precedent. (4) first-seen roster and the New
  badge; `data/mapmeta.txt` takes both with NO reader change, because the reader
  skips any line whose first token is not `meta` and guards trailing columns with
  `n >= 11` (`m_main.qc:1250-1275`). (5) trace and fix the `package/maps/` denial,
  then serve BSP+zone from the Pi. (6) the button itself -- and note the menu has
  exactly ONE `URI_Get_Callback` per VM (`m_lobby.qc:885-931`, `responsecode == 0`
  is success, not 200), so anything new branches inside it; a per-row button
  registered after the row STEALS the row's hover, because sui walks front to back
  (`sui_sys.qc:296,347,409`) -- use `sui_hover_index`/`sui_release_index`, and act
  after `sui_end` or the release fires twice (`cl_scores.qc:1273-1299` is the
  working precedent). (7) the Drive, once its link exists.

## Imported runs (Momentum, KSF)

- **NOTHING OF THE IMPORT IS DEPLOYED.** The Pi has no `data/momentum`, no
  `surfd` change and no progs carrying the tab or the tint. All of it is
  verified locally and on a copy of the live database. Deploying restarts all 12
  lobbies and needs the operator's word; `lextest.md` §2h holds the four
  judgement calls that should be settled first.
- **KSF's per-map leaderboard route is NOT LOCATED, and that is not the same as
  absent.** Their map pages render records, so a route exists. Twelve guesses
  across two rounds (every shape their two documented endpoints imply), the map
  page HTML, and all seventeen of its JS chunks: the chunks hold typed DTOs
  (`steam_id`, `map_name`, `records`, `pr`) but no URL, so the base is composed
  at runtime in a chunk the page does not pull. Until someone finds it,
  `surfd/ksfimport.py` is player-seeded at 25 records each, which is a poor
  substitute for a map board. Whoever finds it should rewrite that tool around
  it. **Do not find it by brute-forcing their server**; read their client.
- **877 imported runs are on a build that is NOWHERE ON THIS MACHINE, and are
  SKIPPED.** The demo's own map SHA1 says so (see AGENTS.md). Searched across
  all three map roots -- Momentum's 1,316, Counter-Strike: Source's 1,084 and
  ftesurf's own -- and **0 of the 877 match any build here**, so they are older
  Momentum cuts since replaced rather than a map we merely mounted from the
  wrong place. Nothing recovers them but the original BSPs.
  (The first search of this missed the CS:S install entirely and reported the
  same answer, which was luck rather than method: a root that is not searched
  cannot contribute a match. The figure above is from the complete sweep.)
  It also confirms from the other direction that no Momentum demo was recorded
  on a CS:S build -- not one hash matched one.
  Their times are real and their paths are not ours to draw. `momimport
  --other-build` imports them if anyone ever wants the times without the lines,
  which would want the line suppressed per run, and nothing does that yet.
- **80 demos failed extraction outright** (of 735 in the last batch): mostly
  `gave up after 30 s in the chain search`. `wrpath_extract --timeout 0` or a
  larger value would take another pass at them; the extractor records failures
  so a re-run skips them by default.
- **The corpus was extracted on CPython 3.10, not the 3.13.9 the extractor is
  bit-pinned to.** Its own oracle still gates every chain, so the output is
  valid, but a chain here may differ from the one the wrlines DLL would pick on
  the same demo. Nothing measured says it does; nothing says it does not. If
  parity with the DLL ever matters, re-extract on 3.13.9 and compare.
- **`surf_antichamber` has 5 demos and no zone file** -- the only one of 500
  demo maps without one. Its runs import and draw, but nothing times that map.
- **An imported run's air-control and energy colouring is graded against THIS
  server's movement settings**, like every other foreign recording -- see the
  `Line_Movevars` entry under Cosmetic. The import makes it concrete: the engine
  prints Momentum's own constants (`accel 5, airaccel 150, aircap 30, gravity
  800`) on every one of those maps, so the file's numbers are KNOWN and still
  not read. `momimport` writes no `pmpin`, deliberately -- it did not run that
  physics either -- so the "no answer" branch is the PERMANENT state for a whole
  tier rather than a legacy case that shrinks.
- **A KSF row's `ticks` is derived, not counted.** KSF reports seconds; the
  schema wants a tick count, so `ksfimport` divides by the CS:S 0.015 and says
  so. Anything reading `ticks` off a ksf row is reading a number nobody
  measured. `millis` is the fact.
- **`momquality` is surfaced at the replay, not on the board.** Opening an
  import whose velocity exceeds the demo's own ceiling prints a `^3` line
  naming the factor, and `replay status` carries it either way (momline A6
  grades both halves on one map). What is still missing is the BOARD side: a
  row that will draw a bad-speed line looks identical to one that will not
  until you open it. 354 of 5,281 rows are affected.
- **The two imported tiers make different claims and the board shows one word
  each.** A `momentum` row is build-verified exactly; a `ksf` row cannot be,
  because nothing on the CS:S side publishes a per-map digest and the 322
  divergent map names are all plain-named. `why` says `momentum` or `ksf`, so
  the information is there for anyone who knows -- but nothing says that one of
  those words carries a check and the other cannot.
- **The blue tint is a hue blend, not a glow**, and against a warm map it reads
  as lavender. `hud_watch_path_foreign` tunes it, but the real answer for
  "someone else's line" is probably a wider or additive draw pass, which is a
  rendering change wanting its own patch and a `replay bench` measurement.
  `lextest.md` §2h(a) asks the operator whether it is enough as it stands.

  **AND A MATCHING NAME IS NOT A MATCHING BUILD, FOR 30% OF THE SHARED LIBRARY --
  which makes the `_ksf` counts above a floor, not a bound.** The import session
  fetched a real `ksf.surf` bestrecords response and found KSF returns records
  under PLAIN map names (`{"map_id":580,"mapName":"surf_whiteout"}`), with
  suffixed and unsuffixed names in the SAME response -- so a KSF record on a plain
  name was still set on KSF's build under KSF's zones, and counting `_ksf`-named
  files understates the exposure. Their API reading is theirs and is not verified
  here (no request was made to ksf.surf from this session). The LOCAL half is, and
  it generalises the point past KSF: of the **1062 map names present in both the
  Momentum and CS:S installs, 322 (30.3%) differ in size, i.e. are a different
  build under the same name** -- and **all 322 are plain-named, zero are
  `_ksf`**. The suffix convention is exactly where the collision does NOT happen.
  Divergence is not marginal: `surf_fantasy` is 155 MB against 351 MB,
  `surf_dune` 21 MB against 156 MB. Method check: `surf_kitsune` reads
  3,952,402 / 4,418,529, the same pair `mapsync.py:47-63` recorded independently
  when it found 323 of 1312 Pi BSPs were the wrong build.

  **CONSEQUENCE FOR THE DOWNLOAD BUTTON, and it is a design constraint rather than
  a caveat: the transfer must be content-addressed, not name-addressed.** "Send me
  `surf_kitsune`" is ambiguous across a third of the library, and getting it wrong
  is SILENT -- the client loads, plays, and `TF_NOMAP` demotes the run because
  mapcrc disagrees. So the button must ask for the build the SERVER holds (its
  mapcrc or a hash), the Pi must answer with that exact file, and the client must
  verify what arrived before the run counts. This is also the strongest argument
  for the Pi-sourced design over Momentum's CDN: the CDN can only ever answer by
  name, and the name is the thing that is not unique.

  **THE KSF DRIVE, SURVEYED 2026-09-28 -- AND IT IS ALL PUBLIC, SO NO OAUTH AND NO
  CREDENTIAL IS NEEDED.** Three links from the operator: maps A-K
  (`17QJ-Wzk9eMHKZqX227HkPCg9_Vmrf9h-`), maps L-Z
  (`1f3Oe65BngrSxTPKHAt6MEwK0FTsDbUsO`), and a roster spreadsheet
  (`1oXU6UXGPdgdqRiAjjD_5c1WfI6PY6ML4`). All three answer an anonymous GET.

  **ENUMERATION: use `embeddedfolderview`, NOT the folder page.**
  `https://drive.google.com/drive/folders/<id>` returns 798 KB of HTML whose
  `window['_DRIVE_ivd']` blob holds **only the first 50 entries** -- the rest
  paginate by XHR, so a scraper built on it silently sees 50 of 466 and looks like
  it worked. `https://drive.google.com/embeddedfolderview?id=<id>#list` returns the
  COMPLETE listing in one unauthenticated request: 466 + 468 titles, **934
  distinct names, 927 of them `.rar`**. The roster exports as CSV with
  `https://docs.google.com/spreadsheets/d/<id>/export?format=csv&gid=1729788986`
  (23 KB, `Map name,Tier,Type`, workbook tabs `Surf Maps - KSF CSS` / `Sorted by
  map type` / `Feuille 3`).

  **THE MEASUREMENT: 929 maps on the roster, 929 archives in the Drive, and we
  already hold 894 of them (96.2%).** Genuinely absent after name reconciliation:
  **31**, and every one of the 31 is present in the Drive, so the mirror is a
  bounded one-off rather than an open-ended sync. Roster tiers run 1-8
  (76/170/262/217/108/56/31/9); types are Staged 496, Linear 404, Staged-Linear
  28, plus one row whose Type is the literal `c`.

  **THE REAL KSF GAP IS ZONES, AT EVERY SCALE THAT WAS MEASURED.** Of the 929
  roster maps, **390 have a zone file (42.0%)** and 389 are both playable and
  timeable; 539 are not. That is the same finding the `_ksf`-suffix census gave
  and the same one the whole-library census gave -- maps are nearly solved, zones
  are not, and no KSF endpoint or Drive artifact supplies zone data.

  **A SCANNER NEEDS A THIRD VERDICT FOR NAMES, because the spreadsheet and the
  Drive disagree on five of them.** `surf_disappointed_fix`/`surf_disappointed`,
  `surf_junglepics_ksf`/`surf_junglespic_ksf` (a transposition), `surf_not_so_zen`/
  `surf_nsz_fix` (an abbreviation), `surf_race_final`/`surf_race`,
  `surf_vestige_fix`/`surf_vestige`. **Four of those five are already on disk under
  the DRIVE's spelling** -- so a scanner that trusts the roster reports 4 maps
  missing that are sitting in the library, and one that trusts the Drive reports 5
  roster entries absent. Neither is a fault; the honest answer is `unreconciled`,
  counted separately and never folded into `missing`. This is the Patch 421/422
  third-verdict shape arriving in a new place.

  **PRACTICAL TRAPS FOR THE FETCHER.** Maps are `.rar`, not `.zip` or loose BSP, so
  an extractor is on the path and a CS:S map archive carries materials and models
  beside the BSP. The Drive's mime types are INCONSISTENT for identical content --
  `application/rar`, `application/x-rar` and `application/x-compressed` all appear
  -- so filter on the name, never the mime. And the spreadsheet is the cheap change
  signal the 6-hourly scan should actually use: one 23 KB unauthenticated GET,
  hashed and diffed against the last copy, gives new-map detection without
  enumerating either folder and without touching anyone's API.

  **PART OF THIS IS NOW BUILT: `tools/maproster.py` (2026-09-28), the official
  surf/bhop list pinned by content hash.** Scope narrowed by the operator to surf
  and bhop, with zones explicitly off this thread (an in-game zone maker is being
  built instead). It writes `data/maproster.txt` -- **1748 maps, 1174 surf and 574
  bhop** -- unioning KSF's roster, Momentum's catalogue and what is on disk;
  1249 installed and hashed, 499 absent, **31 of them fetchable from the KSF
  Drive**. `pin` came out **ok 37, other 2, unknown 1709**.

  It hashes only the build the ENGINE WOULD LOAD, resolved through
  `fs_addons.txt`'s mount order rather than assumed -- 1249 files and 43.7 GB
  instead of the 90 GB both installs hold, and it is also the only build that can
  ever matter. Regeneration is byte-identical on a re-run (checked), which is the
  defect the `mapmeta.py` entry above records, avoided by deriving everything from
  sources and carrying no state forward but the hash cache -- and that cache is
  keyed on size AND mtime, because a stale one is silent.

  **Momentum's published SHA1 is real and was verified independently: a `.mtv`
  carries it as 40 UPPERCASE hex at FIXED byte offset 80**, and across the 2888
  demos in `wrlines_data/demos` 39 of the 40 maps carrying one hash to exactly a
  local build. 5 of those 40 have demos that DISAGREE with each other
  (`surf_4am`, `surf_antichamber`, `surf_blackheart`, `surf_pinkcubes`,
  `surf_tropic`) because Momentum re-released the map and both builds hold times --
  so "the latest version" is not a thing a hash can answer, and the tool reports
  the split rather than resolving it silently.

  **AND IT FOUND A LIVE ONE ON ITS FIRST RUN, which hand-checking the two Steam
  installs had missed: `ftesurf/maps/` WINS THE MOUNT, and two of the four loose
  BSPs in it shadow a different upstream build.** `surf_dune` (156,409,212 bytes)
  and `surf_fantasy` (351,547,373) in the gamedir are **byte-identical to the CS:S
  builds** and override Momentum's 21 MB and 155 MB cuts for everybody on this
  install. So any run on either map is recorded against geometry Momentum's
  leaderboards do not know, and `surf_dune` is exactly the `other` verdict the pin
  is for. Whether those two are deliberate fixtures or leftovers is not recorded
  anywhere and wants deciding; `poop` and `surf_raqbonus3ramp` are gamedir-only
  with no upstream build and are not affected.

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
- **THE RUN LINE'S MARK CAP HAS NEVER FIRED, so its degradation policy is
  written and unexercised.** `LN_EVCAP` is 4096 a slot and the two-stage policy
  (drop the apex/trough class whole, then stop and count, both reported by
  `Line_End` and `replay status`) is what a long bhop run is supposed to meet.
  The biggest fixture available produces 2158 marks: `bhop_monster_jam`
  save010, 127437 samples, which is already nearly twice the POINT cap and
  exercises the halving. So the cap path is reached by no arm. Either find a
  recording past ~4000 marks or run `p449mark.cfg` against a build with
  `LN_EVCAP` lowered and the hash recorded, which is the p439smoke recipe.
  cl_lines.qc `Line_Ev`. Patch 449.
- **The run line's near-plane guard cannot be falsified by the harness, and it
  is kept anyway.** Removing the dot-product test before `project()` in
  `Line_ProjPt` changes nothing measurable -- 158 glyphs either way, no NaN --
  because `q_z < -1` already rejects everything behind the camera, so the dot
  test's unique contribution is the `w == 0` knife edge exactly, which a sampled
  run does not land on. A cut that parks the camera ON a mark (p449win W3,
  t=41.1440) did not produce it either. The guard stays because
  cl_entview.qc:1288-1294 documents the same hazard from a case that DID reach
  QC; what is missing is a way to make the condition. cl_lines.qc `Line_ProjPt`.
  Patch 449.
- **The one-frame angle rule in `reccheck.py` convicts honest low-frame-rate players, and
  `tools/p456solo.py` is the arm for it.** ANG_SOLO faults a pair when too many ticks that
  held exactly ONE rendered frame disagree with the recording by over a flat 0.05 deg. That
  population is selected for having no minimum to take: a tick is scored as the MINIMUM over
  its frames, so a 4-frame tick picks its best of four and a solo tick cannot. Deny the
  ordinary ticks the same advantage and they come out WORSE than the ticks the rule convicts
  on -- 67.7% past cut against 45.8%. And coverage is `solo/comparable`, so a LOW frame rate
  RAISES it, and coverage is what promotes the verdict to `tight`: decimating an honest
  sidecar to one frame per tick (49 fps, nothing rewritten) makes the shipped rule answer
  `angle_rule tight` and "the sidecar is not this recording's" at 67.6%. The candidate fix is
  physics rather than a threshold -- a frame is drawn INSIDE the tick, so it cannot differ
  from that tick's angle by more than the tick's own sweep, and `dev > k*max(sweep, ANG_SOLO)`
  at k=1 clears honest 196 fps (0.6%) and honest 49 fps (0.1%) while still faulting a
  substituted sidecar (99.7%). With the floor at ANG_SOLO a still camera reduces to exactly
  the shipped rule, so the still-camera teeth the sweep rule is blind to are kept. NOT
  APPLIED: it is a verifier change and wants its own review round. The 2026-09-21 surf_4am
  FAULT was adjudicated a false positive on this basis and its `pubkeys.decision` is
  deliberately unset, so the fixed rule re-derives the verdict instead of inheriting a
  hand-cleared row.

## Cosmetic / low
- **The run line's air-control grade is measured against THIS server's movement
  settings, not the recording's.** `Line_Movevars` reads `pm_ticrate`,
  `sv_airaccelerate`, `sv_accelerate`, `sv_maxspeed`, `pm_maxairspeed`,
  `sv_gravity`, `sv_friction`, `sv_stopspeed` and `pm_duckspeed` from the server
  the client is on, which is what the strafe bar does for a replay too -- so the
  two agree, and on a foreign recording they are wrong together. The v9 header
  carries a `pmpin` block of 70 movevars and NOTHING in `src/` reads it; that is
  where the file's own settings would come from. Until then a recording made on
  a differently-configured server is graded against local numbers, silently.
  `tools/p453q.py` says the same in its header, because it is handed the
  settings for the same reason. cl_lines.qc `Line_Movevars`, `Line_Grade`.
  A Momentum import makes this concrete rather than hypothetical: the engine
  prints `Momentum movement: ... accel 5, airaccel 150, aircap 30, gravity 800`
  on every one of those maps, so the file's own numbers are known and still not
  read. tools/momimport.py writes no `pmpin`, for the honesty reason in its
  header -- the importer did not run that physics either.
  **MEASURED OVER THE WHOLE LIBRARY 2026-09-28, AND IT SPLITS THIS IN TWO.** Of
  3733 `.rec` files, `tickrate` is present on 3733 -- all of them -- and `pmpin`
  on 268 (7.2%: v9 243, v10 25; the rest are v5 3107, v4 344, v7 13, v6 1). So
  "read `pmpin`" repairs 7% of the library and the other 93% still needs the
  third verdict above; but the TICK half is separable, library-wide, and needs no
  fallback, because `ln_tick[s]` already holds the file's own rate for every file
  and `Line_Grade` ignores it in eight places (cl_lines.qc:478-501) while the
  energy ceiling at :1115 uses it. Magnitude on this fleet, exactly: surf is
  `pm_ticrate 0.015 / sv_airaccelerate 150`, bhop `0.01 / 1000`, and
  `k = aa*ws*tick*fric` clears aircap 30 in all four combinations (smallest 146,
  at fric 0.25), so `gain` clamps to 30 either way and
  `Strafe_IdealTurn = atan2(gain,speed)*DEG_PER_RAD / tick` differs by the tick
  ratio ALONE: 1.5x. The direction is the reason to care -- the 140 files
  recorded at 0.01, watched on a 0.015 lobby, get a target 1.5x too LOW and so
  read BETTER than they were strafed, and a comparison line that flatters the
  ghost is worse than one that is harsh. `Strafe_CapBinds` does depend on tick,
  so the grey gate can flip in principle; between these two modes it does not.
  WHERE THOSE 140 ACTUALLY ARE, because the import does not dominate them yet:
  of the 2961 files under `data/momentum` 2910 are 0.015 -- Momentum's surf
  interval matches ours exactly -- and only 51 are 0.01, so 89 of the 140 are
  local recordings. The cheap fix needs NO import special case:
  `tools/momimport.py:255-256` writes the file's own interval into both
  `tickrate` and `movetickrate`, so `ln_tick[s]` is already correct for all 2961.
  AND THE NO-ANSWER BRANCH IS PERMANENT, NOT LEGACY. An imported run will never
  carry `pmpin`: momimport omits it deliberately (`:21` -- the machine that ran
  that physics was Source, and filling our 70 movevars from anything else would
  invent a fact). So the third verdict is not a shrinking population of old
  files, it is the standing state of a whole tier, and it wants to read "not
  measurable here" rather than "old file".
  Reported by the import session and NOT verified here -- no `.mtv` survives in
  this tree -- Momentum's other gamemodes carry their own interval: bhop 0.01,
  kz 0.0078125, defrag 0.008, across 7486 headers. Neither 0.0078125 nor 0.008
  appears on any `.rec` yet, so that growth is pending on the 4589 demos still
  extracting; if they land, their errors are 1.92x and 1.875x, WORSE than bhop's
  1.5x, so the count and the magnitude both grow.

- **EVERY BOARD-COMPARISON LINE IS BUILT WITH A ZERO GROUND PLANE, so
  `hud_watch_path_color 4` is wrong on slots 1-8.** `cl_watch.qc:1933` reads
  `(n > WT_C_V4N)` where the replay path at `:1237` spells the same test
  `tokenize(s) >= WT_C_V4N`. `WT_C_V4N` is 17 and a conforming v4+ sample has
  EXACTLY 17 columns -- measured at 17 across 43, 15947 and 19384 samples in
  three real files, and `reccheck.py:142`'s `COLUMNS` pins 17 for every version
  from 4 up, so 18 can never occur and the test is always false. With the plane
  zeroed, `Line_Grade`'s ramp branch (cl_lines.qc:491-499) never fires and every
  airborne sample on a board line is graded against the FLAT `Strafe_IdealTurn`,
  which cl_lines.qc:428-431 says overstates the target by up to 6x on a
  53-degree face. Contact colouring (mode 2) is unaffected: it reads
  `fl & WT_F_RAMP`, not the plane.
  Re-measured independently at scale: 1,538,762 samples across 400 files, every
  one exactly 17 columns, and `reccheck.py:951` faults on
  `len(tok) != want_cols` -- so 18 columns are not merely unobserved, they are
  unrepresentable in a conforming file, and the branch is dead by construction
  rather than by luck of the sample.
  It survived because `cfg/test/p453q.cfg` and `p452col.cfg` only ever issue
  `replay colours 0 <stride>` -- slot 0, never a board slot. A one-character
  fix, but it changes behaviour on a shipped colour mode, so it wants its own
  patch number and an arm that grades slot 1 against slot 0 on the same file.
  Found 2026-09-28 while mapping the line path for the Momentum import; the
  import does not cause it and is not blocked by it.
  Patch 453.
  ONE of the nine is already in hand and unused: `Line_Tick` (cl_lines.qc:274)
  is handed the recording's own `movetickrate` and the energy ceiling divides by
  it, while `Line_Grade` two hundred lines later uses the LIVE `ln_mv_tick` for
  the same file. Whichever way that is resolved, the two should read one number.
  AND THE MISSING-KEY CASE IS INDISTINGUISHABLE FROM AN ANSWER. `ln_mv_airaccel`
  (:282) and `airaccel` (cl_hud.qc:3932) are the only two movevar reads in either
  file with no `<= 0` fallback -- their seven neighbours all have one and
  cl_board.qc:2345 falls back to 150. Absent key gives airaccel 0, so
  `Strafe_CapBinds` returns false and both the bar and the line go to "the cap
  does not bind" -- the third verdict this codebase keeps having to learn, since
  that is also the legitimate answer for a server genuinely running a low rate.
  A fallback of 150 is the WRONG repair (it invents the number the CapBinds
  comment exists to respect); the refusal should name which of the two it is.
  Note the trigger is unreproduced: `SV_UpdateMovementServerInfo` publishes on
  the first frame whenever `sv_airaccelerate` is non-zero, and nothing sets it to
  zero. Value 150 vs bhop's 1000 grade IDENTICALLY -- both saturate the 30 u/s
  cap, per mode_bhop.cfg:75-116 -- which is why the fallback has never been felt.
  Found by ftesurf-a1 reading cl_hud.qc for Patch 462; the cl_lines.qc half and
  the rest of this paragraph are from checking it.
- **A hop whose ground contact falls between two packets has no mark**, and
  cannot have one. Samples are one per packet (43-65/s measured against a 66.67
  Hz tick) and a bhop's ground contact is one tick, so the touch is simply
  absent from the file. The Segments column misses the same hops from the same
  samples, which is why the containment invariant still holds exactly -- but a
  reader counting chevrons on a bhop line is undercounting, and the number is
  not small: `bhop_monster_jam` main has 438 landings marked for 330 jumps.
  Interpolating them would be inventing contacts the file does not record, so
  this is a documented limit rather than a defect. cl_lines.qc header. Patch 449.

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
