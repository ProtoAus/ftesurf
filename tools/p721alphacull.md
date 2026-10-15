# P721 — cull-aware default world-alpha ordering

## Problem and bounded fix

P701 admitted supported same-material foreground panes, but its default1 plane
graph still included commands that actual GL culling would never rasterize.
Those commands could introduce cycles/barriers, leaving the whole run unchanged.
A stale entity RF_XFLIP contribution also had to be cleared before evaluating
world winding; the view-level flip must remain intact.

The default1 static-world single-pass path now omits only proven raster-empty
commands using every indexed triangle, actual remapped FRONT/BACK/two-sided
state, view/projection and positive eye distance. Unknown/degenerate/nonfinite,
eye-spanning, animated/CPU-unavailable geometry remains conservative. Select
the actual world entity before this proof. The existing raw128-face budget is
counted before filtering, and original whole-batch replay remains the fallback.
No new cvar, map-ID shortcut, centroid sort, OIT, worker override, mode0/2
change, default2 promotion, ABI/header, other backend or QC Build change.

## Verification already completed before clean publication

Portable actual-dispatcher regression: four GCC variants (normal, HEXEN2,
fast-math, combined),17 named compiled/runtime mutants ACT and reject. Covers
all28 retained Kitsune fans at six frozen yaws, conservative uncertainty,
projection and cull/view flips, raw budget and entity-state restoration. Required
`tools/blend_world_fixtures.inc` is deliberately included in the engine commit,
not assumed from an untracked local dependency.

Independent native104.2 reference: candidate exactly equals a separately
justified28-command reference fullframe; wrong reference7936px and broken
baseline16996px controls ACT. Subsequent40-frame/3-boot matrix passes exact
stationary repeats, six-yaw cross-startup stability, mode0/2 same-mode baseline
preservation, default returns, and independent104.2 reference equality.
Mode0/default104.2 differs42052px. Every startup/post-shot has4ordinary live
workers; default1 is read before writes and scene cache is explicitly0.
Other-yaw equality is stability, not independent visual ground truth.

Clean latest-upstream source preparation repeats four variants/17 ACTED mutants
with the exact accepted three renderer/test/fixture files. Engine commit
`b548053218a00aa6e549dfee9ad02a65833317b8` / tag `patch-721` builds client,
dedicated server and five plugins as one coherent bundle with stamp
`git-721-b548053218a00aa6e549dfee9ad02a65833317b8`. PE architecture/section,
static imports, plugin entry, metadata/stamp, ZIP CRC/member and hashes pass;
packaging preserves PE prefixes. No increased compiler-warning payload counts
against the retained comparable baselines. Existing warnings remain. All5890
cached dependency files, Box3D archive and1084tracked source files/index remain
unchanged. Client SHA256:
`5ec109179776795784212911492b87da504c50a3eca238bf4d9cc700b58276b2`.

Fresh independently reviewed exact-build native smoke PASSES2026-10-15: one
boot,4engine-written RGB960x720frames,147.7seconds, first attempt/rc0. Default,
repeat and mode0-to-default return equal the ORIGINAL independent104.2 image
fullframe (0changed pixels). Mode0 equals the original same-yaw/mode0 baseline
and differs from default by42052pixels (ACTED). Startup/default-before-write and
every post-shot have4ordinary live workers, cache explicitly0. Independent
post-run byte audit verifies all4images, logs, original8/backups, protected
subject, both untouched installs,1167held inputs plus spec and zero owned
processes remaining. No relaxed oracle, native retry or repeated broad matrix.
Parent opened full default/mode0 PNGs. Source publication and dual-Windows
installation are separate, later receipted operations, not inferred here.

## Explicit remaining limits

No quiet service/cadence/tail acceptance, universal map certification or default2
promotion. Source scene-cache selection is not actual supported-cache action;
new-candidate supported Q1 cache acceptance needs a source-bound diagnostic twin.
Native static-world program/multipass/capture/reflection and raw-budget fixtures
remain separate integration gaps; existing host controls do not manufacture GPU
action. Conservative unsupported geometry/material/recursive-view fallbacks are
intentional, not fixed transparency in all scenes. No Linux/Pi native deployment,
release/archive/feed or QC progs/config shipping is implied.

Detailed local evidence is retained under the owned mapvisual task root in
`artifacts/alpha-review-01a13b94/`, including original failed runs. No failed gate
or historical oracle was relabelled a pass.
