# Patch 1587 claim (ftesurf-46, 16 Nov 2026)

Lex 16 Nov: water's default is the transparent plane (hl2_water 0) and glass's default translucent without
refraction (hl2_refract 0); the dithered and higher modes stay in the graphics panel for players to choose. hl2
plugin defaults (mod_vbsp.c) and ftesurf/cfg/default.cfg + defaultuser.cfg. Root C:\FTESurf-worktrees\lows4-20261116-46.

Landed 16 Nov 2026: engine main 76823c993 (tag patch-1587): renderer.c's hl2_water / hl2_refract registrations (the
defaults players get; the plugin's GetNVFDG returns them) and the plugin's text; QC default.cfg/defaultuser.cfg and the
once-per-config move (cl_hudedit.qc, gated on the engine's help text). Verified by artifacts/p1587_arm.py: a config on
3 / 2 / r_video_rev 1402 prints both moves and reads 0 / 0 / 1587; on an engine without the patch it moves nothing.
Not installed: for the next release, as Lex asked.
Shipped in release 0.1.48 (16 Nov 09:02:44Z, ftesurf-06): installs exe af6a445c (patch-1588), csprogs cc032a87.
