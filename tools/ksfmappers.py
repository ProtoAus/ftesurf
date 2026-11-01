#!/usr/bin/env python3
"""ksfmappers.py -- KSF's mapper names for mapmeta.py's author column (P1178).

Momentum's cache credits its own maps; a map only KSF lists (the CS:S builds) has
its mappers on ksf.surf.  This asks /api/maps/search/<name> once per KSF name and
caches the answer as <cache>/<name>.json ({"found", "mappers"}), so later runs and
mapmeta.py read the cache and ask nothing.  tools/zoningpage.py's cache has the
same "mappers" field and seeds this one (--seed).

    python tools/ksfmappers.py                 # fetch names not yet cached
    python tools/ksfmappers.py --max 50        # at most 50 requests this run
    python tools/ksfmappers.py --offline       # count only
"""
import argparse
import json
import os
import sys
import time
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)        # run with -I, as mapmedia_refresh.py runs its tools
import mapmeta                  # noqa: E402
SURFDIR = os.path.dirname(HERE)
KSF = "https://ksf.surf"
UA = "WorldOfSurf-mapmeta/1 (+https://proto.bar/ftesurf/)"
NAME_OK = set("abcdefghijklmnopqrstuvwxyz0123456789_-.")


def cache_dir(gamedir):
    return os.path.join(gamedir, "data", "mapmedia", "ksf")


def read_cached(cache, name):
    """The cached mapper list, [] for a cached miss, None when not cached."""
    if not os.path.exists(os.path.join(cache, name + ".json")):
        return None
    return mapmeta.ksf_mappers(cache, name)


def write_cached(cache, name, doc):
    path = os.path.join(cache, name + ".json")
    with open(path + ".tmp", "w", encoding="utf-8") as fh:
        json.dump(doc, fh, ensure_ascii=False)
    os.replace(path + ".tmp", path)


def ksf_names(gamedir):
    k = mapmeta.read_ksf(os.path.join(gamedir, "data", "ksf_roster.csv"))
    k.update(mapmeta.read_catalogue_ksf(os.path.join(gamedir, "data", "mapdl.txt"), k))
    return sorted(n for n in k if set(n) <= NAME_OK)


def fetch(name):
    req = urllib.request.Request(KSF + "/api/maps/search/" + urllib.parse.quote(name),
                                 headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=20) as r:
        rows = json.loads(r.read().decode("utf-8"))
    row = next((r for r in rows if isinstance(r, dict) and str(r.get("name", "")).lower() == name), None)
    if row is None:
        return {"found": False, "mappers": []}
    ms = [m for m in row.get("mappers") or [] if isinstance(m, dict)]
    ms.sort(key=lambda m: m.get("type") if isinstance(m.get("type"), int) else 9)  # Mapper before Co-Mapper
    return {"found": True, "mappers": [m.get("name") or m.get("mapperName") for m in ms
                                       if m.get("name") or m.get("mapperName")]}


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--gamedir", default=os.path.join(SURFDIR, "ftesurf"))
    ap.add_argument("--cache", help="default <gamedir>/data/mapmedia/ksf")
    ap.add_argument("--seed", default=os.path.join(SURFDIR, "dist", "zoning-cache"),
                    help="zoningpage.py's cache, copied in where this one has nothing")
    ap.add_argument("--max", type=int, default=400, help="requests this run")
    ap.add_argument("--offline", action="store_true")
    a = ap.parse_args()
    cache = a.cache or cache_dir(a.gamedir)
    os.makedirs(cache, exist_ok=True)
    names = ksf_names(a.gamedir)
    seeded = asked = failed = 0
    for name in names:
        if read_cached(cache, name) is not None:
            continue
        seed = read_cached(a.seed, name) if a.seed and os.path.isdir(a.seed) else None
        if seed is not None:
            write_cached(cache, name, {"found": bool(seed), "mappers": seed})
            seeded += 1
            continue
        if a.offline or asked >= a.max:
            continue
        time.sleep(0.35)
        asked += 1
        try:
            write_cached(cache, name, fetch(name))
        except (OSError, ValueError) as exc:
            failed += 1
            print("  ksf: %s: %s" % (name, exc), file=sys.stderr)
    have = sum(1 for n in names if read_cached(cache, n))
    left = sum(1 for n in names if read_cached(cache, n) is None)
    print("ksfmappers: %d KSF names, %d with mappers, %d not yet asked; this run seeded %d, asked %d, %d failed"
          % (len(names), have, left, seeded, asked, failed))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
