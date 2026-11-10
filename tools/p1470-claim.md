# P1470 claim (ftesurf-1d, 10 Nov 2026)

r_projection (stereographic, fisheye, panoramic, LAEA, equirectangular, panini) on the GL renderer: Lex reports it
"just produces errors". Read so far (gl_rmain.c R_RenderScene_Cubemap): the cube faces are allocated with
glCopyTexImage2D from the bound framebuffer, which is the vid_multisample target (Patch 1260) -- a multisampled read
is INVALID_OPERATION -- and vid.fbpwidth/height are left at the cube size for the final draw and post-processing.
Reproduce first (artifacts/probe_projection.py), then fix.

INSTALLED 10 Nov: both installs run client exe 87c31448 (tag patch-1472 = 789a542da, engine main; ENGINE_PATCHES.md
Patch 1470). Smoke of that exe on surf_pantheon (vid_multisample 4): r_projection 1-6 and r_projection 1 at
r_renderscale 2 each drawn and filling the screen, 0 framebuffer/GL error lines in the client log, 298 fps after.
