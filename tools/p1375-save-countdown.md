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

Installed and live artifact/readback verified 7 Nov 2026, 13:20:46 UTC.
Source 750e1323e09d780caf2f0b7717f5600f3ea03a30; engine journal
d5b6b0d4baab9c71a7313cb1a257f9905cfbf569. Both inspected SHAs pushed.
Clean-commit all-three-VM build: zero warnings. Production-entry rebuild matched
the frozen artifacts byte for byte.

Both Windows installs have exact QW/CS+LNO hashes. Owner menus, cfgs and native
binaries stayed unchanged. Pi used ordinary build.ps1 -Pi with its default
10-second warning/restart (2 players at preflight), no force. All 12 services are
active and in the directory, each advertising exact client folded-MD4 0xd8d404ca,
7509142 bytes. The .prev pair matches the actual immediate preflight.

- qwprogs.dat SHA256: d2f8190353fbdeeed168e6cda2e4dff30b13834b86608f24a47fcdd38dfacb43
- csprogs.dat SHA256: 9cf62ef135cc9a3fb6df2b1bc72df46e245a7862a05a575f464e0ee3491e0407

All 190 enumerated current recorder/resume payloads (258806700 bytes) were captured
off-box before restart and every archive member read back against its hash. Each
capture was bounded to its opened FD size: possibly live prefixes, NOT a claim that
all writers were closed or that this was a simultaneous full snapshot. Postflight
189 captured prefixes match; one original pathname is absent and its old inode was
not found under the gamedir data tree. That is not proof of loss: exact captured
preimage is retained; no automatic restoration, deletion or player-data rewrite.

Disk/live advertisement proof is not new client/pixel proof. Native remained
unlaunched at the safety boundary above; the tiny owner countdown/editor check is
pending. Prior lead-in approval is confirmed; new caption/readability approval is
not invented. No backend, recording/evidence semantics or release change.
