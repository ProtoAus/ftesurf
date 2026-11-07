# P1383 claim -- ftesurf-b8, 8 Nov 2026 ~02:15Z

Lex's paste of 8 Nov: Shift+wheel noclip speed prints but does nothing on a lobby (BACKLOG "Lobby
wheel": Noclip_Wheel writes the server-owned pm_noclipspeed, which only a private/listen game shares).
Engine sv_user.c: a player's userinfo `ncspeed` (0.25..16) is that player's noclip speed, and the
server tells only that client its pm_noclipspeed (svc_serverinfo) so released clients predict it;
cl_main.qc Noclip_Wheel sets the userinfo. Root C:\FTESurf-worktrees\lexbugs-20261108-b8.
