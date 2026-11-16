# P1598 claim (ftesurf-29, 17 Nov 2026)

Lex: a small in-game UI for switching game mode -- `hud_gamemode`, the modes listed 1-7, click one or press its
number. The modes are P1589's movement profiles (default, hl2-pre, hl2-post, ag-100, ag-250, ag-1000, cs16);
none is ranked yet. sv_movementprofile is CVAR_NOTFROMSERVER and every QC localcmd runs insecure, so no QC can
set it: the engine gains `movementprofile <mode>`, which sets it and runs map_restart only on a server this
process hosts (refused when not hosting, and from insecure sources on a dedicated server). The csprogs panel
calls it; on a lobby it lists the modes inert ("only in a game you host").
Engine sv_phys.c; QC src/client/cl_gamemode.qc (+ cl_main.qc hooks, cl_progs.src). Root
C:\FTESurf-worktrees\gamemode-20261117-29.
