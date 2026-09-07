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
    ftesurf/screenshots/<map>.<ext>     your own F5 grabs

The third exists because Momentum only caches an image once its own UI has shown you
that map, which left 751 of 2172 maps with a thumbnail id but no file.  mapfetch.py
GETs those from the URL the cache record already carries; see its docstring.

The fourth exists because CS:S-only maps are in neither of Momentum's caches -- the
library has 1084 loose BSPs in cstrike/maps that Momentum has never indexed.  Take a
screenshot in-game, name it after the map, re-run this, and it gets a thumbnail like
everything else.

Anything with no source at all keeps `-` for page/cell and the menu draws its
placeholder.  That is deliberate: a wrong picture is worse than an obvious absence.

Usage:
    python mapthumbs.py                 # rebuild the atlases and patch mapmeta.txt
    python mapthumbs.py --report        # also say what resolved and what did not
    python mapthumbs.py --limit 50      # small run, for checking the packing
"""

import argparse
import os
import sys

try:
    from PIL import Image
except ImportError:
    raise SystemExit(
        "mapthumbs.py needs Pillow for the JPEG decode:  python -m pip install Pillow")

MOMENTUM = r"C:\Program Files (x86)\Steam\steamapps\common\Momentum Mod Playtest\momentum"
SURFDIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # C:\FTESurf
META = os.path.join(SURFDIR, "ftesurf", "data", "mapmeta.txt")
ATLASDIR = os.path.join(SURFDIR, "ftesurf", "gfx", "mapthumbs")
SHOTS = os.path.join(SURFDIR, "ftesurf", "screenshots")
FETCHED = os.path.join(SURFDIR, "ftesurf", "gfx", "mapshots")   # tools/mapfetch.py

# 16:9, and an exact divisor of PAGE on the x axis so a cell never straddles a
# texel boundary the sampler would then have to guess at.
CELL_W, CELL_H = 128, 72
PAGE = 2048
COLS = PAGE // CELL_W                 # 16
ROWS = PAGE // CELL_H                 # 28
PER_PAGE = COLS * ROWS                # 448

SHOT_EXTS = (".png", ".jpg", ".jpeg", ".tga", ".bmp")

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
        for suffix in ("-small.jpg", "-large.jpg"):
            p = os.path.join(momentum, "_cache", "images", uuid + suffix)
            if os.path.exists(p):
                return p
        # What mapfetch.py pulled down for the maps Momentum never cached.
        # Smallest first: this is a 128x72 cell either way, and decoding a
        # 2560x1440 to get there is twenty times the work for the same pixels.
        for suffix in ("-small.jpg", "-medium.jpg", "-large.jpg", "-xl.jpg"):
            p = os.path.join(FETCHED, uuid + suffix)
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


def build(momentum, meta_path, atlasdir, limit=0, report=False):
    head, rows = read_meta(meta_path)
    os.makedirs(atlasdir, exist_ok=True)

    resolved = []          # (row, source path)
    missing_uuid = 0
    missing_file = 0
    for r in rows:
        name = r[C_NAME]
        uuid = r[C_THUMB] if len(r) > C_THUMB else "-"
        src = source_for(name, uuid, momentum)
        if src is None:
            if uuid == "-":
                missing_uuid += 1
            else:
                missing_file += 1
            r[C_PAGE] = r[C_CELL] = "-"
            continue
        resolved.append((r, src))
        if limit and len(resolved) >= limit:
            break

    print("  %d maps with an image, %d have no thumbnail id, %d id but no cached file"
          % (len(resolved), missing_uuid, missing_file))

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

        p, c = slot // PER_PAGE, slot % PER_PAGE
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
    for extra in range(page_no + 1, page_no + 16):
        stale = os.path.join(atlasdir, "atlas%d.png" % extra)
        if os.path.exists(stale):
            os.remove(stale)
            print("  removed stale %s" % stale)

    with open(meta_path, "w", encoding="utf-8", newline="\n") as f:
        for h in head:
            f.write(h + "\n")
        for r in rows:
            f.write(" ".join(r) + "\n")

    if report:
        print("\n  %d cells over %d page(s), %d decode failures"
              % (written, page_no + 1, failed))
        print("  cell %dx%d, page %d, %d per page" % (CELL_W, CELL_H, PAGE, PER_PAGE))
        print("  menu draws these as gfx/mapthumbs/atlas<N>")
    return written, npages


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--momentum", default=MOMENTUM)
    ap.add_argument("--meta", default=META)
    ap.add_argument("--atlasdir", default=ATLASDIR)
    ap.add_argument("--limit", type=int, default=0, help="only pack the first N maps")
    ap.add_argument("--report", action="store_true")
    a = ap.parse_args()

    if not os.path.exists(a.meta):
        raise SystemExit("%s not found -- run mapmeta.py first" % a.meta)

    print("packing from %s" % os.path.join(a.momentum, "_cache", "images"))
    n, pages = build(a.momentum, a.meta, a.atlasdir, a.limit, a.report)
    print("\npacked %d thumbnails, patched %s" % (n, a.meta))


if __name__ == "__main__":
    main()
