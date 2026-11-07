# P1375 -- save-load countdown and one millisecond editor

## Requested and implemented

Lex approved the observed lead-in on 7 Nov (recorded as human acceptance in
lextest.md), then requested a small center countdown and flagged duplicate editor
options. The two old rows were presets and typed entry for the SAME cl_sl_leadin.

- Draw a small centered label just below the crosshair during save lead-in,
  independently of whether the Save Lock menu is open.
- Milliseconds use the later of the existing minimum-hold deadline and active
  visual travel deadline. Round upward; do not show ready before either ends.
- An unanswered load or pending travel start says Loading save, not a fabricated
  network ETA. Once ready, an unreleased key says Release to play. Tapped loads
  retain their existing automatic release path.
- Keep ONE numeric Lead-in control in hud_edit -> Save & load: 0..2000 ms.
  It still writes the existing seconds-valued cvar through its existing 1000 scale.
  Defaults and saved preferences are not changed.

This is read-only client presentation. The four existing hold/release/state
functions are byte-identical, as are all server, movement, recorder and evidence
source files. No native pin/tag, QC Build, backend or old-save migration.

## Validation

All three VMs built with zero warnings. Source falsifier: published old pane has
2 rows for the cvar, new pane has exactly 1 contiguous numeric row. The caption is
drawn before the save-menu visibility return. Four hold/release functions unchanged.
Twelve presentation-model cases cover disabled/idle/spectating, unknown answer/start,
minimum hold, longer travel, held-ready, tapped-ready and upper duration bound.
These are SOURCE/MODEL checks, not QC runtime or pixel evidence. LSP is not a QC parser.

Native launch was NOT attempted: actual 13:12:24 UTC boundary had 1876 MiB free,
below the unchanged 4096 MiB gate. For this cosmetic change a tiny owner check is
preferred over more test machinery: one tap-load, one held-ready look and one editor
look. New countdown/readability acceptance remains pending; prior approval was for
the existing lead-in, not these new pixels or every original clock/TAS case.

## Delivery

Pending clean-commit build and ordinary exact-artifact dual Windows/Pi deployment.
Menus, native binaries and owner configs are not targets. No release requested.
