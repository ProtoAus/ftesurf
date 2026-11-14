# P1554-P1556 claim (ftesurf-e7, 14 Nov 2026)

Lex (14 Nov): speed up prederror uploads ("HTTP via reportd") and fix two P1551 leftovers.

- P1554 (QC + reportd): the player's half of a prederror report goes over HTTP to reportd's /api/report with a
  one-time token the lobby issues at the begin; the lobby still writes its half; the in-game chunks stay as the
  fallback; prederr_triage.py joins the halves. Files: src/client/cl_prederr.qc, src/server/sv_prederr.qc,
  surfd/reportd.py, tools/prederr_triage.py.
- P1555 (QC): `!r` right after a run re-arms in a start with a startmark (surf_fiellu, 172 units).
- P1556 (QC/engine): the server move at bhop_1n5an3's start with no client trigger (376 units).
Shared docs: PATCHNOTES.md, BACKLOG.md, AGENT_NOTES.md (P1195 section). Task root C:/FTESurf-worktrees/reports-20261114.

Status 14 Nov ~17:12Z: P1554 and P1555 LIVE (reportd, 12 lobbies, both installs); P1556 not established (BACKLOG).
Record: tools/p1550-reports.md.
