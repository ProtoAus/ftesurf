# P1443 -- surf path planner, stage 1: the energy ledger

ftesurf-b8, 9 Nov 2026, at Lex's request (plan a system that improves a demo's ramps and airtime, or
plans its own path, working back from the end; humans can place target points on ramps).

## Stage 1: tools/surfledger.py

`python tools/surfledger.py <map.bsp> <run.rec> [...] [--json out.json]` books a run's energy
(E = |v|^2/2 + g*z, shown as the speed it is worth at the run's lowest point) tick by tick:

- every tick is replayed with Source's air move (half gravity, AirAccelerate at the row's yaw and
  moves, the collision, half gravity); in free air it explains the velocity change to a median of
  0.0001 u/s (2465 of farsh's 3545 airborne ticks under 0.05);
- what it cannot explain is a collision: the residual points out of the plane hit, its energy is
  the clip's loss, and the hull's support point finds the BSP plane (ramp identity across runs);
- TryPlayerMove runs the first part of a contact tick unclipped and all of it before the second
  half of gravity, so a clip's net cost is (w.n)^2/2 - g*dt*|w.n|*nz*(1/2 - f), f the fraction of
  the tick before contact (from the hull's support distance); an in-air duck moves the origin 8.5
  (g*8.5 of real game energy, booked as `duck`);
- the books close: per tick |observed - explained| median 0.15, p99 0.5 (u/s)^2; per run 0-2 u/s
  unexplained in all.

Rides are contact runs on surf planes (n_z 0.02-0.7, any number of faces, air gaps up to 3 ticks);
each gets its board loss, ride strafe and clip, leave state, and the airtime before it.
`tools/test_surfledger.py` builds a synthetic fall-ride-leave with TryPlayerMove's order and needs
exact closure, the ramp's plane and one ride; a ledger without the clip correction fails it
(worst tick 1503 against 0.0000).

Only per-tick rows give a full ledger (KSF imports, Momentum conversions). A native .rec is sampled
per packet; pairs more than a tick apart are skipped.

## surf_null, three KSF runs (farsh 52.52 s, Luco 52.84 s, proga 52.97 s)

All three ride the same 12 ramps in the same order. As speed (higher is better):

| | board | ride (strafe - clip) | air | net |
|---|---|---|---|---|
| farsh | -70 | -617 | +193 | -494 |
| Luco | -70 | -623 | +198 | -495 |
| proga | -80 | -590 | +205 | -465 |
| best of the three, ramp by ramp | -54 | -560 | +214 | -400 |

- The rides, not the boards, cost the most: strafing into the ramp adds speed the clip then takes.
  Ramp 11 (the last, -170 to -208) and ramp 9 (-92 to -102) are the big ones; ramp 0's board
  (the first drop onto an 18-face curved ramp, -28 to -30) is the biggest board.
- Matching the best human on every ramp is worth 65-95 u/s of energy before any optimizing.
- Energy is not time: the fastest run is not the one with the most energy left. The planner's
  score has to be finishing first, then time, with energy as the margin that keeps later ramps
  reachable.

## The planner (stages 2-5)

1. **A fast exact rollout (engine).** Today `tas optimize` plays each candidate through the real
   mover at game speed (one search step a frame). A whole-map search needs 10^5-10^6 candidates, so
   the engine gets a native op: from a captured mover state run K ticks of a generated input tape
   through the same tick code (no network, no render) and return the end state, the contact log and
   any reset/teleport trigger the hull overlapped. Same code, so exact; the accepted result is still
   replayed through the server's verification. A separate Python re-implementation is avoided on
   purpose (the mover's ramp fixes, bevels and re-wound hulls would make an approximation pick paths
   that fail verification on exactly the hard maps).
2. **Link optimizers.** A run is links: air -> board -> ride -> leave. A ride is a few numbers (turn
   rate, end flick and its length, P1092's board offset); an airtime is a strafe profile and its
   switch ticks. Each link is optimized for the energy it delivers into the next target.
3. **Target points (Lex).** Humans place points on ramps -- where the next line should hit, with an
   optional heading -- stored per map like recipes. The air link before a target is scored on
   reaching it with the least boarding loss. Then each target's position on its ramp becomes a
   variable: move it, re-solve the link into it and the link out of it, keep the better spot; sweep
   all targets repeatedly until none moves (a local optimum, refined "until perfect" within it).
4. **Backward windows.** For the last ramp, sample leave states and keep those that finish; for each
   earlier ramp keep the leave states whose air link boards into a state that can still reach the
   window after it. Each ramp gets a target window (where, how much energy, which heading); a human
   target point seeds or narrows it.
5. **Whole-path search.** Forward from the start, keep the best few candidates at every ramp (not just
   one, so a slightly worse ride that sets up a much better board survives), pruned by the backward
   windows. The output is a TAS project the server verifies.

The route (ramp order) comes from a demo or the target points; on these linear hard maps it is fixed.

## Stage 2: tas_rollout (engine p1443: a075767a9, review 1 64433c923, review 2 0e7fa9afb; on patch-1440)

`float tas_rollout(entity player, float *rows, float ticks, float *out)`: from the paused TAS body, ticks rows of
tas_tape words (7 floats) through SV_RunCmd's own mover setup and one PM_PlayerMove a tick; 13 floats a tick out
(origin, velocity, onground, ducked, contact kind and normal as SV_RunCmd publishes them, and the first entity
per-command QC could act on: a touched solid whose touch would run, a non-world ground, any trigger volume with or
without .touch -- negated for a volume the body starts in, which PreThink acts on before tick 1). pmove, movevars,
pmove_mins/maxs and frametime are restored. It refuses (codes -1..-10) where SV_RunCmd's inputs are not the plain
ones: a carrier (run_basevel, non-world ground), a QC limit or forced duck, a gravity direction, water/ladder/duck
transition, non-default gravity, the TAS clock. QC (SV_TASOptRoll) also refuses while per-command state is pending
at the head (trigger edges run_tl*/SV_TrigPending, delayed outputs, the Monolith latch: -31/-32), lends P1193's
no-collide barrier around a rollout as the real command does, and cuts a prediction at the first named entity.

- Measured (tools/p1443_rollcheck.py, p1443_fast.py, p1443_null.py): every played landing that a rollout predicted
  in full was bit-equal in origin and velocity -- 44 in the two-search arm (ground and air), 85 + 2 in the fast arm,
  2 on surf_null (the drop onto ramp 0); a mutant mirroring the strafe gives 0 of 22 (18.3 u, 253 u/s off); the
  installed server, without the builtin, prints no check.
- Read-verified only, not made to happen by an arm: the refusals for pending trigger edges, delayed outputs and the
  Monolith latch, the barrier lending, and the cut before a start volume.
- Speed (`cmd tas rollbench <ticks> <count>`, developer, ticks x count <= 1,000,000): 72-86k ticks/s on this PC --
  ~650 rollouts/s of 128 ticks, ~120/s of 600 -- about a thousand times one played candidate per couple of seconds.
- Reviews: round 1 (carrier field, no-touch limit volumes, touch loop and contact kind), round 2 (pending QC edges
  and delays, the barrier, last-tick cuts, an allowlist that could mask a teleport) -- all fixed.
- Traps met: P1129's SV_BankGravityEnabled() is true whenever QC defines the callback (guard on the entgravity ratio);
  QW progs hand the mover waterjumptime = teleport_time; the engine's run_basevelocity is read-and-clear (always 0
  while paused) -- QC's carrier is run_basevel; restoring a source file by copy keeps its old mtime and make relinks
  the mutant (touch before rebuilding); fteqcc reads `float *a, *b` with b as float**.

## Stage 3: `tas optimize ... [energy] [fast]` (QC 8fd5e63b)

`fast` scores each candidate by rollout (a finer search: 33 grid points and 24 golden steps per number, the
number list run twice) and plays only the best through the real mover, which the landing check compares with its
prediction. `energy` scores |v|^2 + 2g(z - z_start) as a speed. bhop_eazy, from one airborne start, 24 ticks with
board and flick: fast 473 candidates in 0.7 s, exit 163.9 u/s; the played search 85 candidates in 35.7 s, 163.7.
surf_null, the 128-tick drop from the start platform toward ramp 0 (energy): 473 candidates in 3.8 s a side, the
best replayed bit-equal.

## Delivery

- Engine main a23e3ca9a (tag patch-1443, on patch-1444), QC main d9b8720a, after five review rounds.
- LIVE 9 Nov ~14:40 local: 12 lobbies qw 7e843d1c + cs e1ac3414 (one player on, warned; 0 QC errors; the lobbies'
  patch-1353 engine has no tas_rollout, so fast is refused there and TAS itself stays off on lobbies); both
  installs exe fa65287f (git-8579-patch-1443-0-ga23e3ca9a; .prev/.pre1443 edf50724), C:\FTEQuake fteqwsv64
  879099d7, QC the lobbies' pair (.pre1443 cafb0be2 / e84310b0); csprogsvers 72c6143 on the Pi and both installs;
  codes.txt 111 -> 112 (.pre1443). Plugins unchanged (P1440's).
- Checked on the installed binaries (tools/p1443_rollcheck.py, C:\FTEQuake's server + C:\FTESurf's client + the
  deployed QC): 44 of 44 bit-equal, 72-86k ticks/s.

## P1449: targets, demo-guided searches, autosurf (engine 9fdeedc2d, QC 87fd4a41)

- Engine tas_rollout rows FOLLOW / PITCHV / AIM and contact kind 4 (ENGINE_PATCHES.md "Patch 1449"; two review
  rounds). QC: `tas target`, `tas optimize ... curve 12 demo aim late tube R look N hop` (a search over corrections
  to a replay's own turn commands, held near its path, scored on energy at the reach), `tas autosurf <demo.rec>`
  (sv_tasautosurf.qc: a replay's boards and bhop platforms as targets, tries and backtracks), the line editor's
  Optimizer tab (cl_tasoptui.qc). Three QC review rounds, one more on the face fix and the tab's demo list.
- Rig (tools/p1449_chain3.py, surf_null from ksf_null_farsh's ramp-0 state): the driver chain reached boards 1-4
  and both platform hops (tbt1, 9 Nov). In-game autosurf (tauto3, 10 Nov): stretch 1 on 6 of 7 visits after the
  face fix (0 of 2 before); stuck at stretch 2 after 6 backtracks -- a curved pillar (brush 101) 18 u off farsh's
  line, and 400-580 of each search's 638 candidates cut on a wall touch there.
- Delivered 10 Nov: both installs exe e47ccec1 (git-8596-patch-1449-0-g9fdeedc2d; .prev/.pre1449 the patch-1452
  exe), C:\FTEQuake fteqwsv64 54ee2295 (.pre1449 879099d7), csprogs 41a94457 / qwprogs 18dddad9 built from 87fd4a41
  with P1448's held client files (cl_online, cl_profile, cl_scores) at d9b8720a; menu.dat unchanged (e4f7b1ad);
  csprogsvers 89bbcb91 in both installs; tasrevd codes.txt 112 -> 113 (.pre1449). Not on the lobbies (TAS is off
  there). qwprogs grew 1.70 -> 3.16 MB: the search arrays' per-element defs (qwprogs keeps array defs).
- Next: a wall touch costs score instead of cutting (TOPT_WALLPEN, branch p1449-wall), then monolith's ramp 2
  corner and surf_null's ramp 4 launch.

## P1449 follow-ups on branch p1449-wall (10 Nov, not installed yet)

What each change answered (rig runs under rigs/, surf_null with ksf_null_farsh unless named):

- Search scoring. A wall or ceiling touch costs TOPT_WALLPEN 120 a tick instead of cutting the candidate (the cut
  left board 2's pillar, 18 u off farsh's line, unreachable: 400-580 of 638 candidates died there); ground ticks
  cost 60 on board stretches (ramp 0's angled segment tops, normal z 0.85); a reach pays `pace` a tick (energy is
  near flat at speed, so a longer arc cost nothing); `emin` (autosurf 0.95 x farsh's speed at the board) puts a
  slow reach between reaches and misses; the lookahead pays for its walls (a hop whose next 1.4 s ended against the
  next platform's side scored as surviving). SV_TASOptBand keeps penalties inside their band (review 2-3).
- Demo keys by route position (SV_TASOptDemoMap, a second roll when a tick's row moves > 2): by the clock a line
  faster than farsh kept his strafe side past ramp 6's end and ducked late (Lex).
- Tube: free on ramp rides and within 2x its radius of the target; after a ride it starts as wide as the ride left it.
- Early aim seeds (0.4-1.0 of the way): farsh's air arcs run at the 30 u/s cap's turn rate (94 deg at 43 deg/s
  to ramp 6), so a faster line must start earlier. Ramp 6 then at 3235 u/s, farsh's own.
- Plan: rides entered rising onto a surf face are stretches (the ramp past the ceiling after ramp 6); backtracks
  deepen on repeat failures and default to twice the stretches; retries search longer (`gens`, 30 more a try);
  a search stops early only once it has a reach.
- Start box (`tas autosurf <demo> start`): a legal start (`tas start 0`, P1100) with the native guide (P1308) --
  land from the spawn's clip cage, a speed circle (289.6 u/s), capture farsh's exit line like a runway, one jump,
  clear the map's own main_map_startzone trigger and 48 u past the edge (zones are positions: a body paused on the
  edge was put back in the start), then the chain. Also `onjump` / `onexit` for a player's own prestrafe. An
  offline model of the guide's physics (scratch startsim*.py) found the line capture; in the game each strafe-side
  change costs speed, which the model does not show.
- Clicked routes: `tas route add/undo/clear/show`, `tas autosurf route`; a curve search without a demo rolls twice
  when it rides, strafing into the ramp (with no keys the ride slid off ramp 1 into the teleport under it).
- The Optimizer tab: the replay (this map's KSF, leaderboard and Momentum replays), four starts, a progress strip
  against farsh, your route with markers in the world, Advanced for the rest.
- Reviews: seven rounds (scores, armed starts, the start's counters, the tab's chips and route sync; QC's && does
  not short-circuit here and CSQC tokenize splits ':' -- both met in the tab).

Results: from the start box, ramps 0-5 and the first platform pair within 1-2% of farsh in one chain; placed at
ramp 5, ramps 6-8 with the rising ramps within 1%; placed at the ceiling ramp, ramp 7 to the last ramp finished
with no backtracks (hops and the last ramp above farsh's speed). A full start-box run reached 11 of 17 stretches
before its backtracks ran out (the budget now scales).

## P1449 Jargon (branch p1449-wall, merged 8cf14308): delivered to both installs 10 Nov ~20:30 local

- Search and chain: soft walls, rides and boards scored (the board must stay on its face min(40, 0.4 x the guide's
  ride) ticks), placement free above/before the guide's point, `low` 0.5, CEM widening and a per-state memory, a
  stretch failing from the state it already failed from skips its search, human air points (`tas route here`,
  autosurf `air`, 200 u, 85% floor). Placed at farsh's state every remaining stretch makes 99-100% of his energy; the
  full chain still drifts 1-3% (ramp 7's board, after the ramp-6 flight, the worst) -- the open problem.
- Panel rebuilt (Lex: "way too confusing ... more human"): the TAS panel opens on Jargon -- guide run (leaderboard
  lines on + KSF replays), its route auto-filled and drawn (ramp faces, numbered handles) and dragged in noclip, surf
  from the start zone or here, Effort Quick/Normal/Thorough, camera Mine/Overview (third person while it searches,
  first person while it rides). The old workshop is the "Manual TAS" tab.
- Search lines as the demo line (tas_viz_style), tas_viz_rate/lines/fade, widths from gl_2dline_width. The reliable
  stream overflowed a UDP rig client past ~3 KB/s extra: rates above 4 a second are capped there (12 KB/s loopback).
- One review (frozen 846d5e21): two server crashes (as_wk[-1] on a first-stretch failure -- arm tcrashA crashed,
  tcrashB "stuck at stretch 1"; jg_ovt[64]), the camera's lifetime, gl_mindist restore, chunked plans, safe names: all
  fixed in ebb5f9d8.
- Installed: both installs csprogs 50851dd8 / qwprogs 1e15ff34 (built from 8cf14308, fteqcc 73f9a1a4, 0 warnings;
  .prev and .pre1449j = dfedbd7e / 1b2e0c00, the P1447/P1448 delivery's); menu.dat unchanged (55d01b52); csprogsvers
  7f80b5be seeded in both; tasrevd codes.txt 115 -> 116 (.pre1449j). Engine unchanged (P1466/P1467 still need review:
  without them the QC rolls one candidate at a time and reads no ride-wall bit). Not on the lobbies (TAS is off there).
  Rig-checked on that exact build (tdeploy1): route auto-filled, stretches reached, no QC error.

## P1449 Jargon, rounds 2-3 + P1476 (main 8d8fd18d): both installs and the 12 lobbies, 10 Nov ~22:20 local

- Lex's asks of 10 Nov: overshoot on ramp 9 to 10 (a board that flies past its point along the ramp's run by 100+ u
  raises that stretch's least lead to 0.5, 0.7, 0.8: tchain15 overshot 788/786 u, then reached at 0.7); no "hyper
  wiggle" (Wider strafing: engine P1476 AIMWIDE, side flips a stretch 12 -> 4, 46 -> 8); "more points on the ramp"
  (`spots`: the guide's spot, 160 u back/on along the edge, 96 u up, the top-back corner, each on the guide's own plane,
  searched with the next stretch and the best next-ramp energy kept; tspots2 kept a non-guide spot on 4 of 7 swept
  ramps, e.g. further along +28 and +21 u/s, higher where the guide's spot missed); panel text at native sizes.
- Reviews: round 2 (818067fa + engine 231f02a7b) -- `redo 0` read as_ws[-1] (server down), previews clobbered the
  chain's options, redo kept the failed-state memory, the editor camera outlived a map load; engine: the hold capped at
  half the aim gain. Round 3 (50a97b15..544ec249) -- a stale as_redo, chip ids shared with the stretch buttons, a raised
  lead skipped as "failed again", spots on a parallel plane. All fixed (eb900d62, 887e1a213, ed63d469); rig tspots1 found
  one more (as_swv[5], no short-circuit), fixed before 544ec249.
- Engine: patch-1476 = 0b223e614 (P1476/P1467/P1466 on patch-1475), both installs' client exe b0349be2, plugin 8204a248
  kept (same sources); rig tspots1/2/3 ran that exact exe (client and server), rollouts bit-equal, 62 batches a search
  on the worker threads.
- Installed: csprogs 01d9d44e / qwprogs 91ef42d5 (8d8fd18d, fteqcc 73f9a1a4, 0 warnings) in both installs (.prev =
  50851dd8 / 1e15ff34) and on the 12 lobbies (nobody on; .prev = dfedbd7e / 1b2e0c00); menu.dat unchanged (55d01b52);
  csprogsvers b40dd39f seeded in both installs; tasrevd codes.txt 116 -> 117 (.pre1476). Rig tspots3 ran
  these bytes: a sweep, its redo with the kept spot, `redo 0` refused, no QC error. Release 0.1.44 carries this set.

## After round 3 on p1449-wall (11 Nov ~01:00, ftesurf-b8; shipped with P1478)

8e91b3d4 / 15de0242 / a17d6e65 / 7625d984: sloped roofs scored as walls, a wall tick costs the energy it took, backtracks
clear later leads and board shifts, the energy-loss backtrack only for a real deficit nearby, an overshot or skimmed ramp
boards further back and higher, `slack` only on a retry after an early path cut, hops that fall short go back to the
feeding ramp, `fresh` searches after a backtrack. From farsh's ramp-6 state the last 7 stretches finished (ttip6).

## P1478: courses -- one click for the main course, a bonus or a stage, and Continue (ftesurf-16, 11 Nov)

Lex: start maps, bonuses and stages with a click, or continue where you left off; searches that look for the correct
thing. What changed (ENGINE_PATCHES.md "Patch 1478" has the full list):
- The panel lists the map's courses from its zones; guide runs are filtered by their .rec header (track, leg), so a
  bonus replay is never a main guide; a stage may be cut from a full-run guide.
- The server takes `course T L` (or the guide's own header), refuses another course's guide, starts in that course's
  box, cuts the guide at the course's end box, replays the guide's own prestrafe when the body lands where it stood,
  and reports the finish from the timer's finish record.
- Continue: each furthest stretch autosaves `jg_<leg>` (legal-start project) + `jg_<leg>.jargon`; `tas autosurf
  continue T L [effort]` replays it exactly and goes on with a fresh backtrack budget.

Rig runs (root C:/FTESurf-worktrees/jargon-courses-1111a, driver tools/p1478_courses.py), surf_tensor2:
- t2plan1: stage 2 cut from farsh's 3:23 full run = proto's stage-2 replay's 4 boards (within ~40 u, same faces);
  wrong-course guides refused. Main plans 64 points (TAS_ASMAX) of a longer course: now said in the note.
- t2chain1: the P1449 runway start in stage 2's 270 u box jumped 375 u off the line -> the guide-prestrafe replay.
- t2chain2: replay start 20 u from the guide's standstill, stretch 1 at 1130 u/s (guide 1129); saves revs 1-2; stop;
  Continue "reproduced every saved state exactly", went on, backtracked, saved revs 3-6.
- t2chain3/4: the finish target kept the 95% floor (reached too slowly) -> no floor for a course's end; then the
  400 u reach radius let the coast fall off the end and be teleported back to the box -> 96 u.
- t2chain6/7: a 400 u reach then a coast fell into the stage's fail teleport; a padded 96 u target still ended 350 u
  short (its lines cut by a trigger). Final: the 400 u target, then the coast predicted by rollout -- played only when
  the teleport it meets leads into the course's end box, else the last stretch is a failed try.
- shape1-3 (surf_shape bonus 1, KSF x, ksfmoves 0): course start right (zone 2, track 1), the walk to the guide's
  standstill then its prestrafe; stuck at stretch 2 because stretch 1 boards ramp 1 350-375 u from the guide's point
  (board radius 800) and every stretch-2 line is cut within 3 ticks; the auto-escalation fired there. Not solved.
- Reviews (two lenses, 17 findings, no crash in the reviewed tree except NaN/fractional notes numbers): all fixed.
- The search is not deterministic from one state: stretch 1's first search from the same replayed start gave 1130,
  1130 and 1092 u/s in three runs (t2chain2-4).

## Next

Point the fast energy search at a surf_null ride (the board and ride, not the drop); then horizons past one 128-tick
tape (rollouts take 2048; the best plays as successive tapes); then target points (a human mark on a ramp the air
link before it must reach, and the mark refined by moving it); then backward windows and the whole-path search.
