# Five-map low-FPS diagnosis and Garden b1 water (6 Nov 2026)

## Result and status

Fresh matched first/repeat replay-view windows now exist for **all five maps**.
Tensor2 has a substantial persistent sprite sky-query CPU cost; Garden/Demise
respond much more to pixel load; Boreas is mixed. Ceaseless additionally has a
large first-traversal render-phase hitch that the measured GLSL compile time does
not explain. These are diagnoses, **not a new product performance fix**.

An optional, default-off adaptive water refresh prototype was built/tested only
in an isolated engine. It reduced Garden b1 capture work, but did not establish a
meaningful end-to-end speed improvement over nominal60. It is **not committed as
product code, enabled, installed or deployed**. No settings/quality downgrade,
FPS cap or removed visibility traces were shipped. No new engine patch is claimed.

## Measurement contract and frozen inputs

Owned evidence: `C:/FTESurf-worktrees/lowwater-20261106T1910Z-01a1b1d2/`.
`artifacts/plan.md` preregisters controls; `accepted-summary.json` contains parsed
accepted windows; native per-case receipts retain raw dumps/positive witnesses.
There is no owner/player-data edit, driver-cache purge or peer process shutdown.

- Baseline FINAL P1351 native source `c28dcf9bdd40cf9a25ff850338ca0b14e742fe89`,
  version `git-8483-patch-1351-0-gc28dcf9bd`, read from the prior owned ready root.
  Native SHA256 `0a1251d6d05429edc69fbe9650a2c1702a527327236397568cb872a2c95ca54a`;
  normal CS SHA256 `c8fb5d8c7bf2ea623d9bea5f2d7a2230a3242cad25c76d0159d5e84b83f7aff6`.
  Full client/server/plugin/three-progs hashes are in `baseline-inputs.json`.
  This frozen control is NOT a qualification of later P1353/P1354 source/installs.
- Real dedicated socket, fixed1920x1200, `r_renderscale 2` (3840x2400 internally),
  vsync0, uncapped measured windows, `cl_idlefps 0`, `cl_yieldcpu 1`, Christmas0,
  `hl2_water 0` (flat), nominal capture60. Saved owner settings read-only at task
  start included scale2/water0/capture60; not every personal setting is reproduced.
  The separate water trial explicitly uses full live reflection/refraction mode2.
- Fresh application per map; same seek/duration on first and repeat. Existing
  shipped seeds plus the fixture's accumulated learned shader history were retained;
  these are NOT purged-driver/cold-cache trials. Measurement includes normal replay
  viewer/HUD work, not physical live-player input or display-present measurements.
  Imported recordings without view sidecars use existing camera fallback behavior.
- Replay is preloaded/paused/seeked before reset. Advancing native replay timestamps
  prove motion. No screenshot, bridge command, client file logging or clipboard dump in
  timed route windows. Above8ms native console spike breadcrumbs are enabled there.
  `r_budget 1`/GPU-query overhead is held constant; VM profiling and budget-CSQC
  profiling are OFF in the FPS windows. Budget tables describe trailing5s, not
  entire-route averages. Native VM profiles are separate100fps diagnostics.
- Exact native copied-sample tails, floor(N*0.01/0.001), minimum1; FPS is reciprocal
  mean tail duration, NOT reciprocal p99/p99.9. No focus-idle or capacity exclusions.
  Pre/post actor checks plus4096MiB/60s quiet admission; continuous unrelated host
  inactivity is not established. A single pair per route is not a statistical
  product-speedup proof. Long Tensor2 route coverage remains explicitly partial.

## Matched low-FPS observations

FPS columns are average / mean slowest1% / mean slowest0.1%. Worst is milliseconds.
The selected near-whole short routes deliberately stop before a held final frame.

| Map, replay, seek/duration | First FPS | Repeat FPS | Worst first / repeat ms | Samples first / repeat |
|---|---:|---:|---:|---:|
| Boreas r5436,0.25/39.04s |499 /255 /198|497 /257 /219|9.01 /6.19|19496 /19404|
| Demise r1684,0.25/36.65s |390 /237 /160|388 /246 /198|9.89 /6.98|14300 /14215|
| Garden r24789,0.25/86.8s |527 /260 /205|523 /261 /212|9.03 /5.81|45783 /45434|
| Ceaseless r77,0.25/41.5s |738 /235 /44|752 /419 /282|251.64 /11.11|30627 /31218|
| Tensor2 r4729,0.25/60s |353 /216 /116|364 /233 /141|14.38 /9.87|21177 /21866|

Ceaseless had no cached input initially. Existing operator online consent was
checked before two bounded public GETs: combined main board, then replay77.
No consent was manufactured/copied and no upload/top-up was requested. The
import's mapbuild matches the mounted Momentum BSP SHA1; input/digest/schema
receipts exclude player/name fields. No `.view` was invented. Its4337 samples
span-1.34..42.02s; the41.5s viewer window remains before the held finish.

These numbers replace the earlier *missing* Garden/Ceaseless rows, not historical
P1318 numbers by regrading. They do not imply every route, graphical preset or
later native version has these lows. A600-average/300-low ratio can reflect
scene variation; Ceaseless shows why rare long frames and0.1% tails also matter.

## Causal diagnostic controls (not proposed quality settings)

Separate12s moving replay sections, same seek across four arms: normal2x,
quarter-pixels1x, sky-ray-disabled2x, normal2x again. All other measured knobs,
recording/camera and workload remain fixed. Native traces positively advance.
Quarter pixels means changing render scale2->1, not changing output resolution.
Disabling `vbsp_sprite_skyrays` changes visibility semantics and is **diagnostic
only**, not an acceptable exact optimization. The normal64-ray budget is restored.

| Section | Normal first/repeat average,1% FPS | Quarter pixels average,1% | No sky rays average,1% |
|---|---:|---:|---:|
| Boreas0.25..12.25s |426,240 /436,255|445,285|423,256|
| Demise12..24s |420,274 /417,272|516,339|419,288|
| Garden70..82s |482,225 /484,220|583,310|481,236|
| Tensor2 0.25..12.25s |381,240 /386,243|387,251|722,428|

### Tensor2: persistent CPU floor, not just first-use shaders

Quartering pixel load barely changes throughput, while the sky-ray ablation
nearly doubles it in this section. The same8s/100fps diagnostic reports
Sprite_SkyTest1.127606s inclusive, SkyTick1.164283s, UpdateView2.152706s. These
are aggregate profiled seconds, **not calls or unprofiled per-frame timings**;
do not add nested inclusive times. The earlier P1351 split in
`p1351-pacing-results.md` already assigns97.3% of SkyTest inclusive cost to
native eye trace/result publication rather than QC prefix work.

Path: `cl_sprites.qc:Sprite_SkyTest/SkyTick` ->
`pr_csqc.c:PF_cs_traceline` -> `World_Move` + `cs_settracevars`.
World_Move includes dynamic solid/portal and packet BSP entities; MOVE_NOMONSTERS
is NOT world-only. Native VBSP/BIH point clipping, packet broadphase and trace
output/string publication remain unseparated. The engine already has an exact
BIH trace cache; moving-eye rays need not hit it. A larger/looser cache, fewer
rays, discarded doors or reduced invalidation is not an exact fix.

Next discriminating measurement: native world/packet traversal versus result
publication, then matched unprofiled benefit with unchanged dynamic-solid,
portal, miss/surface-name and visibility witnesses. No speculative fix shipped.

### Garden / Demise: pixel load; Boreas: mixed

Garden's selected section gains about21% average FPS and38-41% in1% low when
pixel count is quartered. Trailing GPU time drops2.72-2.89->1.01ms; the normal
3D sky pass alone is0.95-1.13ms in those snapshots; transparent/effects work is
also substantial (0.83ms in the first normal snapshot). Sky-ray removal does not
materially raise average throughput. The Garden pool trial independently shows
3D sky remains dominant even when water capture work is reduced (1.17ms there).

Demise gains about23% average/24%1%-low with fewer pixels, not with sky-ray
removal; trailing GPU time is about1.87-2.37ms normal versus0.81ms reduced. World
rendering is the dominant GPU pass in the first normal snapshot (1.29ms); its
3D sky pass is0.00ms, so do not attribute Demise to Garden's skyroom.
Boreas has a smaller average response and a useful low-tail response, with world
and transparent/effects GPU passes about0.79/0.82ms in the first normal snapshot.
Lowering GPU load leaves a CPU/submission/CSQC floor, so neither a universal
shader-cache fix nor Tensor2's sky-ray target explains every map. These are
selected-scene/trailing snapshots, not an all-frame GPU-versus-CPU classification.

These controls identify work classes, not permission to turn down resolution,
remove the 3D sky, discard map details or call a lower-quality preset a patch.

### Ceaseless: a separate first-traversal render hitch

First traversal contains43.27,181.03 and251.64ms frames near replay11-12s.
The engine phase breadcrumb assigns251.475ms of the251.590ms host frame to
`gfx`, with negligible worker/input/protocol time. The late-compile counter
through first completion is only12/4.151ms and does not rise on repeat, so that
measured compile work cannot account for the quarter-second hitch. This does
NOT exclude deferred driver first-draw work, allocation/upload, replay/CSQC work
inside gfx, or host scheduling; the exact substage is not yet isolated.

Repeat improves1%235->419 and0.1%44->282FPS, but still has11.11ms worst. The
trailing budget is CPU-bound with substantial client-QC cost; it describes the
end of the window, not the stalled frame. The additional seek10.25 diagnostic
refused4096MiB/60s quiet admission (about3768-3979MiB available) before any native
launch. Preserve that refusal; no synthetic noclip data substitutes for this
normal replay. BACKLOG retains the specific first-use phase-split falsifier.

## Garden bonus1: adaptive water experiment rejected for promotion

Prototype source: existing P1351 backend/renderer plus non-archived
`r_captureearlydistance`, default0. At explicit nominal20 and threshold8, squared
camera displacement from the last real capture can request an earlier refresh,
but not before the existing nominal60 minimum age12.5ms. Existing Source/owner/
plane/entity/seat/view/FBO/frame/texture guards remain; rotation correction still
removes translation. This is a cheap motion heuristic, **not parallax correction**
or pixel/depth-accurate water/scene attachment. Pure rotation does not enable the
new early-motion condition. There is no new GPU readback or depth system.

Build via existing `src/build.ps1 -Engine -NoDeploy -Jobs 8 -FteRoot <owned engine>`
passes with zero NEW warnings (existing engine warnings retained). Actual-C
controls atO0/O2 pass; killed mutations prove early refresh, age floor and nominal60
isolation acted. Compile database regenerated; LSP diagnostics were requested,
with no diagnostics recorded (not a runtime/physics/visual pass).

The corrected Garden b1 camera-only fixture uses shipped `zone_goto 11 0 20`,
body(-15920,1440,4608), eye about4672, noclip390u/s (`pm_noclipspeed 1.5`).
Timed path is2s left/4s right/2s left, three cycles per arm, with a zone reset and
settling before each. All reported body/slow-frame positions remain inside the
pool-room bounds; voidscene checks are inactive. This is **not a running/recording
live-player qualification**. Timer/start walking preflight hit the ledge; it is
not relabelled a recorder pass. No owner appearance/alignment acceptance exists.

Order: still60, still20/adaptive, move60-A, move20/adaptive-A, move20/plain-A,
move20/plain-B, move20/adaptive-B, move60-B. Full water mode2; same experimental
binary and normal QC throughout. Logging/profiling off inside measured windows.

| Moving24s arm | Average FPS |1% low FPS|0.1% low FPS|CPU capture self ms/main view*|
|---|---:|---:|---:|---:|
| nominal60 A / B |480 /470|265 /266|183 /200|0.078 /0.082|
| nominal20 adaptive8 A / B |479 /475|275 /269|205 /193|0.049 /0.050|
| nominal20 plain A / B |480 /480|286 /281|216 /223|0.027 /0.027|

*Reflection+refraction self time from the full-window native view counters,
not all host CPU work. Approximate depth1 counts are consistent with about75,
45 and26 capture-pairs/s respectively, **not literal60/20Hz**. Current scheduler
eligibility is0.75/rate; rounded view counters are not exact cadence telemetry.
Stationary60/adaptive20 gives484/485FPS and identical276FPS1% lows. Trailing
GPU times stay about2.0ms while capture CPU work falls: the tiny capture saving
does not remove the scene's dominant GPU work. Moving average differences lie
inside the observed normal60 A/B spread; there is no demonstrated meaningful
end-to-end win. Lower capture count alone fails the user's acceptance condition.
Thus **do not promote/enable/deploy this prototype or claim parallax was fixed**.

The initial1040u/s sideways fixture crossed the room into void and did not reset
between arms. Its high capture counts/throughput are preserved but rejected as
an in-room comparison. A single global capture owner can conservatively invalidate
when fallback draws competing planes/target writers; that explains a plausible
failure mechanism, not a proven per-frame causal join. The corrected arm fixes
the actual path seam rather than bypassing a failed product transaction.

A separate native control shows a roughly19.8-degree camera turn; it is not
visual acceptance or proof the turn returned exactly to its starting angle.
Because the performance gate is unmet, no owner visual acceptance is requested
for an unpromoted candidate. A later approach must first beat nominal60 at the
same appearance, then obtain a small fixed-aim pool-edge sideways check.

## Preserved failures, remaining work and delivery

- First Boreas admission and corrected-water admission refused RAM; same-case
  actor-free retries retained the original refusals and reapplied the full gate.
- Initial Tensor2 route rejected a competing native actor at post-check. Original
  dumps remain rejected; `quiet-host` remeasurement changes the actual host premise
  and independently passes the same gate/actor checks. No failed evidence regraded.
- Native read-only review confirms plausible collision/trace-publication and
  conservative capture-owner invalidation paths, not unmeasured speed claims.
- Only this diagnosis/documentation is published. Optional engine source/binary,
  commands, hashes, failed/accepted dumps and cleanup/retention state remain under
  the owned root, recorded in its OWNER/checkpoint. No unrelated working-tree or
  installed owner state, online consent, fleet actor, config or data was changed.
- Remaining: exact Ceaseless stalled gfx substage; native Tensor2 trace-stage split
  and an exact-semantic optimization; visually aligned lower-rate water that
  demonstrably beats60. Existing strict pre-run closure/barrier work stays partial.
