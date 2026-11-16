# Patch 1578 claim (ftesurf-46, 16 Nov 2026)

Engine: on a fogged map the activation warm-up also compiles the fog variant of each listed permutation of the
map's larger programs (more than the 3 permutation bits Patch 1574 warms whole), and the fog-only permutation. The
warm list is shared by every map, so a permutation seen only on unfogged maps compiled mid-run on a fogged map's
first play (surf_null after P1574: vmt/vertexlit 0x128/0x328, vmt/refract 0x20, 10-16 ms each).
Root C:\FTESurf-worktrees\lows4-20261116-46.
