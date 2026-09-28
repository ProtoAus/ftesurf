#!/usr/bin/env python3
"""
mapgrab.py -- fetch the maps NOBODY here has from the publisher that has them,
straight onto the Pi.

  python tools/mapgrab.py             print the plan, write nothing
  python tools/mapgrab.py --go        fetch
  python tools/mapgrab.py --go --approved-only    skip unapproved submissions

WHY THIS IS NOT mapsync.py.  mapsync copies maps from the local Steam install to
the Pi; it cannot help with a map this workstation does not have either, which
on 2026-09-28 was 468 of the roster's 1748 -- and 443 of those are bhop, where
coverage was 131 of 574.  Those maps exist, they are just not here.

WHY THIS IS A FETCH AND NOT A SCRAPE, the same argument mapfetch.py makes for
thumbnails: every record in momentum/_cache/*.dat already carries the fully
qualified URL of its own BSP.

    "currentVersion": {
      "bspHash":     "293dd4223a351f6182de214764f012597b93eb79",
      "downloadURL": "https://cdn.momentum-mod.org/maps/<uuid>.bsp"
    }

So there is no API to query, no auth, and no map-name-to-URL guess to get wrong.
It is the request the game itself makes when you click a map you do not have.

THE PI FETCHES, NOT THIS BOX.  The maps have to end up on the Pi, and the Pi has
its own link to the CDN -- measured at 2.7 MB/s against bhop_landmark2, where
this workstation's uplink is 40 Mbit. Routing 7.7 GB through here to push it
back out would cost twice the traffic and be slower in both directions.

bspHash IS THE SHA1 OF THE SERVED FILE, verified before this was written rather
than assumed: bhop_landmark2's download sha1sums to exactly the bspHash above.
That is what makes this safe to automate -- every file is checked against a
digest the publisher signed it with, so a truncated or substituted body is
caught rather than installed. It also means a grabbed map arrives with a
KNOWN build: maproster.py can pin it `ok` instead of `unknown`.

DOWNLOAD TO .part, RENAME ONLY ON A HASH MATCH.  This is the same discipline
Patch 465 had to add to the engine's http client, and for the same reason: a
short .bsp under the real name reads as installed, stops the Download button
offering it, and mismatches mapcrc -- a silent TF_NOMAP on every run played on
it. An interrupted curl must leave nothing.

WHAT THIS DOES NOT FETCH.  Zone files. The record carries a `zoneHash` but no
zone URL, so there is nothing cached to fetch from and a zone would need a live
API query. A map without maps/zones/online/<map>.json loads and cannot be timed
(see mapsync.py's header) -- but that is the existing condition for most of the
library, not a regression this introduces: 531 of 1312 local maps have a zone.
"""

import argparse
import collections
import glob
import json
import os
import subprocess
import sys
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
GAME = os.path.join(ROOT, "ftesurf")
DATA = os.path.join(GAME, "data")
ROSTERFILE = os.path.join(DATA, "maproster.txt")

MOMENTUM = (r"C:\Program Files (x86)\Steam\steamapps\common"
            r"\Momentum Mod Playtest\momentum")

PI_HOST = "proto@192.168.1.102"
PI_MAPS = "/srv/nvme/ftesurf-server/game/momentum/maps"
PI_WORK = "/tmp/ftesurf-grab"

# Concurrent curls on the Pi. Four saturates the link without being rude to a
# CDN that is giving these away; the box is a NanoPi, not a fleet.
JOBS = 4


def sh(cmd, timeout=None):
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def read_roster():
    """name -> (mode, src, have).  Absent file is fatal -- without it this has
    no idea what is missing and would happily fetch the entire catalogue."""
    if not os.path.exists(ROSTERFILE):
        sys.exit("no %s -- run tools/maproster.py build first" % ROSTERFILE)
    out = {}
    with open(ROSTERFILE, "r", encoding="utf-8", errors="replace") as fh:
        for ln in fh:
            f = ln.split()
            if len(f) < 11 or f[0] != "roster":
                continue
            out[f[1]] = (f[2], f[3], f[4])
    return out


def read_cache():
    """name -> (url, bspHash, kind).  Newest cache file of each kind wins.

    The numbered suffix bumps every time Momentum's UI refreshes, so globbing
    and taking the last is what mapmeta.py does too -- hardcoding today's
    number means this silently reads a stale catalogue next month."""
    out = {}
    for pat, kind in (("approved_*.dat", "approved"),
                      ("submission_*.dat", "submission")):
        hits = sorted(glob.glob(os.path.join(MOMENTUM, "_cache", pat)))
        if not hits:
            continue
        raw = open(hits[-1], "rb").read()
        if raw[:4] != b"MSML":
            sys.exit("%s: not an MSML container" % hits[-1])
        for r in json.loads(zlib.decompress(raw[12:])):
            cv = r.get("currentVersion") or {}
            url, h = cv.get("downloadURL"), cv.get("bspHash")
            if url and h:
                out.setdefault(r["name"].lower(), (url, h, kind))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--go", action="store_true", help="actually fetch")
    ap.add_argument("--approved-only", action="store_true",
                    help="skip maps still in submission (status 3/4)")
    ap.add_argument("--host", default=PI_HOST)
    ap.add_argument("--jobs", type=int, default=JOBS)
    args = ap.parse_args()

    roster = read_roster()
    cache = read_cache()
    print("roster %d, momentum publishes a bsp for %d" % (len(roster), len(cache)))

    lack = {n: v for n, v in roster.items() if v[2] == "-"}
    want = []
    for n in sorted(lack):
        got = cache.get(n.lower())
        if not got:
            continue
        url, h, kind = got
        if args.approved_only and kind != "approved":
            continue
        # The name becomes a filename and then a URL path component on a
        # case-sensitive box; anything with whitespace would break the xargs
        # driver silently, so refuse rather than mangle.
        if any(c.isspace() for c in n):
            print("  SKIP %r -- whitespace in the name" % n)
            continue
        want.append((n, h, url, kind, lack[n][0]))

    nopub = [n for n in lack if n.lower() not in cache]
    bykind = collections.Counter(w[3] for w in want)
    bymode = collections.Counter(w[4] for w in want)
    print("we lack %d; fetchable %d %s; no publisher at all %d"
          % (len(lack), len(want), dict(bykind), len(nopub)))
    print("  by mode: %s" % dict(bymode))
    for n in sorted(nopub):
        print("    no publisher: %s" % n)

    if not want:
        print("nothing to do")
        return 0

    if not args.go:
        print("\ndry run -- nothing fetched.  --go to fetch %d maps" % len(want))
        return 0

    work = os.path.join(os.environ.get("TEMP", "."), "mapgrab")
    os.makedirs(work, exist_ok=True)
    man = os.path.join(work, "manifest.txt")
    with open(man, "w", encoding="utf-8", newline="\n") as fh:
        for n, h, url, kind, mode in want:
            fh.write("%s %s %s\n" % (n, h, url))

    one = os.path.join(work, "one.sh")
    with open(one, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(ONE_SH % {"dest": PI_MAPS})

    rc, out = sh(["ssh", "-o", "BatchMode=yes", args.host,
                  "mkdir -p %s && df -B1 --output=avail %s | tail -1"
                  % (PI_WORK, PI_MAPS)])
    if rc != 0:
        sys.exit("ssh failed:\n%s" % out[:800])
    free = int(out.strip().splitlines()[-1])
    print("pi free: %.1f GB" % (free / 1073741824.0))

    for src, dst in ((man, "manifest.txt"), (one, "one.sh")):
        rc, out = sh(["scp", "-q", src, "%s:%s/%s" % (args.host, PI_WORK, dst)])
        if rc != 0:
            sys.exit("scp %s failed:\n%s" % (dst, out[:800]))

    print("fetching %d maps with %d concurrent curls..." % (len(want), args.jobs))
    rc, out = sh(["ssh", "-o", "BatchMode=yes", args.host,
                  "chmod +x %s/one.sh && xargs -n3 -P%d %s/one.sh < %s/manifest.txt"
                  % (PI_WORK, args.jobs, PI_WORK, PI_WORK)],
                 timeout=7200)

    tally = collections.Counter()
    bad = []
    for ln in out.splitlines():
        f = ln.split()
        if not f:
            continue
        tally[f[0]] += 1
        if f[0] not in ("OK", "SKIP"):
            bad.append(ln)
    print()
    for k, v in tally.most_common():
        print("  %-10s %d" % (k, v))
    for ln in bad[:40]:
        print("    %s" % ln)
    if len(bad) > 40:
        print("    ... and %d more" % (len(bad) - 40))
    return 0 if not bad else 1


# Written to a file and scp'd rather than passed as a shell string: this is full
# of quoting the local shell would eat.
ONE_SH = r"""#!/bin/sh
# mapgrab one.sh -- fetch ONE map and install it only if it hashes right.
#   $1 name   $2 expected sha1   $3 url
DEST=%(dest)s
f="$DEST/$1.bsp"
[ -f "$f" ] && { echo "SKIP $1"; exit 0; }
t="$DEST/.grab.$1.part"
# .part + rename, never straight to the real name: an interrupted curl must
# leave nothing behind. A short .bsp reads as installed and mismatches mapcrc.
if ! curl -f -s -S --max-time 1800 --retry 2 -o "$t" "$3" 2>/dev/null; then
    rm -f "$t"; echo "CURLFAIL $1"; exit 0
fi
got=`sha1sum "$t" | cut -d' ' -f1`
if [ "$got" != "$2" ]; then
    rm -f "$t"; echo "HASHFAIL $1 want=$2 got=$got"; exit 0
fi
mv "$t" "$f" || { rm -f "$t"; echo "MVFAIL $1"; exit 0; }
echo "OK $1 `stat -c %%s "$f"`"
"""


if __name__ == "__main__":
    sys.exit(main())
