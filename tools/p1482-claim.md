# P1482 claim (ftesurf-18, Claude Code, 11 Nov 2026)

r_spikes splits the "input, console" bucket (stdin pipe, window messages with the slowest one, INS_Move+IN_Commands,
console lines with the slowest one), then the fix for what it finds: 9-15 ms frames in that bucket on surf_tendies,
surf_fairy, surf_mesa_revo and surf_nuclear in the 11 Nov survey. Engine cl_main.c, cl_screen.c, sys_win.c, cmd.c.
Root C:\FTESurf-worktrees\lows2-20261107-opus.
