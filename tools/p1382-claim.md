# P1382 claim -- ftesurf-b8, 8 Nov 2026 ~02:05Z

Lex's paste of 8 Nov: players see pink/black textures (Markbeaton on surf_fortum: his HL2/CS:S are on
another drive) and the console tells them the map "references content that was never shipped" even when
the real cause is an fs_addons.txt game that was not found. Engine fs.c publishes the fs_addons games it
could not mount (fs_addons_missing); the hl2 plugin's advice and csprogs' banner name them; csprogs sends
an automatic missing-material report to the lobby (sv side stores it under data/matreport/).
Root C:\FTESurf-worktrees\lexbugs-20261108-b8.
