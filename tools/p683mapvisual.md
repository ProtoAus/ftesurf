# P683: Source map material and brush compositing

## Scope and root causes

- Kitsune's authored `renderamt 0` must not become native alpha zero (native zero
  means opaque). Keep opacity and EF_NODRAW separate from Enable/Disable.
- Hades2 labels have ordinary alpha blending, not an authored depth mask. Do not
  copy a synthesized opaque pass-zero mask into a program's alpha/additive pass.
- Demise reuses `elly/smokeanimated.vtf` as a 2D emissive image and a 331-layer
  animation array. Texture target is cache identity; an ANY request is a wildcard,
  but a pending ANY image cannot satisfy a concrete-target request. Resource-status
  lookup uses ANY. The old cache returns the array to the 2D sampler.
- VTF frame-zero retention must still traverse all stored frames at every mip.
- A base-less brush uses Source's 32-unit default mapping, not the emissive image's
  1024-pixel width. Model/authored mappings remain distinct.
- Base-less reflective UnlitGeneric has reflection-only albedo, not a white base;
  preserve material/entity/vertex opacity and authored vertex RGB.
- Additive animated mist must mask RGB by vertex opacity, not only output alpha.
  Animated UnlitGeneric also needs `#UNLIT=1`, not an empty macro value.

## Reproducible checks

Use a uniquely owned existing scratch directory; these tools do not touch player
files. The C checks compile the actual production lookup/loop bodies with small
interface stubs, not a rewritten equivalent. They are not whole-renderer tests.

```
python tools/test_image_texture_cache.py --engine <engine-checkout> --workdir <owned-artifacts>
python tools/test_vtf_frames.py --engine <engine-checkout> --workdir <owned-artifacts>
python tools/test_source_material_depth.py --prepare <owned-rig>
python tools/test_source_material_depth.py <resolved-probe-log>
python tools/test_source_brush_alpha.py <dedicated-server-log>
python tools/test_reccheck.py
```

The material fixture must be present before boot. Remap loaded labels to its five
probe names under sv_cheats 1; split stdin commands below the bridge's 240-byte
limit. Query `r_shaderpasses probe/` and grade the saved log. Kitsune's isolated
server executes `cfg/test/source_brush_alpha.cfg`; retain the WHOLE server log.
The fixture exercises real target fan-out with Alpha 75/0, Disable/Enable and
separate render-mode collision controls, then restores opacity zero.

## Evidence and acting controls

Retained root: `C:/FTESurf-worktrees/mapvisual-01a13061`.
Source started at engine `1d3a954` / game `92a9653`; disjoint published changes
were fast-forwarded to engine `f0eadea54` / game `837eb004` before final build.
No owner/peer process was stopped, no owner config/data changed.

- `artifacts/resume-final-build.txt`: actual QC + native/plugin NoDeploy build;
  zero new compiler warnings. Known make peer-target warnings retained.
- `resume-final-cache-matrix.txt`: concrete target/order matrix, same-target
  reuse, ANY lifecycle, legacy identity flags and subpath policies PASS. Actual
  pre-change lookup fails the first mismatched-target assertion; retained in
  `resume-cache-matrix-control.txt`.
- `resume-final-vtf-loop.txt`: 2D frame-zero and 331-frame array traversal PASS
  with both environment layouts. Parent's old-loop frame-zero control fails;
  its array control passes. Header/payload bounds checks remain in production.
- `resume-verified-depth-probes.txt`: implicit alpha no-write; explicit alpha /
  additive depth masks and opaque/replace masks preserved; all five PASS.
- `resume-verified-brush.txt`: 111 state measurements PASS. Same-camera PNGs
  `resume-verified-kitsune-hidden`, `-visible`, `-restored` visibly show black ->
  rainbow Alpha75 -> black Alpha0. Pixel control is distinct from log grading.
- `resume-verified-demise-mist.txt`: both 2D and Array256x256x331 smoke views are
  loaded. `resume-verified-demise-circle.png` shows the native red glyph with no
  loose GLSL override. Mask-only and green-sentinel diagnostic overrides acted
  earlier and are removed from the runtime rig.
- `resume-verified-demise-mist[-off]` PNG/log pair: direct vertex alpha masks
  mist; disabling the feature restores solid coverage. Exact Source brightness
  and remaining background seams are not accepted as solved.
- Native Hades2 PNG and pass log show readable portal labels/backgrounds.
  `effects/combine_binocoverlay` resolves at runtime; an offline asset census
  that omitted Momentum's HL2 pack was not proof that this asset was missing.
- Rise native PNG inspected; its animated TV uses `#UNLIT=1`. Monster Jam's
  resolved alpha glass and water masks inspected; spawn screenshot is NOT a
  water-in-view visual acceptance gate.
- `resume-final-reccheck.txt`: 306 checks, zero failures. No evidence semantics
  changed; no player corpus was rewritten or private records exported.

## Review and limits

Read-only scout and two focused independent reviews completed. ANY preview-cache
reuse and reflection entity/vertex opacity omissions were fixed before final
build. Plugin clangd lacks its plugin compilation context and reports existing
header/type diagnostics; actual compilation is the build verdict.

Render modes 1..5 share an alpha approximation, not every Source compositing
mode. The Kitsune fixture verifies the same target fan-out and output handling,
not a successful native secret-button press: attempts at its physical button did
not ACT. That remains a human check. Reference fog/brightness parity and a proper
water-in-view regression gate remain separate. No map-specific product texture
remap or redistributed Source content is added.

A late-added diagnostic shader plus chained live fs_restart/remap and an empty
remap-reset attempt crashed the owned client; retained as failed harness arms.
Separate baseline and subject fs_restart/flushshaders controls remained alive.
Avoid using an empty remap target as a restore command; retire the test process.
The crash's full lifetime cause is not established by these controls.

## Delivery status

Product code: engine `6b6c8ab6805d7d295884048f4bb07386c8d0b38a`, tag `patch-683`;
game `791123cc173678d7533fb6d3472af032e7e11e7d`. Both exact SHAs pushed to main.
A subsequent documentation-only commit records the observations below; native
pin stays on the tested code commit. No release or QC Build-number bump.

Clean inspected worktrees built with pwsh7 `src/build.ps1 -Engine -Full -NoDeploy
-Jobs 8`, owned FteRoot/make wrapper. Exact-commit native glyph actor passes.
A separate owned detached parent `f0eadea54` full build used identical flags:
423 warning lines in each, zero new normalized messages. Syntax/path-normalizer
failures were retained as failed comparison-tool arms, then corrected; the final
`p683-warning-comparison.json` is the accepted result, not those failures.

At **2026-10-12T18:08:20Z**, 19 native/plugin/VM destinations in both Windows
installs hash-match the tested clean build; their immediate predecessors are
retained/hash-checked as `.prev`. Twelve protected config/manifest observations
remain hash+mtime unchanged. No owner process was stopped. Primary client is
`C:/FTESurf/ftesurf64.exe`; secondary client/server are `C:/FTEQuake/fteqw64.exe`
and `fteqwsv64.exe`; all five companion plugins plus three VMs ship as a pair.

Normal `build.ps1 -Jobs 8 -Pi` from the clean game commit produced zero warnings,
byte-identical programs. Fresh directory guard proved all twelve lobbies empty;
no PiForce. Both progs were staged/read back/swapped while retaining `.prev`, and
all twelve units restarted. menu.dat is Windows-local, never sent to lobbies.

| Program | Deployed SHA256 |
| --- | --- |
| qwprogs.dat | `796d65a027b7f9831a04ecea72c3b93c1b11b8237d140f3c7aab6933ce5e52bd` |
| csprogs.dat | `3e33342c3296afde1bece3f581830665ebb153535b2dd68108a882365ce4e669` |
| Windows menu.dat | `f13f792cb416ff0752ce51c1ac2cd0520e462a0f9a7c314b18caae2492e407c1` |

Post-Pi independent Windows readback still matches all 19 recorded targets.
At **18:17:03Z**, independent fleet readback proves twelve active PIDs, each
responding on its expected UDP socket, expected progs and predecessor hashes,
health OK and twelve empty directory rows. Native/plugin mappings are present;
Linux native/plugin were not shipped by this progs-only operation.

Each actual installed Windows engine/menu pair separately joined lobby 27510
from a fresh owned rig without CSQC. Both downloaded `6dbf6df8.dat` with the exact
served CSQC hash, drew board cols8/type14, reached their end markers and exited
normally with zero QC errors / zero smoke failures. Both screenshots inspected.
The two temporary smoke players are disconnected; no terms accepted or run
submitted. Client integration smoke does not upgrade the physical secret-button,
water-in-view or mist-brightness limits into passes.

Compact logs/screenshots/build hashes/rollback records remain under the owned
root. Original engine checkout's uncommitted work was not merged, stashed,
reverted or deployed. Disposable warning-control build is retired only after
its source/ignored inventory is verified; retained failed diagnostic/native
fixtures are explicitly marked for remaining visual follow-ups in OWNER.md.
