# Patch 1608 claim (Claude Code worldofsurf-ed, 18 Nov 2026)

Two client hitches/costs every map shares (QC only): the board cache's file write (OBC_Save) ran mid-map 5 s after
each board landed and held that frame 3.1 ms (surf_andromeda, r_spikes 2) -- it now saves only at CSQC_Shutdown,
which already saved a dirty cache; and Milk_Supported, ~8% of csprogs' temp strings (three a call, several calls a
frame), re-reads vid_renderer at most once a second. src/client/cl_online.qc, src/milk_sys.qc.
Root FTESurf-worktrees/lows5-20261118-ed.

## Status (18 Nov 2026): claimed, in progress.
