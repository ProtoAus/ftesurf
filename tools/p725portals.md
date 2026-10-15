# P725 — seamless oriented linked portals

## Scope

`surf_tripportals` has116 linked doors:58 pitched and11 rolled. Its portal
outputs include60 Open and40 Close connections. The Momentum and CS:S BSPs
inspected for this task are byte-identical. These are rendered destination
windows, not ordinary trigger teleports.

The matching native engine and progs implement a rigid portal transform for
position, momentum and forward/up view orientation. World gravity remains world
gravity. Camera-plane crossing and hull-centre crossing are separate; a carried
transient eye correction joins them without changing the upright collision hull.
The old200u/s exit floor does not apply to these pin4 linked doors. Reliable named
door snapshots synchronize activation, partner and dimensions with client render
and collision state, including state received before the BSP entity lump.

Native Source pin4 is deliberate. Pins1/2/3 keep their previous mover and digest
semantics; the new aperture/destination fingerprint data is v4-only. Ordinary
teleport-trigger angle handling remains additive. No recording-format version,
QC Build number, release version, updater feed or public download is changed.
Older native clients are not evidence of seamless pin4 prediction: use P725.

## Reproducible native falsifiers

Run from a clean source checkout, with outputs below an ALREADY OWNED task root
(see AGENTS.md before creating one). `--engine` names the engine checkout, not
its nested `engine/` directory. Both native tools accept `--cc`.

```
python tools/test_portals.py --engine <engine-checkout> --out <owned-root>/artifacts/portal-math
python tools/test_portal_collision.py --engine <engine-checkout> --out <owned-root>/artifacts/portal-collision
python tools/test_moveprep.py --engine <engine-checkout>
python tools/test_predinput.py --engine <engine-checkout> --out <owned-root>/artifacts/predinput
python tools/test_reccheck.py
```

- 54006 checks compile ACTUAL production AngleVectors/VectorAngles and rigid
 command-view helpers: random/inverse/alias rotations, pole ambiguity and snaps.
 An Euler-addition control acts and fails the flip invariant.
- 17 actual CSG/posture checks include a fast glancing thin-wall trace, front
 departure/point probes, rear-side approach/point refusal, sill/rectangle bounds
 and preceding standing/ducked output scratch. Controls separately restore
 unconditional carving and remove the front-side gate; both fail their specific
 wall assertions. Tick call order derives eye height AFTER current Duck and
 BEFORE portal-aware movement; the final zero-tick derivation remains.
- The explicit native/QC movement policy covers all13 carried fields. Native
 prediction-input tests complete, including legacy/absent/invalid payload arms.
- The unchanged reader unit suite passes306 checks. A paired sweep of the stable
 canonical run corpus checks289 files with189 existing faults in BOTH arms:
 no fault-count increase, not an all-clean corpus claim. No player evidence or
 raw corpus output is included here.

## Actual dedicated-socket observations

Owned test-only progs append view/body telemetry without changing product source;
real dedicated ports27547(control) and27548(subject), explicit100fps/netfps,
never listen-server prediction. Native `run_portalx`/`run_portalvel` establish
that crossings acted; a coordinate-jump threshold missed valid short links.

| Arm | Observation |
|---|---|
|1 ->2 wall/ceiling | Native crossing, rotated400u/s momentum |
|2 ->1 reverse | Native crossing; measured gravity800 starts with GO |
|3/4 oblique30 degrees, both directions | Native crossings and rotated vectors |
|5/6 floor/floor | Native upward exit, not a gravity-zero artifact |
|10 ->12 roll180 | Native crossings at16,400 and2000u/s; no200u/s floor |
|10 ducked | Actual eye47/hull45; crossing under gravity800 |
|19/20 ceiling/reverse | Native crossings under ordinary gravity800 |
|Old native slow10 | Same placement/command acts without a crossing |
|Open/Close | Old static control stays active; subject render/collision follow I/O |
|Partner-only retarget | Stable old native fingerprint stays7772440; v4 changes15832696 ->6604246 and restoration returns15832696 |

Retarget preconditioning refreshes the same source once so list-relink order
cannot imitate transform hashing. The destination's actual client partner state
also changes, independently of the fingerprint observation.

Screenshots before/through representative doors were inspected for see-through
alignment and orientation. They do not establish a complete human playthrough,
all mouse timing or long-run performance. See `lextest.md` for those checks.

Invalid early controls are retained as invalid: `sv_gravity0` causes the existing
entgravity normalization to produce NaN; use positive1 for near-zero gravity.
`+movedown` was not crouch, and28 was not the configured duck eye. Unsupported
ceiling placements now use gravity1 until acknowledged, then apply measured800
with GO, so the actor cannot fall through during readiness. No unrelated gravity
normalization or map-content fix is included.

## Review and delivery state

Independent geometry, compatibility and runtime-state reviews were followed by
focused reviews of the swept boundary, current-posture eye and front-side gate.
The final focused review has no issues. Product source remained frozen during
those reads; canonical peer edits were neither built nor deployed. P723/P724
published upstream is integrated, along with the already-deployed P726 chat
aliases. ENGINE.txt's highest patch stays726 while its native pin/tag is P725.
Native deltas since the Pi's679 base outside this feature are Windows-only
updater files, not additional server movement code.

Source publication, exact-commit clean builds, Windows installation and NanoPi
fleet delivery are distinct states. Final SHAs/hashes and any concrete delivery
blockers will be appended after those operations. No deployment is claimed by
this initial implementation/test record.
