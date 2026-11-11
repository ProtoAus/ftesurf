# P1499 claim (ftesurf-18, Claude Code, 11 Nov 2026)

The mouse pad (hud_mouse, on by default) sends a stroke that crosses no panel edge straight to Line_Seg2D,
skipping MPad_Seg/MPad_Stroke and the colour calls: the same strokes with fewer QC calls. The whole pad costs
~0.15 ms of CSQC a frame over a full trail (in-motion r_budget A/B, surf_fairy). QC cl_mouse.qc only.
Root C:\FTESurf-worktrees\lows2-20261107-opus.

Delivered 11 Nov: 12 lobbies + both installs cs 4e593c7e (main bb0f284d), after review. Final numbers and the staleness trade in ENGINE.txt "Patch 1497 / 1499".
