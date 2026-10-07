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

NEITHER SIDE CLOBBERS THE OTHER.  The upsert here writes `replay_id` only to
clear it, so a row that momindex gave a recording keeps it even when this runs
afterwards with a marginally different time (within LINK_SLACK_MS) for the same
run.  Order does not matter, which is the property that lets a cron run both.

`ticks` IS DERIVED AND `millis` IS THE FACT.  The API reports seconds; the
schema wants a tick count, so this divides by the gamemode's interval (surf
0.015, bhop 0.01) and says so.  Anything reading `ticks` off one of these rows
is reading a number nobody counted.

INCREMENTAL BY DEFAULT, AND THAT IS NOT AN OPTIMISATION.  This runs from cron
every 7 minutes and the corpus is heading for 2.9M rows now that momfetch pages;
measured at 84k rows a full pass is 2.0 s and 66 MB peak, which extrapolates to
~70 s and ~2.3 GB against a box with 1.0 GB available.  So a run reads only board
files whose mtime is newer than `<boards>/.indexed`, writes in CHUNK-sized
batches rather than building one list of everything, and advances the watermark to
the highest mtime it actually processed.  `--all` does the old full pass and is
the answer if the watermark and the cache ever disagree.

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
import logging
import os
import re
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

# Importing surfd logs "surfd ready" to surfd.log, which reads as a restart on
# every tick (sweep.py's fix): a handler on its logger first keeps it quiet.
if not logging.getLogger("surfd").handlers:
    _quiet = logging.StreamHandler(sys.stderr)
    _quiet.setLevel(logging.WARNING)
    logging.getLogger("surfd").addHandler(_quiet)

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

# How far under Momentum's own #1 a demo-derived row may sit before it is
# reported as impossible.  See the block over `api_best`.
IMPOSSIBLE_RATIO = 0.005
IMPOSSIBLE_FLOOR_MS = 20.0


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


CHUNK = 20000            # rows held before a flush; see the loop's comment
LINK_SLACK_MS = 20       # a linked recording's time must be within this much of its row's, either way: a tick, rounded


def flush(conn, rows):
    """Upsert one chunk of leaderboard rows.  Returns how many landed.

    replay_id is written on INSERT only, so a row momindex gave a recording keeps
    it -- unless the new time leaves that recording more than LINK_SLACK_MS off,
    when it is cleared for link_demos to relink (a 90 s demo once stayed the link
    of an 85 s row, and link_demos only fills replay_id 0).
    """
    if not rows:
        return 0
    wrote = 0
    with conn:
        for item in rows:
            mp, track, leg, sid, alias, ticks, rate, ms, when = item[:9]
            demo = item[9] if len(item) > 9 else ""
            cur = conn.execute(
                "INSERT INTO runs (map, track, leg, tier, style, player, name,"
                "   ticks, tickrate, millis, flags, node, runid, submitted, replay_id, momdemo)"
                " VALUES (?,?,?,?,?,?,?,?,?,?,0,'momapi','',?,0,?)"
                " ON CONFLICT (map, track, leg, tier, style, player) DO UPDATE SET"
                "   ticks=excluded.ticks, millis=excluded.millis,"
                "   name=excluded.name, submitted=excluded.submitted, momdemo=excluded.momdemo,"
                "   replay_id=CASE WHEN EXISTS (SELECT 1 FROM replays p"
                "       WHERE p.id = runs.replay_id"
                "       AND abs(p.millis - excluded.millis) > %d)"
                "     THEN 0 ELSE runs.replay_id END"
                " WHERE excluded.millis < runs.millis" % LINK_SLACK_MS,
                (mp, track, leg, S.TIER_MOMENTUM, S.STYLE_CLEAN, sid, alias,
                 ticks, rate, ms, when, demo))
            wrote += cur.rowcount
            # A metadata-only backfill on equal times. Never attach a slower
            # cached PB's hash to the faster row already indexed.
            if demo:
                meta = conn.execute("UPDATE runs SET momdemo=? WHERE map=? AND track=? AND leg=?"
                             " AND tier=? AND style=? AND player=? AND millis=?"
                             " AND momdemo != ?", (demo, mp, track, leg, S.TIER_MOMENTUM,
                             S.STYLE_CLEAN, sid, ms, demo))
                wrote += meta.rowcount
    return wrote


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


def report_impossible(conn, files, a):
    """Rows whose demo-derived time beats Momentum's own #1.

    Read-only unless --drop-impossible, so the caller may run it on a dry
    run.  Returns the list it reported.
    """
    # A DEMO-DERIVED TIME THAT BEATS MOMENTUM'S OWN #1 IS NOT A RECORD.
    # The API answers for the same board, so the two can be compared, and 5 of
    # 4,743 disagree -- a 0.405 s "run" on a board whose real record is 92.565 s
    # (a 76-sample fragment), a surf_utopia main at half the world record whose
    # own header reports a 10,073 u/s peak. Each sits at the TOP of its board.
    #
    # THE SLACK IS THE SMALLER OF 0.5% AND IMPOSSIBLE_FLOOR_MS, not the ratio
    # alone.  Some slack is needed because the two sources round differently
    # (the API sends seconds as a double, the demo's time comes off its own
    # header) and a row that ties the record is a row that IS the record.  But
    # 0.5% was sized against a 0.405 s "run" on a 92.565 s board, and on a 53 s
    # board it is 268 ms -- wide enough that surf_utopia's public #1 sat 60 ms
    # under Momentum's own record and passed.  The ratio still governs short
    # boards, where it is the tighter of the two (18 ms on a 3.7 s record).
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
        if ref is None:
            continue
        slack = min(ref * IMPOSSIBLE_RATIO, IMPOSSIBLE_FLOOR_MS)
        if r["millis"] < ref - slack:
            bad.append((r["map"], r["track"], r["leg"], r["player"],
                        r["name"], r["millis"], ref))
    print("faster than the official #1  %d row(s)"
          "   (slack: %.1f%% capped at %d ms)"
          % (len(bad), IMPOSSIBLE_RATIO * 100.0, IMPOSSIBLE_FLOOR_MS))
    # Sorted by the SIZE OF THE GAP, not the ratio: the rows worth looking at
    # first are the ones furthest under a record, whatever the board's length.
    for mp, tr, lg, _pl, nm, ms, ref in sorted(bad, key=lambda b: b[5] - b[6])[:20]:
        print("   %-26s t%d l%d  %8.3fs vs %8.3fs official  %+8.3fs  %s"
              % (mp, tr, lg, ms / 1000.0, ref / 1000.0,
                 (ms - ref) / 1000.0, nm[:18]))
    if bad and a.drop_impossible:
        with conn:
            for mp, tr, lg, pl, _nm, _ms, _ref in bad:
                conn.execute("DELETE FROM runs WHERE tier=? AND map=? AND track=?"
                             " AND leg=? AND player=?",
                             (S.TIER_MOMENTUM, mp, tr, lg, pl))
        print("dropped %d row(s); their .rec files are untouched on disk" % len(bad))
    elif bad:
        print("  (left in place -- pass --drop-impossible to remove them)")
    return bad


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--boards", required=True, help="momfetch's cache dir")
    ap.add_argument("--all", action="store_true",
                    help="re-read every board file, ignoring the .indexed\n"
                         "watermark, and re-audit every board for impossible\n"
                         "times.  The default is incremental by file mtime.")
    ap.add_argument("--link", action="store_true",
                    help="join rows to a replay we already hold for that run")
    ap.add_argument("--drop-impossible", action="store_true",
                    help="remove demo-derived rows that beat the official #1 "
                         "for their board; reported either way")
    ap.add_argument("--go", action="store_true")
    a = ap.parse_args()

    allfiles = sorted(glob.glob(os.path.join(a.boards, "*.json")))
    conn = S.connect()
    now = int(time.time())

    # INCREMENTAL BY FILE MTIME, because this runs from cron every 7 minutes and
    # the corpus is heading for 2.9M rows.  Measured at 84k rows: 2.0 s wall and
    # 66 MB peak for a full pass, which extrapolates to ~70 s and ~2.3 GB -- on a
    # box with 1.0 GB available.  A tick that only reads the dozen boards momwatch
    # just touched costs neither.
    #
    # THE WATERMARK LIVES BESIDE THE CACHE IT DESCRIBES, not in the database, so
    # deleting the board cache deletes the claim to have indexed it.  --all forces
    # a full pass and is what to reach for if the two ever disagree.
    mark = os.path.join(a.boards, ".indexed")
    since = 0
    if not a.all:
        try:
            with io.open(mark, encoding="utf-8") as fh:
                since = int(fh.read().strip())
        except (OSError, ValueError):
            since = 0
    files, high = [], since
    for p in allfiles:
        try:
            # NANOSECONDS, AS AN INTEGER.  st_mtime is a float and no decimal
            # spelling of it round-trips: written back as %.6f it rounds DOWN
            # below the real value, so the newest file stays permanently newer
            # than the watermark and is re-read on every run.  Measured twice --
            # once truncating to whole seconds, once at microseconds -- both left
            # exactly one file dirty forever.  st_mtime_ns has no such problem.
            mt = os.stat(p).st_mtime_ns
        except OSError:
            continue
        if mt > since:
            files.append(p)
            # The NEW watermark is the highest mtime actually processed, never
            # `now`: a board written while this was running would otherwise be
            # stamped as indexed and skipped forever.
            high = max(high, mt)
    if since:
        print("indexed through   %s  (%d of %d files changed since)"
              % (time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(since / 1e9)),
                 len(files), len(allfiles)))

    seen = boards = empty = skipped = nodate = 0
    rows = []
    wrote = 0
    dlo = dhi = None
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
                # min/max rather than a list of every date: 2.9M ints is 80 MB
                # held to print two of them.
                dlo = when if dlo is None else min(dlo, when)
                dhi = when if dhi is None else max(dhi, when)
            demo = r.get("hash") or ""
            if not isinstance(demo, str) or not re.fullmatch(r"[0-9a-f]{40}", demo):
                demo = ""
            rows.append((mp, track, leg, sid,
                         S.clean_text(r.get("alias") or "?") or "?",
                         int(round(ms / 1000.0 / tick)), 1.0 / tick, ms, when, demo))
            seen += 1
        # FLUSHED PER CHUNK, not once at the end.  The whole-corpus list is what
        # made a full pass cost 2.3 GB; this caps it at CHUNK tuples.  Safe to
        # write before the count is printed because every statement is an upsert
        # keyed on (map, track, leg, tier, style, player) -- a partial run leaves
        # correct rows, just fewer of them, and the watermark is only advanced at
        # the end so the rest are picked up next tick.
        if a.go and len(rows) >= CHUNK:
            wrote += flush(conn, rows)
            rows = []

    print("board files       %d  (%d empty, %d unusable)" % (boards, empty, skipped))
    print("leaderboard rows  %d" % seen)
    print("no usable created %d  (dated with this import's clock instead)" % nodate)
    if dlo is not None:
        print("run dates         %s .. %s"
              % (time.strftime("%Y-%m-%d", time.gmtime(dlo)),
                 time.strftime("%Y-%m-%d", time.gmtime(dhi))))
    # Read-only, so the list is visible without changing anything.
    if not a.go:
        report_impossible(conn, files, a)
        print("\nDRY RUN -- nothing written.  Pass --go.")
        return 0

    wrote += flush(conn, rows)
    print("board rows set    %d" % wrote)

    # ONLY NOW, and only on --go: a dry run has written nothing and must not
    # claim to have indexed anything, and a crash above leaves the old mark so
    # the same files are re-read rather than silently dropped.
    if a.go and high > since:
        try:
            with io.open(mark, "w", encoding="utf-8", newline="\n") as fh:
                fh.write("%d\n" % high)
        except OSError as e:
            print("could not write %s (%s) -- next run will re-read everything"
                  % (mark, e))

    # Only the boards this run actually read.  A board whose file did not change
    # cannot have become impossible since the last pass; --all re-audits the lot.
    report_impossible(conn, files, a)

    if a.link:
        print("linked to a held demo %d row(s)" % link_demos(conn))
    return 0


def link_demos(conn):
    """Give a momentum `runs` row with no recording a held one whose time IS the
    row's, within LINK_SLACK_MS either way -- never a faster impossible demo, never
    a slower superseded one.

    READ FIRST, WRITE ONLY THE HITS.  This was one UPDATE whose WHERE scanned
    every momentum row with replay_id 0 -- 2.35M on the Pi, 6.2 s -- inside the
    write transaction, past surfd's 5 s busy timeout on every */7 momwatch tick,
    where a /api/run would have been refused (BACKLOG).  The same set comes from
    the ~5k replays probed by runs' own key, without the write lock, and the
    write is only the rows found -- usually none.

    unlink_stale runs first, so a row whose link it drops can relink here.
    """
    dropped = unlink_stale(conn)
    if dropped:
        print("stale demo links dropped %d row(s)" % dropped)
    reps = {}
    for rid, mp, tr, lg, pl, ms in conn.execute(
            "SELECT id, map, track, leg, player, millis FROM replays WHERE kind='momentum'"):
        reps.setdefault((mp, tr, lg, pl), []).append((ms, rid))
    hits = []
    # The full unique key, style included, so each probe is a point lookup: both
    # writers of this tier (flush, momindex) write STYLE_CLEAN and nothing else.
    for (mp, tr, lg, pl), lst in reps.items():
        key = (mp, tr, lg, S.TIER_MOMENTUM, S.STYLE_CLEAN, pl)
        r = conn.execute("SELECT millis FROM runs WHERE map=? AND track=? AND leg=? AND tier=?"
                         " AND style=? AND player=? AND replay_id=0", key).fetchone()
        if r is None:
            continue
        # A recording whose time IS the row's, within slack either way.  The lower
        # bound keeps a demo dropped as impossible (0.405 s on a 92 s board, 28 Sep)
        # from becoming the watch link of the official time; the upper bound keeps a
        # superseded personal best -- slower than the row it would watch -- from
        # linking to a time it does not match.  Both bounds are link_exact's rule.
        ok = sorted(x for x in lst if abs(x[0] - r[0]) <= LINK_SLACK_MS)
        if ok:
            hits.append((ok[0][1],) + key + (ok[0][1],))
    if not hits:
        return 0
    # The write re-states the key, the empty link and the replay with its owner
    # and time: the read held no lock, a rowid could be reused, the replay deleted,
    # or re-filed under another player (momindex's upsert sets player).
    t0 = conn.total_changes
    with conn:
        conn.executemany(
            "UPDATE runs SET replay_id=? WHERE map=? AND track=? AND leg=? AND tier=?"
            " AND style=? AND player=? AND replay_id=0"
            " AND EXISTS (SELECT 1 FROM replays WHERE id=? AND kind='momentum'"
            "             AND map=runs.map AND track=runs.track AND leg=runs.leg"
            "             AND player=runs.player AND abs(millis - runs.millis) <= %d)"
            % LINK_SLACK_MS, hits)
    return conn.total_changes - t0


def unlink_stale(conn):
    """Clear the link of a momentum row whose recording's time is more than
    LINK_SLACK_MS from the row's -- left by flush before it learnt to clear one,
    or by a replay re-filed since.  -> rows cleared.

    Read first, write only the hits, like link_demos: CROSS JOIN pins replays as
    the outer loop (one runs_replay probe each), never a scan of the 2.9M runs.
    """
    hits = conn.execute(
        "SELECT r.map, r.track, r.leg, r.style, r.player, r.replay_id"
        " FROM replays p CROSS JOIN runs r ON r.replay_id = p.id"
        " WHERE r.tier = ? AND abs(p.millis - r.millis) > ?",
        (S.TIER_MOMENTUM, LINK_SLACK_MS)).fetchall()
    if not hits:
        return 0
    t0 = conn.total_changes
    with conn:
        conn.executemany(
            "UPDATE runs SET replay_id=0 WHERE map=? AND track=? AND leg=? AND tier=?"
            " AND style=? AND player=? AND replay_id=?"
            " AND EXISTS (SELECT 1 FROM replays p WHERE p.id = runs.replay_id"
            "             AND abs(p.millis - runs.millis) > %d)" % LINK_SLACK_MS,
            [(mp, tr, lg, S.TIER_MOMENTUM, st, pl, rid)
             for mp, tr, lg, st, pl, rid in hits])
    return conn.total_changes - t0


if __name__ == "__main__":
    raise SystemExit(main())
