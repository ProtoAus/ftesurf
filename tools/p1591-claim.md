# P1591 claim (ftesurf-64, 17 Nov 2026)

Lex: "add autohop to every game mode". `pm_autobunny` (canonical 1, the default mode's
autohop) now applies under every `sv_movementprofile`: the AG mover (ag-100/250/1000,
cs16) honours it on both sides, and hl2-pre/hl2-post stop forcing it to 0. Older clients
are refused from a GoldSrc profile while it is on (they would mispredict every hop).

Engine: pm_ag.c/h, pm_ag_world.c, sv_phys.c, sv_user.c, cl_main.c, tools/test_pm_ag*.
QC: docs (PATCHNOTES, lextest, ENGINE.txt). Root: C:\FTESurf-worktrees\autohop-20261117-64.

## Delivery (17 Nov 2026, LIVE)

Engine main 7ee3b23e7 (annotated tag patch-1591, stamp git-8820-patch-1591-0-g7ee3b23e7; TLS refptr check clean).
QC main 69dba83b (docs + ENGINE.txt pin; no QC code). Both installs run client e1f65829, fteqwsv64 06872866,
fteplug_hl2 8569b6b7, ui_imgui 085fe470 (C:\FTEQuake also cod 63ebe04f, box3d 0c0d200e, ode 4c09795c); .prev kept.
The .dat files are ftesurf-63's P1592 deploy (cs 489fca3a, qw 3287648a, menu 78254538), untouched. Lobbies: no
change (QC unchanged; profiles are chosen per server). Evidence: engine ENGINE_PATCHES.md Patch 1591. Owner feel
check: lextest.md.
