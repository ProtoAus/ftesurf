# P1603 claim -- lex-90 (Claude Code), 2026-11-17

Lex (17 Nov): Linux runs should rank, tagged as Linux runs; boards highlight them blue with the tooltip
"Linux: Not mouse verified"; Linux anti-cheat later. Run-flag bit 21 stays for movement styles, so the mark is a
separate integer `plat` carried in the .rec, saves, the lobby POST, surfd (runs/replays.plat) and the board JSON.

Files: src/server/sv_timer.qc, sv_saveloc.qc, sv_rewindstate.qc, sv_lobby.qc, src/shared/sh_defs.qc,
src/client/cl_replay.qc, cl_online.qc, cl_scores.qc, ftesurf/cfg/lobby/lobby.cfg; surfd/surfd.py, recplot.py,
templates/admin_run.html, web/board.js, board.css, test_plat.py; tools/reccheck.py (+ test). Docs: engine
ENGINE_PATCHES.md, ENGINE.txt, PATCHNOTES.md, AGENT_NOTES.md, BACKLOG.md, tools/backend-pending.md, surfd/README.md.

## Delivery (17 Nov 2026)
FTESurf main (this commit's parent chain), three review rounds (predicate/persistence, evidence/backend, cheater).
NOT deployed: order in tools/backend-pending.md (surfd generation, lobby progs with sv_rank_linux 0, then 1).

## Live (18 Nov 2026, worldofsurf-43)
Steps 1-2 rode gen1603 and the P1604 lobby progs; Lex's Linux run (bhop_2hrs 0:17.520) posted `plat 1` to the
community board; step 3 set `sv_rank_linux 1` in lobby.cfg and on all 12 lobbies (tools/backend-pending.md).
