# P1392 -- Keyboard tab in the key configuration panel

Owner: ftesurf-3a (Claude Code session 5e4b2e2d), 8 Nov 2026. Root C:/FTESurf-worktrees/report-20261108.

## Ask (Lex)

A second tab in the keybind menu working like the reference tool (C:/FTESurf-private/keymenu.png): the
keyboard, the bind list, and placing a bind on the keyboard.

## Change (src/client/cl_keycfg.qc)

- Tabs Actions (unchanged) and Keyboard; `cl_keycfg_tab` (archived); `config_menu actions|keyboard`.
- Keyboard: the 27 actions grouped with their keys; "Keys for <action>"; a "Selected key" box (name,
  engine name, full bind); a drawn ANSI keyboard + nav cluster + numpad + Mouse 1-5 and the wheel (111
  caps, engine key names, ESCAPE not ESC); each cap shows its bind (the action's short label, or the
  raw command shortened: scores, console, menu, journal, chat...). Picked action's keys in the accent,
  other binds on chips, unbound dark. "Bound, but not on this keyboard" lists other bound keys.
- Clicking a key with an action picked binds it (KC_Assign: taken from its row, "(was X)"); right-click
  clears it (bound ""). Clicks need the release over the key. Esc, the console key and the menu key are
  kept. A right Shift/Ctrl/Alt/Win with no bind runs the left key's (keys.c): shown "(as left)", and
  clearing one says it now follows the left key. Right-side modifiers (negative QC key numbers) can be
  bound from both tabs now.
- The 510-key scan and text fitting rebuild only when a crc16 signature of the binds changes.
- `config_menu place <id> <key>`, `clearkey <key>`, `layout [caps]` for arms; console changes with the
  panel closed save at once.

## Verified

- Builds 0 warnings x3. tools/p1392keys.py (hosted surf_dune): 111 caps, none missing; place jump on
  MOUSE4 and HOME binds +jump (bindlist), clearkey takes both back; screenshots of both tabs looked at.
- Review (binding semantics): drag-off clicks, picked action surviving close, right-modifier clear
  reporting, kept keys, rescan cost, closed-panel saves -- all fixed.
