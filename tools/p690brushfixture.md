# P690 rotated inline-brush fixture — bounded zero-worker native PASS

The original worker-enabled gates below remain **REJECTED**, unchanged. A new,
separately frozen startup-controlled gate passes full-frame preservation/transfer
under `-noworkers`; see [the zero-worker result](#zero-worker-startup-follow-up--bounded-native-pass).
This does not repair/certify ordinary worker-enabled startup or promote default2.

A self-contained BSP29 fixture now binds a real production `func_wall` alpha
pane to yaw0/yaw45 images. Rotation and entity drawing ACTED. The initial
P688/merged/P688-return matrix **failed its mode1 control return**. A later
same-loaded-world experiment makes that return exact, but still fails cross-binary
mode1 parity. Neither matrix is accepted; the cause of the two legacy world orders
remains unknown. No engine/QC build, patch, default, install or deployment changed.
Mode2 observations below are measured subsets, not replacement gates.

## Reusable fixture tooling

```text
python -B tools/p690brushfixture.py --output <new-owned-directory>/fixture
python -B tools/test_p690brushfixture.py --output <new-owned-directory>/fixture-tests
```

Python3.10+, standard library only. Fresh operator-owned directories are required;
existing outputs are refused before payload writes. No launcher, BSP compiler,
asset downloads or install writes. Three resources plus a size/SHA256 manifest:

- maps/mv17_brush_yaw0.bsp and maps/mv17_brush_yaw45.bsp: identical geometry and
  materials, differing only in the func_wall entity's `angles` string. World
  black background x600, red half-alpha x256,y[-32,32],z[0,128], tilted blue
  x=128+y,y[-64,384],z[0,128]. Model*1 has one local quad at x0,y/z[-32,32],
  translated to(272,0,64), yaw0 or45. World/model surface/node ranges are separate.
- scripts/mv17-brush.shader: unprogrammed black/red/blue/green materials;
  colored panes use alpha.5/SRC_ALPHA/ONE_MINUS_SRC_ALPHA, cull disabled.

This deliberately minimal fixture has empty collision hulls and no external
textures/lightmaps. It is a renderer station, not a playable/collision-certified
map. Explicit noclip after each load is required to hold the body at origin0.
Production `src/server/sv_entities.qc:func_wall` loads the inline model via
setmodel and keeps the authored angles; no fixture QC or synthetic CSQC draw.

Four focused tests check lump bounds, local quad/inline-model/node/edge ranges,
angle-only entity difference, shader/determinism and acted collision refusal
with existing bytes unchanged. Normal and exact-committed `-O` tests pass and
emit byte-identical resources. These format tests are NOT native acceptance.

## Frozen native capture

Evidence retained at
`C:/FTESurf-worktrees/mapvisual-01a13061/artifacts/brush-overlap-20261013/`.
PREDICTIONS.md/capture.py/generator/helpers/fixtures and the original grader were
frozen BEFORE launch. Retained bundle pins reuse [p690cache.py](p690cache.py):
production P68873322dff5b6898511d62ed775286b23a91b8aad0 and delivered
mergeda8e705787fad1b60661da5e8dd43c9138cc69b1b. No diagnostic executable.

One BLOCKING/serialized capture: P688 yaw0,yaw45; merged yaw0,yaw45; P688-return
 yaw0,yaw45. Six real dedicated socket/client pairs,48 full960x720 PNGs/36 states,
about six minutes. No concurrent parent/child tests/builds/analysis/corpus work,
no native retry or timing matrix. Owner/peer processes were not stopped; this
is not OS-wide isolation.

Each angle/mode records entity-on twice, entity-off, entity-return. Runtime
version/native hashes, loaded `*1:<map>` batch with one mv17_green surface and
r_shaderpasses sort11/no-program/ordinary-alpha bits bind the real actor.
Body/aim0, velocity0 and correct-world timer are recorded with explicit GL/cache0,
quiet HUD, FOV100/sRGB0/render-scale2/fullbright1/viewmodel0. No mask, tolerance,
trim, shader-time freeze or rendered-eye/sorter-admission diagnostic is claimed.
Hashes are local capture receipts, not cryptographic execution attestation.

## What acted, and what failed

Every within-boot ON repeat and entity-return is fullframe exact. OFF images
have no green; visible ON green footprint is:

| Actor angle | Green pixels | Bounds | Size |
|---|---:|---|---|
| yaw0 | 9,216 | [432,312,527,407] | 96x96 |
| yaw45 | 6,532 | [443,308,510,411] | 68x104 |

The projected shape changes in every production arm. Mode2 yaw0/yaw45 ON images
change3,150pixels, and corresponding OFF images are exact across the two maps.
This proves visible transform action; it does not measure internal eligibility.

| Fullframe comparison, both ON and OFF unless specified | yaw0 | yaw45 |
|---|---:|---:|
| Mode1 P688 initial vs P688-return | 0 | **20,604** |
| Mode1 P688 initial vs merged | 0 | **20,604** |
| Mode2 P688 initial vs P688-return | 0 | 0 |
| Mode2 P688 vs merged, brush ON | 0 | 0 |
| Mode2 P688 vs merged, brush OFF | **20,604** | **20,604** |

The yaw45 mode1 initial P688 and its return differ over the entire red/blue
intersection [429,259,530,460], including with the brush OFF. P688 mode1 OFF
also changes20,604pixels across the two yaw-map boots; merged and P688-return
mode1 OFF do not. Direct PNG inspection shows two world-pane blend orders.
Thus the frozen angle-only world-parity and baseline-return premises failed.
A legacy mode1 interbatch-order variation was observed previously too, but this
capture alone does not identify its root cause or establish a candidate bug.

Mode2 ON preserves the inherited P688 image at both angles. OFF changes20,604
pixels in merged, demonstrating the existing world-plane correction ACTED.
Merged mode2's ON/OFF delta includes world reordering, **not just brush area**.
Neither inherited ordering correctness nor the internal fallback reason was
measured. No default2 promotion or all-brush/model/GPU/performance claim.

The original frozen grade_native.py still rejects under normal and `-O` and
remains unchanged. Its empty failed stdout files are not accepted JSON reports.
A separately authored post-capture report_native.py checks source/state/image/
closure and enumerates all nine failed frozen predicates; normal/`-O` diagnostics
are byte-identical and explicitly say **REJECTED**, not PASS. Four in-memory
controls add their own onepixel repeat, onepixel control-return, absent-green
and collapsed-yaw violations; they cannot pass merely because the native matrix
already has other failures. Native files/manifests were never mutated.

All twelve owned processes quitrc0; native8,1,223 protected fixture files and
both canonical client hashes restore/remain unchanged. Three staged resources
and the newly created maps directory return to absent. Unique source/protocol/
raw/PNG/failure/diagnostic/exact-commit receipts retained; only inventoried
current-created byte-identical backup/log duplicates may retire. Parent source
review only; no independent verdict is claimed.

## Same-loaded-world follow-up: return stabilized, default parity still rejected

Retained evidence: `artifacts/brush-sameworld-20261013/` and separately versioned
`artifacts/brush-sameworld-v2-20261013/` beneath the owned root above. The first
54PNG attempt stopped/restored successfully but its checker rejected BEFORE
pixels: inherited helper `Capture.__init__` recorded the helper's `__file__` hash
as `driver_sha256`, not the subclass driver's hash. Original source/manifest/
protocol/rejection remains unchanged and ungraded. V2 explicitly pins both
subclass driver and inherited helper, with real-constructor/mock-helper-init and
wrong-driver negative controls BEFORE launch. No captured manifest was repaired.

Existing engine `poke_ssqc` supports numeric entity.field reads and vector
assignment; no new diagnostic command or QC is needed. In an owned cheats-enabled
server, discover the authored targetname, then read classname/model/targetname/
origin/angles/avelocity before writing ONLY the verified actor's angles:

```text
poke_ssqc <verified-pane-edict>.angles = '0 45 0'
poke_ssqc <verified-pane-edict>.angles
```

Do NOT assume an edict number or dump private/player fields. Here a bounded1..96
targetname-only search found one `mv17_pane`, edict4 in each boot. Readbacks prove
func_wall/model*1/origin272,0,64/avelocity0 and angles0/45/0. Each reply has a fresh
end ticket and complete since-send raw receipt. One yaw0 map per boot stays loaded;
NO map reload between angles. Mode1 then2 each capture ON repeats/OFF at angles
0/45/0-return, then final mode1 ON/OFF return:54 full960x720 PNGs/42states from
serialized exact P688/merged/P688-return, not a timing or diagnostic-binary run.

| V2 exact fullframe comparison | Changed pixels |
|---|---:|
| Within-boot ON repeats and angle/mode returns | 0 |
| Angle0 vs45, ON / OFF, every arm and mode | 3,150 / 0 |
| P688 initial vs P688-return, all18 matching PNGs | **0** |
| P688 vs merged, mode1 all10 matching PNGs | **20,604** |
| P688 vs merged, mode2 ON all5 matching PNGs | 0 |
| P688 vs merged, mode2 OFF all3 matching PNGs | **20,604** |

The green footprints remain exactly9,216/[432,312,527,407]/96x96 at0 and
6,532/[443,308,510,411]/68x104 at45. The stable P688 mode1 world-only centre is
(64,0,127); merged is(127,0,64). Thus same-world angle action and P688 return now
hold, but mode1 cross-binary preservation still does NOT. Do not infer a P690
mode1 code defect: the cause of the batch-order difference is not established.

The frozen V2 gate remains unchanged and rejects under normal/-O. Its native
mode1 onepixel control is hidden by an existing failure on that comparison, so
it cannot prove a NEW specific failure. A separately authored rejection report
validates source/state/closure and enumerates13 failed frozen predicates:10
mode1 comparisons plus3 merged-mode2 pane-only ON/OFF checks. The latter was an
incorrect protocol premise: removing a barrier permits world reordering outside
the pane, as already documented above; it is NOT a newly found product defect.
Do not silently weaken that frozen gate. Six other planned native defect controls
add specific failures; the hidden mode1 control remains explicitly UNPROVED.
Synthetic all54-image positives and all seven specific controls pass normal/-O,
including missing-matrix/within-boot-return and source-attribution controls; that
is checker coverage, not accepted native evidence. Diagnostic reports/crops are
labelled REJECTED, never a substitute gate or masked acceptance.

Source lead ONLY: `Mod_ResortShaders` in engine/gl/gl_model.c prepends old batches
into emptied buckets, reversing unchanged-key lists when called.
`Shader_DoReload` invokes it if any live shader sort changes. Those call sites
have NOT been observed/count-bound in these runs; neither causation nor a fix is
proved. `mod_batchlist` calls `Shader_GetShaderBody`, which can reparse shaders;
do not assume it is an inert order probe. Material inspection here ran AFTER all
pixel states. Source diff at exact P688/merged refs leaves gl_model.c/r_surf.c and
the mode1 submission branch unchanged; static reachability is not native parity.

Both attempts' twelve owned processes quitrc0; original native8,1,223 protected
fixture/config/data/content files and two canonical clients are restored/unchanged.
The two staged resources and created maps directory return to absent. Unique
source/protocol/raw/108PNGs/failures/receipts retained. Parent review only.

## Passive batch-order/lifecycle follow-up — transfer REJECTED

A separately frozen five-boot capture binds raw loaded batches and real reload/
resort events without Shader_GetShaderBody or mod_batchlist. Minimal m-rel
P68873322dff/mergeda8e705787 diagnostic clients use an identical65-line additive
observer. Bounded static receipts record reload reasons, sort changes and list
order before/after actual resorts; the sampler only reads loaded fixture fields.
No reparse, remap, pointer write or forced resort. Exact source/stamps/patches/
binaries/compiler commands/raw/PNGs are retained, not deployed.

The55-PNG production-P688/diagnostic-P688/production-merged/diagnostic-merged/
production-P688-return matrix has valid source/state/fixture/closure receipts:

- Both diagnostic boots have exact observerOFF/ON/OFF fullframe parity. Samples
  1..8 ACT with zero overflow; order/events stay unchanged through yaw0/45/0 and
  mode1/2/1. All11 production P688 returns are exact.
- Diagnostic P688: CL_ParseServerData/ca_active reload changes red/blue/green
  sort5->11. One actual resort reverses old bucket5 blue/red/black into bucket11
  red/blue plus opaque black. Final mode1 intersection is(64,0,127).
- Diagnostic merged: no sort changes or resorts. Final bucket11 blue/red gives
  mode1 intersection(127,0,64). These are observed diagnostic lifecycle records,
  not merely the earlier source-only prepend suspicion.
- Nevertheless, EACH diagnostic's nine mode1 images differs20,604pixels from
  its own production capture; both mode2 images are exact. The frozen gate is
  **REJECTED with18 diagnostic-production transfer failures**. Within-boot
  observer parity/exact P688 return cannot rescue it. Identical observer source
  does not imply identical load lifecycle or prove boot-time nonperturbation.
- Normal/`-O` grades give byte-identical valid JSON with all18 failures. Native
  in-memory observer-onepixel/source/overflow/footer/missing-material controls
  add NEW specific failures on holding predicates; original raw/PNGs unchanged.
  No older rejected protocol/manifest/gate was rewritten.

Builds each have37 inherited compiler warnings/zero NEW; all222 Make grouped-
target warnings are retained separately. The first build checker mixed the two
categories and failed; original source/log/failure retained. Shared dependency-
cache hashes unchanged. Recorder306/0 and canonical corpus/reader/count/fault
aggregates unchanged. All five owned client/server pairs quitrc0; native8,
protected1223/install2 and absent fixture targets/directories restore. Parent
review only; no engine/product/default/deployment/performance acceptance.

## Zero-worker startup follow-up — bounded native PASS

Evidence: `artifacts/brush-workers-20261014/` under the owned root above. One
BLOCKING serialized six-boot attempt reuses the exact retained production and
passive-diagnostic binaries; no rebuild, source/default modification or deployment.
Boot order: default-worker P688 positive control (no PNG), production P688,
diagnostic P688, production merged, diagnostic merged, production P688 return.
The five measured arms use `-noworkers` on BOTH processes before initialization.
Cache0,960x720 GL, fullbright1, identical world/camera/HUD/cadence controls remain
explicit. Unique BEGIN/END tickets, raw hashes, actual MATCH cl/sv wait targets,
nonreused receipt identities and ordered observer/state/PNG phase intervals bind
worker readings to the correct process and phase. Cvar intent alone cannot pass.

- Positive control: BOTH client/server report4 live workers,0 pending loader tasks.
  Every one of210 measured-arm worker receipts reports worker_count0,live0,pending0
  (42 per arm);2 positive-control rows bring the total to212. Snapshots occur at
  boot, before every PNG/observer pair, and after the last PNG. `-noworkers` makes
  loader work synchronous, not absent; it does not empty/prove away WG_MAIN or
  all engine/driver threads.
- ALL55 PNGs pass the preregistered exact full-frame gates: production/diagnostic
  transfer at each state/mode, production P688 return, mode1 P688/merged
  preservation, within-boot repeat and observerOFF/ON/OFF noninterference,
  yaw0/45/0 return and mode2 ON parity. No pane mask, tolerance widening or
  mode2-only subset rescue. Actor4 retains authoritative func_wall/*1 identity;
  green footprints are9,216 pixels/[432,312,527,407] at yaw0 and6,532/
  [443,308,510,411] at yaw45 in each measured arm. Yaw changes3,150 pixels.
- Intentional mode2 OFF world correction still ACTS at20,604 pixels:
  P688 center(127,0,64), merged(64,0,127). Mode1 OFF center(64,0,127), ON
  (32,127,64) and mode2 ON(127,64,32) agree across all five arms. Removing the
  brush permits world reordering; no unsupported pane-only premise is revived.
- Both diagnostic boots now record activation sort5->11 for red/blue/green and
  exactly ONE actual resort. Old bucket5 blue/red/black becomes opaque black
  plus bucket11 red/blue; inline green remains independently bound. Each boot's
  eight passive samples has21 events/zero overflow, unchanged events/resort/order
  throughout yaw0/45/0 and mode1/2/1. These traces match production pixels here;
  they do NOT prove the exact registration timing of uninstrumented production.
- Frozen grade and in-memory negative replay both exit0 normally and under `-O`,
  with byte-identical JSON,zero violations,4 NEW-specific pixel defect controls
  and a36-control native semantic replay (including those four). These reject
  missing/live/pending worker states, wrong receipt sides/reuse/phase, source
  mismatch and
  observer overflow/footer/missing material without changing native evidence.
  Synthetic gates and real conbridge-argparse/native-stub safety regressions
  also pass normally/`-O`. Preflight corrected a split `--server-args` parsing
  bug, fail-open port query and receipt-side/phase reuse BEFORE freeze/launch.
- All six owned client/server pairs quitrc0. Native8,protected1,223 files,two
  canonical clients and absent fixture targets/directories restore. Recorder306/0;
  corpus/reader digests and counts/faults unchanged (273 recordings,91 sidecars,
  inherited168/5 faulted files,176 messages). No new compiler/build claim.
  Source scout completed; review timed out with useful partial findings, fixed
  and tested by parent before freeze. Final correction/result review is parent-only.

This is a NEW bounded result, not a rescue of previous rejected protocols or
proof that workers alone cause their failures. Extra status-ticket cadence and
positive-control warmup also differ; only one fixed zero-worker sequence ran.
No force-resort/reparse/flush, retry selection or observed subset acceptance.
The existing ordinary worker-enabled mode1 boot-order confound remains OPEN.

## Matched-cadence worker-enabled control — native REJECTED

A second NEW preregistered six-boot capture (`artifacts/brush-workers-enabled-20261014/`)
uses the same exact binaries, warmup, phase/ticket/sleep/PNG cadence and gates,
omitting only the worker-disable flags and using fresh bridge/PNG names. One
fixed attempt, not retry selection. All212 client/server receipts show default
empty-auto worker_count,4 live workers,0 pending loader tasks. All55 state/PNG
and16 observer samples have valid source/actual-side/phase/closure receipts.

The unchanged complete gate **REJECTS18 predicates**: nine merged production/
diagnostic mode1 transfers and nine production P688/merged mode1 comparisons,
each20,604 pixels. Merged production OFF center(127,0,64), ON(64,127,32),
versus its diagnostic/P688 OFF(64,0,127), ON(32,127,64). All11 P688 returns,
within-boot repeats/observer parity, yaw returns and both mode2 transfers are
exact; world correction still acts20,604. Both diagnostics AGAIN report one
activation resort, sort5->11 and final red/blue order,21 events/eight stable
samples. That cannot be assigned to the mismatching uninstrumented production.

Normal/`-O` full grades exit1 with byte-identical VALID JSON retaining all18
failures. Four native pixel controls add NEW SPECIFIC failures despite existing
rejections; the44-control native replay exits0 normally/`-O` with all original
failures preserved. Synthetic/real-argparse/native-stub controls pass normal/-O.
All six owned pairs quitrc0; native8/protected1,223/install2 and fixture absence
restore. Canonical corpus/reader/fault aggregates remain unchanged. No failed
stdout was relabelled accepted JSON and neither frozen batch was rewritten.

Across the two batches, ONLY merged production's nine mode1 images differ
(20,604pixels each); the other46 images are exact. This is a diagnostic cross-
batch observation, not a new acceptance subset. Matching cadence/warmup did not
remove the enabled-worker failure in this run. Worker configuration is implicated,
not proved the sole cause: batches ran zero-then-enabled, not randomized/time-
aligned, and no uninstrumented production lifecycle trace is available.

## Next gate

At Mod_ResortShaders/Shader_DoReload and legacy GLBE_SubmitMeshes sortlist order,
isolate actual worker-enabled registration/rescan sequencing without perturbing
production. Matched ticket cadence/warmup is now tested, not an outstanding
prerequisite; exact uninstrumented production/diagnostic/P688-return pixels still
must pass. Stable rebucketing remains a separate possible product investigation,
not a proved fix or permission to force resort during preservation testing.
Do not widen the gate or hide a native defect control behind existing rejection.
Broader animated/oriented/lit sprites, alias/studio models, weapons/depthhack,
portal/reflection captures and moving/time-aligned ordinary service/tails remain
OPEN; r_blendsort default stays1.
See [the completed billboard lane](p690spritefixture.md) and
[quiet ordinary scope](p690ordinary.md).
