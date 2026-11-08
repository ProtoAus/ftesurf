# P1416 -- one-shot particle effects (bursts)

ftesurf-b8, 8 Nov 2026. Root C:\FTESurf-worktrees\xhair-20261108-b8 (bakes pbfull2/gd, arms rigs/pb-*, pl-*).

## What it does

- tools/pcf.py: an instantaneous emitter, or a continuous one with an emission_duration (a timed spurt),
  bakes as a `burst` row: the 26 psys words + count, duration (0 = at once), delay. A system with no
  emitter but children is a count-0 container row. No decay and no fade-out: PERSIST_DIE (3600 s). A
  spurt's count is capped by what can be alive. Clients before P1416 read only psys rows.
- cl_emit.qc: bursts spend a queued count outside the budget (128 a burst, 1024 in all, a frame), a
  spurt over its duration, after its delay, not on the first frame after a load. Fired at load for
  start_active systems and on the server's Start; a Stop drops the queue. A one-shot's children start
  with it. A never-dying one is a state: placed while on and in range, once, again after a reload.
- Wire: ENTWIRE_PSYSSTATE2 = ENTWIRE_PSYSSTATE + start count + fresh flag (old reader kept for demos).
  The server counts only off-to-on Starts (Source's StartParticleSystem ignores a Start while active);
  a client fires new starts (at most three), on first sight only one made in the last second.

## Measured (client fteqw64 824d41cc)

- bhop_angst booster (ent_fire): 66 particles a fire; two Starts 150 ms apart fire once; Stop then Start
  fires; a never-networked system fires on first sight; reconnect replays none; a 1.1 s spurt places
  47/93/122 at 0.55/1.05/1.55 s. Pre-P1416 build: 71 systems, no burst particles (the control).
- kz_bhop_benchmark tele2 at load (vbsp_emit_dist 0): 50 particles on the fixed build, 43 on the build
  before the first-frame wait -- the reviewer's first-frame loss did not occur in that run (not shown).
- bhop_badges2 badges_actizonex (never dies): there at 32 s and after a reconnect.
- Bakes: 1797 burst rows on 122 maps; every pre-P1416 psys row survives unless its system is now a burst
  (287 of 287 names). One review (4 defects, all fixed in review 1).

## Delivery

- LIVE 8 Nov ~17:25 local: 12 lobbies (nobody on, 0 QC errors) qw c80f25c0 + cs 1014478d, fteqcc 73f9a1a4;
  both installs the same (.prev 63fa2880 / 3a379a1b, .pre1416); csprogsvers 87a2cfc3 on the Pi and both
  installs; codes.txt 96 -> 97 (.pre1416). Bakes in C:\FTESurf\ftesurf only: 46 cfgs changed, index 7791
  lines (1797 burst rows); the old index is in the root's backup/. Players get the bakes with the release.

## Open

- surf_tensor2 and surf_boreas keep their installed bakes, which predate P1012's shapes (a rebake changes
  51 / 20 lines of their cfgs). P1411's note that the four first bakes "rebaked byte-identical" was wrong:
  they were never on the bake list. A rebake of those two wants an owner's look.
- Nested containers start one level down only. Stopping a never-dying system leaves its particles.
