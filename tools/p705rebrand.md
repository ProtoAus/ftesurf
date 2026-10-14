# P705 — World of Surf, stage 1: art and web presentation

## Problem

The rename plan had an approved title and future canonical website, but the
landing page, board, account pages and social card still presented FTESurf/FTE.
A global replacement would also damage real download instructions, signed
account statements, update identities and service paths.

## Change

- Reuse the established dark/cyan, type-led direction. Full **World of Surf**
  wordmarks (outlined SVG, dark/light/black/white), compact **WOS** icon,
  1200×630 social card, SVG favicon, 180/192/512 PNG and seven-size native ICO.
  `src/brand/index.html` is an offline art gallery; `src/brand/README.md` records
  inventory, licensing and exact export commands. Native icon integration is
  **not** part of this patch.
- Landing/Anti-Cheat titles, header, full-wordmark hero, product prose, image alt
  and OG/Twitter metadata; explicit modified-FTEQW acknowledgement. New
  `og-worldofsurf.png` key avoids overwriting the old card's cached identity.
- Board static/dynamic titles, native-source badge/tab/tooltip use WOS or World
  of Surf. The tab still sends `tier=ranked`; source/wire classifications stay
  unchanged. Tune the compact header so its visible links fit at 320px.
- Account shared title/mark, consent, return/error and instruction copy only.
  No callback/cookie/signature/account behavior changes.
- Add the source audit/migration plan to version control and record stage state,
  compatibility boundaries and human acceptance. `ENGINE.txt` patch increments;
  engine commit/tag, qcbuild and release version do not.

## Verified — 2026-10-14 UTC, isolated source candidate

Game base: `a5a04db48174d29edbc9e5585bffd818bf150db8`.
Engine ledger base: `28367212b9f3a9f843e99f0fd8745c6775ce2b4e`.
Fresh fetch/max over both patch headings and untracked pNNN filenames was 704;
this task allocated 705. Canonical game source/engine checkouts had unrelated
changes; none were built, reset or included.

Pre-registered controls were recorded before mutation in the owned task's
`artifacts/PLAN.md`. Commands (run from this source tree):

```text
python -B tools/test_rebrand.py
python -B surfd/test_web.py
python -B surfd/test_accounts.py
python -B surfd/test_board.py
node --check surfd/web/board.js
python -B tools/brand_assets.py --browser <installed-edge> --check
python -B tools/test_rebrand_browser.py --browser <installed-edge> --out <owned-artifacts>
```

- New regression suite: **7 passed**. Existing suites: **268 web**, **400
  accounts**, **351 board** checks, **zero failures**. Node syntax passes.
- Original *complete* landing/Anti-Cheat/board pages fail the visible-brand
  detector; all three subjects pass. This is an acting negative control, not
  a claim from an empty search.
- Account Python AST is identical to base after only the specified display
  string substitutions. Board JS bytes are identical after only its nine
  display substitutions. No backend/API/data code was changed.
- Signed `FTESURF-ACCT 1`, six `ftesurf-*` account tags, wire `ranked` tier,
  download template tokens and actual `ftesurf.bat`, `./ftesurf.sh`, `FTESurf`
  archive-folder instructions remain pinned by tests.
- SVGs are outlined/self-contained; PNG dimensions and all seven ICO entries
  checked. Rerender/check of every SVG/PNG/ICO byte-matches using fontTools
  4.60.1, Pillow 12.3.0, Playwright 1.55.0 and **Edge 155.0.4283.45**. Neither
  exporter nor preview needs a browser download or a new runtime dependency.
- Loopback-only browser: landing/Anti-Cheat/board/account at **320, 390, 768,
  1440px**, account light/dark, gallery desktop/mobile, no document/nav overflow;
  all five board-route titles; WOS tab actually selected the `ranked` route and
  retained the synthetic row. Checked both `/ftesurf/` and `/worldofsurf/`
  relative-link fixtures, resource requests and explicit missing-resource 404.
  No page/resource errors. No-JS landing retains the full visible wordmark.
- Inspected actual desktop/mobile screenshots, account light, social card and
  tiny-icon gallery. Board rows are labelled **SAMPLE PLAYER (local fixture)**;
  the map shot fixture explicitly says it is not map art.
- LSP was queried for edited Python/JS: no diagnostics recorded. That is not
  relied on as execution proof; the above suites and browser controls acted.

### Retained failures and fixes

- Edge hung on a 16px viewport screenshot during the first art export. The
  exporter now renders in a >=256px viewport and clips each native-size icon.
  The complete export and byte-for-byte rebuild then passed.
- First preview attempt imported `test_accounts.py`, which executes its entire
  suite on import. Its missing-verifier control was confounded by the preview
  tool's own `tools/` import path. The preview no longer imports that suite;
  it obtains the actual link page from the existing web fixture instead. The
  standalone accounts suite passes in its documented execution environment.
- Pixel inspection exposed cropped mobile header text even though document
  width passed. Compact spacing was fixed and the falsifier now also checks
  the nav scroll width; the rerun passes.
- Adding the resource-error detector exposed a missing *fixture* map shot. A
  labelled synthetic JPEG now exercises the real shot endpoint. No product
  fallback was changed to conceal a 404.
- A post-commit rerun caught a hash-navigation timing race in the preview test:
  `networkidle` alone did not prove the new board had rendered. Before publication,
  the harness was strengthened to await each exact route title, the WOS control
  and its actual `tier=ranked` HTTP response/pressed state. No product navigation
  logic was changed; the bounded source candidate was reverified.

## Delivery boundary and next gate

**Source candidate only; no live deployment/public release.** No native/QC
binary, launcher, endpoint, nginx configuration, service, account path, updater
feed, storage format or player data has moved. Runtime/evidence semantics are
unchanged, so no recorder-corpus migration is being asserted. Existing art and
wrapper filenames remain reachable/accurate. The old social `og.png` is retained
but not referenced by new metadata.

The staged OG/Twitter URLs intentionally remain on `/ftesurf/` until the
canonical route/account transition is actually ready. Local relative-link
checks do **not** verify nginx MIME/cache configuration, signed Steam callback
preservation or public reachability. Do not publish this as a complete cutover.
Owner art acceptance is in `lextest.md`; then proceed through
`REBRANDING_PLAN.md`'s remaining game/engine/launcher/compatibility/release gates.
No full on-disk rename or player-data migration has been silently selected.
