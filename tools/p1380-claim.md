# P1380 claim -- ftesurf-b8, 8 Nov 2026 ~02:00Z

Lex's paste of 8 Nov: surf_centipedes' spawn sign (centipede/centipedesign, VTF flags POINTSAMPLE|NOMIP|
CLAMPS|CLAMPT) wraps at the brush edges, so slivers of the neighbouring tile's letters show beside the
title, and point sampling drops texel columns when it is drawn below native size. Engine image.c only
(client). Root C:\FTESurf-worktrees\lexbugs-20261108-b8.
