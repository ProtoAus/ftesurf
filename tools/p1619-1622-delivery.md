# P1619–P1622 — requested boards/chat/Splits/Story changes

Owner: pi.dev task `requests-20261119-5a3b`, 19 November 2026. Game baseline
`163ef4edffb75e45872bc3260b522541c6de5dea`; engine documentation base `e8329c814`.
Pre-existing unrelated `ROADMAP.md` tournament-planning edits were preserved and excluded.
Native children implemented separate stages with one source writer at a time; the parent reviewed the final diff.
No engine C/C++/plugin/recording grammar/schema/QC Build-number change.

## Implemented

- **P1619:** optional mode chips select one or toggle off to Normal, with explicit Normal labels; existing
  exclusive Segmented/TAS behavior stays. Direct WOS/Momentum/KSF source stops, no Filter switch, fixed Fetch
  reservation. Menu board matches control/column ordering and asks for the player's vicinity by default, while
  preserving explicit profile seeks and first-page rows on a missing-player result. Download/Wrong build label
  block centered vertically.
- **P1620:** new game-origin global-chat messages freeze sender map/stage/bonus in stored text, not lobby number.
  Old stored tags remain readable; no backend protocol/storage change.
- **P1621:** plain mono stage-time/rank text below Splits follows its position/size/visibility, shares editor
  bounds/preview and exposes Stage result/duration under Splits. Timing and rank semantics unchanged.
- **P1622:** 73 occupied ordinary Story slots with finish bronze, 71 actual G4/G2 silver/gold pairs and two
  finish-only courses without cuts. Eight requested Story maps added, explicitly `surf_autumn_fix`; four Event
  courses added. Nightingale B4/B5 are pending actual bonus zones, finish-only and course-gated. Stable occupied
  slots, Story59 and explicit gate bars preserved; affected mixed-tier chapter titles made neutral.
  Details, calibration provenance and deferred old challenge issues: `story-catalogue-audit.md`.

## Validation already run

- Parent final rerun: `surfd/test_story.py` **54/54**, `surfd/test_groups.py` **10/10**,
  `tools/test_remaining_requests.py` **4/4** pass. Includes exact group-boundary acceptance, exact fixed-map/course
  identity, pending-course precedence/read failures, overflowing numeric/deep JSON, cache refresh and held credit.
- `surfd/test_social.py`: **86 pass, two errors** in the existing configured-verifier service-layout test under
  Flask 2.2.5/Python 3.14. New message-origin transport regression passes. Full suite is not green.
- `tools/test_board_navigation.py`: **11/12 pass**. Existing source assertion expects PF_CF4; untouched baseline
  `src/client/cl_profile.qc` defines PF_CF5. Three new navigation guards pass. Full suite is not green.
- Worker all-three QC compile: exit0, zero warnings. Parent final clean-tree compile/runtime/install results
  are appended below after verification. Python/QC LSP had no recorded diagnostics; QC compilation, not clangd,
  is the parser/build evidence.
- Independent reviewer could not start: `/usr/bin/node` missing `libsimdjson.so.36`, runner exit127. No model/CLI
  fallback and no independent-review pass claimed. Parent source review added the numeric/depth fail-closed tests.
- An overbroad worker comment replacement removed part of cl_scores; caught before install by compilation.
  Exact earlier UI tool edits were replayed against the pinned baseline in scratch, preserving the intentional
  Normal-label tail changes; recovery diff and successful subsequent compile retained. Failed logs stay failed.

Private operational logs/artifacts are retained under the owned task root
`FTESurf-worktrees/requests-20261119-5a3b/` (OWNER.md/CHECKPOINT.md). No credentials/player rows in audit snapshot.

## Delivery boundaries

- No public release/updater, lobby fleet or live backend/catalogue deployment performed.
- **Backend order is mandatory:** next guarded surfd generation must include the `course zones` parser/gate,
  THEN use guarded `tools/story_push.py` catalogue validation/promotion. Old backend cannot parse the new directive.
  Handoff: `backend-pending.md`. Never overwrite a sealed live backend directly.
- Nightingale still needs Lex's B4/B5 zones; availability updates through Story's existing worker/TTL, not instantly.
- Real rendered cursor/dimming/centering, editor drag/scale/hide and actual stage-finish placement remain owner
  acceptance checks in `../lextest.md`. Headless console checks do not exercise CSQC_UpdateView or prove pixels.
- Supported fleet deployment is PowerShell-based (`src/build.ps1 -Pi`); `pwsh` is unavailable locally and on
  the Pi. The read-only SSH probe succeeded but general noninteractive root (`sudo -n /usr/bin/true`) is unavailable;
  the sealed backend generation needs its privileged stage/seal/systemd steps. No ad hoc deploy path, direct live
  backend overwrite or root-policy bypass was attempted. Releases are separate and were not requested/performed.

## Final parent build / local install — 19 November 2026, 05:47 UTC

- Implementation source commit: `4cd92390fbf1b963bf879dbc13cd65f3b3f4f21e`, independently checked out clean under
  the owned task root. All three VMs compiled using the exact Linux wrapper flags, **exit0 / zero warnings**.
  The first manual compiler invocation used unsupported flags/`-src`; its failure is retained as
  `artifacts/clean-build/sv_progs.invocation-failed.log`. Corrected to the documented wrapper's `-srcfile` on the
  same source/tree/artifact cohort; no source defect or new compiler workaround was introduced.
- `qcframes.py`: server/client **zero frame-global hits**; menu has **three existing hits**. The exact same
  compiler/options against baseline `163ef4ed` reproduce the identical `(function,global)` set:
  `ui_dl_cancel_ready/dl_have_cancel`, `MF_PresencePoll/mf_linkstate`, `Sty_AskMe/mf_linkstate`. **Zero new hits**,
  not a clean scanner exit. This preserves the existing P1617 finding rather than silently repairing peer code.
- The same clean-baseline control reproduces the navigation PF_CF failure and both social configured-verifier
  errors; current code adds three navigation checks and one passing social transport check without new failures.
- Clean implementation tree rerun: Story54, Groups10, focused regressions4 all pass. `story_push.py --check` passes
  against the live public map roster, **not copied**. It still reports the existing missing route spots and
  unzoned sinister/fruits2/1998/kismet; those are explicit authored/content follow-ups, not parser failures.
- Owned native Linux headless engine probe against the exact final artifacts: CSQC loaded, mode/source commands
  acted (Backwards → Normal, Segmented → Normal), Splits editor commands accepted, end marker reached, exit0,
  no unknown command/VM error; owned process stopped. This does **not** run CSQC_UpdateView or prove clicks/pixels.
- Ran the canonical `/home/lex/Projects/WorldofSurf/wos-build.sh`; the installed local three VMs match the
  clean-checkout artifacts byte-for-byte. Previous local progs preserved in the owned artifacts for rollback.

| Local artifact | SHA256 |
|---|---|
| qwprogs.dat | `e76cb0c28c70a8b9728b51ac6c460e536964065a3b324d25d070c5460270ea66` |
| csprogs.dat | `7d3d0dffffc7821e959a87d87516838012503ec5998c4b0c96b71caed4b24149` |
| menu.dat | `8ca956bcc81ace34cef09ddfdc21613d6125436877e0441a5a1228f5142eefc0` |

Final parent review additionally found that the first course gate omitted curated/shipped overrides. The follow-up
adds the full seven-position game-before-Momentum file priority (configurable SURFD_ZONES_CURATED/LIBRARY for the
game's curated/local library paths). The extended priority test fails on the original three-directory gate,
then passes with the fix; Story54 passes again. This changes backend Python/tests/docs, not QC source or these
compiled bytes. The native engine pin/tag and QC Build89 are unchanged. Fleet/backend/catalogue remain pending the supported
privileged deployment environment; Nightingale additionally awaits Lex's actual bonus zones. See `../lextest.md`
for the small rendered owner checks; the code is installed in the Linux development game for those checks now.
