# World of Surf — stage 1 brand kit

**Presentation candidate, not a live cutover.** Retain the established dark/cyan,
type-led direction: **World of Surf** is the full name; **WOS** is the compact
badge; **WorldofSurf** is the technical/public-path spelling when a later stage
actually migrates that surface. No new wave symbol or tagline. FTEQW remains the
engine attribution, never the product's short name.

## Assets and use

| Asset | Location / intended use |
|---|---|
| Dark full wordmark | `../release/site/worldofsurf-wordmark.svg`; transparent, white/cyan, 720×320 |
| Light full wordmark | `wordmark-light.svg`; dark/deep blue, transparent |
| One-color full wordmark | `wordmark-mono.svg` (black), `wordmark-white.svg` (white) |
| One-color compact mark | `wos-mono.svg`; black, transparent |
| Compact color icon | `../release/site/favicon.svg`; dark WOS on cyan |
| Social source/export | `social.svg` → `../release/site/og-worldofsurf.png`, 1200×630 |
| Square exports | `../release/site/worldofsurf-{192,512}.png` |
| Apple touch export | `../release/site/apple-touch-icon.png`, 180×180 |
| Future native icon | `worldofsurf.ico`, native-grid 16/24/32/48/64/128/256 entries; **not wired to the engine yet** |

The vectors contain outlined glyphs: no runtime font loading, embedded script,
remote content, or dependency on an installed system font. Keep proportions and
clear margins. Use the light variant on light backgrounds, the white or cyan
variant on dark backgrounds. Do not put the light-background blue on black. Use
the compact icon rather than squeezing the full wordmark into a favicon.

Palette: cyan `#59bfff`, dark ink `#00131f`, white `#f5f5f7`, social background
`#070b12`. The existing site font and palette remain in use. Nav text uses the
same two-line hierarchy, with a complete accessible “World of Surf home” label.

Bebas Neue Regular comes from `ftesurf/gfx/fonts/BebasNeueRegular.ttf`, with its
SIL Open Font License in the adjacent `OFL.txt`. Preserve that notice with
redistributed art (the site already ships `OFL.txt`). The supplied font is not
modified or renamed. Brand sources/exports are part of this GPLv2-or-later game
repository; the upstream font retains its OFL terms.

## Rebuild (development only)

Use an isolated Python environment, not a live server install:

```text
python -m pip install fonttools==4.60.1 Pillow==12.3.0 playwright==1.55.0
python tools/brand_assets.py --browser "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe"
python tools/brand_assets.py --browser "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe" --check
python tools/test_rebrand.py
python tools/test_rebrand_browser.py --browser "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe" --out <owned-artifact-directory>
```

No browser download is needed; pass a locally installed Chromium executable.
`--out <root>` exports into that root's `src/brand` and `src/release/site` rather
than this checkout. Omitting `--browser` rebuilds/checks **SVG only**. Nothing is
installed into an owner's game or live website. Browser raster versions can
change pixels; record the printed version and compare the exports before
accepting a new renderer. The initial exports used Edge 155.0.4283.45 (verify
against the stage receipt if re-exporting).

The browser falsifier also needs Flask (the existing surfd test dependency).
It starts/stops its own loopback HTTP server, blocks
non-loopback browser requests and uses disposable synthetic surfd test fixtures.
It checks 320/390/768/1440px pages, account light/dark, all five dynamic board
titles and the WOS-tab → `tier=ranked` action under **both** base paths. These
are local relative-link checks, not nginx/Steam callback-path migration proof.
Its Linux download fields are explicitly sample values, not a release manifest.

## Compatibility boundaries / next gate

This candidate changes public **copy and art**, not identity or data. Signed
account tags, wire tiers, service paths, config/cookies, evidence formats,
updater feeds, executables, launch wrappers and the `ftesurf` gamedir are
unchanged. The download instructions intentionally still name the files and
archive folder a player will actually receive. Social URLs intentionally remain
under `/ftesurf/`; a new image basename avoids reusing the old card's cache key.
The prior `og.png` is retained as a legacy asset, not used by the new metadata.

Before public launch: owner accepts art; test nginx and all asset MIME types,
cache behavior and screenshot loads; migrate account paths as a set (never
redirect signed in-flight callbacks); update canonical/OG URLs only when the new
route is real; then deploy source-compatible web changes from an inspected
commit. See `REBRANDING_PLAN.md` for subsequent runtime, launcher/update and
packaging gates. This stage does not claim native launcher/icon integration or a
rebranded game build.
