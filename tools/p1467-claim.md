# P1467 claim (ftesurf-b8, 10 Nov 2026)

tas_rollout_batch: a generation of surf-planner candidates simulated on worker threads (Lex: multi-threaded tests).
Movement, collision scratch and BIH clip flags become thread-local; the entity list is built once on the main
thread; per-tick trigger queries get a worker-safe dedupe; portals, Q2/Q3 BSP and unloaded models fall back to
one thread. Engine sv_tas_rollout.inc, pmove/pm_source/pmovetst, com_bih, world.c, pr_cmds.c (+ QC sv_tasoptimize.qc).
