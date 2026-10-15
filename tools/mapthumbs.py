#!/usr/bin/env python3
"""
mapthumbs.py -- pack every map's screenshot into a few atlas pages the menu can
draw from, and write each map's page/cell back into data/mapmeta.txt.

WHY AN ATLAS, and not just one texture per map.

Momentum's cached screenshots are 480x270 (`-small`) and 1920x1080 (`-large`).
There are ~1400 of the small ones on this install.  Three things rule out drawing
them directly in the map list:

  1. MenuQC has no `freepic` declared (it is builtin #453 in the menu VM,
     pr_menu.c:2746, but absent from defs/m_defs.qc), so a naive per-row
     `drawpic` cache has no eviction and grows without bound.  1400 pics at
     480x270 RGBA is ~725 MB of VRAM.
  2. `drawpic` loads through Shader_Default2D, which sets IF_NOMIPMAP
     (gl_shader.c:7452-7464).  A 480x270 source scaled into an 84 px row has no
     mip to sample and shimmers as the list scrolls.  Baking near the display size
     is the fix, and it has to happen somewhere -- there is no QC resize builtin.
  3. Scrolling a 2000-row list would fault in a new texture per row per frame.

So: box-downscale once, offline, to CELL_W x CELL_H, and pack COLS x ROWS of them
into each PAGE x PAGE atlas.  The menu then holds a bounded handful of textures and
draws each row with one `drawsubpic`.  At 128x72 in a 2048x2048 page that is 448
maps per page -- three pages for the whole library, ~50 MB, paid once at load.

SOURCE PRECEDENCE, per map:

    _cache/images/<uuid>-small.jpg      Momentum's own, already 480x270
    _cache/images/<uuid>-large.jpg      when only the large one was cached
    gfx/mapshots/<uuid>-small.jpg       fetched from the CDN by tools/mapfetch.py
    gfx/mapshots/ksf/<map>.jpg          KSF's picture, fetched by tools/ksfshots.py
    ftesurf/screenshots/<map>.<ext>     your own F5 grabs

The third exists because Momentum only caches an image once its own UI has shown you
that map, which left 751 of 2172 maps with a thumbnail id but no file.  mapfetch.py
GETs those from the URL the cache record already carries; see its docstring.

The fourth is keyed by NAME, not uuid, so it is how a KSF-only map (a `ksf` row in
mapmeta.txt, with no uuid) gets a picture at all.

The fifth exists because CS:S-only maps are in neither of Momentum's caches -- the
library has 1084 loose BSPs in cstrike/maps that Momentum has never indexed.  Take a
screenshot in-game, name it after the map, re-run this, and it gets a thumbnail like
everything else.

Anything with no source at all keeps `-` for page/cell and the menu draws its
placeholder.  That is deliberate: a wrong picture is worse than an obvious absence.

Usage:
    python mapthumbs.py                 # rebuild the atlases and patch mapmeta.txt
    python mapthumbs.py --report        # also say what resolved and what did not
    python mapthumbs.py --limit 50      # small run, for checking the packing
    python mapthumbs.py --gamedir DIR   # another tree's mapmeta, atlases and pictures
"""

import argparse
import json
import os
import re
import sys

try:
    from PIL import Image
except ImportError:
    raise SystemExit(
        "mapthumbs.py needs Pillow for the JPEG decode:  python -m pip install Pillow")

MOMENTUM = r"C:\Program Files (x86)\Steam\steamapps\common\Momentum Mod Playtest\momentum"
SURFDIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # C:\FTESurf
GAMEDIR = os.path.join(SURFDIR, "ftesurf")
# The picture sources under the gamedir; main() repoints them at --gamedir.
SHOTS = os.path.join(GAMEDIR, "screenshots")
FETCHED = os.path.join(GAMEDIR, "gfx", "mapshots")              # tools/mapfetch.py
KSFSHOTS = os.path.join(FETCHED, "ksf")                         # tools/ksfshots.py

# 16:9, and an exact divisor of PAGE on the x axis so a cell never straddles a
# texel boundary the sampler would then have to guess at.
CELL_W, CELL_H = 128, 72
PAGE = 2048
COLS = PAGE // CELL_W                 # 16
ROWS = PAGE // CELL_H                 # 28
PER_PAGE = COLS * ROWS                # 448

SHOT_EXTS = (".png", ".jpg", ".jpeg", ".tga", ".bmp")
FALLBACK_IMAGES = None
THUMB_IDS = {}

# mapmeta.txt column indices, matching what mapmeta.py writes
C_NAME, C_PAGE, C_CELL, C_THUMB = 1, 6, 7, 8


def read_meta(path):
    """Return (header_lines, [token_list, ...]) preserving order and comments."""
    head, rows = [], []
    with open(path, "r", encoding="utf-8") as f:
        for raw in f:
            s = raw.rstrip("\n")
            if s.startswith("meta "):
                rows.append(s.split())
            else:
                head.append(s)
    return head, rows


def source_for(name, uuid, momentum):
    """The best available image file for one map, or None."""
    if uuid and uuid != "-":
        uuid = THUMB_IDS.get(uuid, uuid)
        candidates = []
        for directory in (os.path.join(momentum, "_cache", "images"), FETCHED, FALLBACK_IMAGES):
            if not directory: continue
            for suffix in ("-small.jpg", "-medium.jpg", "-large.jpg", "-xl.jpg"):
                p = os.path.join(directory, uuid + suffix)
                try:
                    with Image.open(p) as im:
                        w, h = im.size
                    candidates.append((p, w, h))
                except (OSError, ValueError): continue
        # Pick a source large enough for the requested cell, not a small image
        # upscaled merely because it was encountered first. Decode only once.
        enough = [(p,w,h) for p,w,h in candidates if w >= CELL_W and h >= CELL_H]
        if enough: return min(enough, key=lambda c: c[1]*c[2])[0]
        if candidates: return max(candidates, key=lambda c: c[1]*c[2])[0]
    p = os.path.join(KSFSHOTS, name.lower() + ".jpg")
    if os.path.exists(p):
        return p
    for ext in SHOT_EXTS:
        p = os.path.join(SHOTS, name + ext)
        if os.path.exists(p):
            return p
    return None


def load_cell(path):
    """Decode, centre-crop to 16:9, box-downscale to one cell.  None on failure.

    Centre-crop rather than letterbox: the row is a fixed 16:9 slot, and a black
    bar inside it reads as a rendering bug rather than as an aspect mismatch.  Every
    Momentum image is already 16:9 so this only ever fires on your own screenshots.
    """
    try:
        im = Image.open(path)
        im.load()
    except Exception as e:                                      # noqa: BLE001
        print("  ! %s: %s" % (os.path.basename(path), e), file=sys.stderr)
        return None

    im = im.convert("RGB")
    w, h = im.size
    want = CELL_W / CELL_H
    have = w / h if h else want
    if abs(have - want) > 0.001:
        if have > want:                       # too wide -- trim the sides
            nw = int(round(h * want))
            x = (w - nw) // 2
            im = im.crop((x, 0, x + nw, h))
        else:                                 # too tall -- trim top and bottom
            nh = int(round(w / want))
            y = (h - nh) // 2
            im = im.crop((0, y, w, y + nh))
    # BOX is the right filter going down by ~4x: it averages every source texel
    # exactly once, which is the mip the GPU will not be building for us.
    return im.resize((CELL_W, CELL_H), Image.BOX)


def build(momentum, meta_path, atlasdir, limit=0, report=False, fill_missing=False, start_page=None):
    head, rows = read_meta(meta_path)
    os.makedirs(atlasdir, exist_ok=True)
    occupied = [int(r[C_PAGE]) for r in rows if r[C_PAGE].isdigit() and r[C_CELL].isdigit()]
    first_page = max(occupied) + 1 if occupied and fill_missing else 0
    if start_page is not None:
        if not fill_missing or start_page < first_page: raise ValueError('start-page overlaps existing cells')
        first_page = start_page

    resolved = []          # (row, source path)
    missing_uuid = 0
    missing_file = 0
    for r in rows:
        if fill_missing and r[C_PAGE].isdigit() and r[C_CELL].isdigit(): continue
        name = r[C_NAME]
        uuid = r[C_THUMB] if len(r) > C_THUMB else "-"
        src = source_for(name, uuid, momentum)
        if src is None:
            if uuid == "-":
                missing_uuid += 1
            else:
                missing_file += 1
            if not fill_missing: r[C_PAGE] = r[C_CELL] = "-"
            continue
        resolved.append((r, src))
        if limit and len(resolved) >= limit:
            break

    print("  %d maps with an image (%d of them KSF's), %d have no thumbnail id, "
          "%d id but no cached file"
          % (len(resolved),
             sum(1 for _, s in resolved if os.path.dirname(s) == KSFSHOTS),
             missing_uuid, missing_file))

    if fill_missing and not resolved:
        print('  no missing cells with available sources; existing metadata/pages unchanged')
        return 0, 0
    npages = (len(resolved) + PER_PAGE - 1) // PER_PAGE
    written = 0
    failed = 0
    slot = 0
    page_img = None
    page_no = -1

    for row, src in resolved:
        cell = load_cell(src)
        if cell is None:
            row[C_PAGE] = row[C_CELL] = "-"
            failed += 1
            continue

        p, c = first_page + slot // PER_PAGE, slot % PER_PAGE
        if p != page_no:
            if page_img is not None:
                out = os.path.join(atlasdir, "atlas%d.png" % page_no)
                page_img.save(out, optimize=True)
                print("  wrote %s" % out)
            page_img = Image.new("RGB", (PAGE, PAGE), (18, 18, 22))
            page_no = p

        page_img.paste(cell, ((c % COLS) * CELL_W, (c // COLS) * CELL_H))
        row[C_PAGE], row[C_CELL] = str(p), str(c)
        slot += 1
        written += 1

    if page_img is not None:
        out = os.path.join(atlasdir, "atlas%d.png" % page_no)
        page_img.save(out, optimize=True)
        print("  wrote %s" % out)

    # Remove stale pages from a previous, larger run so the menu cannot draw from
    # an atlas no row points into any more.
    for extra in ([] if fill_missing else range(page_no + 1, page_no + 16)):
        stale = os.path.join(atlasdir, "atlas%d.png" % extra)
        if os.path.exists(stale):
            os.remove(stale)
            print("  removed stale %s" % stale)

    if failed:
        raise RuntimeError('%d image decodes failed; metadata not replaced' % failed)
    with open(meta_path, "w", encoding="utf-8", newline="\n") as f:
        for h in head:
            f.write(h + "\n")
        for r in rows:
            f.write(" ".join(r) + "\n")

    if report:
        print("\n  %d cells over %d page(s), %d decode failures"
              % (written, npages, failed))
        print("  cell %dx%d, page %d, %d per page" % (CELL_W, CELL_H, PAGE, PER_PAGE))
        print("  menu draws these as gfx/mapthumbs/atlas<N>")
    return written, npages


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--momentum", default=MOMENTUM)
    ap.add_argument("--gamedir", default=GAMEDIR,
                    help="the ftesurf/ dir: pictures are read from its screenshots/ "
                         "and gfx/mapshots/, and it holds the two below by default")
    ap.add_argument("--meta", help="mapmeta.txt to patch (<gamedir>/data/mapmeta.txt)")
    ap.add_argument("--atlasdir", help="atlas output (<gamedir>/gfx/mapthumbs)")
    ap.add_argument("--limit", type=int, default=0, help="only pack the first N maps")
    ap.add_argument("--report", action="store_true")
    ap.add_argument("--images", help="XL/derivative source directory from mapmedia.py")
    ap.add_argument("--fallback-images", help="additional existing picture directory")
    ap.add_argument("--coverage", help="mapmedia coverage.json (deleted-thumbnail alternatives)")
    ap.add_argument("--fill-missing", action="store_true",
                    help="append new pages without shifting existing thumbnail cells")
    ap.add_argument("--start-page", type=int, help="first new page for fill-missing; must exceed existing pages")
    ap.add_argument("--cell-width", type=int, choices=(128,256,512), default=128,
                    help="128 is the game atlas contract; larger values are offline export layouts")
    a = ap.parse_args()

    global SHOTS, FETCHED, KSFSHOTS, FALLBACK_IMAGES, THUMB_IDS
    global CELL_W, CELL_H, COLS, ROWS, PER_PAGE
    CELL_W, CELL_H = a.cell_width, a.cell_width * 9 // 16
    COLS, ROWS = PAGE // CELL_W, PAGE // CELL_H
    PER_PAGE = COLS * ROWS
    FALLBACK_IMAGES = a.fallback_images
    if a.coverage:
        with open(a.coverage, encoding='utf-8') as f: coverage = json.load(f)
        for row in coverage['images']:
            if row.get('state') == 'ok' and row.get('requested_uuid'):
                if all(re.fullmatch(r'[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}', row[k]) for k in ('uuid','requested_uuid')):
                    THUMB_IDS[row['requested_uuid']] = row['uuid']
    SHOTS = os.path.join(a.gamedir, "screenshots")
    FETCHED = a.images or os.path.join(a.gamedir, "gfx", "mapshots")
    KSFSHOTS = os.path.join(FETCHED, "ksf")
    meta = a.meta or os.path.join(a.gamedir, "data", "mapmeta.txt")
    atlasdir = a.atlasdir or os.path.join(a.gamedir, "gfx", "mapthumbs")

    if not os.path.exists(meta):
        raise SystemExit("%s not found -- run mapmeta.py first" % meta)

    print("packing from %s" % os.path.join(a.momentum, "_cache", "images"))
    if a.fill_missing and CELL_W != 128: ap.error('fill-missing preserves the game 128px atlas contract')
    n, pages = build(a.momentum, meta, atlasdir, a.limit, a.report, a.fill_missing, a.start_page)
    with open(os.path.join(atlasdir, 'layout.json'), 'w', encoding='utf-8') as f:
        json.dump(dict(cell_width=CELL_W, cell_height=CELL_H, page=PAGE, columns=COLS,
                       per_page=PER_PAGE, pages=pages, game_compatible=(CELL_W == 128)), f, indent=2)
    print("\npacked %d thumbnails, patched %s" % (n, meta))


if __name__ == "__main__":
    main()
