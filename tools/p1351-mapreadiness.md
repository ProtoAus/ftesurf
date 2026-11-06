# P1351 — bounded activation closure and late-work diagnostics

## Contract (not a universal loading guarantee)

At `CL_MakeActive`, after the existing shader reload, attempt this named closure:

- Named slots in the server, CSQC and viewweapon model precaches.
- File images in the current renderer registration sequence, excluding render targets.
- Base programs of live shaders/passes, plus their remembered/seeded, supported GLSL permutations. Duplicate program pointers and masked permutation aliases count once.

`r_mapready_budget` defaults to **2 soft seconds**, clamped to 0..10. It is a shared budget for pending resource completion and additional permutation compilation, checked before every queued main-thread completion and every additional compile. It does NOT preempt an individual synchronous upload, worker completion or driver compilation, nor bound initial resource registration, the prior shader reload, history-file I/O, or traversal/sorting time. It does not drain unrelated jobs through an unbounded full sync. `COM_HasWork()` is not a completion predicate: an executing worker has removed its queue entry. The implementation polls actual registered resource load states instead.

An unrequested/missing model/image is incomplete but is not waited on as though an executing worker will complete it. A failed compile's base-program fallback remains renderer-compatible but is **failed**, not ready. Timeout leaves a positive pending count. The readiness diagnostic is informational at the existing loading boundary, **not client authority over server timer/evidence admission**. Strict timer/start gating is not implemented by this patch.

### Explicit exclusions

Future registrations, unsupported/unremembered permutations, unowned fixed-emulation programs, render targets/reflections, driver first draw/link residency, audio, dynamic route events, and universal map coverage. Loaded model state is not proof that every lazy GPU mesh buffer is allocated or remains resident. A `ready-closure` activation is not a promise that no later work can occur. Optional failed image lookup attempts remain visible; this diagnostic does not know the complete fallback-material dependency graph.

## Reading `r_mapready_info`

- Primary state: `not-started`, `disabled`, `unsupported`, `incomplete`, `ready-closure`, `late-work` or `invalidated`.
- `activation` preserves the historical loading-boundary result even after later work invalidates a broader interpretation.
- Programs: unique program count, missing base program count, unique eligible permutations, already available, successfully compiled, failed/fallback, pending.
- Activation model/image slots: total, pending, failed, unrequested.
- Late GLSL compile attempts/failures, cumulative measured compile time, last program/permutation.
- Late image completions/failures, cumulative main-thread completion time, last image. This is upload/completion time, **not background file/decode duration**, and includes optional failed lookup completions. Only main-thread work is counted.
- Reload requests invalidate the activation; future compilation/completion is counted separately. Each activation resets counters. Telemetry never opens/writes a file during play; the pre-existing GLSL history is saved at the loading boundary.

No automatic retry hides a failure. Inspect the reason; `developer 1; imagelist` includes failed image attempts in the existing image inventory (default image-list output hides them). A reconnect/map activation starts a new bounded attempt. `r_glsl_warm 0` remains an explicit disabled control, not a successful readiness result. `r_mapready_budget 0` inventories pending shader work without issuing additional compile requests.

## Verification so far

- Source-bound `tools/test_mapreadiness.py`: **32 checks**, `-Wall -Wextra -Werror`, covering acting compilation, shared-program/masked-permutation deduplication, repeat availability, zero budget, failed and pre-existing fallback, executing-worker resource completion, nonprogressing timeout, failed/unrequested resources, old-registration/render-target exclusions, disabled/unsupported renderers, late compile/image telemetry, main-thread and warming exclusions, invalidation/reset, NaN/negative-infinity budget controls using the engine's actual `bound` macro.
- Supported isolated full native build and QC build passed. QC: three passes, zero warnings. Native: pre-existing warnings in untouched files; no warning from changed implementation files. clangd's generated database resolves changed C translation units, with pre-existing style diagnostics only; standalone `render.h` lacks its includer context and is not an independent translation unit.
- Initial in-flight signature build failure and a detached MSYS make stall retained under the owned root. Same supported build entrypoint succeeded synchronously; do not repeat the hidden detached build path.
- Graphical native/socket smoke accepted: normal reconnect compiled61 eligible permutations, pending0/failed0; budget0 compiled0/pending61/budget-hit1; later replay drawing added6 compiles and one image completion; PBR change reported primary `invalidated`. Initial app activation included648 file images/207 failed attempts; reconnect included460/8. These are registered lookup failures, not proof of visible missing materials. Both remain **incomplete**. Exact console/counters retained under artifacts/native-smoke/.
- Engine source c28dcf9bd/tagpatch-1351 is committed/pushed. Sixteen fresh first-use/repeat route windows were captured with advancing replay controls, no idle exclusions/capacity eviction and no competing game at pre/post census. Detailed interpretation and Tensor2 attribution are recorded separately; this is not a causal product before/after comparison. Clean metadata-correct P1351 natives were subsequently installed in BOTH Windows installs at2026-11-06T18:09:25Z:10destinations and their.prev verified; both installed clients return the expected clean stamp. Owner config/QC/symbol files were hash-preserved. No Pi/backend or release publication was needed.
- Unchanged frame sampler/dump regression:442 plus550 exact-controls checks, zero failures. Native warning comparison to the retained P1348 full-build control found46 distinct warning types on both, zero novel types; none points to the changed implementation.
- Full capture interpretation, positive late-work findings, delivery provenance and remaining gates: [p1351-pacing-results.md](p1351-pacing-results.md). No measured final performance improvement, driver-cache-cold result, universal residency, complete route closure, or owner visual confirmation claimed.

## Reproduction

```text
python -B tools/test_mapreadiness.py --engine <owned-fte-checkout> --out <owned-root>/artifacts/readiness-test
pwsh -NoProfile -Command "./build.ps1 -Engine -Full -NoDeploy -Jobs 8 -FteRoot <owned-fte-checkout>"
```

Owned continuation workspace: `C:/FTESurf-worktrees/ready-20261106T1706Z-01a1b1d2/`.
0.1.41 release and its frozen workspace are untouched and are not rebuilt or republished.
