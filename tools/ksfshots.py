#!/usr/bin/env python3
"""
ksfshots.py -- fetch KSF's picture of each map on its roster, for the map
browser's thumbnails.  mapthumbs.py uses them after Momentum's own pictures and
before your screenshots, so they are what a KSF-only map shows.

RUN BY HAND, NEVER FROM CRON OR A SCHEDULED TASK.  It is ~930 requests and
about 1 GB from somebody else's server (one picture measured at ~1 MB); one run
fetches the set and a re-run only asks for what is still missing.

    python tools/ksfshots.py --gamedir C:/FTESurf/ftesurf --dry-run
    python tools/ksfshots.py --gamedir C:/FTESurf/ftesurf --limit 5
    python tools/ksfshots.py --gamedir C:/FTESurf/ftesurf
    python tools/ksfshots.py --gamedir C:/FTESurf/ftesurf --only surf_whiteout

Reads <gamedir>/data/ksf_roster.csv (maproster.py fetch) and writes
<gamedir>/gfx/mapshots/ksf/<map>.jpg, skipping any already there.

Politeness, as in momfetch.py: one request at a time, at least 1.5 s apart, a
User-Agent that says who is asking, nothing retried.  A 404 means KSF has no
picture of that map -- counted, not an error.  A 403 or 429 is the host saying
no and stops the run at once; any other failure (5xx, timeout, a reply that is
not a picture) counts toward a streak, and FAIL_STREAK in a row stops it.
"""

import argparse
import csv
import hashlib
import http.client
import io
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
GAMEDIR = os.path.join(os.path.dirname(HERE), "ftesurf")

URL = "https://ksf.surf/images/%s.jpg"
UA = "FTESurf/0.1 ksfshots (+https://proto.bar/ftesurf)"
DELAY = 1.5             # the floor: --delay can raise it, never lower it
TIMEOUT = 30
FAIL_STREAK = 3
# Names become a URL and a file name, so nothing that could leave ksf/.
NAME_RE = re.compile(r"^[a-z0-9_][a-z0-9_.-]*$")


class NoPicture(Exception):
    """404: KSF has no picture of this map."""


class Refused(Exception):
    """403/429: the host said no to us.  Stops the run."""


class Failed(Exception):
    """Anything else.  Counts toward FAIL_STREAK."""


def read_roster(path):
    names = []
    with io.open(path, encoding="utf-8-sig", errors="replace") as fh:
        for row in csv.DictReader(fh):
            nm = (row.get("Map name") or "").strip().lower()
            if nm and nm not in names:
                names.append(nm)
    return names


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            body = r.read()
            ctype = r.headers.get("Content-Type", "")
    except urllib.error.HTTPError as e:
        if e.code == 404:
            raise NoPicture()
        if e.code in (403, 429):
            raise Refused("HTTP %d" % e.code)
        raise Failed("HTTP %d" % e.code)
    except (urllib.error.URLError, http.client.HTTPException, OSError) as e:
        raise Failed(str(getattr(e, "reason", e)) or e.__class__.__name__)
    # An error page saved as .jpg would only fail later, in mapthumbs.
    if not body.startswith((b"\xff\xd8\xff", b"\x89PNG")):
        raise Failed("not a picture (%s, %d bytes)" % (ctype or "no type", len(body)))
    return body


def save(path, body):
    tmp = path + ".tmp"
    try:
        with open(tmp, "wb") as fh:
            fh.write(body)
        os.replace(tmp, path)
    except OSError:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise


def same_bytes(d):
    """[[name, ...]] of pictures with identical bytes -- a placeholder served
    with a 200 for maps KSF has no picture of would show up here."""
    by_size = {}
    for f in os.listdir(d):
        if f.endswith(".jpg"):
            by_size.setdefault(os.path.getsize(os.path.join(d, f)), []).append(f)
    groups = {}
    for fs in by_size.values():
        if len(fs) < 2:
            continue
        for f in fs:
            with open(os.path.join(d, f), "rb") as fh:
                groups.setdefault(hashlib.sha1(fh.read()).hexdigest(), []).append(f[:-4])
    return [g for g in groups.values() if len(g) > 1]


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--gamedir", default=GAMEDIR,
                    help="the ftesurf/ dir: reads data/ksf_roster.csv, "
                         "writes gfx/mapshots/ksf/")
    ap.add_argument("--only", action="append", default=[], metavar="MAP",
                    help="just this map (repeatable)")
    ap.add_argument("--limit", type=int, default=0, help="fetch at most N")
    ap.add_argument("--delay", type=float, default=DELAY,
                    help="seconds between requests (at least %.1f)" % DELAY)
    ap.add_argument("--dry-run", action="store_true",
                    help="list what would be fetched; no network")
    a = ap.parse_args()

    roster = os.path.join(a.gamedir, "data", "ksf_roster.csv")
    out = os.path.join(a.gamedir, "gfx", "mapshots", "ksf")
    delay = max(DELAY, a.delay)
    if not os.path.exists(roster):
        sys.exit("no %s -- run tools/maproster.py fetch first" % roster)

    names = read_roster(roster)
    if a.only:
        want = [n.lower() for n in a.only]
        stray = [n for n in want if n not in names]
        if stray:
            print("not on KSF's roster, skipped: %s" % " ".join(stray))
        names = [n for n in names if n in want]
    bad = [n for n in names if not NAME_RE.match(n)]
    if bad:
        print("unusable names, skipped: %s" % " ".join(bad))
    names = [n for n in names if NAME_RE.match(n)]
    have = [n for n in names if os.path.exists(os.path.join(out, n + ".jpg"))]
    todo = [n for n in names if n not in set(have)]
    if a.limit:
        todo = todo[:a.limit]
    print("roster %d maps: %d pictures already in %s, %d to ask for"
          % (len(names), len(have), out, len(todo)))

    if a.dry_run:
        for n in todo:
            print("  " + URL % urllib.parse.quote(n))
        print("dry run: nothing fetched.  %d requests at %.1f s apart is ~%.0f min."
              % (len(todo), delay, len(todo) * delay / 60.0))
        return 0

    os.makedirs(out, exist_ok=True)
    got = nopic = failed = streak = nbytes = 0
    stop = None
    t0 = time.time()
    for i, n in enumerate(todo):
        if i:
            time.sleep(delay)
        try:
            body = get(URL % urllib.parse.quote(n))
        except NoPicture:
            nopic += 1
            streak = 0
            print("  %-36s no picture" % n)
            continue
        except Refused as e:
            stop = "%s: %s -- the host said no" % (n, e)
            break
        except Failed as e:
            failed += 1
            streak += 1
            print("  %-36s FAILED: %s" % (n, e))
            if streak >= FAIL_STREAK:
                stop = "%d failures in a row" % streak
                break
            continue
        streak = 0
        save(os.path.join(out, n + ".jpg"), body)
        got += 1
        nbytes += len(body)
        print("  %-36s %5d KB" % (n, (len(body) + 1023) // 1024))

    print("\nfetched %d (%.1f MB), no picture %d, failed %d, already here %d, "
          "not asked %d, in %.0f s"
          % (got, nbytes / 1048576.0, nopic, failed, len(have),
             len(todo) - got - nopic - failed, time.time() - t0))
    dup = same_bytes(out)
    if dup:
        print("%d set(s) of maps share a byte-identical picture -- a placeholder?"
              % len(dup))
        for g in dup[:5]:
            print("  %d maps: %s" % (len(g), " ".join(sorted(g)[:6])))
    if stop:
        print("STOPPED, nothing retried: %s.  Re-running resumes; pictures on "
              "disk are skipped." % stop)
        return 1
    if got:
        print("next: tools/mapthumbs.py --gamedir %s" % a.gamedir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
