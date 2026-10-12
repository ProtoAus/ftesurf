# P680 — inert canonical reset/zone movement policies

P678's module now prepares `zone_goto` and `!m`/`!s`/`!b`/`!r` body answers,
including `zone_reset`/`restart`'s existing `!r` route. **No normal production
consumer, predicted operation, wire request, cache, or native application exists.**
This is a prerequisite, not instant movement or completed client prediction.

## Authoritative decisions, shared rather than copied

- `SV_ZoneRequestZone` resolves the main start, numbered stage/bonus, or latched
  restart region; unlatched restart derives the current track/segment. Duplicate
  track/segment regions keep the actual latch, not the first matching region.
- `SV_ZoneDestRead` is the live destination algorithm's read-only half: explicit
  `teleDestPos`/yaw, named target origin/yaw, legacy box floor+2, standing-hull
  down trace, conditional lift, and raw-point+1 void/solid fallbacks. Named yaw
  zero is real; its authored pitch is ignored just as before. Only the live
  `SV_ZoneDest` wrapper prints and caches a missing named target as `ZTD_NONE`.
- `SV_SaveLocPickInZoneRead` shares the existing newest-sequence, zero-tick,
  hull/slab, traces, pitch clamp and post-snap occupancy selection. The live
  picker alone gates, allocates and rescans. A builder does none of those.
- Latched `!r` prefers that start-save origin/aim, except an active same-stage
  restart, just as current live QC. It never loads the saved speed, completed
  duck, timer or recorder state. `!m`/`!s`/`!b` have no save-list dependency.
  A stale/unallocated eligible preference returns STALE, not an invented zone
  fallback; the lobby's quiet disabled/unattributed save gate retains its zone
  fallback. Cached save rows are authoritative for this path: unlike save load,
  live restart does not reread `state.txt`, so no new disk dependency is added.

## Descriptor/body contract

Owned output comes from `SV_MovePrepAlloc`, and every attempt first clears it;
non-READY answers leave no valid payload. Free it with `SV_MovePrepFree`.
`SV_MovePrepZone(e, index, setang, yaw, pitch, out)` and
`SV_MovePrepReset(e, word, number, out)` prepare only for valid player slots.
Unavailable zones/lists, invalid input, missing zones, and unsupported mode
transitions remain distinct. Spectate/watch/ghost/resume transitions are not
modeled here; hold-to-reset and ordinary walk/noclip policies are modeled.

READY reset/zone policies: origin SET; speed SET to zero; carrier CLEAR;
completed duck KEEP; all 12 Source carried fields PRESERVE; gravity/jump KEEP.
Immediate `FL_ONGROUND`/groundentity are **KEEP**, not CLEAR: `setorigin` only
relinks and `SV_TimerWarped` does not recategorize the ground. The next movement
categorizes it. Save LOAD remains CLEAR according to its separate existing path.
The explicit `forceduck_policy` removes ambiguity between KEEP and a zero value.
Angle KEEP for a box/no yaw, SET for destination yaw (pitch zero) or an explicit
`zone_goto` override; start-save restart uses its clamped pitch and saved yaw.
A held reset prepares its final restored walk mode and zero velocity, not a
continued hold. Noclip reset keeps the mode. No timer/recorder state is captured
or restored; their existing live transitions still own the operation.

The current map and zone hash, zone index, and selected save id/seq/owner are
identity hints only. **They are not map/ruleset/connection/save/hold/rewind epochs.**
These descriptors cannot be retained or admitted safely as requests yet. Traces
also change the engine's `trace_*` scratch globals: read-only here means no
player/timer/recorder/list/root/zone-table/file mutation, not mathematical purity.
The save preference still uses current live hull/cvars. Do not claim those have
been made into client-visible immutable baselines.

## Actual falsifiers

`python tools/test_zoneprep.py --engine <engine-tree> --out <owned-output>`
compiles real QC at zero warnings and checks all Source fields plus absence of
production consumers/exports. Runtime fixture only:
`cfg/test/p680zoneprep.cfg` under `runlines_smoke.py --dedicated --mount`, with
inspected client/server **and matching sibling plugins**, an owned output-dir,
and an explicit fixture attribution key. Grade both server and client logs:

```
python tools/test_zoneprep.py --log <server.log> --client-log <client.log>
```

Dedicated subject: **71 checks, 0 failed**; existing P678 controls in the same
session: **66 checks, 0 failed**. Acting real floor and solid-box probes;
map/stage/bonus/latch/save-backed/native operation parity; zero yaw, named and
missing targets, box/void/solid, explicit aim; no mutation; stale, owner, mode,
input and output invalidation. `--weak` compiles one changed policy (keep current
speed instead of reset zero); the dedicated mutant has **2/71 expected failures**,
including the required reset-zero assertion, and P678 remains **66/0**. P678's
independent weakened-validation runtime still produces **23/66 expected failures**.
The grader requires all 71 controls, exactly one completion, matching failure
markers/count, acted P678 controls, and client completion; setup/VM faults and
silence cannot become a negative-control pass. Thirteen grader falsifiers pass.

All three normal QC programs compile at zero warnings. Reader suite **306/0**;
canonical run corpus **270 recordings, 91 sidecars, 170 pre-existing faults**,
unchanged reader bytes/count. Broader default save-prefix sweep stopped at an
untouched directory named `run.rec`; that failed invocation is not a pass and no
fixture/player data was repaired. Initial solid-box control escaped its short
obstacle: **1/64 failed**, retained. A tall acting obstacle exercises the intended
solid-fallback branch. Review also found a selected save can fail post-snap
occupancy and leave its pitch behind. The first high-slab control had no eligible
row (**1/71 actor failed**), not evidence. Correct point/hull occupancy produces
an acting **2/71 fallback/live-parity mismatch**; clearing fallback pitch fixes it
in the final **71/0** run. Fixture compiler first crashed on direct struct-pointer
vector component syntax; compare whole vector fields instead. Missing mount and
missing sibling-plugin attempts never connected and are retained failures.

Native executables/plugins used are the prior checkpoint's frozen build, not a
new P680 engine build or proof of what installations/fleet run. No deployment,
Build bump, recorder/evidence format or ranked-policy change is claimed.

## Remaining activation gates

Owned lifecycle generations and source revalidation; canonical rewind-go/native
selection preparation; complete replay-copyable descriptors and explicit
pre-input admission/ordering/cancellation/bounds; operation-bearing baseline
reconciliation and duplicate suppression; real client prediction with delay,
loss, reorder, choke and prediction-off controls. P675 command identity and P672
native seam alone do not supply them. Production prediction stays disabled.
