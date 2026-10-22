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
Cold-save/teleport restoration during an active assist and real socket client
prediction error counts were not runtime-tested; carried-state roundtrip is a
narrower claim. The owner's short check is preferred to a new visual harness.

## Deployed (ordinary development update, not a release)

Source commits/tag are pushed. Clean merged native 14c303027, stamp
`git-7703-patch-916-2-g14c303027` (build.ps1's historical count offset included):

- ARM full dedicated + HL2 plugin build passed. Native selftest on the actual Pi
  passed all original checks and all 36 P916 checks. The attempted map-based
  control fixture could not load VBSP because its isolated plugin path/load
  setup was wrong, including on the unchanged control. After the bounded
  diagnostic cycle, stopped that fixture, retained failures and used the
  map-free real-hull test; do not claim its dettest or legacy pm_verify passed.
- Pi promotion completed **2026-10-22T06:55:26Z**: all 12 empty lobbies restarted
  one at a time after fresh UDP emptiness checks; actual /proc executable hashes,
  newly mapped matching plugin inode, UDP status, version, mover 11 and
  sv_tickparts 1 verified on every unit. The sweeper lock covered only paired
  promotion, not the offline build or extended testing. Protected configs/QC and
  an aggregate of player-data trees were byte-for-byte unchanged. Backups:
  `fteqw-svarm64.pre916-20261022T065339Z` and the matching plugin backup beside
  the live files.
- ARM native SHA256 `5d88b9742419595b7aa16731c644b384f1d6572a3be345b9ac8e7b7280c7db27`;
  HL2 plugin `f9c1b6d6886abf49d5e52f0e60d64f2bc6eb0aedd9af4cc100512bc4ac2e51f4`.
- Windows dual native deployment completed **2026-10-22T06:57:08Z**: 10 matching
  client/server/plugin files at C:/FTESurf and C:/FTEQuake, each destination hash
  verified. No owner processes were stopped. QC, settings and installed.lst
  hashes unchanged; native rollback files use `.pre916-20261022T065705Z`.
  The deployed C:/FTEQuake dedicated executable then passed the public smoke,
  including all 36 P916 checks, in an owned no-home fixture.
- Windows client SHA256 `23e44fd27f6b3a910bc4fa04213c75d89e4f7dbc8b4864cbed650c79ddd92a3e`;
  dedicated `fc551b6a8780bfcedb55aebe4f240fb1082a61de4e0772899b9b3b90340b1fd2`.
- Native only: no unrelated QC/writer or configs shipped; QC build remains 89.
  No release/version publication or player-data migration was performed.

Task roots: C:/FTESurf-worktrees/source-move-20261022T0556Z and
/srv/nvme/agent-work/source-move-20261022T0556Z. Retain concise source/archive,
compiled controls and verification/deployment evidence; retire owned build
caches and test overlays after readback. No maintenance gate remains active.
