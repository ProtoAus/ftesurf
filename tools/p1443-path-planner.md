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

## Next

Point the fast energy search at a surf_null ride (the board and ride, not the drop); then horizons past one 128-tick
tape (rollouts take 2048; the best plays as successive tapes); then target points (a human mark on a ramp the air
link before it must reach, and the mark refined by moving it); then backward windows and the whole-path search.
