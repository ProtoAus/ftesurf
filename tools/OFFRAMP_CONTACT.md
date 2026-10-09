# Off-ramp contact measurement (diagnostic only)

`offramp_contact_smoke.py`, `offramp_contact.py` and
`test_offramp_contact.py` measure ROADMAP 12.4 before a classification change.
They do **not** implement it, verify physics, or repair P560's requested/native
clock mismatch. No patch number, engine pin, or deployment is implied.

## Safety and setup

Use two **clean, isolated Git worktrees**, one for the game and one for FTE.
The seam installers refuse a primary checkout or tracked-dirty worktree.
Diagnostic source, binaries, rigs, logs and reports belong in the private tree;
never deploy the instrumented progs/server. No owner config, player fixture or
recording needs replacing. The overlay runner starts/stops only its own processes.
Choose an unused dedicated lobby-range port (default 27617).

From the isolated game worktree:

```
python -B tools/offramp_contact_smoke.py --instrument-native <isolated-fte-worktree>
python -B tools/offramp_contact_smoke.py --instrument-only
```

Build the instrumented dedicated server with the engine's Windows `sv-rel`
procedure, not the game's deploying `-Engine` option. In **pwsh 7**, put the
MSYS2 UCRT64 and usr bin directories on PATH, set TEMP/TMP/TMPDIR to a writable
private directory, and run:

```
make -j8 -C <isolated-fte-worktree>/engine sv-rel FTE_TARGET=win64
```

The result is `engine/release/fteqwsv64.exe`. Existing compiler/Makefile warnings
must be compared to an uninstrumented build at the same source; diagnostics must
not add warnings. The private mover trace runs after **each** `PMSrc_Tick`, using
the host client's cumulative move-tick base, not just the last tick of a command.

Seed `src/fteqcc64.exe` from the normal build tool, then build the three private
progs from the isolated game's `src/` directory without deploying:

```
pwsh -NoProfile -File ./build.ps1 -Jobs 8 -QuakeDir ''
```

From the isolated game's root:

```
python -B tools/offramp_contact_smoke.py --native-server <private-server-exe> --output-dir <private-dir> --fps 30 100 300
python -B tools/offramp_contact.py <retained-rig> --output <private-report.json>
python -B tools/test_offramp_contact.py --rig <acted-retained-rig> --output-dir <private-controls-dir>
```

The launch runner retains artifacts; **retention/completion is not a PASS**.
Run the strict grader on each arm. `--grade-only <rig>` is also supported by the
smoke wrapper. A process terminated between packet and clock-anchor writes is a
strict-red capture, not permission to ignore missing anchors. Preserve it before
an explicitly recorded rerun.

## What acts and what is measured

The default route is `surf_voyager`: warp using `cmd zone_goto start`, then walk
**backward** out of the start box to touch the map's real launch pad. Walking
forward only explores the floor and is an unacted native-ramp control. The
optional `--map surf_dune` route can ride its initial slope but land before an
air leave; that is not a successful off-ramp arm.

Client input ordinals are retained even when run timestamps repeat. Each sample
contains its real raw flags, `Line_Contact` kind/hold state, command frame and
predicted body. Event rows come from `Line_Ev`; render rows come from the actual
`Line_Marks` call after the normal visibility gates. A private observer opens
production rewind twice after the first actual surf-to-air leave (including its
confirmation), then selects that measured event for the chase view. This is
**view selection**, not native resume/save selection or a resume-clock test.

The grader requires an acted native ramp plane and airborne loss, native/packet
clock and raw-contact agreement, actual counted recording anchors, contiguous
client ordinals, an independent 80 ms hold reconstruction, and a leave at that
sample's exact ordinal/time/position. A discontinuity clears the hold with
`Line_Point`'s actual `t - 999` stamp (not an invented zero), including QC's
float32 subtraction and hold comparison. Timing thresholds are not widened. Its rendered marker must retain the stored
event's position and time. Counterfactuals remove/forge each stage and must be
refused. Native authority in the client log is rejected, not promoted.

## Interpretation and limits

`structural_gates: PASS` means the measurement acted and its stage contracts
agree. `fix_acceptance: NOT_TESTED` remains explicit. Stage reports distinguish:

- native loss, using counted server packet anchors;
- last observed positive contact and the next client clock step;
- the held-kind transition and its mark;
- the position passed to the actual render call.

Native-to-mark distance includes predicted-body placement and packet/stat
sampling, not just the hold constant. A large gap between sampled run timestamps
must not be reported as a longer configured hold. The preceding native edge in
a report is a stage association, **not** a snapshot-selection oracle. Different
FPS caps can produce different live input/launch histories; this route is not a
bit-identical cross-FPS physics comparison. Diagnostic log overhead also affects
cadence, so do not treat these runs as an uninstrumented performance benchmark.

Classification remains unresolved: decide whether to label the last raw contact
point while preserving short-gap smoothing only after testing real short native
gaps, sustained exits, ground landings, steep ramps, walls, seams and tiny steps.
Jump-off versus downhill-edge, sloped-air troughs, LOD placement, ordinary camera
acceptance and human tests are separate. Do not substitute elapsed-time retiming
or a look-ahead threshold for those semantics.

## Buffered immutable-input replay control

The live stage seam above prints per native tick. To isolate that overhead from
raw-contact behaviour, `offramp_buffer_smoke.py` installs a **different** private
seam in a fresh clean engine worktree. Do not combine the two seam installers.
Build and retain an uninstrumented `sv-rel` server at the inspected engine commit
**first**, then install/build the buffered subject:

```
python -B tools/offramp_buffer_smoke.py --instrument-native <new-isolated-fte-worktree>
```

Use the same pwsh/native build procedure above; build uninstrumented game progs
in an isolated game worktree without deploying. The buffer include is a tooling
fixture, not product C source or a mover change. Never ship either diagnostic.

```
python -B tools/offramp_buffer_smoke.py --control-server <clean-server> --server <buffered-server> --recording <private-exact-state.rec> --output-dir <new-private-dir> --packets 10000
python -B tools/test_offramp_buffer.py
python -B tools/test_offramp_buffer.py --arms <new-private-dir>/arms.json
python -B tools/offramp_geometry.py --arms <new-private-dir>/arms.json --map <runtime-map.bsp> --output <private-geometry.json>
```

The Windows runner uses private rigs, local executable/plugin copies and only
its own processes. It copies the isolated game's configs/progs, loads the same
installed HL2 loader explicitly, and removes only its own content junctions.
The loader's source/build provenance is external to this control; its hash is
recorded and equal across arms, not declared freshly compiled. Map, input,
plugin and progs hashes must agree; the BSP is also hashed before/after each arm.
`--packets` is an upper limit, not a promise that the file contains that many.
A failed/aborted rig remains evidence; do not reuse its output directory.

Four arms must ACT: clean server, buffered server with capture OFF, capture ON,
and repeated ON. Existing `pm_recsim` clock/world/body summaries must agree and
its open loop must reproduce every selected packet's six recorded body numbers.
This is the recorder's own text precision, **not** a new bit-exact clean/ON
state proof. ON/repeat numeric trace rows must match exactly. OFF/clean must be
quiet. The current grader intentionally refuses discontinuous/session-reset
native clocks; do not widen it merely to fit a rewind file.

Capture stores fixed-size tick/contact records only: no formatting, I/O,
allocation, cvar lookup or added trace in the native hot path. The accepted ramp
trace retains its fraction/plane, sweep endpoints, hull, physent index and
recovery flag. Arrays are capped at 32768 ticks and contacts each; a dropped
record or missing footer rejects the capture. Dumping occurs after capture is
disabled, before the existing summaries. This is lower-overhead by construction,
not a measured uninstrumented performance benchmark or a live FPS comparison.

Offline geometry returns **all candidates**, never an authenticated winning
brush. It considers only model 0's referenced solid/playerclip VBSP brushes,
matching the last accepted world non-recovery plane and the preceding hull.
It preserves the Source compressed lump header's declared output size, as the
plugin does; raw LZMA decoder padding is not another leaf. Face support gaps and
nonface halfspace gaps are numeric candidate diagnostics. The 0.0625-unit
candidate envelope is not a new contact/hold/classification threshold. No
matching brush abstains: triangle/displacement hits and recovery/moving/portal
geometry need other evidence. Short raw gaps can occur without crossing a
candidate's nonface boundary, so placing a leave on every raw loss is not yet
justified. Full render/held-stage FPS/tick-rate, geometry-winning identity,
jump/edge/seam discrimination, camera/LOD and P560 resume-clock acceptance stay
**NOT_TESTED** by this control.

## Return-bound winning-trace provenance

`offramp_origin_smoke.py` composes the buffer plan with a private BIH witness.
Use another **new**, clean isolated engine worktree; do not layer it over either
installed seam. All original-text anchors and include collisions are checked
before writes. Disjoint edits are composed from original spans, not against
successively changed source. The shared buffer installer still works alone.

```
python -B tools/offramp_origin_smoke.py --instrument-native <new-isolated-fte-worktree>
# Build its private sv-rel server using the procedure above.
python -B tools/offramp_buffer_smoke.py --control-server <clean-server> --server <origin-server> --recording <private-exact-state.rec> --progs <unmodified-progs-dir> --output-dir <new-private-dir> --packets 10000
python -B tools/offramp_origin.py --arms <new-private-dir>/arms.json --output <private-origin.json>
python -B tools/test_offramp_origin.py --arms <new-private-dir>/arms.json
```

The witness lives in each BIH trace. A leaf's actual accepted clip updates it,
including the legacy equal-fraction replacement (Source's brush rule keeps the
first equal-fraction winner). Nested-model and physent comparisons carry ONLY
the winner. A result is stamped with its exact output trace address; each native
call clears the stamp, so nonparticipating paths cannot promote an old result.
TryPlayerMove saves provenance immediately before validation/ground probes can
replace the shared result. A cached firsttrace carries its own copy. Recovery
has an explicit route because its synthesized accepted normal is not the
normal of the underlying collider. Portal paths conservatively abstain.

Origin rows bind to buffer contact/tick ordinals and physent index; the tick
row carries the native move tick and input/command/packet ordinals. They retain route (0 fresh / 1 cached / 2 recovery / 3 portal),
BIH kind (0 unknown / 1 brush / 2 triangle / 3 patch), runtime leaf/root-leaf,
embedded depth, contents and model resource name. Internal pointers never
serialize. **Runtime BIH leaf ordinals are not Source brush-lump indices.** The
origin-only snapshot identifies collider provenance; it does not export the
winning brush's halfspaces or authenticate the earlier offline candidates.
The optional whole-brush snapshot seam below exports the loaded halfspaces.
World triangles remain unresolved, not guessed to be displacement faces;
embedded models, inline/dynamic entities, solids and recovery/portal paths do
not become supported exit geometry merely because a model is identified.

Before replay rows, sixteen authored setup-only native controls exercise the
real BIH/physent merge: leaf competition, both equal-fraction rules, triangle
identity, nested winner/loser, unstamped results, no-hit/solid abstention,
output-address mismatch, a later probe, physent winner/loser and conservative
portal abstention. They restore pmove/probe/clip-mode state. They are NOT
partial/full/convex edge, jump, seam or portal-traversal motion fixtures. No
extra trace or I/O is added to the mover capture path; output is buffered until
capture ends. Only the single-threaded exact replay is supported.

The same clean/OFF/ON/repeat gates still apply, with exact repeated origin rows
and no origin output in clean/OFF. The runner's game source ref identifies the
tooling/config tree, not necessarily an externally supplied progs compilation;
retain the separate progs build provenance and hashes. The installed loader's
compilation provenance also remains external. Structural/provenance PASS
leaves winning-leaf geometry, cached/recovery/portal movement-path coverage,
physical exit, classification, live stages/rates and camera acceptance
**NOT_TESTED**. Do not switch marks to every raw contact loss on this evidence.

## Copied winning brush halfspaces (diagnostic only)

`offramp_shape_smoke.py` installs all three measurement layers together in a
**new** clean isolated engine worktree. It validates original/generated seams
and all include collisions before writes. Original buffer/origin installers
remain independent; never layer installations onto an instrumented tree.

```
python -B tools/offramp_shape_smoke.py --instrument-native <new-isolated-fte-worktree>
# Build the private sv-rel server as above. NEVER deploy it.
python -B tools/offramp_buffer_smoke.py --control-server <clean-server> --server <shape-server> --recording <private-exact-state.rec> --progs <unmodified-progs-dir> --output-dir <new-private-dir> --packets 10000
python -B tools/offramp_shape.py --arms <new-private-dir>/arms.json --output <private-shape.json>
python -B tools/test_offramp_shape.py --arms <new-private-dir>/arms.json
```

At the actual winning brush leaf, fixed-copy the complete **loaded** side
planes and model-local bounds, including loader-generated bevels absent from
the BSP plane lumps. Later probes, source-plane mutations or losing nested/
physent candidates cannot replace these copied values. Capture instance
origin/angles/raw scale, capsule status and direct-BIH callback ownership at
the winning return/physent comparison. A wrapper returning an inner BIH result
is NOT direct callback ownership. No source geometry is reopened at dump.
No extra trace, allocation, I/O or cvar lookup enters the mover capture path.

There is a fixed **64-side** whole-shape cap. Over-cap brushes retain bounds/
source side count and explicit ABSTAIN, never a partial plane list disguised as
complete. Unknown/triangle/patch leaves clear old brush values. Fourteen
setup-only native controls check copies, exact plane membership, mutation/
probe independence, nested/physent winners, cap/invalid-source/triangle cases,
pose/capsule metadata and hybrid callback abstention. These are not surf
edge/jump/seam, capsule-movement or displacement-loader trajectory fixtures.

Repeated plane I/O can timeout despite correct physics. Protocol v2 deduplicates
**already copied** immutable payloads AFTER capture using a fixed bounded table.
It emits BEGIN (version/side cap/table cap), SHAPE (payload ID/status/count/
bounds), PLANE (payload ID/side ordinal/normal/distance), CONTACT (contact/tick
ordinal, payload ID, winning leaf/root/depth/contents and instance metadata),
then END (contact/complete/capped/payload counts). A payload is defined once
before first use. Payload IDs are neither collider IDs nor Source lump indices;
even distinct colliders may share identical copied payloads. The dictionary
points only into private captured entries, never live brush storage.

The reader verifies complete finite unit planes, bounds/counts, ordinals,
unknown/nonbrush clearing, native setup checks and quiet clean/OFF plus repeat
parity. A static runtime leaf cannot change geometry mid-capture. Static world
AABB diagnostics require direct untransformed BIH, ordinary world model,
noncapsule hull and exact accepted normal/distance membership in the copied
planes. No collision/matching tolerance is enlarged. Identical duplicate side
planes are membership matches, not a guessed unique Source face. Raw scale 0
is recorded/allowed for the inspected unscaled world convention: BIH's native
call takes no scale argument; convex fallback remains unstamped/unsupported.
Embedded/entity geometry, transformed/scaled instances, capsules, recovery/
portal normals and non-direct callbacks remain unsupported for these queries.

Valid unsupported rows remain ABSTAIN. With no supported contact the overall
snapshot gate is ABSTAIN, not structural REFUSE or a false positive PASS. The
actual immutable-input acceptance control must still prove a supported copy
ACTED. Unmatched accepted planes retain their payload but abstain.

Loss reports include exact copied payloads and raw side-gap diagnostics at the
accepted sweep point and tick ends, expanded using the **previous contact's
recorded AABB**. The loss tick's actual hull/posture is NOT captured here;
bounds are retained separately, and numeric halfspace queries are NOT a full
engine collision/support oracle. No gap threshold, exit time interpolation,
debounce or new marker policy is introduced. Winning movement geometry,
physical exits, rate/camera/LOD/hold/render/classification acceptance stay
**NOT_TESTED** pending authored mover trajectories and same-input live stages.

## Actual contact and tick-end hull/posture (diagnostic only)

`offramp_hull_smoke.py` composes buffer/origin/shape plus a fourth optional layer
in a **new clean isolated** native worktree. All original/generated anchors and
include collisions are checked before writes. Do not layer it onto an already
instrumented tree; do not ship the resulting server.

```
python -B tools/offramp_hull_smoke.py --instrument-native <new-isolated-fte-worktree>
# Build the private sv-rel server as above. NEVER deploy it.
python -B tools/offramp_buffer_smoke.py --control-server <same-ref-clean-server> --server <hull-server> --recording <private-exact-state.rec> --progs <unmodified-progs-dir> --output-dir <new-private-dir> --packets 4418 --timeout 180
python -B tools/offramp_hull.py --arms <new-private-dir>/arms.json --output <private-hull.json>
python -B tools/test_offramp_hull.py --arms <new-private-dir>/arms.json
```

Capture the ACTUAL `pmove.player_mins/maxs`, capsule and movement type, ducked/
ducking flags, duck timer, old buttons and **RAW** `movevars.standheight`/
`duckheight` at accepted contacts and at each completed native tick. Raw cvar
heights may use fallback values; they are NOT observed hull dimensions. Do not
infer a small hull merely from a transition flag. Snapshots are fixed copies,
not pointers. No new trace, allocation, I/O or cvar lookup is added to capture.

Seven setup-only native controls invoke the real `PMSrc_ApplyHull`, checking
nondefault standing/crouched dimensions, transition posture, capsule/movement
metadata, immutable copies, distinct contact/tick snapshots and raw-height
fallbacks. Restore the full pmove, movevars and stand-bound globals before
replay. These are hull application/copy checks, **NOT** motion trajectories,
capsule collision tests or full posture-transition-policy acceptance.

Independent protocol v1: CHECK ordinal/name/pass rows, SELFTEST total/failures,
BEGIN version/tick-contact capacity, contiguous TICK rows, contiguous CONTACT
rows, then END tick/contact counts. TICK begins with native tick ordinal;
CONTACT begins with accepted-contact ordinal/native tick ordinal. Both then
carry fourteen fields: mins XYZ, maxs XYZ, capsule, pm_type, ducked, ducking,
ducktime, oldbuttons, raw standheight, raw duckheight. Exact envelope, widths,
finite fields, nondegenerate bounds, legal integer ranges, ordinals and footer
are mandatory. Contact bounds/capsule must match accepted trace metadata.
Clean/OFF are quiet; ON/repeat have equal canonical snapshots and replay
summaries against an independently clean binary at the same inspected ref.

This reader replaces the shape reader's previous-contact-hull-only numeric view
with EACH POINT's actual captured hull: accepted sweep, previous tick end and
raw-loss tick end. A legally changed later hull must change that point's side
gaps. Capsule or non-normal movement samples abstain from AABB diagnostics;
other shape/origin unsupported categories remain abstentions. No gap threshold,
exit interpolation, collider identity, classifier or marker policy is inferred.

The initial real replay control observes only standing tick hulls. It validates
capture/parity, NOT live crouch or posture-change movement coverage. Extra dump
rows exceeded the prior 120-second harness allowance on the original segment;
180 seconds permitted completion. Output occurs after capture stops, but this
is not a performance claim. Retain every timed-out output directory.

The hull-only replay stage does not validate authored movement trajectories.
The separate native command below adds bounded edge/input/jump/seam/posture
controls plus ACTED capsule/transformed paths with explicit geometry abstention. Full
collision/support, physical-exit/classification and clock/render/camera/rate/
LOD/hold/mark acceptance remain **NOT_TESTED**.

## Authored static-brush native trajectories (diagnostic only)

`offramp_motion_smoke.py` adds a PRIVATE `pm_offramp_trajectory` command in a
NEW isolated native tree. This is a test command, **never a product command**.
It drives the real `PM_PlayerMove` → `PMSrc_PlayerMove` → `PMSrc_Tick`, with
explicit fixed movevars and usercmds, on in-memory authored static brush models
built by the existing **`BIH_Build` API**. It does not mirror private BIH node
layouts. NativeTrace/PointContents callbacks are the real builder callbacks.
No map, progs, loader plugin, async spawn, player fixture or game process is
needed. Free owned model groups after each case and restore saved movement
state/config. Diagnostic query/probe output is not a production game state.

Build TWO separate NEW native worktrees at the SAME inspected base:

```
python -B tools/offramp_motion_smoke.py --instrument-native <subject-tree>
python -B tools/offramp_motion_smoke.py --instrument-native <control-tree> --fixture-only
# sv-rel build BOTH as above, never deploy either binary.
python -B tools/offramp_motion_smoke.py --server <subject-exe> --control-server <control-exe> --output-dir <NEW-private-dir> --port 27617
python -B tools/offramp_motion.py --arms <dir>/arms.json --output <private-motion.json>
python -B tools/test_offramp_motion.py --arms <dir>/arms.json
```

The independently built control is **fixture-only**, not a vanilla clean binary:
it contains the same authored command but NO buffer/origin/shape/hull seams.
Five arms: no-oracle control, oracle control, subject OFF, ON, repeat. Exact
sampled body equality with/without queries proves that oracle queries do not
alter later movement. Control/OFF/ON/repeat bodies AND query returns must be
identical; ON/repeat captured winning geometry/hull bindings must be equal.
The native numeric selftest runs without a map before each fixture command.

First bounded family, six cases × 32 actual 15ms native ticks:
- interior steep-face ride;
- straight partial-to-full side exit;
- convex diagonal side exit;
- input-driven interior contact loss and reacquisition (NOT an injected
  mid-trajectory velocity or a jump command);
- real jump-button launch on a STANDABLE brush (NOT a steep-ramp jump test);
- adjacent/overlapping coplanar brush handoff with persistent union support.

After each completed command, query the full native collision kernel with that
sample's ACTUAL hull: stationary, immediate 2u downward, and a ±2u vertical
sweep at the authored face projection. Projected queries cover ALL brushes and
each individual brush. These explicit query windows are fixture oracles, not
new collision/mark thresholds. Copy results into bounded rows and dump after
movement/capture stops; build/allocation/printing are outside the mover capture
path. No production trace is replaced and no extra oracle is called inside it.

Reader checks native queries against **joint** brush/query-AABB feasibility:
three-plane vertices of the complete constraint intersection, all inequalities
at the SAME point. Independently expanded planes are NOT the oracle. A unit
counterexample has valid individual expanded inequalities but no joint overlap.
A numeric feasibility tolerance is not a physical/classifier gap threshold.
This bounded static convex oracle is not arbitrary map/capsule/transform/SAT
or continuous collision-time coverage. Mismatch is refusal, never a weakened
physical-exit claim. Accepted whole winning snapshots must match an authored
brush, and native tick/hull/posture/trace/leaf ordinals bind to actual samples.

Protocol `OFFRAMPMOTION_` v6: BEGIN capture/oracle/case counts and maximum step
capacity, explicit per-CASE step counts (first six 32, open posture 96, ceiling
posture 192, capsule 32, transformed 32, entity-present/removed and embedded-present/removed 32 each), SOURCE
fixture-template SHA256 and native base commit, exact ordered PARAM rows
(including explicit rotated-box-hull cvar), CASE/BRUSH/PLANE/SEED, INSTANCE
for transformed/entity/embedded cases, SET/PHYSENT for the entity/embedded pairs,
EMBED for the embedded pair, ordered TICK and ORACLE rows, CASE_END, END, COMPLETE.
TICK carries actual command inputs, native tick count/rate, ramp/ground state,
body/velocity, hull/posture. ORACLE carries case/tick/kind/brush, exact endpoints,
fraction/solid flags/entity/plane/contents. Missing/duplicate/reordered/unknown/
malformed rows, changed input/provenance, nonfinite data, unregistered hull/pose,
wrong bindings, quiet subject or failed actor/native query all refuse. Named
capsule/transformed/entity/embedded cases are structurally validated but ABSTAIN
from geometry. Embedded SOURCE is build provenance, not tamper-proof binary or map authenticity.

The first successful family observes two distinct delays: side/convex projected
support is gone at a tick end while that tick still reports accepted ramp
contact; the raw contact falling edge follows later. Conversely, an interior
input-driven raw loss retains immediate AND projected native support, and a
previous brush's support can vanish while the seam union persists. These are
sampled diagnostic observations, **not rules to shift visible marks**.

Two further **real posture** cases use a standing seed and genuine duck-button
press/hold/release while moving on a standable floor: an open duck/unduck cycle,
and a low ceiling that blocks standing until the whole body clears its edge.
No mid-trajectory pose/hull/velocity is injected. Completion requires an actual
standing-hull duck transition, smaller crouched hull, unduck transition and
restored standing hull, bound to captured ticks/timers/buttons. Ground support
and nonembedded actual-body queries must ACT throughout. The first six cases'
body/oracle/accepted bindings remain exactly equal to their retained v1 controls.

Posture cases add a separately named `standing` stationary world query at the
actual tick position, using a LOCAL copy of the hull with the explicit profile's
standing height. It NEVER mutates pmove. The reader checks the standing AABB
against the same whole-brush joint oracle. In the eight AABB cases, solid flags
are permitted ONLY for this counterfactual fit query; they must not be promoted
to actual-body contact. The capsule case's separately named box counterfactual
below may also report solid, never as actual capsule contact.
The ceiling control must block the standing query while the crouched query
misses, retain crouch after button release, clear the ceiling, then really stand.
The open control must never block standing. These are bounded static/AABB
posture-policy controls, not capsule, arbitrary ceiling or airborne-duck coverage.
The initial 96-tick ceiling attempt remained blocked and failed completion;
its retained evidence was not called a pass. The ceiling horizon was extended,
not its clearance/completion/parity requirements relaxed.

## ACTED native capsule path with explicit geometry abstention

A ninth 32-tick case seeds a real standing capsule on an oblique brush, then
executes ordinary 15ms native commands through ramp ride and side departure.
The capsule bit is set only in the seed; no mid-trajectory hull/pose/velocity
injection. Actual tick and accepted-contact hull snapshots and winning trace
metadata must retain capsule=1. Copied winner planes require exact membership
in the complete authored brush, but that is snapshot binding, NOT collision
classification. Existing shape/hull readers keep `capsule-hull-unsupported`.

After each command, query native capsule `stationary` and `down2`, plus a
separately named `box` stationary counterfactual with the SAME actual point/
mins/maxs but capsule=false. Only the local NativeTrace argument changes;
pmove is never mutated. Stationary capsule queries must miss throughout.
Native capsule down2 must hit AND later miss, accepted sloped contacts and a
raw falling edge must ACT, and at least one same-pose box must be solid while
the capsule misses. Thus a copied metadata bit or quiet unsupported subject
cannot close the path gate. In the bounded control, 22 accepted capsule contacts
ACT; down2 hits ticks 0..20 and misses 21..31, raw loss is tick 22, and same-pose
box solid/capsule miss ACTS on 0..20. These native returns are not independently
proven capsule support or continuous exit truth.

The capsule report explicitly says geometry/support **ABSTAIN** and independent
capsule oracle **NOT_IMPLEMENTED**. Do NOT call joint AABB feasibility for actual
capsule results or interpret the box counterfactual as capsule geometry. The
box counterfactual itself may use the existing joint AABB oracle. Endpoint/
finite/plane/contents checks still bind all native rows. A plausible changed
native capsule result may survive the abstaining standalone reader; exact
cross-arm equality must still refuse it. Units falsify accidental invocation
of the AABB oracle; ACTED controls also refuse silent hit/miss/path differences,
changed native/accepted/tick capsule metadata and promoted geometry status.

All original eight body/oracle/winner arrays remain exactly equal to retained
controls. Fixture-only/nooracle/control/OFF/ON/repeat parity stays mandatory;
ON/repeat capsule snapshots match exactly. Only bounded native execution,
query sensitivity and snapshot/abstention gates are closed for capsules, NOT a
capsule collision/support oracle, general capsule or posture-policy acceptance.

## ACTED translated/yaw brush with explicit geometry abstention

A tenth 32-tick case translates a real world-brush physent by (1000,-300,100)
and yaws it 45 degrees. The world-aligned standing AABB executes ordinary
native commands through ramp ride and departure. Set origin/angles/unscaled
instance only in the seed; no mid-trajectory body or transform injection.
`INSTANCE` binds actual physent index/origin/angles/scale/capsule before movement.
Explicitly pin `pm_rotatedboxhulls=1`, emit it as PARAM and restore its previous
numeric value after the command. This is an artificial transformed-world
physent fixture; it does NOT close non-world/entity/map/PointContents wiring.

Actual PM_PlayerTrace -> PM_TransformedHullCheck -> BIH_Trace must produce
sloped contacts whose copied winning origin/angles/scale/native callback,
whole local brush, accepted plane and actual hull snapshots match the instance.
Existing category stays `transformed-instance-unsupported`; geometry/support
**ABSTAIN**, independent transform oracle **NOT_IMPLEMENTED**.

Native `stationary` and `down2` queries use the same actual translation/basis,
matching the mover wrapper's AngleVectors/negated-right convention. A separately
named `identity` down2 counterfactual uses SAME world endpoints/origin/hull but
removes ONLY the local query's rotation argument. It never mutates pmove.
Stationary actual body must miss/nonembed throughout; actual down2 hits AND
later misses and raw ramp loss must ACT. At least one actual hit must coincide
with a genuine identity MISS (fraction=1, BOTH solid flags=0), not simply an
identity non-hit whose solid flags were ignored. In this bounded actor: 24
accepted contacts, down2 hits 0..22 and misses 23..31, raw loss 24; genuine
actual-hit/identity-miss differences ACT 0..7. Identity is instead allsolid on
8..22. Those solid rows are counterfactual, NEVER actual-body contact or misses.

The first rig executed but the reader rejected identity-solid rows. A strict
named-query correction preserves the native contract: identity allsolid has
fraction=1, both solid flags=1, ZERO plane and ZERO contents (no winning plane
was set). Require joint local-coordinate AABB overlap for that result; absent/
stale flags/plane/contents refuse. Actual-body solid checks remain strict.
Keep failed rigs; do not reuse output directories or alter the movement actor.

Do NOT use an unrotated AABB oracle for actual transformed geometry. Identity
queries alone may use the existing joint oracle after subtracting translation.
Endpoint/finiteness/schema/contents/plane binding still applies to every native
row. BIH rotates the accepted normal to WORLD while the mover wrapper leaves
plane.dist MODEL-local. Validate that exact mixed snapshot convention (rotated
normal, unchanged copied local distance); do not manufacture an affine world
plane, surface distance, support or classification result from it. Units ACT
accidental AABB invocation and stale/world-distance promotion. Plausible changed
native transformed fractions may survive standalone abstention, but exact
five-arm query parity must refuse them.

All original nine body/oracle/winner arrays stay EXACTLY equal to retained
capsule controls, including capsule ABSTAIN. Fixture-only/nooracle/control/OFF/
ON/repeat parity and actual native/capture actuation stay mandatory. Only this
bounded transformed execution/query sensitivity/copy binding gate is closed.

## ACTED non-world physent winner and removed-entity trajectory

Two further matched 32-tick cases use the SAME standing-AABB seed, velocity and
zero commands. World physent 0 owns only a remote brush (y -1024..-896); a separate
physent 1 owns the ordinary oblique ramp (y -64..64), named
`*authored_offramp_entity`, info 42, untransformed and scale 1. The removed arm
configures the same slots/models but limits the active physent list to the world.
These are authored native model fixtures, NOT map/QC/entity-loading coverage.

Ordered `SET` rows bind actual active count and skip filter. `PHYSENT` binds
case/index/info/model/brush/active flag; `INSTANCE` binds each configured slot's
origin/angles/scale/capsule. The present actor must produce real
PM_PlayerMove -> PM_PlayerTrace -> BIH brush winners on physent 1. Capture binds
accepted contact/entity index, origin route/model/direct leaf, whole brush 1,
identity pose/scale/direct-BIH flag and actual standing hull. The shape reader's
existing **`entity-unsupported`** category is unchanged: non-world geometry/support
**ABSTAIN**, even though these sampled unrotated native queries can be checked.
No entity snapshot may be promoted to world-brush support.

After each command, actual `stationary` and `down2` queries call PM_PlayerTrace
over the active physents. The named `worldonly` down2 counterfactual uses SAME
body endpoints/hull but temporarily limits the local query's physent count to 1,
then immediately restores it. Present hits must have native winner index 1;
misses have -1, zero plane/contents. Stationary actual body must miss/nonembed.
The joint convex/AABB oracle includes ONLY active brushes; `worldonly` and the
removed actor include ONLY brush 0. An inactive entity cannot prove a collision.
This independent bounded query check is not a generalized entity identity,
support/physical-exit or anti-cheat oracle.

The bounded present case ACTS with 22 accepted sloped entity contacts, down2
hits 0..20 and misses 21..31, raw ramp loss 22. Every `worldonly` query misses;
actual-hit/removal-miss differences ACT 0..20. The removed actor has no ramp bit,
accepted contact or native down2 hit, and its first/final body states differ from
the present trajectory. Thus the positive gate cannot pass through metadata
alone or a quietly missing collider. Removed zero-contact captures still require
complete tick/hull/selftest/footer envelopes, not a fabricated brush witness.

No-oracle/fixture-only/OFF/ON/repeat BODY and enabled QUERY parity, ON/repeat
whole capture equality and exact original-ten body/oracle/winner arrays remain
mandatory. No-oracle equality also proves removal queries did not affect later
movement. ACTED refusals cover active lists/slot/model/info/pose, world-winner or
copied-shape substitution, cached route, silent native hits/removal, stale misses,
query/body binding and entity-to-world geometry promotion. Capsules and
transformed instances retain their previous explicit abstentions.

## ACTED embedded BIH_MODEL winner and removed-parent trajectory

Here **embedded means a child collision model in a BIH_MODEL leaf**, NOT a player
starting inside solid. All actual-body stationary/nonembedded checks stay strict.
Two matched 32-tick cases use the prior entity pair's standing AABB, geometry,
seed/velocity and zero commands. Present world physent 0 has one BIH_MODEL root
leaf pointing to a loaded native single-brush child `*authored_offramp_embedded`,
identity embedded origin/axis. Child leaf 0 owns ramp brush 1. The removed parent
has only remote direct brush 0 instead. No new collision callback or production
mover branch is invented; both parents/child use the actual BIH_Build API.

SET/PHYSENT/INSTANCE bind actual world physent/count/filter/model/pose. Ordered
`EMBED` rows bind case, root/child leaf, actual parent node count, active-child
flag, model/brush root kind, child name, embedded origin and axis. A real present
PM_PlayerMove -> PM_PlayerTrace -> BIH_MODEL -> child BIH_BRUSH winner must bind
world physent 0, child model name, leaf/root 0, depth 1, route 0, complete copied
brush 1, accepted plane and actual standing hull. The existing
**`embedded-model-unsupported`** category remains intact: geometry/support
**ABSTAIN**. Copied root-physent pose is not a general embedded-transform snapshot;
child planes must never silently become accepted world-brush support.

Actual stationary/down2 queries use PM_PlayerTrace over the parent. Named
`unembedded` repeats SAME down2 endpoints/hull with only the query's world model
pointer temporarily replaced by the direct remote-brush model, then immediately
restores it. Hits require native world winner 0; misses require -1 and zero
plane/contents. The joint AABB check includes ONLY child brush 1 for present
actual identity-embedded queries, and ONLY remote brush 0 for unembedded/removed
queries. These are sampled identity-transform fixture queries, NOT general
embedded geometry/support/identity/map-loading acceptance.

The present actor produces 22 actual depth-1 child-brush contacts, down2 hits
0..20/misses 21..31 and raw ramp loss 22. Every unembedded query misses and the
actual-hit/removal-miss difference ACTS 0..20. The removed trajectory has no ramp,
contact or downward hit, with physically different first/final body states.
Empty removed captures still require full valid tick/hull/selftest envelopes.
All five-arm parity checks and exact original-twelve body/query/winner arrays
remain mandatory; nooracle parity proves temporary model replacement did not
alter later movement. ACTED refusals cover embedding schema/root/child/axis,
wrong depth/model/leaf/hull/callback, cached route, silent native hit/removal,
parent/child-physent confusion and embedded-to-world support promotion. Previous
capsule/transformed/entity gates and abstentions remain unchanged.

Exact physical exit time, classification/debounce/mark policy, general embedded/
nested-transform/model/map wiring and geometry, triangle/displacement, general
non-world/entity geometry, general airborne/other posture trajectories, explicit
cached/recovery/portal motion, general world support, independent capsule/
transform geometry, P560 clock and same-input recorded/live/render/rate/camera/
LOD/hold acceptance remain **NOT_TESTED**.

## ACTED native BIH_TRIANGLE winner and removed-triangle trajectory

Two additional matched 32-tick standing-AABB cases use the entity pair's exact
seed/velocity/zero commands. Present world physent 0 owns one actual BIH_TRIANGLE
leaf, indices 0/1/2, vertices (-256,-64,256*.8/.6), (-256,64,256*.8/.6),
(256,0,-256*.8/.6). The removed world has only remote brush 0. Both use BIH_Build
and the existing native triangle collision code, not a brush-shaped substitute.
Pin `pm_trisoup_bevels=1`, emit its PARAM, restore the prior numeric value.
Ordered `TRIANGLE` rows bind case/active flag/runtime leaf/indices/vertices;
these are **authored fixture wiring, NOT copied accepted triangle geometry**.
SET/PHYSENT/INSTANCE still bind actual world/count/filter/model/identity pose.

Real PM_PlayerMove -> PM_PlayerTrace -> BIH_TRIANGLE contacts must bind origin
kind 2, route 0, world physent 0, runtime leaf/root 0, depth 0, world model,
identity instance/scale/direct-BIH callback and actual accepted standing hull.
The brush snapshot must be empty with no stale sides/bounds/planes. Native
accepted planes remain native triangle/slab/bevel results, not a brush payload.
At least one accepted/query plane must be the authored sloped face. Existing
**`world-triangle-unresolved`** category stays intact; triangle geometry/support
**ABSTAIN**, independent triangle query oracle **NOT_IMPLEMENTED**. Unit/finite
plane checks bind the native protocol, not a triangle-support oracle. No general
triangle, displacement, mesh adjacency or real-map prop acceptance is implied.

After every command actual stationary/down2 queries call PM_PlayerTrace. Named
`untriangled` repeats SAME down2 endpoints/hull with only the local query's world
model replaced by remote brush 0, then restores it. Native hits require winner 0;
misses require -1 and zero plane/contents. Actual stationary/body solids refuse.
Do NOT substitute joint AABB feasibility for actual triangle queries. Only the
remote-brush removal/removed queries use that bounded oracle. Plausible changed
triangle fractions may survive standalone native-result abstention; exact
cross-arm parity must still refuse them.

Present produces 14 actual triangle contacts, down2 hits 0..13, misses 14..31,
raw contact loss 14. Every same-pose removal query misses; native-hit/removal-miss
sensitivity ACTS 0..13. Removed moves without any contact/ramp/downward hit;
first/final body states differ. Empty removed captures require full envelopes.
All five-arm parity checks and exact original-fourteen full case/winner arrays
remain mandatory; nooracle body parity proves the extra queries do not mutate
later movement. Nineteen motion units and 271 ACTED native refusal controls pass,
including all retained controls, triangle wiring/origin/model/leaf/hull/empty
payload faults, silent hit/miss/removal and geometry-promotion refusal.

This closes only the bounded native triangle execution/query/capture-binding
control. Independent slab/bevel/support/continuous-exit geometry, real-map
triangle/displacement/props, general airborne posture, explicit cached/recovery/portal
actors, classifier/live marker and clock/render/rates/LOD/hold acceptance remain
**NOT_TESTED**. No product mover or collision behavior changes or deployment.

## ACTED open-air duck/unduck and matched no-duck falling control

Protocol 8 appends two 64-tick flat-floor AABB actors (18 total cases). Both seed
standing at (-100,0,128) with velocity (60,0,0), then use real 15ms PM_PlayerMove
commands. Case 16 holds duck on ticks 3..10 and releases on 11; case 17 never
ducks. There is no post-seed pose/hull injection. These are open-air falling
controls, NOT airborne collision/ceiling/sliding or general posture coverage.

Native duck is instantaneous in air: on tick 3 the actual hull becomes 45 high,
ducked=1, ducking=0, timer=1000 and oldbuttons carries duck. The timer decreases
15ms per held tick. Native release on 11 immediately restores the 62-high hull,
clears ducked/ducking/timer/buttons, and reverses the origin adjustment. Against
the matched no-duck trajectory, actual origin.z differs by +8.5 on 3..10 and by
zero before/after (float32 rounding tolerance 1e-4); XY and velocities agree.
Both have actual airborne gravity, one matching native landing on 37, and end
standing on the floor. The reader requires all of these ACTED gates.

After each tick, stationary/down2/projected whole-floor/single-floor queries use
the CURRENT actual hull. Full native hit/solid truth must agree with the bounded
joint convex/AABB oracle. The stationary standing-hull query uses a LOCAL hull
copy at the current pose: it is not the mover's CanUnduck sweep, physical support
or an accepted body contact. Projected floor hits throughout; actual down2 misses
in early flight and hits after landing. Capture binds native body, actual hull,
posture/timer/buttons for every completed tick. These actors have ZERO accepted
ramp contacts; full tick/hull/selftest/footer envelopes remain mandatory, and
nothing promotes that absence into airborne winning-geometry coverage.

Fixture-only nooracle/oracle and capture OFF/ON/repeat preserve exact body/query
parity and repeat capture bindings. Original sixteen full case/winner objects
stay EXACT. Twenty-one motion units and 295 ACTED refusal controls pass, including
all retained controls and airborne actor/hull/timer/button/origin/query/landing
faults. Fixture-only oracle mutations also refuse without a capture backstop.

Only bounded open-air crouch/release execution and snapshot/query binding are
closed. General airborne/blocked-unduck/sliding/dead/spectator posture, native
general cached/recovery/portal trajectories, independent capsule/transform/triangle
geometry, real-map coverage, continuous physical exit/classifier/marks/clock/
render/rates/LOD/hold/human acceptance remain OPEN. Tooling only, NEVER ship the
private instrumented servers; no product patch/pins/Build or deployment.

## ACTED cached first-trace approach and native ramp-removal control

Protocol 9 appends two 64-tick standing actors (20 total cases). Both start at
(-100,0,.05) with velocity (250,0,0) and execute real 15ms forward=250 commands.
The world has a wide flat floor plus an ascending steep brush ramp with normal
(-.8,0,.6). The matched control removes ONLY the ramp leaf, keeping the authored
geometry, seed and commands. BRUSHSET binds actual world leaf count/active flags.
No per-tick pose/hull/ground/route injection is permitted.

Native WalkMove supplies its blocked first trace to StepMove; the flat
TryPlayerMove branch reuses that trace when its requested endpoint matches.
The actual diagnostic seam selects route 1 and copies firstorigin/firstshape/
firstinstance. This is the mover's cached FIRST TRACE, not a general engine brush
collision-cache test. The actor actually enters this branch on ticks 22, 23, 24,
then has 39 fresh route-0 contacts (42 total). The removed-ramp actor performs a
native grounded walk and accepts zero ramp contacts. Both agree before first
impact on 22 and then diverge. Native ramp-contact and ground bits can coexist;
do not equate the ground bit with unique geometric ramp support.

Each cached winner must be bump 0, nonrecovered/nonsolid, world brush with the
matching whole ascending-ramp payload, native plane, identity instance and
actual standing hull. Sweep start binds to the previous completed grounded body;
first impact follows no-ramp grounded approach. Requested horizontal sweep length
binds to this prescribed one-dimensional command's native friction/acceleration
profile: 3.75 units initially, then shorter after actual clipping. This check is
not a generalized mover solver, physical-support oracle or continuity proof.
Runtime BIH leaf/root ordinals bind capture rows, not stable map brush IDs.

Four native queries use completed actual body/hull: stationary/full-world,
down2/full-world, down2/isolated ramp (rampdown2), down2/isolated floor (unramped).
All truth must match bounded joint convex/AABB feasibility over the appropriate
active/local geometry. Full-world actual-body solid remains refusal. Only the
removed actor's isolated ramp counterfactual can be solid: native fraction=1,
startsolid=allsolid=1, entity=0, ZERO plane and ZERO contents. BIH returns early
for this inside-brush case without accepting a winning plane; fabricating contents
or a witness refuses. This is NOT an actual-body collision. Subject ramp hit vs
floor-only miss and removed actor's inactive-ramp solid query must ACT.

Fixture-only nooracle/oracle and capture OFF/ON/repeat pass exact body/query/
repeat binding parity. Original eighteen full case/winner objects remain EXACT.
Twenty-three motion units and 330 ACTED native refusal controls pass, including
all retained controls, missing/altered BRUSHSET, silent/fake body/removal queries,
cached-route erasure/fresh promotion, wrong origin/model/shape/hull/plane/sweep/
fraction/recovery and fixture-only actor faults without a capture backstop.

Only this grounded cached-firsttrace trajectory/query/capture branch is closed.
General cached/water/posture/step variants, native recovery/portal actors,
independent capsule/transform/triangle geometry, real maps, continuous physical
exit/classifier/marks/clock/render/rates/LOD/hold/human acceptance stay OPEN.
Tooling only; no product behavior/pins/Build/deployment. NEVER ship these servers.

## Independent authored triangle/slab query oracle (diagnostic only)

`offramp_triangle.py` adds a separate offline check of the retained native
triangle/removal cases, without changing the motion protocol, template, native
binary, capture category or any existing case/body/query/winner array. Its inputs
are a five-arm manifest from `offramp_motion_smoke.py` and the retained logs and
binaries; the existing motion reader first proves actor/binding/parity. Reports
need a NEW output path. Example (private retained paths supplied by the operator):

```
python tools/offramp_triangle.py --arms <arms.json> --output <new-report.json>
python tools/test_offramp_triangle.py --native-arms <arms.json>
```

The independent geometry is the finite triangular prism made from the three
AUTHORED wiring vertices plus their four-unit backward extrusion along the
solid-side winding normal. It is NOT copied accepted triangle geometry. Project
all six prism vertices and the full actual standing AABB onto the prism-face
axes, box-face axes and all prism-edge/box-axis crosses; intersect their continuous
time intervals for the translating box. Both interval bounds/signs matter. Native
planes, fractions and solid flags do NOT construct this geometric answer.
Touching and strict overlap are separate results. Degenerate/nonfinite geometry,
nonpositive slab thickness and inverted/zero-volume hulls refuse.

Nine pure units include hand-derived front/back sweeps, partial vertex/edge
contact, complete exits, winding, slab-vs-thin-slab sensitivity, translation,
and independent JOINT convex-feasibility comparisons. A concrete oblique back
corner ACTS a false positive if edge-cross axes are omitted, and both full SAT
and joint feasibility reject it. This is not a collection of quiet negatives.

For the bounded native actor, query endpoints/hull/posture/active triangle bind
exactly. Present stationary body must be clear. Down2 hit/miss agrees with SAT;
native impact plane matches an independently derived geometric entry plane and
native fraction stops 1/32 early along that normal (2e-4 spatial tolerance for
float32 vertices/body/log values). Native miss/removal requires fraction 1,
both solid flags 0, entity -1, ZERO plane and ZERO contents. Same-pose untriangled
and removed movement use only the active native remote brush, while SAT against
the inactive triangle is explicitly a hypothetical geometry result. It may
intersect/start-overlap without any actual native collision; never call that an
embedded actual body or an authenticated support plane.

The retained present actor has down2 hits 0..13 and misses 14..31; inactive
triangle intersection ACTS on removed-body down2 ticks 0..13. All 192 native
query rows pass. Thirteen tests (nine pure, four retained-native) pass with 1,558
ACTED refusal controls. A wrong triangle fraction mirrored into ALL oracle arms
still passes the existing body/query parity, then fails this independent SAT/bias
check. Endpoint/hull/posture/wiring/active flags and native fraction/plane/solid/
entity/contents faults also refuse. Ordinary unit invocation explicitly skips
four native tests; those skips are NOT runtime evidence.

Only authored-fixture standing-AABB query agreement is closed. Native axial
clipping/broadphase and biased clipping need not equal the ideal full prism for
arbitrary sweeps. Existing `world-triangle-unresolved` capture and triangle
support geometry **ABSTAIN** stay unchanged; the original motion reader still
abstains on independent triangle geometry. No accepted-triangle copy, general
mesh/adjacency/displacement/prop geometry, exact physical exit, recovery/portal,
classifier/marks, clock/render/rates/LOD/hold, human or real-map acceptance is
implied. This is reader tooling over retained native evidence, NOT a new native
runtime/build/deployment or a product off-ramp fix.

## Return-bound winning triangle fixed copy (private diagnostic only)

`offramp_tricopy_smoke.py` composes the unchanged motion/buffer/origin/brush/hull
plans and a separate fixed triangle payload in the private origin. This does NOT
change trace/model/plugin ABI, the public movement actor/template/protocol or
existing capture categories. Install in a NEW tracked-clean isolated engine
worktree, build sv-rel with pwsh7, then use the unchanged motion five-arm runner:

```
python tools/offramp_tricopy_smoke.py --instrument-native <private-engine>
python tools/offramp_motion_smoke.py --server <private-server> --control-server <fixture-only-server> --output-dir <new-arms-dir> --timeout 240
python tools/offramp_tricopy.py --arms <arms.json> --output <new-copy-report.json>
python tools/test_offramp_tricopy.py --native-arms <arms.json>
```

NEVER ship these servers. This is a private native diagnostic rebuild, NOT an
engine product patch/pin/tag/QC Build/deployment or a newly authored mover actor.
A retained fixture-only binary at the SAME engine/fixture base can be the control
if its compiled provenance is explicit. Hash actual binaries/configs/manifests;
verify the new copy-code digest and unchanged motion fixture stamp. Clean exact
commit proof rebuilds the subject and repeats all five arms, not just a reader
run against an earlier binary. The logging-heavy batch can exceed a 180s outer
command timeout even though each server finishes; use an adequate outer limit,
retain partial rigs/unknown exits, and never invent missing exit metadata.

At the same sequence-proven accepted leaf win as origin, copy the actual native
index triple and referenced three xyz vertices immediately, plus the winning
native plane tag, applied bevel flag and four-unit back-slab constant (installer
guards BOTH native clip/test expressions). No source/model/index/vertex pointer
survives. Point traces correctly record no applied bevels; current standing-AABB
motion records applied bevels. Plane tags are copied diagnostics, not an oracle
for constructing geometry. Nontriangle winners clear all triangle fields.
Unknown/disabled/solid/portal returns retain existing Unknown clearing. Status0
is empty/nontriangle/unknown; status1 is complete fixed-three-vertex geometry;
status2 is invalid source with ALL remaining fields zero, never a partial copy.

Native triangle leaves provide no vertex-array count. This is copying already
accepted native dereferences, NOT validating arbitrary pointers/index bounds,
mesh ownership/topology/adjacency or concurrent source loading. Invalid/null/
degenerate direct snapshot controls are safe setup negatives, not native traces
through invalid memory. Runtime capture adds no allocation/query/string format/
cvar lookup: fixed scalar/vertex value copies only. Setup/dump checks are not
hot-path performance proof, and these private origin structs are larger.

Twenty-three native setup checks per case ACT real near/far same-kind triangle
wins, actual differing index triples, saved-copy preservation under later source
mutation/probes, wrong output address, nearer/equal-fraction/brush competition,
nested and physent losing/winning ownership. Equal-fraction triangle wins REPLACE
with `enterfrac <= truefraction`; first-wins was a wrong initial test, not an
engine bug. Translated/capsule/hybrid metadata and portal/solid/disabled/nohit
clearing are separately controlled, NOT new unsupported movement trajectories.
Source nodes/xyz/indexes/pmove/probe/callback state restore before the mover.

The `OFFRAMPTRICOPY` v1 protocol has ordered CHECK/SELFTEST, BEGIN(1,3), SOURCE
(copy-template/installer digest), CONTACT18 and END(total,complete,invalid).
CONTACT is ordinal/tick/status/plane-tag/bevels/back-slab/three-indexes/nine-xyz.
One fixed row per actual accepted contact; no global dictionary ID or current
probe lookup at dump. Rows bind to the returned buffer ordinal/tick/origin and
native model/leaf/root/depth/physent. Complete copies require finite ordered
nondegenerate geometry, distinct integral native index values and native slab/
flag/tag validity; empty/invalid payloads cannot promote stale data. Fixture-only
and capture-OFF arms must contain NO new rows. Setup failures, missing/duplicate/
reordered/source-drifted rows, count/binding/geometry faults and repeat mismatch
all refuse. Reports require a NEW path; retained binary/input hashes are checked.

The twenty-case actor remains exact to the preceding cached proof. There are
251 accepted contacts: fourteen triangle snapshots, 237 explicit empty copies.
All fourteen current direct worldBIH, identity-instance, standing-AABB, fresh
route-0, front-face contacts match actual native wiring/index identity, then
independently match a finite-prism SAT sweep using **COPIED WINNING xyz**, not
substituted authored vertices or the native plane. Native entry normal/distance
matches independent geometry, and biased fraction is
`max(0, geometric_enter - (1/32)/abs(dot(delta, entry_normal)))`, checked within
2e-4 spatial units / 1e-5 normal tolerance. These are bounded accepted-sweep
checks, NOT raw-loss/physical-exit timing or a global support oracle.

Fourteen tests (nine pure, five actual-native) and 4,938 ACTED native refusal
controls pass, including every accepted contact's binding/empty-or-complete
faults, all copied xyz/index/slab/tag/bevel faults and every triangle sweep's
fraction/plane/hull/route faults. Mirrored wrong copied vertices preserve ALL
old five-arm case/body/query/winner parity, then fail native copy binding. Ordinary
unit invocation explicitly skips five native tests; skips are not runtime proof.
Eight installer controls prove existing-include/late-anchor/native-slab-drift/
tracked-dirty/owner-checkout refusal with all bytes unchanged; the owned temporary
dirty fixture restores byte-exact. Never remove another session's fixture.

Original `world-triangle-unresolved` and general triangle support **ABSTAIN** stay
unchanged. Existing authored query SAT remains a separate unchanged diagnostic.
Current face contacts do not measure general native axial/broadphase/back-slab/
corner/bevel bias or equal-fraction support choices, transforms/capsules/entities/
nested models, arbitrary triangle copying/overflow/index validity, displacement/
prop/real-map topology, recovery/portal, classifier/debounce/marks, continuous
physical exit, clock/render/rates/LOD/hold or human acceptance. Those are OPEN.

## Full native back-slab non-equivalence falsifier (private setup only)

`offramp_trislab_smoke.py` composes the unchanged triangle-copy/motion layers
with a separate restored setup-only BIH query fixture. Install in a NEW clean
isolated engine worktree, build sv-rel using pwsh7 and the documented TMP/TEMP
recipe, then use the unchanged five-arm motion runner. NEVER ship these servers.

```
python tools/offramp_trislab_smoke.py --instrument-native <private-engine>
python tools/offramp_motion_smoke.py --server <private-server> --control-server <same-base-fixture-only-server> --output-dir <new-arms-dir> --timeout 240
python tools/offramp_trislab.py --arms <arms.json> --output <new-report.json>
python tools/test_offramp_trislab.py --native-arms <arms.json>
```

The fixture is one large horizontal +Z-wound triangle, four-unit back slab,
identity model, bevels/source clipping ON and a small AABB [-.5,.5] on all axes.
Six full `BIH_Trace` queries (front, back, short-back, stationary back-slab,
stationary face, outside) each run active and removed, then repeat. Twenty setup
calls per ON arm produce 480 query rows; OFF and fixture-only emit NONE. Probe,
origin/callback/cvar state restores before the unchanged mover actor. Numeric
rows copy before dump; these are NOT hot-path logs or new PM trajectories.

Front sweep z6 -> -6 hits at true fraction5.5/12 and native biased fraction
(5.5-1/32)/12; independent ideal finite-prism SAT agrees at geometric entry.
Back sweep z-6 -> 2 hits at native true fraction5.5/8, biased (5.5-1/32)/8 and
axial -Z plane tag105/dist0. Ideal prism instead enters at1.5/8 with -Z/dist4:
the native hit is FOUR units later. The source's shaped axial planes use the
original triangle extents, not the extruded back vertices. Short sweep z-6 -> -2
and stationary z-2 are native misses despite ideal prism intersection/strict
overlap respectively. The stationary miss alone does not distinguish native
broadphase from axial exclusion. Stationary z0 ACTS native startsolid/allsolid;
x150 is clear in both. All same-pose removal queries are clear natively, even
where the now-inactive prism hypothetically intersects. No removal/solid return
is promoted to a return-bound accepted triangle copy or actual support.

This is a measured **NON-equivalence**, not a failed search repackaged as global
agreement. Ideal SAT is built from authored setup xyz, not the native plane/tag/
fraction or an accepted-copy claim. Analytic front/back intervals and separate
joint convex feasibility controls support the geometry. Nine tests (six pure,
three retained-native), 10,440 ACTED query/fixture refusal controls and mirrored
fraction faults pass; mirrored faults preserve old body/query/winner/copy parity
then fail this new diagnostic. Ordinary invocation explicitly skips the three
native tests; skips are NOT runtime evidence. Protocol v1 has strict ordered
BEGIN(1,24), SOURCE(template/installer digest), FIXTURE18, QUERY21 x24, END24;
input/hull/geometry/index/active/count/source/fraction/plane/flags/ownership and
local/runtime repeat drift refuse. Reports require NEW paths and hash retained
binaries/configs/manifests/logs. Existing twenty-case arrays and triangle-copy
reader result remain EXACT against the preceding retained proof. Native build
retains existing diagnostics with zero NEW normalized messages.

General triangle support stays **ABSTAIN**; original capture categories remain
unresolved. This falsifier closes only the claim that ideal full-prism SAT can
serve as an unconditional oracle for these native back-slab queries: it cannot.
It does NOT fix engine collision, off-ramp marking, physical exit or topology,
or close arbitrary bevel/corner/bias/tie/transform/capsule/entity/recovery/portal/
real-map, clock/render/rates/LOD/hold or human acceptance. No product patch,
ENGINE pin/tag, QC Build, installed program or deployment changes are implied.

## Bounded copied-winning front-edge/bevel queries (private setup only)

`offramp_tribev_smoke.py` composes the unchanged motion/copy/back-slab layers
with a restored setup-only full BIH fixture. Install in a NEW clean isolated
engine worktree, build sv-rel with pwsh7 and the documented TMP/TEMP recipe,
then use the unchanged five-arm motion runner. NEVER ship these servers.

```
python tools/offramp_tribev_smoke.py --instrument-native <private-engine>
python tools/offramp_motion_smoke.py --server <private-server> --control-server <same-base-fixture-only-server> --output-dir <new-arms-dir> --timeout 240
python tools/offramp_tribev.py --arms <arms.json> --output <new-report.json>
python tools/test_offramp_tribev.py --native-arms <arms.json>
```

Ordered xyz (0,0,0), (0,4,-4), (4,0,-4), indexes0/1/2, solid-side normal
(1,1,1)/sqrt3, slab4 and centered AABB[-.5,.5] define this identity fixture.
Five full native queries run active bevels1, active bevels0, removed bevels1,
then repeat. Twenty restored setup calls per ON arm produce600 QUERY rows and
600 bound COPY rows; fixture-only/capture-OFF emit NONE. Fixed numeric copies
are made immediately at return; no source/model/index/xyz pointer survives into
these rows. Probe/origin/callback/out/sourceclip/bevel state restores before the
original mover; no new PM path queries, hot-path logs or actor changes.

- Face reference (1,1,2)->(1,1,-2) ACTS front tag0 at true5/8 and native biased
  fraction5/8-sqrt3/128, both bevel modes.
- Edge (-.25,2,0)->(-.25,2,-2) ACTS bevel tag5/normal(0,1,1)/sqrt2/dist0 with
  true1/2 and biased1/2-sqrt2/64. Independent full finite-prism SAT over COPIED
  WINNING xyz gives that entry plane and truefraction, not vice versa.
- Bevel-OFF instead ACTS in-plane tag2/normal(-2,1,1)/sqrt6 at true1/4 and
  biased1/4-sqrt6/64. Independent geometry still enters1/2: earlier hit is a
  ghost, NOT actual geometric support.
- Stationary (-.25,2,-.75) is independently clear: hull minimum y+z=.25 exceeds
  prism maximum0. Native bevels1 misses, bevels0 sets startsolid/allsolid.
  Stationary (-.25,2,-2) ACTS solid in both; (6,6,6) is clear in both.
- Every same-pose removal query is natively clear, even where the now-inactive
  prism hypothetically intersects. Solid/miss/removal copies are fully empty;
  only actual clear-start winning hits carry the complete fixed native copy.

Original triangle axial bounds admit these front contacts and ghost poses;
bevel-OFF changes only edge-cross constraints, not those bounds or broadphase.
The hand-derived ON edge bound is y+z<=1 for this box; the OFF in-plane bound
-2x+y+z<=2 instead admits y+z<=1.5 at x=-.25. Separate joint convex feasibility
checks agree with full SAT before/after entry and on stationary separation;
omitting edge-cross axes ACTS that ghost as an offline false positive. This
bounded front result does NOT undo the measured back-slab NON-equivalence or
establish global native/ideal geometry agreement.

Protocol v1 orders BEGIN(1,30), SOURCE(template/installer digest), FIXTURE18,
QUERY23/COPY17 x30 and END30. Queries bind ordinal/mode/actual endpoints, native
fraction/truefraction/flags/contents/plane and kind/leaf/root/depth/direct-BIH;
copies bind ordinal/status/tag/applied bevel/slab/indexes/xyz, with explicit empty
clearing on nonwinning returns. Source/schema/order/envelope/count/finite/integer/
fixture/geometry/hull/ownership/binding/local/runtime-repeat faults refuse.
Reports need NEW paths and hash retained binaries/configs/manifests/logs. Ten
units (six pure, four actual-native) and24,360 ACTED numeric refusal controls pass;
mirrored wrong new fraction/xyz preserves all old mover/copy/slab parity then
refuses. Pure invocation skips four native tests; skips are NOT runtime evidence.
Clean exact-commit native rebuild repeats all five arms, not merely the reader.
Original twenty full motion/copy/back-slab results stay exact, with zero NEW
normalized native build messages versus the same-base fixture-only control.

This is setup-only small-AABB evidence, NOT a new bevel-winning PM trajectory,
physical exit measurement, support authentication or off-ramp marker/classifier
fix. Original unresolved capture categories and general triangle support ABSTAIN
remain. General corner/tie/bias/transform/capsule/entity/nested/topology/recovery/
portal/real-map, clock/render/rates/LOD/hold and human acceptance are OPEN. No
product patch, engine pin/tag, QC Build, installed program or deployment change.

## Real PM copied-winning bevel trajectory (private diagnostic only)

`offramp_bevpm_smoke.py` keeps the original twenty-case command unchanged and
adds a separate `pm_offramp_bevtrajectory capture oracle` command/envelope. Use
NEW clean paired engine worktrees at the inspected native base, one fixture-only
and one full motion/copy/slab/bevel capture composition; NEVER ship either server.

```
python tools/offramp_bevpm_smoke.py --instrument-native <private-engine>
python tools/offramp_bevpm_smoke.py --instrument-native <fixture-only-engine> --fixture-only
# sv-rel build BOTH with pwsh7 and the documented TMP/TEMP recipe; never deploy.
python tools/offramp_bevpm_smoke.py --server <private-server> --control-server <fixture-only-server> --output-dir <new-arms-dir>
python tools/offramp_bevpm.py --arms <arms.json> --output <new-report.json>
python tools/test_offramp_bevpm.py --native-arms <arms.json>
```

Registered winding xyz (0,0,0), (0,256,-1024/3), (256,0,-256), indices0/1/2,
back slab4 and standing AABB[-16,-16,0]..[16,16,62] produce front normal
(3,4,3)/sqrt34. The x=0 edge-cross-X bevel is (0,.8,.6), dist0/tag5, in the
surf band rather than the standable small-box setup's 1/sqrt2 bevel. Single
initial origin(-8,64,-32)/velocity(-25,200,-400), explicit existing motion
profile, then32 zero-input15ms commands: real PM_PlayerMove -> PMSrc_Tick ->
PM_PlayerTrace -> BIH_TRIANGLE. No post-seed body/hull injection or brush proxy.

Three matched actors: triangle/bevelON; actual zero-leaf BIH removal/bevelON;
triangle/bevelOFF. The zero-leaf builder owns one empty group node, NOT a
triangle. Removal also repeats each down2 query at the SAME actual pose with
only the model pointer replaced, then immediately restored. Full mover/profile/
probe/debug state restores at command end; identical BIH-local probe save/restore
adapters exist in BOTH control and capture builds. There is no new movement
query or hot-path print; fixed native numeric rows dump only after capture ends.

The retained actor ACTS12 tag5 bevel contacts/ramp ticks10..21 and raw loss22.
Post-command down2 hits10..20, misses0..9 and21..31; every stationary and local
triangle-removal query misses. Removed actor has no contact/ramp/downward hit
and a different final body. BevelOFF ACTS6 earlier tag2 side-plane contacts,
ticks6..11, before the ideal finite prism: ghosts, NOT physical support. Even
its final contact sweep eventually enters the ideal prism, but its accepted
native fraction is earlier at a separately joint/SAT-clear pose. ModeOFF side
fraction/bias is checked against independently derived OLD side-plane algebra,
explicitly not an ideal geometry oracle.

Complete13-axis finite-prism SAT over each ON accepted COPIED WINNING xyz gives
a clear-start entry with that bevel plane and native1/32 biased fraction. The
accepted sweep start/end bind previous native body/velocity and half gravity;
actual posture/identity instance/direct BIH/world physent0/origin route0/leaf0/
root0/depth0, empty brush snapshot and fixed index/xyz/tag/bevel/slab copy bind
independently. Query SAT uses authored fixture xyz, explicitly NOT an accepted
copy. Native original-triangle axial bounds can still exclude extruded back
corners; query misses never establish general geometric support absence.

New v1 BEGIN binds version/capture/oracle/cases3/steps32; SOURCE binds template+
installer/motion/native-base identity. Ordered CASE/FIXTURE/SEED,32 TICK rows
and optional stationary/down2/untriangled QUERY triples, CASE_END and END are
strict. Capture has the unchanged buffer/origin/shape/hull/copy/slab/bevel
selftests/envelopes, including empty removal. Unknown/duplicate/missing/nonfinite/
integer/order/geometry/source/winner/hull/input/plane/fraction/bias/binding faults
refuse; no capture rows may escape cases or appear in quiet global envelopes.
The reader splits only that strict new envelope before grading original twenty
cases; their full preceding reader result stays EXACT. Five-arm body parity,
four enabled-query parity and ON/repeat full capture equality are mandatory.

Twelve tests (six pure, six actual-native) pass without skips in the retained
native invocation:6,018 ACTED numeric query/fixture/seed/accepted-contact/winning-
copy refusals, plus schema/quiet/envelope controls. Sixty-two stationary checks
on actual copied sweeps independently agree with joint convex feasibility.
Mirrored plausible new fractions preserve all enabled new-query parity AND old
twenty-case results, then refuse against independent geometry. Pure invocation
skips native tests; skips are NOT runtime evidence. Reports need NEW paths and
hash retained binaries/configs/manifests/logs. Same-base native control warning
multiset matches the subject: zero NEW compiler diagnostics. A fresh exact-
commit build/run must repeat all five arms before publication is called proved.

Only this bounded real PM bevel/copy/bias/removed/OFF control is closed. Native
`world-triangle-unresolved` stays; general triangle support **ABSTAIN**, general
native/ideal semantics **NOT_VERIFIED**, physical-exit/classifier/render/hold
**NOT_TESTED**. Back-slab NON-equivalence remains measured. Arbitrary corner/tie,
capsule/transform/entity/nested/recovery/portal/topology/real-map, clock/render/
rates/camera/LOD/hold and human acceptance remain open. No product patch,
ENGINE pin/tag, QC Build, installed program or deployment changes.

## Bounded native triangle plane-set characterization (offline diagnostic)

`offramp_bevclip.py` consumes the retained five-arm bevel-PM capture above. It
adds no native seam, query, binary or physics change. All predecessor PM/body/
query/capture/source gates still run, and their complete report is retained.
Use NEW report paths in an owned private task root:

```
python -B tools/offramp_bevclip.py --arms <retained-bevel-PM-arms.json> --output <new-private-report.json>
python -B tools/test_offramp_bevclip.py --native-arms <retained-bevel-PM-arms.json>
```

The independent mathematical model constructs front/back-four, three outward
side planes, optional edge-cross-axis slab-support bevels, and six axial planes
from xyz/winding, before consulting native outputs. Hull support uses the bound
standing AABB. Crucially, native axial distances use the ORIGINAL three triangle
vertices, not the six extruded-prism vertices. This is a native-semantic model,
NOT the physical finite-prism oracle. Closed intersection intervals and every
plane's signed start/end distances remain in the report; the native 1/32 entering
bias is separate from geometric intersection. The first entering plane wins an
exact within-triangle tie in algebra; general native tie acceptance is untested.

All288 retained actual queries and18 accepted contacts agree. Query geometry
uses authored xyz, while accepted geometry uses the copied winning triangle.
Contacts do not capture truefraction: its prediction is labeled, never reported
as an observed measurement. Only accepted entry tags2/5 ACT here, NOT every
plane or all native semantics. Quiet-arm queries are NOT_CAPTURED. Removed-
triangle counterfactuals can be embedded in hypothetical geometry; their closed
intervals are reported but embedded PM-wrapper outputs are explicitly NOT_MODELED.

For ON down2 ticks21/22, native negative-X axial tag103 separates the whole query
by0.25/0.625 units. Removing just that plane restores the ideal finite-prism entry
interval. ON stationary queries are clear in BOTH models. The first unobstructed
move derived at raw loss22 is clear in BOTH models: outward side tag2 is also a
full-prism separating plane. Removing tag103 alone does NOT make that move hit.
The post-command down2 ideal query still intersects at22. Thus neither raw loss
nor native down2 miss is promoted to physical support departure. The derived
loss sweep is labeled NOT_CAPTURED_ACCEPTED_TRACE, not invented capture evidence.

Seventeen tests (nine pure, eight retained-native) include2,880 NEW-gate numeric
query-output refusals,108 copied-contact output/tag refusals and three ACTED
plane-construction mutants, all independent of the old reader's refusal gates.
Expanding axial planes to the full slab, removing bevels or shifting the acted
side plane refuses while predecessor reports and retained arms stay unchanged.
A shifted front plane does NOT ACT on this fixture; that explicit negative
coverage control prevents an all-plane runtime-verification claim. Relaxed
late-query prism overlap also agrees with independent joint convex feasibility.
Pure invocation skips the eight retained-native tests; skips are not runtime
evidence. Clean exact-commit OFFLINE reproduction uses the existing immutable
arms; this does not claim a new native build/run or renewed engine verification.

Only this fixed identity/world/standing-AABB plane-set comparison is closed.
General triangle support **ABSTAIN**, arbitrary native semantics **NOT_TESTED**,
physical-exit/classifier/render/hold acceptance **NOT_TESTED**. No product patch,
engine pin/tag, QC Build, installed program, deployment or release changes.

## Exact bounded front-triangle reachability and derived gap algebra

`offramp_trisupport.py` builds a separate zero-thickness FRONT-surface model.
It consumes the retained bevel-PM arms through all prior gates and preserves the
complete preceding plane-set report. It neither launches nor instruments an
engine. Use NEW report paths under an owned private task root:

```
python -B tools/offramp_trisupport.py --arms <retained-bevel-PM-arms.json> --output <new-private-report.json>
python -B tools/test_offramp_trisupport.py --native-arms <retained-bevel-PM-arms.json>
```

For supplied upward-wound finite triangle xyz and a fixed translating AABB,
construct the closed feasible domain of `origin=start+t*(end-start)-d*Z`,
`0<=t<=1`, `0<=d<=D`. Complete triangle/AABB SAT uses xyz, triangle normal and
triangle-edge cross xyz axes. Unnormalized rational axes and exact halfplane
clipping introduce no geometric epsilon, native bias or four-unit back slab.
Inputs are exact rational interpretations of serialized finite decimals, NOT
exact underlying float32/native physics. Output rationals are reduced fraction
strings; constraints, domain vertices, parameter bounds, downward-distance
range and coverage interval remain explicit. Zero horizon and degenerate
segment/point domains retain closed touching, not invented penetration.

A second construction requires a COMMON triangle point in the translated box:
nonnegative barycentrics summing to one, with all xyz box inequalities satisfied
simultaneously. Exact Fourier-Motzkin elimination projects barycentric variables
onto the same t/d domain. This construction has no SAT axes or native planes;
it shares the exact polygon-clipping primitive, not an independent arithmetic
implementation. Domain/projection equality is required. Independent spatial
barycentric clipping supplies xyz/common-point witnesses at every domain vertex
and sampled body, with legal downward distances. Analytic fixtures and spatial
grid checks additionally test the shared arithmetic.

The diagnostic reports 96 captured body samples, 96 explicitly DERIVED linear
command-endpoint segments and 18 captured accepted-contact REQUEST domains.
Authored fixture-front geometry and copied winning-front geometry have separate
labels and provenance. A captured attempted sweep is not the final collision-
clipped body path. Removed geometry can remain counterfactually reachable but
never becomes live supplied-patch coverage. D=2 simply binds the existing down2
query horizon, not a physical-support/classifier constant. Horizontal footprint
loss, vertical reach loss, initial overlap and mathematical surface intersection
are not automatically standable or load-bearing contact. Vertical/downward or
degenerate triangles, nonfinite coordinates and invalid hulls/horizons refuse;
no capsule/transform/entity/embedded/posture substitution is introduced.

`patch_coverage` unions only EXPLICITLY SUPPLIED triangles, never presumed map
neighbors or reconstructed topology. The complement preserves every positive
gap and endpoint inclusion. Tests cover partial footprint support after center
exit, diagonal-corner refusal despite independent axial overlap, contiguous
patch handoff, short gap/recontact, removed-neighbor suffix loss, vertical lift
and exact zero-measure contact. Both endpoints can be reachable while the
interior is not; tiny positive gaps are not rounded away or silently dwelled.
The converse alias (unreachable endpoints, reachable interpolated interior)
also ACTS on a retained trajectory. Neither alias establishes actual sub-command
movement. Derived gap durations do not define a hold threshold or physical
exit timestamp. No dwell or exit policy is implemented.

Twenty-five tests (17 pure, eight retained-native) include 40 deterministic
random domain comparisons with 480 spatial-grid checks, 288 sampled domains at
registered horizons 0/2/8, 270 copied-xyz/hull binding refusals, 15 fixture/mode
manifest refusals and two ACTED retained-trajectory geometric construction
mutants with unchanged predecessor reports. Binding refusals are not independent
native-semantic verification. Missing diagonal axes, replacing front by back,
concealing an expanded horizon or using center-only footprint ACT in pure
geometry tests. Pure-only invocation skips retained tests; skips are not runtime
proof. Clean exact-commit reproduction is OFFLINE reuse of retained captures,
not a new native build/run, generalization or deployed acceptance.

General triangle support remains **ABSTAIN**; standability/load-bearing contact,
complete discovered neighborhood topology, physical exit, native equivalence,
classifier/render/hold/clock acceptance remain **NOT_TESTED** or **NOT_IMPLEMENTED**.
No product patch, engine pin/tag, QC Build, installed progs, deployment or release.
