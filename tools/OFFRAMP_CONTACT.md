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
