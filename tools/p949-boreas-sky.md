# P949 — Boreas foreground-mountain sky cut

## Problem, prediction and bounded repair

The owner's Boreas Save11 PNG has a large sky-colored cut through the foreground
mountain. The historical P265 engine branch correction is already present in
native945; today's forced depth2 can still recreate the finite sky-brush mask.
Do not call this a new trigger, material or displacement fix.

Prediction registered before native testing: at a read-only Save11-derived pose,
2 cuts the mountain,1 restores it,2 cuts it again. A new map-local auto1 override
must then apply without a manual sky-depth1 command, and another map must read2.
Native server sky permission stays authoritative. No global depth relaxation.

Change: only cfg/maps/render_surf_boreas.cfg selects existing native auto1.
P948's already-delivered map-ready CSQC layer applies it; render_default restores2
elsewhere. No native/source VM logic, physics, recorder/reader, evidence schema,
body observer, command/channel, input API or player-data change.

## Verified

- Source versions: native9e73/patch945; existing P948 QWd2d507cc, CSQC67b40bdd,
  retained MENU5429. Actual Momentum BSP provider is observed in the native log.
- Original local Save11 was read ONLY for the requested pose/map binding. A new
  minimal DEMOTED fixture uses that pose and zero velocity through the existing
  isolated --put/saveloc interface. No original file, recording, identity, clock,
  split or timestamp is copied/edited. No pose/private data is committed here.
- Current native2/1/2 readbacks and three inspected screenshots show cut/full/cut
  at the same controlled scene. The body pose is observed with existing viewpos.
  This is a rendering control, not a prediction/physics or ranked-run claim.
- Corrected automatic test starts2 before map load; actual Boreas layer log,
  readback1 and inspected full-mountain PNG prove it acted. Mounted Autumnal
  then loads and reads2, proving no Boreas override leakage.
- A fresh OWNED native sl_save also writes its actual world CRC; it matches the
  requested map binding positively, not just absence of a mismatch message.
- Three VMs compile with zero warnings. Before the concurrent release merge all
  three equalled P948. Clean merged source preserves released0.1.30: QW/CSQC
  remain byte-identical; MENU differs ONLY by the two literal version bytes
  0.1.29->0.1.30 (same size, exact normalized comparison), not this config change.
  No program/native/backend promotion or Pi restart is needed; retain the current
  installed menu. No release/qcbuild decision is made by this task.

## Retained harness failures, not feature passes

The first matrix generated valid native PNGs/readbacks, but its wrapper returned1:
qconsole versus expected runlines_smoke log, wrong completion marker and unknown
scr_menus/sl_status aliases. Actual artifacts are retained; no wrapper pass is
invented. The next automatic arm did apply1/restore2 and produced matching native
CRC, but issued vbsp_skyroom BEFORE CSQC registered it, so it too is a wrapper
failure. Moving that existing cvar after map load fixes the same CFG seam.
Final existing runlines_smoke invocation returns0, no command/VM errors, actual
1/full then2, native CRC equality; all owned actors stop/wait and links retire.
No replacement wrapper chain, public/private player fixture or weakened check.

## Delivered; manual acceptance remains pending

Concurrent published release0.1.30/history, tooling and the owner's unrelated
Source-polish acceptance are preserved; P949 stays under next, NOT retrospectively
inside that published release. Final source d9050d841cde6b163bcfa4885e900a9220dec4fc
is clean/inspected/published; clean merged three-VM build0warnings qualifies the
unchanged QW/CSQC and two-byte release-version-only menu difference separately.
The final documentation-only amendment changes no compiled/config input.

BOTH Windows config targets independently hash-verified23Oct14:42:18.092Z:
`3a5016c7b23f7422445e4cd628d91f077c343a8b3940a324085cf437d3216c40`.
Exact bytes equal the native automatic-test file.36protected native/program/menu/
owner-config files unchanged; only the two new render_surf_boreas.cfg files were
promoted atomically. No BSP/mount/player-data edit or game process killed.
Existing Pi-served67b40bdd is sufficient: NO programs/native/backend deployment,
cache cleanup, Pi swap/restart, release or qcbuild action. Other clients need the
updated client config too; this is development delivery, not a new release.

Use the next Boreas load or fresh client launch, not a manual console workaround.
Owner in-game Save11 confirmation is pending in lextest.md. The native saved-pose
result does not invent that confirmation or acceptance of other graphics settings,
alternate BSP builds, Phantasia's textures or Epiphany's black scene. Needed
synthetic logs/images/source remain private under the owned task root.
