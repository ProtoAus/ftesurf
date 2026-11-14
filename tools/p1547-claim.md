# P1547 claim (ftesurf-e7, Claude Code, 14 Nov 2026)

Lex (14 Nov), after P1544: "can we make it so the system works on the first load?" A load pressed within a
round trip of a save still waits for the save's answer (P1544 BACKLOG). The live save rides one usercmd
(WOP_SAVE, impulse 200, under serverinfo fs_wopsave) so the server saves at that command; the client takes
the row at the same command from its prediction and predicts a load right after it. Client + server QC.
After fetch: origin/main 3a16e6aa; highest claim P1546. Root C:\FTESurf-worktrees\opsave-20261114.
