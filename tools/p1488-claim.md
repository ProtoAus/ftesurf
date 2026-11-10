# P1488 claim (ftesurf-18, Claude Code, 11 Nov 2026)

surf_fairy / surf_jumble (the two worst 0.1%-low maps of survey 3): their slowest frames are glare and sky-test
traces -- traceline 5-9.5 ms in a frame (66-98 rays at ~100 us on fairy; r_spikes 2 builtin attribution). Halving
vbsp_glare_traces and vbsp_sprite_skyrays on a quiet machine: fairy warm 0.1% 82 -> 110, stutters 840 -> 185.
Fix for every map: engine gettime(2) = seconds into the frame (0.1 ms steps); QC Sprite_Glare + Sprite_SkyTick share
one per-frame trace time budget (vbsp_sprite_tracems), leftovers carried, old engines uncapped. Revives P1456's
reviewed cap (origin/p1456-glarefade) with a usable clock. Engine pr_bgcmd.c; QC cl_sprites.qc, cl_main.qc.
Root C:\FTESurf-worktrees\lows2-20261107-opus.
