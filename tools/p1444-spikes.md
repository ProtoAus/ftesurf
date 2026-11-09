# P1444 -- r_spikes: what the slowest frames spent their time on

Lex, 9 Nov: "is it possible to somehow check or test what exactly what task is causing the most CPU time? ... see if
we can reduce it to get a more stable 0.1% lows?" -- he suspected the 66/100 tick and the water recaptures.

**Engine** (ftequakers main 18f0514b4, tag patch-1444; ENGINE_PATCHES.md "Patch 1444"): `r_spikes 1` times the
engine's buckets and keeps the 8 slowest frames since `r_frametime_reset`, each with its own CPU ms per r_budget
group, its largest bucket, late shader compiles / image uploads, packets read and nested views;
`r_frametime_dump` prints them under the average frame. Off by default.

**Use:** `r_frametime 1; r_spikes 1; r_frametime_reset`, play, `r_frametime_dump` (also copies to the clipboard).

## Findings so far (the PC, i9-9900K / RTX 2080 SUPER; Lex's settings; warm session; uncapped)

- Water (artifacts/run_cvarab.py, 30 s per arm, one session): r_capturerate 60 beats capturing every frame on
  every number (bhop_ceaseless avg 600-607 vs 498, 0.1% 181-197 vs 149; surf_kitsune 0.1% 196-224 vs 175).
  hl2_water 0 lifts ceaseless's 1% low (271-280 -> 325) but not its 0.1% (196); on kitsune it is within noise.
- cl_debug_spikes (artifacts/run_spikelog.py, frames over 5 ms): nuclear 4 of 5 slow frames in the render, 1 a
  5.8 ms packet parse; pantheon 39 of 39 in the render. The tick itself runs on the lobby server, not the PC.
- r_spikes on surf_nuclear, two runs: the largest are pairs of frames at the same two places on the route (around
  -6900 -5640 -3440, and -13400..-14300 800-1000 -7200..-9380 looking down) -- "prediction" 5.5-7.7 ms then
  "QC UpdateView, HUD" 5.2-8.3 ms against an average CSQC of 0.7 ms. r_budget files "prediction" under CSQC, but
  it is ENGINE code: CL_SetSolidEntities + CL_TransitionEntities + CL_PredictMove (pr_csqc.c ~9515, whose comment
  suspects PredictMove tracing every trimesh prop with no broadphase); frames with 2 nested water views 4-6 ms in
  PrepareFrame + opaque draws; one 49.8 ms and one 8.7 ms swap/present stall; one 5.0 ms "network" frame with no
  packet counted. Packets 0-1 in every listed frame.
- surf_pantheon: draw calls 2-3.4 ms plus CSQC 1.4-2.7 ms in its slowest frames -- heavy views, no single cause.

## Next

What arrives at nuclear's two places -- an entity flood as the PVS opens would explain a network/prediction frame
followed by a QC UpdateView frame (next: count entities per spike); the swap stalls (driver/compositor -- once each run, the rig window sits behind others); water frames'
PrepareFrame cost.
