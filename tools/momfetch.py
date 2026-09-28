"""Fetch Momentum Mod leaderboards for every surf and bhop board we can host.

  python tools/momfetch.py --cache <momentum/_cache> --maps <momentum/maps> \
                           --out dist/momboards [--go] [--delay 1.0]

TIMES FIRST, DEMOS SEPARATELY, and the split is a size argument rather than a
preference.  3,678 boards is one request each -- about an hour at a second
apiece.  The top 25 of every one of those is ~92,000 demos, ~35 GB and a day of
sustained requests against somebody else's infrastructure.  So this fetches
TIMES for everything and leaves demos to `--demos`, which is bounded by
`--demo-boards` and defaults to main tracks only.

POLITENESS, and none of it is negotiable in the code:
  * one request at a time, never concurrent
  * --delay between every request, default 1.0s -- 2.5x the 400ms the wrlines
    reference settled on against this same API, because that figure was for a
    person pressing a button and this is a sweep
  * a cap per invocation (--max), so one command cannot become a runaway
  * a User-Agent that says what this is and where to complain
  * a non-2xx is a REFUSAL: it stops, it is reported, and nothing is retried.
    If the host does not want this, the answer is to stop asking, not to look
    more like a browser.
  * EVERY answer is cached to disk, so a re-run costs nothing and an interrupted
    sweep resumes exactly where it stopped.  This is the property that makes
    running it again cheap rather than rude.

WHY A SWEEP IS DEFENSIBLE HERE AT ALL.  The wrlines reference's rule is "never
automatic, every request is downstream of a button", and a sweep plainly is not
that.  Two things make this different rather than an exception: the data is
public and unauthenticated by Momentum's own choice (@BypassJwtAuth on this
endpoint), and the result is cached forever and shared by every player of this
server -- so the total traffic is ONE sweep instead of one request per player
per map per visit, which is the outcome the button rule exists to avoid.  It is
still somebody else's bandwidth; hence the delay.

TRACK NUMBERS COME FROM THE GAME'S OWN CATALOGUE, not from guessing.  There is
no endpoint that maps a name to an id or lists a map's tracks; `_cache/*.dat`
is the only source, which tools/msml.py reads.  A board that the catalogue does
not claim is never asked for.
"""
import argparse
import collections
import io
import json
import os
import sys
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import msml  # noqa: E402

# Player aliases are free Unicode from another game's API, and Windows'
# default stdout is cp1252 -- so merely PRINTING a name can kill the tool
# after the work is done.  This has now bitten once on a file write and once
# on a progress line; "replace" rather than "strict" because a mangled glyph
# in a console line is not worth losing a sweep over.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

API = "https://api.momentum-mod.org/v1"
UA = "FTESurf/0.1 momfetch (+https://proto.bar/ftesurf)"
TIMEOUT = 30
TAKE_MAX = 100        # the API's own cap: take=101 is a 400

# Consecutive 404s before the sweep stops.  See NoSuchBoard: a 404 is about
# one board, but a host that began refusing everything would answer 404 to
# everything too, and only the count tells them apart.
SKIP_STREAK = 40


class Refused(Exception):
    """The host said no TO US.  Reported, never retried, stops the sweep."""


class NoSuchBoard(Exception):
    """404: that board does not exist.  An ANSWER about one map, not a refusal.

    THIS COST A SWEEP.  The catalogue comes from the game's own `_cache`, which
    carries submission maps alongside approved ones; the public API does not
    publish every one of them, and says so with a 404.  The first run of this
    tool treated that as Refused and stopped at 547 of 3,692 on surf_binx
    (mapid 2365), having already cached 12,025 perfectly good rows.

    The same fix had been made in surfd/ksfimport.py an hour earlier, for the
    same shape -- a per-item "no such thing" wearing a status code -- and was
    not carried across.  Two tools, one author, one afternoon.

    BOUNDED, because the reading is inferred: SKIP_STREAK consecutive 404s
    stops the sweep, since a host that has started refusing everything looks
    exactly like a long run of unpublished maps for as long as you do not
    count.
    """


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA,
                                               "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            if r.status < 200 or r.status >= 300:
                raise Refused("HTTP %d" % r.status)
            return r.read()
    except urllib.error.HTTPError as e:
        if e.code == 404:
            raise NoSuchBoard("HTTP 404")
        raise Refused("HTTP %d" % e.code)
    except urllib.error.URLError as e:
        raise Refused(str(e.reason))


def read_tracks(path):
    """The catalogue shape, from tools/msml.py --out's TSV."""
    cat = {}
    with io.open(path, encoding="utf-8") as fh:
        for ln in fh:
            if ln.startswith("#") or not ln.strip():
                continue
            f = ln.rstrip("\n").split("\t")
            if len(f) < 6:
                continue
            try:
                name, mid, tier = f[0], int(f[1]), int(f[2])
                gm, tt, tn = int(f[3]), int(f[4]), int(f[5])
            except ValueError:
                continue
            m = cat.setdefault(name, {"id": mid, "name": name, "tier": tier,
                                      "boards": []})
            m["boards"].append((gm, tt, tn))
    for m in cat.values():
        m["boards"] = sorted(set(m["boards"]))
    return cat


def board_key(mapid, gm, tt, tn):
    return "%d_g%d_t%d%d" % (mapid, gm, tt, tn)


def gm_of(name):
    """A map's own gamemode by the community naming, or None.

    Every map in the catalogue claims a board in nearly every gamemode and
    almost all of them are empty -- wrlines: "all 546 surf maps here claim
    twelve".  Asking for all of them would be 44,676 requests for 3,678
    boards' worth of data.
    """
    n = name.lower()
    if n.startswith("surf_"):
        return msml.GM_SURF
    if n.startswith("bhop_"):
        return msml.GM_BHOP
    return None


def parse_board(doc):
    """(totalCount, [row]) from one leaderboard reply; unusable rows dropped."""
    if not isinstance(doc, dict):
        return 0, []
    total = doc.get("totalCount")
    total = total if isinstance(total, int) else 0
    out = []
    for e in (doc.get("data") or []):
        if not isinstance(e, dict):
            continue
        h = e.get("replayHash")
        t = e.get("time")
        if not isinstance(h, str) or not h or not isinstance(t, (int, float)):
            continue
        u = e.get("user") or {}
        # steamID is a STRING on purpose: a SteamID64 does not survive a JSON
        # number, which is a double and loses the low digits above 2^53.
        sid = u.get("steamID")
        out.append({
            "rank": e.get("rank") if isinstance(e.get("rank"), int) else 0,
            "time": float(t),
            "hash": h,
            "steamid": sid if isinstance(sid, str) else "",
            "alias": (u.get("alias") or "?").replace("\t", " ").strip() or "?",
            "created": e.get("createdAt") or "",
            "url": e.get("downloadURL") or "",
        })
    return total, out


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cache", help="the game's momentum/_cache")
    ap.add_argument("--tracks",
                    help="a TSV from tools/msml.py --out, for a box with no\ngame install: map, mapid, tier, gamemode, trackType, trackNum")
    ap.add_argument("--maps", help="momentum/maps, to skip maps we cannot host")
    ap.add_argument("--out", required=True, help="where board JSON is cached")
    ap.add_argument("--take", type=int, default=25, help="places per board (max 100)")
    ap.add_argument("--delay", type=float, default=1.0, help="seconds between requests")
    ap.add_argument("--max", type=int, default=100000, help="requests this invocation")
    ap.add_argument("--gamemode", type=int, action="append", default=[],
                    help="limit to these (1 surf, 2 bhop); default both")
    ap.add_argument("--main-only", action="store_true", help="skip stages and bonuses")
    ap.add_argument("--refresh", action="store_true", help="re-ask for cached boards")
    ap.add_argument("--map", action="append", default=[], help="only these map names")
    ap.add_argument("--go", action="store_true", help="actually make requests")
    a = ap.parse_args()

    take = max(1, min(a.take, TAKE_MAX))
    want_gm = set(a.gamemode) or {msml.GM_SURF, msml.GM_BHOP}
    only = {m.lower() for m in a.map}

    if a.tracks:
        cat = read_tracks(a.tracks)
    elif a.cache:
        cat = msml.catalogue(a.cache)
    else:
        print("give --cache (the game's _cache) or --tracks (its export)")
        return 2
    # No --maps is not "every map": it means this box cannot tell which maps it
    # can host, so the caller has already decided that (the track export is
    # written with --have, so it carries the answer).
    have = None
    if a.maps:
        have = {os.path.splitext(f)[0].lower()
                for f in os.listdir(a.maps) if f.lower().endswith(".bsp")}

    jobs = []
    for name, m in sorted(cat.items()):
        gm = gm_of(name)
        if gm is None or gm not in want_gm:
            continue
        if have is not None and name.lower() not in have:
            continue                      # a board for a map nobody here can load
        if only and name.lower() not in only:
            continue
        for bgm, tt, tn in m["boards"]:
            if bgm != gm:
                continue
            if a.main_only and tt != msml.TRACK_MAIN:
                continue
            jobs.append((name, m["id"], gm, tt, tn))

    os.makedirs(a.out, exist_ok=True)
    todo = [j for j in jobs
            if a.refresh or not os.path.exists(
                os.path.join(a.out, board_key(j[1], j[2], j[3], j[4]) + ".json"))]

    print("boards in scope   %d" % len(jobs))
    print("already cached    %d" % (len(jobs) - len(todo)))
    print("to ask for        %d  (cap %d)" % (len(todo), a.max))
    todo = todo[:a.max]
    if not a.go:
        print("\nat %.1fs each that is %.1f hour(s).  DRY RUN -- pass --go."
              % (a.delay, len(todo) * a.delay / 3600.0))
        return 0

    asked = empty = rows = 0
    gone = streak = 0
    refused = None
    t0 = time.time()
    for i, (name, mid, gm, tt, tn) in enumerate(todo):
        if asked:
            time.sleep(a.delay)
        url = ("%s/maps/%d/leaderboard?gamemode=%d&trackType=%d&trackNum=%d"
               "&take=%d&skip=0" % (API, mid, gm, tt, tn, take))
        try:
            body = get(url)
        except NoSuchBoard:
            asked += 1
            gone += 1
            streak += 1
            if streak >= SKIP_STREAK:
                refused = ("%d boards in a row answered 404 -- stopping. That is\n"
                           "  more likely the host refusing than a run of\n"
                           "  unpublished maps, and the difference is not ours\n"
                           "  to assume." % streak)
                break
            # Cache the absence, so a resume does not ask again.
            rec = {"map": name, "mapid": mid, "gamemode": gm, "trackType": tt,
                   "trackNum": tn, "total": 0, "fetched": int(time.time()),
                   "absent": True, "rows": []}
            p = os.path.join(a.out, board_key(mid, gm, tt, tn) + ".json")
            with io.open(p, "w", encoding="utf-8", newline="\n") as fh:
                fh.write(json.dumps(rec, separators=(",", ":")))
            continue
        except Refused as e:
            refused = "%s (%s g%d t%d%d): %s" % (name, mid, gm, tt, tn, e)
            break
        streak = 0
        asked += 1
        try:
            doc = json.loads(body.decode("utf-8", "replace"))
        except ValueError:
            refused = "%s: reply did not parse" % name
            break
        total, data = parse_board(doc)
        if not data:
            empty += 1
        rows += len(data)
        rec = {"map": name, "mapid": mid, "gamemode": gm, "trackType": tt,
               "trackNum": tn, "total": total, "fetched": int(time.time()),
               "rows": data}
        p = os.path.join(a.out, board_key(mid, gm, tt, tn) + ".json")
        with io.open(p, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(json.dumps(rec, separators=(",", ":")))
        if (i + 1) % 100 == 0:
            el = time.time() - t0
            print("  %5d/%d  %6.1f min elapsed  %5d rows  %4d empty  (%s)"
                  % (i + 1, len(todo), el / 60.0, rows, empty, name))

    print()
    print("requests made     %d" % asked)
    # asked counts every answer including the absent ones, so both have to
    # come off or this line claims rows for a board that 404d.
    print("boards with rows  %d" % (asked - empty - gone))
    print("boards empty      %d  (the catalogue claims them; nobody has run them)"
          % empty)
    print("boards absent     %d  (404: in the game's cache, not on the public API)"
          % gone)
    print("run rows cached   %d" % rows)
    print("elapsed           %.1f min" % ((time.time() - t0) / 60.0))
    if refused:
        print("\nREFUSED and stopped, nothing retried: %s" % refused)
        print("Everything already written is cached; re-running resumes here.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
