# P719 — minimal website copy

## Scope

Product commit: `eaa87531941336b70b1ce017a7072a4c692777de`, isolated from
QC `afd6c514602e2d04cf0b8a96953f2d66acb11973`. Website only. No game build,
engine pin/tag, QC Build number, detection/evidence semantics, signed release,
archive, account service, leaderboard implementation or lobby restart changed.

- Homepage: one movement description, four feature bullets, download requirements
  and setup. Remove statistics, repeated tiles and promotional slogans.
- Anti-cheat: explain the recorded data, server physics replay, input analysis,
  review, board separation, badge meaning and verification limits. Correct the
  old implication that verification precedes every ranked-board appearance.
- Plain requirements/setup lists and compact article layout. Version the CSS
  URL so previously cached styles do not obscure the new presentation.
- Main-content word counts, including collapsed support details: homepage
  701 -> 451; anti-cheat 345 -> 192. Homepage 5 -> 3 sections; anti-cheat 5 -> 4.

## Verification

- `python tools/test_site_copy.py`: 6 tests pass. Final predecessor control
  (`--revision afd6c514602e2d04cf0b8a96953f2d66acb11973`) fails 21 copy assertions;
  parser and download/support controls still pass. Initial control failed 20
  before adding the automation-description assertion.
- `python tools/test_rebrand.py`: 7 tests pass.
- `pwsh -NoProfile -File src/release/test_releaselib.ps1`: 76 pass, 0 fail.
- Published 0.1.25 receipt rendered with `Get-ReceiptTokens`, `Split-PageBlocks`
  and exact Windows/Linux token-set checks; no unresolved tokens.
- Local AND public Chrome: homepage/anti-cheat at 1440x1000 and 390x844.
  No horizontal overflow, JavaScript errors or failed resource requests.
  Loaded images, download anchor, all details and four clipboard buttons act.
  Missing-resource control returns 404. Inspected full-page desktop/mobile
  screenshots show the compact layout and readable article.
- Presentation dry-run accepts exactly three changed files; deliberately
  modified receipt is refused, with the predecessor pointer unchanged.
- Final `git diff --check` clean. LSP records no diagnostics for the changed
  HTML/CSS/test (not a substitute for rendering/browser checks).

Initial test-authoring failure: support assertions guessed Linux element names,
archive command spelling and build label instead of reading the template.
Corrected the test to the unchanged existing IDs/commands, then reran the
predecessor control and subject. No product behavior was changed to satisfy it.

## Published presentation

UTC: **2026-10-15 01:32:29**. Exact clean product commit rendered and published
with `src/release/present.py`, under the shared publication lock:

- New pointer: `presentations/sitecopy-20261015-7f2df7`
- Preserved rollback pointer: `presentations/brand-20261014T1750Z`
- Complete tree: 20 files; exactly `index.html`, `anticheat.html`, `site.css`
  changed. Predecessor whole-tree manifest unchanged.
- All 20 files fetched from `https://proto.bar/ftesurf/` and SHA256-compared.
  `version.json`, `update.json`, `update-verified.json` and every other unchanged
  file remain byte-identical. Release version and advertised archive build
  labels still come from the original receipt.

Changed-file SHA256:

```
index.html      624c36426957b9c9e4273cb0b558dd7c0c0c1f3bce9616f4a9d49a0a9988ead5
anticheat.html  69079c6fbaeea26dc1a25f773391bafe643d64b13284b80959b64d7ddfabb96d
site.css        7c49783107a28e7841349be4ae90add9b05ea2c4b73611e765b7fb4097ffc278
```

Limits: browser checks cover these two static pages and their existing links/
controls. No new detector effectiveness, native/Linux game execution, archive
installation, account round trip or leaderboard-backend acceptance is claimed.
