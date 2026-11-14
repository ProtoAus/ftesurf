# P1550-P1552 claim (ftesurf-e7, 14 Nov 2026)

Lex (14 Nov): fix the crash, the prederrors, and the report system if it is broken.

- P1550 (engine): "BZ_Malloc: Failed on allocation of 18446744071578836992 bytes" on the story-mode switch to
  the next map's lobby -- three crash records from Akatosh on patch-1476 (has P1417/P1421), same size as
  MetalGio's 8 Nov report. Files: engine (site to be found), ENGINE_PATCHES.md.
- P1551 (QC, maybe engine): the causes of the prederror reports of 8-13 Nov (39 since the last triage).
  Files: src/client/*, tools/p1551-*.md.
- P1552 (QC/engine): F6 reports arriving with only the server's half at 330+ ping (8 of 39).
  Files: the prederror upload path (CSQC/SSQC), tools/prederr_triage.py.
Shared docs: PATCHNOTES.md, lextest.md, AGENT_NOTES.md (P1195 section), BACKLOG.md.
Task root C:/FTESurf-worktrees/reports-20261114 (OWNER.md).
