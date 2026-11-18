# P1611 claim

- Owner: Claude Code session worldofsurf-c5 (for Lex), 2026-11-18.
- Work: Wayland fullscreen. F11 / Alt+Enter / vid_toggle switch fullscreen live (xdg_toplevel set/unset_fullscreen, no renderer restart);
  windowed honours vid_winmaximize (maximized); no client-side caption inside fullscreen; window title kept across restarts.
- Repos/files: ftequakers engine/gl/gl_vidwayland.c, engine/client/renderer.c, engine/client/vid.h, ENGINE_PATCHES.md;
  FTESurf ENGINE.txt, BACKLOG.md (Linux lows5 entry), lextest.md.
- Root: FTESurf-worktrees/wlfs-20261118-c5
