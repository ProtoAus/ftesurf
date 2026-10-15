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
|Open/Close | Old static control stays active; subject render/collision follow I/O; closed10 has81 actual body observations and0 crossings |
|Fresh late join | Already-closed10 is active0/solid0/draw0; live reopen becomes active1/solid21 |
|Map transition/no portals | surf_demise count0, actual body/view moves95.46 units |
|Yaw/floor doorway | surf_kitsune20 apertures, standing feet1 above sill crosses once without crouch-jump |
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
Server/common deltas since the Pi's679 base outside this feature are Windows-
only updater files, not additional server movement code. The matching rebuilt
HL2 plugin also includes published P683 material/rendering work; no extra Source
collision policy was introduced for it.

### Publication and exact builds

- Engine`77f614b462e1173076bbd0771e64bb3aadd54914`, annotated`patch-725`.
- QC`7f3a0672b3b9c54f0de72d79ea7cc62179d4970d`, including approved P726.
- Exact inspected SHAs pushed to main; all3 production VMs zero warnings.
- Clean full Windows native revision`git-7334-patch-725-0-g77f614b46`.
  Archive/worktree builds supplied this revision explicitly because the native
  Makefile's directory-only`.git` test otherwise drops the stamp.
- Clean native ARM subject/control each15 identical inherited warnings; matching
  HL2 subject/control each1 identical comment warning: zero NEW warnings.

### Windows delivery — completed2026-10-15 UTC

Both installs received the standard native/plugin/VM set from the exact clean
build outputs:16 destination files, all SHA256-verified, previous files retained
as`.prev`. Owner cfg hashes were unchanged; no player data/configs were copied.
Existing install processes were not killed; deployment waited until they had
exited and preflight write access succeeded. This is installed-file provenance,
not a claim about a human's currently running process or completed playthrough.

| Output | SHA256 |
|---|---|
| Native client |`c3e8417cd09e14851dea4fa5f95b98cd9056cd2b1afc92e4ee829b7675e0bf34`|
| Native dedicated |`3935f65f15985e5da41d95ed940deb8a603c7f02c32a8a7a77c4c1cfc0ebccef`|
| qwprogs.dat |`9593a086282eeacf78f7f6bc991bf043f2caeac1baaaacad09d174f8520385b2`|
| csprogs.dat |`a0a3065892b3f100c61746776d7f698e5fdb4db1e9eaf5aca49652b09de7fd88`|
| menu.dat |`44f12fd918278bd160db66f6cfb45b176d56eeb6290e3d28e6365e81e3bbcbd9`|

### NanoPi gates — passed; fleet delivery BLOCKED

The actual candidate native and matching HL2 passed selftests and all7 native
map/libm/trace/mover/tick/Source hash fields against Windows on bhop_eazy,
surf_ace, surf_kitsune and surf_dune. Both arms used explicit identical BSP
bytes in owned overlays: initial raw map variants were different, not a physics
failure, and canonical map-library hashes were verified unchanged.

Matched clean old engine85ef3e3/QC2de3726 controls and new engine77f614b46/QC7f3a067
subjects replayed BOTH the approved pin1 reference3107 ticks/rows and provided
pin2 synthetic4418 ticks/rows to PASS. Private player paths/raw output are not
included. This legacy acceptance is not a completed new pin4 portal-route test.

A verified four-file candidate is retained at
`/srv/nvme/agent-work/portals-01a13e7a/stage/` with its manifest:

- Native SHA256`c3c6a2b7ae6202b77f4e5f0a5327709474baf075ad49906739c206db7c32f9e2`.
- Matching HL2 SHA256`4dd685d408af2c9839b892ea99d1629755a1b09eebb36be1eaabb84da549866a`.
- QW/CS hashes exactly match the Windows table; menu is NOT a lobby artifact.

At11:36Z both public and direct lobby directories returned ZERO rows while12
services were active. An empty directory cannot prove quietness. No live native,
plugin or progs file was replaced, and no live service was restarted. Readback
still matched the separately deployed P726 pair (`7fb25d13…`/`a78f8dd6…`).
At12:28Z the directory recovered to12 positive rows; a fresh census then showed
ONE connected player. The swap remains held for a zero-player fleet, not a
failed native gate. No active player was disconnected. Recheck quietness and
current deployed provenance before resuming; never guess a lobby count or
overwrite a newer peer deployment.

A later fetch also found [P727's guarded-runtime handover blocker](p727completion.md).
This task did not copy backend source, migrate schema or attempt that handover.
A future fleet resume must coordinate the current runtime and accepted native
origins with its owner; a restored directory alone is not proof of that closure.
Do not overwrite immutable inputs or run a normal backend deploy as a workaround.

No Build/release/updater/feed operation was performed. Full-route camera feel,
mouse timing and new pin4 complete-route receipt acceptance remain human checks
in`lextest.md`, not automated claims.
