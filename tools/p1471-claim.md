# P1471 claim (ftesurf-1d, 10 Nov 2026)

Lex (10 Nov): "People don't play below 66fps ... we could just cap the fps to 66.6667>fps". While playing with the
Source mover, a cl_maxfps under the server's tick rate (1/pm_ticrate: 66.67 surf, 100 bhop) is raised to it -- below
it one usercmd covers two of pm_source.c's whole ticks with one input. Engine client cl_main.c (limiter) and sys_win.c
(present pacing reads the same cap). 0 (uncapped), menus, demos and the minimised throttle unchanged.
