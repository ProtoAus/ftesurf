# Human-first surf TAS editor

Requested by Lex after trying the existing workshop, 4 November 2026.
**Status: work in progress, 6 November 2026.** The controller foundation, full
captured local line and P1323 literal input templates are installed BOTH Windows
and all 12 lobbies; exact receiver/source evidence and limits are in
[the input-template qualification](p1323-tas-recipes.md). Historical local control
settings now have an implemented, runtime-checked P1329 candidate; its review and
live delivery are separate in [the settings contract](p1329-tas-settings.md).
Contact sections and the constrained next-ramp solver remain unfinished. The
complete workflow below is NOT delivered.
This changes the local-editor priority in [the original TAS plan](plan-tas.md),
not its assisted ancestry, contribution or verified-board requirements.
Owner observations are recorded separately in [lextest.md](../lextest.md).
Lex approved this design direction on 4 November and added crouched strafing and
automatic vertical aim following travel. This approves the plan, not unbuilt
product behavior or numeric physics claims.

## 1. The product we are building

> Play a line normally. Pause. Go back to the part that went wrong. Hold left
> or right, turn a little faster or slower, advance or recalculate, and compare
> the result. Going back must also bring back that moment's editing settings.

The main screen is a surf controller and a navigable line, not a usercmd form.
Exact angles, raw movement magnitudes, signatures and numerical solver controls
remain available under Advanced; they must not be prerequisites for basic use.

Lex found movement left/right, auto strafe and frame advance useful. He found
that the gain-oriented turn did not turn sharply enough to stay on his ramp,
and reported about 275 ground speed with forward+right where he expected about 289.
These are genuine owner observations, not measured thresholds or proof of the
cause. The exact ground rules/state and a reproducible example remain to capture.

### Non-negotiable user outcomes

1. Normal play -> Pause -> select earlier ticks -> recalculate the previous line.
2. Forward/left/back/right laid out like arrow keys; left/right dominate the UI.
3. Movement buttons and assisted turning are independent controls.
4. Fine control of turn rate relative to a gain-oriented reference, including
   turning MORE sharply to remain on a ramp. No required absolute-angle snaps.
5. Keep the whole captured run/project, not just the current tiny edit window.
6. Seek/back restores the associated control settings, not today's stale draft.
7. Browse another run's timeline without claiming missing inputs or state exist.
8. Later: navigate and improve start/jump, air, ramp, air, ramp sections.
9. Handle standing/crouched strafes and duck transitions using actual mover rules.
10. Optional automatic vertical aim: look up when climbing and down when falling,
    without taking over the important left/right yaw control.

## 2. Inspected baseline on 4 November (not current delivery status)

Source inspected: QC origin/main3b132f12; native published origin/main6924bf32.
The canonical native checkout is on older historical source, so its absence of
modern TAS headers is NOT evidence that the published feature is absent.

- `sv_tasinput.qc::SV_TASInputRead` requires a retained exact warm checkpoint.
  `SV_TASRecalculate` limits the affected tail to128 ticks. The timeline page
  clamps browsing to that same tail. This is not a full-run editor even though
  projects already retain more input rows.
- `sv_tasproject.qc` already has project buffers, legal-start sessions and a
  96000-row cap. Reuse these contracts; do not invent a second project format
  or silently remove resource bounds.
- Native `engine/server/sv_tas_strafe.h` explicitly optimizes an observed-state
  AIR acceleration objective. `sv_tas_plan.inc::SV_TASPlanOverlay` uses the
  preset on ground/unsupported states. In an admitted air case it overrides
  movement to pure A/D at full key strength. It is not ground optimization,
  a fixed turn-rate controller, collision lookahead or ramp/path optimization.
- The current UI does explain that air uses450-side and ground uses the preset,
  and reports air-selector versus preset/live. Nevertheless the overall
  interaction did not communicate/usefully solve the owner's surf task. Do not
  invent a missing status label or treat relabelling alone as a ground fix.
- `sv_tasoptimize.qc` searches bounded constant rates/boarding/flick parameters
  on the actual mover. Its speed objective can prefer a bad onward route;
  its128-tick tapes, world-time dependence and finish/rollback limits remain.

Thus: previous recalc is a restricted existing capability with poor reach/UX;
full-history recalculation, adjustable assistance and section solving are NEW
work. None is solved just by rearranging buttons.

## 3. Proposed default screen

```text
TAS: My line / Working copy       Pause | Play       Undo | Redo
Tick 1842 / 6400     Time 27.630     Speed 1250     Ramp 2

                  [ Forward ]
         [ Left ] [  Back   ] [ Right ]      [ Jump ] [ Duck ]

Turning: [ Manual ] [ Auto strafe ]     Direction follows Left/Right
Turn amount:    -   [---------|---------]   +       1.20x
                gentler   1.00x reference   sharper
Status: air-gain guide / ground-gain guide / preset / unavailable
Vertical look: [ Manual ] [ Follow travel ]

[ Back 1 ] [ Forward 1 ] [ Step 8 v ]  [ Play slowly ]

Start -- Jump -- Air -- Ramp 1 -- Air -- Ramp 2 -- ... -- End
                   [ selected interval ]
[ Go to selection start ] [ End ] [ Recalculate ] [ Compare ]
[ Keep result ] [ Discard result ]                    [ Advanced ]
```

Labels/numbers are a mockup, not current game commands or measured values.

### Direction pad and stepping

- These mean `+forward`, `+moveleft`, `+back`, `+moveright`, NOT yaw-turn
  commands `+left`/`+right`. No bind/config-file rewrite.
- Buttons latch visibly for authored ticks; allow forward+left/right, including
  ground prestrafe. Opposed pairs cancel visibly, as normal movement does.
- Default surf operation is A or D. Back/forward remain available; no raw450
  number entry. Auto turn follows the chosen left/right direction, so choosing D
  does not require a second "Auto right" mode. No selected direction means no
  automatic turn unless an explicit Advanced override is active; display it.
  Preserve captured analog values rather than pretending every historical command
  was a full digital key press.
- Jump/duck are secondary. View direction can follow normal mouse aim; using
  assisted turning must not require repeatedly copying a yaw into a form.
- One-step, small configurable batches and hold-to-step have bounded execution;
  releasing/cancelling must not leave movement or queued work stuck. Keep the
  exact last queued/executed tick visible. Physical key releases predating the
  panel must still reach their owner; do not regress the existing input fixes.

### Fine turn adjustment, not angle snapping

- **Auto strafe** is the familiar primary toggle; its gain guide/reference and
  applied air/ground/fallback state are explicit, not a claim of global optimality.
- `1.00x` is a documented, state-appropriate gain-oriented turn-rate reference;
  `0.85x` is gentler and `1.20x` sharper in the chosen turn direction. These
  are illustrations, not a claim that 1.20x yields 20% more speed.
- Scale the yaw CHANGE/rate per physics tick, never the absolute compass yaw.
  Readouts may show degrees/tick or degrees/second under Advanced, but the normal
  interaction is a fine slider, +/- and reset-to-1.00x. Proposed fine nudge 0.01x,
  modifier 0.001x, coarse 0.10x; final range/feel is tuned with Lex on one ramp.
- The current selector returns a best heading, not a rate. Before coding the
  multiplier, define/test the reference from actual mover/key-mask behavior.
  Preserve the current view when enabling it; no hidden initial 90-degree snap.
  Smooth alignment is allowed to sacrifice immediate gain. Do not promise both
  instant maximum gain from an arbitrary heading and no initial direction jump.
- Support independent direction and button state: forward+right must not become
  pure right just because turning assistance is enabled. A changed key mask
  requires the appropriate reference, not the old pure-A/D formula reused blindly.
- Faster turn trades some immediate gain for trajectory control. Show speed/gain
  and trajectory; don't silently clamp the user's sharper turn back to the
  greedy-air optimum. No claim that the reference keeps a player on a ramp.
- Air gain, ground gain and ramp/contact-aware objectives are distinct. If a
  guide is unavailable, show exactly what is applied; no falsely advertised
  optimum on a preset or unsupported friction/water/ladder/transition state.

### Crouched strafing is part of the controller, not just a duck button

- Keep Duck visibly selectable for a tick/range and restore it on seek/load/Undo,
  including the actual transition state from historical mover state/replay, not
  unchecked editor metadata. Requested duck, fully crouched, part-way down/up
  and blocked unduck are not interchangeable. A smaller hull can change
  ramp/ceiling contact and therefore the resulting line.
- Inspect the production mover rather than assume a lower crouched
  `airaccelerate`. Native source be4e3072: `PMSrc_HandleDuckingSpeedCrop` crops
  inputs only for `ducked && onground`; `PMSrc_AirMove` passes the ordinary
  `movevars.airaccelerate`, and `PMSrc_AirAccelerate` has no crouch multiplier.
  Airborne crouch therefore does NOT receive that ground-only crop. Existing
  source tests explicitly cover the difference. This source finding is not a
  new measured guarantee that crouch never affects a surf trajectory.
- Compute references from effective state/rules, key mask, wishspeed, friction,
  clock and contact, not a guessed blanket duck penalty. Ground crouch needs the
  real cropped inputs; air crouch must not accidentally use the ground model.
  Include entering/leaving a ramp or ground contact during duck transitions.
- Compare standing/crouched air strafes from matched supported state, then actual
  crouched ramp routes and grounded combined-key cases. Prove Duck executes and
  the hull/transition changes where appropriate. Check both clocks and a
  deliberately cropped-ground control; identical output in one capped air case
  is not proof of globally identical behavior or absence of a binding-rate case.

### Automatic vertical aim: Follow travel

The request is to follow the vertical DIRECTION of travel, not to derive yaw
from velocity or bank the whole screen. Left/right yaw remains the primary
manual/strafe control. Keep the horizon level by default.

- Add **Vertical look: Manual / Follow travel**. The target inclination follows
  actual travel: upwards on a climb, near level through an apex, down while
  falling. In the normal world-up convention, the reference is
  `atan2(vertical velocity, horizontal speed)`; convert to the engine's pitch
  sign (negative looks up). Do not use yaw-turn rate as vertical inclination.
- Smooth changes and limit pitch/angular rate to comfortable bounds, with a
  configurable strength/offset under Advanced. No collision-driven camera
  chatter, snap on enabling, upside-down roll or rapid near-vertical oscillation.
  At negligible travel speed hold the last useful pitch or ease gently neutral.
- Use accepted physical travel velocity, including a verified carrier
  contribution where applicable, not a teleport displacement or render-frame
  estimate. Reset/reseed at portals/warps and restore the historical state on
  seek. Do not blend across unrelated branches or treat a rewind as falling.
- Default to a clearly labelled VIEW/PREVIEW convenience: never alter yaw,
  movement keys, gain targets or an immutable run's recorded angles. If authored
  head motion should appear in a saved/exported TAS, expose an explicit record-
  pitch option and generate ordinary input pitch through the existing validated
  path. Cosmetic camera motion and recorded command pitch are distinct.
- Save the mode/strength/offset with the tick's editing recipe. For deterministic
  recorded pitch, evaluate smoothing on physics ticks and preserve/reconstruct
  its state across checkpoints/chunk boundaries; never use wall-clock or render
  FPS. Existing raw pitch rows remain truth on unchanged replay.
- Mouse vertical input can temporarily override/release automatic pitch without
  changing horizontal control; resume is smooth and explicit. Crouch eye-height
  interpolation remains owned by the existing mover/camera, not counted a second
  time as auto-pitch. Genuine server corrections retain their existing ownership.
- Acceptance: climbing ramp, apex, falling air, standstill, duck/unduck and portal/
  seek transitions. Show actual pitch and unchanged authored yaw/inputs with
  follow on/off; a physically operated owner check settles comfort/readability.
  A recorded-pitch option additionally needs same-state movement/arrival controls,
  especially combined forward/side inputs and nonstandard movement states. Do
  not assume every ruleset treats pitch as physics-neutral just because the
  normal published `PMSrc_WishDir` flattens/normalizes forward/right horizontally.

## 4. Play normally, then revise a previous line

1. A local editing session captures effective executed inputs from its beginning
   while normal physical controls remain normal. Remove console-only setup from
   the normal workflow where support permits. A current unsupported recording
   gets a useful reason/action, never a silent mid-run change of recorder mode.
2. Pause opens at the actual head. The full timeline remains visible, with
   hover/click tick/time and a range selection. Offer both dragging and precise
   tick/time entry; no requirement to type raw `tas edit` commands.
3. Seek to an earlier tick using verified state restoration/replay. Simply
   selecting a row/ghost is read-only; it must not teleport the live body.
4. Change direction/turn settings for the selected interval. Preview regenerates
   effective commands INSIDE that interval, then simulates the affected tail.
   By default, commands outside the edit stay unchanged. Re-evaluating later
   assist recipes is a separate explicit operation, not a hidden cascade.
5. Keep the original as a comparison ghost/immutable working parent. Show the
   candidate's line, speed and downstream arrival; Keep/Discard, Undo/Redo and
   cancel must not destroy the previous good line. Persist a recovery revision
   before risky long operations. A finish during preview is an explicit tested
   case, not an event allowed to strand the editor.
6. Resume normal play from the selected/candidate state, or step further.

Distinguish **Replay unchanged**, **Recalculate edited interval** and later
**Improve section**. Recalculate does not mean a solver has found an optimum.
When a changed line reaches a different ramp/zone, show that divergence; do not
paste the old endpoint or silently discard inconvenient trajectory changes.

### Full tick history and responsive long replay

- Store every effective input row for the captured session within explicit
  duration/storage caps, using the existing project/journal data where possible.
  A full-run browser must not inherit the native128-tick execution window.
- Index/page long histories. Retain canonical inputs plus sparse validated replay
  checkpoints/caches, not a complete duplicated world snapshot for every tick.
  Execute long replays in bounded chunks with progress/cancellation and a known
  original branch. Do not expose unlimited memory/CPU as a requirement.
- Display total available extent and any actual gaps/limit before editing. Never
  silently evict the beginning while displaying the run as fully editable.
- A cold seek may replay from a legal start or qualified project base. A row of
  origin/velocity alone is not a restorable checkpoint; preserve timing carry,
  movement/recorder/trigger context and supported world-state constraints.
- REC14 streamed historical restore is currently unsupported. This work must
  either implement/qualify that complete contract or use a supported complete
  project replay path. No fabricated warm state, nearest-pose substitute or
  metadata copied from the current head into a past tick.
- Keep10ms and15ms clocks explicit. Run tick, placement tick, command duration,
  subtick carry and render frames are not interchangeable.

### Restore settings as well as the body

Each authored interval has an editing recipe: movement/key mask, assist mode,
turn direction/multiplier, requested jump/duck, vertical-look mode/settings and
any intentional manual/recorded aim behavior. Physical duck-transition state is
restored by the qualified movement-history path, not trusted from this recipe.
Store both that recipe and the ACTUAL executed commands. Commands remain the
replay truth; an assistant algorithm update must not silently rewrite old work.

P1329 uses the completed tick T's known settings in Controls, consistent with
native warm back/seek. New steps inherit that recipe until an explicit edit or
local look change. Timeline row T+1 remains the next input, not a second name for
these controls. Selecting a raw row without seeking does not restore its recipe.
A separate outgoing-T+1/selected-row procedural display remains proposed UX, not
implemented behavior. Back/seek, project load, branch switch and Undo/Redo restore
the implemented completed-tick state consistently.

For physical-play rows that never had a recipe, display **Recorded input** with
its observed keys/aim; do not invent an old 1.00x helper setting. Turning those
rows into an assisted interval is an explicit edit. New ticks after the old head
inherit the last applicable recipe, visibly.

P1329 deliberately uses optional hash-bound ranges in a new version4 local base
project, rather than a mutable unbound sidecar. Legacy versions1/2/3 retain their
existing hashes and literal/unknown semantics; legal-start3 and literal templates
do not gain invented procedural settings. Unsupported version5 is refused.
Metadata confers no body, native permission, evidence or input-row contribution
credit. The schema/hash contract and limits are explicit in the settings document;
this is not an incidental UI-format bump or a new signing authority.

## 5. A timeline for other runs

Use the same browser for a current attempt, completed local/native recording,
saved TAS revision or imported replay, with an honest capability label:

| Available data | What the editor may offer |
|---|---|
| Complete effective inputs, supported start/base and replay context | View, fork, seek/replay and edit a TAS working copy |
| Inputs but missing exact start/context | Input inspection; editing disabled with the missing prerequisite named |
| Position/velocity samples only (some imported runs) | Time/sample playback, trajectory and section inspection; no invented keys or exact native ticks |

Preserve each source's real clock. Source frames/samples must not be relabelled
as exact native physics ticks. A future input-reconstruction tool would be an
explicit estimated TAS, not the original player's commands. Opening/forking never
modifies the original recording, human-board result or imported record. A fork
from a normal run may remain a local base-save project; it does not acquire a
portable legal start or board eligibility merely because its inputs were copied.

## 6. Ground prestrafe is a separate correctness task

Reproduce Lex's forward+right example before deciding whether 275 is a bug,
a preset limitation, mismatched rules or a different supported maximum. Capture
actual horizontal speed, executed forward/side and yaw, grounded contact,
friction/stamina/weapon-speed state, effective movement settings and tick rate.
No jump/booster/air tick may masquerade as a ground-speed improvement.

Implement a ground-gain guide against the actual production ground mover,
including friction, acceleration and combined-key wish direction. Preserve the
selected keys. Check immediate gain AND the sustained runway/turn trajectory;
a one-tick winner is not proof of the highest sustainable ground speed.

Use an acting manual/prestrafe control under the identical state/rules and a
bounded exhaustive yaw/reference comparison. Reach approximately 289 only if that
control establishes it is reachable there. Otherwise report the actual scoped
maximum and the reason; never change physics or hardcode 289 to satisfy the UI.
The current air guide can remain useful without being advertised as ground-optimal.

## 7. Later: sections of the recorded route

Sections belong to a particular line/revision, not a universal static partition
of the map. Start with manual markers, then propose automatic sections:

`Start approach -> jump/takeoff -> air -> ramp1 -> air -> ramp2 -> ... -> finish`.

- Detect ramp boarding/leaving from actual mover collision/contact information
  (surface normal and relevant surface identity), not `FL_ONGROUND` alone:
  surfing a steep ramp is often classified as airborne. Keep real contact edges;
  tolerate seams/tiny gaps in presentation without deleting the underlying events.
- Allow split/merge/rename/move-boundary overrides. Do not merge distinct ramp
  faces or routes just because their normals look similar. Annotate ambiguous
  multi-contact/transition ticks and unsupported moving-world cases honestly.
- Previous/next section and Start/End restore the appropriate exact state via
  the same seek/replay mechanism. No `setpos` shortcut.
- Change a line -> invalidate/recompute affected proposed boundaries while
  preserving the original section map for comparison. Do not attach stale
  "Ramp2" settings to a different contact after an edit.

### Improve a ramp or air section

Build on existing constant-turn/boarding/flick searches, after the hands-on
controller is useful. Most ramps can start with one constant/low-parameter turn
recipe; air sections can use a small sequence of strafe turns. Add complexity
only when a measured route needs it.

Offer explicit goals: keep/improve this line; exit speed; travel time; or arrive
well for the next ramp. A candidate must satisfy the chosen exit/boarding region,
direction and safety constraints before its speed is scored. Include limited
lookahead into the next section: maximizing exit speed while missing the next
ramp is not a winning candidate. Never assume maximum speed means best time.

Compare the unchanged source, a valid slower candidate and a faster-but-missing
candidate to prove the constraint actually acts. Search is bounded; report best
FOUND under displayed constraints, never globally optimal. Keep progress,
stop/cancel, best-so-far and explicit acceptance. Solver output remains TAS.

## 8. Delivery order and falsifiers

The owner request is a PLAN, not authorization to claim any implementation or
acceptance. Suggested implementation order:

| Slice | Deliverable / acceptance that must ACT |
|---|---|
| 0. Fast owner layout check | Show a small directional-pad/turn/timeline mockup. Lex can identify forward/A/D/back, change turn sharpness and understand the selected range without raw angles. Use a five-minute human check, not a new UI-test framework. |
| 1. Human controller and recipe state | A/D and W+D remain selected under assistance; turn multipliers visibly change yaw/trajectory without a snap. Duck/unduck uses real state, not a guessed air-acceleration penalty. Optional Follow travel pitches up/down without taking yaw control. Back/load/Undo restore settings and transition/filter state. Ground fallback remains explicit. Pilot one familiar ramp early. |
| 2. Complete normal-play editing loop | Play a captured line LONGER than128 ticks and beyond the warm ring, pause, edit an early interval, replay to the old head, compare/keep/discard, save/reload and resume. Unchanged replay must match the scoped control; an intentional key/turn edit must visibly act. Entire captured extent stays browsable. Complete this before calling the first full-workflow milestone delivered. |
| 3. Ground guide | Same-state manual and old-preset controls act; real ground acceleration/steady-speed comparisons prove selected W+D is retained and the claimed improvement occurs at both supported clocks. Lex's reported case is repeated; numeric289 is not assumed. |
| 4. Section navigation | Manual markers first, then actual air/ramp contact edges on a familiar two-ramp line; jump Start/End and back across boarding restore the right body, tick and controls. Boundary changes on an edited route invalidate old labels. |
| 5. Constrained section solver | Real ramp and air candidates; a fast missed-ramp candidate loses to a valid one, original input line survives cancel/finish/failure, next-ramp arrival acts and the owner finds the result useful. |

Slices1/2 may share foundation work, but a cosmetic pad or another128-tick demo
is NOT completion of the requested normal-play/full-history workflow. Ground
correctness remains explicit; do not hide it behind completion of the air pilot.
Public submission/board work stays separate and preserved; it does not block
local UX or become the priority merely because its infrastructure already exists.

### Required regression/safety gates when implementation begins

- Native input/controller tests plus real dedicated-socket client controls;
  screenshots/physical-device feel confirmed by Lex for the surface he observed.
  Reuse existing native strafer/tape tests and a small real-map check; do not
  spend the feature effort constructing a new proof framework.
- Both clocks, frame/net cadence, angle wrap, left/right symmetry, zero speed,
  combined/opposed keys, standing/crouched/transition/blocked-unduck states,
  contact changes, input release and enable/disable. Follow-travel pitch covers
  ascent/apex/descent, yaw independence, manual override, portal corrections and
  seek/cold-load/filter continuity; camera-only on/off must not change commands.
- Whole-history/chunk boundaries, branch/undo, cold seek, partial/malformed data,
  cancellation, storage limits, disconnect and natural finish. Missing exact
  context refuses before mutation. No fake unchanged-input pass based only on
  matching rounded pose/velocity where stronger existing replay evidence exists.
- Preserve original input rows outside the selected edit; metadata and preview
  cannot taint or rewrite an original human run. Passive capture must preserve
  ordinary input/evidence semantics. Pausing/simulation control retains existing
  TAS classification; apply ancestry before any restored, authored or replayed
  movement and never clear it on exit. An unfinished attempt that used TAS pause
  cannot resume as a clean human-board run just because its old line was retained.
- Dynamic/time-dependent world behavior remains scoped: detect/report supported
  limitations, retain original work and refuse unsafe replay rather than claiming
  every map is exactly rewindable. Read the recorder/verifier/private contracts
  before any implementation that changes evidence or historical-state semantics.
- Standard clean-source builds, zero NEW warnings, required recorder-reader and
  paired-corpus controls for evidence changes, dual deployment/provenance for
  actual product work. This document changes no executable, schema or deployment.

## 9. First concrete implementation target

A local line with one ramp and its following airtime: play it, pause after the
ramp, select an earlier interval, choose A/D and a sharper/gentler turn, preview
and compare, back to that tick with settings restored, then save/reopen the
working copy. Use that result to tune the interface before broad solver work.

Still needed for measurements, NOT blockers to this plan: Lex's preferred test
map/ramp and exact ground-prestrafe setup. Slider fine/coarse defaults and
assisted-enable smoothing are provisional until that small owner check. No
request to repeat permission for already approved general development/deployment;
this task itself is documentation, not a runtime rollout.
