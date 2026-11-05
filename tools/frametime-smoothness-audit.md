# Surf loading, frame-time statistics and noclip-void audit — 6 Nov 2026

## Scope and source identity

Investigation, not a delivered performance patch. Three independent read-only
subagents audited statistics, void rendering and loading; parent reread decisive
source and executed the literal sampler/statistics C with a deterministic clock.
No product source/configuration/quality change, client launch or deployment.

Inspected mod `2882f0a9d4205d827c2af512c3e991acfe7cae8f`; engine
`d6c185c12fc32267b8944313e69b96ecb5ac5950`. Canonical checkouts were dirty/stale,
so clean worktrees were used. The installed Windows client hashes were read back
as `55040dc1820171f00d50d5863218a263b6285d83f7b5de0893e9629d814c2194`, matching
the retained P1318 report. `engine/client/cl_screen.c` has no diff between that
reported installed source `3a64ae747654c152c556777e8a686008c3719aa1` and the
audited engine ref. This binds the sampler source, not a new runtime performance
measurement. Engine citations below are relative to that inspected engine ref;
QC citations are relative to the inspected mod ref.

## Are the 1% / 0.1% lows accurate?

**Useful filtered approximations, not exact or complete frame-presentation data.**
The actual command is `r_frametime`, with `r_frametime_dump/reset`.

- `engine/client/cl_screen.c:948–1041` samples wall-clock intervals once per
  rendered frame. In OpenGL the endpoint is after normal scene/HUD work but
  before the final overlay flush, frame-end GPU marker, pacing and present
  (`engine/gl/gl_screen.c:264–280`). The next interval includes the preceding
  wait/present/scheduling. This is neither GPU-only time nor display-present time.
- Lows are `1000 / mean(slowest max(1,floor(N*fraction)) frame durations)`.
  They are **not p99/p99.9** and not the mean of reciprocal per-frame FPS.
  For fewer than 2,000 samples, the 0.1% low uses just one worst sample.
- Most timings are histogram-bin midpoints: 0.05 ms bins, error up to about
  0.025 ms per represented frame. Average uses the exact accumulated durations.
  Values from about 199.95 ms share an overflow bin: the slowest 64 are kept
  exactly, the rest approximated by their mean. Large overflow tails can differ
  from a sorted exact reference even after fixing the cache defects below.
- Default statistics window is **30 seconds**, separate from the 10-second graph.
  Clamp is 1–120 seconds. Capacity is 65,536 frames; higher rates shorten the
  actual covered duration (about 2,185 FPS at 30 seconds, 547 FPS at 120 seconds).
  Reset explicitly for each map/pass; no map reset is implemented in this module.
- Intervals **over 1,000 ms are discarded**, even if a real gameplay freeze caused
  them. Exactly 1,000 ms counts. Positive idle throttling while unfocused also
  excludes intervals. Menus/loading under a second can conversely enter the
  window. Dumps rebase the sampler around synchronous output and should stay
  outside measured passes. These policies need explicit disclosure/exclusion
  counters, not silently interpreting a missing stall as smooth playback.

### Two actual cache bugs, reproduced from production C

1. `cl_screen.c:993–1020`: after appending the new frame, expiry rebuild includes
   it, then normal insertion includes it again. Actual retained frames
   `[400,610] ms` produce cache `[610,610,400]`; overflow rank1 reads610 instead
   of400. This can corrupt overflow-tail statistics and worst-frame listings.
   Normal sub-200 ms histogram-tail values do not thereby become universally
   wrong. Smallest fix: newest frame enters the rebuilt/incremental cache once,
   preserving camera metadata.
2. `cl_screen.c:849–857,991–1008`: capacity eviction updates histogram/sum but
   does not invalidate the exact slow-frame cache until time expiry. With a
   120-second window, after replacing an initial900 ms frame with65,536 genuine
   0.5 ms samples, reported worst remains900 ms. Smallest fix: invalidate/rebuild
   cached frames on ring-cap removal as well as time expiry, without duplicating
   the appended frame.

### Reproducible CPU-only audit

`tools/audit_frametime.py` extracts the actual C between `FT_RING` and
`R_FrameTime_Draw`, stubs only clock/cvars/view metadata, compiles with the
existing C toolchain and records source/body hashes and observations. It is a
**diagnostic**, not a fixed-engine regression pass or a GPU benchmark. An
unsupported source layout fails loudly. Output must be under an owned task root.

```powershell
python tools/audit_frametime.py `
  --source C:/FTESurf-worktrees/<owned-task>/engine/engine/client/cl_screen.c `
  --out C:/FTESurf-worktrees/<owned-task>/artifacts/cpu-audit `
  --cc C:/msys64/ucrt64/bin/gcc.exe
```

Verified with GCC16.1.0, `-std=c99 -O2 -Wall -Wextra`, zero diagnostics:

| Stimulus | Actual C observation |
|---|---|
| Expiry with400/610 ms retained | duplicate610; second-slowest overflow rank wrong |
| Capacity eviction of900 ms, retained frames all0.5 ms | worst incorrectly900 ms |
| 10 ms +1,501 ms +10 ms | only two samples /20 ms accepted over1,521 ms |
| 999x10 ms +1x100 ms | 1%52.56242 FPS vs exact tail52.63158; 0.1%9.9975 vs10 (binning) |
| 1,000 ms then1,001 ms then10 ms | only1,000+10 ms accepted |

Sampler source SHA256 `5314592cd03862c1c6d246b26dfa919296687d4a5debbca3d92790d78123a96c`;
extracted-body SHA256 `683ddcd2639a7d61e755ab51d2ddde8c26201b0976f7ca3ac2953d9b7bb6371c`.
Early scratch harness attempts failed before a valid test: wrong extraction-token
assumptions, wrong compiler directory and missing documented UCRT PATH. They are
not product failures or passes. The reusable tool corrects those seams and keeps
compiler diagnostics. No native game build was attempted/claimed.

## What noclip-void actually does

**It does not currently implement BSP-only/effects-free rendering.**

- `engine/client/r_surf.c:2445–2465,2596–2655`: the primary camera must have
  cluster-1, noclip/spectator movement type and nonzero `r_voidvis`. It forces an
  all-visible PVS while retaining frustum/area culling. Ordinary valid empty
  leaves are not void. Non-noclip falling uses the last-good-cluster fallback.
- With default `r_voidfog 1`, the active void flag suppresses the normal blended
  global-fog path (`gl/gl_rmain.c:2870–2905`); `r_voidfog 0` retains map fog.
  OpenGL portal-budget collection rejects cluster-1 (`:1511–1535`). This is not
  a blanket suppression of skyrooms, water/material shading or other effects.
- Historical entity-drop modes were explicitly removed. The comment's zero
  entities on one old surf_666 view is **not a guarantee for current maps**.
  Native Source props use the forced PVS and can survive their PVS/area/frustum
  tests, load models and perform initial lighting (`plugins/hl2/mod_vbsp.c:
  10486–10488,10803–10867`). The existing `RDF_NOENTS` seam skips this native
  prop loop before lighting; no new plugin ABI is inherently required.
- `src/client/cl_main.qc:2029–2076` still queues bodies/viewmodels/overlays and
  calls Snow/Emit/RampWear/Winter/Weather. Camera-following snow in
  `cl_snow.qc:101–138` has no void guard. Native static entities, particles and
  persistent decals still run (`engine/client/r_surf.c:4094–4105`). Late entity
  filtering alone cannot suppress already queued QC polygons or particle work.
- All-world visibility can itself be expensive: no PVS rejection, more geometry,
  material batches, displacement meshes, overdraw and transparent world shading.
  Batched BSP is not automatically cheap. Dominant cost at the owner's camera
  has **not** been measured here.

A coherent future policy must share the final-camera predicate across QC/native
submission paths, suppress unwanted props/effects before expensive preparation,
keep world/displacements and define whether brush submodels (doors/ramps/glass)
and the structural 3D skyroom remain. Do not freeze particle lifetimes or mutate
archived quality cvars: reentry must not produce stale bursts or changed settings.

Falsifier: an interleaved same-camera suppression-off/on pair must keep forced
world visibility, fog and portal policy identical. Off must positively show native
props, an emitter and camera snow; on must remove their submissions/pixels while
retained structural meshes stay identical. Check indoor noclip, ordinary walk,
falling, recursive views and reentry. `r_voidvis 0/1` alone is NOT this control:
it changes which world geometry is visible too. Owner map/pose/aim is still needed
for the quickest specific reproduction; a small human visual check is preferable
to a new sprawling harness.

## Loading and shaders: improved, but not an all-ready guarantee

`engine/client/cl_main.c:456–500` reloads shaders and calls `GLSLWarm_MapActive`
behind loading. `engine/gl/gl_shader.c:5676–5718` warms remembered permutations
for existing active programs with a **soft two-second budget** (checked after a
compile). Late-created/unremembered programs and later reloads remain gaps; the
current count/time message does not report pending work or budget exhaustion.
A linked program is not proof of texture/model upload, first-draw driver work,
particle/audio residency or reflection-target allocation. No remaining resource
hitch of those classes was newly measured on these four maps in this audit.

Do not increase the limit blindly or claim enumeration of all2^N permutations.
Define a finite map/material/event resource closure, completion/invalidation and
failure/timeout behavior, then expose eligible/pending/budget-hit/late-compile
telemetry. CPU assets, uploads, GLSL/link and first draw are separate layers.
See the existing strict-readiness entry in `ROADMAP.md`.

### Reused map evidence, not freshly measured FPS

- **surf_boreas / surf_demise:** P1311 seeds three demonstrated missing variants;
  P1318 fixed a separate false first-view lightmap rebuild. Its acted control
  removed647 false rebuilds/44.79 ms. Retained installed-client checks report
  Boreas worst9.51 ms and Demise10.83 ms on their specified routes. These are
  historical, bounded checks, not new universal FPS results or proof every
  shader/resource is ready. Cache bugs above do not invalidate the separate
  lightmap counters/causal control. See `p1318-lightmap-first-view.md` and
  `p1311-map-prewarm.md` for settings, limits and exact evidence.
- **bhop_ceaseless / surf_garden:** no current four-layer first-traversal
  acceptance established by this bounded evidence review. Old Garden work is
  not current prewarm acceptance. The current P1321 BACKLOG entry additionally
  records Garden first/repeat full-view opening hitches: those include replay
  startup, not only active gameplay; its settled diagnostic remains pending.
  Do not invent a pass, regrade those captures or invent a missing-asset blocker.
- No additional GPU runs were launched: this investigation used existing demo
  evidence and a CPU-only falsifier, without competing with other bots' replay
  measurements or introducing their observer artifacts. No new four-map claim.

## Recommended implementation order (not implemented by this audit)

1. Repair the two statistics-cache defects and report excluded time, sample count
   and actual covered span; retain explicit tail-vs-percentile labels.
2. Implement the shared primary-view world-only policy, preserving agreed
   structural geometry, with acted off/on witnesses and indoor/reentry controls.
3. Add bounded deferred-work telemetry, then test fresh first/repeat Garden and
   Ceaseless routes plus reload/budget-exhaustion/missing-permutation controls.
4. Finish a finite, explicit pre-run readiness contract without hiding failures
   or degrading quality. Separate ordinary scene/GPU cost from one-off loading.
