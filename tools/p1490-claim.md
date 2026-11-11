# P1490 claim (ftesurf-18, Claude Code, 11 Nov 2026)

r_blendsort 2 remembers a failure no certificate can keep (P1465 keeps only strict-edge proofs; at surf_fairy's
worst spot pass 1 crosses a barrier through an unproved pair, so the ~34k-work sort re-ran and failed every frame
in two views). The failure's pass-2 cycle is kept; while it re-proves, the view keeps the unsorted order and sorts
again every r_blendsort_retry (4) frames; a success with the cycle present forgets it. Paused fairy spot: transparent
1.21 -> 0.70 ms (Lex's settings 1.14 -> 0.62). Engine gl_backend.c, renderer.c, render.h.
Root C:\FTESurf-worktrees\lows2-20261107-opus.
