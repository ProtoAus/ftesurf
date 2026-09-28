"""Read Momentum's own map catalogue out of the game's `_cache/*.dat`.

  MSML | u32 decompressed size | u32 map count | zlib stream -> a JSON array

There is NO network endpoint that maps a name to an id -- the leaderboard API
takes numeric ids and nothing serves the table -- so this file is the only way
to ask for a board by name.  The game writes these, so a headless box needs a
copy; they are the one Momentum input that cannot be fetched.

DUPLICATES ARE REAL AND THE ORDER MATTERS.  `approved_*.dat` and
`submission_*.dat` overlap by about eighty maps, so files are read in sorted
filename order and a later file wins on map NAME.  That is wrlines' rule, kept
because the alternative is two ids for one name and a silent coin flip.

`"id": 265.0` IS SKIPPED, NOT ROUNDED.  A JSON number is a double; an id that
arrived as a real has already been through something that could have lost its
low digits, and guessing which is worse than not having it.
"""
import glob
import io
import json
import os
import struct
import zlib

MSML_MAGIC = b"MSML"

# Momentum's Gamemode enum, 1-based (wr_board.cpp:10-13).  Only the two this
# project has maps and players for are named; the rest are numbers on purpose.
GM_SURF = 1
GM_BHOP = 2
GAMEMODES = {1: "surf", 2: "bhop", 3: "bhop_hl1", 4: "climb_mom", 5: "climb_kzt",
             6: "climb_16", 7: "rj", 8: "sj", 9: "ahop", 10: "conc",
             11: "defrag_cpm", 12: "defrag_vq3", 13: "defrag_vtg"}

TRACK_MAIN, TRACK_STAGE, TRACK_BONUS = 0, 1, 2


def read_cache(path):
    """[map dict] from one .dat, or [] if it is not one."""
    with open(path, "rb") as fh:
        head = fh.read(12)
        if len(head) < 12 or head[:4] != MSML_MAGIC:
            return []
        raw = fh.read()
    try:
        blob = zlib.decompress(raw)
    except zlib.error:
        return []
    try:
        doc = json.loads(blob.decode("utf-8", "replace"))
    except ValueError:
        return []
    return doc if isinstance(doc, list) else []


def catalogue(cache_dir):
    """name -> {id, name, tier, boards:[(gamemode, trackType, trackNum)]}.

    Later files win on name; see the header.
    """
    out = {}
    for p in sorted(glob.glob(os.path.join(cache_dir, "*.dat"))):
        for m in read_cache(p):
            if not isinstance(m, dict):
                continue
            mid, name = m.get("id"), m.get("name")
            if not isinstance(mid, int) or not isinstance(name, str) or not name:
                continue                      # a real id is skipped, see header
            boards, tier = [], 0
            for lb in (m.get("leaderboards") or []):
                if not isinstance(lb, dict):
                    continue
                gm, tt = lb.get("gamemode"), lb.get("trackType")
                tn = lb.get("trackNum")
                if not all(isinstance(v, int) for v in (gm, tt, tn)):
                    continue
                boards.append((gm, tt, tn))
                if tt == TRACK_MAIN and isinstance(lb.get("tier"), int):
                    tier = lb["tier"]
            out[name] = {"id": mid, "name": name, "tier": tier,
                         "boards": sorted(set(boards))}
    return out


def _main():
    import argparse
    import collections
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cache", required=True, help="the game's momentum/_cache dir")
    ap.add_argument("--gamemode", type=int, action="append", default=[],
                    help="limit to these gamemodes (1 surf, 2 bhop)")
    ap.add_argument("--have", default=None,
                    help="a maps dir; count only maps whose .bsp is there")
    ap.add_argument("--out", default=None, help="write a TSV of the boards")
    a = ap.parse_args()

    cat = catalogue(a.cache)
    have = None
    if a.have:
        have = {os.path.splitext(f)[0].lower()
                for f in os.listdir(a.have) if f.lower().endswith(".bsp")}
    want = set(a.gamemode) or None

    rows, maps = [], set()
    per_gm = collections.Counter()
    for name, m in sorted(cat.items()):
        if have is not None and name.lower() not in have:
            continue
        for gm, tt, tn in m["boards"]:
            if want and gm not in want:
                continue
            rows.append((name, m["id"], m["tier"], gm, tt, tn))
            maps.add(name)
            per_gm[gm] += 1

    print("catalogue          %d map(s)" % len(cat))
    if have is not None:
        print("  with a .bsp here %d" % sum(1 for n in cat if n.lower() in have))
    print("boards selected    %d across %d map(s)" % (len(rows), len(maps)))
    for gm, n in sorted(per_gm.items()):
        print("   gamemode %-2d %-12s %d board(s)" % (gm, GAMEMODES.get(gm, "?"), n))
    kinds = collections.Counter(r[4] for r in rows)
    print("   main %d   stage %d   bonus %d"
          % (kinds.get(0, 0), kinds.get(1, 0), kinds.get(2, 0)))

    if a.out:
        with io.open(a.out, "w", encoding="utf-8", newline="\n") as fh:
            fh.write("# map\tmapid\ttier\tgamemode\ttrackType\ttrackNum\n")
            for r in rows:
                fh.write("%s\t%d\t%d\t%d\t%d\t%d\n" % r)
        print("wrote %s" % a.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
