# P1407: surf_voyager hands-free -- why a flight sometimes does not finish (8 Nov 2026, ftesurf-3a)

Lex: "surf_voyager can be played back without a keypress once you walk into the start zone, and the map
completes most of the time, idk if because framerate drops, or rng, or rampbugs."

## Measured (tools/p1407voy.py, hosted game on C:\FTESurf's build of 8 Nov, private homedir)

| condition | flights | finished | time |
| --- | --- | --- | --- |
| 250 fps, +back 600 ms | 3 | 3 | 1:06.270 each |
| 30 fps (every packet 2-3 ticks) | 3 | 3 | 1:06.270 each |
| 250 fps, entry holds 450/800/1100 ms (different entry paths) | 3 | 3 | 1:06.270 each |
| 250 fps + 20 random hitches (cl_maxfps 15 for 60-250 ms) per flight | 4 | 4 | 1:06.270 each |

1:06.270 = 4418 ticks = Lex's Momentum run of the map. The hitched flights had 678 ticks inside
multi-tick packets against 378 clean (the .rec `in` rows' part flag), so the hitches landed, and the
shield edge read `z 4015.08 vz 166.87` in every flight. Lobby finishes (Lex 4 Nov, bussn 6 Nov) equal
the hosted .rec at every common sample (0.00 difference).

## Ruled out, and how

- RNG: `run_startjitter` is 0 on this map (cfg/maps/map_surf_voyager.cfg since fd5fe8d7; the
  timer logs `startjit rule 0`).
- Frame drops: the engine runs each tick of a long packet as its own part (Patch 893,
  `input_cmd_later`); the hitch arm above.
- Moving solids: of 38 func_rotating only rotation_near_Y is solid; it and its two solid combineball
  props stay ~1000 units from the route (Momentum run's path). The shield sphere is `solid 0`.
- Mouse/view: with no movement keys the mover reads the view only on ladders (pm_source.c).
- Settings: lobby .rec `pmpin` lines equal the hosted one. markbeaton54's 4419 (1 Nov) ran mover
  pmsrcver 11, the previous version.

## Not demonstrated

One lobby attempt (Lex, lobby 1, 4 Nov ~16:40Z) left the shield trigger (*558) at `z 4017.81 vz 167.27`
against 4015.08/166.87 and did not finish; its start edge (*561) was identical. Unfinished attempts keep
no recording, so its inputs cannot be read: a key touched during it, or a lobby-only effect (packet loss
bursting commands at the server: not yet tested), remain. Next: a dedicated server + client arm with
`net_fakeloss`, and keeping a short per-tick record of unfinished attempts so the next failure can be
diffed tick by tick against a clean flight.
