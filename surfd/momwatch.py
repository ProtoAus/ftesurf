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
  2. nothing else.  A sweep of everything is tools/momfetch.py and is a separate,
     deliberate act.

IT IS A SLOW LOOP ON PURPOSE.  --max bounds one invocation, the fetcher keeps
its own delay between requests, and a map whose boards are fresh costs nothing
at all.  Run it from cron every few minutes: on an idle fleet it makes zero
requests, and on a busy one it makes a few dozen spread over minutes.

STALENESS IS PER BOARD, NOT PER MAP.  A map's stage 7 board is refreshed on its
own schedule from its own file mtime, so a map that gained one new stage record
does not re-fetch its other fifteen boards.
"""
import argparse
import io
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))

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


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--tracks", required=True)
    ap.add_argument("--boards", required=True)
    ap.add_argument("--stale", type=float, default=24.0, help="hours")
    ap.add_argument("--max", type=int, default=60, help="requests this invocation")
    ap.add_argument("--delay", type=float, default=1.0)
    ap.add_argument("--take", type=int, default=25)
    ap.add_argument("--index", action="store_true",
                    help="run momboards afterwards so the rows land")
    ap.add_argument("--go", action="store_true")
    a = ap.parse_args()

    cat = momfetch.read_tracks(a.tracks)
    by_lower = {n.lower(): m for n, m in cat.items()}

    conn = S.connect()
    live = live_maps(conn)
    conn.close()
    if not live:
        print("no live lobby in the last %ds -- nothing to prepare" % LOBBY_FRESH)
        return 0

    cut = time.time() - a.stale * 3600.0
    want, fresh_n, unknown = [], 0, []
    for name, pop, nodes in live:
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
            try:
                if os.path.getmtime(p) >= cut:
                    fresh_n += 1
                    continue
            except OSError:
                pass
            want.append((m["name"], pop))

    print("live maps          %d  %s" % (len(live), [n for n, _, _ in live[:6]]))
    if unknown:
        print("  not in the catalogue: %s" % unknown[:6])
    print("boards already fresh %d  (inside %.0f h)" % (fresh_n, a.stale))
    print("boards to refresh    %d" % len(want))

    # One momfetch per MAP, not per board: its own cache check picks exactly the
    # stale ones, and a map is the unit a player is waiting on.
    maps = []
    for n, _pop in want:
        if n not in maps:
            maps.append(n)
    if not maps:
        print("everything the fleet is on is already prepared.")
        return 0
    print("maps to ask about    %d  %s" % (len(maps), maps[:6]))

    if not a.go:
        print("\nDRY RUN -- nothing fetched.  Pass --go.")
        return 0

    cmd = [sys.executable, os.path.join(os.path.dirname(HERE), "tools", "momfetch.py"),
           "--tracks", a.tracks, "--out", a.boards, "--take", str(a.take),
           "--delay", str(a.delay), "--max", str(a.max), "--refresh", "--go"]
    for n in maps:
        cmd += ["--map", n]
    rc = subprocess.call(cmd)
    if rc != 0:
        print("momfetch stopped (%d) -- see above; nothing is retried here" % rc)
        return rc

    if a.index:
        rc = subprocess.call([sys.executable, os.path.join(HERE, "momboards.py"),
                              "--boards", a.boards, "--link", "--go"])
        if rc != 0:
            return rc
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
