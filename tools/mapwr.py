#!/usr/bin/env python3
"""
mapwr.py -- the best known MAIN-track time per map, projected to a flat table
the map browser can read without a network.

WHY A TABLE AND NOT A FETCH.  The browser draws ~2270 rows and the record for
each is one row of surfd's `runs`.  Asking per map is 2270 requests behind a
rate limiter; asking for all of them at once needs a bulk route on the public
vhost that nothing else wants.  Every other column in that browser is already a
generated table (mapmeta.txt, mapdl.txt, mapdeps.txt) built on this box and
shipped in the archive, so this is the shape that is already paid for -- and it
means the column still draws with the Pi switched off.

THE COST is that it is a SNAPSHOT.  Regenerate at release time.  That is
honest for what it holds: 608 of the 736 maps with a time have Momentum's
imported archive as their source, and an import does not move.

WHICH ROW IS "THE BEST".  surfd ranks a board by

    BOARD_ORDER = "millis ASC, submitted ASC, player ASC"      surfd.py:2056

so the winning TIME is MIN(millis) and the tiebreaks only decide whose name is
against it.  This reads millis for exactly that reason -- `ticks` is not
comparable across rows, because tickrate is per-run (66.6667, 100 and 125 all
appear in this table) and 3532 ticks is a different time at each of them.

ACROSS EVERY TIER, and the tier is recorded.  A map's record is whoever holds
it: `momentum` and `ksf` are imported archives, `ranked` is our own fleet.
Taking the minimum over all of them is what makes the column mean "the best
time anyone is known to have set" rather than "the best time on an empty board"
-- with 36 ranked maps against 608 imported ones, a ranked-only reading would
be blank almost everywhere.  The source travels with the number so the row can
say where it came from instead of implying we watched it happen.

  track=0, leg=0 is the MAIN track.  Stage and bonus boards live at other
  (track, leg) pairs and are deliberately not in here: the browser's row is
  about the map, and a stage record shown next to a main-track PB would be two
  different runs under one heading.
"""

import argparse
import os
import subprocess
import sys

PI_HOST = "proto@192.168.1.102"
PI_DB = "/srv/nvme/surfd/data/surfd.db"
OUT = os.path.join("ftesurf", "data", "mapwr.txt")

# Run on the Pi.  Passed on stdin rather than as an argv string: it carries
# quotes and a here-doc would be a second layer of escaping to get wrong.
REMOTE = r'''
import sqlite3, sys

db = sqlite3.connect("file:%(db)s?mode=ro", uri=True)
db.row_factory = sqlite3.Row

# GROUP BY with a bare column alongside MIN() is a SQLite extension that picks
# the row the MIN came from -- documented, and the whole reason this is one
# query rather than a window function plus a join.  The tier printed is
# therefore the tier OF the fastest run, not some arbitrary row's.
rows = db.execute(
    "SELECT map, MIN(millis) AS ms, tier, name"
    "  FROM runs"
    " WHERE track=0 AND leg=0 AND style='clean' AND millis > 0"
    " GROUP BY map"
    " ORDER BY map").fetchall()

for r in rows:
    # The name can hold spaces and colour codes; it is LAST on the line so the
    # reader can take it whole, and every field before it is one token.
    print("wr %%s %%d %%s %%s" %% (r["map"], r["ms"], r["tier"],
                                (r["name"] or "-").replace("\n", " ")))
'''


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--host", default=PI_HOST)
    ap.add_argument("--db", default=PI_DB)
    ap.add_argument("--out", default=OUT)
    args = ap.parse_args()

    # encoding NAMED, not left to the platform.  Player names are free text and
    # this table holds bytes no cp1252 codepage can decode; on Windows the
    # default codec raises inside subprocess' reader THREAD, which surfaces as
    # p.stdout being None rather than as the decode error it is.
    p = subprocess.run(["ssh", "-o", "BatchMode=yes", args.host, "python3", "-"],
                       input=REMOTE % {"db": args.db},
                       capture_output=True, text=True, timeout=180,
                       encoding="utf-8", errors="replace")
    if p.returncode != 0:
        sys.exit("ssh failed (%d):\n%s" % (p.returncode, (p.stderr or "")[:2000]))

    lines = [ln for ln in p.stdout.splitlines() if ln.startswith("wr ")]
    if not lines:
        sys.exit("no rows came back -- refusing to write an empty table over a "
                 "good one:\n%s" % (p.stdout or p.stderr)[:800])

    tiers = {}
    for ln in lines:
        tiers[ln.split()[3]] = tiers.get(ln.split()[3], 0) + 1

    tmp = args.out + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("FTESURF-MAPWR 1\n")
        fh.write("# written by tools/mapwr.py -- do not edit\n")
        fh.write("# wr <name> <millis> <tier> <holder>\n")
        fh.write("# tier: momentum / ksf = an imported archive, "
                 "ranked / community = set on this fleet\n")
        for ln in lines:
            fh.write(ln + "\n")
    os.replace(tmp, args.out)

    print("%s: %d maps" % (args.out, len(lines)))
    for t in sorted(tiers, key=lambda k: -tiers[k]):
        print("  %-10s %d" % (t, tiers[t]))


if __name__ == "__main__":
    main()
