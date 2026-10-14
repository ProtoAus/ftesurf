#!/usr/bin/env python3
"""Rebuild the World of Surf brand kit; no network or live-install writes.

Python dependencies and export recipe: src/brand/README.md. SVG glyphs are
outlined from the repository's OFL Bebas Neue font, not a system-font fallback.
Raster exports use a locally installed Chromium browser through Playwright.
"""

import argparse
import io
from pathlib import Path

from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont

ROOT = Path(__file__).resolve().parents[1]
FONT = ROOT / "ftesurf/gfx/fonts/BebasNeueRegular.ttf"
KIT = Path("src/brand")
SITE = Path("src/release/site")


def lettering(font, text, box, color):
    glyphs = font.getGlyphSet()
    cmap = font.getBestCmap()
    pen = SVGPathPen(glyphs)
    bounds = BoundsPen(glyphs)
    cursor = 0
    for ch in text:
        glyph = glyphs[cmap[ord(ch)]]
        for target in (pen, bounds):
            glyph.draw(TransformPen(target, (1, 0, 0, 1, cursor, 0)))
        cursor += glyph.width
    x0, y0, x1, y1 = bounds.bounds
    x, y, w, h = box
    scale = min(w / (x1 - x0), h / (y1 - y0))
    tx = x + (w - (x1 - x0) * scale) / 2 - x0 * scale
    ty = y + (h - (y1 - y0) * scale) / 2 + y1 * scale
    return (f'<path fill="{color}" transform="translate({tx:.6f} {ty:.6f}) '
            f'scale({scale:.6f} {-scale:.6f})" d="{pen.getCommands()}"/>')


def svg(w, h, title, body):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
            f'viewBox="0 0 {w} {h}" role="img" aria-labelledby="title">\n'
            f'<title id="title">{title}</title>\n' + body + '\n</svg>\n')


def wordmark(font, top, surf):
    return svg(720, 320, "World of Surf", '\n'.join([
        lettering(font, "WORLD OF", (150, 24, 420, 62), top),
        lettering(font, "SURF", (42, 110, 636, 186), surf),
    ]))


def sources():
    with TTFont(FONT) as font:
        dark = wordmark(font, "#f5f5f7", "#59bfff")
        icon = svg(256, 256, "WOS — World of Surf", '\n'.join([
            '<rect width="256" height="256" rx="48" fill="#59bfff"/>',
            lettering(font, "WOS", (22, 56, 212, 144), "#00131f"),
        ]))
        social = svg(1200, 630, "World of Surf", '\n'.join([
            '<rect width="1200" height="630" fill="#070b12"/>',
            '<path d="M96 64H1104" stroke="#59bfff" stroke-width="4"/>',
            '<g transform="translate(168 110) scale(1.2)">',
            lettering(font, "WORLD OF", (150, 24, 420, 62), "#f5f5f7"),
            lettering(font, "SURF", (42, 110, 636, 186), "#59bfff"),
            '</g>',
            '<path d="M96 566H1104" stroke="#254052" stroke-width="2"/>',
        ]))
        return {
            SITE / "worldofsurf-wordmark.svg": dark,
            SITE / "favicon.svg": icon,
            KIT / "wordmark-light.svg": wordmark(font, "#142431", "#0873a3"),
            KIT / "wordmark-mono.svg": wordmark(font, "#000000", "#000000"),
            KIT / "wordmark-white.svg": wordmark(font, "#ffffff", "#ffffff"),
            KIT / "wos-mono.svg": svg(256, 160, "WOS — World of Surf",
                                      lettering(font, "WOS", (8, 8, 240, 144), "#000000")),
            KIT / "social.svg": social,
        }


def exports(browser_path):
    from PIL import Image
    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        browser = pw.chromium.launch(executable_path=browser_path, headless=True)
        try:
            page = browser.new_page(device_scale_factor=1)
            page.route("**/*", lambda route: route.abort())

            def raster(source, width, height):
                page.set_viewport_size({"width": max(256, width), "height": max(256, height)})
                # Clip small exports: Edge cannot reliably capture a 16px viewport.
                # Only our self-contained SVG is rendered; no file or HTTP inputs.
                page.set_content(f'<style>html,body{{margin:0}}svg{{display:block;width:{width}px;height:{height}px}}</style>' + source)
                return page.screenshot(omit_background=True, animations="disabled",
                                       clip={"x": 0, "y": 0, "width": width, "height": height})

            src = sources()
            icon = src[SITE / "favicon.svg"]
            files = {SITE / "og-worldofsurf.png": raster(src[KIT / "social.svg"], 1200, 630)}
            for size in (180, 192, 512):
                name = "apple-touch-icon.png" if size == 180 else f"worldofsurf-{size}.png"
                files[SITE / name] = raster(icon, size, size)
            ico = io.BytesIO()
            # Render each small size at its native pixel grid; no thumbnail resampling.
            sizes = (16, 24, 32, 48, 64, 128, 256)
            images = [Image.open(io.BytesIO(raster(icon, n, n))).convert("RGBA") for n in sizes]
            images[-1].save(ico, format="ICO", sizes=[(n, n) for n in sizes], append_images=images[:-1])
            files[KIT / "worldofsurf.ico"] = ico.getvalue()
            print("Raster browser:", browser.version)
            return files
        finally:
            browser.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--browser", help="absolute path to an installed Chromium/Edge executable")
    parser.add_argument("--out", type=Path, default=ROOT, help="output root (default: this source tree)")
    parser.add_argument("--check", action="store_true", help="compare exports without writing")
    args = parser.parse_args()
    files = {p: s.encode("utf-8") for p, s in sources().items()}
    if args.browser:
        files.update(exports(args.browser))
    else:
        print("SVG only; pass --browser to include PNG/ICO exports.")
    for rel, data in files.items():
        path = args.out / rel
        if args.check:
            if not path.is_file() or path.read_bytes() != data:
                raise SystemExit(f"Export differs: {path}")
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        print(("Checked " if args.check else "Wrote ") + str(rel))


if __name__ == "__main__":
    main()
