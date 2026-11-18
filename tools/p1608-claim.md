# Patch 1608 claim (Claude Code worldofsurf-ed, 18 Nov 2026)

Two client hitches/costs every map shares (QC only): the board cache's file write (OBC_Save) ran mid-map 5 s after
each board landed and held that frame 3.1 ms (surf_andromeda, r_spikes 2) -- it now saves only at CSQC_Shutdown,
which already saved a dirty cache; and Milk_Supported, ~8% of csprogs' temp strings (three a call, several calls a
frame), re-reads vid_renderer at most once a second. src/client/cl_online.qc, src/milk_sys.qc.
Root FTESurf-worktrees/lows5-20261118-ed.

## Status (18 Nov 2026): merged -- FTESurf 02c240e8 (QC); engine record entry 5798ac79a. Not deployed: main's QC also
carries P1603, whose surfd goes first (tools/backend-pending.md); local installs get it with their next QC build.
Verified: no OBC_Save in r_spikes 2 (was 3.14 ms), the cache written at quit, Milk_Supported 0 of the census reports
(66 before), fteqcc 0 warnings. Record: engine ENGINE_PATCHES.md "Patch 1608".
