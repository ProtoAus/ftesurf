# P737 — mode2 cull-aware plane ordering

## Cause and narrow change

Owner confirms P736 fixes the original Kitsune saved angle; save2 is also good,
but turning right toward save3 exposes another ramp flip. The actual C sorter
with20 nearby source-map grid fans reproduces it: poses1/2 order successfully,
pose3 hits a constraint cycle and retains the angle-dependent centre baseline.

Proven GL-empty backfaces were still contributing constraints in mode2. Reuse
the existing default1 conservative static-world/single-pass raster-empty proof
before gathering mode2 records, selecting the real world entity first to clear
a preceding RF_XFLIP. In this scene8 empty draws disappear, leaving12 commands,
6 admitted planes and the same contributing-pane order at every saved angle.

Modes0/1/default1, budgets, plane proofs, P736 centres, gameplay and materials
are unchanged. Unknown/near-span/program/multipass/fog/two-sided/recursive/
nonstandard-view/dynamic/coarse/capture cases retain conservative handling.
No map-ID shortcut, triangle splitting, OIT, universal transparency or measured
performance claim. No new capture/reflection harness or gameplay process.

## Acting evidence

- Existing actual-dispatcher suite:4 normal/HEXEN2/fast-math Werror variants,
  all3 saved poses plus33 interpolated2-to3 angles,7 unsupported-context guards,
  mode0 full-range preservation and20 named acting mutants. Old/no mode2 cull
  and missing world-selection mutants fail the new four-pane rank assertion.
- Original P736 with the corrected fixture fails that rank assertion; new code
  passes. All20 original command labels remain in unsupported-context controls.
- Independent indexed-triangle ray sampling:1724/2280/2452 overlapping pane-pair
  samples at poses1/2/3;0 errors against2073,2086,2047,2071 far-to-near. The old
  pose3 fallback reverses2452 samples. This is geometry evidence, not GPU pixels.
- Existing plane-helper suite and its acting normal/fast-math mutants pass.
- Initial synthetic XFLIP setup omitted the matching renderer-state field;
  that inconsistent arm is excluded and retained. The first-triangle-only
  mutant now acts earlier at an existing draw-rank assertion; its exact expected
  failure was updated, not weakened to arbitrary crashes or tolerances.

## Exact native build and dual delivery

Clean engine/tag: `2aec8c6de262598abf4e836f133f6c35c7a0623b` / `patch-737`.
Both executables embed `git-7353-patch-737-0-g2aec8c6de`.
Pwsh7 src/build.ps1 -Engine -Full -NoDeploy -Jobs8, owned temporary directories,
borrowed native dependencies, explicit SVN_VERSION/SVNREVISION. All3 QC compiles
report0 warnings; progs were NOT shipped. Full native build matches all74 prior
compiler diagnostics and349 Make warnings,0 NEW. All20 fixed installed guards
and5890 cached dependency files remain unchanged during isolated building.

Dual native drop completed **2026-10-16T08:43:03.4040295Z**, with all10 destinations
held exclusively through backup/copy/hash verification and rehashed afterward:

- C:\FTESurf: ftesurf64.exe, hl2/ui_imgui plugins.
- C:\FTEQuake: client, dedicated server and hl2/cod/box3d/ode/ui_imgui plugins.
- Immediate predecessors remain `.prev`; before/subject and older-prev bytes
  remain independently retained under `delivery-p737/`. P736 history is preserved.
- No owner process stopped, config/save/player data or installed progs shipped,
  QC Build bump, NanoPi operation, public release or native ABI/header change.

| Product | SHA-256 |
| --- | --- |
| fteqw64.exe / ftesurf64.exe | 6694363b9fa69eb02c0e5ea4643b2dd71ac476d73935166d227ae18f1d765130 |
| fteqwsv64.exe | 24b76ea0ed15f45104dd8f6b81810684d93f1946249c1a1b5893f1e47b14083c |
| hl2 plugin | 23d7d6e56c342ef05f754b44ef115c63d1cb23f1520f60bedea20e9f04e31f81 |
| cod plugin | 42c5677502c286024d0a222f2fb7c32c4c160d14fc8caacb242e65d29720cede |
| box3d plugin | 6f00d43e975d478d0d089498b2b9d524a879f1df022c086d7fc45e8e58ad9449 |
| ode plugin | b0a598a80c2103f677e4c17a13066f1e56ccf987176cf67518510981b6f73c7e |
| ui_imgui plugin | a796046e41ed89a86bdbf2ec4e52bf683c573efa73bbda79ec5784b6be811d48 |

## Human gate and retention

**P737 live visual acceptance FAILED:** owner reports all3 exact saved angles
look correct, but moving between2/3 or farther right still switches surfaces.
The33 interpolated views are not a proof of arbitrary live mouse motion.

Read-only r_shaderpasses grid_orange reports flags0x8 (front cull), sort11,
passes1, shaderbits0x400065 (ordinary alpha blend/fullrate), no shader/pass
program: the material is not a custom-program/multipass exclusion. Static BSP
PVS reconstruction at the estimated eye resolves cluster132/area12 and the same
20 grid fans, rather than demonstrating a larger graph budget failure. A wider
2D pitch/yaw diagnostic does not reproduce the reported2-to3 failure in that
static model; far-right admission/rank transitions alone are NOT a GPU error
oracle. Runtime renderer/cache values, whether a bad angle stays wrong after
motion stops, and a stationary failing save4 remain requested. No new product
patch, rebuilt binary or deployment is claimed for this follow-up.

Track the unresolved live issue in BACKLOG.md. Preserve the current P737
native/rollback state until a real failing control is obtained; no new capture
harness, reference rig or screenshot campaign is required.

Retain clean sources, staged natives, rollback bytes and evidence pending that
check at `C:\FTESurf-worktrees\mapvisual-01a13061\ramp-centre\` (OWNER.md).
Only this task's disposable outputs may later retire; preserve unique ignored
evidence and unlink the borrowed dependency junction without following it.
Original screenshots/saves stay untouched and are not exported.
