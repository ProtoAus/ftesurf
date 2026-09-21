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

Sections 14-17 are schema 5: the 4 -> 5 migration and its race, the `ver`
flag, reject/clear through restand(), and that no verdict, reason or review
reaches a public body.  Section 18 is schema 6: a stage row's `run`, and the
5 -> 6 migration and its race.
"""

import hashlib
import importlib
import json
import os
import re
import sqlite3
import sys
import tempfile
import threading

FAILED = []


def check(label, got, want):
    ok = got == want
    print("%-4s %-58s %r" % ("ok" if ok else "FAIL", label, got))
    if not ok:
        FAILED.append("%s: got %r, want %r" % (label, got, want))


def fresh(key="testkey", seed_v1=False, seed=None):
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
    if seed is not None:
        seed(db)

    os.environ["SURFD_HOME"] = home
    os.environ["SURFD_DB"] = db
    os.environ["SURFD_ENV"] = os.path.join(home, "surfd.env")
    # The run tree too, or section 19's recordings land in the default -- the
    # LIVE lobbies' data/runs on the Pi (they did, 2026-09-20/21: surf_test).
    os.environ["SURFD_RUNS"] = os.path.join(home, "runs")
    os.makedirs(os.environ["SURFD_RUNS"], exist_ok=True)
    for k in ("SURFD_EVIDENCE", "SURFD_KEEP"):
        os.environ.pop(k, None)
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

    def monotonic(self):                 # map_index() reads this one
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
# Pinned as a literal so a schema bump is a conscious act: bump this with
# surfd.SCHEMA_VERSION (6 -> 7 went unbumped here for a day).
HEAD_SCHEMA = 8

print("\n--- 1. schema -----------------------------------------------------")

m = fresh()
check("a fresh database is stamped the head schema", user_version(m), HEAD_SCHEMA)
check("...and SCHEMA_VERSION agrees", m.SCHEMA_VERSION, HEAD_SCHEMA)
check("an empty board answers with an empty row list", names(board(m)), [])

m = fresh(seed_v1=True)
check("a schema-1 database upgrades to the head", user_version(m), HEAD_SCHEMA)
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

# The two demotions that had no falsifier: build 72's TF_NOPROFILE and build
# 73's TF_NOMAP.  Both were added to certifiable() and neither was tested, which
# for a demotion is the expensive direction to miss -- a bit that is recorded,
# archived and reported but never ACTED on looks exactly like a bit that works,
# from every side except the board itself.
#
# ITS OWN FIXTURE, not section 5's.  Appending two rows to that one moved four
# later expectations that count rows, so the first version of this block failed
# tests it had not touched.  A fresh module is free and cannot reach them.
m = fresh()
submit(m, player="ranked1", flags=0, ticks=900)
submit(m, player="noprof", flags=m.TF_NOPROFILE, ticks=1002)
check("TF_NOPROFILE is demoted off the ranked board",
      names(board(m, tier="community")), ["noprof"])

submit(m, player="nomap", flags=m.TF_NOMAP, ticks=1003)
check("TF_NOMAP is demoted too",
      names(board(m, tier="community")), ["noprof", "nomap"])
check("...and neither reached the ranked board",
      names(board(m, tier="ranked")), ["ranked1"])

# Build 76's TF_NOCLOCK, tested here for the reason the two above were: a
# demotion with no falsifier looks identical to a demotion that works, from
# everywhere except the board.  This one is the likeliest of the five to be
# reached by an operator rather than a player -- it fires when the engine and the
# QC are deployed out of order -- so the row it produces is the diagnostic.
submit(m, player="noclock", flags=m.TF_NOCLOCK, ticks=1005)
check("TF_NOCLOCK is demoted off the ranked board",
      names(board(m, tier="community")), ["noprof", "nomap", "noclock"])
check("...and the ranked board is still only the clean row",
      names(board(m, tier="ranked")), ["ranked1"])

# Patch 406's TF_NOCOUNTS, for the same reason: the client sent cursor data
# instead of Patch 376 mouse counts (cl_prydoncursor).  The sixth bit, and the
# only one that describes something the player had to do -- it still only
# demotes, because a quiet gate survives a false negative and an accusation
# does not.
submit(m, player="nocount", flags=m.TF_NOCOUNTS, ticks=1007)
check("TF_NOCOUNTS is demoted off the ranked board",
      names(board(m, tier="community")), ["noprof", "nomap", "noclock", "nocount"])
check("...and certifiable() refuses it on its own",
      (m.certifiable(m.TF_NOCOUNTS), m.certifiable(0)), (False, True))
check("...and the ranked board is STILL only the clean row",
      names(board(m, tier="ranked")), ["ranked1"])

# THE CONTROL.  The demotion has to be caused by the BIT and not by anything the
# two demoted rows happen to share -- a slower time, a later arrival, the same
# key.  Identical shape, flags 0, and it ranks.
submit(m, player="clean2", flags=0, ticks=1004)
check("a clean run arriving last, and slowest, still ranks",
      names(board(m, tier="ranked")), ["ranked1", "clean2"])

# Multi-Session (sv_resume.qc): the bit is display only.  It must neither demote
# a clean run nor mask a demotion or a refusal -- a controls on all three.
m = fresh()
check("TF_MULTISESSION alone is clean", m.style_of(m.TF_MULTISESSION), "clean")
check("...and certifiable", m.certifiable(m.TF_MULTISESSION), True)
check("...|TF_SEGMENT is still segmented",
      m.style_of(m.TF_MULTISESSION | m.TF_SEGMENT), "segmented")
submit(m, player="multi", flags=m.TF_MULTISESSION, ticks=1000)
b = board(m, tier="ranked")
check("a Multi-Session run ranks", names(b), ["multi"])
check("...and its row keeps the bit",
      b["rows"][0]["flags"] if isinstance(b, dict) else b, m.TF_MULTISESSION)
submit(m, player="msjrn", flags=m.TF_MULTISESSION | m.TF_NOJOURNAL, ticks=1001)
check("...|TF_NOJOURNAL is still demoted",
      names(board(m, tier="community")), ["msjrn"])
check("...|TF_CHEAT is still refused",
      submit(m, player="mscheat", flags=m.TF_MULTISESSION | m.TF_CHEAT), "HTTP 204")

# Patch 382: TF_SPEC is a marker like TF_MULTISESSION -- a spectated run stays
# ranked, and the bit masks neither a demotion nor a refusal.
m = fresh()
check("TF_SPEC alone is clean", m.style_of(m.TF_SPEC), "clean")
check("...and certifiable", m.certifiable(m.TF_SPEC), True)
check("...|TF_SEGMENT is still segmented",
      m.style_of(m.TF_SPEC | m.TF_SEGMENT), "segmented")
submit(m, player="spec", flags=m.TF_SPEC, ticks=1000)
b = board(m, tier="ranked")
check("a spectated run ranks", names(b), ["spec"])
check("...and its row keeps the bit",
      b["rows"][0]["flags"] if isinstance(b, dict) else b, m.TF_SPEC)
submit(m, player="specjrn", flags=m.TF_SPEC | m.TF_NOJOURNAL, ticks=1001)
check("...|TF_NOJOURNAL is still demoted",
      names(board(m, tier="community")), ["specjrn"])
check("...|TF_CHEAT is still refused",
      submit(m, player="speccheat", flags=m.TF_SPEC | m.TF_CHEAT), "HTTP 204")

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
m.RUN_RATE_MAX_TRUSTED = m.RUN_RATE_MAX   # loopback is trusted; section 12 covers that cap

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
    # TF_NOPROFILE was added to surfd by build 72 and never added HERE, so the
    # one constant most likely to be renumbered next was the one constant this
    # cross-repo pin did not cover.  Both it and build 73's TF_NOMAP are listed
    # now; the list is the point of the section, so an addition that skips it
    # silently loses the guarantee for exactly the newest value.
    for const in ("TF_PRACTICE", "TF_SHADOW", "TF_SEGMENT", "TF_CHEAT",
                  "TF_NOJOURNAL", "TF_NORULESET", "TF_NOPROFILE", "TF_NOMAP",
                  "TF_NOCLOCK", "TF_MULTISESSION", "TF_SPEC"):
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
# 11. BEHIND THE REVERSE PROXY.
#
# /api/board is the first rate-limited route to be reachable from the internet,
# and it arrives through nginx on loopback -- so request.remote_addr is
# 127.0.0.1 for every player alive.  Keying the limiter on that collapses a
# per-IP 120/min into ONE bucket shared by the whole game, which a single
# stranger at 2 req/s can spend: strictly worse than the 404 it replaced.
#
# THIS SECTION EXISTS BECAUSE NOTHING ELSE IN EITHER SUITE SENDS A PROXY HEADER.
# The bug it guards is invisible to every other case here -- they all speak to
# surfd directly, which is exactly how the 404 that started this shipped: the
# endpoint was only ever exercised on the one path no player takes.
#
# The security half matters as much as the rate half.  X-Real-IP is believed
# ONLY from an address in SURFD_PROXIES; believed from anywhere, every client
# could choose its own limiter identity and the limiter would be decorative.
print("\n-- 11. behind the reverse proxy --")


def board_via(mod, peer, real_ip=None):
    """GET a board as nginx would relay it: peer is the proxy, the header is
    the player.  real_ip=None sends no header at all."""
    headers = {}
    if real_ip is not None:
        headers["X-Real-IP"] = real_ip
    return mod.app.test_client().get(
        "/api/board", query_string={"map": "surf_test"}, headers=headers,
        environ_base={"REMOTE_ADDR": peer},
    ).status_code


def flood(mod, peer, real_ip, n):
    """n board reads; returns how many were refused."""
    return sum(1 for _ in range(n) if board_via(mod, peer, real_ip) == 429)


m = fresh()
m.RUN_RATE_MAX = 5           # small enough to exhaust in a few requests

# The fix itself: two players behind one proxy are two buckets, not one.
check("proxy: player A exhausts their own board budget",
      flood(m, "127.0.0.1", "198.51.100.7", 8) > 0, True)
check("...and player B, same proxy, is UNAFFECTED",
      flood(m, "127.0.0.1", "198.51.100.8", 4), 0)

# The control that proves the check above measures something.  With no header
# there is nothing to separate them by, so the same traffic must now be refused
# -- this is the collapsed-bucket bug itself, reproduced deliberately.
m = fresh()
m.RUN_RATE_MAX = 5
check("control: with NO X-Real-IP the same two players share one bucket",
      flood(m, "127.0.0.1", None, 8) > 0 and flood(m, "127.0.0.1", None, 4) > 0,
      True)

# The security half: a claim from an address that is not one of our proxies is
# ignored, so a public caller cannot pick a fresh identity per request.
m = fresh()
m.RUN_RATE_MAX = 5
check("an untrusted peer's X-Real-IP is IGNORED (no evasion)",
      flood(m, "203.0.113.9", "198.51.100.1", 4) +
      flood(m, "203.0.113.9", "198.51.100.2", 4) > 0, True)

# Junk in the header falls back to the peer rather than becoming a table key.
m = fresh()
m.RUN_RATE_MAX = 5
check("a non-address X-Real-IP falls back to the peer",
      flood(m, "127.0.0.1", "not-an-ip", 8) > 0, True)
with m.app.test_request_context("/api/board",
                                headers={"X-Real-IP": "not-an-ip"},
                                environ_base={"REMOTE_ADDR": "127.0.0.1"}):
    check("...and rate_key() returns the peer for it", m.rate_key(), "127.0.0.1")
with m.app.test_request_context("/api/board",
                                headers={"X-Real-IP": "198.51.100.4"},
                                environ_base={"REMOTE_ADDR": "127.0.0.1"}):
    check("...and the player's address for a good one",
          m.rate_key(), "198.51.100.4")

# SURFD_PROXIES must NOT become SURFD_TRUSTED.  The trusted list contains whole
# private ranges by default; if the header were believed from those, every
# machine on the LAN could forge its own limiter identity.
check("SURFD_PROXIES defaults to loopback only, unlike SURFD_TRUSTED",
      [str(n) for n in m.PROXY_SOURCES], ["127.0.0.1/32", "::1/128"])
check("...so a LAN address is trusted but is NOT a proxy",
      (m.is_trusted("192.168.1.50", m.TRUSTED_SOURCES),
       m.is_trusted("192.168.1.50", m.PROXY_SOURCES)), (True, False))

# And the invariant the whole vhost design rests on: the HEARTBEAT still reads
# the socket peer, so a proxied heartbeat would still advertise the proxy --
# which is why it is kept off the public vhost.  Nothing above may change this.
m = fresh()
m.app.test_client().post(
    "/api/heartbeat",
    data={"key": "testkey", "node": "p1", "map": "surf_test",
          "players": "0", "max": "32", "port": "27510", "name": "n"},
    headers={"X-Real-IP": "198.51.100.9"},
    environ_base={"REMOTE_ADDR": "127.0.0.1"},
)
rows = json.loads(m.app.test_client().get("/lobbies.json").data)["lobbies"]
check("heartbeat still derives its address from the PEER, not X-Real-IP",
      [l.get("addr", "") for l in rows], ["127.0.0.1:27510"])

# --------------------------------------------------------------------------
print("\n--- 11. the rank a submitter is told ---------------------------------")

# WHAT THIS SECTION IS FOR.  /api/run now answers with the run's position, and
# the game prints that number to the person who just finished and draws it on
# the finish card.  There are therefore TWO pieces of code that decide where a
# run stands -- the COUNT in rank_of and the ORDER BY in /api/board -- and the
# failure they can produce together is the worst kind available here: the game
# says "#3 of 17", the player opens the board to look, and they are fourth.
# Nothing errors, nothing is logged, and the player is simply told a falsehood
# about their own run.
#
# So the falsifier is not "is the rank plausible" but "does it EQUAL what the
# board shows", asserted for every player on a board after every kind of
# submission.  agree() below is that check and it is the point of the section.


def rank_on_board(mod, player, **kw):
    """The rank /api/board gives `player`, or 0 if it does not list them."""
    body = board(mod, limit=200, **kw)
    if not isinstance(body, dict):
        return body
    for row in body["rows"]:
        if row["player"] == player:
            return row["r"]
    return 0


def agree(mod, label, player, reply, **kw):
    """Assert the reply's rank/of is exactly what the board says."""
    shown = rank_on_board(mod, player, **kw)
    total = len(board(mod, limit=200, **kw)["rows"])
    check(label, (reply.get("rank"), reply.get("of")), (shown, total))


m = fresh()
clock = FakeClock()
m.time = clock

r = submit(m, player="alice", ticks=4000)
check("the first run on a board is told it is first", (r["rank"], r["of"]),
      (1, 1))

clock.now += 10
r = submit(m, player="bob", ticks=3000)
check("a faster second run is told #1 of 2", (r["rank"], r["of"]), (1, 2))
agree(m, "...and the board agrees about bob", "bob", r)

clock.now += 10
r = submit(m, player="carol", ticks=5000)
check("a slower third run is told #3 of 3", (r["rank"], r["of"]), (3, 3))
agree(m, "...and the board agrees about carol", "carol", r)

# THE CASE THAT PAYS FOR THE `prev` BRANCH.  A run that does not improve still
# has a standing row, and the number the player wants is where they stand --
# which did not move.  Reporting the SLOWER run's hypothetical rank here would
# tell a player they had dropped to last by running a worse practice attempt.
clock.now += 10
r = submit(m, player="bob", ticks=9000)
check("a non-improving run is not stored", r["stored"], False)
check("...and is told the STANDING row's rank, not the slow run's",
      (r["rank"], r["of"]), (1, 3))
agree(m, "...which is what the board shows", "bob", r)

clock.now += 10
r = submit(m, player="carol", ticks=1000)
check("an improving run is told its new rank", (r["rank"], r["of"]), (1, 3))
agree(m, "...and the board agrees after the move", "carol", r)
check("...and the run it displaced moved down",
      rank_on_board(m, "bob"), 2)

# TIES, WHICH ARE THE REASON BOARD_ORDER GREW A THIRD COLUMN.  `submitted` is
# whole seconds, so two equal times filed in the same second compare equal on
# millis AND on submitted.  Before the `player` tiebreak the order was whatever
# SQLite felt like returning -- not stable between two calls of the SAME query,
# which meant rank_of could not agree with a list that did not agree with
# itself, and LIMIT/OFFSET paging across the tie could show one row twice and
# skip another.
m = fresh()
clock = FakeClock()
m.time = clock
submit(m, player="zoe", ticks=3000)
submit(m, player="adam", ticks=3000)         # same second, same time, exactly
submit(m, player="mike", ticks=3000)
check("an exact tie inside one second is ordered stably",
      names(board(m)), ["adam", "mike", "zoe"])
check("...the same way when asked again", names(board(m)),
      ["adam", "mike", "zoe"])
for who, want in (("adam", 1), ("mike", 2), ("zoe", 3)):
    r = submit(m, player=who, ticks=3000)     # equal: not stored, ranks the row
    check("...and %s is told %d, which is what the board shows" % (who, want),
          (r["rank"], rank_on_board(m, who)), (want, want))

# Paging across the tie: with a non-total order this is where a row gets
# duplicated or lost.  Three equal rows, one per page.
seen = []
for off in range(3):
    seen += names(board(m, limit=1, offset=off))
check("...and paging one row at a time visits each exactly once",
      sorted(seen), ["adam", "mike", "zoe"])

# TIERS ARE SEPARATE BOARDS, so a community run must not inflate the field the
# ranked submitter is told they beat.  Sharing `of` across tiers would let
# anybody with an unkeyed server change every ranked player's displayed field.
m = fresh()
m.time = FakeClock()
submit(m, player="ranked1", ticks=4000)
submit(m, player="comm1", ticks=1000, tier="community")
r = submit(m, player="ranked2", ticks=5000)
check("a community run does not appear in a ranked field size",
      (r["rank"], r["of"]), (2, 2))
check("...and does not outrank a ranked run despite being faster",
      names(board(m)), ["ranked1", "ranked2"])
agree(m, "...and the ranked board agrees", "ranked2", r)

# The community board ranks on its own terms.
r = submit(m, player="comm2", ticks=2000, tier="community")
check("the community board ranks within itself",
      (r["rank"], r["of"]), (2, 2))
agree(m, "...and its board agrees", "comm2", r, tier="community")

# STYLES ARE SEPARATE BOARDS TOO -- the same argument, one level down.  A
# segmented run standing in a clean field would tell every clean runner they
# are one place further down than they are.
m = fresh()
m.time = FakeClock()
submit(m, player="clean1", ticks=4000)
submit(m, player="seg1", ticks=1000, flags=str(128))        # TF_SEGMENT
r = submit(m, player="clean2", ticks=5000)
check("a segmented run does not count in the clean field",
      (r["rank"], r["of"]), (2, 2))
agree(m, "...and the clean board agrees", "clean2", r)

# A RUN WITH NO BOARD CARRIES NO RANK AT ALL.  204 already means "understood,
# stored nothing"; attaching a number to it would be a rank on a board the run
# is not on, and the client draws exactly that distinction.
m = fresh()
m.time = FakeClock()
check("a cheated run is still 204 and carries no rank",
      submit(m, player="x", flags=str(256)), "HTTP 204")

# The rank must survive a per-leg split: leg 2's board is not leg 0's.
m = fresh()
m.time = FakeClock()
submit(m, player="a", ticks=4000, leg=0)
submit(m, player="b", ticks=1000, leg=0)
r = submit(m, player="a", ticks=9000, leg=2)
check("a stage board is ranked independently of the full run",
      (r["rank"], r["of"]), (1, 1))
agree(m, "...and that stage board agrees", "a", r, leg=2)

# --------------------------------------------------------------------------
print("\n--- 12. the reply says which board, and what stood before ----------")

# The client tells a demoted player "unranked: <reason>" from `tier`, and draws
# the delta against the standing row from `prevms`.  Without `tier` a demoted
# run would read as "#1 of 1" on a board the player never sees.
m = fresh()
m.time = FakeClock()
r = submit(m, player="c", flags=0, ticks=2000)
check("control: a clean first run lands on ranked, no standing row",
      (r["tier"], r["prevms"], r["stored"]), ("ranked", 0, True))
r = submit(m, player="d", flags=m.TF_NOJOURNAL, ticks=2000)
check("a TF_NOJOURNAL run says it landed on community",
      (r["tier"], r["stored"]), ("community", True))
r = submit(m, player="d", flags=m.TF_NOJOURNAL, ticks=2100)
check("...a slower resubmit: not stored, prevms is the standing 30000 ms",
      (r["tier"], r["stored"], r["prevms"]), ("community", False, 30000))
r = submit(m, player="c", flags=0, ticks=1800)
check("a faster ranked resubmit: stored, prevms is the row it replaced",
      (r["tier"], r["stored"], r["prevms"]), ("ranked", True, 30000))

# --------------------------------------------------------------------------
print("\n--- 13. stage legs get their own run bucket and row cap -------------")

# Main runs post every primed stage they pass, so stage posts from loopback
# multiply.  They must never spend leg 0's budget, and a trusted node gets the
# cluster-sized cap while the internet keeps RUN_RATE_MAX.
m = fresh()
m.time = FakeClock()
m.RUN_RATE_MAX_TRUSTED = 20
n = 0
while submit(m, player="s%d" % n, leg=2) != "HTTP 429":
    n += 1
    if n > 100:
        break
check("a stage-leg flood is refused at the trusted cap", n, 20)
check("...and a main-run post from the same ip still stores",
      submit(m, player="main1", leg=0)["stored"], True)

m = fresh()
m.time = FakeClock()
m.RUN_RATE_MAX_TRUSTED = 20
n = 0
while submit(m, player="t%d" % n, leg=0) != "HTTP 429":
    n += 1
    if n > 100:
        break
check("control: a leg-0 flood does refuse leg 0", n, 20)
check("...and leg=00 is leg 0's bucket, not a second budget",
      submit(m, player="t00", leg="00"), "HTTP 429")

m = fresh()
m.time = FakeClock()
refused = 0
for i in range(12 * 30):                   # 12 lobbies x 30 stage posts, one minute
    if submit(m, player="u%d" % (i % 12), leg=1 + i % 5,
              ticks=1000 + i) == "HTTP 429":
        refused += 1
check("12 lobbies x 30 stage posts a minute from loopback: none refused",
      refused, 0)
m = fresh()
m.time = FakeClock()
m.RUN_RATE_MAX_TRUSTED = m.RUN_RATE_MAX          # pretend the fix was never made
refused = 0
for i in range(12 * 30):
    if submit(m, player="u%d" % (i % 12), leg=1 + i % 5,
              ticks=1000 + i) == "HTTP 429":
        refused += 1
check("control: the same traffic at the old cap IS refused", refused > 0, True)

m = fresh()
m.time = FakeClock()
n = 0
while submit(m, src="203.0.113.9", player="x%d" % n, leg=3) != "HTTP 429":
    n += 1
    if n > m.RUN_RATE_MAX * 3:
        break
check("an untrusted source is still held to RUN_RATE_MAX", n, m.RUN_RATE_MAX)

m = fresh()
m.time = FakeClock()
m.MAX_STAGE_RUNS = 2
submit(m, player="a", leg=1)
submit(m, player="b", leg=2)
check("the stage row cap refuses a third stage row",
      submit(m, player="c", leg=3), "HTTP 429")
check("...and does not touch main rows",
      submit(m, player="c", leg=0)["stored"], True)
m = fresh()
m.time = FakeClock()
r = submit(m, player="e", leg=2)
check("a leafless stage row stores with rep 0", (r["stored"], r["rep"]), (True, 0))

# --------------------------------------------------------------------------
print("\n--- 14. schema 5: the 4 -> 5 migration, and its race --------------")

# A live v4 database: steps 1-4 plus the table sweep.py created on its own.
V4 = """
CREATE TABLE lobbies (node TEXT PRIMARY KEY, map TEXT NOT NULL,
    players INTEGER NOT NULL, maxplayers INTEGER NOT NULL, addr TEXT NOT NULL,
    name TEXT NOT NULL, last_seen INTEGER NOT NULL);
CREATE TABLE runs (map TEXT NOT NULL, track INTEGER NOT NULL,
    leg INTEGER NOT NULL, tier TEXT NOT NULL, style TEXT NOT NULL,
    player TEXT NOT NULL, name TEXT NOT NULL, ticks INTEGER NOT NULL,
    tickrate REAL NOT NULL, millis INTEGER NOT NULL, flags INTEGER NOT NULL,
    node TEXT NOT NULL, runid TEXT NOT NULL, submitted INTEGER NOT NULL,
    replay_id INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (map, track, leg, tier, style, player));
CREATE INDEX runs_board ON runs (map, track, leg, tier, style, millis, submitted);
CREATE TABLE replays (id INTEGER PRIMARY KEY AUTOINCREMENT, map TEXT NOT NULL,
    map_dir TEXT NOT NULL, track INTEGER NOT NULL, leg INTEGER NOT NULL,
    leaf TEXT NOT NULL, tier TEXT NOT NULL, style TEXT NOT NULL,
    player TEXT NOT NULL, name TEXT NOT NULL, ticks INTEGER NOT NULL,
    tickrate REAL NOT NULL, millis INTEGER NOT NULL, flags INTEGER NOT NULL,
    node TEXT NOT NULL, submitted INTEGER NOT NULL,
    bytes INTEGER NOT NULL DEFAULT -1, truncated INTEGER NOT NULL DEFAULT 0,
    seen INTEGER NOT NULL DEFAULT -1, checked INTEGER NOT NULL DEFAULT 0,
    UNIQUE (map, track, leg, leaf));
CREATE INDEX replays_player ON replays (map, track, leg, tier, style, player,
    millis, submitted);
CREATE INDEX replays_sweep ON replays (checked, id);
CREATE TABLE assignments (node TEXT PRIMARY KEY, map TEXT NOT NULL,
    map_dir TEXT NOT NULL, asked_at INTEGER NOT NULL, src TEXT NOT NULL);
CREATE INDEX assignments_map ON assignments (map, asked_at);
CREATE TABLE verdicts (id INTEGER PRIMARY KEY AUTOINCREMENT,
    replay_id INTEGER NOT NULL, verdict TEXT NOT NULL, reason TEXT NOT NULL,
    ticks INTEGER NOT NULL DEFAULT -1, engine TEXT NOT NULL,
    progs TEXT NOT NULL, at INTEGER NOT NULL);
CREATE INDEX verdicts_replay ON verdicts (replay_id, id);
INSERT INTO runs VALUES ('surf_test',0,0,'ranked','clean','old','Old',
    4108,100.0,41080,0,'p27510','',1700000000,1);
INSERT INTO replays (map, map_dir, track, leg, leaf, tier, style, player, name,
    ticks, tickrate, millis, flags, node, submitted, seen, checked)
    VALUES ('surf_test','surf_test',0,0,'0004108_run.rec','ranked','clean',
    'old','Old',4108,100.0,41080,0,'p27510',1700000000,1700000100,1);
INSERT INTO verdicts (replay_id, verdict, reason, ticks, engine, progs, at)
    VALUES (1,'REFUSE','an old format',-1,'e0','p0',1700000100);
PRAGMA user_version=4;
"""


def seed_v4(path):
    # WAL, as the live file is (header bytes 18-19 read 2 2 on the Pi).  From
    # rollback mode, two connect()s racing to switch it lose with "database is
    # locked" in connect() itself, before migrate() runs.
    conn = sqlite3.connect(path)
    conn.executescript(V4)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.commit()
    conn.close()


def q(mod, sql, args=()):
    conn = sqlite3.connect(mod._test_db)
    try:
        return [tuple(r) for r in conn.execute(sql, args).fetchall()]
    finally:
        conn.close()


def objects(path):
    conn = sqlite3.connect(path)
    try:
        names = {r[0] for r in conn.execute("SELECT name FROM sqlite_master")}
        cols = [r[1] for r in conn.execute("PRAGMA table_info(replays)")]
        return names, cols, conn.execute("PRAGMA user_version").fetchone()[0]
    finally:
        conn.close()


m = fresh(seed=seed_v4)
check("a v4 database upgrades to the head", user_version(m), HEAD_SCHEMA)
check("...keeping sweep's verdict row",
      q(m, "SELECT replay_id, verdict, reason, at FROM verdicts"),
      [(1, "REFUSE", "an old format", 1700000100)])
check("...and the runs and replays rows",
      (q(m, "SELECT player, millis, replay_id FROM runs"),
       q(m, "SELECT id, leaf, checked FROM replays")),
      ([("old", 41080, 1)], [(1, "0004108_run.rec", 1)]))
names_, cols, _ = objects(m._test_db)
check("...gaining reviews and the runs_replay index",
      ("reviews" in names_, "runs_replay" in names_), (True, True))
check("...and replays.recheck_at, 0 for the old row",
      ("recheck_at" in cols, q(m, "SELECT recheck_at FROM replays")),
      (True, [(0,)]))
check("...and the old REFUSE row reads plain on the board",
      [(r["player"], r["ver"]) for r in board(m)["rows"]], [("old", 0)])

conn = sqlite3.connect(m._test_db)
conn.execute("PRAGMA user_version=4")
conn.commit()
conn.close()
try:
    m.migrate()
    rerun = "ok"
except Exception as exc:                     # the failure being tested for
    rerun = repr(exc)
check("re-running step 5 over a finished step 5 does not raise", rerun, "ok")
check("...and stamps the head again", user_version(m), HEAD_SCHEMA)


class RacingConn(object):
    """A connection whose ALTER is beaten to it by another process."""

    def __init__(self, real, path, needle="ADD COLUMN recheck_at"):
        self._real, self._path, self._needle = real, path, needle
        self.raced = False

    def execute(self, sql, *args):
        if self._needle in sql:
            other = sqlite3.connect(self._path)
            other.execute(sql)
            other.commit()
            other.close()
            self.raced = True
        return self._real.execute(sql, *args)

    def __getattr__(self, name):
        return getattr(self._real, name)


def migrate_file(mod, path, conn_factory=None):
    """Run mod.migrate() against another database file."""
    real_path, real_connect = mod.DB_PATH, mod.connect
    mod.DB_PATH = path
    if conn_factory is not None:
        mod.connect = lambda: conn_factory(real_connect())
    try:
        mod.migrate()
        return "ok"
    except Exception as exc:
        return repr(exc)
    finally:
        mod.DB_PATH, mod.connect = real_path, real_connect


race_db = os.path.join(m._test_home, "race.db")
seed_v4(race_db)
seen = []


def racing(real):
    rc = RacingConn(real, race_db)
    seen.append(rc)
    return rc


check("another process adding recheck_at between the check and the ALTER",
      migrate_file(m, race_db, racing), "ok")
check("...really raced (control)", any(rc.raced for rc in seen), True)
names_, cols, ver = objects(race_db)
check("...leaves one recheck_at, reviews, and the head schema",
      (cols.count("recheck_at"), "reviews" in names_, ver), (1, True, HEAD_SCHEMA))
conn = sqlite3.connect(race_db)
try:
    conn.execute("ALTER TABLE replays ADD COLUMN recheck_at INTEGER")
    dup = "no error"
except sqlite3.OperationalError as exc:
    dup = str(exc)
conn.close()
check("control: SQLite's error for the lost race is the tolerated one",
      "duplicate column" in dup, True)

# Two threads migrating one v4 file at once, released by a barrier.
errors = []
steps = []                                      # "migrated 4 -> 6" per round
real_path = m.DB_PATH
m.log.info =lambda msg, *a, **k: steps.append((n, msg % a))
try:
    for n in range(20):
        path = os.path.join(m._test_home, "thr%d.db" % n)
        seed_v4(path)
        m.DB_PATH = path
        gate = threading.Barrier(2)

        def worker(gate=gate):
            try:
                gate.wait()
                m.migrate()
            except Exception as exc:
                errors.append(repr(exc))
        threads = [threading.Thread(target=worker) for _ in range(2)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        names_, cols, ver = objects(path)
        if (cols.count("recheck_at"), "reviews" in names_, ver) != (1, True, HEAD_SCHEMA):
            errors.append("round %d: %r" % (n, (cols.count("recheck_at"), ver)))
finally:
    m.DB_PATH = real_path
    del m.log.info                              # back to Logger.info
both = sum(1 for k in range(20)
           if sum(1 for r, s in steps if r == k and "migrated 4 -> " in s) == 2)
print("     (both threads ran step 5 in %d of 20 rounds)" % both)
check("two threads migrating one v4 file, 20 rounds: no error", errors, [])
# Real overlap is luck, and a round-2 reviewer saw this fail at HEAD and its
# parent alike; the RacingConn arm above is the deterministic race.
if both:
    check("control: in some round both threads really ran step 5", both > 0, True)
else:
    print("skip threads never overlapped in step 5 this run -- see the RacingConn arm")

# --------------------------------------------------------------------------
print("\n--- 15. the VERIFIED flag (`ver`) ---------------------------------")


def leaf(ticks, player):
    return "%07d_%s_run.rec" % (ticks, hashlib.sha256(player.encode()).hexdigest()[:8])


def run(mod, player, ticks, rec=True, **kw):
    """Submit at tickrate 100 (ms = ticks * 10); returns the reply."""
    if rec:
        kw["rec"] = leaf(ticks, player)
    return submit(mod, player=player, name=player.capitalize(), ticks=ticks,
                  tickrate=100, **kw)


def tie_rec(mod, player, ticks, runid):
    """The file a second run leaves under the same leaf (an exact tie writes it
    before it files): a held replay changes only against its file (425)."""
    d = os.path.join(mod.RUNS_DIR, "surf_test", "main")
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, leaf(ticks, player)), "w", encoding="utf-8",
              newline="\n") as fh:
        fh.write("FTESURF-REC 9\nmap surf_test\ntrack 0\nleg 0\nrunid %s\n"
                 "tickrate 0.01\nbegin\nend %d 0 0 0 0 0 0 0 0 0 1\n" % (runid, ticks))


def add_verdict(mod, rid, verdict, at, reason="r"):
    conn = sqlite3.connect(mod._test_db)
    conn.execute("INSERT INTO verdicts (replay_id, verdict, reason, ticks,"
                 " engine, progs, at) VALUES (?,?,?,-1,'e','p',?)",
                 (rid, verdict, reason, at))
    conn.commit()
    conn.close()


def review(mod, rid, decision, at, note=""):
    """What an admin approve/reject/clear does: one transaction + restand."""
    conn = mod.connect()
    try:
        with conn:
            if decision is None:
                conn.execute("DELETE FROM reviews WHERE replay_id = ?", (rid,))
            else:
                conn.execute(
                    "INSERT INTO reviews (replay_id, decision, note, at)"
                    " VALUES (?,?,?,?) ON CONFLICT(replay_id) DO UPDATE SET"
                    " decision = excluded.decision, note = excluded.note,"
                    " at = excluded.at", (rid, decision, note, at))
            return mod.restand(conn, rid)
    finally:
        conn.close()


def rows_by_player(mod, **kw):
    body = board(mod, limit=200, **kw)
    return {r["player"]: r for r in body["rows"]}


m = fresh()
clock = FakeClock()
m.time = clock
T = int(clock.now)
grid = []
for verdict in (None, "PASS", "HOLD", "REFUSE", "ERROR"):
    for decision in (None, "approve"):
        who = "g%s%s" % ((verdict or "none").lower(), decision or "")
        rid = run(m, who, 3000 + len(grid))["rep"]
        if verdict:
            add_verdict(m, rid, verdict, T + 5)
        if decision:
            review(m, rid, decision, T + 5)
        grid.append((who, verdict, decision))
got = rows_by_player(m)
for who, verdict, decision in grid:
    want = 1 if m.public_state(verdict, decision) == "verified" else 0
    check("ver %-6s x %-7s == public_state" % (verdict, decision),
          got[who]["ver"], want)
check("control: the grid has both answers",
      sorted({got[w]["ver"] for w, _, _ in grid}), [0, 1])
r = run(m, "nofile", 2000, rec=False)
check("a rep-0 row reads ver 0", (r["rep"], rows_by_player(m)["nofile"]["ver"]), (0, 0))

a = run(m, "late1", 5000)["rep"]
add_verdict(m, a, "PASS", T + 5)
add_verdict(m, a, "HOLD", T + 6)
b = run(m, "late2", 5001)["rep"]
add_verdict(m, b, "HOLD", T + 5)
add_verdict(m, b, "PASS", T + 6)
e1 = run(m, "late3", 5002)["rep"]                # ERROR is not a verdict
add_verdict(m, e1, "PASS", T + 5)
add_verdict(m, e1, "ERROR", T + 6)
e2 = run(m, "late4", 5003)["rep"]
add_verdict(m, e2, "HOLD", T + 5)
add_verdict(m, e2, "ERROR", T + 6)
got = rows_by_player(m)
check("the latest verdict wins: PASS then HOLD is 0", got["late1"]["ver"], 0)
check("...and HOLD then PASS is 1", got["late2"]["ver"], 1)
check("PASS then ERROR stays 1 (an ERROR never revokes)", got["late3"]["ver"], 1)
check("HOLD then ERROR stays 0 (...nor grants)", got["late4"]["ver"], 0)

c = run(m, "cur", 5100)["rep"]
add_verdict(m, c, "PASS", T + 5)
check("control: a PASS on the standing replay reads 1",
      rows_by_player(m)["cur"]["ver"], 1)
clock.now += 60
# Exact tie, but a SECOND RUN: its own runid, as every real one has (SV_RecOpen
# stamps wallclock+slot).  That is what makes it new evidence rather than the
# same row re-posted -- section 19 (c) pins the other half, that an identical
# re-post must NOT move `submitted` and void the verdict under it.
tie_rec(m, "cur", 5100, "r-cur-2")
r = run(m, "cur", 5100, runid="r-cur-2")
check("an exact-tie resubmission reuses the replay row", r["rep"], c)
check("...and the older PASS no longer counts", rows_by_player(m)["cur"]["ver"], 0)

# --------------------------------------------------------------------------
print("\n--- 16. reject, clear, and restand() -------------------------------")

m = fresh()
clock = FakeClock()
m.time = clock
T = int(clock.now)
run(m, "xavier", 4400)                          # 44 s
run(m, "yara", 6000)                            # 60 s
clock.now += 1
slow = run(m, "eve", 5000)["rep"]               # 50 s
clock.now += 1
fast = run(m, "eve", 4000)["rep"]               # 40 s, now her row
check("eve stands on her 40 s run", rows_by_player(m)["eve"]["ms"], 40000)
check("reject the 40 s replay -> moved", review(m, fast, "reject", T + 10), "moved")
check("...and the board shows her 50 s run", rows_by_player(m)["eve"]["ms"], 50000)
check("...pointing at that replay", rows_by_player(m)["eve"]["rep"], slow)
check("clear -> moved back", review(m, fast, None, T + 11), "moved")
check("...and the board shows 40 s again", rows_by_player(m)["eve"]["ms"], 40000)
check("reject again", review(m, fast, "reject", T + 12), "moved")
clock.now += 20
r = run(m, "eve", 4500)                          # 45 s, slower than the rejected 40
check("after the reject a 45 s run stores", r["stored"], True)
body = board(m, limit=200)
pos = [x["player"] for x in body["rows"]].index("eve") + 1
check("...and submit_run's rank is the board position",
      (r["rank"], r["of"]), (pos, len(body["rows"])))
check("...which is #2 behind 44 s", pos, 2)

m2 = fresh()
m2.time = FakeClock()
rid = run(m2, "lone", 3000)["rep"]
check("a lone rejected row is removed", review(m2, rid, "reject", T + 10), "removed")
check("...and is off the board", "lone" in rows_by_player(m2), False)
check("...and clear restores it", (review(m2, rid, None, T + 11),
      rows_by_player(m2)["lone"]["ms"]), ("moved", 30000))

m3 = fresh()
m3.time = FakeClock()
rid = run(m3, "zero", 4000)["rep"]
m3.time.now += 1
run(m3, "zero", 3000, rec=False)                # faster, no recording: rep 0
check("a rep-0 row is kept when an older replay is rejected",
      (review(m3, rid, "reject", T + 10), rows_by_player(m3)["zero"]["rep"]),
      ("kept", 0))
check("restand of an unknown replay is none", m3.restand(m3.connect(), 9999), "none")

# restand runs in the caller's transaction: a rollback undoes it.
m4 = fresh()
m4.time = FakeClock()
rid = run(m4, "roll", 3000)["rep"]
conn = m4.connect()
try:
    with conn:
        conn.execute("INSERT INTO reviews (replay_id, decision, at)"
                     " VALUES (?, 'reject', ?)", (rid, T + 10))
        inner = m4.restand(conn, rid)
        raise RuntimeError("roll back")
except RuntimeError:
    pass
conn.close()
check("restand inside a rolled-back transaction said removed", inner, "removed")
check("...and nothing of it survived",
      ("roll" in rows_by_player(m4), q(m4, "SELECT COUNT(*) FROM reviews")),
      (True, [(0,)]))

# An old reject lapses when an exact tie re-describes the replay row.
m5 = fresh()
clock = FakeClock()
m5.time = clock
rid = run(m5, "tie", 3000)["rep"]
review(m5, rid, "reject", int(clock.now) + 5)
check("control: the rejected run is off the board", "tie" in rows_by_player(m5), False)
clock.now += 60
tie_rec(m5, "tie", 3000, "r-tie-2")
r = run(m5, "tie", 3000, runid="r-tie-2")    # a second run, so its own runid
check("an exact tie after the reject stores on the same replay row",
      (r["stored"], r["rep"]), (True, rid))
check("...and the lapsed reject no longer moves it", m5.restand(m5.connect(), rid), "kept")

# --------------------------------------------------------------------------
print("\n--- 17. nothing private reaches a public body ---------------------")

priv = tempfile.mkdtemp(prefix="surfd-board-maps-")
os.makedirs(os.path.join(priv, "zones", "online"))
os.environ["SURFD_MAPS"] = priv
os.environ["SURFD_ZONES"] = os.path.join(priv, "zones", "online")
m = fresh()
m.time = FakeClock()
T = int(m.time.now)
held = run(m, "holdme", 3000)["rep"]
add_verdict(m, held, "HOLD", T + 5, reason="SENTINEL-REASON")
kept = run(m, "noted", 3100)["rep"]
review(m, kept, "approve", T + 5, note="SENTINEL-NOTE")
gone = run(m, "hidden", 2900)["rep"]
review(m, gone, "reject", T + 5, note="SENTINEL-NOTE2")
c = m.app.test_client()
bodies = {}
for path in ("/api/board?map=surf_test", "/board/api/maps",
             "/board/api/map?map=surf_test", "/board/", "/board/board.js",
             "/board/board.css"):
    resp = c.get(path, environ_base={"REMOTE_ADDR": "127.0.0.1"})
    bodies[path] = (resp.status_code, resp.get_data(as_text=True))
check("every public body answered 200",
      sorted({s for s, _ in bodies.values()}), [200])
for path, (_, text) in sorted(bodies.items()):
    low = text.lower()
    leaked = [w for w in ("sentinel", "verdict", "reason", "reject", "approve")
              if w in low] + (["HOLD"] if "HOLD" in text else [])
    check("no private word in %s" % path, leaked, [])
check("control: the sentinels are in the database",
      (q(m, "SELECT reason FROM verdicts WHERE replay_id = ?", (held,)),
       sorted(r[0] for r in q(m, "SELECT note FROM reviews"))),
      ([("SENTINEL-REASON",)], ["SENTINEL-NOTE", "SENTINEL-NOTE2"]))
check("control: the approved run shows VERIFIED, the rejected one is gone",
      (rows_by_player(m)["noted"]["ver"], "hidden" in rows_by_player(m)), (1, False))
os.environ.pop("SURFD_MAPS", None)
os.environ.pop("SURFD_ZONES", None)

# --------------------------------------------------------------------------
print("\n--- 18. schema 6: the run a stage row was set in (`run`) ----------")

R = "20260918-142825-0-p27510"
R2 = "20260918-150000-0-p27510"


def q6(mod, sql, args=()):
    """q(), but a schema-5 database's missing column reads as a value."""
    try:
        return q(mod, sql, args)
    except sqlite3.Error as exc:
        return "error: %s" % exc


def legrows(mod, leg):
    body = board(mod, leg=leg, limit=200)
    return {r["player"]: r for r in body["rows"]} if isinstance(body, dict) else {}


m = fresh()
clock = FakeClock()
m.time = clock
T = int(clock.now)
run(m, "alice", 700, rec=False, leg=1, runid=R)       # posted mid-run, no leaf
clock.now += 1
run(m, "alice", 900, rec=False, leg=2, runid=R)
check("(b) a stage posted before its run finishes reads run 0",
      legrows(m, 2)["alice"].get("run"), 0)
clock.now += 1
main = run(m, "alice", 4000, runid=R)["rep"]
a1, a2 = legrows(m, 1)["alice"], legrows(m, 2)["alice"]
check("(a) legs 1 and 2: rep 0, run = the main run's replay",
      (a1["rep"], a1.get("run"), a2["rep"], a2.get("run")), (0, main, 0, main))
check("(a) ...and the main row itself reads run 0",
      legrows(m, 0)["alice"].get("run"), 0)
check("(a) control: the main replay is a real id", main > 0, True)

clock.now += 1
new = run(m, "alice", 3500, runid=R2)["rep"]
check("(c) alice improves her main run: a new replay stands",
      (new != main, legrows(m, 0)["alice"]["rep"]), (True, new))
check("(c) ...and the stage row still names the run it was set in",
      legrows(m, 2)["alice"].get("run"), main)
check("(c) control: no leg-0 runs row carries R now (a runs join reads 0)",
      q(m, "SELECT 1 FROM runs WHERE leg = 0 AND runid = ?", (R,)), [])

check("(d) reject the parent replay", review(m, main, "reject", T + 10), "kept")
check("(d) ...and the stage row reads run 0", legrows(m, 2)["alice"].get("run"), 0)
review(m, main, None, T + 11)
check("(d) control: clearing the review links it again",
      legrows(m, 2)["alice"].get("run"), main)

clock.now += 1
bob = run(m, "bob", 5000, runid=R)["rep"]
check("(e) bob's run under the same runid string leaves alice's link",
      legrows(m, 2)["alice"].get("run"), main)
check("(e) control: bob's is the newest leg-0 replay with that runid",
      q6(m, "SELECT MAX(id) FROM replays WHERE leg = 0 AND runid = ?", (R,)),
      [(bob,)])

clock.now += 1
own = run(m, "carol", 800, leg=2, runid="R-carol")["rep"]   # !s 2: its own leaf
run(m, "carol", 6000, runid="R-carol")
row = legrows(m, 2)["carol"]
check("(f) a stage-only run with its own leaf: rep > 0, run 0",
      (own > 0 and row["rep"] == own, row.get("run")), (True, 0))

# (g) the 5 -> 6 migration: a live v5 file, one run and one superseded replay.
V5 = V4.replace("PRAGMA user_version=4;", "") + """
CREATE TABLE reviews (replay_id INTEGER PRIMARY KEY, decision TEXT NOT NULL
    CHECK (decision IN ('approve', 'reject')), note TEXT NOT NULL DEFAULT '',
    at INTEGER NOT NULL);
CREATE INDEX runs_replay ON runs (replay_id);
ALTER TABLE replays ADD COLUMN recheck_at INTEGER NOT NULL DEFAULT 0;
UPDATE runs SET runid = '%s';
INSERT INTO runs VALUES ('surf_test',0,2,'ranked','clean','old','Old',
    700,100.0,7000,0,'p27510','%s',1700000000,0);
INSERT INTO replays (map, map_dir, track, leg, leaf, tier, style, player, name,
    ticks, tickrate, millis, flags, node, submitted, seen, checked)
    VALUES ('surf_test','surf_test',0,0,'0005000_run.rec','ranked','clean',
    'old','Old',5000,100.0,50000,0,'p27510',1690000000,-1,0);
PRAGMA user_version=5;
""" % (R, R)


def seed_v5(path):
    conn = sqlite3.connect(path)
    conn.executescript(V5)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.commit()
    conn.close()


m = fresh(seed=seed_v5)
names_, cols, ver = objects(m._test_db)
check("(g) a v5 database upgrades to the head", ver, HEAD_SCHEMA)
check("(g) ...gaining replays.runid, kind and the replays_runid index",
      (cols.count("runid"), cols.count("kind"), "replays_runid" in names_),
      (1, 1, True))
check("(g) ...keeping its rows, runid backfilled from runs, kind 'run'",
      (q(m, "SELECT player, leg, runid, replay_id FROM runs ORDER BY leg"),
       q6(m, "SELECT id, runid, kind FROM replays ORDER BY id")),
      ([("old", 0, R, 1), ("old", 2, R, 0)], [(1, R, "run"), (2, "", "run")]))
check("(g) ...and the upgraded stage row names its run",
      [(r["player"], r.get("run")) for r in board(m, leg=2)["rows"]], [("old", 1)])

race5 = os.path.join(m._test_home, "race5.db")
seed_v5(race5)
seen5 = []


def racing5(real):
    rc = RacingConn(real, race5, "ADD COLUMN runid")
    seen5.append(rc)
    return rc


check("(g) another process adding runid between the check and the ALTER",
      migrate_file(m, race5, racing5), "ok")
check("(g) ...really raced (control)", any(rc.raced for rc in seen5), True)
names_, cols, ver = objects(race5)
check("(g) ...leaves one runid, one kind, and the head schema",
      (cols.count("runid"), cols.count("kind"), ver), (1, 1, HEAD_SCHEMA))
conn = sqlite3.connect(race5)
try:
    conn.execute("ALTER TABLE replays ADD COLUMN runid TEXT")
    dup = "no error"
except sqlite3.OperationalError as exc:
    dup = str(exc)
conn.close()
check("(g) control: SQLite's error for the lost race is the tolerated one",
      "duplicate column" in dup, True)

errors = []
steps = []
real_path = m.DB_PATH
m.log.info = lambda msg, *a, **k: steps.append((n, msg % a))
try:
    for n in range(20):
        path = os.path.join(m._test_home, "thr5_%d.db" % n)
        seed_v5(path)
        m.DB_PATH = path
        gate = threading.Barrier(2)

        def worker(gate=gate):
            try:
                gate.wait()
                m.migrate()
            except Exception as exc:
                errors.append(repr(exc))
        threads = [threading.Thread(target=worker) for _ in range(2)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        names_, cols, ver = objects(path)
        if (cols.count("runid"), cols.count("kind"), ver) != (1, 1, HEAD_SCHEMA):
            errors.append("round %d: %r" % (n, (cols.count("runid"), ver)))
finally:
    m.DB_PATH = real_path
    del m.log.info
both = sum(1 for k in range(20)
           if sum(1 for r, s in steps if r == k and "migrated 5 -> " in s) == 2)
print("     (both threads ran step 6 in %d of 20 rounds)" % both)
check("(g) two threads migrating one v5 file, 20 rounds: no error", errors, [])
if both:
    check("(g) control: in some round both threads really ran step 6", both > 0, True)
else:
    print("skip (g) threads never overlapped in step 6 this run -- see the RacingConn arm")

# --------------------------------------------------------------------------
print("\n--- 19. a leaf is a claim on a file, not just a description -------")

# 2026-09-20.  `replays` is UNIQUE(map, track, leg, leaf) and the upsert rewrites
# the row, so a submission naming somebody else's leaf took their row, re-queued
# THEIR file, and wore the PASS it earned (VER_SQL).  Capability: the shared key
# and a trusted source -- no Pi write, no patched client.  The leaf is public
# (/api/replay serves it as the download filename) and so is `player`
# (/api/board emits it), which is why THE FIRST FIX FOR THIS WAS WRONG: it
# authenticated on `player`, and the attacker simply asserted the victim's.
# These cases therefore attack as the victim, which is the case that fix missed.
#
# The binding is now the FILE: submit_run opens the .rec and compares its header
# (map/track/leg/runid/flags) with the row being filed, and a re-post of the same
# evidence cannot rename its replay row (Patch 424).  So these arms write real
# files under RUNS_DIR, which the rest of the suite does not.


def wrec(mod, mapname, track, leg, leafname, owner, runid, ticks=700, flags=0):
    """Write a minimal but honest .rec where replay_file() will look for it."""
    d = os.path.join(mod.RUNS_DIR, mapname, mod.leg_dir(track, leg))
    os.makedirs(d, exist_ok=True)
    path = os.path.join(d, leafname)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("FTESURF-REC 9\nmap %s\ntrack %d\nleg %d\nowner %s\nrunid %s\n"
                 "tickrate 0.01\nclock counted\nflags %-10d\nbegin\n"
                 % (mapname, track, leg, owner, runid, flags))
        fh.write("end %d 0 0 0 0 0 0 0 0 0 1\n" % ticks)
    return path


m = fresh()
clock = FakeClock()
m.time = clock
T = int(clock.now)

alice_leaf = leaf(700, "alice")
wrec(m, "surf_test", 0, 0, alice_leaf, "Alice", "r1")
arep = run(m, "alice", 700)["rep"]
add_verdict(m, arep, "PASS", T + 1)
check("(a) alice's run is indexed and verified",
      (arep > 0, rows_by_player(m)["alice"]["ver"]), (True, 1))
a_before = q(m, "SELECT player, name, submitted, checked FROM replays WHERE id=?",
             (arep,))

# THE ATTACK THE FIRST FIX MISSED: assert the victim's `player` (it is public),
# and put your own name on the row.  Both of the old rules passed this.  Since
# Patch 424 the leaf binds (the runid matches) and the row keeps its own name.
clock.now += 10
steal = submit(m, player="alice", name="MALLORY", ticks=700, tickrate=100,
               rec=alice_leaf)
check("(b) naming alice's file under a different name is a re-post of her row",
      steal.get("rep"), arep)
check("(b) ...and her row is untouched: player, name, submitted, checked",
      q(m, "SELECT player, name, submitted, checked FROM replays WHERE id=?",
        (arep,)), a_before)
check("(b) ...and her standing PASS is still current",
      rows_by_player(m)["alice"]["ver"], 1)

# The badge-strip variant: re-post the row EXACTLY, to push `submitted` past the
# verdict and the approval.  Identical rows are now a no-op.
clock.now += 10
same = submit(m, player="alice", name="Alice", ticks=700, tickrate=100,
              rec=alice_leaf, runid="r1")
check("(c) re-posting an identical row does not move submitted/checked",
      q(m, "SELECT submitted, checked FROM replays WHERE id=?", (arep,)),
      [(a_before[0][2], a_before[0][3])])
check("(c) ...so the PASS stays current", rows_by_player(m)["alice"]["ver"], 1)
check("(c) control: it is still the same row", same.get("rep"), arep)

# A file whose header names another map/leg/runid cannot be filed here either.
clock.now += 10
wrong = leaf(650, "mallory")
wrec(m, "surf_test", 0, 0, wrong, "Mallory", "rX")
bad = submit(m, player="mallory", name="Mallory", ticks=650, tickrate=100,
             rec=wrong, runid="r-different")
check("(d) a runid that disagrees with the file drops the leaf",
      bad.get("rep"), 0)

# CONTROL: the honest submission of that same file indexes.
clock.now += 10
good = submit(m, player="mallory", name="Mallory", ticks=650, tickrate=100,
              rec=wrong, runid="rX")
check("(d) control: with the file's own runid it indexes", good.get("rep") > 0, True)
check("(d) control: ...as mallory's row",
      q(m, "SELECT player, name FROM replays WHERE id=?", (good["rep"],)),
      [("mallory", "Mallory")])

# A leaf with NO file behind it is kept, deliberately: it can inherit no verdict,
# and dropping it would punish a submit that races the recorder's rename.
clock.now += 10
nofile = submit(m, player="eve", name="Eve", ticks=640, tickrate=100,
                rec="0000640_run.rec")
check("(e) a leaf with no file is indexed unverified", nofile.get("rep") > 0, True)

# And the digest rule still bites when the leaf carries one that is not yours.
clock.now += 10
dig = submit(m, player="eve", name="Eve", ticks=700, tickrate=100, rec=alice_leaf)
check("(f) a leaf whose digest is another player's is dropped", dig.get("rep"), 0)
check("(f) ...alice's row still hers",
      q(m, "SELECT player, name FROM replays WHERE id=?", (arep,)),
      [(a_before[0][0], a_before[0][1])])

# Patch 424: A RENAME MID-RUN IS THE SAME RUN.  The header's `owner` is the
# netname at SV_RecOpen, the submit's `name` the one at the finish; comparing
# them took an honest ranked run off verification.  The board row shows the new
# name, the replay row the recorded one.
clock.now += 10
rleaf = leaf(690, "rena")
wrec(m, "surf_test", 0, 0, rleaf, "OldName", "rr")
ren = submit(m, player="rena", name="NewName", ticks=690, tickrate=100,
             rec=rleaf, runid="rr")
check("(g) a rename mid-run keeps the recording", ren.get("rep", 0) > 0, True)
check("(g) ...the replay row wears the name it was filed under",
      q(m, "SELECT player, name FROM replays WHERE id=?", (ren.get("rep", 0),)),
      [("rena", "NewName")])
add_verdict(m, ren.get("rep", 0), "PASS", int(clock.now) + 1)
row = rows_by_player(m)["rena"]
check("(g) ...the board row shows the new name, and it verifies",
      (row["name"], row["ver"]), ("NewName", 1))

# Control: the runid still binds -- the same rename with another run's id drops.
clock.now += 10
rleaf2 = leaf(680, "rena")
wrec(m, "surf_test", 0, 0, rleaf2, "OldName", "rr2")
ren2 = submit(m, player="rena", name="NewName", ticks=680, tickrate=100,
              rec=rleaf2, runid="rr-other")
check("(g) control: a runid the file contradicts still drops the leaf",
      ren2.get("rep"), 0)

# The Patch 424 review: with `owner` unchecked, a re-post could still choose
# the BOARD (flags), shave the time (a tickrate inside the old 0.5 Hz slack) or
# land a new board row under its own name beside the victim's badge.
clock.now += 10
seg = submit(m, player="alice", name="MALLORY", ticks=700, tickrate=100,
             rec=alice_leaf, runid="r1", flags=128)
check("(i) a re-post under other flags (another board) drops the leaf",
      seg.get("rep"), 0)
check("(i) ...and alice's replay row keeps its board",
      q(m, "SELECT style, flags FROM replays WHERE id=?", (arep,)),
      [("clean", 0)])
clock.now += 10
shave = submit(m, player="alice", name="Alice", ticks=700, tickrate=100.4,
               rec=alice_leaf, runid="r1")
check("(i) a tickrate 0.4% off the file's drops the leaf", shave.get("rep"), 0)
clock.now += 10
rleaf3 = leaf(640, "rena")
wrec(m, "surf_test", 0, 0, rleaf3, "Rena", "rr3", flags=0)
path3 = os.path.join(m.RUNS_DIR, "surf_test", "main", rleaf3)
with open(path3, encoding="utf-8") as fh:
    body3 = fh.read().replace("tickrate 0.01\n", "tickrate 0.015\n")
with open(path3, "w", encoding="utf-8", newline="\n") as fh:
    fh.write(body3)
fmt = submit(m, player="rena", name="Rena", ticks=640, tickrate=66.6667,
             rec=rleaf3, runid="rr3")
check("(i) control: the lobby's %.4f of a 0.015 period still binds",
      fmt.get("rep", 0) > 0, True)
db = sqlite3.connect(m._test_db)
db.execute("DELETE FROM runs WHERE player = 'alice'")
db.commit()
db.close()
clock.now += 10
new = submit(m, player="alice", name="MALLORY", ticks=700, tickrate=100,
             rec=alice_leaf, runid="r1")
check("(i) a board row a re-post creates wears the replay's name",
      (new.get("rep"), rows_by_player(m)["alice"]["name"]), (arep, "Alice"))
clock.now += 10
cmty = submit(m, player="alice", name="Alice", ticks=700, tickrate=100,
              rec=alice_leaf, runid="r1", tier="community")
check("(i) a re-post asking for another tier keeps the replay's board",
      (q(m, "SELECT tier FROM replays WHERE id=?", (arep,)),
       sorted(rows_by_player(m, tier="community"))), ([("ranked",)], []))
clock.now += 10
fifth = submit(m, player="rena", name="Rena", ticks=640, tickrate=66.6679,
               rec=rleaf3, runid="rr3")
check("(i) 66.6679/s against a 0.015 period (1.2 mHz off) is refused",
      fifth.get("rep"), 0)

# A rejected recording never takes a board row back, and never wears the badge.
clock.now += 10
review(m, arep, "reject", int(clock.now))
check("(j) control: the reject took alice's row off the board",
      "alice" in rows_by_player(m), False)
clock.now += 10
back = submit(m, player="alice", name="Alice", ticks=700, tickrate=100,
              rec=alice_leaf, runid="r1")
check("(j) an identical re-post of a rejected replay is not stood",
      (back.get("stored"), "alice" in rows_by_player(m)), (False, False))
db = sqlite3.connect(m._test_db)
db.execute("INSERT INTO runs (map, track, leg, tier, style, player, name, ticks,"
           " tickrate, millis, flags, node, runid, submitted, replay_id)"
           " VALUES ('surf_test', 0, 0, 'ranked', 'clean', 'alice', 'Alice', 700,"
           " 100, 7000, 0, 'p1', 'r1', ?, ?)", (int(clock.now), arep))
db.commit()
db.close()
check("(j) a board row that names a rejected replay wears no badge (VER_SQL)",
      rows_by_player(m)["alice"]["ver"], 0)

# The header's map is the name as loaded, the board key is lowercased: until
# 424 the compare was exact and every leaf on a map with capitals dropped.
clock.now += 10
cleaf = leaf(660, "caps")
wrec(m, "surf_Aser", 0, 0, cleaf, "Caps", "rc")
cap = submit(m, map="surf_Aser", player="caps", name="Caps", ticks=660,
             tickrate=100, rec=cleaf, runid="rc")
check("(h) a map with capitals keeps its recording", cap.get("rep", 0) > 0, True)
clock.now += 10
oleaf = leaf(650, "caps")
p = wrec(m, "surf_Aser", 0, 0, oleaf, "Caps", "ro")
with open(p, encoding="utf-8") as fh:
    body = fh.read().replace("map surf_Aser\n", "map surf_Bser\n")
with open(p, "w", encoding="utf-8", newline="\n") as fh:
    fh.write(body)
oth = submit(m, map="surf_Aser", player="caps", name="Caps", ticks=650,
             tickrate=100, rec=oleaf, runid="ro")
check("(h) control: a header naming another map still drops", oth.get("rep"), 0)

# --------------------------------------------------------------------------
print("\n--- 20. the published TIME and the badge, bound to the file -------")

# The second review of section 19's fix found two criticals in it, both
# measured.  Section 19 tested WHO may claim a file; neither of these is about
# who -- they are about what a row may then SAY while wearing a badge.  Every
# input is public: /api/board emits player, name and ticks, and /api/replay
# serves the .rec (header: owner, runid) under the leaf as its filename.
#
#  (a) millis = ticks * 1000 / tickrate.  `ticks` is pinned by the leaf's own
#      prefix; `tickrate` was pinned by nothing, so the published TIME was a
#      caller-typed field no file contradicted.  The header carries it as a
#      PERIOD (`tickrate 0.01`) against the POST's frequency (100), so the
#      compare is a reciprocal, not a string.
#  (b) `bytes` was the sender's `recbytes`, and it is one of the four columns
#      deciding whether `submitted` moves.  One digit forced the ELSE arm and
#      voided the standing PASS and any owner approval -- the badge strip
#      section 19 claimed to close, still a one-field operation.  It is now the
#      file's real size, from the same stat the header came from.
#
# WHAT IS NOT CLOSED HERE, AND CANNOT BE AT THIS LAYER: a key holder may still
# post a FASTER time as anybody, and the runs row updates on an improvement, so
# the victim's board row is displaced.  The badge does not transfer -- the fake
# has no replay behind it -- but it does go dark.  Only player identity (the
# keypair, plan item 6) closes that; the shared key is documented as "a spam
# filter rather than a credential".  Asserted below so the boundary is pinned
# rather than assumed.

m = fresh()
clock = FakeClock()
m.time = clock
T = int(clock.now)

vleaf = leaf(700, "vic")
wrec(m, "surf_test", 0, 0, vleaf, "Vic", "rv")
vrep = submit(m, player="vic", name="Vic", ticks=700, tickrate=100,
              rec=vleaf, runid="rv")["rep"]
add_verdict(m, vrep, "PASS", T + 1)
before = q(m, "SELECT millis, tickrate FROM replays WHERE id=?", (vrep,))
check("(a) vic's honest run: 7000 ms and verified",
      (before[0][0], rows_by_player(m)["vic"]["ver"]), (7000, 1))

# THE FABRICATION: same player, name, runid, ticks and leaf -- only tickrate
# changed.  Before this fix it produced a 70 ms VERIFIED row.
clock.now += 10
fake = submit(m, player="vic", name="Vic", ticks=700, tickrate=10000,
              rec=vleaf, runid="rv")
check("(a) a tickrate the file contradicts drops the leaf", fake.get("rep"), 0)
check("(a) ...the replay row keeps its own millis and tickrate",
      q(m, "SELECT millis, tickrate FROM replays WHERE id=?", (vrep,)),
      [(before[0][0], before[0][1])])
row = rows_by_player(m)["vic"]
check("(a) THE BADGE DID NOT FOLLOW THE FABRICATED TIME",
      (row["ms"], row["ver"]), (70, 0))
check("(a) boundary: no row anywhere wears a badge for 70 ms",
      [r["ms"] for r in board(m)["rows"] if r["ver"]], [])

# CONTROL: the file's own tickrate still indexes, so this is not a blanket drop.
clock.now += 10
ok2 = submit(m, player="vic", name="Vic", ticks=700, tickrate=100,
             rec=vleaf, runid="rv")
check("(a) control: the file's own tickrate still indexes", ok2.get("rep"), vrep)

# (b) on its own database, because (a) legitimately displaced vic's board row.
m2 = fresh()
clock2 = FakeClock()
m2.time = clock2
T2 = int(clock2.now)
bleaf = leaf(700, "bob")
wrec(m2, "surf_test", 0, 0, bleaf, "Bob", "rb")
brep = submit(m2, player="bob", name="Bob", ticks=700, tickrate=100,
              rec=bleaf, runid="rb")["rep"]
add_verdict(m2, brep, "PASS", T2 + 1)
check("(b) bob's honest run is verified", rows_by_player(m2)["bob"]["ver"], 1)
b_before = q(m2, "SELECT submitted, checked, bytes FROM replays WHERE id=?", (brep,))
real = len(open(os.path.join(m2.RUNS_DIR, "surf_test", "main", bleaf), "rb").read())
check("(b) bytes is the file on disk, not the wire", b_before[0][2], real)

clock2.now += 10
strip = submit(m2, player="bob", name="Bob", ticks=700, tickrate=100,
               rec=bleaf, runid="rb", recbytes=999999)
check("(b) a wrong recbytes moves neither submitted, checked nor bytes",
      q(m2, "SELECT submitted, checked, bytes FROM replays WHERE id=?", (brep,)),
      b_before)
check("(b) ...so the PASS is still current", rows_by_player(m2)["bob"]["ver"], 1)
check("(b) control: it is still the same row", strip.get("rep"), brep)

# An owner approval is the other thing a moved `submitted` would void.
review(m2, brep, "approve", int(clock2.now) + 1)
clock2.now += 10
submit(m2, player="bob", name="Bob", ticks=700, tickrate=100, rec=bleaf,
       runid="rb", recbytes=12345)
check("(b) an approval survives a re-post with a wrong recbytes",
      rows_by_player(m2)["bob"]["ver"], 1)

# --------------------------------------------------------------------------
print("\n--- 21. a re-post changes nothing its evidence did not (review round 3)")
# The header bindings run only when the file opens.  On the Pi's ext4 a map
# spelling in other capitals does not, so a re-post skipped them all, kept its
# PASS as "the same evidence" and rewrote the replay's rate and board; with a
# changed recbytes it moved `submitted` and lapsed reviews.  cased() is ext4.

m = fresh()
clock = FakeClock()
m.time = clock
T = int(clock.now)
vleaf = leaf(700, "vic")
wrec(m, "surf_test", 0, 0, vleaf, "Vic", "rv")
vrep = submit(m, player="vic", name="Vic", ticks=700, tickrate=100,
              rec=vleaf, runid="rv")["rep"]
add_verdict(m, vrep, "PASS", T + 1)
held = "SELECT map_dir, tickrate, millis, flags, submitted, checked FROM replays WHERE id=?"
before = q(m, held, (vrep,))
real = m.replay_file


def cased(row):
    if row["map_dir"] != "surf_test":
        return None, "missing"
    return real(row)


clock.now += 10
submit(m, player="vic", name="Vic", ticks=700, tickrate=100.0002, rec=vleaf,
       runid="rv")
check("(b) a same-evidence re-post inside the rate bound keeps the stored rate",
      (q(m, held, (vrep,)), rows_by_player(m)["vic"]["ms"]), (before, 7000))
clock.now += 10
lleaf = leaf(100000, "lng")                # long enough for 4e-4 Hz to be ms
wrec(m, "surf_test", 0, 0, lleaf, "Lng", "rl", ticks=100000)
submit(m, player="lng", name="Lng", ticks=100000, tickrate=100, rec=lleaf, runid="rl")
clock.now += 10
submit(m, player="lng", name="Lng", ticks=100000, tickrate=100.0004, rec=lleaf,
       runid="rl")
check("(b) ...so the board keeps the stored time of a long run (4 ms otherwise)",
      (rows_by_player(m)["lng"]["ms"], rows_by_player(m)["lng"]["ver"]), (1000000, 0))
m.replay_file = cased
clock.now += 10
submit(m, map="SURF_TEST", player="vic", name="Vic", ticks=700, tickrate=100,
       rec=vleaf, runid="rv", recbytes=12345)
check("(a) another spelling binds through the one it was filed under: nothing moves",
      q(m, held, (vrep,)), before)
check("(a) ...and the board keeps the verified 7000 ms",
      (rows_by_player(m)["vic"]["ms"], rows_by_player(m)["vic"]["ver"]), (7000, 1))
clock.now += 10
submit(m, map="SURF_TEST", player="vic", name="Vic", ticks=700, tickrate=1000,
       rec=vleaf, runid="rv")
check("(a) ...and its header still binds: a rate it contradicts drops the leaf",
      q(m, held, (vrep,)), before)
check("(a) boundary (section 20): the faster fake stands with no badge",
      (rows_by_player(m)["vic"]["ms"], rows_by_player(m)["vic"]["ver"]), (700, 0))
m.replay_file = real

# 96 Hz written from a period with more digits than %g keeps (0.0104166667).
clock.now += 10
hleaf = leaf(960, "hz")
p96 = wrec(m, "surf_test", 0, 0, hleaf, "Hz", "r96")
with open(p96, encoding="utf-8") as fh:
    b96 = fh.read().replace("tickrate 0.01\n", "tickrate 0.0104167\n")
with open(p96, "w", encoding="utf-8", newline="\n") as fh:
    fh.write(b96)
h96 = submit(m, player="hz", name="Hz", ticks=960, tickrate=96.0, rec=hleaf,
             runid="r96")
check("(c) the lobby's 96.0000 against a %g period of 0.0104167 binds",
      h96.get("rep", 0) > 0, True)

# An exact tie filed on another board (a certification bit: community) by a
# new run: the ranked row no longer has that recording behind it.
clock.now += 10
tleaf = leaf(710, "tie")
wrec(m, "surf_test", 0, 0, tleaf, "Tie", "rt1")
t1 = submit(m, player="tie", name="Tie", ticks=710, tickrate=100, rec=tleaf,
            runid="rt1")["rep"]
clock.now += 10
wrec(m, "surf_test", 0, 0, tleaf, "Tie", "rt2", flags=512)
t2 = submit(m, player="tie", name="Tie", ticks=710, tickrate=100, rec=tleaf,
            runid="rt2", flags=512)
check("(d) control: the tie re-files the same replay row, on community",
      (t2.get("rep"), q(m, "SELECT tier FROM replays WHERE id=?", (t1,))),
      (t1, [("community",)]))
check("(d) ...and the ranked row no longer points at it",
      q(m, "SELECT tier, replay_id FROM runs WHERE player='tie' ORDER BY tier"),
      [("community", t1), ("ranked", 0)])


# A size off the wire is no evidence: with the file gone, a re-post naming a
# rejected replay with another recbytes must not lapse the reject (round 4).
clock.now += 10
review(m, vrep, "reject", int(clock.now))
os.unlink(os.path.join(m.RUNS_DIR, "surf_test", "main", vleaf))
clock.now += 10
submit(m, player="vic", name="Vic", ticks=700, tickrate=100, rec=vleaf,
       runid="rv", recbytes=99)
check("(e) with the file gone, a changed recbytes does not lapse the reject",
      q(m, "SELECT r.decision, r.at >= p.submitted FROM reviews r JOIN replays p"
           " ON p.id = r.replay_id WHERE p.id = ?", (vrep,)), [("reject", 1)])
clock.now += 10
submit(m, player="vic", name="EVIL", ticks=700, tickrate=10000, rec=vleaf,
       runid="Rother")
check("(e) with the file gone, another runid rewrites nothing on the held row",
      q(m, "SELECT runid, name, tickrate, millis FROM replays WHERE id=?", (vrep,)),
      [("rv", "Vic", 100.0, 7000)])
# A digest-less leaf (s<slot>, or none) binds no player: with its file gone, a
# re-post by another player must not stand on the owner's replay and badge.
clock.now += 10
dl = "0000720_run.rec"
wrec(m, "surf_test", 0, 0, dl, "Owner", "rdl", ticks=720)
drep = submit(m, player="owner", name="Owner", ticks=720, tickrate=100, rec=dl,
              runid="rdl")["rep"]
add_verdict(m, drep, "PASS", int(clock.now) + 1)
os.unlink(os.path.join(m.RUNS_DIR, "surf_test", "main", dl))
clock.now += 10
evil = submit(m, player="evil", name="Evil", ticks=720, tickrate=100, rec=dl,
              runid="rdl")
check("(e) a file-less re-post of another player's digest-less leaf stands on nothing of theirs",
      (evil.get("rep"), rows_by_player(m)["evil"]["name"], rows_by_player(m)["evil"]["ver"]),
      (0, "Evil", 0))
check("(e) runs_run indexes the per-run stage lookups",
      "runs_run" in [r[1] for r in q(m, "PRAGMA index_list(runs)")], True)


# --------------------------------------------------------------------------
print("\n--- (h) schema 8: the owner's word on a (key, player) pair -----------")
# Patch 422.  A v7 database is a v8 one with the two columns dropped.


def seed_v7(path, rows=True, first_cut=False):
    """first_cut: what c97b430 left -- stamped 8, pubkeys.decision present, none
    of the receipts columns."""
    src = sqlite3.connect(m._test_db)
    dst = sqlite3.connect(path)
    src.backup(dst)
    src.close()
    drops = [("receipts", "sig"), ("receipts", "signed_at"), ("receipts", "stale")]
    if not first_cut:
        drops += [("pubkeys", "decision"), ("pubkeys", "decided_at")]
    for table, col in drops:
        dst.execute("ALTER TABLE %s DROP COLUMN %s" % (table, col))
    dst.execute("DROP TABLE sweepmeta")
    if rows:
        dst.execute("INSERT INTO pubkeys (pub, player, first_at, last_at, runs)"
                    " VALUES ('k', 'p', 1, 2, 3)")
        dst.execute("INSERT INTO receipts (runid, pub, verdict, at) VALUES"
                    " ('r1', 'k', 'VALID', 50), ('r2', 'k', 'FAULT', 60)")
    dst.execute("PRAGMA user_version=%d" % (8 if first_cut else 7))
    dst.commit()
    dst.close()


def pubkey_cols(path):
    conn = sqlite3.connect(path)
    try:
        return [r[1] for r in conn.execute("PRAGMA table_info(pubkeys)")]
    finally:
        conn.close()


m = fresh()
v7 = os.path.join(m._test_home, "v7.db")
seed_v7(v7)
check("(h) control: the seed is a schema-7 pubkeys",
      pubkey_cols(v7), ["pub", "player", "first_at", "last_at", "runs"])
check("(h) a v7 database migrates", migrate_file(m, v7), "ok")
names_, cols, ver = objects(v7)
check("(h) ...to the head schema", ver, HEAD_SCHEMA)
check("(h) ...gaining decision and decided_at once each",
      [c for c in pubkey_cols(v7) if c in ("decision", "decided_at")],
      ["decision", "decided_at"])
conn = sqlite3.connect(v7)
check("(h) ...keeping the pair, undecided",
      conn.execute("SELECT pub, player, runs, decision, decided_at FROM pubkeys").fetchall(),
      [("k", "p", 3, "", 0)])
check("(h) ...backfilling receipts (VALID signed, FAULT unknown, signed_at = at)"
      " and marking them to be read again",
      conn.execute("SELECT runid, sig, signed_at, stale FROM receipts ORDER BY runid").fetchall(),
      [("r1", 1, 50, 1), ("r2", 0, 60, 1)])
check("(h) ...and creating sweepmeta",
      conn.execute("SELECT COUNT(*) FROM sqlite_master WHERE name = 'sweepmeta'").fetchone()[0], 1)
conn.close()

cut = os.path.join(m._test_home, "firstcut.db")
seed_v7(cut, first_cut=True)
check("(h) control: the first cut's database is stamped 8 without receipts.sig",
      (objects(cut)[2], "sig" in [r[1] for r in sqlite3.connect(cut).execute(
          "PRAGMA table_info(receipts)")]), (8, False))
check("(h) a database the first cut stamped 8 migrates", migrate_file(m, cut), "ok")
conn = sqlite3.connect(cut)
check("(h) ...and is repaired: the receipts columns and sweepmeta exist",
      ({"sig", "signed_at", "stale"} <= {r[1] for r in conn.execute("PRAGMA table_info(receipts)")},
       conn.execute("SELECT COUNT(*) FROM sqlite_master WHERE name = 'sweepmeta'").fetchone()[0]),
      (True, 1))
conn.close()

race7 = os.path.join(m._test_home, "race7.db")
seed_v7(race7)
seen7 = []


def racing7(real):
    rc = RacingConn(real, race7, "ADD COLUMN decision")
    seen7.append(rc)
    return rc


check("(h) another process adding decision between the check and the ALTER",
      migrate_file(m, race7, racing7), "ok")
check("(h) ...really raced (control)", any(rc.raced for rc in seen7), True)
check("(h) ...leaves one decision column and the head schema",
      (pubkey_cols(race7).count("decision"), objects(race7)[2]), (1, HEAD_SCHEMA))

errors = []
steps = []
real_path = m.DB_PATH
m.log.info = lambda msg, *a, **k: steps.append((n, msg % a))
try:
    for n in range(40):
        path = os.path.join(m._test_home, "thr7_%d.db" % n)
        seed_v7(path, rows=False)
        m.DB_PATH = path
        gate = threading.Barrier(2)

        def worker(gate=gate):
            try:
                gate.wait()
                m.migrate()
            except Exception as exc:
                errors.append(repr(exc))
        threads = [threading.Thread(target=worker) for _ in range(2)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        got = (pubkey_cols(path).count("decision"), objects(path)[2])
        if got != (1, HEAD_SCHEMA):
            errors.append("round %d: %r" % (n, got))
finally:
    m.DB_PATH = real_path
    del m.log.info
both = sum(1 for k in range(40)
           if sum(1 for r, s in steps if r == k and "migrated 7 -> " in s) == 2)
print("     (both threads ran step 8 in %d of 40 rounds)" % both)
check("(h) two threads migrating one v7 file, 40 rounds: no error", errors, [])
# Step 8 is two ALTERs, so real overlap is luck (0 of 40 in two of three runs);
# the RacingConn arm above is the deterministic race.  Say so, do not fail.
if both:
    check("(h) control: in some round both threads really ran step 8", both > 0, True)
else:
    print("skip (h) threads never overlapped in step 8 this run -- see the RacingConn arm")

# --------------------------------------------------------------------------
print("")
if FAILED:
    print("%d FAILED" % len(FAILED))
    for line in FAILED:
        print("  " + line)
    sys.exit(1)
print("all checks passed")
