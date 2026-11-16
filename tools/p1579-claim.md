# P1579 claim -- Jargon: a stage start after a speed-resetting teleport walks and jumps; no backtrack through it

16 Nov 2026, Claude Code session ftesurf-dc, task root C:\FTESurf-worktrees\jargon4-20261116-dc.
Fetched both repos: claim files to p1578 (ftesurf-46), engine tag patch-1574 -> 1579.

Lex, 16 Nov, watching surf_rookie: Jargon finished stage 1 countless times before going on, then bunny-hopped the
start of stage 2; unless horizontal speed carries between stages (it does not on surf_rookie), walk to the first ramp
and jump. Rig f1: after the stage-end portal (1 u from the guide's landing, speed reset) stretch 5 hopped and failed,
and each backtrack replayed stage 1 into the same state ("counted as failed again").
Scope: src/server/sv_tasautosurf.qc (QC only); PATCHNOTES.md, BACKLOG.md, lextest.md.
