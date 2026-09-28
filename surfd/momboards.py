"""Index Momentum leaderboard TIMES (no demo needed) into the imported tier.

  python surfd/momboards.py --boards dist/momboards [--go] [--link]

tools/momfetch.py caches one JSON per board.  This turns those into `runs` rows
under TIER_MOMENTUM, so a map has a full board -- top N of main, every stage and
every bonus -- whether or not anybody has the demo.

TIMES AND REPLAYS ARRIVE BY DIFFERENT ROADS AND MEET HERE.  momindex.py files
the runs we hold a .mtv for and gives each a replay; this files the rest of the
leaderboard from the API and gives them `replay_id = 0`, which the board already
draws as "no watch".  Where the two describe the SAME run -- same map, track,
leg and SteamID -- `--link` joins them, and the row becomes watchable without
being fetched twice.

NEITHER SIDE CLOBBERS THE OTHER.  The upsert here never writes `replay_id`, so
a row that momindex gave a recording keeps it even when this runs afterwards
with a marginally different time for the same run.  Order does not matter, which
is the property that lets a cron run both.

`ticks` IS DERIVED AND `millis` IS THE FACT.  The API reports seconds; the
schema wants a tick count, so this divides by the gamemode's interval (surf
0.015, bhop 0.01) and says so.  Anything reading `ticks` off one of these rows
is reading a number nobody counted.

`submitted` IS THE RUN'S OWN DATE, NOT OUR INGEST TIME.  Each API row carries
`created`, and the web board draws that column, so ingest time made all 85,085
imported rows read 2026-09-28.  Nothing reads an import's ingest time (no review
exists on one, staleness is per-file mtime), and BOARD_ORDER's `submitted`
tiebreak gets MORE correct: on equal times the run set first ranks first.  A row
whose `created` will not parse falls back to now and is counted, never zeroed.
"""
import argparse
import datetime
import glob
import io
import json
import os
import re
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import surfd as S       # noqa: E402  -- import-safe: app.run is __main__-guarded

# Player aliases are free Unicode from another game's API, and Windows'
# default stdout is cp1252 -- so merely PRINTING a name can kill the tool
# after the work is done.  This has now bitten once on a file write and once
# on a progress line; "replace" rather than "strict" because a mangled glyph
# in a console line is not worth losing a sweep over.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Momentum's own tick interval per gamemode, measured over 7486 .mtv headers:
# surf 0.015 (66.67, exactly ours), bhop 0.01.  Not a guess and not a default.
TICK = {1: 0.015, 2: 0.01}


# The fractional seconds in an ISO timestamp, after the seconds field.
_FRAC = re.compile(r"(?<=:\d\d)\.(\d+)")


def created_epoch(raw):
    """A row's `created` -> unix seconds, or None if it is not a timestamp.

    Not `fromisoformat(raw)`: the Pi runs 3.10, which learned neither the `Z`
    suffix nor an odd-width fraction until 3.11 -- measured, both raise
    ValueError there -- so the suffix is swapped and the fraction padded to 6.
    A naive stamp is read as UTC; all 81,290 rows in the 3,726-file cache are
    `...Z` with exactly 3 fractional digits, so the rest is for a format drift.
    """
    if not isinstance(raw, str) or not raw.strip():
        return None
    s = raw.strip()
    if s[-1] in "Zz":
        s = s[:-1] + "+00:00"
    m = _FRAC.search(s)
    if m:
        s = s[:m.start(1)] + (m.group(1) + "000000")[:6] + s[m.end(1):]
    try:
        dt = datetime.datetime.fromisoformat(s)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=datetime.timezone.utc)
    try:
        return int(dt.timestamp())
    except (OverflowError, OSError, ValueError):
        return None


def track_leg(track_type, track_num):
    """Momentum's (trackType, trackNum) -> our (track, leg). trackNum is 1-based."""
    if track_type == 0:
        return 0, 0
    if track_type == 1:
        return 0, int(track_num)
    return int(track_num), 0


def load(path):
    try:
        with io.open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--boards", required=True, help="momfetch's cache dir")
    ap.add_argument("--link", action="store_true",
                    help="join rows to a replay we already hold for that run")
    ap.add_argument("--drop-impossible", action="store_true",
                    help="remove demo-derived rows that beat the official #1 "
                         "for their board; reported either way")
    ap.add_argument("--go", action="store_true")
    a = ap.parse_args()

    files = sorted(glob.glob(os.path.join(a.boards, "*.json")))
    conn = S.connect()
    now = int(time.time())

    seen = boards = empty = skipped = nodate = 0
    rows = []
    dates = []
    for p in files:
        doc = load(p)
        if not doc:
            skipped += 1
            continue
        boards += 1
        gm = doc.get("gamemode")
        tick = TICK.get(gm)
        if tick is None:
            skipped += 1
            continue
        mp = S.clean_map(doc.get("map") or "")
        if mp is None:
            skipped += 1
            continue
        track, leg = track_leg(doc.get("trackType", 0), doc.get("trackNum", 1))
        data = doc.get("rows") or []
        if not data:
            empty += 1
            continue
        for r in data:
            sid = r.get("steamid") or ""
            t = r.get("time")
            if not sid.isdigit() or not isinstance(t, (int, float)) or t <= 0:
                continue
            ms = int(round(t * 1000.0))
            when = created_epoch(r.get("created"))
            if when is None:
                nodate += 1
                when = now
            else:
                dates.append(when)
            rows.append((mp, track, leg, sid,
                         S.clean_text(r.get("alias") or "?") or "?",
                         int(round(ms / 1000.0 / tick)), 1.0 / tick, ms, when))
            seen += 1

    print("board files       %d  (%d empty, %d unusable)" % (boards, empty, skipped))
    print("leaderboard rows  %d" % seen)
    print("no usable created %d  (dated with this import's clock instead)" % nodate)
    if dates:
        print("run dates         %s .. %s"
              % (time.strftime("%Y-%m-%d", time.gmtime(min(dates))),
                 time.strftime("%Y-%m-%d", time.gmtime(max(dates)))))
    if not a.go:
        print("\nDRY RUN -- nothing written.  Pass --go.")
        return 0

    wrote = 0
    with conn:
        for (mp, track, leg, sid, alias, ticks, rate, ms, when) in rows:
            # replay_id is written on INSERT only.  The update list deliberately
            # omits it, so a row momindex gave a recording keeps it.
            cur = conn.execute(
                "INSERT INTO runs (map, track, leg, tier, style, player, name,"
                "   ticks, tickrate, millis, flags, node, runid, submitted, replay_id)"
                " VALUES (?,?,?,?,?,?,?,?,?,?,0,'momapi','',?,0)"
                " ON CONFLICT (map, track, leg, tier, style, player) DO UPDATE SET"
                "   ticks=excluded.ticks, millis=excluded.millis,"
                "   name=excluded.name, submitted=excluded.submitted"
                " WHERE excluded.millis < runs.millis",
                (mp, track, leg, S.TIER_MOMENTUM, S.STYLE_CLEAN, sid, alias,
                 ticks, rate, ms, when))
            wrote += cur.rowcount
    print("board rows set    %d" % wrote)

    # A DEMO-DERIVED TIME THAT BEATS MOMENTUM'S OWN #1 IS NOT A RECORD.
    # The API answers for the same board, so the two can be compared, and 5 of
    # 4,743 disagree -- a 0.405 s "run" on a board whose real record is 92.565 s
    # (a 76-sample fragment), a surf_utopia main at half the world record whose
    # own header reports a 10,073 u/s peak. Each sits at the TOP of its board.
    #
    # 0.5% of slack, not zero: the two sources round differently (the API sends
    # seconds as a double, the demo's time comes off its own header), and a row
    # that ties the record is a row that IS the record.
    #
    # Reported always, removed only on request: deleting somebody's row because
    # two sources disagree is a judgement, and the number is small enough to
    # look at.
    api_best = {}
    for p in files:
        doc = load(p)
        if not doc or not (doc.get("rows") or []):
            continue
        tt, tn = doc.get("trackType", 0), doc.get("trackNum", 1)
        tr, lg = track_leg(tt, tn)
        mp = S.clean_map(doc.get("map") or "")
        if mp is None:
            continue
        api_best[(mp, tr, lg)] = min(r["time"] for r in doc["rows"]) * 1000.0

    bad = []
    for r in conn.execute(
            "SELECT map, track, leg, player, name, millis FROM runs"
            " WHERE tier=? AND replay_id>0", (S.TIER_MOMENTUM,)):
        ref = api_best.get((r["map"], r["track"], r["leg"]))
        if ref is not None and r["millis"] < ref * 0.995:
            bad.append((r["map"], r["track"], r["leg"], r["player"],
                        r["name"], r["millis"], ref))
    print("faster than the official #1  %d row(s)" % len(bad))
    for mp, tr, lg, _pl, nm, ms, ref in sorted(bad, key=lambda b: b[5] / b[6])[:8]:
        print("   %-26s t%d l%d  %8.3fs vs %8.3fs official   %s"
              % (mp, tr, lg, ms / 1000.0, ref / 1000.0, nm[:18]))
    if bad and a.drop_impossible:
        with conn:
            for mp, tr, lg, pl, _nm, _ms, _ref in bad:
                conn.execute("DELETE FROM runs WHERE tier=? AND map=? AND track=?"
                             " AND leg=? AND player=?",
                             (S.TIER_MOMENTUM, mp, tr, lg, pl))
        print("dropped %d row(s); their .rec files are untouched on disk" % len(bad))
    elif bad:
        print("  (left in place -- pass --drop-impossible to remove them)")

    if a.link:
        with conn:
            cur = conn.execute(
                "UPDATE runs SET replay_id = ("
                "  SELECT p.id FROM replays p"
                "   WHERE p.kind='momentum' AND p.map=runs.map AND p.track=runs.track"
                "     AND p.leg=runs.leg AND p.player=runs.player"
                "   ORDER BY p.millis ASC LIMIT 1)"
                " WHERE tier=? AND replay_id=0 AND EXISTS ("
                "  SELECT 1 FROM replays p WHERE p.kind='momentum' AND p.map=runs.map"
                "     AND p.track=runs.track AND p.leg=runs.leg"
                "     AND p.player=runs.player)",
                (S.TIER_MOMENTUM,))
            print("linked to a held demo %d row(s)" % cur.rowcount)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
