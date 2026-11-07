#!/usr/bin/env python3
"""P1379: park or restore one map's WOS leaderboard times, on purpose.

    python3 -I boardarchive.py [--db PATH] list    --map M
    python3 -I boardarchive.py [--db PATH] archive --map M --label L [--apply]
    python3 -I boardarchive.py [--db PATH] restore --map M --label L [--park-live-as L2] [--apply]

Owner, 8 Nov 2026: when a map moves between surf and bhop rules (zone_edit's mode, P1371), its old
times go to an archive, restorable.  Run by hand after such a change: zonepub refuses an automatic
hide/archive (zonepub.py stage()), and the automatic detection first written for P1379 failed review
(boards already mixed, a misread mapmeta.txt parking boards nobody changed, a zone admin flipping a
board twenty times an hour).

HOW.  A `runs` row or kind='run' `replays` row of the map whose tier is a WOS tier -- ranked or
community, their stage forms "<tier>@<runid>" / "<tier>^<tag>", each optionally under "banned:" --
moves to "mode:<label>:" + tier, inside any "banned:".  That is how accounts.ban_rows parks a ban:
every reader names its tiers, so nothing lists or ranks a parked row, and ban, unban and restand keep
working inside the family.  Imported tiers (momentum, ksf, ...) never move.  Replay ids do not change,
so verdicts, reviews and receipts stay linked and a restore is exact.

REVIEWS MADE WHILE PARKED.  surfd's stage maintenance (restage) works on live tiers only, so a replay
cleared or approved while its map was parked keeps that run's stage times hidden ("<tier>@<runid>")
after a restore.  restore names every such run: re-review it once in the admin panel.  The reverse (a
reject made while parked) is put right by the sweeper's restage_rejected within one pass.

NOTHING IS DELETED.  archive refuses a label that already holds rows of the map; restore refuses while
live rows exist unless they are parked first under --park-live-as.  So no board slot ever collides
(the runs key holds the tier).  A dry run unless --apply; each applied operation is one
BEGIN IMMEDIATE transaction and one line in boardarchive.log beside the database.

Standalone on purpose (sqlite3 only): on the Pi surfd.py is a guarded generation's dispatcher, and
this tool must not import or restart the service.
"""
import argparse
import datetime
import os
import re
import sqlite3
import sys

BAN = "banned:"                 # accounts.BAN_TIER
MODE = "mode:"
WOS = ("ranked", "community")   # surfd.TIERS
LABEL_OK = re.compile(r"[a-z0-9][a-z0-9-]{0,15}\Z")
MAP_OK = re.compile(r"[a-z0-9_.+\-]{1,64}\Z")   # surfd _MAPNAME_OK's set, lowercased
DEFAULT_DB = "/srv/nvme/surfd/data/surfd.db"


def _unban(tier):
    return (BAN, tier[len(BAN):]) if tier.startswith(BAN) else ("", tier)


def is_live_wos(tier):
    _, t = _unban(tier)
    if t.startswith(MODE):
        return False
    return re.split(r"[@^]", t, maxsplit=1)[0] in WOS


def parked_label(tier):
    """The label a parked tier carries, or None."""
    _, t = _unban(tier)
    if not t.startswith(MODE):
        return None
    label, sep, rest = t[len(MODE):].partition(":")
    return label if sep and re.split(r"[@^]", rest, maxsplit=1)[0] in WOS else None


def park(tier, label):
    ban, t = _unban(tier)
    return ban + MODE + label + ":" + t


def unpark(tier, label):
    ban, t = _unban(tier)
    return ban + t[len(MODE + label + ":"):]


def connect(path):
    if not os.path.isfile(path):
        raise SystemExit("no database at %s" % path)
    conn = sqlite3.connect(path, timeout=10.0, isolation_level=None)
    conn.execute("PRAGMA busy_timeout=10000")
    return conn


def _rows(conn, mapname):
    runs = conn.execute("SELECT rowid, tier FROM runs WHERE map = ?", (mapname,)).fetchall()
    reps = conn.execute("SELECT id, tier FROM replays WHERE map = ? AND kind = 'run'",
                        (mapname,)).fetchall()
    return runs, reps


def summary(conn, mapname):
    """{"live": (runs, replays), "<label>": (runs, replays), "other": (runs, replays)}"""
    runs, reps = _rows(conn, mapname)
    out = {}

    def add(key, i):
        r = list(out.get(key, (0, 0)))
        r[i] += 1
        out[key] = tuple(r)
    for i, rows in ((0, runs), (1, reps)):
        for _, tier in rows:
            if is_live_wos(tier):
                add("live", i)
            elif parked_label(tier) is not None:
                add("label " + parked_label(tier), i)
            else:
                add("other (imported, untouched)", i)
    return out


def _move(conn, mapname, pick, dest):
    runs, reps = _rows(conn, mapname)
    n_runs = n_reps = 0
    for rowid, tier in runs:
        if pick(tier):
            conn.execute("UPDATE runs SET tier = ? WHERE rowid = ?", (dest(tier), rowid))
            n_runs += 1
    for rid, tier in reps:
        if pick(tier):
            conn.execute("UPDATE replays SET tier = ? WHERE id = ?", (dest(tier), rid))
            n_reps += 1
    return n_runs, n_reps


def archive(conn, mapname, label, apply):
    s = summary(conn, mapname)
    live = s.get("live", (0, 0))
    held = s.get("label " + label, (0, 0))
    if held != (0, 0):
        return 1, "label %r already holds %d rows / %d recordings of %s: pick another label" % (
            label, held[0], held[1], mapname)
    if live == (0, 0):
        return 1, "%s has no live WOS times to archive" % mapname
    if not apply:
        return 0, "dry run: would park %d rows / %d recordings of %s as %r (--apply to do it)" % (
            live[0], live[1], mapname, label)
    conn.execute("BEGIN IMMEDIATE")
    try:
        if summary(conn, mapname).get("label " + label, (0, 0)) != (0, 0):
            raise RuntimeError("label filled meanwhile")
        n = _move(conn, mapname, is_live_wos, lambda t: park(t, label))
        conn.execute("COMMIT")
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    return 0, "parked %d rows / %d recordings of %s as %r" % (n[0], n[1], mapname, label)


def restore(conn, mapname, label, park_live_as, apply):
    s = summary(conn, mapname)
    held = s.get("label " + label, (0, 0))
    live = s.get("live", (0, 0))
    if held == (0, 0):
        return 1, "nothing of %s is parked as %r" % (mapname, label)
    if live != (0, 0) and not park_live_as:
        return 1, ("%s has %d live rows / %d recordings: pass --park-live-as LABEL to park them first"
                   % (mapname, live[0], live[1]))
    if park_live_as:
        if park_live_as == label:
            return 1, "--park-live-as must differ from --label"
        other = s.get("label " + park_live_as, (0, 0))
        if live != (0, 0) and other != (0, 0):
            return 1, "label %r already holds %d rows / %d recordings of %s" % (
                park_live_as, other[0], other[1], mapname)
    if not apply:
        first = ("park %d live rows / %d recordings as %r, then " % (live[0], live[1], park_live_as)
                 if live != (0, 0) else "")
        return 0, "dry run: would %srestore %d rows / %d recordings of %s from %r (--apply to do it)" % (
            first, held[0], held[1], mapname, label)
    conn.execute("BEGIN IMMEDIATE")
    try:
        s = summary(conn, mapname)
        parked_first = (0, 0)
        if s.get("live", (0, 0)) != (0, 0):
            if not park_live_as or s.get("label " + park_live_as, (0, 0)) != (0, 0):
                raise RuntimeError("live rows appeared meanwhile; run it again")
            parked_first = _move(conn, mapname, is_live_wos, lambda t: park(t, park_live_as))
        n = _move(conn, mapname, lambda t: parked_label(t) == label, lambda t: unpark(t, label))
        conn.execute("COMMIT")
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    msg = "restored %d rows / %d recordings of %s from %r" % (n[0], n[1], mapname, label)
    if parked_first != (0, 0):
        msg = "parked %d rows / %d recordings as %r; %s" % (parked_first[0], parked_first[1],
                                                           park_live_as, msg)
    return 0, msg


# surfd.py _REJECTED_SQL and _run_rejected: a current reject on a bound recording of the run.
_RUN_REJECTED = ("SELECT 1 FROM replays p WHERE p.map = ? AND p.track = ? AND p.player = ? AND p.runid = ?"
                 " AND p.bound = 1 AND EXISTS (SELECT 1 FROM reviews w WHERE w.replay_id = p.id"
                 " AND w.decision = 'reject' AND w.at >= p.submitted) LIMIT 1")


def stage_mismatch(conn, mapname):
    """Runs whose live stage rows disagree with their current reviews: (hidden but not rejected,
    shown but rejected), each a list of (track, player, runid)."""
    hidden, shown = set(), set()
    for track, tier, player, runid in conn.execute(
            "SELECT track, tier, player, runid FROM runs WHERE map = ? AND leg > 0", (mapname,)):
        _, t = _unban(tier)
        base, sep, run = t.partition("@")
        if base not in WOS or t.startswith(MODE):
            continue
        if sep:
            key = (track, player, run)
            if conn.execute(_RUN_REJECTED, (mapname,) + key).fetchone() is None:
                hidden.add(key)
        elif "^" not in t and runid not in ("", "-"):
            key = (track, player, runid)
            if conn.execute(_RUN_REJECTED, (mapname,) + key).fetchone() is not None:
                shown.add(key)
    return sorted(hidden), sorted(shown)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", default=DEFAULT_DB)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("list", "archive", "restore"):
        p = sub.add_parser(name)
        p.add_argument("--map", required=True)
        if name != "list":
            p.add_argument("--label", required=True, help="e.g. surf or bhop: the rules the times were set under")
            p.add_argument("--apply", action="store_true", help="write; otherwise a dry run")
        if name == "restore":
            p.add_argument("--park-live-as", help="park the current live times under this label first")
    a = ap.parse_args(argv)
    mapname = a.map.lower()
    if not MAP_OK.match(mapname):
        print("bad map name"); return 2
    for lab in (getattr(a, "label", None), getattr(a, "park_live_as", None)):
        if lab is not None and not LABEL_OK.match(lab):
            print("bad label %r: [a-z0-9-], at most 16" % lab); return 2
    conn = connect(a.db)
    log = None
    try:
        if a.cmd != "list" and a.apply:     # opened first: an applied change is never left unlogged
            log = open(os.path.join(os.path.dirname(os.path.abspath(a.db)), "boardarchive.log"), "a")
        if a.cmd == "list":
            for k, (r, p) in sorted(summary(conn, mapname).items()):
                print("%-32s %6d rows %6d recordings" % (k, r, p))
            return 0
        if a.cmd == "archive":
            code, msg = archive(conn, mapname, a.label, a.apply)
        else:
            code, msg = restore(conn, mapname, a.label, a.park_live_as, a.apply)
        if code == 0 and log is not None:
            log.write("%s %s %s %s\n" % (datetime.datetime.now(datetime.timezone.utc)
                                          .strftime("%Y-%m-%dT%H:%M:%SZ"), a.cmd, mapname, msg))
            log.flush()
        print(msg)
        if code == 0 and a.cmd == "restore" and a.apply:
            hidden, shown = stage_mismatch(conn, mapname)
            for track, player, run in hidden:
                print("  stage times of run %s (%s, track %d) are hidden with no current reject:"
                      " re-review its replay once to show them" % (run, player, track))
            for track, player, run in shown:
                print("  stage times of run %s (%s, track %d) are shown under a current reject:"
                      " the sweeper re-hides them within one pass" % (run, player, track))
        return code
    finally:
        if log is not None:
            log.close()
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
