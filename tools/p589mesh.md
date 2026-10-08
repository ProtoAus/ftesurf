# Patch 589 — versioned native indexed 2D prerequisite

Forward-renumbered before publication after peers published P586 and then
P587/588. Earlier P586/P587 working rigs and source history are retained; their
internal names are not the published patch number. No published tag was moved.

## Scope / pre-registered predictions

A separate exact-size `2DMesh/1` C interface; legacy `2D` stays unchanged.
No ImGui, native UI service/QC builtin or real-panel migration in this patch.
The explicit QC bridge is a subsequent milestone, not a Sbar callback workaround.

- Old deployed P581 client rejects the new ABI but an existing-2D sentinel acts.
  Subject accepts exact size, rejects short/long size and unknown version.
- Physical top-left pixel positions and half-open clip rectangles; normalized
  UVs and straight RGBA8 textures/vertex colors. Bounded triangle-index batches
  include index/vertex offsets. Gallery covers both windings, nonzero offsets,
  vertex tint/alpha, atlas alpha, partial/empty/outside clips and batch order.
- Clip triangles in CPU space with interpolated UV/color; do NOT set BE_Scissor.
  This avoids its backend-dependent units/origin and preserves inherited clip.
  Submit real meshes through the renderer abstraction; flush pending 2D before
  and after. Keep caller color/blend/clip ownership intact. CPU clipping cost
  is not performance acceptance; budgets must be measured before UI migration.
- Texture tokens are opaque, plugin-owned, non-repeating across release/reuse,
  reload/unload and renderer restart. Invalid/stale/foreign tokens reject.
  Raw upload validates exact bytes/dimensions and per-plugin/global budgets.
  Automatic cleanup before renderer teardown and after plugin shutdown.
- Full-batch validation before drawing: invalid pointers/counts/indices/offsets,
  nonfinite data, invalid texture or clip reject with no partial submission.
  Native plugins are trusted code; this is not a hostile-pointer sandbox.
- Acting legacy draw-before/after markers, repeated captures at virtual scale
  1/2, renderer restart, plugin unload/reload, and -noplugins controls. Mixed
  real QC-before/after/inherited clip will be required by the following bridge
  milestone, not replaced by a native-only gallery here.
- GCC fixture compiles with -Wall -Wextra -Werror; native client/server retain
  zero NEW warnings. Grader mutations must reject missing action/pixels,
  incorrect offsets/clipping/alpha/dimensions and lifecycle witnesses.

Use disposable installs/cfgs only; never stop the owner's game, change their
settings or deploy uncommitted peers. No server progs/evidence/Pi changes.

## Verified frozen implementation

Engine `69b2c1bdb1cf916c8513df1dac2c374bd6c1f0f1`, annotated `patch-589`.
Its C/header tree exactly equals the initially verified `516a6a1f5` source;
only patch-note renumbering and preserved peer documentation were merged.
Clean full build stamp `git-7109-patch-589-0-g69b2c1bdb`; client SHA256
`7d125dedb98d597e1a786304b7e233ddea275bd598a6aa4e3fd1ac65ad885378`.
Full client/server/four-plugin compile retains all 74 P581 compiler warning
messages/counts, zero new; two baseline plugin-TU tidy warnings and one renderer
TU tidy warning. Standalone header/fixture clangd lacks engine include context;
both actual GCC DLL builds pass -Wall -Wextra -Werror.

```text
python tools/p589mesh.py --control <inspected-P581-client>
python tools/test_p589mesh_unit.py
python tools/p589mesh.py grade <retained-rig>
```

`rig/p589-mesh-xro1c2lq`: all five acting arms pass. Subject scale 1/2 and
repeat/restart/main-plugin reload images are exactly identical; screenshots
inspected. Each subject reaches 25 invalid, seven lifetime and 61 count-budget
assertions, foreign destroy AND submit rejection, both 32-texture cleanup
witnesses and no-renderer startup marker. 33 portable grader tests pass.
P581 atlas regression (`p577-atlas-2udum58u`), native font quality scales 1/2
(`font-quality-31y2a0yy`, `font-quality-8nf0jxpl`) and all 28 dedicated/editor
controls pass; native font crops are pixel-identical across scales and to the
P581 baseline.

Retained initial harness failures: engine snprintf macro needed undefining in
the standalone fixture; one grader pixel lay on the reverse triangle's diagonal
and one lay inside a bilinear atlas transition. Corrected geometric samples,
not loosened tolerances. Disabled arm's console can animate, so compare its
absence samples, not unrelated whole-screen console pixels. Final positive
runtime captures plus changed pixel/action/lifecycle mutations reject.

Limits: native-only GL/NVIDIA, not mixed QC inherited clip or explicit QC draw
ordering, non-GL/device/ImGui acceptance, byte/global-budget exhaustion stress,
thread/hostile-pointer isolation or CPU/GPU cost approval. The phase gallery
uses MenuEvent only as a test surface; the production UI bridge MUST be called
explicitly from MQC/CSQC, not substitute Sbar/Menu callbacks for that bridge.
Delivery/rollback and clean game-ref proof are recorded in AGENT_NOTES.md.

## Delivery checkpoint

Clean game `2cad73344ccab9e4addeb0e638f1c98bf620afce` in
`C:/FTESurf-mesh-proof` repeats zero-warning QC compile, all mesh arms and 33
unit tests. `p589-mesh-bcynr8m7` is the clean proof gallery.
At 2026-10-08T09:09:48Z, guarded native-only dual deployment ships the client
and matching hl2/cod/box3d/ode DLLs; all ten hashes match the frozen candidate.
Rollback: `.prev` plus `C:/FTESurf-mesh-proof/rig/deploy-p589-20261008T090946Z`.
Installed-client COPIES repeat all five arms (`p589-mesh-_9isse8e`,
`p589-mesh-20f_971_`), zero failed. Post-test destination and protected files
match. No owner process stop, progs/config/reader/asset/server/Pi/release swap,
settings edit or Build bump. This native prerequisite does not install ImGui.

