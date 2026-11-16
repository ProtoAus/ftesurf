# Patch 1578 claim (ftesurf-46, 16 Nov 2026)

Engine: on a fogged map the activation warm-up also compiles the fog variant of each listed permutation of the
map's larger programs (more than the 3 permutation bits Patch 1574 warms whole), and the fog-only permutation. The
warm list is shared by every map, so a permutation seen only on unfogged maps compiled mid-run on a fogged map's
first play (surf_null after P1574: vmt/vertexlit 0x128/0x328, vmt/refract 0x20, 10-16 ms each).
Root C:\FTESurf-worktrees\lows4-20261116-46.

Delivered 16 Nov 2026 03:46Z: engine main 216ed6bae (tag patch-1578, stamp git-8797-patch-1578-0-g216ed6bae), with P1575 and P1578 together. Both installs' client exe e004597b (predecessors ftesurf64/fteqw64 4fffcfb1 patch-1572 kept as .prev, archived in the task root's artifacts/delivery-p1575). Measured and reviewed: engine ENGINE_PATCHES.md Patch 1578.
