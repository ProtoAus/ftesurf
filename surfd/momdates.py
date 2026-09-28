"""Backfill `submitted` on imported Momentum rows from the run's own date.

  python surfd/momdates.py --boards /srv/nvme/surfd/data/momboards [--go]

THE ROWS THIS REPAIRS WERE FILED BEFORE momboards.py READ `created`.  All 85,085
of them carry the instant their import ran -- one day, 2026-09-28 -- and the web
board draws that column as the run's Date.  The real one was already on disk:
every cached board row has `created`, the API's timestamp for that run.
momboards.py uses it for new rows; this walks the same cache and repairs the old.

IT CANNOT REACH EVERY ROW, AND SAYS WHICH.  momfetch caches the top N of a board
(25 by default) while a board's own `total` runs to 26,112, so a demo-derived row
ranked below that has no board row and no date here.  Measured on the live copy:
81,290 of 85,085 repaired, 3,795 left at their import date rather than guessed.

MATCHED THE WAY momboards.py FILES THEM.  It imports `track_leg` and
`created_epoch` from that module rather than re-deriving the mapping, so the
(map, track, leg, player) key is the same key there or neither works.  Measured
over the 3,726-file cache: 81,290 rows, 81,290 distinct keys, so the mapping is
1:1 and no row has to choose between two dates.

IT DATES THE REPLAY THE ROW POINTS AT, and only that one.  `runs.replay_id` names
the recording the board offers to Watch, so that is the run this date describes.
The rest are counted BY REASON -- its runs row matched nothing, or nothing points
at it (a beaten run, whose date a board does not publish) -- because one lumped
total reads 1,486 on a re-run where it reads 490 on the first, and did.

NOTHING OUTSIDE THE IMPORTED TIER MOVES.  Every statement filters
tier='momentum' / kind='momentum': ranked and community rows are dated by the
lobby that wrote them, and ksf rows already carry KSF's own `date`.
"""
import argparse
import glob
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import surfd as S       # noqa: E402  -- import-safe: app.run is __main__-guarded
import momboards as MB  # noqa: E402  -- track_leg + created_epoch, not a copy

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def day(t):
    return time.strftime("%Y-%m-%d", time.gmtime(t)) if t else "-"


def span(values):
    return "%s .. %s" % (day(min(values)), day(max(values))) if values else "(none)"


def read_boards(board_dir):
    """(key -> run date) plus the counts, over momfetch's cache.

    The key is momboards.py's board key with the player appended, and the row
    filters are its filters: a non-numeric SteamID or a non-positive time never
    became a `runs` row, so it must not claim one here either.
    """
    files = sorted(glob.glob(os.path.join(board_dir, "*.json")))
    want = {}
    seen = boards = empty = skipped = nodate = 0
    for p in files:
        doc = MB.load(p)
        if not doc:
            skipped += 1
            continue
        boards += 1
        mp = S.clean_map(doc.get("map") or "")
        if mp is None:
            skipped += 1
            continue
        track, leg = MB.track_leg(doc.get("trackType", 0), doc.get("trackNum", 1))
        data = doc.get("rows") or []
        if not data:
            empty += 1
            continue
        for r in data:
            sid = r.get("steamid") or ""
            t = r.get("time")
            if not sid.isdigit() or not isinstance(t, (int, float)) or t <= 0:
                continue
            seen += 1
            when = MB.created_epoch(r.get("created"))
            if when is None:
                nodate += 1
                continue
            want[(mp, track, leg, sid)] = when
    return want, files, boards, empty, skipped, seen, nodate


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--boards", required=True, help="momfetch's cache dir")
    ap.add_argument("--go", action="store_true", help="write; otherwise a dry run")
    a = ap.parse_args()

    want, files, boards, empty, skipped, seen, nodate = read_boards(a.boards)
    print("board files       %d  (%d empty, %d unusable)"
          % (boards, empty, skipped))
    print("leaderboard rows  %d" % seen)
    print("rows with no date %d  (unparseable `created`; their row is left alone)"
          % nodate)
    print("dated board keys  %d   %s" % (len(want), span(list(want.values()))))
    if not files:
        print("\nno *.json under %s -- nothing to match against" % a.boards)
        return 2

    conn = S.connect()
    mom_replays = {r["id"] for r in conn.execute(
        "SELECT id FROM replays WHERE kind='momentum'")}

    run_edits = []          # (when, tier, map, track, leg, player)
    rep_edits = {}          # replay id -> when
    rep_ok = set()          # already carries its run's date
    rep_nomatch = set()     # its runs row matched no board row
    examined = matched = already = unmatched = 0
    before, after = [], []
    for r in conn.execute(
            "SELECT map, track, leg, player, submitted, replay_id FROM runs"
            " WHERE tier=?", (S.TIER_MOMENTUM,)):
        examined += 1
        before.append(r["submitted"])
        when = want.get((r["map"], r["track"], r["leg"], r["player"]))
        if when is None:
            unmatched += 1
            after.append(r["submitted"])
            if r["replay_id"] in mom_replays:
                rep_nomatch.add(r["replay_id"])
            continue
        matched += 1
        after.append(when)
        if when == r["submitted"]:
            already += 1
            if r["replay_id"] in mom_replays:
                rep_ok.add(r["replay_id"])
            continue
        run_edits.append((when, S.TIER_MOMENTUM, r["map"], r["track"], r["leg"],
                          r["player"]))
        if r["replay_id"] in mom_replays:
            rep_edits[r["replay_id"]] = when

    rep_before = [x["submitted"] for x in conn.execute(
        "SELECT submitted FROM replays WHERE kind='momentum'")]
    # All three reasons subtracted, not the edits alone -- see the docstring on
    # counting by reason; rep_ok exists for the re-run case.
    rep_unpointed = len(mom_replays - set(rep_edits) - rep_ok - rep_nomatch)

    print("\nruns rows (tier=momentum)")
    print("  examined        %d" % examined)
    print("  matched a board %d" % matched)
    print("  already correct %d" % already)
    print("  to update       %d" % len(run_edits))
    print("  no board row    %d  (outside the cached top N; left as they are)"
          % unmatched)
    print("replays rows (kind=momentum)")
    print("  indexed         %d" % len(mom_replays))
    print("  to update       %d" % len(rep_edits))
    print("  already correct %d" % len(rep_ok))
    print("  runs row unmatched  %d" % len(rep_nomatch))
    print("  no runs row points at it  %d  (a beaten run; the cache holds only"
          " the player's best)" % rep_unpointed)
    print("\nruns submitted  before  %s" % span(before))
    print("runs submitted  after   %s%s"
          % (span(after), "" if a.go else "   (projected)"))
    print("replays before          %s" % span(rep_before))

    if not a.go:
        print("\nDRY RUN -- nothing written.  Pass --go.")
        return 0

    with conn:
        conn.executemany(
            "UPDATE runs SET submitted=? WHERE tier=?"
            "  AND map=? AND track=? AND leg=? AND player=?", run_edits)
        conn.executemany(
            "UPDATE replays SET submitted=? WHERE id=? AND kind='momentum'",
            [(w, i) for i, w in rep_edits.items()])
    print("\nruns rows set      %d" % len(run_edits))
    print("replays rows set   %d" % len(rep_edits))
    now = [x["submitted"] for x in conn.execute(
        "SELECT submitted FROM runs WHERE tier=?", (S.TIER_MOMENTUM,))]
    rep_now = [x["submitted"] for x in conn.execute(
        "SELECT submitted FROM replays WHERE kind='momentum'")]
    print("runs submitted     %s" % span(now))
    print("replays submitted  %s" % span(rep_now))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
