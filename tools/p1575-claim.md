# Patch 1575 claim (ftesurf-46, 16 Nov 2026)

Engine: the main view's water capture targets (reflection texture, its depth and multisampled pair under
r_reflectmultisample, refraction texture/depth and their FBOs) are made and cleared at activation, at the size the
first capture will ask for, so the driver allocates their storage behind the loading screen rather than on the first
sight of water (29-53 ms frames on surf_chateau/boreas in P1574's first-play census). Root
C:\FTESurf-worktrees\lows4-20261116-46.

Delivered 16 Nov 2026 03:46Z: engine main 216ed6bae (tag patch-1578, stamp git-8797-patch-1578-0-g216ed6bae), with P1575 and P1578 together. Both installs' client exe e004597b (predecessors ftesurf64/fteqw64 4fffcfb1 patch-1572 kept as .prev, archived in the task root's artifacts/delivery-p1575). Measured and reviewed: engine ENGINE_PATCHES.md Patch 1575.
