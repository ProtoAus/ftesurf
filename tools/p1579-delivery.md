# P1579 Jargon walks into a stage after a speed-zeroing teleport -- delivery (16 Nov 2026, ftesurf-dc)

Lex, 16 Nov, watching surf_rookie: Jargon finished stage 1 countless times before going on, then bunny-hopped the
start of stage 2; unless horizontal speed carries between stages, walk to the first ramp and jump. Task root
C:\FTESurf-worktrees\jargon4-20261116-dc (rigs f1, g3-g6 and their logs under artifacts/).

## On main

FTESurf 90d1d568 (code, QC only) + 3cf910dd (notes, lextest, BACKLOG, ENGINE.txt patch 1581). Engine log entry
0d3897591 (engine code and pins unchanged: tag patch-1578, commit 216ed6bae).

## Verified

- Three VMs 0 warnings (fteqcc 1f2efd06).
- surf_rookie main, headless bench, installed client e004597b + server a34a3459: six stage starts each walked and jumped
  at the guide's own speed (262-276 u/s) 0-1 u from its takeoff, and boarded; stretch 16 of 64 in 420 s, one backtrack,
  none before a stage portal; 22/22 predicted landings bit-equal (g6). g5 (before the review-2 fixes): 20 of 64 in
  480 s, takeoffs 4 u late, 26/26. Before the patch (f1): stretch 9 in 1200 s, stage 1 re-finished each backtrack.
- Two reviews (control flow and state); every finding fixed except a replay that ends in a state that cannot board
  (deterministic; BACKLOG). The engine log's Patch 1579 entry lists the cuts measured and replaced.

## Delivery, 16 Nov 2026 UTC

- Lobbies ~04:27Z: build.ps1 -Pi from the worktree at main 3cf910dd, one combined deploy carrying P1579, ftesurf-31's
  P1581 (their yes) and ftesurf-06's P1582 review 2 (their yes); 12 rows, 0 players, warned, swapped, all 12 restarted
  and active. Live qwprogs ccf0d9a4 / csprogs 97e47c88 (.prev 56f3de88 / 92f9604e). tasrevd codes.txt 146 -> 147 lines
  (97e47c88..., backup codes.txt.pre1579).
- Both installs: qwprogs ccf0d9a4, csprogs 97e47c88 (.prev 56f3de88 / 92f9604e), menu cfea7114 unchanged; hashed equal to
  the build. csprogsvers not seeded (clients fetch the new csprogs on first join).
- The Pi's server engine is unchanged: P1579 is QC only and runs on it; P1572's push following still needs a newer Pi
  engine.

## Owner check

lextest.md "P1579 Jargon stage starts".
