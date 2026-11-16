# P1584 -- hud_crosshair saved between sessions

Owner: ftesurf-06 (Claude Code), 16 Nov 2026. Task root C:/FTESurf-worktrees/savelock-audit-20261116 (OWNER.md).

## Report

Lex, relaying akatosh: "hud_crosshair value is not saving between sessions because its set by default.cfg every game
launch".

## Found (true, for a value set any way but the HUD editor)

- The engine runs cfg/default.cfg, then the saved ftesurf.cfg (cl_main.c CL_ExecInitialConfigs; cmd.c redirects
  `exec config.cfg` to MAINCONFIG), so a saved `seta` would win.
- But default.cfg's plain `set hud_crosshair 1` creates the cvar unarchived, and CSQC's `registercvar(...,
  CVAR_ARCHIVE)` on an existing cvar adds only userinfo/serverinfo flags (cvar.c Cvar_Get2). So `hud_crosshair 3`
  typed at the console (or set by a bind or a cfg with `set`) is never written by cfg_save: the next launch is back
  on 1. The HUD editor writes `seta`, which archives it -- the configs that already hold a `seta hud_crosshair` line
  keep working. default.cfg's header records the rule; con_notifylines is the precedent for `seta` there.
- 211 cvars default.cfg sets are registered CVAR_ARCHIVE by the game code and behave the same way. That is the
  design (a plain `set` lets a changed default reach every player who never chose one); not changed here.

## Change

default.cfg: `seta` for hud_crosshair, hud_crosshair_size and hud_crosshair_alpha. The saved ftesurf.cfg still
runs after it, so a player's value wins; FTE saves archived cvars, so a later default change to these needs a
migration (HE_MigrateDefaults).

## Measured

tmp/p1584xhair.py in the task root: an isolated basedir (tools/p1384lead.py prepare(), MAINCONFIG ftesurf), exe
e004597b, local game on surf_dune; launch 1 types `hud_crosshair 3` after CSQC loads and runs `cfg_save`; launch 2
reads the value after CSQC loads.

| default.cfg | before | typed | saved by cfg_save | after restart |
|---|---|---|---|---|
| main (`set`) | 1 | 3 | no hud_crosshair line | 1 -- lost |
| P1584 (`seta`) | 1 | 3 | `seta hud_crosshair "3"` | 3 -- kept |

## Delivery

Both installs' cfg/default.cfg 705ad2cd (.prev b82050b9 = main before P1584), 16 Nov ~15:10 local. Players get it
with the next release (progs deploys do not carry cfg).
