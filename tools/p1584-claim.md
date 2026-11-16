# P1584 claim -- hud_crosshair (and its size/alpha) saved between sessions

16 Nov 2026, Claude Code session ftesurf-06, task root C:\FTESurf-worktrees\savelock-audit-20261116.

Lex relaying akatosh: hud_crosshair does not save between sessions because default.cfg sets it every launch.
ftesurf/cfg/default.cfg: the three crosshair lines become seta. Docs: ENGINE.txt, lextest.md.
