# P690 — conservative plane refinement (OpenGL, opt-in)

## Scope and settings

Only `r_blendsort 2` is refined. Modes 0/1 and default **1** stay unchanged.
No QC Build, public release version, Linux fleet or updater-feed change.
P685's per-face collector remains the fallback. Intersecting/coplanar geometry,
recursive captures, dynamic entities and uncertain CPU geometry are not promised
correct by this patch. Source envmap/model-lighting drafts are excluded.

Enable with `r_blendsort 2`; compare `r_blendsort 1` at the same fixed camera.
Leave other settings unchanged. `r_temporalscenecache` need not be globally off.

## Implementation contract

Eligible static identity-world faces in the blend-sort bucket must have finite,
bounded, planar CPU vertices/valid indices, no material programs and the standard
perspective projection. This is not a conventional-alpha-blend-factor gate.
Disjoint projected bounds remain unconstrained; certified separated-plane proofs
supply edges. Unknown overlapping admitted pairs retain centre-depth baseline
edges. Stable bounded topological ordering rejects cycles atomically; any proposed
move crossing an unsupported record's slot also abstains atomically. Dynamic,
deformed, oversized and CPU-unavailable records are not admitted. Weapon/depthhack
and recursion-safe capture behavior remain P685's. The per-face caps of 64
vertices/192 indices exclude that record and protect its slot; other admitted
faces may still move without crossing it. Exceeding 128 admitted faces, 2,048
admitted vertices or 65,536 pair-work units atomically retains the entire centre-
depth collector order. Limits do not create new coarse commands or bound the
complete collector/admission scan.

## Portable falsifiers (engine repository)

```sh
python tools/test_gl_blend_faces.py --output <owned-artifact-dir>/faces
python tools/test_gl_blend_planes.py --output <owned-artifact-dir>/planes
```

Both compile exact extracted production C, not a Python sorter simulation.
Normal and HEXEN2 variants, with and without `-ffast-math`, use C99
`-Wall -Wextra -Werror`. Keep Python assertions enabled. Plane tests reject
Python `-O` before running. Eight plane mutants must successfully compile and
then fail assertions. Their logs distinguish an acted failure from a broken build:

- plane ordering disabled or reversed;
- ineligible-record ordering barrier removed;
- unknown-pair fallback edge removed;
- orthographic admission guard removed;
- material-program and vertex-program admission guards weakened independently;
- external-projection admission guard removed.

Separate asserted arms cover dynamic/deformed/nonplanar geometry, atomic
face/vertex/work budgets, coplanar/intersecting faces and a real triangle cycle.

Frozen `tools/blend_plane_fixtures.inc` contains Kitsune window vertices/indices.
The existing collector falsifiers retain cached-VBO, scenetris-depth and NaN arms.
Dynamic-barrier and unknown overlapping admitted-world-pair collector assertions
were observed failing on pre-fix source before fixing either defect. The latter
uses three CPU-available faces with an unproven intersecting pair; it is not the
cached-VBO/CPU-unavailable regression.

## Retained native controls and honest limits

Owned evidence root: `C:/FTESurf-worktrees/mapvisual-01a13061/`.
Reviewed prepublication candidate base: engine `b4a2d220409803a049e4b9850a589f490774c1bd`.
The four production/test files were hash-bound to the v3 evidence below:

| File | SHA-256 |
|---|---|
| engine/gl/gl_backend.c | c614650d462518d6369e4b1f75a1a4aee84f631804704220be096e4e7fb09c4b |
| tools/test_gl_blend_faces.py | 47f08151d8215e6497d18969591b759ef038835c2fe4e87cd2eed40f432328d8 |
| tools/test_gl_blend_planes.py | abe0b74f20904bff1834c0120972a9fdb95ba0ead747e25cf01775b12df94f0d |
| tools/blend_plane_fixtures.inc | 7ec908da9a5849c41d88285eeb89c7fd9e2ff2a66c24c25d91ea93db3be51534 |

`artifacts/plane-acceptance-20261013/v3-source-attestation.json` is authoritative
for those inputs; hashes will be checked again during publication.
`grade_acceptance.py` re-grades the retained native PNG/capture controls. It keeps
failed/unstable arms distinct rather than treating them as passing evidence.

- `clamped-inputlocked-v3`: all 48 repeated Kitsune PNGs are exact; mode1 is
  byte-identical baseline/subject at all six yaws. Mode2 ACTS: 12,065 / 8,931 /
  12,277 / 12,016 / 16,900 / 15,244 changed pixels at yaws125.6/104.3/104.2/103.2/
  103.1/95. Frozen geometry/helper oracle proves order; changed pixels alone do
  not prove correctness. An earlier uncontrolled input run moved the camera and
  is excluded. Input lock and server aim/body/zero-velocity checks are required.
- `native-fixtures` and `native-followup-complete`: authored indexed BSP29 quads
  give wrong red-over-blue baseline centre(127,0,64), correct subject blue-over-
  red(64,0,127). Dynamic barrier baseline B,D,A centre(127,64,32) is kept by v3;
  old candidate A,D,B centre(32,64,127) fails. Removing the actual green brush
  allows correction again. Three admitted world faces with an unknown intersecting
  pair similarly preserve correct green-over-red(64,127,0), unlike the old
  candidate(127,64,0). Top and pass-local programmable alpha fixtures ACT and
  remain exact baseline in v3. Fixed-function deformation mode2 remains exact.
  These are not arbitrary model/sprite/weapon native certification.
- Q1 cache1 is separately attributed to v2 `6a0f0414` (`native-fixtures`):
  wanted1/inuse1 and stale MarkLeaves16..21s prove actual cache use. Admission
  guards are unchanged in v3, but this is not a fresh v3 or Source-cache1 test.
- `water-v3`: actual Source bhop_monster_jam, cache0, Full1 -> Dither3 -> Full-
  return1. Full is `vmt/water#LQWATER#DEPTH`/6 merged passes; Dither is
  `vmt/flatdither#WATER`/1 pass. All repeats and Full-return are exact; mode1vs2
  images exactly match per setting/arm. Full/Dither differ in 431,672 pixels.
  Cross-binary difference is 1,501 PNG-visible Air-HUD pixels: documented
  post-triage mask x91..292,y335..352 leaves zero other changes. No Source
  `r_waterinfo` call (pre-existing crash), cache1 or cube/portal runtime claim.
- `native-cost-v3`: warmup + three256-frame samples per mode/arm, A/B/A means
  mode1 0.619105/0.624758/0.628283 ms; mode2 0.674844/0.695402/0.668383 ms.
  Baseline-return stays within20%; candidate increment is below0.5ms. This
  timerefresh/explicit-finish gate is not ordinary vsync/refresh frame time.
- `mode1-triage`: the SAME unchanged baseline executable produces both legacy
  batch orders on return (20,402 changed pixels), while candidate matches the
  initial baseline in cold/flush1/flush2. Existing mode1 interbatch instability
  is recorded, not repaired. Initial Q1 cross-binary mode1 differences are not
  default-parity evidence; the exact Kitsune controls above supply that evidence.

Remaining unmeasured scope: hardware tessellation, external-projection runtime,
arbitrary model/sprite/weapon native certification and broad all-map/GPU/perf
coverage. Portable rejection/submission guards are not a substitute for GPU tests.

No owner game/process, config, player data or canonical native file was retained
modified by those acceptance runs. Process stops, restored hashes and guard
manifests are retained beside the runs.

## Publication gates

Latest isolated integration base: engine P688 `73322dff5`, QC `13972d9`.
Canonical source trees contain peer edits and are not build/deploy inputs.
Final engine source: `7598b4c4d454db73774fdbc7ebea27ec45a9dba1`, tag `patch-690`.

Number collision: sorter `b59026cc2` was initially pushed under P689, while the
native-recovery session independently created `c325d045`/`patch-689` during the
long builds. Our tag-creation failed, but the following push wrongly exported
that pre-existing peer tag. The operator was notified immediately. No tag or
history is deleted/rewritten: forward metadata-only `7598b4c4d` assigns this
sorter P690. Its production/test bytes are unchanged; the final bundle below
is rebuilt with the exact `git-690-7598b4c4d...` stamp. Peer recovery code is not
in this tree or bundle. Do not use `patch-689` as the sorter source pin.
The first unpublished metadata draft mixed historical native measurements and
misstated graph scope. Independent review blocked that prose; all four findings
were corrected against the authoritative v3 checkpoint/grader. Bounded re-review
is OK with notes; its remaining per-face-cap versus whole-stage-budget distinction
is also corrected above. No new demonstrated sorter defect required a source fix.
The final exact-commit bundle was rebuilt after both metadata corrections.

Fresh clean P688/P690 full client/server/five-plugin builds both have **74 compiler
warning occurrences / 45 distinct message payloads**, zero new or missing payloads,
**349** Make grouped-target warnings, and three QC zero-warning summaries (426
warning-containing lines total). No bare “zero warnings” native claim. First build
attempt rejected the MSYS-Git autocrlf false dirty status; fixed adapter explicitly
uses Git-for-Windows. Fresh native outputs are bound by `candidate-native/hashes.json`
and `provenance.json`, never by a timestamp or the ENGINE.txt pin alone.

`artifacts/plane-delivery-20261013/native_station.py` compares clean P688 and final
P690 bundles on the owned subject, dedicated port27620. All48 repeats are exact;
all six mode1 fullframe images exactly match. Mode2 ACTED counts are again
12,065/8,931/12,277/12,016/16,900/15,244, reproducing the v3 results exactly. Runtime
`version` reports each expected full commit stamp, measured settings are explicit,
and server origin/angles/zero velocity are checked before every shot. Initial
parser setup expected “setpos” while conbridge info returns “origin ... angles”;
that arm stopped/restored and is excluded. Both valid pairs stop rc0, config/data/
top-level guards are unchanged, all eight subject native files are hash-restored,
and canonical install clients remain unchanged. Inherited water/cache/program/cost
arms remain separately attributed above; they are not relabelled final-P688 reruns.

Exact final native hashes:

| Output | SHA-256 |
|---|---|
| fteqw64.exe | 5a86d84815c4d22d1d0a6c14535b283ae99682dd0fa1005e255dd5232f5368b2 |
| fteqwsv64.exe | 06cb4cd3ec062357028fe75ed4cd402a2facd7458720d6a08e269e402c8404e6 |
| fteplug_hl2_x64.dll | 756ced495885be6ec7e47dcb67f773671bd214e8e47c96dbcd70a50de2e51d75 |
| fteplug_cod_x64.dll | 658b48138d7fc5fc0fe37e29747e752c5ad1f222c157ede167a61b0e27b55abc |
| fteplug_box3d_x64.dll | 4661d6d4c0f5206c42411730c2f1c1a30baae4c8ed04bca3b039996f6d5ec1c5 |
| fteplug_ode_x64.dll | 45a70b1553f75295282d135e505347631d73c0661ca31b69dcca8c5369bca6b0 |
| fteplug_ui_imgui_x64.dll | f02b0e1118cd5eef153ff04a5e6bdf39b5179efefbf594c4debd5e15b71d4615 |

**Windows delivery: pending/blocked.** Preflight found pre-existing native
clients and dedicated servers using the canonical installs after the owned
station had stopped. None was killed and no install binary/plugin/progs/config
was swapped. Stage the exact bundle only when both installs are free, preserving
`.prev`, verifying every destination hash and running each installed executable
against an owned guarded fixture. No Pi/fleet or signed updater-feed change.
A source commit/tag/pin is not proof that either installed executable runs P690.
