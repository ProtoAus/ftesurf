# P1318 — avoid false startup dynamic-lightmap invalidation

## State

Engine source **3a64ae747654c152c556777e8a686008c3719aa1**, annotated
**patch-1318**, is published. The renderer fix is implemented and verified by
acted diagnostics and an uninstrumented prepublication candidate. **The final
1318-stamped binary and dual Windows activation are pending:** the unchanged
4000MiB memory gate refused after available RAM fell to260–1043MiB. No process
was stopped and no safety gate was weakened. No final installed-native claim.

## Root cause and minimal change

At fresh-process map load, both an untouched surface's `dlightframe` and the
renderer light counter are0. Equality wrongly sets `cached_dlight`; first
visibility then rebuilds static lightmaps to remove a light that never existed.
Boreas' first late-route water reflection rebuilt647faces:44.79ms, zero style
changes and zero live CPU lightmap lights. This is not shader compilation.

Require a nonzero surface marker when caching that equality. R_PushDlights
increments the counter before marking real lights. Every nonzero-marker case
keeps its old behavior. No lighting math, quality, cvar, capture resolution,
shader, movement, recorder, protocol or QC Build change.

## Acted controls

- Same frozen Boreas viewer route: control647false dynamic-light rebuilds;
  instrumented subject0. Subject rendered-frame worst6.64/7.64ms over two passes,
  rather than the control's roughly40–50ms first reflection.
-36-case marker matrix changes only0/0. Real injected Source GPU light visibly
  appears and expires: world ROI mean absolute RGB difference before/live54.23,
  before/removed0.00071. Pictures inspected; no residual glow observed.
- Source VBSP has no CPU MarkLights callback. Its zero CPU-light counts are NOT
  a positive CPU-light regression. Nonzero CPU-marker behavior is unchanged by
  inspection/matrix, not claimed as an executed Quake CPU-lightmap scenario.
- Instrumentation is local only. Matching symbols retained per binary; all
  diagnostic code removed before the clean candidate build.

## Clean candidate, not universal stability

Prepublication candidate **1e8638c5c**, SHA256
`3e068bc8b54082e64755019bf905923fbd558e300e76eb687d845b423b8e8057`,
was built in a clean isolated worktree:36existing warnings, **zero NEW** warning
messages against the retained full native control. No diagnostic marker strings.

| Route | Pass | Average FPS | 1% low | 0.1% low | Worst frame |
|---|---:|---:|---:|---:|---:|
| Boreas | first |497|240|159|25.81ms |
| Boreas | repeat |500|248|200|7.18ms |
| Demise | first |393|254|190|7.69ms |
| Demise | repeat |390|242|148|24.78ms |

These are two complete replay traversals per map, not an all-map or numerical
causal percentage claim. The specific647-face first-reflection hitch is removed;
other spikes remain. Demise's repeat worst is at playback entry. Replay-open
parsing/allocation stalls must not be conflated with mid-run drawing. Both final
route screenshots were inspected. A missing test-menu ui_close command and an
existing empty model-directory warning remain in the log; routes completed.

Actual output1920x1200; scalar2, capture60/half0, GLSL warming1, uncapped,
idle0/vsync0/yield1 explicitly set. No driver-cache purge. Frozen content/plugin
and replay paths reused; screenshot/logging outside measured traversals. Tests
use imported bookmark replays, not evidence of a native ranked/movement verdict.
No automatic native-resolution, AA, frame-cap or saved-settings change.

## Numbering and build provenance

The earlier1317 reservation collided with the concurrent published Christmas
asset patch. Renderer1317 was NEVER published or installed. Final feature is
**1318 only**; preserve old raw logs/stamps, do not relabel or redate them.
From that candidate to1318, executable source semantics are unchanged; the source
comment and publication/version metadata changed. The peer integration changes
only ENGINE_PATCHES.md on the native side. Final metadata still requires an
actual clean rebuild, not binary string editing or an incremental relink.

The first manual metadata command omitted standard build.ps1's `--tags`; changing
the version compiler flags also failed to invalidate existing objects. Failed
artifacts are retained. Standard `--tags`/source-date stamping and full `m-rel`
recompilation are the correction, not a product Makefile defect claim.

## Exact remaining delivery

Build the inspected tag with the existing native m-rel target, same complete
UCRT codec cache/flags, two jobs, standard source stamp and full rebuild; require
the unchanged memory/rig gate, correct embedded1318 source stamp and no probe.
Then use the standard build.ps1 Deploy helper on ONLY the actual primary pair:
`C:/FTESurf/ftesurf64.exe` and `C:/FTEQuake/fteqw64.exe`. Preserve current/older.prev
preimages; verify destination hashes and live behavior. Optional client aliases,
QC programs, dedicated servers, plugins, configs, player data, backend and lobbies
are not this patch's ship set. Published P1314 server-side native source is already
part of the inspected engine parent; no separate dedicated/server deployment.

Both current primary clients remain exact P1312 bytes, SHA256
`2b8735018e018e9ae8540a981e0c44c716514acf47bba2a8f2e708ef438544b3`.
No client activation or rollback file has been changed by this renderer work.

Local evidence/retention root:
`C:/FTESurf-worktrees/lows-20261104T2339Z-01a1a8e6/`.
`artifacts/boreas-lmprobe`, `boreas-lmfixed`, `p1317-client`, `p1317-clean` retain
acted controls, matching symbols, failed metadata build, clean outputs and images.
Paired source worktrees/cache retained for the blocked final build; not abandoned.
P1311's known-shader seed was already delivered separately to both installs.
Its2second budget and late-created programs still prevent an all-shaders-ready
guarantee. Owner feel acceptance remains pending in lextest.md.
