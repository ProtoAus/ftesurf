# Patch 1594 claim (ftesurf-31, 17 Nov 2026)

Key timing below the journal: the client measures, for every key press and release, how long after the
keyboard's own raw report the game's key message arrived (buckets under 1 ms to 100 ms), and counts releases
no keyboard reported; the `.hid` carries the counts. Notes only. An in-process tool that delays or advances key
messages keeps their hardware origin (P1576) and changes no code bytes it must keep (P1586), but not this
timing. Engine in_win.c / in_generic.c, FTESurf tools/hidcheck.py. Root C:\FTESurf-worktrees\acguard-20261116-c5.
