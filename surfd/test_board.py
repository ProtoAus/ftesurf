#!/usr/bin/env python3
"""
test_board.py -- the falsifier for surfd's leaderboard (schema 2).

Run it anywhere Flask is installed, against a THROWAWAY home directory:

    SURFD_HOME=/tmp/surfd-test python3 test_board.py

It never touches a live instance: every case re-imports surfd with a fresh
SURFD_HOME, its own DB and its own env file -- the same harness test_surfd.py
uses, and for the same reason.

WHAT IT IS FOR.  The board is the first thing in this tree that stores a claim
about a named person and shows it to everybody else, so the cases that matter
are the ones where it would say something FALSE:

  * a run put on the ranked board by someone who may not write to it (s2),
  * a run filed under the wrong style, which renames what somebody did (s4),
  * a segmented run standing on the clean board, or vice versa (s4, s6),
  * a community run appearing in a ranked list (s5),
  * a slower time replacing a faster one, or a faster one being ignored (s6),
  * two runs ranked by tick count when their tickrates differ, which orders
    them by the wrong quantity entirely (s7),
  * and the one that takes down a feature nobody was touching: a submission
    flood spending the heartbeat's rate budget and blanking the map picker
    (s8).

Section 9 pins the TF_* constants against src/shared/sh_defs.qc itself, because
every classification in this file is arithmetic on that word and a renumber
there would silently re-file every run on the board rather than fail.
"""

import importlib
import json
import os
import re
import sqlite3
import sys
import tempfile

FAILED = []


def check(label, got, want):
    ok = got == want
    print("%-4s %-58s %r" % ("ok" if ok else "FAIL", label, got))
    if not ok:
        FAILED.append("%s: got %r, want %r" % (label, got, want))


def fresh(key="testkey", seed_v1=False):
    """Import surfd with a clean home dir.

    `seed_v1` builds a schema-1 database with a lobby row in it BEFORE the
    import, which is the only way to exercise the 1 -> 2 upgrade: surfd
    migrates at import time, so a database created afterwards is never a v1
    one.  Section 1 uses it to prove the upgrade keeps the lobby directory --
    a migration that quietly dropped it would take every server off the map
    picker on the deploy that shipped the board.
    """
    home = tempfile.mkdtemp(prefix="surfd-board-")
    db = os.path.join(home, "test.db")
    with open(os.path.join(home, "surfd.env"), "w") as fh:
        fh.write("SURFD_KEY=%s\n" % key)

    if seed_v1:
        conn = sqlite3.connect(db)
        conn.executescript(
            """
            CREATE TABLE lobbies (
                node       TEXT    PRIMARY KEY,
                map        TEXT    NOT NULL,
                players    INTEGER NOT NULL,
                maxplayers INTEGER NOT NULL,
                addr       TEXT    NOT NULL,
                name       TEXT    NOT NULL,
                last_seen  INTEGER NOT NULL
            );
            INSERT INTO lobbies VALUES
                ('p27510','surf_legacy',3,32,'10.0.0.1:27510','old',2000000000);
            PRAGMA user_version=1;
            """
        )
        conn.commit()
        conn.close()

    os.environ["SURFD_HOME"] = home
    os.environ["SURFD_DB"] = db
    os.environ["SURFD_ENV"] = os.path.join(home, "surfd.env")
    os.environ.pop("SURFD_PUBLIC_HOST", None)
    os.environ.pop("SURFD_TRUSTED", None)
    sys.modules.pop("surfd", None)
    mod = importlib.import_module("surfd")
    mod._test_home = home
    mod._test_db = db
    return mod


class FakeClock(object):
    """Stands in for `time` inside ONE imported surfd. See test_surfd.py."""

    def __init__(self, now=1800000000.0):
        self.now = float(now)

    def time(self):
        return self.now


def submit(mod, key="testkey", src="127.0.0.1", **kw):
    """POST one run. Returns the parsed body, or 'HTTP nnn'."""
    form = {
        "key": key,
        "map": "surf_test",
        "track": "0",
        "leg": "0",
        "player": "alice",
        "name": "Alice",
        "ticks": "4108",
        "tickrate": "66.666667",
        "flags": "0",
        "node": "p27510",
        "runid": "r1",
    }
    form.update({k: str(v) for k, v in kw.items()})
    form = {k: v for k, v in form.items() if v != "__omit__"}
    resp = mod.app.test_client().post(
        "/api/run", data=form, environ_base={"REMOTE_ADDR": src}
    )
    if resp.status_code == 204:
        return "HTTP 204"
    if resp.status_code != 200:
        return "HTTP %d" % resp.status_code
    return resp.get_json()


def board(mod, src="127.0.0.1", **kw):
    """GET one board page. Returns the parsed body, or 'HTTP nnn'."""
    args = {"map": "surf_test"}
    args.update({k: str(v) for k, v in kw.items()})
    resp = mod.app.test_client().get(
        "/api/board", query_string=args, environ_base={"REMOTE_ADDR": src}
    )
    if resp.status_code != 200:
        return "HTTP %d" % resp.status_code
    return resp.get_json()


def names(body):
    """The player column of a board result, in rank order."""
    if not isinstance(body, dict):
        return body
    return [r["player"] for r in body["rows"]]


def user_version(mod):
    conn = sqlite3.connect(mod._test_db)
    try:
        return conn.execute("PRAGMA user_version").fetchone()[0]
    finally:
        conn.close()


# --------------------------------------------------------------------------
print("\n--- 1. schema -----------------------------------------------------")

m = fresh()
check("a fresh database is stamped schema 2", user_version(m), 2)
check("...and SCHEMA_VERSION agrees", m.SCHEMA_VERSION, 2)
check("an empty board answers with an empty row list", names(board(m)), [])

m = fresh(seed_v1=True)
check("a schema-1 database upgrades to 2", user_version(m), 2)
conn = sqlite3.connect(m._test_db)
kept = conn.execute("SELECT map FROM lobbies").fetchall()
conn.close()
check("...and the upgrade keeps the lobby rows", [r[0] for r in kept],
      ["surf_legacy"])
check("...and the board works on the upgraded db", names(board(m)), [])

# --------------------------------------------------------------------------
print("\n--- 2. who may write ----------------------------------------------")

m = fresh()
check("no key rejected", submit(m, key="__omit__"), "HTTP 403")
check("wrong key rejected", submit(m, key="wrong"), "HTTP 403")
check("empty key rejected", submit(m, key=""), "HTTP 403")
check("the right key is accepted", submit(m)["stored"], True)
check("...and the run is on the board", names(board(m)), ["alice"])

# --------------------------------------------------------------------------
print("\n--- 3. what a submission may say -----------------------------------")

m = fresh()
check("a map name with a slash is refused",
      submit(m, map="surf/../etc"), "HTTP 400")
check("a traversal is refused", submit(m, map=".."), "HTTP 400")
check("a leading dot is refused", submit(m, map=".hidden"), "HTTP 400")
check("an empty map is refused", submit(m, map=""), "HTTP 400")
check("a 65-character map name is refused",
      submit(m, map="a" * 65), "HTTP 400")
check("a 64-character map name is accepted",
      submit(m, map="a" * 64)["stored"], True)
check("a negative track is refused", submit(m, track=-1), "HTTP 400")
check("a negative leg is refused", submit(m, leg=-1), "HTTP 400")
check("a non-numeric leg is refused", submit(m, leg="main"), "HTTP 400")
check("zero ticks is refused", submit(m, ticks=0), "HTTP 400")
check("a negative tick count is refused", submit(m, ticks=-5), "HTTP 400")
check("a zero tickrate is refused (it would divide)",
      submit(m, tickrate=0), "HTTP 400")
check("a NaN tickrate is refused", submit(m, tickrate="nan"), "HTTP 400")
check("an infinite tickrate is refused", submit(m, tickrate="inf"), "HTTP 400")
check("a missing player is refused", submit(m, player=""), "HTTP 400")
check("an unknown tier is refused", submit(m, tier="elite"), "HTTP 400")
check("an unknown style on a read is refused",
      board(m, style="freestyle"), "HTTP 400")
check("a bad map on a read is refused", board(m, map="a/b"), "HTTP 400")

# --------------------------------------------------------------------------
print("\n--- 4. which board a run belongs on ---------------------------------")

m = fresh()
TF_PRACTICE, TF_SHADOW, TF_SEGMENT = 1, 8, 128
TF_CHEAT, TF_NOJOURNAL, TF_NORULESET = 256, 512, 1024

check("flags 0 is clean", m.style_of(0), "clean")
check("TF_SEGMENT is segmented", m.style_of(TF_SEGMENT), "segmented")
check("TF_SHADOW is segmented too (pre-44 files)",
      m.style_of(TF_SHADOW), "segmented")
check("TF_PRACTICE has no board", m.style_of(TF_PRACTICE), None)
check("TF_CHEAT has no board", m.style_of(TF_CHEAT), None)
check("cheat outranks segment, as FS_RunClass does",
      m.style_of(TF_CHEAT | TF_SEGMENT), None)
check("segment outranks practice, as FS_RunClass does",
      m.style_of(TF_SEGMENT | TF_PRACTICE), "segmented")
check("a journal-less run still has a board",
      m.style_of(TF_NOJOURNAL), "clean")
check("a ruleset-less run still has a board",
      m.style_of(TF_NORULESET), "clean")

check("a practice run is stored nowhere, and says so",
      submit(m, flags=TF_PRACTICE), "HTTP 204")
check("a cheated run is stored nowhere",
      submit(m, flags=TF_CHEAT), "HTTP 204")
check("...and neither reached the board", names(board(m)), [])

submit(m, player="clean1", flags=0)
submit(m, player="seg1", flags=TF_SEGMENT, ticks=3000)
check("the clean board holds only the clean run",
      names(board(m, style="clean")), ["clean1"])
check("the segmented board holds only the segmented run",
      names(board(m, style="segmented")), ["seg1"])
check("...and the faster segmented run does NOT undercut the clean board",
      names(board(m, style="clean")), ["clean1"])

# One player, both styles: they are peer achievements and must coexist.
submit(m, player="both", flags=0, ticks=5000)
submit(m, player="both", flags=TF_SEGMENT, ticks=2000)
check("a player may hold a clean PB and a segmented PB at once",
      (names(board(m, style="clean")), names(board(m, style="segmented"))),
      (["clean1", "both"], ["both", "seg1"]))

# --------------------------------------------------------------------------
print("\n--- 5. trust tiers -------------------------------------------------")

m = fresh()
submit(m, player="ranked1", flags=0)
check("a keyed submission is ranked by default",
      names(board(m, tier="ranked")), ["ranked1"])
check("...and is not on the community board",
      names(board(m, tier="community")), [])

submit(m, player="nojrn", flags=TF_NOJOURNAL, ticks=1000)
check("TF_NOJOURNAL is demoted off the ranked board",
      names(board(m, tier="ranked")), ["ranked1"])
check("...and lands on the community board instead",
      names(board(m, tier="community")), ["nojrn"])

submit(m, player="norule", flags=TF_NORULESET, ticks=1001)
check("TF_NORULESET is demoted too",
      names(board(m, tier="community")), ["nojrn", "norule"])

submit(m, player="casual", flags=0, tier="community", ticks=999)
check("a keyed server may ASK for the lower tier",
      names(board(m, tier="community")), ["casual", "nojrn", "norule"])
check("...and asking does not put it on the ranked board",
      names(board(m, tier="ranked")), ["ranked1"])

b = board(m, tier="ranked")
check("the response carries both tiers' counts",
      b["counts"], {"ranked": 1, "community": 3})

# The same player, both tiers: a community run must never displace a ranked
# one, which is what keeping `tier` in the primary key buys.
m = fresh()
submit(m, player="dave", flags=0, ticks=5000)
submit(m, player="dave", flags=0, tier="community", ticks=1)
check("a community time does not overwrite the same player's ranked time",
      [r["ticks"] for r in board(m, tier="ranked")["rows"]], [5000])
check("...and the community row is its own",
      [r["ticks"] for r in board(m, tier="community")["rows"]], [1])

# --------------------------------------------------------------------------
print("\n--- 6. ranking and personal bests ----------------------------------")

m = fresh()
clock = FakeClock()
m.time = clock

submit(m, player="slow", ticks=9000)
clock.now += 10
submit(m, player="fast", ticks=1000)
clock.now += 10
submit(m, player="mid", ticks=5000)
check("rows come back fastest first", names(board(m)), ["fast", "mid", "slow"])
check("...and rank starts at 1",
      [r["r"] for r in board(m)["rows"]], [1, 2, 3])

clock.now += 10
r = submit(m, player="fast", ticks=2000)
check("a SLOWER resubmission is not stored", r["stored"], False)
check("...and reports the standing best", r["best"], 15000)
check("...and the board is unchanged", names(board(m)), ["fast", "mid", "slow"])

r = submit(m, player="fast", ticks=500)
check("a FASTER resubmission is stored", r["stored"], True)
check("...and one player still holds one row", len(board(m)["rows"]), 3)
check("...with the improved time",
      [x["ticks"] for x in board(m)["rows"]], [500, 5000, 9000])

r = submit(m, player="fast", ticks=500)
check("an EQUAL resubmission is not stored (ties keep the earlier claim)",
      r["stored"], False)

# A tie between two players breaks on who got there first.
m = fresh()
clock = FakeClock()
m.time = clock
submit(m, player="first", ticks=3000)
clock.now += 60
submit(m, player="second", ticks=3000)
check("a tie is broken by the earlier submission",
      names(board(m)), ["first", "second"])

# Paging.
m = fresh()
for i in range(10):
    submit(m, player="p%d" % i, ticks=1000 + i)
check("limit caps the page", names(board(m, limit=3)), ["p0", "p1", "p2"])
check("offset pages through it",
      names(board(m, limit=3, offset=3)), ["p3", "p4", "p5"])
check("...and rank survives the offset",
      [r["r"] for r in board(m, limit=3, offset=3)["rows"]], [4, 5, 6])
check("an over-large limit is clamped, not refused",
      len(board(m, limit=99999)["rows"]), 10)

# --------------------------------------------------------------------------
print("\n--- 7. ticks are not a duration ------------------------------------")

# THE CASE THE RANK KEY EXISTS FOR.  4000 ticks at 100 Hz is 40 s; 3000 ticks
# at 50 Hz is 60 s.  Ranked on ticks the 3000 wins, and it is twenty seconds
# slower.  pm_ticrate is locked on a conforming server, but the board must not
# be the thing that assumes it.
m = fresh()
submit(m, player="hz100", ticks=4000, tickrate=100.0)
submit(m, player="hz50", ticks=3000, tickrate=50.0)
check("ranked by duration, not by tick count", names(board(m)),
      ["hz100", "hz50"])
check("...and the durations are the ones arithmetic gives",
      [r["ms"] for r in board(m)["rows"]], [40000, 60000])
check("...while the exact tick counts survive beside them",
      [r["ticks"] for r in board(m)["rows"]], [4000, 3000])

# --------------------------------------------------------------------------
print("\n--- 8. the rate buckets are separate --------------------------------")

# THE FAILURE THIS SECTION EXISTS TO CATCH is not in the board at all: it is
# the map picker going blank because a busy evening of finishes spent the
# heartbeat's budget.  rate_ok keys on the source IP, and every lobby on the
# Pi posts from 127.0.0.1.
m = fresh()
clock = FakeClock()
m.time = clock
now = int(clock.now)

flood = 0
while submit(m, player="p%d" % flood) != "HTTP 429":
    flood += 1
    if flood > m.RUN_RATE_MAX * 3:
        break
check("a submission flood is eventually refused", flood, m.RUN_RATE_MAX)
check("...and a heartbeat from the SAME ip still gets through",
      m.rate_ok("127.0.0.1", now), True)
check("...and so does a board read", board(m) != "HTTP 429", True)

# The control, in this suite's own idiom: a limiter that cannot produce a 429
# proves nothing by not producing one.  Sharing the bucket DOES refuse it.
m = fresh()
shared_refused = False
for i in range(m.RATE_MAX + 5):
    if not m.rate_ok("127.0.0.1", now, m.RATE_MAX, ""):
        shared_refused = True
        break
check("control: one shared bucket does refuse at the cap", shared_refused, True)

# --------------------------------------------------------------------------
print("\n--- 9. the TF_* word is the client's ---------------------------------")

# Every classification above is arithmetic on sh_defs.qc's flags word.  A
# renumber there with no change here would not fail: it would silently re-file
# runs under the wrong style and demote the wrong ones off the ranked board.
QC = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                  "..", "src", "shared", "sh_defs.qc")
m = fresh()

# SKIPPED WHERE THE GAME SOURCE IS NOT, WHICH IS THE DEPLOYMENT.  surfd ships
# to /srv/nvme/surfd on the Pi with no src/ tree beside it, and a check that
# fails there would fail for the wrong reason -- "the constants disagree" when
# the truth is "there is nothing to compare against".  A cross-repo assertion
# has to be able to say "not applicable here" or it trains people to ignore it.
# Absent the file this SKIPS; present and disagreeing, it FAILS.
if not os.path.exists(QC):
    print("skip %-58s %r" % ("sh_defs.qc not beside surfd (deployed copy)",
                             os.path.normpath(QC)))
else:
    with open(QC, "r", errors="replace") as fh:
        src_text = fh.read()
    found = dict(
        (name, int(value))
        for name, value in re.findall(
            r"^#define\s+(TF_[A-Z]+)\s+(\d+)", src_text, re.M
        )
    )
    for const in ("TF_PRACTICE", "TF_SHADOW", "TF_SEGMENT", "TF_CHEAT",
                  "TF_NOJOURNAL", "TF_NORULESET"):
        check("%s matches sh_defs.qc" % const,
              getattr(m, const), found.get(const))

# --------------------------------------------------------------------------
print("\n--- 10. the heartbeat cap scales with a cluster ----------------------")

# THE FAILURE THIS SECTION EXISTS TO CATCH is a map picker that goes blank as
# the cluster gets busy.  Under mapcluster there is one server process per LIVE
# MAP, each running the same QC and so each heartbeating every
# lobby_master_rate (5s) = 12/minute.  RATE_MAX was sized for FIVE lobbies, so
# it caps the cluster at 12 nodes -- below the Pi's own RAM ceiling.


def beat_n(mod, src, nodes, minutes=1, key="testkey"):
    """Play `nodes` servers' heartbeats for `minutes`. Returns refusals."""
    client = mod.app.test_client()
    refused = 0
    for tick in range(int(minutes * 12)):          # 12 beats/node/minute
        for n in range(nodes):
            r = client.post(
                "/api/heartbeat",
                data={"key": key, "node": "n%d" % n, "map": "surf_%d" % n,
                      "players": "0", "max": "32", "port": str(27600 + n),
                      "name": "n%d" % n},
                environ_base={"REMOTE_ADDR": src},
            )
            if r.status_code == 429:
                refused += 1
        mod.time.now += 5.0
    return refused


m = fresh()
m.time = FakeClock()
check("30 cluster nodes from loopback: no beat refused",
      beat_n(m, "127.0.0.1", 30, minutes=2), 0)

m = fresh()
m.time = FakeClock()
check("...and 64 nodes, the planned ceiling, also fit",
      beat_n(m, "127.0.0.1", 64, minutes=1), 0)

# THE CONTROL.  A cap that cannot refuse proves nothing by not refusing: the
# same traffic against the OLD single cap must produce 429s, or the section
# above is measuring nothing.
m = fresh()
m.time = FakeClock()
m.RATE_MAX_TRUSTED = m.RATE_MAX          # pretend the fix was never made
check("control: the same 30 nodes at the old cap ARE refused",
      beat_n(m, "127.0.0.1", 30, minutes=2) > 0, True)

# And the protection that mattered before is untouched: an UNTRUSTED source
# (the public internet) still gets the original 150, not the cluster cap.
m = fresh()
m.time = FakeClock()
check("an untrusted source is still held to the original cap",
      beat_n(m, "203.0.113.9", 30, minutes=2) > 0, True)
check("...and loopback is trusted by default, with no SURFD_TRUSTED set",
      m.is_trusted("127.0.0.1", m.TRUSTED_SOURCES), True)
check("...while a public address is not",
      m.is_trusted("203.0.113.9", m.TRUSTED_SOURCES), False)

# --------------------------------------------------------------------------
print("")
if FAILED:
    print("%d FAILED" % len(FAILED))
    for line in FAILED:
        print("  " + line)
    sys.exit(1)
print("all checks passed")
