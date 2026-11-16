# P1589 claim (ftesurf-64, 16 Nov 2026)

Optional movement profiles on the existing `sv_movementprofile` map-spawn switch:
`hl2-pre` and `hl2-post` (Source mover + HL2 settings + the HL2 jump boost, before/after
its limiter), `ag-1000` (AG at 1 ms ticks), `cs16` (AG mover + CS 1.6 settings,
jump stamina and bhop cap). Unranked practice, namespaced like P1542's ag-100/ag-250.

Engine: pm_ag.c/h, pm_ag_world.c, pm_source.c, pmove.h, sv_phys.c, sv_ccmds.c,
sv_held_file.c, pr_cmds.c, cl_main.c, cl_input.c. QC: sh_defs.qc, sv_player.qc,
sv_resume.qc, cl_replay.qc.
