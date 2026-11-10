# P1465 claim (ftesurf-1d, 10 Nov 2026)

r_blendsort 2 on surf_fairy, after P1457/P1463: the views whose sort ends in a cycle still spend ~0.67 ms/view
(main view and the water refraction capture). Timing split first (trace-only build), then the fix. Lead: faces wholly
outside the clip volume (off-screen, or past a capture's oblique water plane) draw nothing but still join the plane
graph, and its cost is quadratic in the faces admitted. gl_backend.c GLBE_SubmitBlendedFaces / GLBE_BlendPlaneSort.
