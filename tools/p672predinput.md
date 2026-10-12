# Patch 672: native replayed pre-input seam

This is an engine interface, **not completed reset/load/hold-release/rewind
prediction**. Normal `cl_progs.src` does not include the test callback.
No server, timer, recorder, evidence grammar, ranking or Build policy changes.

## Contract

Optional QC callback:

```qc
void(float seat, float sequence, float seconds, float offsetseconds)
CSQC_PredictPlayerPreMove;
```

It runs only in the local replay chain with a loaded world, an access-allowed
CSQC module, `cl_predict_qchook 1`, and no listen server. It is before carrier
cash-out and `PM_PlayerMove`, after native baseline Source, command and hull
state initialization. The existing `CSQC_PredictPlayerMove` trigger callback
stays after movement. Both callback durations are seconds (despite the older
hook's prototype naming its argument `msec`).

Each invocation seeds these independent globals from the current native piece:

| Global | Seed / selected meaning |
| --- | --- |
| `float predinput_apply` | 0; explicit edit-mask below |
| `vector predinput_origin` | current origin; BODY replacement |
| `vector predinput_velocity` | current velocity; BODY replacement |
| `float predinput_onground` | current ground; BODY must be exactly 0 or 1 |
| `float predinput_pmtype` | current mode; MODE must be an integer PM_NORMAL (0) through PM_6DOF (8) |
| `float predinput_forceduck` | 0; DUCK must be 1 stand or 2 duck |

Mask bits: **1 BODY**, **2 MODE**, **4 DUCK**, **8 HOLD**, **16 CLEARCARRIER**.
The mask must be an integer in 0..31. All selected payload is validated before
any edit or carrier clear. Missing requested globals, NaN/Inf coordinates or
velocity, invalid booleans/enums/posture and invalid masks reject the entire
transaction and emit a developer diagnostic. Missing callback/apply/module,
disabled cvar and excluded chains do not call the callback. Zero-mask writes
are ignored; unused globals are optional. A callback invocation is NOT server
admission, successful execution, an ACK or baseline coverage.

BODY sets only origin, velocity and onground; view angles, gravity, jump,
waterjump, Source history and command input remain separate. It invalidates the
mover's safe-origin hint. MODE persists into the output player state. DUCK
applies the server's completed-posture policy: ducked, ducking=false, ducktime=0;
it does not restore historical stamina, ladder, carrier, hull or duck animation.
The real mover subsequently derives the hull.

HOLD sets **only the native copy's command duration to zero**. The network
command and logical split budget are unchanged. It skips the CSQC post-trigger
callback, but still saves the carrier's final consumed state. It does not
choose PM_NONE, zero velocity, clear a carrier, freeze a server clock or prevent
all mover housekeeping. Combine separate restrictions deliberately. Save-style
MOVETYPE_NONE with regular elapsed ticks is NOT equivalent to this flag.

CLEARCARRIER clears the immediate and held/armed carrier before old cash-out.
It writes current sequence state without deleting earlier replay history. Later
pieces of the same logical command consume current within-command state rather
than restoring the pre-operation sequence-1 carrier; a fresh post-trigger push
may still arm and be consumed. Without CLEAR, legacy splitting behavior remains
unchanged.

## Replay and split discipline

`seconds` is this subpiece's original duration; `offsetseconds` is its position
within the logical command, not the render frame. Both preserve fractional
milliseconds: 51 ms splits into 25.5 ms pieces. Existing >500 ms input clamping
is unchanged. Offset zero selects the first substep on **each replay**. A
consumer may apply a body/mode/posture transition only there, and apply held
restrictions on every relevant piece. The engine does not enforce that consumer
policy. Never use a render-lifetime apply-once latch: the same sequence is
reconstructed repeatedly from a baseline. Sequence is marshaled as the existing
QC float; large-integer precision, connection/map epochs and request identity
are NOT supplied by this hook.

Before production frontend activation, build server-prepared complete state
and generation-aware descriptors, bounded ordered/scoped requests, explicit
server admission/application, and reconciliation against the authoritative body
baseline that contains an operation. A processed SaveLoc ACK alone cannot retire
it. ACK-before-body, refusal, stale destination and competing operations remain
follow-up work in ROADMAP.md. The new optional hook is ignored by an older engine;
a real future consumer needs an explicit capability/fallback policy.

## Acting tests and limits

`tools/test_predinput.py` extracts the actual production application helper,
CSQC bridge, carrier consume/save and CL prediction recursion; compiles against
real engine headers using `compile_commands.json`; and supplies controlled VM
and **linear mover doubles**. It does not duplicate the production seam, but it
is NOT a collision-physics, network-authority or hostile-VM registration test.

Ten groups cover default reseeding/no-mask writes, disabled/absent/nonlocal/listen
controls, body-before-move/mode writeback, 0/.5/50.5/51/100.75/101/255 ms split
replays and selected output equality, clear-before-cashout/fresh re-arm, held-only
and mixed-split ring commits, invalid/missing payload atomic rejection, completed
stand/duck and preservation of unrelated Source fields at the helper boundary.
Direct invalid-adapter arms compare whole mover and carrier-history bytes.
Access-restricted discovery is source-reviewed only. Multi-seat/wrap behavior,
complete historical Source restore and all real physics/carrier-trigger cases
are not certified here.

```text
python C:/FTESurf/tools/clangdb.py --engine <owned-engine>
python tools/test_predinput.py --engine <owned-engine> --out <owned-root>/artifacts/unit
```

For the runtime fixture, use paired clean worktrees and the workspace contract.
Build standard programs and full native/plugin outputs with pwsh 7 from `src/`:

```text
./build.ps1 -Engine -Full -Jobs 8 -NoDeploy -FteRoot <owned-engine>
```

NoDeploy retains progs in the printed isolated output directory and native
outputs in the paired engine's release directory. Copy the three progs into the
owned QC worktree's `ftesurf/`, never a live install. Make an **untracked scratch**
copy of `src/cl_progs.src` with `../tools/fixtures/predinput.qc` appended, then run
`fteqcc64.exe -srcfile <scratch>.src` from src. That writes only the owned
worktree's fixture csprogs. It must compile with zero warnings. The normal
production source manifest is unchanged.

```text
python tools/runlines_smoke.py ftesurf/cfg/test/p672predinput.cfg --output-dir <owned-root> --dedicated --map surf_dune --mount --client <owned-engine>/engine/release/fteqw64.exe --server-arg "+sv_minping 100" --port 27617 --timeout 100
python tools/test_predinput.py --log <printed-rig>/ftesurf/logs/runlines_smoke.log
```

The strict grader requires acting no-op and legacy post-trigger probes, BODY
placement followed by moved native next-subpiece origin/velocity, HOLD followed
by identical native origin and committed PM_NONE, a disabled window with an
independent native prediction-trace heartbeat, callback return afterward, and
completion/no VM or command errors. It reads **entry** values captured before
fixture edits, not requested PLACE/mode output. Missing-arm counterfactuals must
fail. A second run of the same fixture with the installed older client plus
`--log ... --old-engine` proves it ignores the optional callback while its
legacy hook acts. Neither arm claims SSQC accepted a placement.

Prepublication dedicated surf_dune/100 ms controls: 2,070 no-op probes, 117 moved
body pieces, 44 held pieces; disabled native trace and re-enabled callback acted.
Old-engine fixture control passed. Two read-only subagent reviews exposed and
closed missing held-piece carrier commit and fractional-offset coverage defects.
The initial runtime's early `ui_close` failed before menu initialization; it was
removed because this fixture makes no HUD/menu claim. That failed log is retained,
not counted as a pass. Fixture programs and scratch source are never deployed.
