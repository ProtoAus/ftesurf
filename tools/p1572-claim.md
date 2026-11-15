# P1572 claim -- Jargon: tuning weights + per-stretch results, faster search, trigger_push in tas_rollout

16 Nov 2026, Claude Code session ftesurf-dc, task root C:\FTESurf-worktrees\jargon4-20261116-dc.
Fetched both repos: highest heading P1570 (engine ENGINE_PATCHES.md), tag patch-1571 (appearance
tables, unmerged), claim files to p1570 -> 1572.

Lex, 16 Nov: Jargon is slow and completes little; does it know push triggers; give numbers to adjust.
Scope: src/server/sv_tasoptimize.qc, sv_tasautosurf.qc, sv_player.qc (search frame), src/client/cl_jargon.qc
(and cl_tasoptui.qc if the panel needs it); engine engine/server/sv_tas_rollout.inc, sv_tas_rewind.inc;
ENGINE_PATCHES.md, ENGINE.txt, PATCHNOTES.md, BACKLOG.md, lextest.md.
