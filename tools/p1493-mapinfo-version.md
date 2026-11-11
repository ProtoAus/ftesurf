# P1493 — local game version next to World of Surf

## Problem / change

The map-info heading lacked the player's version. Downloaded lobby CSQC is shared
by different client releases, so its compiled version would be misleading.
Append local ui_release_version, already stamped by release.ps1. If absent,
MU_Init publishes the actual local compiled menu version in non-archived
ui_menu_version, adding (dev) for a development menu. If neither exists, show
unknown. Measure/draw the same complete right-aligned title.

No native code/pin/tag, QC Build, server channel, or integrity/security decision.
This is ordinary editable local display metadata, like the update menu.

## Verification

- Qualified retained compiler SHA256
  73f9a1a471d603a8d0ee5a83432229ba2dd10affbf358ba41d345c8c15af68c4.
- Supported src/build.ps1 -NoDeploy -Jobs8: all3VMs zero warnings, including
  final strcmp empty checks and combined published P1489 world-loader updates.
  Actual combined artifacts: qc/rig/build-nodeploy-c739132251674cd6936bc54dba2b1c2b
  under C:/FTESurf-worktrees/playerfix-20261110-01a1c798.
- Native MENU-only metadata control/subject: predecessor lacks ui_menu_version;
  subject supplies0.1.44(dev); explicit local release fixture0.1.42 remains
  unchanged in both. Both logs reach completion. Existing runlines wrapper
  additionally requires CSQC loaded and therefore refused these menu-only arms.
  Preserve that refusal: this is acting MENU producer proof, not a full CSQC
  harness/framebuffer pass. No harness repair/expansion was needed.
- Independent source review: no issues. Actual rendered alignment remains a
  small owner check in lextest.md; peer performance clients held graphics use.
- Current source base includes published backend P1491. Its changes do not alter
  compiled src/VERSION inputs; verify those against the combined build commit
  before reusing that build evidence rather than rerunning unchanged tests.

Initial local work/probe labels used1490 before a concurrent renderer claim was
published. That number was ceded; unpublished source/history was preserved under
owned superseded refs, never pushed or rewritten after publication.1493 is the
single final HUD patch. Earlier probe labels are historical, not extra patches.
The corrected P1487 compiler-hash transcription and numbered replay patch-note
heading preserve evidence/format accuracy; they do not change deployed bytes.

## Delivery

Source verification complete; actual install/fleet hashes and UTC remain to be
recorded after promotion. No release published. The multi-bug task continues.
