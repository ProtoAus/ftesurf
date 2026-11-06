# P1345 - accurate frame reports and smoother map-only noclip

## Status and scope

P1345 implementation/build controls passed, but independent held-source reviews
then found FOUR state/classification regressions. Published edaafce84/tag1345 and
rejected e317/CS729ad625 remain immutable historical controls, NOT eligible for
promotion/catalog admission. This task deployed none of those images.
P1348 corrects the findings; see tools/p1348-overview-state.md for current source,
normal Full/native and both THREE-VM builds, current Pi218721aa preservation,
1102acting source controls and pending delta reviews/publication/delivery.
The earlier final unprofiled native check REFUSED100s admission below4GiB, with
no game/lock held. It did not execute and is not a GPU/FPS pass. Do not weaken
4GiB/60s guards. Owner feel is separate; this is not release/acceptance evidence.
Unpublished reservation1331 was superseded by ONE1345 claim after fetching both
repositories and a full registered-worktree/claim census. Original evidence names,
source images, rejected attempts and timestamps remain unchanged.

The goal is accurate diagnostics and quick outside-map navigation without lowering
normal in-map quality. This is not a universal zero-hitch or all-resource readiness
barrier, and it does not change physics formulae, wire or recording formats.

## Frame statistics corrections

- Slow slots keep retained-sample identity, including equal-duration entries at
  different camera locations. Expiry/capacity eviction and ties cannot retain the
  wrong slot or repeatedly rebuild the ring.
- Long positive stalls are retained. Focus/idle exclusions, retained coverage and
  the wall-clock source are explicit; exclusions rebase rather than join gaps.
- The live graph remains a cheap, labelled histogram estimate. Explicit dumps
  sort copied raw samples for nearest-rank percentiles, median-threshold stutters
  and exact floor-count slow-tail averages, minimum one sample.
- Temporary application allocation is checked and capped at256KiB; it is freed
  before report publication. Allocation failure publishes no new report and
  rebases sampling. Query/dump overhead is not gameplay performance evidence.

`tools/test_frametime.py` compiles the actual selected source with tracked
allocation/OOM controls. Original sampler:440checks/10failures; corrected13992/0.
The prior approximate dump passes its old suite but fails58of14100 expanded
checks; exact dump14100/0. This is algorithm/ownership evidence, not native FPS.

## Map-only rendering policy

Read-only native `VF_WORLDONLY228` classifies the final primary gameplay camera,
actual noclip movement, loaded world and invalid visibility cluster. The query is
visual-only and respects optional-engine capability via `r_voidscene`; older
engines return the existing path without calling the new property.

With `r_voidvis`, nonarchived `r_voidscene` defaults1. It keeps BSP, loaded
structural brush models, authored `func_lod` visibility and frustum policy while
skipping decorative submissions, emitters, lights, particles/trails and optional
QC effects. Capture/input/recorder/nonvisual state and ordinary HUD keep advancing.
Reentry restores drawmask eligibility and owned weather state without a burst of
hidden-history effects. Reflection geometry remains available; optional3D skyrooms are omitted only in
map-only scenes.

Uncovered forced-void pixels are explicitly cleared for the eligible primary
mono/single-seat screen view in BOTH mode0 and1. Native secondary insets, recursion,
stereo, other seats, named targets and loading are excluded. Native point queries
receive all required output pointers; permissive null-output stubs were rejected.

Developer census is now scoped to primary STANDARD screen candidates before
skip ranges/PVS/frustum/model culls. Nested passes cannot overwrite it and other
passes cannot increment its rejected count. It is NOT rendered-model geometry.
`r_voidscene_info` observes before transient batch restoration; change-triggered
`voidvis` messages include the host frame for spike correlation.

## The first-void rendering pause

The owner reports a brief rendering pause on each crossing, worst first noclip
out, rather than a camera jump. A first long gfx frame correlated with the exact
visibility transition. That six-arm comparison was rejected after a competing
session appeared; its numbers are not representative performance evidence.

The subsequent existing native sampler/compile/open/lightmap probe ran with
qualified admission and no competing game at postflight. Exact EXE/debug and
same-byte HL2 plugin symbols attribute the cold boundary to:

`BIH_Trace -> VBSP_WorldLightVisible -> VBSP_AddWorldLightCube ->
VBSP_LightPointValues -> HL2_CalcModelLighting -> VBSP_PrepareFrame`,
inside recursive reflection rendering. Of161samples at that boundary,154 contain
BIH_Trace and156 contain HL2_CalcModelLighting, each function counted at most once
per sample. Per-frame lightmap rebuild counters and file-open count were0. There
were no lazy-compile records, but no positive compile-hook control: this alone
DOES NOT establish universal absence of shader compilation.

Static props deliberately use exact once-per-map lighting; its quality is NOT
reduced. The defect was our unconditional clearing of `RDF_WORLDONLY` in recursive
views, which revived props and their cold lighting work inside reflections.

The fix separates two meanings: the legacy raw void predicate stays view-local;
the explicit parent map-only quality policy survives positive recursive children.
Fresh primary/named scenes still clear and rederive it. No normal-parent policy
bit is created, and normal exact lighting/BSP/reflection geometry remains intact.

The same source-bound instrumented subject has no armed12ms spike/sample at its
first/repeated boundary events. This is targeted attribution/regression evidence,
NOT product FPS, a numerical app-cold speedup or proof of no smaller hitches. A
setup outlier before the boundary remains explicit. Probe code/include were
removed against exact owned source preimages; none may ship. Baseline, subject,
symbols, raw data and rejected results are retained separately in the task ledger.

## Other acting controls and limits

- Actual pure query:5760cases; loaded-brush classifier280/no loads; guarded native
  color-clear4423680cases, with old/null-output/stereo/secondary controls acting.
- Actual primary census fragments432cases, including a legacy nested overwrite
  control. Actual policy reset1280cases: primary clears stale state, selected
  recursive child retains only an existing bit, unrelated flags unchanged.
  Pure query bodies remain unchanged across this policy fix.
- Three-map native pixel/geometry checks keep the map visible and remove forced
  snow; the first failed snow-pixel observation is retained, not relabelled.
  A fixed uncovered Anubis crop changed442->0. Shape counts are not a screenshot
  or geometry checksum, and candidate model totals are not draw counts.
- Ceaseless exposed skipped authored LOD visibility. The narrow visibility-only
  helper and its child callback now act, without arbitrary effects predraws;
  drawmask eligibility is restored on exit. Initial-entry native gate, loaded
  CSQC identity and explicit proximity mode controls act.
- Full Tensor2 normal profile was recovered from a completed log after an early
  reader false failure. `Sprite_SkyTest` dominates QC self time, but tracing versus
  name work is not separately measured. Prefix-only optimization preserves native
  lowercase and query/cache cadence;337344model cases pass. No substantive normal
  trace reduction or FPS gain is claimed.
- Older diagnostics used canonical7ccb compiler with two known F333property227
  miscompilations. Those programs are NOT a safe fleet baseline. Final builds use
  the exact read-only qualified c24ede65 compiler in the owned source tree, with
  canonical tools untouched. Native C controls and attribution retain their own
  bindings; do not silently promote old bytecode to the new closure.
- Main and Pi-compatible client profiles differ. Never ship whole current main
  cl_main/menu/server to the Pi: narrowly compose only this rendering delta onto
  the current compatible profile and preserve unrelated native/QW/menu/data.

## Delivery / acceptance still to bind

- [x] Full normal engine/plugin and THREE-VM build, qualified compiler, no new warnings.
- [ ] Exact final-product first/repeated out/in native check without the profiler:
  automated admission refused below4GiB; no GPU pass. Use actual owner acceptance
  for visual feel, not a manufactured numerical/native benchmark result.
- [ ] Clean inspected commits, exact SHA pushes and engine tag/pins; QC Build89 unchanged.
- [ ] BOTH Windows installs and compatible Pi client profile, hashes/live served bytes.
- [ ] UTC provenance, rollback/data-preservation receipts and targeted owner check.

Human acceptance belongs in `lextest.md`: after installation, noclip out/back in
several times and confirm smoother entry, readable map, no lingering effects and
normal in-map appearance. No human pass has been invented.
