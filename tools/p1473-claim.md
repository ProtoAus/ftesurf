# P1473 claim (ftesurf-1d, 10 Nov 2026)

Lex (10 Nov) asked for a test of Reflex 2's frame warp. r_framewarp (default 0, a test setting): just before the
HUD, the drawn view is turned by the mouse movement that arrived while it was drawn -- rotation only, one projective
map (P * view * inverse(turned view) * inverse(P)), drawn as a grid of R2D quads. The mouse peek pumps only WM_INPUT
early and reads the input queue without draining it (P293's identity: m_filter 0, m_accel 0, cursor grabbed); the
angles sent to the server are unchanged. Touches the input path, so an evidence-lens review before any install.
Engine client gl_rmain.c, in_generic.c, in_win.c, renderer.c, render.h, client.h.

PARKED 10 Nov, not shipped (branch p1473-framewarp). The warp math is right once it reads m_projection_noclip, but the
fresh input is the problem: there is no way to see queued raw mouse input without consuming it, and pumping WM_INPUT
early splits each raw report from its legacy twin across the rest of the frame. Evidence review: P1424's 100 ms key
pairing and P307's button pairing compare HANDLING times, so a >100 ms frame after the warp logs an honest key as
injected ('y') and can turn a raw button-up into a phantom K_MOUSE1 press ('b'); with cl_threadedphysics the journal's
clock goes backwards. Prerequisite for any late-input feature: pair raw and legacy input by message arrival time
(GetMessageTime), an evidence change with its own review. Also open on the branch: matrix (2D ortho at warp time),
static shader/FBO across vid_restart, views the mouse does not drive (spectate, save hold, rewind, TAS lock).
