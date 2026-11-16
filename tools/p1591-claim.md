# P1591 claim (ftesurf-64, 17 Nov 2026)

Lex: "add autohop to every game mode". `pm_autobunny` (canonical 1, the default mode's
autohop) now applies under every `sv_movementprofile`: the AG mover (ag-100/250/1000,
cs16) honours it on both sides, and hl2-pre/hl2-post stop forcing it to 0. Older clients
are refused from a GoldSrc profile while it is on (they would mispredict every hop).

Engine: pm_ag.c/h, pm_ag_world.c, sv_phys.c, sv_user.c, cl_main.c, tools/test_pm_ag*.
QC: docs (PATCHNOTES, lextest, ENGINE.txt). Root: C:\FTESurf-worktrees\autohop-20261117-64.
