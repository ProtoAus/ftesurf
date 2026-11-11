# P1504 claim (ftesurf-18, Claude Code, 11 Nov 2026)

The light-glow glare checks its trace budget (P1488) before the four corner rays as well as before each glow: a glow
is 1 centre + 4 corner rays (~180 us each on surf_fairy), so one check let a frame trace ~0.9 ms past the 1 ms
budget (1.6-1.9 ms of traceline in fairy's slowest frames, players' default sprites/glows). Over budget, the glow keeps its
last answer and is first next frame. QC cl_sprites.qc. Root C:\FTESurf-worktrees\lows2-20261107-opus.

Delivered 11 Nov 12:51Z after two reviews: the check runs every 16 visits too (the measured overrun was culled glows' QC, not the corners alone); 12 lobbies + both installs cs 267e9b9b; tasrevd codes.txt appended (.pre1504).
