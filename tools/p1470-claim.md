# P1470 claim (ftesurf-1d, 10 Nov 2026)

r_projection (stereographic, fisheye, panoramic, LAEA, equirectangular, panini) on the GL renderer: Lex reports it
"just produces errors". Read so far (gl_rmain.c R_RenderScene_Cubemap): the cube faces are allocated with
glCopyTexImage2D from the bound framebuffer, which is the vid_multisample target (Patch 1260) -- a multisampled read
is INVALID_OPERATION -- and vid.fbpwidth/height are left at the cube size for the final draw and post-processing.
Reproduce first (artifacts/probe_projection.py), then fix.
