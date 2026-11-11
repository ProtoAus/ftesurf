# P1501 claim (ftesurf-18, Claude Code, 11 Nov 2026)

Static prop models load behind the loading screen: the hl2 plugin requests every static prop model when the map
loads (only solid ones were, for collision; the rest loaded in the first frame that drew them), and r_mapready waits
for every requested model, so their materials register before the shader warm-up and their programs compile there.
surf_fairy: ~120 prop shaders registered in the first rendered frame; 4 late compiles a play, 2 of them remembered
in the warm list but never warmed (program created after activation). Engine gl_shader.c, plugin mod_vbsp.c.
Root C:\FTESurf-worktrees\lows2-20261107-opus.

Delivered 11 Nov 09:04Z: engine tag patch-1501 = 1ecd63016 after one review (prop wait half the budget, ready-closure, renderer guard); both installs exe 32a64a94 + hl2 plugin 70b9810f. No QC or lobby change.
