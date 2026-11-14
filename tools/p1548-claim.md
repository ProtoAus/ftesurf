# P1548 claim (ftesurf-e7, Claude Code, 14 Nov 2026)

Lex (14 Nov): replace the pink/black missing-material checker with the surface's colour when we have it
-- "some sort of index for all of the textures ... where it will just shade that surface that colour,
with lightmap" -- and other improvements for players without the assets. P1191 already tints map
materials with no VMT from dtexdata reflectivity; this extends it to a VMT whose base image is missing
(map and model), to model materials (a colour index built from the installed games, shipped), and to
0x0 texdata. hl2 plugin (mat_vmt.c, mod_vbsp.c) + tools/ index builder + the index data.
After fetch: game origin/main f4d0bce9, highest claim P1547; engine tags to patch-1543.
Root C:\FTESurf-worktrees\matcolour-20261114.
