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

DEPTH: `--depth`, AND THE UNIT OF WORK IS A PAGE RATHER THAN A BOARD.  Until
2026-09-29 every URL here carried a literal `&skip=0`, so 25 places was not a
default but a ceiling -- measured against the cache it built, 81,290 times held
of 2,927,709 that exist, 2.8%, with 2,914 of 3,726 boards stopped at exactly 25.
The API pages perfectly well (`skip=100` returns ranks 101-200, contiguous,
probed by hand before this was written); nothing asked it to.

  --depth 0    ONE page of --take, i.e. exactly what this tool did before.  The
               default, because a flag that deepens 3,726 boards should be typed
               rather than inherited.
  --depth 200  the deepest rank anything we serve can render (surfd.py's
               BOARD_LIMIT_MAX) -- 5,778 requests, ~2.4 h at 1.5 s
  --depth -1   every place on every board -- 31,420 requests, ~13 h

THE CACHE IS THE CURSOR.  `skip` is `len(rows)` of the board's own cached file,
so an interrupted deepening resumes with no bookkeeping, and the 429 that a long
sweep WILL hit (2,164 consecutive requests, measured) costs nothing but the
sitting.  This is the same property the original one-page-per-board design had,
extended rather than replaced.

PAGES ARE SORTED BY DEPTH, so every board reaches page 2 before any board
reaches page 3.  One `sort`, and it is what stops a sitting disappearing into
surf_kitsune stage 1 -- 26,112 times, 262 pages, more than an entire sitting's
budget for one board out of 3,726.  An interrupted deep sweep should leave the
corpus EVEN, not one map finished and a thousand untouched.

ROWS MERGE BY replayHash AND ARE ORDERED BY TIME.  A board that gains a record
between two of its pages shifts every rank below it, so appending blind would
duplicate the boundary row and dropping blind would lose it; identity by hash is
immune to the shift.  The `rank` field the API sends is kept but is ADVISORY --
nothing reads it (checked: momboards.py never mentions it, and surfd derives
rank at query time from BOARD_ORDER), which is what makes a stale one harmless.
WHAT THIS CANNOT SEE is a run DELETED upstream.  A union never shrinks, and
--refresh merges too rather than replacing, so nothing in this tool purges a row
the API has stopped serving -- deleting the board's json is the only way, which
costs its whole depth.  That is a deliberate trade and the reason is momwatch:
it passes --refresh every 7 minutes, and a first page that REPLACED would cut
each played map's board back to one page of rows on every tick.
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


def load_board(path):
    """A cached board record, or None if there is not a usable one.

    None covers absent, unreadable and half-written alike, and all three get the
    same answer: ask for the board from skip=0.  That is the self-healing
    property a deep sweep needs, since it is the one tool here most likely to be
    killed mid-write -- which is also why write_board goes through os.replace.
    """
    try:
        with io.open(path, encoding="utf-8") as fh:
            d = json.load(fh)
    except (OSError, ValueError):
        return None
    if not isinstance(d, dict) or not isinstance(d.get("rows"), list):
        return None
    return d


def write_board(path, rec):
    """.part then os.replace -- atomic, so an interrupted sweep never leaves a
    truncated JSON where a board used to be.  262 pages of surf_kitsune is a
    long time to hold a file open and hope."""
    part = path + ".part"
    with io.open(part, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(rec, separators=(",", ":")))
    os.replace(part, path)


def merge_rows(old, new):
    """Union by replayHash, ordered by time.

    See the docstring's ROWS MERGE paragraph for why identity is the hash and
    not the rank.  A row without a hash cannot be identified, so it is dropped
    -- parse_board already refuses those on the way in, and this is the second
    reader that would otherwise have to guess.
    """
    by = {}
    for r in list(old) + list(new):        # new wins: its rank is the fresher one
        h = r.get("hash")
        if h:
            by[h] = r
    out = list(by.values())
    out.sort(key=lambda r: (r.get("time", 0.0), r.get("rank") or 0))
    return out


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
    ap.add_argument("--take", type=int, default=25, help="places per REQUEST (max 100)")
    ap.add_argument("--depth", type=int, default=0,
                    help="places to hold per board; 0 means --take only (the\n"
                         "pre-2026-09-29 behaviour), -1 means the whole board")
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

    # A PAGE, not a board -- see the docstring's DEPTH section.  `skip` is read
    # off the cached rows, so this list is a plan against what is already held.
    todo = []
    held = wanted = fresh_boards = 0
    for (name, mid, gm, tt, tn) in jobs:
        path = os.path.join(a.out, board_key(mid, gm, tt, tn) + ".json")
        cur = load_board(path)
        if cur is None:
            todo.append((0, name, mid, gm, tt, tn))
            continue
        fresh_boards += 1
        have = len(cur["rows"])
        held += have
        if cur.get("absent"):
            # A 404 is cached so a resume does not ask again; only --refresh
            # reopens the question of whether the board has since appeared.
            if a.refresh:
                todo.append((0, name, mid, gm, tt, tn))
            continue
        total = cur.get("total") or 0
        want = total if a.depth < 0 else (min(total, a.depth) if a.depth else
                                         min(total, take))
        wanted += want
        # A set, so --refresh's page 1 and a tail that also starts at 0 are one
        # request rather than two.  A non-aligned skip is fine and is the normal
        # case here: the 2,914 boards stopped at 25 resume at skip=25, which
        # returns ranks 26-125.
        skips = set(range(have, want, take))
        if a.refresh:
            skips.add(0)
        for s in sorted(skips):
            todo.append((s, name, mid, gm, tt, tn))

    print("boards in scope   %d" % len(jobs))
    print("boards cached     %d" % fresh_boards)
    print("times held        %d" % held)
    print("times wanted      %d  (--depth %d)" % (wanted, a.depth))
    print("pages to ask for  %d  (cap %d)" % (len(todo), a.max))
    # SORTED BY DEPTH so the corpus deepens evenly; the docstring says why.
    todo.sort(key=lambda j: (j[0], j[1]))
    todo = todo[:a.max]
    if not a.go:
        print("\nat %.1fs each that is %.1f hour(s).  DRY RUN -- pass --go."
              % (a.delay, len(todo) * a.delay / 3600.0))
        return 0

    asked = empty = rows = 0
    gone = streak = 0
    refused = None
    t0 = time.time()
    got = short = 0
    for i, (skip, name, mid, gm, tt, tn) in enumerate(todo):
        if asked:
            time.sleep(a.delay)
        url = ("%s/maps/%d/leaderboard?gamemode=%d&trackType=%d&trackNum=%d"
               "&take=%d&skip=%d" % (API, mid, gm, tt, tn, take, skip))
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
            # Cache the absence, so a resume does not ask again.  Only ever on
            # the FIRST page: a 404 at skip=900 is the board ending, not the
            # board being absent, and writing absent:True there would throw away
            # 900 good rows.
            if skip:
                continue
            rec = {"map": name, "mapid": mid, "gamemode": gm, "trackType": tt,
                   "trackNum": tn, "total": 0, "fetched": int(time.time()),
                   "absent": True, "rows": []}
            write_board(os.path.join(a.out, board_key(mid, gm, tt, tn) + ".json"),
                        rec)
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
            # An empty FIRST page is a board the catalogue claims and nobody has
            # run.  An empty later page is the board ending sooner than its own
            # totalCount promised -- a different fact, counted separately, and
            # not a reason to doubt the rows already held.
            if skip:
                short += 1
            else:
                empty += 1
        rows += len(data)
        p = os.path.join(a.out, board_key(mid, gm, tt, tn) + ".json")
        # ALWAYS merge, including at skip=0.  Replacing on the first page looks
        # right and truncates a deep board to one page -- and momwatch passes
        # --refresh on every 7-minute tick, so that would have quietly cut every
        # played map's board back to `take` rows.
        cur = load_board(p)
        merged = merge_rows(cur["rows"], data) if cur else data
        got += len(merged) - (len(cur["rows"]) if cur else 0)

        # A SHORT LATER PAGE MEANS THE BOARD ENDED, so believe the page over the
        # board's own totalCount.  Without this an off-by-a-few totalCount is an
        # INFINITE ASK: want stays above have, the plan keeps generating that
        # last page, the page keeps returning nothing, and a backfill loops on it
        # forever.  Clamping is safe because a --refresh re-reads totalCount from
        # page 1 and restores the real figure, so a transient short page heals.
        if skip and len(data) < take:
            total = len(merged)
        rec = {"map": name, "mapid": mid, "gamemode": gm, "trackType": tt,
               "trackNum": tn, "total": total, "fetched": int(time.time()),
               "rows": merged}
        write_board(p, rec)
        if (i + 1) % 100 == 0:
            el = time.time() - t0
            print("  %5d/%d  %6.1f min  %6d new rows  %4d empty  (%s skip %d)"
                  % (i + 1, len(todo), el / 60.0, got, empty, name, skip))

    print()
    print("requests made     %d" % asked)
    # asked counts every answer including the absent ones, so both have to
    # come off or this line claims rows for a board that 404d.
    print("boards with rows  %d" % (asked - empty - gone))
    print("boards empty      %d  (the catalogue claims them; nobody has run them)"
          % empty)
    print("boards absent     %d  (404: in the game's cache, not on the public API)"
          % gone)
    print("pages short       %d  (a later page came back empty: the board ended\n"
          "                     sooner than its own totalCount promised)" % short)
    print("rows seen         %d" % rows)
    print("rows NEW to cache %d  (the rest were already held: see merge_rows)"
          % got)
    print("elapsed           %.1f min" % ((time.time() - t0) / 60.0))
    if refused:
        print("\nREFUSED and stopped, nothing retried: %s" % refused)
        print("Everything already written is cached; re-running resumes here.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
