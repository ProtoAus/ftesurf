# P1410: the window-focusing click presses nothing (8 Nov 2026, ftesurf-3a + helper)

Lex chose this after P1407: his ftesurf.cfg binds MOUSE1 +duck / MOUSE2 +jump, and clicking the
background game window to watch a surf_voyager flight ducked the player and lost the flight.

- Path (diagnostic build): WM_MOUSEACTIVATE eats the activating WM_LBUTTONDOWN and raw input never
  sees it (window not foreground yet); the next WM_MOUSEMOVE with MK_LBUTTON (jitter, or the grab's
  SetCursorPos) passed INS_MouseEvent's duplicate check as a fresh K_MOUSE1 press.
- Fix (engine client in_win.c, gl_vidnt.c, winquake.h): INS_MouseActivateClick marks the activating
  button(s) on WM_MOUSEACTIVATE (not in embedded mode); INS_MouseEvent holds that button at its old
  state until a message shows it released; the raw reader drops its unmatched up and clears the mark
  on any new down. DirectInput and embedded mode unchanged.
- Arm (message-driven, ABAB, artifacts/p1410round.py in the task root): activating click with a held
  move 1/1/1 unpatched vs 0/0/0 patched; next click 1/1; drag while focused 1/1 (not doubled); alt-tab
  then click 1/1. Lex ran artifacts/p1410real.py new/old on real hardware: "yes it works".
- Native: engine commits ce0955656 (fix), 5cf662a2c (merge P1409), 8d80046ee (notes), merged to main
  d5e960a2e; tag patch-1410 = 5cf662a2c. Exe a3bf7f83 (git-8549-patch-1409-2-g5cf662a2c) installed
  8 Nov as C:/FTESurf/ftesurf64.exe and C:/FTEQuake/fteqw64.exe (.prev = 684cf4a4, patch-1409).
  fteqwsv64 unchanged. Rides the next release.
- Seen on the way: C:/FTEQuake/ftesurf64.exe is a stale patch-1306 build (5 Nov); that install's
  client is fteqw64.exe.
