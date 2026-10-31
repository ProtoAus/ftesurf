# P1154: native TAS clock contexts

Local TAS movement can use an exact Source interval of **0.010** or **0.015**
seconds. The ordinary/default interval remains unchanged. This is not a new
human-run category or a canonical TAS qualification claim.

## Operator setup

Select the supported mover configuration and `pm_ticrate` **before loading the
map**. The timer latches its interval in `SV_TimerMapInit`; changing the cvar
later does not create a new timer timeline. Use `tas on`/a fresh legal-start TAS
session before beginning a recording. A running human REC14 stream is not
silently converted into a rewindable practice recording.

`tas status` reports:

- Native admission, pause/pending/completion and monotone movement counters.
- Fractional movement carry.
- The last admitted mover interval, the map's latched timer interval, native
  rewind capability and timer state. The last mover interval is not a replacement
  for reading the current configured cvar after native admission is blocked.

A mover/timer mismatch refuses authoring and base-save project placement/replay
before new grants. The ordinary step/input gate and both project-load branches
share the same map-clock preflight; base-save loading checks it before reading
the project or moving/pausing the body. An observed native
rate change invalidates the connection/map clock context, clears marked queued
work and prevents a return to the previous rate from reviving it. Use a fresh
connection at the matching map interval, or reload the map for a deliberately
changed timeline. A mere reconnect does not relatch the map's timer.

Unsupported intervals, adjacent float values, non-Source/unsupported drivers,
invalid carry and unsupported global speed remain outside TAS admission. Normal
movement is not turned into TAS or stopped merely because TAS is unavailable.

## Implementation

`SV_TASTickMsec` maps only exact supported intervals to10/15ms. The command grant,
carry validation and native rewind/input entrypoints share the selected interval
and connection/map-bound clock context. The actual planner already uses current
movevars; it does not receive a new movement formula. Existing TAS ancestry,
bounds, native checkpoint ownership and current-world limitations remain.

## Verification and limits

- Expanded portable actual-C admission/input/queue controls:100262 checks pass;
  exact/adjacent/invalid intervals, carry boundaries, userid/map identity and
  observed change/revert controls are included. Source assertions cover the
  native entrypoints, the shared SSQC mover/map-timer gate and both legal/base-save
  project-load paths.
- Header-full isolated Windows engine build: no new warnings over its native
  baseline. SSQC/menu0 warnings; the two existing CSQC F333 warnings remain.
- Real dedicated sockets:15ms control and10ms subject retain carry, grant exactly
  1/7 actual native movement ticks, hold paused body/count/carry, rewind7 and repeat
  the same printed endpoint. Completion counters do not roll back with the pose.
- An active queue cancels after a rate change and remains stopped after revert.
  Fresh matching context acts; unsupported20ms leaves ordinary movement live.
  A native-ready mixed mover/map-timer context is refused before pause/grants.
- Additional10ms controls exercise manual/directional authored input, retained
  native input-tape replay and a bounded4-tick air optimizer reporting22 candidates.
  Movement and completion deltas are native and monotone throughout.
- Real `bhop_eazy` base-save controls generate nonempty10/15ms projects and reopen
  them with one actual input grant each at matching clocks. The loader reports
  its saved states reproduced. These explicitly retain/prime the native pool;
  they are NOT fresh-session/cold project coverage.
- With the same valid10ms project and a primed native pool, the old mixed
  15ms-map/10ms-mover loader places and pauses the body and completes one grant.
  The fixed loader refuses before reading/placement/pause/grants, leaves the
  stable start pose unchanged and completes no grant.
- Reader regression:949 controls pass. On the same current canonical run corpus,
  the prefeature reader and current reader produce exactly identical diagnostics,
  including existing faults. An older historical inventory has fewer members;
  that growth is not relabeled an unchanged or clean corpus.

These are **airborne components**, with pose comparisons at console print
precision. The synthetic text-map's intended floor collision was not established;
leaving its start vertically must not be described as a grounded walking proof.
A real-map route reentered its start during the stepped tail and correctly
refused back. Neither result is canonical whole-world or byte-state equality.

Full10ms cold `.tasp` coverage, grounded/collision cases and owner feel are not
claimed by these controls. A separate matched-clock fresh-session falsifier
confirms the existing native input-row validator requires an already-created
native pool; the cold base-save load refusal is tracked in `BACKLOG.md`. Native source qualification and TAS-board admission
remain held; backend verification's explicitly supported profile is unchanged.
Review, final commit/tag build and destination/live provenance are separate
requirements. Human-only acceptance is recorded in `lextest.md`, not inferred
from these numerical controls.
