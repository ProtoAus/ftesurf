# P1074: next-tick TAS workshop, mouse lock and directional AIR help

## Use

Use the matching local native/client/server with `cl_threadedphysics 0`. Walk out
of the start so a recorded timeline is running, then `tas pause` and `tas menu`.
The window is own-body/single-seat; active-seat console authoring remains separate.

- Choose Live keys, Manual, Auto left or Auto right. Manual uses the configured
  forward/side, pitch/yaw and held Jump/Duck/Walk buttons. W/A/S/D/None fill movement.
- Advance1 or AdvanceN grants actual native ticks (N1..128), then stays paused.
  Apply only configures without advancing. Every Advance binds its complete draft;
  delayed server statistics cannot silently substitute a newer/different plan.
- Auto left/right recomputes quantized yaw for current horizontal AIR acceleration
  gain each granted tick, using a full450-side key. Ground/contact/unsupported
  states use the configured preset and carried heading. The server reports whether
  the last selection was AIR or preset/live. This is NOT route/collision search.
- Physical mouse look locks while your own body is TAS-paused by default. Toggle
  Mouse free, Esc, aim deliberately, reopen and Use view; restore Mouse locked when
  ready. `tas mouse on/off/status` and `cl_tas_mouselock` expose the same preference.
  This does not block authored steps, rewind or genuine server camera corrections.
- Esc/X only closes the panel. Play/Controls off cancel future authoring and replay;
  off restores speed, not human eligibility. Back1 uses existing exact warm history.

Console equivalents:

```
tas menu
tas plan manual 450 0 0 0 1
tas next left 450 0 0 0 1 8
tas plan live 0 0 0 0 0
tas menu status
```

`plan MODE FORWARD SIDE PITCH YAW BITS` configures only; `next` adds COUNT.
Modes are live/manual/left/right; bits are jump1+duck2+walk4. Movement is bounded
-450..450, pitch-89..89 and yaw-360..360. GUI imports legal endpoint pitch without
changing its native word; validated CLI angle tokens are not shortened. An unchanged
server configuration preserves assist carry within the same movement epoch.

## Domain and limits

Supported authoritative Source15ms duration input, own live player body and
non-threaded input only. Existing streamed-REC14 edit/back refusal, warm-history,
replay and context guards remain. Missing native authoring support prints an update
message rather than pretending to simulate. Capability1071 is the protocol marker,
independent of this publication patch number1074.

The objective uses observed horizontal velocity, effective walk/stamina speed,
air-cap/acceleration and matching surface friction. Ground/water/ladder/limit,
transition/fixangle, zero-speed and near-clamp cases use preset. Server and effective
mover caps must agree positively, the head must survive both and the entire AIR
acceleration bound must fit; differing custom caps conservatively use preset.
Future QC/geometry/collision, shared movers/time and total-route outcomes are not
predicted. No speed is written directly and no globally fastest-line claim is made.

This is not a persisted timeline/project, branch/undo UI, arbitrary world rewind,
comparison overlay, signed contribution protocol or TAS board. All assistance
retains TAS/practice ancestry. Public lobby editing policy and guarded native/backend
promotion are separate from the local tool; no backend transition is authorized by
these tests. See [the staged plan](plan-tas.md).

## Verification

- Actual-C model/guard suite983/0: exhaustive actual Source AIR objective comparisons,
  effective input scaling and acting mover/pre-server-clamp counterexamples. Normal
  Source selftests pass. Full native build has the same74warnings; QC only2oldF333.
- Real dedicated sockets and production progs: selected movement/aim/buttons captured
  before physics, exact grants, sustained left/right turns and gain, stored-tail replay,
  exact prefix rewind, invalid/stale request nonmutation and Play/Off cancellation.
- A private scheduling actor calls actual production bhop PostThink teleport: the old
  control restores stale heading; corrected execution and unchanged full transactions
  retain the genuine final heading. A real cached-stat GUI sequence queues a newer
  edit and Advance before acknowledgement: old shortcut executes wrong draft; new
  full transaction executes the displayed draft. Actor code/progs are NEVER shipped.
- Native physical delta lock/unlock, authored camera, broker release, tiny-yaw command
  word and both imported pitch endpoints pass.393219relevant float32 serialization
  roundtrips pass. Unchanged930reader checks and paired full-corpus comparison retain
  existing findings without increase. Source reviews cleared substantive corrections.

Headless checks do not establish rendered appearance or feel. Please perform the
small pending owner check in lextest.md; no owner confirmation is inferred.

## Production qualification and delivery

Implementation/source verification are complete. Final clean pinned/tagged build,
installation UTC/hashes and installed-client smoke will be recorded here only after
execution. No Build/release bump. Existing peer MENU, configs, install lists and
player data are not selected payloads. Public native/backend/lobby promotion is not
implied by a local Windows build.
