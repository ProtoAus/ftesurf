# P1463 claim (ftesurf-1d, 10 Nov 2026)

r_blendsort 2's plane sort, pass 1: resolve a strict pair's overlap verdict only when Kahn needs it to decide a pick
(gl_backend.c GLBE_BlendPlaneSort). Same order while the overlap budget lasts. surf_fairy's worst views end in a cycle
after ~1010 pass-1 verdicts (~0.9 ms/view with P1457).
