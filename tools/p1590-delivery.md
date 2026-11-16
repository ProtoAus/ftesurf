# P1590 Groups, one mode row, the server beside the board, clone maps once -- delivery (16 Nov 2026, ftesurf-06)

Lex, 16 Nov: Momentum/KSF Groups on the leaderboard (coloured lines where the group changes, your group as a
badge on Main/stages/bonuses), based on Momentum's or KSF's times; a map and its `_ksf`/CS:S build counted once on
the Stats page; the server's players floating right of the TAB board with their main time in their colour; the
filters as one exclusive row (Segmented blue, TAS purple, the directions). Root C:\FTESurf-worktrees\groups-20261116-c7.

## On main

- 03922e48 (P1590), 7b076341 (follow-up: the floating list starts on the column headings' line, clear of the HUD's
  top-right map block, seen overlapping in the 1280x720 lobby smoke). Engine log: ftequakers main de10b00a4.
- The ladder: Lex's calculator with its defaults (Top 10; G1 to max(15, 10 + 2% X); cutoff max(100, 67% X); G2-G5
  log-spaced, G6 at the cutoff; 5 ranks the narrowest). Reproduces his 50 / 150 / 50,000 screenshots exactly.
  X and the cut times come from the leg's larger imported board: Momentum (full depth: 5,365 times on
  surf_borderlands main, 15,913 on surf_utopia) else KSF (partly crawled: a lower bound, BACKLOG).

## Verified

- surfd/test_groups.py 10/10; test_board, test_web, test_completion_pool, test_home_completion, test_mapcards,
  test_profile_completion_segmented, test_profile_filters, test_variants pass after the review fixes.
- tools/p1590groups.py (this checkout's surfd over a scratch database; the game driven by `scores mode`, graded on
  `scores status`): 14/14 on the shipped build and on 7b076341. Frames inspected: lines and pills, strips, badges
  G2/G4, footer source, Segmented/TAS lit in their colours, the floating list.
- Read-only timing on the Pi's database: cold worst 0.3 s (surf_rookie, 19 legs, 171 queries), cached 600 s.
- Reviews: one round per lens (QC state; surfd cost/consistency), every finding fixed and re-measured.

## Delivery, 16 Nov 2026 UTC

- Lobbies ~11:03Z: build.ps1 -Pi from the worktree at 03922e48; directory showed all 12 lobbies with 0 players;
  warned, swapped, 12/12 restarted and active, no QC errors since. Live csprogs 427bd885 (.prev 97e47c88, P1579's),
  qwprogs ccf0d9a4 (unchanged bytes). This also brought the lobbies the released P1587/P1588 client QC.
- tasrevd codes.txt 148 -> 149 lines (427bd885..., backup codes.txt.pre1590).
- Both installs: csprogs 427bd885, menu 7cc94995, qwprogs ccf0d9a4 (C:\FTESurf by hand: .prev = 0.1.48's cc032a87 /
  39d64915); csprogsvers 2cc0b58d.dat seeded in both.
- pi_lobby_smoke against 27510 on the 0.1.48 exe: PASS (served csprogs 427bd885, board drew, no QC error).
- 7b076341 rides ftesurf-64's P1589 ship build and -Pi (agreed by message); not deployed by this session.
- Superseded the same day by ftesurf-64's P1589 deploy from main 811361e2 (carries P1590 and 7b076341):
  lobbies cs e393efdc / qw d5774a9f (.prev 427bd885 / ccf0d9a4), 12/12 active; both installs cs e393efdc,
  qw d5774a9f, menu 3b1928ae; tasrevd codes.txt 150 lines (.pre1589). Read back from the Pi and both installs.

## Not live: the surfd half

game_groups and the completion families are on main but surfd runs a sealed guarded generation; a new one is
built and cut over by the backend transition machinery with an owner root step (P1569/P1570). Until then:
- the client's groups request is answered 400; it waits 30 s and asks again (no lines, no badges);
- the Stats page still counts a map and its CS:S build twice.

## Owner check

lextest.md "P1590 Groups, one mode row, your server beside the board".
