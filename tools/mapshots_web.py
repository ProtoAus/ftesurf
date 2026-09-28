"""mapshots_web.py -- one web-sized screenshot per map, for the leaderboard site.

WHY A SECOND SET AND NOT THE ONES WE HAVE.  gfx/mapshots holds Momentum's own
sizes: `medium` is 1280x720 at 124 KB and `xl` is 1920x1080 at 405 KB, and the
board page is 860 px wide.  Shipping a 124 KB image to fill 860 px is three
times the bytes for a picture nobody can see the extra detail in.  At 960 px
q72 the same shot is 49 KB -- wide enough to cover the column on a 1x display
and to stay honest on a 2x one, since this is a header illustration and not
something anybody reads pixels off.

  measured over a 23-file sample, 2026-09-28:
    640 px q72   24.4 KB      960 px q72   48.7 KB
    800 px q72   35.9 KB      960 px q80   60.3 KB
    source (1280 px)         128.9 KB

NAMED FOR THE MAP, NOT FOR THE UUID.  gfx/mapshots is keyed by Momentum's
image uuid, which means resolving one needs mapmeta.txt.  surfd would then need
a copy of mapmeta.txt on the Pi, kept in step with this tree, to answer a
request for a picture.  Doing the join HERE, once, at build time, means surfd
opens `<map>.jpg` and needs no catalogue at all -- and a map whose uuid changes
upstream just gets a new file under the same name.

The join is the same one the menu does: mapmeta.txt column 8 (`thumbuuid`,
MT_UUID in src/menu/m_main.qc), map name lowercased, which is how surfd's
clean_map stores a board key.

Idempotent: a map whose .jpg is already there is skipped unless --force, so a
re-run after adding 20 maps encodes 20 files and not 2,241.

Usage:
  python tools/mapshots_web.py --db <surfd.db>        # just the board's maps
  python tools/mapshots_web.py --all                  # every map with a shot
  python tools/mapshots_web.py --db <surfd.db> --force
  python tools/mapshots_web.py --all --width 640 --quality 72
"""
import argparse
import io
import os
import sqlite3
import sys

try:
    from PIL import Image
except ImportError:
    raise SystemExit(
        "mapshots_web.py needs Pillow for the JPEG work:  python -m pip install Pillow")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
META = os.path.join(ROOT, "ftesurf", "data", "mapmeta.txt")
SHOTS = os.path.join(ROOT, "ftesurf", "gfx", "mapshots")
OUT = os.path.join(ROOT, "dist", "webshots")

MT_NAME = 1
MT_UUID = 8          # src/menu/m_main.qc:1285

# Preference order.  `medium` first because it is the smallest source that is
# still wider than the output, so the resample is always a downscale; xl is the
# fallback for the handful of maps that have no medium, and `small` (480x270)
# would be an UPSCALE and is deliberately not in this list -- a blurry 960 px
# image is worse than the page having no picture.
SIZES = ("medium", "xl")


def read_meta(path):
    """{map name (lower): image uuid} for every row that carries one."""
    out = {}
    with io.open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            p = line.split()
            if len(p) > MT_UUID and p[0] == "meta" and p[MT_UUID] not in ("-", ""):
                out[p[MT_NAME].lower()] = p[MT_UUID]
    return out


def board_maps(db):
    con = sqlite3.connect("file:%s?mode=ro" % db.replace("?", "%3f"), uri=True)
    try:
        return sorted({r[0] for r in con.execute("SELECT DISTINCT map FROM runs")})
    finally:
        con.close()


def source_for(uuid):
    for tag in SIZES:
        p = os.path.join(SHOTS, "%s-%s.jpg" % (uuid, tag))
        if os.path.exists(p):
            return p
    return None


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--db", help="a surfd.db; build only the maps it has runs for")
    ap.add_argument("--all", action="store_true",
                    help="build every map in mapmeta.txt that has a screenshot")
    ap.add_argument("--out", default=OUT)
    ap.add_argument("--width", type=int, default=960)
    ap.add_argument("--quality", type=int, default=72)
    ap.add_argument("--force", action="store_true",
                    help="re-encode maps that already have a file")
    a = ap.parse_args()

    if not a.db and not a.all:
        ap.error("give --db <surfd.db> or --all")

    meta = read_meta(META)
    print("mapmeta.txt: %d maps carry an image uuid" % len(meta))

    if a.all:
        want = sorted(meta)
        print("building every one of them that has a source")
    else:
        want = board_maps(a.db)
        print("%s: %d distinct maps on the board" % (os.path.basename(a.db), len(want)))

    if not os.path.isdir(a.out):
        os.makedirs(a.out)

    made = skipped = nouuid = nosrc = failed = 0
    bytes_out = 0
    for name in want:
        dst = os.path.join(a.out, name + ".jpg")
        if os.path.exists(dst) and not a.force:
            skipped += 1
            bytes_out += os.path.getsize(dst)
            continue
        uuid = meta.get(name)
        if not uuid:
            nouuid += 1
            continue
        src = source_for(uuid)
        if not src:
            nosrc += 1
            continue
        try:
            im = Image.open(src)
            im.load()
            h = int(round(im.height * a.width / float(im.width)))
            im = im.convert("RGB").resize((a.width, h), Image.LANCZOS)
            # .part then rename: a half-written JPEG under the real name would
            # be served by surfd as a truncated image rather than as a miss.
            im.save(dst + ".part", "JPEG", quality=a.quality,
                    optimize=True, progressive=True)
            os.replace(dst + ".part", dst)
        except Exception as exc:              # a CDN error page saved as .jpg
            failed += 1
            print("  FAILED %-32s %s" % (name, exc))
            try:
                os.remove(dst + ".part")
            except OSError:
                pass
            continue
        made += 1
        bytes_out += os.path.getsize(dst)

    print("\nwrote   %d" % made)
    print("kept    %d  (already present; --force to redo)" % skipped)
    print("no uuid %d  (not in mapmeta.txt)" % nouuid)
    print("no shot %d  (uuid known, no medium or xl on disk)" % nosrc)
    if failed:
        print("FAILED  %d" % failed)
    n = made + skipped
    if n:
        print("\n%s: %d file(s), %.1f MB, avg %.1f KB"
              % (os.path.relpath(a.out, ROOT), n, bytes_out / 1e6,
                 bytes_out / float(n) / 1e3))
    print("\nsurfd serves these from SURFD_WEBSHOTS (default data/webshots).")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
