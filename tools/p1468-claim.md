# P1468 claim (ftesurf-1d, 10 Nov 2026)

hl2 plugin world walk (mod_vbsp.c VBSP_RecursiveWorldNode and the unvised/displacement emits): the per-view surface
marks and the leaf/node surface loops read compact per-surface arrays instead of msurface_t's visframe/flags (two
cache lines of a ~200-byte struct per touch). Same surfaces, same order. Sampled: the walk's own time is 6.7% of a
surf_pantheon frame, 3.4% centi. Plugin + exe; cvar A/B before claiming a number.

PARKED 10 Nov, measured: no gain. surf_pantheon paused views, same plugin, hl2_walkarrays 0/1/0: the r_budget
PrepareFrame row (which holds the walk) read 0.39/0.41/0.39 ms at t=5 and 0.25/0.22/0.22 at t=20; draws and batches
equal. The sampled 6.7% was not cache misses on msurface_t (a view's surfaces stay cached frame to frame). Code kept on
origin branch p1468-walkarrays (reviewed: equivalent), not merged.
