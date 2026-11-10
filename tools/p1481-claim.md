# P1481 claim (ftesurf-18, Claude Code, 11 Nov 2026)

The CSQC/menu/SSQC tempstring collector's start copies only the QC memory pages written since its last start
(Windows write watch on the VM hunk, a mirror kept page for page) instead of the whole hunk -- 7-25 MB a collection on
the main thread, 1-6 ms spikes on every map in Lex's 0.1%-low survey (11 Nov). `pr_gc_writewatch` 0/1/2 (2 verifies
the mirror against the hunk). Engine qclib initlib.c/progsint.h/progslib.h + pr_bgcmd.c and the three VM setups.
Root C:\FTESurf-worktrees\lows2-20261107-opus.
