# P1163 — soft inventory ice aura

## Player-visible correction

The owner confirmed P1160's right-hand 4x4 inventory and item toggles work,
but reported its aura as a hard line stroke instead of a fade from the player.
P1163 changes only that cosmetic rendering and its label (Ice aura).

A depth-tested, backface-only shader expands the animated body's normals.
Sixteen shells integrate decreasing squared-falloff weights across an eight-unit
radius: bright near the body, faint outside. The opaque body and independent
paper-hat selection remain. This is a bounded mesh-shell approximation, not the
supplied depth-capture/JFA screen-space effect; no pixel-width-invariance,
through-wall, numerical performance or final owner-appearance claim is made.

## Source and checks

- Actual clean fleet source: `471fa957846350f1c52770d158eb9027bf27eda1`, based on
  the already deployed P1160 `84a8ff1a`. Other pending main-branch work was not
  released. Native source/pin/tag, qcbuild, backend schema and grants unchanged.
- Built using `src/build.ps1 -Jobs 8 -NoDeploy`, then from the inspected committed
  tree with `src/build.ps1 -Jobs 8 -Pi -PiForce`. Both use pwsh7. No new compiler
  warnings; two existing client F333 argument227 warnings remain.
- Retained real dedicated-socket fixture: actual OFF/ON inventory snapshots,
  item ownership/equipment acknowledged, shader compiled, screenshots inspected.
  The first single-shell view-angle approach compiled but still looked like
  flat strokes on the low-poly player; that is retained failed visual evidence.
  The sixteen-shell subject shows a soft cyan falloff and the selected hat.
- The pass retains ordinary scene depth testing. Fully hidden other-avatar
  appearance and ordinary playing smoothness still need the small owner check
  in `lextest.md`; a preview is not evidence of wall occlusion.

## Delivery / rollback

Destination readback **2026-11-01T00:57:55Z**:

| Program | SHA256 |
| --- | --- |
| csprogs.dat | `39518177ac12597f133f5b5547c16e68a6d73b850a8cca6700d6a572bfd6712b` |
| qwprogs.dat (unchanged) | `051557d568fce88a252ad1f960598990c6d90570b8160cfe4ddf4c526fa503db` |
| menu.dat (unchanged) | `6c9f9034ea348ead9874e5224b144751d39fd03d56bebca1d595aafe7bf2d938` |

Both Windows installs have matching three DATs/LNOs and verified immediate
preimages in `.prev`. Their native executables and owner configurations are
unchanged. The content-addressed client cache is seeded at folded MD4
`6356fae7`. The isolated build deploys its own source gamedir plus QuakeDir:
`C:\FTEQuake` was deployed by the entrypoint; only the missing canonical
`C:\FTESurf` copy was completed from those same verified artifacts, preserving
and checking all six `.prev` preimages. No repeat build or extra lobby restart
was used to repair that caller target assumption.

The NanoPi has the exact two DATs and matching `.prev`; the Pi ship set has no
LNO requirement. All 12 units are active, all 12 directory rows fresh, all 12
UDP status sockets reply. Empty-lobby replies did not advertise a CSQC checksum,
so those replies are liveness evidence, not checksum proof. Destination hashes
and the acting native capture provide the separate artifact/render evidence.
The entrypoint used PiForce, with zero players at its actual boundary. Backend
schema25 primary remains OPEN and compatibility remains CLOSED.

Old CSQC rollback: `cba6fdc6359bf8bf0a6ab381636e1d85cc43b9262ecd9a4661487c2f5b9ffdd9`.
No inventory data restore is needed for a client cosmetic rollback.

## Owner acceptance

P1160 grid placement and item toggles: confirmed manually. P1163 softer aura:
deployed for owner confirmation; not yet confirmed. A screenshot/native shader
pass does not replace the owner's requested look. Reconnect before judging it
so the client loads the new CSQC.
