# Patch 1308 — human-first TAS controller foundation

This is the controller foundation for [the full human-first editor](plan-tas-human-workflow.md),
**not completion of normal-play/full-history editing**. Source integration, final
clean-source reviews/builds and deployment are tracked below; do not infer an
installed build from this document or an isolated test.

## Using the controller

On a supported local attempt, `tas pause`, then `tas menu`. This remains TAS
practice: pausing/authoring/replaying never becomes a clean human-board attempt.

- Select Forward/Left/Back/Right as movement keys, not yaw-turn commands. Select
  combined keys such as W+D. Opposed buttons visibly replace the opposing choice;
  a historical analog value stays intact until explicitly changed.
- **Auto strafe** changes turning assistance, not your selected movement keys.
  Off means authored HOLD; on means the native gain GUIDE in the chosen A/D
  direction. No selected side means no automatic turning reference.
- **Turn amount** scales the yaw change from a state-appropriate local gain
  reference. `1.00x` is the reference, smaller is gentler and larger sharper.
  Fine buttons change0.01x, coarse buttons0.10x; reset returns1.00x. Range0..4x.
  This is not a percentage-speed claim, a globally optimal route or a guarantee
  of staying on a ramp. Enabling aligns gradually from the actual body view,
  rather than snapping to an absolute heading.
- Jump and Duck are held for the authored ticks, not toggled on/off by each
  native step. Step1 or a bounded batch; Play cancels remaining synthetic work
  and returns to live controls. The editor does not take ownership of a physical
  movement key that was already held.
- **Vertical look / Follow travel** is a smoothed VIEW-only pitch convenience:
  up on ascent, level near an apex, down during a fall. It does not rewrite
  recorded pitch, yaw, keys or gain targets. Manual vertical input temporarily
  overrides it; use mouse-free mode when you want free mouse look. Server/save
  corrections retain ownership. Physical comfort is still owner acceptance.
- Recent qualified authored warm history restores its incoming recipe, including
  mode, nominal inputs, turn amount and follow setting. The existing short warm
  history and native checkpoint eligibility still apply. Draft changes alone do
  not execute movement.
- Under **Advanced**, `Use view` takes local input/view aim; `Use server` explicitly
  reloads the current authoritative controls, even at the same tick. These are
  deliberately different operations. `tas menu status` shows draft amount/follow
  and read-only rendered versus raw input angles for one owned body.

The native engine/server must support capability1308. Older native versions
refuse new HOLD/GUIDE authoring before granting movement; existing typed
LIVE/manual/left/right commands retain their old interface.

## Crouch and grounded turning

The guide uses the production Source mover's clamped combined-key wish direction,
friction/acceleration, clock and supported stance. Fully crouched grounded input
gets the real ground crop. Airborne Duck is NOT assigned a fabricated lower
`airaccelerate`; hull/contact, caps and transition states still matter. Water,
ladders, transitioning/unsupported configurations fall back explicitly rather
than masquerading as an optimized ground/air result.

An integration bug found by the real crouched-ground control was fixed in all
three planner cache/capture/seed sites. Casting the naked `ANGLE2SHORT` macro
cast whole degrees before multiplication, and negative-to-unsigned conversion
was invalid. The planner now preserves signed fractional angle words, without
changing the engine-wide macro or movement physics.

## Evidence and limits at the pre-integration checkpoint

- Actual production clamp/crop/friction/acceleration C functions, both10/15ms,
  independent/combined keys, supported ground/air/crouch and binding caps;
  all65536 signed fractional angle-word roundtrips and low-speed cropped-ground
  slew/cache pipeline:67392 checks, zero failures. Existing native admission,
  input and queue controls also pass; these are not hardware provenance claims.
- A real dedicated socket/rendered client acted:15ms GUI callbacks20/20;
  10ms controller/held-Duck/warm-restore17/17; travel-pitch rise/apex/fall/raw-aim
  and keyboard-look override16/16; old-native legacy/refusal18/18 and current
  legacy16/16; cancellation/live pending-input ownership8/8. No missing log was
  accepted as a pass. Body state and native completions were observed.
- Real15ms `surf_dune` default260maxspeed/5accel/4friction/75stop, interior W+A
  curve:289.5414 standing and97.8939 fully crouched after64 guide ticks, each
  observed chunk native ground-kind2/vz0. This scoped measurement is NOT a replay
  of Lex's unspecified W+D/map setup, a universal limit or collision/route optimum.
  That owner setup and matching manual/preset ground comparisons remain explicit
  follow-up in the full project, not a fabricated cause for the reported275.
- The original crouched-ground actor really failed at88.4018; native diagnostics
  identified cache corruption, and the unchanged90..103 acceptance passed after
  the fix. Temporary diagnostics were removed before the subject full build.
- The frozen Windows subject compiled with zero new warnings:74/74 normalized
  native `warning:` records and the same two pre-existing CL F333 diagnostics;
  SV/MENU zero. This precedes integration of published1301..1307 and capability
  renumbering; final combined-source qualification is separate, not implied.
- Cancellation initially used an invalid world-X-speed proxy after live yaw/route
  changed. Correct observation uses existing `hud_wishtrace` primary pending/sent
  input450/0 with keyboard fallbackOFF. Queue cancellation and Duck release had
  already acted; the physical-key ownership assertion was not weakened.

All recording formats, raw-input provenance and board contribution/eligibility
contracts are preserved. Editor recipe metadata confers no evidence credit.
No private logs, source recordings or design are shipped with these tests.

## Final review corrections and corpus qualification

Two independent frozen-source reviews completed. Corrections restore native1x
when cancellation clears a changed identity, and accumulate small pitch deltas
before Follow travel yields to manual look. Actual production C67399 checks pass;
the exact old cancellation body fails2 lifecycle checks. A real100fps/1degree-per-
second keyboard actor shows raw-1.805/rendered0 on the old camera, then passes the
corrected render-versus-raw check. The camera never writes raw aim or movement.
A first reconnect observation read native-cap0 and only the UI's initial1x; it is
NOT live reconnect acceptance. The actual native reset-branch before/after checks,
not that unqualified observation, close the default fix.

Reader949 checks pass. Current exact RUNS domain:542 files/349 structural faults
in BOTH published-parent control and candidate, with identical reader source and
stable SHA-bound inputs. No corpus-fault increase is attributable to this patch;
this is not a clean-corpus claim. Earlier recursive selection/old341 expectation
failures remain preserved privately. A separate all-SAVES observation refused at
a protected unreadable historical fixture; no data or permissions were changed.

## Still in scope for the full requested editor

Complete normal-play capture beyond128/the warm ring; indexed full timeline and
selection; qualified cold/base replay in bounded chunks; immutable original and
candidate comparison; Keep/Discard, Undo/Redo, save/load, resume; revision-bound
per-tick recipes and camera state; honest other-run inspection; manual then actual
contact-aware sections; bounded next-ramp-constrained improvement. REC14 historical
restore is not invented. The controller's warm demo is not that full workflow.

Final clean-source review/build, Windows BOTH and supported fleet delivery:
**pending**. Human ramp/turn/camera feel: **pending**, see `lextest.md`.
