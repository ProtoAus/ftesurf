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

Protocol `OFFRAMPMOTION_` v4: BEGIN capture/oracle/case counts and maximum step
capacity, explicit per-CASE step counts (first six 32, open posture 96, ceiling
posture 192, capsule 32, transformed 32), SOURCE
fixture-template SHA256 and native base commit, exact ordered PARAM rows
(including explicit rotated-box-hull cvar), CASE/BRUSH/PLANE/SEED, INSTANCE
only for the transformed case, ordered TICK and ORACLE rows, CASE_END, END, COMPLETE.
TICK carries actual command inputs, native tick count/rate, ramp/ground state,
body/velocity, hull/posture. ORACLE carries case/tick/kind/brush, exact endpoints,
fraction/solid flags/entity/plane/contents. Missing/duplicate/reordered/unknown/
malformed rows, changed input/provenance, nonfinite data, unregistered hull/pose,
wrong bindings, quiet subject or failed actor/native query all refuse. Named
capsule/transformed cases are structurally validated but explicitly ABSTAIN
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

Exact physical exit time, classification/debounce/mark policy, embedded/
non-world/entity/triangle/displacement, airborne or other posture trajectories,
explicit cached/recovery/portal motion, general world support, independent
capsule/transform geometry, P560 clock and same-input recorded/live/render/rate/
camera/LOD/hold acceptance remain **NOT_TESTED**.
