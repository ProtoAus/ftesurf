#!/usr/bin/env python3
"""
test_momprofile.py -- the falsifier for P1117's per-player Momentum walk, and
for steamsync queueing every account's walks again each day.

    python surfd/test_momprofile.py

No network: `get` is a fake Momentum serving /v1/users and /v1/runs and
recording every URL.  surfd is imported against a throwaway home.
"""

import contextlib
import io
import json
import logging
import os
import re
import shutil
import sqlite3
import sys
import tempfile
import time
from unittest.mock import patch

FAILED = []
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)


def check(label, got, want):
    ok = got == want
    print("%-4s %-66s %r" % ("ok" if ok else "FAIL", label, got))
    if not ok:
        FAILED.append("%s: got %r, want %r" % (label, got, want))


HOME = tempfile.mkdtemp(prefix="surfd-momp-")
os.environ.update(SURFD_HOME=HOME, SURFD_DB=os.path.join(HOME, "test.db"))
import surfd as S          # noqa: E402
import momprofile as P     # noqa: E402
import ksfprofile as KP    # noqa: E402
import steamsync           # noqa: E402
import momwatch as MW      # noqa: E402

A, B = "76561198064721002", "76561198074624273"
NOW = 1793260000
# (mapid, gamemode, trackType, trackNum) -> map: momtracks' boards, own gamemode only
TRACKED = {(20, 1, 0, 1): "surf_utopia", (20, 1, 1, 1): "surf_utopia",
           (1, 2, 0, 1): "bhop_eazy"}


def db():
    S.migrate()
    c = S.connect()
    for t in ("momprofiles", "ksfprofiles", "momusers", "runs", "accounts"):
        c.execute("DELETE FROM %s" % t)
    c.commit()
    return c


def pb(mid, gm, tt, tn, t, style=0, pb=True, when="2026-10-23T09:38:15.836Z", uid=None):
    """uid None: the asked user's own (FakeMomentum fills it in)."""
    return {"id": 1, "gamemode": gm, "trackType": tt, "trackNum": tn, "style": style,
            "time": t, "flags": [], "isPB": pb, "userID": uid, "mapID": mid, "createdAt": when}


class FakeMomentum(object):
    """users: steamid -> Momentum id; runs: Momentum id -> [PB rows], newest first."""

    def __init__(self, users, runs):
        self.users, self.runs, self.asked = users, runs, []
        self.fail = None

    def __call__(self, url):
        self.asked.append(url[len(P.API):])
        if self.fail:
            raise self.fail
        m = re.match(r".*/users\?steamID=(\d+)$", url)
        if m:
            uid = self.users.get(m.group(1))
            data = [{"id": uid, "steamID": m.group(1), "alias": "x"}] if uid else []
            return json.dumps({"totalCount": len(data), "data": data}).encode()
        m = re.match(r".*/runs\?userID=(\d+)&isPB=true&take=(\d+)&skip=(\d+)$", url)
        uid = int(m.group(1))
        rows = [dict(r, userID=uid) if r["userID"] is None else r for r in self.runs.get(uid, [])]
        take, skip = int(m.group(2)), int(m.group(3))
        return json.dumps({"totalCount": len(rows), "data": rows[skip:skip + take]}).encode()


def momrows(c, player):
    return c.execute("SELECT map, track, leg, millis, submitted, name FROM runs WHERE"
                     " tier='momentum' AND player=? ORDER BY map, track, leg",
                     (player,)).fetchall()


def case_enqueue():
    c = db()
    check("a non-SteamID64 is not queued", P.enqueue(c, "b143a32b4cd1", NOW)["state"], "ineligible")
    c.execute("INSERT INTO momusers (steamid, momid) VALUES (?, 177)", (A,))
    c.commit()
    check("a SteamID64 is queued, with the Momentum id momusers holds",
          (P.enqueue(c, A, NOW)["state"],
           tuple(c.execute("SELECT momid, cursor FROM momprofiles WHERE player=?", (A,)).fetchone())),
          ("queued", (177, 0)))
    c.execute("UPDATE momprofiles SET state='complete', cursor=5, updated=? WHERE player=?", (NOW, A))
    c.commit()
    check("...a walk finished within TTL is not queued again",
          (P.enqueue(c, A, NOW + P.TTL - 1)["state"]), "complete")
    check("...and after TTL it is, from the first page",
          (P.enqueue(c, A, NOW + P.TTL)["state"],
           c.execute("SELECT cursor FROM momprofiles WHERE player=?", (A,)).fetchone()[0]),
          ("queued", 0))
    for i in range(P.MAX_ACTIVE):
        c.execute("INSERT INTO momprofiles (player, momid, cursor, state, asked, updated)"
                  " VALUES (?, 0, 0, 'queued', ?, ?)", ("x%d" % i, NOW, NOW))
    c.commit()
    check("...and past MAX_ACTIVE live walks a new one is refused as busy",
          P.enqueue(c, B, NOW)["state"], "busy")
    c.close()


def case_walk():
    c = db()
    c.execute("INSERT INTO runs (map, track, leg, tier, style, player, name, ticks, tickrate,"
              " millis, flags, node, runid, submitted, replay_id) VALUES"
              " ('surf_utopia', 0, 0, 'momentum', 'clean', ?, 'Proto', 1, 66.67, 53000, 0,"
              " 'momapi', '', 1, 0)", (A,))
    c.commit()
    P.enqueue(c, A, NOW)            # no momusers row: the walk asks who A is first
    pbs = [pb(20, 1, 0, 1, 54.0),                 # slower than the row held: not filed
           pb(20, 1, 1, 1, 5.775),                # a stage of a tracked map
           pb(20, 2, 0, 1, 9.0),                  # surf_utopia's bhop board: not tracked
           pb(20, 1, 1, 1, 5.0, style=1),         # another style
           pb(1, 2, 0, 1, 24.5, when="bad"),      # bhop_eazy, undated: today
           pb(999, 1, 0, 1, 10.0)]                # a map we do not track
    fake = FakeMomentum({A: 177}, {177: pbs})
    with patch.object(P, "TAKE", 4):
        spent = P.step(c, TRACKED, 1, fake, delay=0, now=NOW)
        check("the first request resolves the player's Momentum id, within budget",
              (spent, fake.asked, c.execute("SELECT momid FROM momusers WHERE steamid=?",
                                            (A,)).fetchone()[0]),
              (1, ["/users?steamID=" + A], 177))
        spent = P.step(c, TRACKED, 5, fake, delay=0, now=NOW)
    check("...then pages its PBs until the list ends",
          (spent, fake.asked[1:]), (2, ["/runs?userID=177&isPB=true&take=4&skip=0",
                                        "/runs?userID=177&isPB=true&take=4&skip=4"]))
    check("only tracked boards, style 0, the map's own gamemode, and a slower time never replaces",
          [tuple(r) for r in momrows(c, A)],
          [("bhop_eazy", 0, 0, 24500, NOW, "Proto"),
           ("surf_utopia", 0, 0, 53000, 1, "Proto"),
           ("surf_utopia", 0, 1, 5775, 1792748295, "Proto")])
    check("...and the walk is complete", P.status(c, A)["state"], "complete")
    c.close()


def case_round_robin_refusal_and_shape():
    c = db()
    c.execute("INSERT INTO momusers (steamid, momid) VALUES (?, 1), (?, 2)", (A, B))
    c.commit()
    P.enqueue(c, A, NOW)
    P.enqueue(c, B, NOW + 1)
    fake = FakeMomentum({}, {1: [pb(20, 1, 0, 1, 60.0 + i) for i in range(10)],
                             2: [pb(1, 2, 0, 1, 20.0)]})
    with patch.object(P, "TAKE", 4):
        P.step(c, TRACKED, 2, fake, delay=0, now=NOW + 10)
    check("two walks take turns, one page each", [u.split("&")[0] for u in fake.asked],
          ["/runs?userID=1", "/runs?userID=2"])
    fake.fail, fake.asked = RuntimeError("HTTP 429"), []
    try:
        with patch.object(P, "TAKE", 4):
            P.step(c, TRACKED, 2, fake, delay=0, now=NOW + 20)
        raised = False
    except RuntimeError:
        raised = True
    check("a refusal from get propagates (momwatch stops the tick), after one request",
          (raised, len(fake.asked)), (True, 1))
    check("...and leaves the cursor where the last answer did",
          (P.status(c, A)["state"], P.status(c, A)["next"]), ("partial", 4))
    fake.fail = None
    with patch.object(P, "TAKE", 4):
        P.step(c, TRACKED, 1, lambda url: b"<html>not json</html>", delay=0, now=NOW + 30)
    check("a reply of the wrong shape ends that walk as unknown, nothing raised",
          P.status(c, A)["state"], "refused")
    c.close()


def case_p1117r1_hostile_rows():
    """Every field is somebody else's: types, ranges, and the user it is for."""
    c = db()
    c.execute("INSERT INTO momusers (steamid, momid) VALUES (?, 177)", (A,))
    c.commit()
    P.enqueue(c, A, NOW)
    bad = [pb(20, 1, 1, 1, 5.0, uid=178),                  # another user's PB
           pb(20, 1, 1, 1, float("nan")), pb(20, 1, 1, 1, float("inf")),
           pb(20, 1, 1, 1, 0.0001), pb(20, 1, 1, 1, 0.0005), pb(20, 1, 1, 1, -3.0),
           pb(20, 1, 1, 1, 2e6), pb(20, 1, 1, 1, 10 ** 400),
           pb(20, 1, 1, 1, True), pb(20, 1, 1, 1, 5.1, style=False),
           pb("20", 1, 1, 1, 5.2), pb(20, True, 1, 1, 5.3), pb(20, 1, 1.0, 1, 5.4),
           dict(pb(20, 1, 1, 1, 5.5), isPB=1)]
    fake = FakeMomentum({}, {177: bad + [pb(20, 1, 1, 1, 7.25)]})
    P.step(c, TRACKED, 1, fake, delay=0, now=NOW)
    check("P1117r1: only the asked user's well-formed PB is filed",
          [tuple(r)[:4] for r in momrows(c, A)], [("surf_utopia", 0, 1, 7250)])
    for label, body in (("not JSON", b"<html>"), ("a list", b"[]"),
                        ("a bool total", b'{"totalCount": true, "data": []}'),
                        ("JSON nested past recursion", b"[" * 200000),
                        ("an id past 2**53", json.dumps({"totalCount": 1, "data": [
                            {"id": 2 ** 53, "steamID": B}]}).encode())):
        c.execute("DELETE FROM momprofiles")
        c.execute("DELETE FROM momusers WHERE steamid=?", (B,))
        c.commit()
        P.enqueue(c, B, NOW)
        P.step(c, TRACKED, 1, lambda url: body, delay=0, now=NOW)
        # P1117 review 4: a reply it cannot read is 'refused' (a day); no usable id is
        # Momentum knowing nobody, 'unknown' (a week).
        check("P1117r1: %s ends the walk, nothing raised" % label,
              (P.status(c, B)["state"],
               c.execute("SELECT COUNT(*) FROM momusers WHERE steamid=?", (B,)).fetchone()[0]),
              ("unknown" if "2**53" in label else "refused", 0))
    c.close()


def case_p1117r2_strikes():
    """A refused walk gives up its turn, and after STRIKES in a row ends."""
    c = db()
    c.execute("INSERT INTO momusers (steamid, momid) VALUES (?, 1), (?, 2)", (A, B))
    c.commit()
    P.enqueue(c, A, NOW)
    P.enqueue(c, B, NOW + 1)
    asked = []

    def get(url):
        asked.append(url.split("userID=")[1].split("&")[0])
        if "userID=1&" in url:
            raise RuntimeError("HTTP 403")
        return json.dumps({"totalCount": 0, "data": []}).encode()
    for tick in range(P.STRIKES + 1):
        try:
            P.step(c, TRACKED, 1, get, delay=0, now=NOW + 10 + tick)
        except RuntimeError:
            pass
        if tick == 0:
            c.execute("UPDATE momprofiles SET state='queued', updated=? WHERE player=?", (NOW + 2, B))
            c.commit()
    check("P1117r2: the refused walk gives the next turn to the other, then ends after STRIKES",
          (asked, P.status(c, A)["state"]), (["1", "2", "1", "1"], "refused"))
    c.close()


def case_steamsync_requeue():
    c = db()
    c.execute("INSERT INTO accounts (steamid, name, created_at, seen_at) VALUES (?, 'Proto', 1, ?)", (A, NOW))
    c.execute("INSERT INTO accounts (steamid, name, created_at, banned_at, seen_at) VALUES (?, 'x', 1, 5, ?)",
              (B, NOW))
    c.commit()
    check("steamsync: a dry run counts the walks due and queues none",
          (steamsync.requeue(c, NOW, False),
           c.execute("SELECT COUNT(*) FROM momprofiles").fetchone()[0]), (2, 0))
    check("...a run queues every unbanned account's KSF and Momentum walk",
          (steamsync.requeue(c, NOW, True),
           [tuple(r) for r in c.execute("SELECT player, state FROM ksfprofiles")],
           [tuple(r) for r in c.execute("SELECT player, state FROM momprofiles")]),
          (2, [(A, "queued")], [(A, "queued")]))
    check("...a walk still queued is not counted again", steamsync.requeue(c, NOW + 5, True), 0)
    c.execute("UPDATE momprofiles SET state='complete', updated=?", (NOW,))
    c.execute("UPDATE ksfprofiles SET state='complete', updated=?", (NOW,))
    c.commit()
    check("...not again within the day", steamsync.requeue(c, NOW + 86399, True), 0)
    check("P1117r3: ...nor within the week, for a finished walk",
          steamsync.requeue(c, NOW + steamsync.DONE_TTL - 1, True), 0)
    check("...and again once the last walk is a week old", steamsync.requeue(c, NOW + steamsync.DONE_TTL, True), 2)
    c.execute("UPDATE momprofiles SET state='limited', updated=?", (NOW,))
    c.execute("UPDATE ksfprofiles SET state='limited', updated=?", (NOW,))
    c.commit()
    check("P1117r3: a walk that stopped short waits only the day", steamsync.requeue(c, NOW + 86400, True), 2)
    c.execute("UPDATE momprofiles SET state='complete', updated=0")
    for i in range(P.MAX_ACTIVE):
        c.execute("INSERT INTO momprofiles (player, momid, cursor, state, asked, updated)"
                  " VALUES (?, 1, 0, 'queued', ?, ?)", ("x%d" % i, NOW, NOW))
    c.commit()
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        steamsync.requeue(c, NOW + 2 * 86400, True)
    check("P1117r1: a walk refused as busy is said, not dropped silently",
          "momprofile busy: %s not queued again" % A in out.getvalue(), True)
    c.close()


def case_p1117r2_requeue_order():
    """steamsync re-queues the account walked longest ago first: a full queue turns over."""
    c = db()
    old, recent = "76561198000000302", "76561198000000301"     # SteamID order would favour `recent`
    for sid in (old, recent):
        c.execute("INSERT INTO accounts (steamid, name, created_at, seen_at) VALUES (?, 'x', 1, ?)", (sid, NOW))
    for sid, upd in ((old, NOW - 5 * 86400), (recent, NOW - 2 * 86400)):
        c.execute("INSERT INTO momprofiles (player, momid, cursor, state, asked, updated)"
                  " VALUES (?, 0, 0, 'limited', 1, ?)", (sid, upd))
        c.execute("INSERT INTO ksfprofiles (player, mode, cursor, state, asked, updated)"
                  " VALUES (?, 0, 1, 'limited', 1, ?)", (sid, upd))
    c.commit()
    with patch.object(P, "MAX_ACTIVE", 1), patch.object(KP, "MAX_ACTIVE", 1), \
            contextlib.redirect_stdout(io.StringIO()):
        steamsync.requeue(c, NOW, True)
    check("P1117r2: with one slot, the account walked longest ago gets it",
          ([tuple(r) for r in c.execute("SELECT player FROM momprofiles WHERE state='queued'")],
           [tuple(r) for r in c.execute("SELECT player FROM ksfprofiles WHERE state='queued'")]),
          ([(old,)], [(old,)]))
    c.close()


def case_p1117r3_recent_accounts_only():
    c = db()
    c.execute("DELETE FROM installs")
    gone, plays = "76561198000000401", "76561198000000402"
    for sid in (gone, plays):
        c.execute("INSERT INTO accounts (steamid, name, created_at, seen_at) VALUES (?, 'x', 1, ?)",
                  (sid, NOW - 40 * 86400))
    c.execute("INSERT INTO installs (steamid, install, pub, first_at, last_at) VALUES (?, 'i', 'k', 1, ?)",
              (plays, NOW - 86400))
    c.commit()
    with contextlib.redirect_stdout(io.StringIO()):
        steamsync.requeue(c, NOW, True)
    check("P1117r3: only accounts signed in or played lately are queued again",
          [tuple(r) for r in c.execute("SELECT player FROM ksfprofiles")], [(plays,)])
    c.execute("DELETE FROM installs")
    c.commit()
    c.close()


def case_p1117r3_requeue_survives_an_error():
    c = db()
    for sid in (A, B):
        c.execute("INSERT INTO accounts (steamid, name, created_at, seen_at) VALUES (?, 'x', 1, ?)", (sid, NOW))
    c.commit()

    def broken(*a, **k):
        raise sqlite3.OperationalError("no such column: strikes")
    out = io.StringIO()
    with patch.object(P, "enqueue", broken), contextlib.redirect_stdout(out):
        steamsync.requeue(c, NOW, True)
    check("P1117r3: one account's Momentum error does not stop the other accounts' KSF walks",
          (sorted(tuple(r) for r in c.execute("SELECT player FROM ksfprofiles")),
           "no such column" in out.getvalue()), ([(A,), (B,)], True))
    c.close()


def case_p1117r3_old_table_gains_strikes():
    c = db()
    c.execute("DROP TABLE momprofiles")
    c.execute("CREATE TABLE momprofiles (player TEXT PRIMARY KEY, momid INTEGER NOT NULL DEFAULT 0,"
              " cursor INTEGER NOT NULL, state TEXT NOT NULL, asked INTEGER NOT NULL,"
              " updated INTEGER NOT NULL, pages INTEGER NOT NULL DEFAULT 0, filed INTEGER NOT NULL DEFAULT 0)")
    c.commit()
    c.close()
    S.migrate()
    c = S.connect()
    check("P1117r3: a momprofiles table from a round-1 build gains strikes, and enqueue works",
          ("strikes" in {r[1] for r in c.execute("PRAGMA table_info(momprofiles)")},
           P.enqueue(c, A, NOW)["state"]), (True, "queued"))
    c.close()


def case_p1117r3_lookup_resets_strikes():
    c = db()
    P.enqueue(c, A, NOW)
    c.execute("UPDATE momprofiles SET strikes=2")
    c.commit()
    P.step(c, TRACKED, 1, FakeMomentum({A: 177}, {}), delay=0, now=NOW + 1)
    check("P1117r3: an answered id lookup clears the strikes",
          tuple(c.execute("SELECT momid, strikes FROM momprofiles WHERE player=?", (A,)).fetchone()), (177, 0))
    c.close()


def case_p1117r4_refused_waits_a_day():
    c = db()
    c.execute("INSERT INTO accounts (steamid, name, created_at, seen_at) VALUES (?, 'x', 1, ?)", (A, NOW))
    c.execute("INSERT INTO momprofiles (player, momid, cursor, state, asked, updated)"
              " VALUES (?, 1, 0, 'refused', 1, ?)", (A, NOW))
    c.execute("INSERT INTO ksfprofiles (player, mode, cursor, state, asked, updated)"
              " VALUES (?, 0, 1, 'unknown', 1, ?)", (A, NOW))
    c.commit()
    check("P1117r4: a refused walk waits a day, a found-nobody one a week",
          (steamsync.requeue(c, NOW + 86400, False), steamsync.requeue(c, NOW + steamsync.DONE_TTL, False)),
          (1, 2))
    c.close()


def case_momwatch_budget():
    c = db()
    c.execute("INSERT INTO momusers (steamid, momid) VALUES (?, 177)", (A,))
    c.commit()
    P.enqueue(c, A, NOW)
    c.close()
    d = tempfile.mkdtemp(prefix="watch-", dir=HOME)
    tsv = os.path.join(d, "momtracks.tsv")
    with io.open(tsv, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("# map\tmapid\ttier\tgamemode\ttrackType\ttrackNum\n"
                 "surf_utopia\t20\t1\t1\t0\t1\nsurf_utopia\t20\t1\t1\t1\t1\n"
                 "surf_utopia\t20\t1\t2\t0\t1\n")
    boards = os.path.join(d, "boards")
    os.makedirs(boards)
    fake = FakeMomentum({}, {177: [pb(20, 1, 1, 1, 5.5), pb(20, 2, 0, 1, 9.0)]
                                 + [pb(999, 1, 0, 1, 1.0)] * 150})
    calls = []
    argv = ["momwatch.py", "--tracks", tsv, "--boards", boards, "--delay", "0",
            "--depth", "-1", "--backfill", "15", "--go"]
    with patch.object(MW.momfetch, "get", fake), patch.object(MW.subprocess, "call",
                                                              lambda cmd: calls.append(cmd) or 0), \
            patch.object(sys, "argv", argv), contextlib.redirect_stdout(io.StringIO()):
        MW.main()
    back = [cmd[cmd.index("--max") + 1] for cmd in calls if "--rewalk" in cmd]
    check("momwatch: a queued walk gets PROFILE_MAX requests of EXTRA_MAX, the backfill the rest",
          (len(fake.asked), back), (MW.PROFILE_MAX, [str(MW.EXTRA_MAX - MW.PROFILE_MAX)]))
    c = S.connect()
    check("...and its rows land on the board, never a surf map's bhop board", [tuple(r)[:4] for r in momrows(c, A)],
          [("surf_utopia", 0, 1, 5500)])
    c.close()
    check("a 404 from Momentum is an empty answer, not a refusal",
          json.loads(profile_404()), {"totalCount": 0, "data": []})


def case_p1142_profile_dates():
    dates = ('1960-01-01T00:00:00Z', '2999-01-01T00:00:00Z', '2026-10-23T09:38:15.836Z')
    got = [P.rows_of([pb(20, 1, 0, 1, 5.0, when=d, uid=177)],
                     A, 'fixture', TRACKED, NOW, 177)[0][-2] for d in dates]
    check('P1142: profile dates use board bounds; valid date remains exact',
          got, [NOW, NOW, 1792748295])


def case_p1142_small_budgets():
    d = tempfile.mkdtemp(prefix='small-budget-', dir=HOME)
    tsv, boards = os.path.join(d, 'tracks.tsv'), os.path.join(d, 'boards')
    os.makedirs(boards)
    with open(tsv, 'w', encoding='utf-8') as f:
        f.write('# map\\tmapid\\ttier\\tgamemode\\ttrackType\\ttrackNum\n'.replace('\\t', '\t'))
        for tt in (0, 1, 2):
            f.write('surf_utopia\t20\t1\t1\t%d\t1\n' % tt)
    stale = ['20_g1_t01', '20_g1_t11', '20_g1_t21']
    for budget in (1, 2, 3):
        c = db()
        c.execute('INSERT INTO momusers (steamid, momid) VALUES (?, 177)', (A,))
        c.commit(); P.enqueue(c, A, NOW); c.close()
        fake, calls = FakeMomentum({}, {177: []}), []
        argv = ['momwatch.py', '--tracks', tsv, '--boards', boards, '--delay', '0',
                '--depth', '-1', '--backfill', str(budget), '--go']
        with patch.object(MW.momfetch, 'get', fake), \
                patch.object(MW, 'stalest_boards', lambda *a: stale[:a[3]]), \
                patch.object(MW, 'live_maps', lambda c: []), \
                patch.object(MW, 'wanted_maps', lambda *a: []), \
                patch.object(MW.subprocess, 'call', lambda cmd: calls.append(cmd) or 0), \
                patch.object(sys, 'argv', argv), contextlib.redirect_stdout(io.StringIO()):
            MW.main()
        c = S.connect()
        total = len(fake.asked) + sum(int(cmd[cmd.index('--max') + 1]) for cmd in calls)
        check('P1142: backlog cannot starve a profile with budget%d; total cap holds' % budget,
              (len(fake.asked), P.status(c, A)['state'], total), (1, 'complete', budget))
        c.close()


def profile_404():
    def nosuch(url):
        raise MW.momfetch.NoSuchBoard("HTTP 404")
    with patch.object(MW.momfetch, "get", nosuch):
        return MW.profile_get("x")


def main():
    try:
        for case in (case_enqueue, case_walk, case_round_robin_refusal_and_shape, case_p1117r1_hostile_rows,
                     case_p1117r2_strikes, case_p1117r2_requeue_order,
                     case_p1117r3_recent_accounts_only, case_p1117r3_requeue_survives_an_error,
                     case_p1117r3_old_table_gains_strikes, case_p1117r3_lookup_resets_strikes,
                     case_p1117r4_refused_waits_a_day,
                     case_steamsync_requeue, case_momwatch_budget,
                     case_p1142_profile_dates, case_p1142_small_budgets):
            print("\n%s:" % case.__name__)
            case()
    finally:
        logging.shutdown()      # the logger holds a file in HOME on Windows
        shutil.rmtree(HOME, ignore_errors=True)
    print("\n%d failed" % len(FAILED))
    for f in FAILED:
        print("  " + f)
    return 1 if FAILED else 0


if __name__ == "__main__":
    raise SystemExit(main())
