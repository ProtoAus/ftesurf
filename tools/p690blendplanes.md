# P690 — conservative plane refinement (OpenGL, opt-in)

## Scope and settings

Only `r_blendsort 2` is refined. Modes 0/1 and default **1** stay unchanged.
No QC Build, public release version, Linux fleet or updater-feed change.
P685's per-face collector remains the fallback. Intersecting/coplanar geometry,
recursive captures, dynamic entities and uncertain CPU geometry are not promised
correct by this patch. Source envmap/model-lighting drafts are excluded.

Enable with `r_blendsort 2`; compare `r_blendsort 1` at the same fixed camera.
Leave other settings unchanged. `r_temporalscenecache` need not be globally off.
On the delivered Source loader, selecting cache1 does **not** activate the temporal
cache; see the reachability controls below. Static world VBOs are a different path.

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

**Initial sorter-only publication: Windows delivery was blocked.** Preflight
found pre-existing clients/servers in both canonical installs after the owned
station stopped. None was killed and that arm swapped nothing. The historical
7598 bundle above was not deployed. The later merged delivery below resolves
this blocker without removing P689 recovery from the integrated runtime.
A source commit/tag/pin alone remains insufficient proof of installed behavior.

## Merged P689+P690 Windows delivery — 2026-10-13

Built source: `a8e705787fad1b60661da5e8dd43c9138cc69b1b`, tag
`patch-690-with-p689`, full executable stamp
`git-690-a8e705787fad1b60661da5e8dd43c9138cc69b1b`. The four sorter/test files remain
byte-identical to accepted P690; `qkupdate.c` is identical to accepted P689
`c325d045`. Engine main `9c7737643` adds only P691 documentation after this
integrated source. No uncommitted canonical source was used. Cold build used QC
`8a14c577` only as the build driver; its generated progs were NOT deployed here.

Evidence: `artifacts/plane-merged-20261013/` below the owned root above.
`source-attestation.json`, `bundle.json` and the complete cold `native-build.txt`
bind inputs/outputs. Both executables carry the exact full stamp. DLLs do not
embed that stamp: their provenance is the cold compilation/header input plus
output hash, not a claimed version string.

Native warning payloads still match clean P688/P690 exactly: **74 occurrences /
45 distinct payloads**, plus **349** Make grouped-target warnings. A build setup
mistake copied the ODE0.16.5 tar without preserving mtime and triggered a rebuild
in the shared dependency cache. That cache was therefore **not read-only**;
1,041 additional ODE dependency warnings/13 payloads bring the full compiler
count to **1,115**. `warnings-triage.json` attributes every added payload/file;
parallel plugin compilation makes contiguous log-range subtraction incorrect.
No cache restoration/deletion was attempted. Three QC programs compiled at zero
warnings, but were only staged. The unsupported build parameter, attribution,
DLL-stamp and wrong signed-fixture setup failures are retained and excluded.

Fresh actual-C collector/plane gates and all 11 compile-and-act mutants pass.
The merged client passes all eight signed Windows cold-recovery controls in
`recovery-02/result.json`, using the exact published fixture hash
`366a1d6b88dd562de2acce643d18288f8370dcf1f1a3225e35534df590be0368`.
The positive case reports `NATIVE_RECOVERY_ACTED`; intervention/journal refusal
cases preserve honest state. This is not live HTTPS/planner, ACL or crash-safe
journal certification.

`native-station/results.json`: fresh P688 versus integrated runtime, 48 exact
repeats, six fullframe mode1 comparisons all zero. Mode2 ACTED counts reproduce
12,065/8,931/12,277/12,016/16,900/15,244 exactly. Full commit/version and explicit
settings/body/aim/zero velocity are checked; all eight subject native files are
hash-restored and both bridge-owned runtimes stop rc0. Earlier native water,
cache, authored geometry/program and timing arms remain attributed to their
original builds above, not relabelled as new merged reruns.

### Installed native set and live smoke

At **2026-10-13 11:10:45 UTC**, `windows-deployment.json` records 13 verified
native destinations: FTESurf client plus five DLLs; FTEQuake client/server plus
five DLLs. This expands the stock build script's FTESurf DLL set (hl2/ui_imgui)
to refresh its three existing physics/content DLLs as well. Every predecessor
was backed up before the first live replacement. Every `.prev` and immutable
`native-rollback/` file matches the predecessor hash. Canonical process guards
ran before swaps; no existing owner/peer process was stopped, including the
separate Desktop client. Configs, QC progs, player data and defaults were not
changed by this delivery; no Pi/Linux, feed, release or Build-number operation.

| Retained merged output | SHA-256 |
|---|---|
| fteqw64.exe (both installed clients) | aa1d9e1bc2f167520538bb24423c6e690081b943026186de79269d90b7944668 |
| fteqwsv64.exe | 5807ff1858ac0eca3796baf459dcc463f412f39c95aabd91647735da9b1eed3e |
| fteplug_hl2_x64.dll | 30857eb260b135c4b47a8b12dd22deb0e6f3513acb4246762b0a6a47e16bc1d9 |
| fteplug_cod_x64.dll | c1b6c146923e7ea58bb8bb79666cced1677b7fab8dda701344cf850eef4475c3 |
| fteplug_box3d_x64.dll | 845f113db7770a968f6823944a5e159e805c0ba80a1de5f398699e2d332e25ee |
| fteplug_ode_x64.dll | 7f0de2b9aa68a0c2141e361995774cd7647c491d3d145ebe2aa5e740c69f46f9 |
| fteplug_ui_imgui_x64.dll | b1c99a18fc58699f662ca106b6cd1452a637948785a44dc99de77651148dd841 |

`installed-smoke-03/result.json` launches each actual installed client and the
installed dedicated server against the owned guarded fixture, not owner data.
Version readbacks match the exact integrated stamp and `r_blendsort 1 (default)`;
real dedicated connection, Kitsune map, bridge body/timer and PNG-visible HUD ACT.
OS loaded-module queries prove each DLL came from the corresponding canonical
install directory. All five client DLLs and four server DLLs are checked across
two physics phases: Box3D and ODE cannot be active together. Dedicated-server UI
plugin refusal is expected because its client interfaces are absent. Initial
smoke arms assumed simultaneous physics and server UI availability; they stop
rc0 with guards unchanged, remain excluded, and are not product fixes. The
corrected smoke stops every owned runtime rc0, with no guard changes. Plugin
loading is not certification of every physics/content/UI feature.

At **2026-10-13 11:16:55 UTC**, `delivery-final.json` records a full post-smoke
recheck: all 13 native destinations/rollback files match; complete membership,
size, SHA-256 and mtime of **9,310** protected config/progs/player-data files are
unchanged. Receipt SHA-256:
`dc2ea2f68607b24566d4cedb53ff0472c5af0e6688b94d4d1d3d47120857980d`.
Installed smoke result SHA-256:
`ea46bc1f59530e82536e29bcc5aadceec25c927deadc9cb24b4e466c4b1b6218`.
A bounded independent source/bundle/installer review is OK with notes; its mapping
clarification is fixed. Actual installed runtime and protected-tree acceptance
remain distinct from that review. Defaults remain mode1; mode2 is still opt-in.
All broader limits above remain unchanged.

## Source temporal-cache reachability — 2026-10-13

At the delivered integrated engine `a8e705787`, Source cache1 is **NOT REACHED**,
not a passing cached-path gate. `plugins/hl2/mod_vbsp.c:10965–10966` assigns VBSP
worlds `fg_new` and `MDLF_SOURCEBSP`; `engine/client/r_surf.c:3812` admits only
`fg_quake`, `fg_halflife` and `fg_quake3` to temporal-cache generation. Source
continues through `VBSP_PrepareFrame` and ordinary world submission even with
an explicit cache1. The generator's unsupported-world branch is empty: changing
only that admission condition would not implement Source cache support.
A static brush VBO, a cache cvar readback, or `r_waterinfo`'s misleadingly named
“in use” field (`.ival`, not draw activity) is not a cached-path witness.
Do not invoke `r_waterinfo` on Source; its existing diagnostic crash is separate.

New owned evidence: `artifacts/source-cache-20261013/`. A diagnostic-only build
adds ticketed counters **after** ordinary/cached main-view `BE_DrawWorld` calls,
plus model identity, requested/effective cvar and actual rendered eye/angles.
It changes no cache decision, geometry, shader or default. It is derived from
`a8e705787`, not identical production source, and was never installed. Full stamp:
`git-690-a8e705787fad1b60661da5e8dd43c9138cc69b1b-mv11-cacheprobe`.
Diagnostic client SHA-256:
`e6c8b0fbf6fbfc54defc9298169c0f878603ca2adfe538e2547bd678cb3344bb`.
The client-only build has 37 compiler-warning occurrences, no new message
payload against the accepted full native baseline; it is not a zero-warning
build or a fresh full plugin-build control.

- `native-final`: cold Source1 and fixed-station cache0 -> cache1 -> return0,
  both sorting modes. VBSP reports fromgame4, flags0x3480. Cached count remains
  zero; settled cache1 samples add 232/233 ordinary submissions for modes1/2.
  Actual rendered eye/angles are stable. Thus “cache1 enabled” would have been
  a false action claim without this actor control.
- `native-probe2`: separately staged BSP29/shader positive control, with actual
  map identity required. Cache1 adds 234/231 cached submissions for modes1/2
  and zero ordinary submissions between settled samples. Cache0/return add
  ordinary submissions and zero cached submissions. Nonempty coloured fixture
  pixels and exact repeats accompany the counters. This proves the probe can
  observe real cached action; it is diagnostic-build evidence, not production
  Q1-cache certification or arbitrary opaque Source support.
- Exact retained production P688 and installed integrated P689+P690 bundles,
  tested on the owned subject at Kitsune body
  `-14986.3 -14484.8 772.3`, aim `19.3 125.6 0`, FOV100/960x720, with pinned
  shader/refraction/prediction/mouse controls: all 36 PNGs repeat exactly.
  Selected cache0/cache1/return0 match for each arm/mode. Mode1 cross-binary
  comparison is zero; mode2 changes **12,065 pixels in each cache setting**,
  reproducing the earlier bounded acted sorter result. The diagnostic images
  also exactly match the corresponding production merged images. These are
  ordinary-path Source pixels, not proof of Source cache or frame-time behavior.

`grade_cache.py` freezes strict counters, image hashes/parity and exclusions in
`CACHE_RESULTS.json` (SHA-256
`47f606571cd38ad2551599d9c8a0a80b965c7fc6b81aadead5608b05d2190883`).
First-run Q1 map404 stayed on Source and is excluded despite its label/zero body;
earlier unrelated water-station Source pixels animate and are not parity
acceptance. Two compiler tempdir setup failures occurred before compilation;
PowerShell make succeeded. Failed attempts remain retained, not relabelled.
All bridge-owned processes stopped rc0; eight subject native files were
hash-restored, temporary fixture files/created map directory restored absent,
and both installed client hashes stayed unchanged. No product patch, config/QC,
fleet, release, default or deployment operation was part of this continuation.

Promotion gates must separate **supported-map cached-path preservation** from
**Source temporal-cache support**. The former still needs representative native
coverage; the latter needs an explicit generation/data-interface implementation
and acted GPU/visual/performance controls before it can be an acceptance arm.
Do not manufacture a pass by toggling cache1 on VBSP. Default1 remains retained.
