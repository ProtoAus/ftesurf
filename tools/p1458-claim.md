# P1458 claim -- ftesurf-49, 2026-11-09T16:43:57Z

env_lightglow fade ramp: MaxDist < MinDist was read as "on beyond MaxDist" (Source remaps it: on near, off far). surf_beginner2 stage 7 whiteout. Plus a "Light glows" gfx row (vbsp_lightglow) so Sprites off is not undone by the glows fading back in. Files: src/client/cl_sprites.qc, src/client/cl_gfx.qc. Root C:\FTESurf-worktrees\lexlist-20261110-49.
