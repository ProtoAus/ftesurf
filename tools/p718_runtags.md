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
changed. Independent review, post-corpus sweep and deployment pending.
