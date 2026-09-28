"""Keep the imported board fresh for the maps people are actually on.

  python surfd/momwatch.py --tracks dist/momtracks.tsv --boards dist/momboards \
                           [--go] [--stale 24] [--max 60]

THE POINT IS THAT NOBODY WAITS.  A player presses tab and the board is already
there, because the map they are on had its leaderboards refreshed while they
were playing it.  surfd already knows what every lobby is running -- the
`lobbies` table carries each node's current map -- so this needs no new protocol,
no hook in the game and no message from the client.  It reads what is already
recorded.

WHAT IT REFRESHES, IN ORDER:
  1. maps a lobby is on RIGHT NOW whose boards are missing or older than --stale
  2. maps somebody opened on the WEBSITE, newest interest first (--want).  The
     queue is surfd's `mapwant` table, written by /board/api/map.
  3. with whatever --backfill allows, the shallowest boards anywhere (--depth).
  4. nothing else.  A full deliberate sweep is still tools/momfetch.py.

THE WEB QUEUE IS A QUEUE AND NOT A FETCH, and that is the point of it.  A public
unauthenticated GET must never turn into an outbound request to somebody else's
API while the visitor waits -- that is how a board page becomes a way to spend
our rate limit, and it is the shape the "every request is downstream of a button"
rule exists to prevent.  So the page records a row and this spends it on our own
schedule, under our own cap.

FRESH IS NOT THE SAME AS DEEP, and until 2026-09-29 this file could not tell the
difference.  It asked only whether a board's file was older than --stale, so a
board holding 25 of 322 places stayed at 25 forever however many people played
the map -- measured across the whole cache, 2,914 of 3,726 boards sat at exactly
25.  With --depth a board that is fresh but SHORT is also work.

IT IS A SLOW LOOP ON PURPOSE.  --max bounds the live/queued work and --backfill
bounds the crawl, separately, so one cannot eat the other; the fetcher keeps its
own delay between requests, and a map whose boards are fresh AND deep costs
nothing at all.  Run it from cron every few minutes: on an idle fleet with no
backfill it makes zero requests.

STALENESS IS MEASURED PER BOARD; THE FETCH IS STILL PER MAP.  Each board's own
file mtime decides whether it is stale, so one new stage record does not make the
map look stale everywhere -- but what this hands momfetch is `--map`, and with
--refresh that re-asks page 1 of every board that map has.  So a single stale
stage board does cost ~16 requests, not one.  Stated because the line this
replaces claimed the opposite and had done since the file was written; the fix
is an explicit --board selector in momfetch, which is in BACKLOG.md and not
here.

THE BACKFILL NEEDS NO STATE OF ITS OWN.  momfetch sorts its pages by depth, so
"every board to 100 before any board to 200" is already its behaviour; a backfill
is simply that tool with a small --max and no --map filter.  Nothing here has to
remember where it got to, because the board cache is the cursor.
"""
import argparse
import io
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
# In the repo, momfetch lives in ../tools.  On a deployed box everything is
# copied flat into one directory, so look there too -- and look BESIDE first,
# because that is the copy that shipped with this one.
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
sys.path.insert(0, HERE)


def _momfetch_path():
    for d in (HERE, os.path.join(os.path.dirname(HERE), "tools")):
        p = os.path.join(d, "momfetch.py")
        if os.path.exists(p):
            return p
    raise SystemExit("cannot find momfetch.py beside %s or in ../tools" % HERE)

import surfd as S       # noqa: E402
import momfetch         # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

LOBBY_FRESH = 300        # s; a lobby row older than this is not a live lobby


def live_maps(conn, fresh=LOBBY_FRESH):
    """Lowercased map names the fleet is on right now, most players first."""
    cut = int(time.time()) - fresh
    rows = conn.execute(
        "SELECT map, SUM(players) AS pop, COUNT(*) AS nodes FROM lobbies"
        " WHERE last_seen >= ? AND map != '' GROUP BY map"
        " ORDER BY pop DESC, map ASC", (cut,)).fetchall()
    return [(r["map"].lower(), r["pop"] or 0, r["nodes"]) for r in rows]


def wanted_maps(conn, limit):
    """Maps somebody opened on the website, newest interest first.

    BOUNDED RATHER THAN DRAINED.  A map nobody has looked at since Tuesday is
    not worth a request ahead of one somebody opened a minute ago, and --backfill
    reaches the rest regardless, so the queue is read as a priority list and
    never emptied.  Nothing is deleted here: the table is one row per map and
    cannot outgrow the library.

    An empty list is also the right answer against a schema-8 database, which
    has no such table -- this tool has to keep running through the deploy that
    adds one.
    """
    if limit <= 0:
        return []
    try:
        rows = conn.execute(
            "SELECT map FROM mapwant WHERE map != ''"
            " ORDER BY last DESC, asked DESC LIMIT ?", (limit,)).fetchall()
    except Exception:
        return []
    return [r["map"].lower() for r in rows]


def short_of_depth(path, depth, take):
    """Is this cached board holding fewer places than --depth asks for?

    False for a board with no readable file -- that is `missing`, which the mtime
    test has already called stale -- and False for a board SHORTER than depth: a
    40-place board is not thin at --depth 200, it is finished.  Getting that
    second one wrong is an infinite ask, which is the same trap momfetch's
    short-page clamp exists for.
    """
    d = momfetch.load_board(path)
    if d is None or d.get("absent"):
        return False
    total = d.get("total") or 0
    want = total if depth < 0 else min(total, depth if depth else take)
    return len(d["rows"]) < want


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--tracks", required=True)
    ap.add_argument("--boards", required=True)
    ap.add_argument("--stale", type=float, default=24.0, help="hours")
    ap.add_argument("--max", type=int, default=60, help="requests this invocation")
    ap.add_argument("--delay", type=float, default=1.0)
    # 100 is the API's own cap and there is no reason to ask for less: the same
    # data in a quarter of the requests, which is the scarce thing here.  Was 25
    # until 2026-09-29, when 25 stopped being a ceiling.
    ap.add_argument("--take", type=int, default=100, help="places per REQUEST")
    ap.add_argument("--depth", type=int, default=0,
                    help="places to hold per board; 0 keeps the pre-2026-09-29\n"
                         "behaviour (one page), -1 means the whole board")
    ap.add_argument("--want", type=int, default=0,
                    help="also prepare up to N maps from the website's queue")
    ap.add_argument("--backfill", type=int, default=0,
                    help="after the above, spend up to N requests deepening the\n"
                         "shallowest boards anywhere.  Its own cap on purpose,\n"
                         "so a busy fleet cannot starve the crawl and a long\n"
                         "crawl cannot delay a map somebody is standing on.")
    ap.add_argument("--index", action="store_true",
                    help="run momboards afterwards so the rows land")
    ap.add_argument("--go", action="store_true")
    a = ap.parse_args()

    cat = momfetch.read_tracks(a.tracks)
    by_lower = {n.lower(): m for n, m in cat.items()}

    conn = S.connect()
    live = live_maps(conn)
    queued = wanted_maps(conn, a.want)
    conn.close()

    # Lobbies first: somebody is standing on those maps.  The website's queue is
    # appended, minus anything a lobby already covers.
    onlive = {n for n, _, _ in live}
    cand = [(n, pop) for n, pop, _ in live] + [(n, 0) for n in queued
                                               if n not in onlive]
    print("live maps          %d  %s" % (len(live), [n for n, _, _ in live[:6]]))
    if queued:
        print("queued by the web  %d  %s" % (len(queued), queued[:6]))
    if not cand and a.backfill <= 0:
        print("no live lobby in the last %ds and nothing queued -- nothing to do"
              % LOBBY_FRESH)
        return 0

    cut = time.time() - a.stale * 3600.0
    want, fresh_n, unknown, thin, stale_n = [], 0, [], 0, 0
    for name, pop in cand:
        m = by_lower.get(name)
        if m is None:
            unknown.append(name)
            continue
        gm = momfetch.gm_of(m["name"])
        if gm is None:
            continue
        for bgm, tt, tn in m["boards"]:
            if bgm != gm:
                continue
            p = os.path.join(a.boards,
                             momfetch.board_key(m["id"], bgm, tt, tn) + ".json")
            stale = True
            try:
                stale = os.path.getmtime(p) < cut
            except OSError:
                pass                       # missing counts as stale
            if not stale:
                # Fresh, so the only remaining question is whether it is DEEP --
                # see the docstring.  Before --depth existed this was the end of
                # it and a 25-place board stayed one forever.
                if short_of_depth(p, a.depth, a.take):
                    thin += 1
                else:
                    fresh_n += 1
                    continue
            else:
                stale_n += 1
            want.append((m["name"], pop))

    if unknown:
        print("  not in the catalogue: %s" % unknown[:6])
    print("boards already done  %d  (fresh inside %.0f h and deep enough)"
          % (fresh_n, a.stale))
    print("boards stale         %d  (older than %.0f h: page 1 is re-asked)"
          % (stale_n, a.stale))
    print("boards fresh but thin %d  (--depth %d: only the missing pages)"
          % (thin, a.depth))
    print("boards to fetch      %d" % len(want))

    # One momfetch per MAP, not per board: its own cache check picks exactly the
    # stale ones, and a map is the unit a player is waiting on.
    maps = []
    for n, _pop in want:
        if n not in maps:
            maps.append(n)
    if maps:
        print("maps to ask about    %d  %s" % (len(maps), maps[:6]))
    else:
        print("everything live and queued is already prepared.")
    if not maps and a.backfill <= 0:
        return 0

    if not a.go:
        print("\nDRY RUN -- nothing fetched.  Pass --go.")
        return 0

    fetched = False

    if maps:
        cmd = [sys.executable, _momfetch_path(),
               "--tracks", a.tracks, "--out", a.boards, "--take", str(a.take),
               "--delay", str(a.delay), "--depth", str(a.depth),
               "--max", str(a.max), "--go"]
        # --refresh ONLY IF SOMETHING IS ACTUALLY STALE, and this is the one line
        # that decides whether a tick makes progress.  momfetch sorts pages by
        # depth, so a refresh's skip=0 pages sort ahead of every depth page --
        # measured: with --max 2 against two thin boards, both requests went on
        # re-reading ranks 1-25 we already held and the tick gained 0 rows, while
        # the backfill beside it gained 50 from the same budget.  A board that is
        # merely SHORT does not need its first page again.
        if stale_n:
            cmd.append("--refresh")
        for n in maps:
            cmd += ["--map", n]
        # FLUSH BEFORE EVERY CHILD.  Our prints are block-buffered under cron's
        # redirect while momfetch writes straight to the same fd, so without this
        # the log carries the fetch output ABOVE the summary that explains it --
        # observed in the first live run of this code.
        sys.stdout.flush()
        rc = subprocess.call(cmd)
        fetched = True
        if rc != 0:
            print("momfetch stopped (%d) -- see above; nothing is retried here"
                  % rc)
            return rc

    # THE BACKFILL, and it is deliberately the same tool with no --map and no
    # --refresh.  momfetch already sorts its pages by depth, so this asks for the
    # shallowest boards in the whole library and nothing else; --depth must be a
    # real depth or there is nothing to crawl towards, hence the -1 default here
    # rather than 0.
    if a.backfill > 0:
        print("\n--- backfill: up to %d page(s) into the shallowest boards ---"
              % a.backfill)
        cmd = [sys.executable, _momfetch_path(),
               "--tracks", a.tracks, "--out", a.boards,
               "--take", str(a.take),
               "--depth", str(a.depth if a.depth else -1),
               "--delay", str(a.delay), "--max", str(a.backfill), "--go"]
        sys.stdout.flush()
        rc = subprocess.call(cmd)
        fetched = True
        if rc != 0:
            print("backfill stopped (%d) -- nothing is retried here" % rc)
            return rc

    if a.index and fetched:
        sys.stdout.flush()
        rc = subprocess.call([sys.executable, os.path.join(HERE, "momboards.py"),
                              "--boards", a.boards, "--link", "--go"])
        if rc != 0:
            return rc
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
