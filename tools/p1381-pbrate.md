# P1381 -- personal bests carry their tick rate; zone_edit's P1371 quirks

ftesurf-3a (Claude Code), 8 Nov 2026 local. Owner: "can you fix those last things you wrote up?" after
P1371. QC only. Claimed as 1377; pi.dev's similarity patch took 1377 on main first.

## Why

P1371 lets a zone file move a map between surf (66.67 Hz) and bhop (100 Hz). Personal bests were stored
as raw ticks (data/runs/<map>/best.pb; client lobby times as `<ticks>_lobby.rec` names and lobby.pb), so
after a move a 45 s best counted at 66.67 Hz (3000 ticks) read as 30 s, and a slower run could be refused
or a faster one kept wrongly; the lobby-time pruner could even delete the faster file.

## What changed

- sv_timer.qc: SV_PBSave writes `rate <pm_ticrate>`; SV_PBLoad converts every best/split/cp from the
  file's rate to the map's (nearest tick) and says so once. Older builds skip the 2-word line.
- cl_lobbytime.qc: LT_FileFlags records the file's `tickrate`; LT_BestClassOnLeg compares by duration
  (LT_AtTick); the card's `mine` exclusion needs the current rate; lobby.pb `best` lines carry the rate.
  The unranked-over-certified name guard checks the destination file itself (review 1: comparing a
  converted best with the raw stamp let an unranked time overwrite a certified file of another rate).
- cl_results.qc: the card's rank converts lobby files only (review 2: it runs at stage boundaries
  mid-run and must open no extra files; local _pb/_run stay raw, BACKLOG).
- cl_zoneedit_extra.qc: re-clicking the selected mode keeps the local air accel (the note names the
  real value and says the lobbies use the mode's preset); tiers stage only when they differ from the
  table; P841's speed-cap note first whenever its condition holds.
- Not done: the menu. m_main.qc ui_map_tick (the "menu shows lobby times at the wrong rate" item) has no
  caller since P1062, so nothing visible was wrong there.

## Verification (Windows rig, hosted game, installed P1371 exe 0fc47fd5)

agtricks (100 Hz), planted best.pb `rate 0.015 / best 0 0 3000` and lobby files 0003000@0.015 (45 s),
0004400@0.01 (44 s): control (installed P1371 QC) `cmd timer` pb 0:30.000, `lobbytime` best 3000;
P1381 pb 0:45.000 (+ the load notice), best 4400. Collision: certified 0002000_lobby.rec @0.015, then
`lobbytime keep 0 0 2000 512`: the first cut overwrote it (flags 0 -> 512, certified best gone); the fix
refuses and the file is untouched. zone_edit: local airaccel 120, re-click Surf: file still 120, Surf
staged. QC 0 warnings (fteqcc c24ede65). Two review rounds; left items in BACKLOG (P1371 entry).

## Delivery (8 Nov local / 7 Nov ~14:45Z)

- Lobbies: `build.ps1 -Pi` from a clean worktree at main a3334ff2 (on ftesurf-1d's P1376/P1373 deploy):
  qw 0795c83a / cs ba19b605 (.prev = 1d's 5f2c5837 / a3d7aef3), 1 player warned, 12/12 restarted, 0 QC
  errors in server1-12; Pi engine unchanged (632ceca2, P1371). tasrevd codes.txt 82 -> 83 (.pre1381);
  csprogsvers d6c8a764.dat seeded on the Pi.
- Installs: C:\FTESurf and C:\FTEQuake qw/cs/.lno = the same build (.prev = 1d's), csprogsvers seeded;
  menu and cfgs untouched.
