# P1436 -- func_fish_pool's fish swim, simulated on the client

ftesurf-b8, 9 Nov 2026 (entgap-20261108, look-only group). Root C:\FTESurf-worktrees\xhair-20261108-b8
(tools/armsc.sh, armsd.sh, fsh1.cfg, rigs/bm-fs*).

## What

- func_fish_pool (216 pools, 1,275 fish on 28 maps; at most 20 a pool, 240 on surf_garden_css) drew nothing.
  src/client/cl_fish.qc ports fish.cpp and c_fish.cpp: each pool's fish_count fish (its model) start at its
  origin; every 0.1 s line of sight (every 0.5 s, spread across pools), Avoid's two feelers and max_range,
  FlockTo the visible fish and the centre, the speed-limited turn, calm/panic speeds and the go/move timers,
  the edge clamp, then the step's move stopped by the world. Each fish is drawn tracking the position the
  network would have carried (sampled at the step's start on SendPropFloat's 7-bit grid) with c_fish.cpp's
  spring, sub-stepped, and its wiggle. The local player within 75 units panics a fish. Pools past 3000 units
  from the eye rest. vbsp_fish 0 turns them off (live).
- Client only (Lex: decorative motion is client-side); the server still drops the entity, and each client
  runs its own fish. Fish are non-solid in Source too.

## Measured (client C:\FTEQuake\fteqw64.exe c61f874b, surf_garden_css pool 0; 0 QC errors)

- Review-1 build (cs 7de36a4c), tools/fsh1.cfg: "fish: 240 in 14 of 14 func_fish_pool". From the side, 1030
  and 1142 px change between shots 2.6 s apart over the pool (the fish, rigs/bm-fs2-new); the control (P1433
  build) 0 px and no fish. The subject's own line every 2 s: fish 0 swims at its calm 10.7 u/s with the drawn
  position within ~5 units of the simulated one; after the camera moves into the pool it panics (want 52.7)
  and reaches 52.7 u/s.
- First build: the same pictures (1106 / 1183 px).

## Review

One round. Fixed: the tracking spring blew up on a frame over ~0.125 s (fast fish thrown out of the pool) --
sub-stepped at 0.05 s; a trace and a relink for every fish every frame -- the move is once a step and a fish
relinks only after a 32-unit move; the client sample is taken at the step's start on Source's grid (it was the
moving position every frame); all pools' sight checks fell in one frame; spawn timers had expired at load (the
clock arrives later); panic from the camera rather than the predicted origin; vbsp_fish now reloads live.

## Delivery

- LIVE 9 Nov ~05:00 local: 12 lobbies (nobody on; warned; 0 QC errors) qw 23bcf6b5 + cs 0fe650c4 from main
  beccbabf (P1433 + P1435 + P1436 in one build); both installs the same (.prev dd2b7fa2 / a90ec502, .pre1436);
  csprogsvers f2c58ee3 on the Pi and both installs; codes.txt 104 -> 105 (.pre1436). The client half is in
  csprogs: players have it from the lobbies.

## Left

- Frame cost on surf_garden_css not measured (estimated from the trace counts: ~5k Avoid and ~4k sight traces a
  second with every pool awake, plus 240 predraws a frame).
- Other players do not panic a client's fish; fish never die (no damage).
