# P1588 claim -- ftesurf-06, 16 Nov 2026

Local games (a listen server: `map ...`) run no warp-op pre-move hook and no predicted hold (Patch 862 left
both gated), so every save load there waits on the server: "Loading save" flashes each load and sv_minping
freezes the body. Engine (pr_csqc.c, cl_pred.c): open both on a listen server behind a cvar; QC: the
"Loading save" text waits before it shows. Root C:\FTESurf-worktrees\localload-20261116-06.
