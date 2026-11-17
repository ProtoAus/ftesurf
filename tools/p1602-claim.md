# P1602 claim -- lex-90 (Claude Code), 2026-11-17

Lex (his first Linux desktop, labwc, DP-1 2560x1600 at scale 1.25, DP-2 1920x1200): scaling support, the game should
"just work" on Linux. Native Wayland by default on a Wayland session (`vid_renderer gl` resolves by priority), HiDPI
through wp_fractional_scale/wp_viewporter, server-side decorations, key repeat, clipboard, tearing control, frame
callbacks that never stall the host. Lex chose Wayland by default over the P386 GLX preference (17 Nov).

Files: engine gl/gl_vidwayland.c, gl/gl_vidlinuxglx.c, gl/gl_videgl.c/.h, client/renderer.c; FTESurf
ftesurf/cfg/default.cfg (comment). Docs: engine ENGINE_PATCHES.md, ENGINE.txt, PATCHNOTES.md. Claimed to lex-72,
chatbot3-1d, media-00. Root: ~/Projects/WorldofSurf/FTESurf-worktrees/linux-20261117-90.

## Delivery (17 Nov 2026)
Engine main 1847a5b71 (tag patch-1602), three review rounds; record in ENGINE_PATCHES.md. Not yet in a release; the
owner's Linux play copy runs a build of it. Human checks pending (lextest.md): key repeat, Ctrl+V, cursor, title bar,
smoothness at 300/360 Hz.
