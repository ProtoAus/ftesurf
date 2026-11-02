Patch 1207 claimed by ftesurf-e2 (Claude Code), 2026-11-02T08:24Z, from Lex's prederror report (2 Nov):
in a local game the client replays no commands after spawn (cl_pred.c breaks at to.time >= simtime), so
nothing is predicted and every server-side move (the `!r` reset, 2992 u on surf_anubis) is offered as a
prederror report. CSQC only (cl_prederr.qc, cl_warpop.qc): no report box while prediction is not running,
the reason a reset went unpredicted in the context, and the progs identity in the report.
Root: C:\FTESurf-worktrees\anubisreset-20261102T0713Z
