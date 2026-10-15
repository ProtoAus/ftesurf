# P720 — single-screen homepage

## Scope and product

User follow-up: one full page with Windows and Linux downloads, without the
scroll-down sections. Product `642a40e1ce21306561f5303bfcfd0281753474d9`, isolated
from QC `a9dce85f27f94b6c89672b6b63fc5659801ebe4c` and ledger `0a716de6a`.

One hero now contains both direct archive links, wordmark, short description,
required Steam games and launcher guidance. Project/licence/manifest links stay
in a compact footer. Responsive viewport layout removes all lower feature,
screenshot, setup and verification sections. Archive byte counts/SHA256 and
compatibility metadata remain on download titles and in the build manifest.

No anti-cheat content, site JavaScript, runtime, evidence, signed release,
archive, receipt, feed, engine pin/tag or QC Build-number change. No game build,
backend deployment or service restart. CSS changes are scoped to the homepage;
its URL gets a fresh cache key. Obsolete lower-section test assertions now check
the direct archive links/filenames instead. Release token contracts are intact.

## Acting checks

- `python tools/test_site_copy.py`: 6 pass. Predecessor control with
  `--revision a9dce85f27f94b6c89672b6b63fc5659801ebe4c`: 5 failures; unchanged
  parser, anti-cheat and slogan checks pass.
- `python tools/test_rebrand.py`: 7 pass.
- `pwsh -NoProfile -File src/release/test_releaselib.ps1`: 76 pass, 0 fail.
- Published receipt rendered with existing receipt helpers and exact Windows /
  Linux token sets. No unresolved token or inline-token script introduced.
- Local predecessor: both actual archive links exist, but all five viewport
  controls falsify one-screen fit and above-fold availability.
- Local subject AND public Chrome: **1440x900, 1280x720, 390x844, 320x568,
  844x390**. Document dimensions fit each viewport exactly, without vertical or
  horizontal scrolling; both platform buttons are fully visible. Loaded
  wordmark/resources, unclipped navigation, one section, no details panels.
  No page/resource errors. Missing-resource control returns 404.
- JavaScript-disabled phone still fits and exposes both downloads. At simulated
  200% CSS zoom, both downloads remain reachable by normal scrolling; no content-hiding rule
  forces artificial single-screen fit. Desktop/mobile screenshots inspected.
- Protected-receipt mutation dry run refuses; restored subject accepts exactly
  index.html and site.css. Prior pointer and whole tree are preserved.
- All 20 public files match expected SHA256. Both unchanged archive endpoints
  answer browser-like one-byte range probes with 206 and receipt-matching total
  lengths (42,381,944 Windows; 42,225,560 Linux). No full archive installation or
  new binary verification is claimed.

Failed iterations retained as failures: an inline optional-Linux marker was
rejected by the whole-line block parser and moved onto its own line; obsolete
verification-panel ID assertions were replaced for the requested removal;
320x568 initially overflowed by 81px and 844x390 by 10px. Reduced spacing/logo /
button padding for short screens, then reran all five controls and subjects.
A bare Python HEAD archive probe returned 403; browser-like range HEAD/GET
probes returned 206 for both endpoints. No server/CDN policy was changed.

## Live publication

**2026-10-15 02:00:04 UTC**, locked `src/release/present.py` transaction:

- Current: `presentations/sitecopy-fullpage-20261015-7f2df7`
- Rollback retained: `presentations/sitecopy-20261015-7f2df7`
- 20 files; only index.html/site.css change. Anti-cheat HTML, version.json,
  both update feeds and all other files remain byte-identical. Prior complete
  presentation manifest is unchanged.

```
index.html  7bd6e1387df1da4b188d8445f1006899a8117981d96ab0c4d6fb9bae38620bd4
site.css    35226dd2d38c113a025e9758929e5c94c61b0e6a72f0a3fb7a8585650dd97497
```

Published completion-guidance-only AGENTS.md commit `d86f560` arrived during
verification. Read and merged it without changing tested/published site bytes.
No backend, account round trip, game runtime or detector acceptance is inferred
from this static-site check.
