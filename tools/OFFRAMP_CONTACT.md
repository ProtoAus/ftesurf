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
sample's exact ordinal/time/position. Its rendered marker must retain the stored
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
