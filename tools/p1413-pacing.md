# P1413 -- sys_framepacing 5, predictive present pacing (8 Nov 2026)

Lex, 8 Nov: "at 100fps the 0.1% lows were at like 80fps ... given the game has 10ms to draw the frame, it
should be perfect no?" Root C:\FTESurf-worktrees\lows2-20261107-opus (artifacts/run_pacing.py, pacing-*.out).

- Cause (BACKLOG "Frame pacing under an fps cap"): frames start on the grid and present when done, so render-time
  variance (water capture frames at r_capturerate 60) reaches the present cadence. Every player ran mode 1:
  cfg/default.cfg sets `sys_framepacing 1` at each boot (the cvar is not archived; the engine default 2 never
  applied). On GL modes 1 and 2 are the same.
- Change (engine sys_win.c, cl_main.c, gl_screen.c, cl_screen.c): mode 5 starts each frame its predicted render
  time (sys_framepacing_quantile of the last 64, default the slowest, +0.5 ms) before its slot and holds the swap
  to that slot; a late frame presents at once. Mode 2 behaviour off-GL, uncapped, minimised, timedemo, cl_netfps 0,
  vid_vsync on, or while the swap blocks (median of 32 > 1 ms). default.cfg/defaultuser.cfg now set 5.
  r_frametime samples right after the swap on Windows GL (HUD-timed it reads a held swap as jitter).
- bhop_ceaseless save 35, cap 100, present p99 / p99.9 (ms):

  | arm (30 s)            | p99         | p99.9       | frames start before present |
  |-----------------------|-------------|-------------|-----------------------------|
  | mode 5                | 10.11-10.23 | 11.49-12.88 | ~3.2 ms                      |
  | mode 2 (= 1 on GL)    | 11.00-11.23 | 12.18-12.34 | render time (~3)             |
  | mode 4                | 10.21       | 10.66       | ~10 ms                       |
  | full build, 12 s: 5/1 | 10.38/12.67 | 10.94/13.74 |                              |

  Cap 300: p99 4.32 -> 3.50. Cap 1000 unreached: 529 vs 530 fps. vid_vsync 1: mode 5 stood aside (11.03/12.15).
  Through a reconnect it kept pacing.
- Not demonstrated: the swap-blocking test. Windowed on this PC, vid_vsync 1 did not block the swap (p50 0.25 ms),
  so driver-forced vsync in exclusive fullscreen is untested; vid_vsync on is handled by the cvar. A sim of a
  blocking vsync swap (cap 60 on 59.94 Hz) showed the first cut's slot rule dropping 25 frames in a row to 30 fps.
- Left: the 0.1% -- about 3 frames per 30 s whose render ran 6-9 ms against ~3. Pacing hides them only by
  starting every frame earlier (mode 4, ~7 ms more input age at cap 100). Unprofiled.
- Reviews: round 1 (vsync runs, capped timedemo, loading busy-wait, off-GL anchor), round 2 (r_frametime's clock
  switching mid-hitch, a stale start after minimise) fixed. The first cut froze the client: with no present yet,
  the planned slot moved with the clock.
- Installed 8 Nov: both installs exe 824d41cc / fteqwsv64 0e2d9f5c (git-8558-patch-1413-0-g30faf8780,
  artifacts/delivery-p1413); engine main 30faf8780, tag patch-1413 (includes P1410).
