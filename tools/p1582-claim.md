# P1582 claim -- save-lock loads: lead-in off by default (migrated), load latency audit

16 Nov 2026, Claude Code session ftesurf-06, task root C:\FTESurf-worktrees\savelock-audit-20261116.
Fetched both repos: claim files to p1581, engine patch log to 1577.

Lex, 16 Nov: players' videos show a 200-300 ms stutter on every save-lock load. QC (cl_saveloc.qc, cl_hudedit.qc):
cl_sl_leadin default 0 and a once-per-config move of a saved 1; tools/p1384lead.py gets a real key-hold length.
Docs: ENGINE.txt, BACKLOG.md (save-lock / trail-load entries), lextest.md.
