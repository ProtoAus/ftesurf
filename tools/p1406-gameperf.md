# P1406: game-code frame audit and exact speedups (8 Nov 2026, ftesurf-3a + helper)

Lex: "the player collision/movement and just everything the QC does in a frame to be maximum quick ...
the movement stays the same as Momentum." Full measured write-up: BACKLOG.md (P1406 entry, c435c5f6).

- surf_voyager flight at Lex's settings: 485 fps, CPU 1.87 ms/frame; CSQC view+HUD 0.51, prediction
  0.14 (engine mover; QC hooks ~0.01), QC physics 0.015. Client QC ~53k instructions/frame.
- Changed (QC only, movement untouched): StartFrame builds the player list once (sv_plchain), ~a dozen
  per-frame walks read it -- QC StartFrame 134 -> 61 us per server frame, one client (check build:
  0 of 67,160 answers differ from find(); mutant 16,405); func_lod predraw keeps its box centre
  (7,441 -> 5,179 instructions/frame; 0 of 5.8M differ). Client frame time: no change within rig noise.
- Reviews: round 1 (one crafted-map edge, fixed 5424ab86 / 471abdbd), round 2 clean (order and
  staleness traced against find(); unenforced rule: a new writer of classname "player" must keep
  the list in step -- the file header says so).

## Delivery

- LIVE 8 Nov (local afternoon): 12 lobbies (2 occupied, warned + 10 s), qw d4d20322 / cs ba7e0c60,
  main 45fb397d; every lobby booted with 0 QC errors; codes.txt 93 -> 94 (.pre1406). Both installs
  (C:\FTESurf, C:\FTEQuake under rig.lock), .prev beside each file, csprogsvers 6af51682 seeded.

## Left (BACKLOG has the detail)

Server, exact: SV_PeRow's three sprintfs per command; acct_here walks (Archive_Frame, PlayStats_Frame,
Account_SelfFrame); 16 registercvar calls in Lobby_Frame per frame. Lex's call (changes timing/state):
posing only on-screen csprogs movers; a slower sky-trace cadence. Not done: owned-trigger list for the
mirror (needs prediction evidence). Pre-existing: a non-client edict named "player" crashes
SV_SaveLocReset (crafted map only).
