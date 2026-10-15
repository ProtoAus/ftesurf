# Patch 718 — Practice labels and save-owned run tags

Reserved 2026-10-15T00:12Z after fetching both repos and checking patch headings and untracked pNNN reservations (max 717).

## Predictions registered before editing/testing

- Noclip uses the Practice label/colour everywhere; internal reason/evidence bits and legacy recording filenames stay compatible and nonrankable.
- Loading a clean saved start after noclip restores that save's tags without first touching the start zone.
- Loading a practice save does not cleanse it; live noclip/sv_cheats still marks the restored attempt.
- Loading a running save still adds segmented/shadow; it never grants a clean ranked continuation.
- Recorder rewind failure retains the existing cancellation contract.

## Verification

- Base: inspected `origin/main` 8edb549. Isolated `build.ps1 -Jobs 8 -NoDeploy`
  with `C:/FTESurf/src` added to PATH for fteqcc; server/client/menu each zero
  warnings. The first build lacked fteqcc on PATH and did not compile anything.
- `cfg/test/p718tags.cfg` runs via `tools/runlines_smoke.py --dedicated
  --map surf_dune --mount --port 27616`, with explicit control/subject
  `--ssqc`/`--csqc`. Use an owned task-root `--output-dir`, not shared fixtures.
- `python tools/p718tags_check.py <control-rig> --control`: 39 checks, zero
  failures. Against subject expectations the control fails 11 checks.
- Subject: 39 checks, zero failures. A/B prove a clean RUNNING recording and
  acting noclip; C/F load that clean run without a start-zone visit and clear
  run/stage/latch reason while retaining segmented/shadow; D preserves a
  practice save's reason; E keeps CURRENT noclip; G/H/I restore a clean start
  and walk out into a fresh clean recording. Full and stage banner probes say
  PRACTICE; both `scores filter practice` and legacy `cheated` select Practice.
- HUD screenshots inspected: amber practice while noclipping, shadow/held on
  the clean restored running row. Full-banner screenshot retained for review.
- Initial rig was invalid: an unknown cvar and enough delay for the run to fall
  and reset before measurement. Corrected by removing that cvar, measuring
  noclip sooner, and pinning the RUNNING load with documented `sl_hold`.
- `python tools/test_reccheck.py`: 306 checks, zero failures.
- Baseline recursive `ftesurf/data/runs` sweep: 289 files, 189 with existing
  faults. The default broader sweep encountered a pre-existing inaccessible
  save fixture, so the measured corpus is explicitly the runs directory.

## Limits / delivery

Internal reason bits and legacy `cheat` recording filenames are intentionally
retained; this is not a file-format migration or a ranked-save-load feature.
Existing hopped-start forgiveness, resume and recorder-failure rules are not
changed.

## Independent review and strengthened controls

Two fresh read-only reviews of frozen b70a29b: gameplay/ranking OK; UI/tests OK
with two accepted P2 findings. Fixed the chat colour mapper's obsolete
`TC_CHEAT` red comparison (now an alias of amber Practice). Replaced empty-list
filter checks with six synthetic header-only browser fixtures: clean,
segmented, bare practice, flagged legacy reason, unflagged legacy reason and
unknown. These are never verifier/playback evidence. Generate with
`python tools/p718tags_fixtures.py <new-owned-fixture-dir>` and pass each file
as `--put data/runs/surf_dune/stage_2/<name>=<absolute-file>` to the rig.

The first populated-list arm used an invalid `_seg` filename and correctly
failed the six-row assertion; corrected the fixture to the existing `_shadow`
filename, without changing the reader. Final control/subject each pass 42
checks under their own expectations; the control fails 12 subject checks.
Subject Practice keeps bare practice and both old reason variants; segmented
stays separate and unknown remains visible in every chip. Full/stage banners
and explicit finish-chat exercised. Final VMs compile with zero warnings.
Post-run corpus: **289 files, 189 with existing faults**, unchanged.
Final fix-blast-radius review: OK, both P2 findings resolved. Subject screenshot
also visibly confirms amber Practice finish chat. Fresh verifier rerun: 306/0.

## Delivery — 2026-10-15

Product source pushed as inspected d9c2e92 (includes the non-product P717
interrupt-test/docs peer merge). Rebuilt that clean committed tree with
`build.ps1 -Jobs 8 -NoDeploy`, zero warnings in all three VMs; all three output
hashes match the final tested subject. At **00:41:27 UTC**, mirrored ONLY these
verified generated outputs to BOTH `C:/FTESurf/ftesurf` and
`C:/FTEQuake/ftesurf`, preserving each destination as `.prev`. Asserted no game
or dedicated process running and no target hash change since inspection.
Source working checkouts/owner cfg/player data untouched.

SHA-256, identical at both destinations:

- qwprogs.dat: `f21b9d53d18879318db138213ec1e16118cdb4471c6103e5002b1122bd66cdc2`
- csprogs.dat: `a871d60d94aacd2eaf342911c023ff848c9361b203ff682e21d71d975bc6d88f`
- menu.dat: `44f12fd918278bd160db66f6cfb45b176d56eeb6290e3d28e6365e81e3bbcbd9`

A fresh dedicated-socket rig copied server progs from the first install and
client progs from the second: **42 checks, zero failures**, no command/VM
errors. Thus both installed artifacts, not merely pre-deploy source, acted.
The NanoPi SSH and directory probes timed out; **no Pi files changed and no
live-lobby deployment/restart/verification is claimed**. Fleet update remains
blocked by connectivity. This is not a release or a Build-number bump.

Task evidence retained at `C:/FTESurf-worktrees/runtags-20261015-001/artifacts`
with OWNER.md lifecycle/provenance; disposable full worktrees/runtime junctions
are retired after recording completion.
