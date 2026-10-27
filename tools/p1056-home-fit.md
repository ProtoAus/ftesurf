# P1056: all Home lobbies and stats without scrolling

## Request / change

Owner confirmed P1054 "yes it works", then requested every lobby and every stat
visible without scrolling. That confirmation is recorded as manual P1054 menu
acceptance only, not proof of Steam/DM/API/performance cases they did not observe.

- Home uses its available window area (up to1660x920) and an adaptive lobby grid:
  four columns in the observed1920x1111 window, three at1280x720, two at800x600.
  All12 directory rows are drawn as clickable cells in port order, no lobby list
  view or scroll window. Larger fleets compress into numbered cells instead of
  silently dropping lobbies. At the64-row stress cap/800x600 the cells are
  numbered-only; this does not claim all map/player metadata is readable there.
- Four summary cards, all8 tiers plus Unrated and both Story/Event cards are
  always present. Tier rows use a two-column grid, compact bars at short window
  heights. No stats list view/scroll. Unknown/offline data is `--`, not zero.
- A populated runtime exposed the old tier decoder feeding an integer JSON
  length into MENU min's untyped tail: only Tier1 and Unrated were loaded. Convert
  the length to float first; all nine rows now have values. Standard and extra
  tiers have stable indexed slots rather than conflating missing data with zero.
- Stats reuse Story/map boards' existing configured, consent-gated GET interface;
  social proofs remain fixed to the trusted social endpoint. Loaded own stats do
  not blank during ordinary refresh; failures retain values with a stale note.
- Version/update hints live in the Home tab strip rather than covering Friends.
  The ready/downloading states and F2 access remain. Compact lobby text no longer
  overlaps, and the chat waiting message wraps at narrow widths.

## Verification (2026-10-27 UTC)

Predictions and retained runner: owned task root
`C:\FTESurf-worktrees\menu-20261026T1632Z`, `PLAN-home-fit.md` and
`home-fit-smoke.py`. It reuses `tools/test_ui_maps_runtime.py`'s owned overlay,
console transport, process gate and verified junction cleanup. Only synthetic
profile/directory/story data was seeded, never live identity/player files.

- Live read-only directory showed12 lobbies. Old P1054 control received the local
  twelve-row fixture, rendered the first lobby but did not hold `home_lob11` as a
  control: the old scroll window was the subject of the complaint, not an empty
  fixture. Control evidence: `artifacts/home-fit/control-c9aef627f2`.
- Standard pwsh7 `src/build.ps1 -Jobs 8 -NoDeploy`: server/menu0 warnings;
  CSQC the SAME two untouched cl_viewmodel setproperty227 warnings; zero new.
- Final populated real-client subject at EXACT1280x720,1920x1111 and800x600:
  all12/12 lobby cells; all9 populated WOS and Everything tier rows; their bottom
  bounds above Story/Event; synthetic Story2/4 and Event1/3 loaded; last lobby's
  action present; WOS/Everything clicks acted. Actual PNG dimensions checked,
  not inferred from command arguments. `vid_winmaximize 0` was needed in the
  isolated fixture to stop the engine's default maximizing window policy from
  superseding the requested size. No owner video settings changed.
- Stress64/64 cells at800x600, including last action, no scroll/tail or bottom
  overflow. Legacy service omitting new WOS fields: native cards unknown, real
  Everything values remain, all9 tier labels visible. Offline: every card/tier
  label remains visible with unknown values. Screenshots inspected for all cases.
- Qualified subject: `artifacts/home-fit/subject-b07cfcbbd6`; final exact-commit
  `051ac299` rebuild repeated the same cases as `subject-d225830031` and passed.
  Its byte-identical tested menu is the installed payload. Initial requested-size
  failure, incomplete-tier screenshot and fixture routing correction are retained
  as failures/diagnostics, not passed coverage. They do not describe the final
  corrected subject. The original fixture incorrectly used story=progress rather
  than the existing story=player route; the corrected route populated both cards.
- This is local synthetic UI evidence, not real Steam/chat acceptance, production
  stats availability or a numerical frame-time claim. Existing backend/API,
  website and CSQC/SSQC promotion remains outside this menu-only deployment and
  subject to the already-recorded guarded-cohort coordination requirement.

## Installation / retention

Installed BOTH `C:\FTESurf\ftesurf\menu.dat` and
`C:\FTEQuake\ftesurf\menu.dat` at **2026-10-27T03:35:51Z**, from inspected/pushed
QC `051ac299c880c4701176ca1ff611bdd3fe2f6d8a`. Both destinations and the tested
runtime menu SHA256:
`178c518cb9ed502c0fc3dbf3db9c8fee48469ee9735c43ceb3c4b3e8d96b8ee6`.
Predecessor hash/identity checks acted at swap; both unique adjacent rollback files
are `menu.dat.pre-p1056-home-20261027T033551Z`. All16 protected binary/plugin/
progs/config hashes stayed unchanged. No game process existed at the boundary;
none was terminated. No native/plugin, CSQC, SSQC, website, API, config or player
data changes were part of this swap. UTC receipt:
`artifacts/menu-local-install/20261027T033551Z/receipt.json`; immutable source/
artifact manifest: `artifacts/p1056-manifest.json`. The short canonical menu claim
was released after both hashes verified. Engine docs are pushed as `5f33b8166`;
the clean engine documentation worktree was retired. Five owned generated build
directories were archived, hash-verified and retired; source/staging/runtime
screenshots/logs are intentionally retained for acceptance and coordinated API
promotion. Restart MENU with `menu_restart`, then `menu_main`.

A peer's stale canonical build replaced only FTESurf's P1054 menu at02:46:18Z
while FTEQuake retained it. The P1056 claim identifies only the exact conflicting
menu destinations/short swap boundary; no broad build pause or process kill was
used. Do not infer a missing feature from that overwrite or repair unrelated
peer source. Use clean inspected builds and preserve the verified menu when
performing independent native/TAS promotion.
