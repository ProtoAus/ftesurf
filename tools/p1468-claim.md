# P1468 claim (ftesurf-1d, 10 Nov 2026)

hl2 plugin world walk (mod_vbsp.c VBSP_RecursiveWorldNode and the unvised/displacement emits): the per-view surface
marks and the leaf/node surface loops read compact per-surface arrays instead of msurface_t's visframe/flags (two
cache lines of a ~200-byte struct per touch). Same surfaces, same order. Sampled: the walk's own time is 6.7% of a
surf_pantheon frame, 3.4% centi. Plugin + exe; cvar A/B before claiming a number.
