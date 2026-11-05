# P1318 — avoid false startup dynamic-lightmap invalidation

## Implemented, verified, published and installed

Engine source **3a64ae747654c152c556777e8a686008c3719aa1**, annotated
**patch-1318**, is published. The clean final client is installed in both actual
Windows primary locations and both actual executables completed fresh replay
checks. Owner feel acceptance remains pending; this is not universal stability.

## Root cause and minimal change

At fresh-process map load, both an untouched surface's `dlightframe` and the
renderer light counter are zero. Equality wrongly sets `cached_dlight`; first
visibility rebuilds static lightmaps to remove a light that never existed.
Boreas' first late-route water reflection rebuilt **647 faces / 44.79 ms**, with
zero style changes and zero live CPU lightmap lights. This is not shader compilation.

Require a nonzero surface marker when caching that equality. R_PushDlights
increments the counter before marking real lights. Every nonzero-marker case
keeps its old behavior. No lighting math, quality, cvar, capture resolution,
shader, movement, recorder, protocol or QC Build change.

## Acted controls

- Same frozen Boreas viewer route: control 647 false dynamic-light rebuilds;
  instrumented subject zero. Subject rendered-frame worst 6.64/7.64 ms over two
  passes, rather than the control's roughly 40–50 ms first reflection.
- A 36-case marker matrix changes only 0/0. Real injected Source GPU light visibly
  appears and expires: world ROI mean absolute RGB difference before/live 54.23,
  before/removed 0.00071. Pictures inspected; no residual glow observed.
- Source VBSP has no CPU MarkLights callback. Its zero CPU-light counts are NOT
  a positive CPU-light regression. Nonzero CPU-marker behavior is unchanged by
  inspection/matrix, not claimed as an executed Quake CPU-lightmap scenario.
- Instrumentation is local only. Matching symbols retained per binary; all
  diagnostic code removed before either clean candidate or final native build.

## Uninstrumented checks and limits

Prepublication candidate **1e8638c5c**, SHA256
`3e068bc8b54082e64755019bf905923fbd558e300e76eb687d845b423b8e8057`,
completed two traversals per map and inspected screenshots:

| Route | Pass | Average FPS | 1% low | 0.1% low | Worst frame |
|---|---:|---:|---:|---:|---:|
| Boreas | first | 497 | 240 | 159 | 25.81 ms |
| Boreas | repeat | 500 | 248 | 200 | 7.18 ms |
| Demise | first | 393 | 254 | 190 | 7.69 ms |
| Demise | repeat | 390 | 242 | 148 | 24.78 ms |

After final installation, **each actual primary executable**, not a renamed test
copy, ran with an owned `-basedir`/`-nohome` fixture and exited normally:

| Actual receiver | Route | Average FPS | 1% low | 0.1% low | Worst frame |
|---|---|---:|---:|---:|---:|
| C:/FTESurf/ftesurf64.exe | Boreas | 447 | 209 | 167 | 9.51 ms |
| C:/FTEQuake/fteqw64.exe | Demise | 369 | 205 | 159 | 10.83 ms |

The final Boreas worst is at the same late reflection camera, now 9.51 ms rather
than the repeatable roughly 40–50 ms control. These are not all-map or causal
whole-FPS percentage claims. Other spikes remain; candidate Demise's repeat worst
was at playback entry. Replay-open parsing/allocation stalls must not be conflated
with mid-run drawing. The existing empty model-directory warning and unavailable
fixture ui_close command remain; scenes/replay completion and expected native
stamp acted. No new product runtime error was found.

Actual output 1920x1200; scalar 2, capture 60/half 0, GLSL warming 1, uncapped,
idle 0/vsync 0/yield 1 explicitly set. No driver-cache purge. Frozen content/plugin
and replay paths reused; screenshots/logging outside measured traversals. Tests
use imported bookmark replays, not a native ranked/movement verdict. Background
load varied; do not turn these rows into a universal performance percentage.
No automatic native-resolution, AA, frame-cap or saved-settings change.

## Build and Windows activation — 5 November 2026 UTC

Final native stamp: **git-8383-patch-1318-0-g3a64ae747**, no dirty suffix.
Client SHA256:
`55040dc1820171f00d50d5863218a263b6285d83f7b5de0893e9629d814c2194`.
Clean isolated source, full native `m-rel` rebuild, two jobs, existing complete
UCRT codec cache and standard build.ps1 Windows-Git/source-date metadata:
**36 existing warnings / zero NEW** against the retained full native control.
No diagnostic marker strings in the final image.

At **09:13:08–09:13:09 UTC**, reused the existing build.ps1 Deploy/Ok helpers on
ONLY `C:/FTESurf/ftesurf64.exe` and `C:/FTEQuake/fteqw64.exe`. Both destination
hashes match the final artifact. Both `.prev` files equal exact P1312 predecessor
SHA256 `2b8735018e018e9ae8540a981e0c44c716514acf47bba2a8f2e708ef438544b3`.
Current and older `.prev` preimages were separately archived and rehashed before
copying. All **58 protected non-target native/progs/owner-config files** were
unchanged across activation AND after both actual receiver checks.

No optional client alias, QC program, dedicated server, plugin, configuration,
player data, backend, lobby or release was deployed. Published P1314 server-side
native source is already part of the inspected engine parent; this does not
activate its separate QC feature or perform a dedicated/server deployment.
Rollback is the exact primary pair's `.prev`, with older history additionally
retained under `artifacts/p1318-activation/`; never restore unrelated player data.

## Preserved failures, numbering and readiness limits

The earlier 1317 reservation collided with the concurrent published Christmas
asset patch. Renderer 1317 was NEVER published or installed. Final feature is
**1318 only**; old raw logs/stamps were not relabelled or redated. Native executable
source differs from that validated candidate only in a comment; final version
metadata was genuinely recompiled, not edited into a binary.

The manual build path initially omitted standard `--tags`; changed version
compiler flags also needed a full rebuild. A later trial selected MSYS Git after
PATH mutation and falsely stamped a clean CRLF checkout dirty. The final build
uses the absolute inspected Windows Git before compiler PATH mutation, as the
standard build already requires. Failed artifacts retained; no Makefile defect
claimed. The unchanged 4000 MiB/quiet/rig gates refused low-memory or busy windows;
RAM later recovered and both final build and runtime checks passed normally.
No owner/peer process was stopped and no gate was weakened.

Local evidence/rollback retention root:
`C:/FTESurf-worktrees/lows-20261104T2339Z-01a1a8e6/`.
Acted controls, matching symbols, failure records, final build, activation receipt
and receiver summaries remain under `artifacts/`. P1311's known-shader seed was
already delivered separately to both installs. Its two-second budget and
late-created programs still prevent an all-shaders-ready guarantee. Owner feel
acceptance remains pending in lextest.md.
