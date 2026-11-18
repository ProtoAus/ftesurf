# Patch 1607 claim (Claude Code worldofsurf-ed, 18 Nov 2026)

Linux frame pacing: `sys_framepacing` (Patch 1413's predictive present pacing, default 5) exists only in sys_win.c, so
on Linux a capped game (Lex: cl_maxfps 300) paces frame STARTS and every bit of render-time variance reaches the
present and the frame-time graph -- surf_andromeda at Lex's settings: p50 3.33, p99.9 4.4-4.5, max 5.7 ms while every
view along the route costs 1.1-1.7 ms. Port the modes to Linux (clock_nanosleep + spin wait, the swap hold in
gl_screen.c, r_frametime sampled at the swap). Engine client/sys_linux.c, cl_main.c, cl_screen.c, gl/gl_screen.c.
Root FTESurf-worktrees/lows5-20261118-ed.

## Status (18 Nov 2026): claimed, in progress.
