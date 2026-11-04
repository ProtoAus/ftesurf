# P1283 claim

ftesurf-ac, 20261104, from P1280 (Lex 4 Nov: CS:GO hands frame-rate dips) and 2b's P1277 voyager item (handed over 4 Nov):
a model light sample on a Source map traces to every world light in PVS/range (VBSP_AddWorldLightCube ->
VBSP_WorldLightVisible -> BIH). At two spots on bhop_ceaseless one sample traces 1248-1516 lights (~10 ms); movers
on surf_voyager 8-13 ms. Plan: cache per-light occlusion in the hl2 plugin so a moving model does not re-trace them all.
Files: plugins/hl2/mod_vbsp.c (engine repo); ENGINE_PATCHES.md; BACKLOG.md (P1277 mover-lighting line).
State: live: both installs (exe 23ec25b6, plugin d8b18216); tag patch-1283, engine main 571c7e23a.
