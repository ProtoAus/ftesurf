# P1472 claim (ftesurf-1d, 10 Nov 2026)

Lex (10 Nov): "People don't play below 66fps ... we could just cap the fps to 66.6667>fps". While playing with the
Source mover, a cl_maxfps under the server's tick rate (1/pm_ticrate: 66.67 surf, 100 bhop) is raised to it -- below
it one usercmd covers two of pm_source.c's whole ticks with one input. Engine client cl_main.c (limiter) and sys_win.c
(present pacing reads the same cap). 0 (uncapped), menus, demos and the minimised throttle unchanged.
(First pushed as p1471-claim.md over another session's P1471 claim by mistake; that file is restored byte for byte.)

INSTALLED 10 Nov: both installs run client exe 87c31448 (tag patch-1472 = 789a542da, engine main; ENGINE_PATCHES.md
Patch 1472). Smoke of that exe on surf_pantheon: cl_maxfps 30 -> 15.28 ms frames (65 fps by r_budget), cl_maxfps 100
-> 10.01 ms, back to 300 -> 3.36 ms.
