# Patch 1575 claim (ftesurf-46, 16 Nov 2026)

Engine: the main view's water capture targets (reflection texture, its depth and multisampled pair under
r_reflectmultisample, refraction texture/depth and their FBOs) are made and cleared at activation, at the size the
first capture will ask for, so the driver allocates their storage behind the loading screen rather than on the first
sight of water (29-53 ms frames on surf_chateau/boreas in P1574's first-play census). Root
C:\FTESurf-worktrees\lows4-20261116-46.
