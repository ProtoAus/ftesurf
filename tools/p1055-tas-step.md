# P1055: authoritative TAS pause and movement-tick advance

## Controls

Use the matching server engine and new progs, ordinary QuakeWorld duration input,
Source movement at its normal15ms tick, gamespeed1 and `cl_threadedphysics 0`.
Return to your own living body first; save/watch holds, spectate, ghost and resume
control do not combine with stepping.

```
tas pause
tas step          // one movement tick
tas step 7        // seven movement ticks, then remain paused
tas status
tas play          // resume at the selected practice speed
tas off           // resume normal speed, controls off, ancestry retained
```

A binding such as `bind F6 "tas step"` is optional; the game does not replace
existing bindings. A request queues1..128ticks. Completion is reported from
actual movement, not command receipt. Reliable request tickets and decoded input
freshness prevent a repeated request/backfill from consuming a second grant.
`tas status` shows pause, pending, completed, native support/fault and mover
counter/carry. A native fault clears queued grants rather than claiming success;
`tas play` escapes before another pause attempt. Paused packet bookkeeping uses
that bounded actual-step acknowledgement, not a rounded cumulative counter.
Both the connection movement clock and completed/queued grants stay within
16million exact integer ticks; reconnect if the connection-clock limit is reached.

While paused, change movement/buttons/view normally; each granted tick takes the
next fresh input sample. Client command duration does not authorize movement.
The client retains normal raw durations while paused; the server installs one
15ms synthetic command per admitted grant and waits for one actual Source tick.
Prediction/thread guards reuse the per-seat slow-practice mechanism. Play keeps
the chosen `tas speed`; off restores1. All assisted ancestry remains TAS.

Successful saved-state loads, ghost entry and explicit zone/reset placements
cancel live controls. Native body-state/impulse transitions cancel incompatible
grants too. Controls are not serialized into custom run/save state. Old engines
refuse pause/step without marking an otherwise clean player. Old QC/mods without
the complete optional field protocol keep their original native movement path.

## Deliberate boundaries

This pauses the player's **movement driver**, not the whole world, other players,
audio, entity IO or physics props. It is not a private world snapshot or a promise
that a dynamic map replays identically. Static-world line work is the supported
starting point. Shared effects/pushers can still affect the world around a paused
body. Unsupported clocks, timestamp/VR inputs and NQ world-frame physics do not
gain step support. A live NQ bypass invalidates pause, pending and readiness.

The synthetic15ms command publishes no decoded-duration provenance. Recorder
formats, the existing start horizon, held-session acceptance and ordinary human/
segmented eligibility are not widened. TAS remains local assisted practice;
editing, optimization, signed contributors and public TAS verification/boards
remain later stages in [plan-tas.md](plan-tas.md).

## Verification

- Standard pwsh7 isolated NoDeploy builds, with full native/header rebuild.
  Server/menu0warnings; the same2existing client property227warnings. Native
  warning comparison:57unique existing warnings, zero new. Native LSP no errors.
- Actual-header C test:167checks, including sequence wrap/backfill, malformed and
  bounded grants, exact supported clock/carry, the two-tick tolerance regression
  and stat-slot collision protection. This tests admission, not a whole mover.
  `python tools/test_tas_step.py --engine <checkout> --out <owned-root>/headers`.
- Real dedicated-socket old-native control refuses pause without TAS marking.
  Subject proves static pause/counter/carry, exact1/7ticks, exact1,000,001request
  identity, duplicate refusal, play and retained ancestry after off.
- Running/recording control acts before pause. Entirely blocked packets add no
  input rows/samples; actual final steps flush recorder inputs. Configured render/
  net pairs30/20,100/66.6667and240/144each execute exactly1and7ticks; one flat tick
  moves the70u/s body1.0..1.1u at viewpos's0.1u precision. Another player moves
  while the paused body's mover counter stays fixed. Jump/release gravity and a
  full128tick queue act. These are configured rate pairs, not measured FPS claims.
- Bounds/nonfinite requests leave state unchanged. Real NQ transition invalidates
  controls. A separate cheats-enabled30ms-clock fixture proves unsupported-clock
  refusal, direct-zone cancellation, restoration and queued128/off cancellation.
  The earlier locked-ruleset fixture failed to change the clock; that failed
  attempt is retained and is not counted as acting clock coverage.
- Final precision follow-up passes all39live socket checks in one complete run,
  including recorder flushing and the acting unsupported-clock/warp transitions.
  The float32/static wiring guard demonstrates the2^24alias; it is not a
  near-limit runtime test. The produced REC has zero reader faults and no VIEW.
- Portable Linux x86_64 client/server/HL2 build at native2e9260645 passes allten
  platform gates, including ELF, symbol-version, soname, plugin and revision checks.
- Completed TAS REC passes the existing reader. Native old/new static-map
  regression matches all11bhop_eazy digests. Both open-loop replays reproduce
  all52stored packet poses exactly at the file's text precision; both verifiers
  retain HOLD for the same57physent-digest mismatches after the other player
  changed the shared world. No native PASS or dynamic-world parity is claimed.
- Reader suite930checks, zero failed; canonical497RECs/167pairedVIEWs retain the
  same306historical faults. The final sweep also checks10unpairedVIEWs (177total),
  with the same fault count and stable membership/bytes during the sweep. Initial
  paired-count and final all-VIEW counts are distinct, not a hidden dropped check.
  No VIEW was captured for the new
  timed fixture, so it supplies no paired-view/angle or human-input qualification.
- Three independent final reviews closed the initial stat, ticket, clock, bypass
  and cancellation findings. Three bounded precision-follow-up source reviews
  also found no remaining source blocker; those reviews do not claim execution.

## Installation status

Clean QCabc62390 and native2e9260645 are installed in BOTH Windows installs:
`C:\FTESurf\ftesurf64.exe` and `C:\FTEQuake\fteqw64.exe`, with the matching secondary
dedicated server and normal native plugin ship set. Both qw/cs DAT/LNO payloads
match the qualified clean artifacts. Each installed client/server pair passes
8live socket checks (16total). Normal `.prev` slots remain; their older contents
were retained before promotion. Existing menu/config/install-list files and
player data were not replaced, nor were unrelated CSQC cache partials deleted.

Native AArch64 server compilation and167actual-header checks also pass at the
same engine pin. That is not full ARM gameplay/parity or public-fleet admission.
The prepared native artifact is retained; live lobbies/backend were not changed.
Guarded public-fleet promotion remains a coordinated handoff, not an ordinary
progs-only swap. No release or BuildNN bump was performed.

Owner feel/aim/crouch acceptance remains pending in lextest.md. The implemented
movement controls do not complete the timeline/editor/optimizer/signature stages.
