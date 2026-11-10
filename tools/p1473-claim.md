# P1473 claim (ftesurf-1d, 10 Nov 2026)

Lex (10 Nov) asked for a test of Reflex 2's frame warp. r_framewarp (default 0, a test setting): just before the
HUD, the drawn view is turned by the mouse movement that arrived while it was drawn -- rotation only, one projective
map (P * view * inverse(turned view) * inverse(P)), drawn as a grid of R2D quads. The mouse peek pumps only WM_INPUT
early and reads the input queue without draining it (P293's identity: m_filter 0, m_accel 0, cursor grabbed); the
angles sent to the server are unchanged. Touches the input path, so an evidence-lens review before any install.
Engine client gl_rmain.c, in_generic.c, in_win.c, renderer.c, render.h, client.h.
