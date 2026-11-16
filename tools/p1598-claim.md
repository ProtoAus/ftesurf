# P1598 claim (ftesurf-29, 17 Nov 2026)

Lex: a small in-game UI for switching game mode -- `hud_gamemode`, the modes listed 1-7, click one or press its
number. The modes are P1589's movement profiles (default, hl2-pre, hl2-post, ag-100, ag-250, ag-1000, cs16);
none is ranked yet. sv_movementprofile is CVAR_NOTFROMSERVER and every QC localcmd runs insecure, so no QC can
set it: the engine gains `movementprofile <mode>`, which sets it and runs map_restart only on a server this
process hosts (refused when not hosting, and from insecure sources on a dedicated server). The csprogs panel
calls it; on a lobby it lists the modes inert ("only in a game you host").
Engine sv_phys.c; QC src/client/cl_gamemode.qc (+ cl_main.qc hooks, cl_progs.src). Root
C:\FTESurf-worktrees\gamemode-20261117-29.

## Delivery (17 Nov 2026, LIVE)

Engine main 7cc93e58e (tag patch-1598, stamp git-8842-patch-1598-0-g7cc93e58e, TLS check clean): both installs
client 424548fb, fteqwsv64 2d0fea30, hl2 fc1c9afc, ui_imgui dfbb11c2 (.prev = patch-1593). QC main 0c92a57e: lobbies
12/12 restarted (-Pi, 0 players) and both installs, qw 21ff074b / cs 83467981, menu f43460fe unchanged; tasrevd
codes.txt 154 -> 155 (.pre1598). pi_lobby_smoke on the released 0.1.48 exe: PASS. Final binaries: the local phase's
17 checks pass. Evidence and limits: engine ENGINE_PATCHES.md Patch 1598, BACKLOG "Movement mode picker".
