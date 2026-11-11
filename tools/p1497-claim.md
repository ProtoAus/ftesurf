# P1497 claim (ftesurf-18, Claude Code, 11 Nov 2026)

The sprite/beam sky test backs off while a verdict holds: the re-trace distance doubles per confirming trace, up to
256 units and 1/32 of the distance (16 within 512 units), and resets on a change. surf_fairy at Lex's settings
re-traced 38 far beams ~3,600 times a second with no change in ~88k traces (0.34 ms of CSQC a frame, in-motion
r_budget A/B). QC cl_sprites.qc only. Root C:\FTESurf-worktrees\lows2-20261107-opus.

Delivered 11 Nov: 12 lobbies + both installs cs 4e593c7e (main bb0f284d), after review. Final numbers and the staleness trade in ENGINE.txt "Patch 1497 / 1499".
