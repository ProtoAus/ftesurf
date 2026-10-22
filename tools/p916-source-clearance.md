# P916 — Source head clearance and water exit

Implementation: engine eacc763469d1b42f7d54f4b696a7c5121999b578, patch-916.
Merged clean native source: 14c3030275736ae5548f725d5d04dd05122ecef6. Main
advanced during push with the separately published P915 native reader support;
retain both published commits, resolve only the adjacent patch-heading conflict,
and rebuild/recheck merged artifacts. P915 QC/writers are not part of this ship.
Isolated bases: game 2d4e6957, engine aa45837f0. The initial unpublished P915
candidate was renumbered after discovering a peer-owned local patch-915 tag;
that tag and its unpublished REC13 work were not changed or included.

## Behavioural reference (public; independently implemented, not copied)

Momentum Mod a299840b8571927efa275f5110a1a0192242016d:
`mp/src/game/shared/momentum/mom_gamemovement.cpp`,
`CMomentumGameMovement::PlayerMove`: 12-unit eye clearance above standing/ducked
view-height hull, clamp view only; no ground requirement, bypass noclip.
`mp/src/game/shared/gamemovement.cpp`, `CGameMovement::CheckWaterJump`,
`WaterJump`, `FullWalkMove`; header default constants: waist-deep, facing ledge
within 24 units, reject falling faster than 180 or moving backwards, clear high
probe at eye + 8, walkable downward probe, Z 256 / wall-normal XY 50 for up to
2 seconds. The first swimming tick also applies ordinary water drag. Jump/up
are not required by the lip check; they can get the swimmer to the surface.
https://github.com/momentum-mod/game/tree/a299840b8571927efa275f5110a1a0192242016d/mp/src/game/shared
These are public Source-derived CS-based behaviours, not a claim of measured
binary-identical CS:S. Eye tracing deliberately starts from a valid hull top,
so a roof between the body and eye cannot hide behind an initial solid trace.

## Predictions and falsifiers (registered before implementation)

* Standing/airborne beneath a roof: eye <= roof - 12, body/hull unchanged;
  transitioning duck never raises the current eye. Open space restores normal
  view. Old-mover control retains its too-high eye. Noclip unchanged.
* Valid water lip facing forward: assist without jump. Wrong facing/backwards,
  fast entry, blocked headroom or no ledge must not start it. Actual trace and
  movement calls must act in positive and obstructed controls. Held jump cannot
  overwrite Z. Full submersion cannot start the waist-level check.
* Carry timer/direction through commands, prediction, saves and recorder state;
  old seeds readable; missing/partial v11 state cannot earn an exact replay.
  No verification eligibility or evidence-policy change.

## Implemented / verified

- Both behaviours gated at mover 11; historical movement preserved.
- Timer and fixed XY push are per-player carried state, not process statics or
  Quake teleport_time. Native text serializes all three, validates their bounds
  and finite numeric values; v11 requires all three for an exact replay.
- Full isolated Windows client/server/all-plugin build via
  `src/build.ps1 -Engine -Full -NoDeploy -Jobs 8 -FteRoot <owned engine>`;
  no new warnings versus identical baseline. Build from clean committed engine
  also passed. No source or artifacts from peer dirty trees were shipped.
- Baseline native pm_selftest passed. Subject passed all original checks plus
  36 new checks: real hull collisions, grounded/air roofs including eye above
  roof while body fits, unchanged body/hull, old mover/noclip, actual upward and
  forward assist motion, backwards/facing-away/fast descent/tall/no lip controls,
  held jump, carried/text state roundtrip and invalid/missing state. One initial
  test expected a boolean from a length-returning writer; corrected that test.
- `python tools/test_reccheck.py`: 852 checks, zero failed. Runs-only corpus:
  402 files, 271 existing faults. Python reader is unchanged. A broad default
  sweep additionally hit an inaccessible historical saves fixture; that is not
  presented as a completed saves sweep or fixed by changing its permissions.
- clangd database regenerated for the isolated tree. Source TU diagnostics have
  no new errors; standalone-header diagnostics are not a supported build proof.
- Public regression entrypoint: `tools/test_source_clearance.py --server <exe>
  --rig <new path under an owned task root>`. Logs must contain the completion
  marker and passing selftest; silence is not a pass.

## Acceptance and deployment

Visual/feel acceptance is PENDING in lextest.md. In particular, an owner's actual
roof and water ledge, +up swimming feel, and gameplay under moving ceilings are
not claimed by synthetic traces. No mandatory new visual automation framework.
Deployment provenance will be appended after the native fleet/install readback;
building, committing, pushing and deploying are separate states.
