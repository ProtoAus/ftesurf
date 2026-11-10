# P1482 claim (ftesurf-18, Claude Code, 11 Nov 2026)

r_spikes splits the "input, console" bucket (stdin pipe, window messages with the slowest one, INS_Move+IN_Commands,
console lines with the slowest one), then the fix for what it finds: 9-15 ms frames in that bucket on surf_tendies,
surf_fairy, surf_mesa_revo and surf_nuclear in the 11 Nov survey. Engine cl_main.c, cl_screen.c, sys_win.c, cmd.c.
Root C:\FTESurf-worktrees\lows2-20261107-opus.

DELIVERED 11 Nov 20:18Z (ftesurf-18) with P1481: the r_spikes split only -- the WM_PAINT handling it was meant to carry was measured ineffective and dropped. tools/p1481-survey3.md.
