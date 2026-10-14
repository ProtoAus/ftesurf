# P700 — default alpha-order correction

Actual renderer changes, not new tracing/tooling. Default remains `r_blendsort 1`;
workers remain enabled. No QC Build bump, generated programs or release change.

## Fixed in source

- Shader reload no longer reverses unchanged batch lists. An immutable BSP
  first-surface key reconstructs original batch order after shaders migrate among
  sort bands, independent of reload history. Loading/nonbrush/unkeyed producers
  and cache/number invalidation retain their contracts.
- Default OpenGL ordinary static-world transparency now reaches the existing
  tested conservative plane sorter. Proven far-side faces draw before nearer
  faces across material batches; the baseline is BSP traversal, not yaw-sensitive
  centroids. Dynamic/weapon order and opt-in mode2 are not promoted or rewritten.
- Fog, program/deform, multipass, animation/callback, capture/portal and unavailable
  CPU geometry remain original-position whole-batch barriers. Unchanged,
  over-budget and cyclic runs replay original batch nodes. This preserves
  callback updates and does not interleave extra fog/material passes.

This is not order-independent transparency or a solution for arbitrary
intersecting, animated or program-displaced geometry.

## Verification

From the engine checkout, with a GCC-compatible C99 toolchain:

```text
python tools/test_model_shader_resort.py --cc gcc --output <owned-output>
python tools/test_gl_blend_faces.py --cc gcc --output <owned-output>
python tools/test_gl_blend_planes.py --cc gcc --output <owned-output>
```

Use a distinct output directory for each. On Windows add
`C:/msys64/ucrt64/bin` to PATH even when `--cc` is absolute. Do not use Python `-O`
for the existing blend tests: their assertions are the oracle.

Production functions are extracted, compiled and executed, not merely searched:
- O0/O2 rebucketing: unchanged lists, split/reunion, two different initial-band
  histories, shared/null shaders, loading/nonbrush/unkeyed producers, equal-key
  stability, shuffled4096-node membership, cache and number invalidation.
  Restored prepend and removed canonical sorting both compile and fail.
- Actual default0/1/2 dispatcher: all36 combinations of the three frozen Kitsune
  panes and six recorded viewpoints, dynamic boundary, capture barriers,
  fog/multipass/program/cache/recursive and oversize fallbacks, original callback
  persistence. Normal/HEXEN2 and normal/fast-math strict builds pass. Restoring old
  default dispatch or losing the fog/callback guards compiles and fails.
- Existing conservative geometry/program/projection/cycle/budget regressions and
  their eight compiled controls remain passing.
- Full isolated Windows m-rel build passes:37 existing compiler warning instances,
  zero new diagnostic payloads, shared dependency-cache5890 files hash/size/mtime
  unchanged through the client build. clangd compile database regenerated;
  no errors in affected C translation units; standalone header diagnostics lack
  its required including context. A later server/plugin `make -n` inspection
  timed out after recursive dependency configuration changed49 shared-cache
  paths. Failure/change inventory retained; no cache restoration/deletion.
  Server/plugin bundle verification is not claimed and deployment is blocked.

These are source/host regressions and a real client build, **not fresh GPU/pixel,
worker-startup or representative performance acceptance**. Historical rejected
native arms remain rejected; the spent decoder experiment is not rerun or credited.
No live Windows, Pi or Linux deployment is claimed. Exact candidate source,
client binary and unique failed/passing evidence are retained under
`C:/FTESurf-worktrees/mapvisual-01a13061`, in `engine-alpha/` and
`artifacts/alpha-fix-20261014/`.

## Remaining product validation

New coordinated native tests should compare correctly composited pane pixels
and worker-enabled startup repeats against an old-default control that is
required to fail. Preserve mode0/2/capture behavior; do not preserve incorrect
old default pixels as an acceptance requirement. Broader general transparency
and performance acceptance remain in BACKLOG.md.
