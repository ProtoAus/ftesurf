#!/usr/bin/env python3
"""
mapfetch.py -- fill in the map screenshots Momentum has an id for but has not
cached locally, by fetching them from Momentum's own CDN.

WHY THIS EXISTS.  mapthumbs.py can only pack what is on disk, and Momentum only
caches an image once its UI has actually shown you that map.  On this install that
left 1421 of 2172 maps with a picture and 751 with nothing but a placeholder -- not
because the picture does not exist, but because nobody had scrolled past it.

WHAT MAKES THIS A FETCH AND NOT A SCRAPE.  Every record in _cache/*.dat already
carries the fully-qualified URL of each of its own images:

    "thumbnail": {
      "id":     "a078c8a5-9847-43e6-9846-d581ae392225",
      "small":  "https://cdn.momentum-mod.org/img/<id>-small.jpg",    480x270
      "medium": "https://cdn.momentum-mod.org/img/<id>-medium.jpg",  1280x720
      "large":  "https://cdn.momentum-mod.org/img/<id>-large.jpg",   1920x1080
      "xl":     "https://cdn.momentum-mod.org/img/<id>-xl.jpg"       2560x1440
    }

So there is no API to query, no auth, no HTML to parse and no map-name-to-URL guess
to get wrong: the exact URL for the exact image is already sitting in the local
cache.  This tool reads those URLs and GETs the ones whose file is missing.  It is
the same request the game itself would make, just made ahead of time for maps you
have not browsed to yet.  Sizes above are measured, not assumed.

WHERE THEY GO, and why not into Momentum's cache.  `ftesurf/gfx/mapshots/`, ours.
Writing into another program's cache directory means the next thing that prunes it
silently undoes this, and it is not our directory to grow.  Ours is inside the game
path, so the engine can read it directly for the menu backdrop, and mapthumbs.py
picks it up as a thumbnail source.

WHAT IT COSTS, measured against the CDN for the 2172 distinct thumbnail ids in
this library rather than guessed:

    small    480x270    ~20 KB      ~43 MB for the whole set
    medium  1280x720    ~93 KB     ~196 MB
    large   1920x1080  ~171 KB     ~362 MB
    xl      2560x1440  ~261 KB     ~554 MB

Smalls are the default because they alone complete the *thumbnails*, which is the
point, and cost ~16 MB for the maps Momentum had not cached.  The larger sizes only
buy a sharper menu *backdrop*, so they are opt-in.  Pick the one that matches the
screen: `large` is exactly 1080p, `xl` is 1440p, and asking for more than the
display can show is bytes and VRAM spent on pixels nobody sees.  Momentum's own
cache holds 1503 smalls and 817 larges and no medium or xl at all, so those two
sizes always fetch the full set.

WHERE THEY GO can be redirected with --into-momentum, which writes into Momentum's
own _cache/images instead.  Off by default for the reason above -- it is not our
directory to grow, and the next thing that prunes it undoes the work -- but it is
there because both this menu and Momentum's read that path.

BEING A GOOD CITIZEN.  Four workers, a delay per request, a real User-Agent, one
retry, and a permanent record of 404s in mapshots/.missing so a second run does not
ask again for something that is genuinely not there.  Already-present files are
never re-fetched, so re-running this is cheap and safe.

Usage:
    python mapfetch.py                  # smalls for every map that has none
    python mapfetch.py --dry-run        # say what it would fetch, fetch nothing
    python mapfetch.py --medium         # + 1280x720 backdrops
    python mapfetch.py --large          # + 1920x1080 backdrops
    python mapfetch.py --xl             # + 2560x1440 backdrops
    python mapfetch.py --all            # every size the CDN offers (~1.1 GB)
    python mapfetch.py --limit 20       # a small run, to check it works
"""

import argparse
import glob
import os
import sys
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mapmeta import MOMENTUM, SURFDIR, read_msml          # noqa: E402

OUTDIR = os.path.join(SURFDIR, "ftesurf", "gfx", "mapshots")

# Every size the CDN offers, smallest first.  Order matters: a run that asks for
# several fetches the cheap ones first, so an interrupted run still leaves the
# thumbnails complete.
SIZES = ("small", "medium", "large", "xl")

UA = "FTESurf-mapfetch/1.0 (+local map browser thumbnails)"
WORKERS = 4
DELAY = 0.25            # seconds per request per worker -> ~16 req/s overall
TIMEOUT = 30


def missing_path(outdir):
    return os.path.join(outdir, ".missing")


def load_missing(outdir):
    """URLs the CDN has already told us do not exist.  Never asked for twice."""
    p = missing_path(outdir)
    if not os.path.exists(p):
        return set()
    with open(p, "r", encoding="utf-8") as f:
        return set(l.strip() for l in f if l.strip() and not l.startswith("#"))


def wanted(momentum, sizes, outdir):
    """[(uuid, size, url)] for every image we want and do not have.

    Deduplicated by uuid+size: a map that appears in both the approved and the
    submission cache is one image, and several maps can share a thumbnail id.
    """
    local = set(os.listdir(os.path.join(momentum, "_cache", "images"))) \
        if os.path.isdir(os.path.join(momentum, "_cache", "images")) else set()
    ours = set(os.listdir(outdir)) if os.path.isdir(outdir) else set()
    dead = load_missing(outdir)

    out, seen, held = [], set(), 0
    for p in sorted(glob.glob(os.path.join(momentum, "_cache", "*.dat"))):
        try:
            records = read_msml(p)
        except Exception as e:                                  # noqa: BLE001
            print("  ! %s: %s" % (os.path.basename(p), e), file=sys.stderr)
            continue
        for m in records:
            thumb = m.get("thumbnail") or {}
            uuid = thumb.get("id")
            if not uuid:
                continue
            for size in sizes:
                url = thumb.get(size)
                if not url:
                    continue
                key = (uuid, size)
                if key in seen:
                    continue
                seen.add(key)
                fn = "%s-%s.jpg" % (uuid, size)
                # Momentum's own copy counts as having it -- both the menu and
                # mapthumbs.py read that directory too.
                if fn in local or fn in ours:
                    held += 1
                    continue
                if url in dead:
                    continue
                out.append((uuid, size, url))
    return out, held


def fetch_one(url, dest, lock, counters, dry):
    if dry:
        return "dry"
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    for attempt in (1, 2):
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
                body = r.read()
            break
        except urllib.error.HTTPError as e:
            if e.code == 404:
                with lock:
                    counters["gone"].append(url)
                return "404"
            if attempt == 2:
                with lock:
                    counters["fail"] += 1
                return "http %d" % e.code
            time.sleep(1.0)
        except Exception:                                       # noqa: BLE001
            if attempt == 2:
                with lock:
                    counters["fail"] += 1
                return "error"
            time.sleep(1.0)

    if not body.startswith(b"\xff\xd8"):
        # A CDN error page saved as .jpg would decode-fail later, in mapthumbs,
        # a long way from the cause.  Reject it here where the URL is in hand.
        with lock:
            counters["fail"] += 1
        return "not a jpeg"

    tmp = dest + ".part"
    with open(tmp, "wb") as f:
        f.write(body)
    os.replace(tmp, dest)
    with lock:
        counters["ok"] += 1
        counters["bytes"] += len(body)
    time.sleep(DELAY)
    return "ok"


def run(momentum, sizes, limit, dry, outdir):
    os.makedirs(outdir, exist_ok=True)
    todo, held = wanted(momentum, sizes, outdir)
    print("  %d images already on disk, %d to fetch (%s)"
          % (held, len(todo), ", ".join(sizes)))
    if limit:
        todo = todo[:limit]
        print("  --limit %d: fetching only the first %d" % (limit, len(todo)))
    if not todo:
        print("\nnothing to do -- every image with an id is already local.")
        return

    lock = threading.Lock()
    counters = {"ok": 0, "fail": 0, "bytes": 0, "gone": []}
    done = [0]
    total = len(todo)

    def work(item):
        uuid, size, url = item
        dest = os.path.join(outdir, "%s-%s.jpg" % (uuid, size))
        fetch_one(url, dest, lock, counters, dry)
        with lock:
            done[0] += 1
            if done[0] % 50 == 0 or done[0] == total:
                print("    %d/%d  ok %d  failed %d  gone %d  %.1f MB"
                      % (done[0], total, counters["ok"], counters["fail"],
                         len(counters["gone"]), counters["bytes"] / 1048576),
                      flush=True)

    t0 = time.time()
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        list(ex.map(work, todo))

    if counters["gone"]:
        # Record 404s so the next run does not ask again.  These are real: a map
        # record can outlive the image it points at.
        fresh = not os.path.exists(missing_path(outdir))
        with open(missing_path(outdir), "a", encoding="utf-8") as f:
            if fresh:
                f.write("# URLs the CDN returned 404 for.  Delete a line to retry it.\n")
            for u in counters["gone"]:
                f.write(u + "\n")

    print("\nfetched %d images, %.1f MB, in %.0fs  (%d failed, %d gone)"
          % (counters["ok"], counters["bytes"] / 1048576, time.time() - t0,
             counters["fail"], len(counters["gone"])))
    print("into %s" % outdir)
    if counters["ok"]:
        print("now re-run:  python tools\\mapthumbs.py --report")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--momentum", default=MOMENTUM)
    ap.add_argument("--medium", action="store_true",
                    help="also fetch 1280x720 backdrops (~196 MB for the set)")
    ap.add_argument("--large", action="store_true",
                    help="also fetch 1920x1080 backdrops (~362 MB for the set)")
    ap.add_argument("--xl", action="store_true",
                    help="also fetch 2560x1440 backdrops (~554 MB for the set)")
    ap.add_argument("--all", action="store_true",
                    help="every size the CDN offers (~1.1 GB for the set)")
    ap.add_argument("--into-momentum", action="store_true",
                    help="write into Momentum's _cache/images instead of ours")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    if not os.path.isdir(a.momentum):
        raise SystemExit("Momentum dir not found: %s" % a.momentum)

    if a.all:
        sizes = list(SIZES)
    else:
        want = {"small", "medium" if a.medium else "",
                "large" if a.large else "", "xl" if a.xl else ""}
        sizes = [s for s in SIZES if s in want]

    outdir = os.path.join(a.momentum, "_cache", "images") if a.into_momentum \
        else OUTDIR

    print("cdn.momentum-mod.org, urls taken from %s"
          % os.path.join(a.momentum, "_cache", "*.dat"))
    run(a.momentum, sizes, a.limit, a.dry_run, outdir)


if __name__ == "__main__":
    main()
