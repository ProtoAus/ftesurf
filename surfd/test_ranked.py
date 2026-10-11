#!/usr/bin/env python3
"""Ranked means linked (Patch 629, ROADMAP 14.3 a): /api/run with
SURFD_RANKED_LINKED on.  The board's own mechanics are test_board.py's, with
the switch off; the link itself is test_accounts.py's.  Here: whose row a run
is, and where it lands when it is nobody's.

    python test_ranked.py
"""
import hashlib
import importlib
import logging
import os
import shutil
import sqlite3
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
os.environ["SURFD_TOOLS"] = os.environ.get("ACCOUNTS_TEST_TOOLS") or os.path.join(
    os.path.dirname(HERE), "tools")

FAILS = []
HOMES = []


def check(what, got, want):
    ok = got == want
    if not ok:
        FAILS.append(what)
    print("%s %-74s %s" % ("ok  " if ok else "FAIL", what[:74],
                           "" if ok else "%r  want %r" % (got, want)))


def fresh(linked="1", home=None):
    home = home or tempfile.mkdtemp(prefix="surfd-ranked-")
    if home not in HOMES:
        HOMES.append(home)
    with open(os.path.join(home, "surfd.env"), "w") as fh:
        fh.write("SURFD_KEY=testkey\n")
    os.environ.update(SURFD_HOME=home, SURFD_DB=os.path.join(home, "test.db"),
                      SURFD_ENV=os.path.join(home, "surfd.env"),
                      SURFD_RUNS=os.path.join(home, "runs"),
                      SURFD_MAPS=os.path.join(home, "maps"),
                      SURFD_WEBSHOTS=os.path.join(home, "webshots"))
    for k in ("SURFD_PUBLIC_HOST", "SURFD_TRUSTED", "SURFD_EVIDENCE", "SURFD_KEEP",
              "SURFD_RANKED_LINKED"):
        os.environ.pop(k, None)
    if linked is not None:
        os.environ["SURFD_RANKED_LINKED"] = linked
    for mod in ("surfd", "admin", "rcon"):
        sys.modules.pop(mod, None)
    m = importlib.import_module("surfd")
    m._home, m._db = home, os.environ["SURFD_DB"]
    return m


def rows(m, sql, args=()):
    conn = sqlite3.connect(m._db)
    try:
        return conn.execute(sql, args).fetchall()
    finally:
        conn.close()


def run_sql(m, sql, args=()):
    conn = sqlite3.connect(m._db)
    try:
        conn.execute(sql, args)
        conn.commit()
    finally:
        conn.close()


SID, SID2 = "76561198000000001", "76561198000000002"
GUID1, GUID2, GUID3 = "9fb6" + "a1" * 14, "0c0d" + "b2" * 14, "7777" + "c3" * 14
PUB1, PUB2, PUB3, PUB4 = "11" * 32, "22" * 32, "33" * 32, "44" * 32
NOW = 1800000000


def account(m, sid, name, banned=0):
    run_sql(m, "INSERT INTO accounts (steamid, name, created_at, banned_at) VALUES (?,?,?,?)",
            (sid, name, NOW, banned))


def linked(m, pub, sid, guid="g"):
    run_sql(m, "INSERT OR REPLACE INTO keylinks (pub, steamid, player, node, linked_at)"
               " VALUES (?,?,?,?,?)", (pub, sid, guid, "p27510", NOW))


def leaf(ticks, guid):
    """A recording's name as the game writes it: the INSTALL's digest in it."""
    return "%07d_proto-%s_run.rec" % (ticks, hashlib.sha256(guid.encode()).hexdigest()[:8])


def submit(m, guid, ticks, pub=None, src="127.0.0.1", **kw):
    """POST one run at tickrate 100 (ms = ticks * 10).  -> (status, body)."""
    form = {"key": "testkey", "map": "surf_test", "track": "0", "leg": "0", "player": guid,
            "name": "Proto", "ticks": str(ticks), "tickrate": "100", "flags": "0",
            "node": "p27510", "runid": "r%d" % ticks}
    if pub is not None:
        form["pub"] = pub
    form.update({k: str(v) for k, v in kw.items()})
    r = m.app.test_client().post("/api/run", data=form, environ_base={"REMOTE_ADDR": src})
    return r.status_code, (r.get_json() if r.mimetype == "application/json" else r.get_data(True))


def answer(reply):
    """The parts of a reply this suite is about."""
    code, body = reply
    if not isinstance(body, dict):
        return code, body
    return code, body.get("stored"), body.get("tier"), body.get("why"), body.get("rank")


def board(m, sql_tier="ranked"):
    return rows(m, "SELECT tier, player, millis FROM runs WHERE map = 'surf_test' AND leg = 0"
                   " AND tier = ? ORDER BY millis", (sql_tier,))


print("--- 1. whose row a run is")
m = fresh()
check("the switch is on unless the setting says 0", m.RANKED_LINKED, True)
account(m, SID, "Lex")
account(m, SID2, "Other")
linked(m, PUB1, SID)
r = submit(m, GUID1, 5000, PUB1)
check("a run whose connection proved a linked key is stored ranked, under the ACCOUNT",
      (answer(r), board(m)), ((200, True, "ranked", "", 1), [("ranked", SID, 50000)]))
submit(m, GUID1, 900, PUB1, leg=2, runid="r5000")
check("...and the install it came from is noted, beside the board: once a run, not once a post",
      rows(m, "SELECT steamid, install, pub, runs FROM installs"), [(SID, GUID1, PUB1, 1)])
check("...and neither the guid nor the key is in the answer",
      [w for w in (GUID1, PUB1) if w in str(r[1])], [])
linked(m, PUB2, SID)
r = submit(m, GUID2, 4000, PUB2)
check("a second install of the same account improves the SAME row",
      (answer(r), board(m), len(rows(m, "SELECT 1 FROM installs"))),
      ((200, True, "ranked", "", 1), [("ranked", SID, 40000)], 2))
check("...and a slower run from the first install does not replace it",
      (answer(submit(m, GUID1, 4500, PUB1)), board(m)),
      ((200, False, "ranked", "", 1), [("ranked", SID, 40000)]))
linked(m, PUB3, SID2)
r = submit(m, GUID3, 4200, PUB3)
check("another account's run is another row, ranked behind it",
      (answer(r), board(m)),
      ((200, True, "ranked", "", 2), [("ranked", SID, 40000), ("ranked", SID2, 42000)]))

print("\n--- 2. nobody's run")
for label, pub, why in (("no key was proven on its connection", None, "unproven"),
                        ("its key is nobody's", PUB4, "unlinked"),
                        ("its key is not 64 lowercase hex", "AB" * 32, "unproven"),
                        ("its key is 63 characters", "1" * 63, "unproven")):
    m = fresh()
    account(m, SID, "Lex")
    linked(m, PUB1, SID)
    r = submit(m, GUID1, 3000, pub)
    check("a run asking for the ranked board when %s lands on the community one, and says why"
          % label,
          (answer(r), board(m), board(m, "community")),
          ((200, True, "community", why, 1), [], [("community", GUID1, 30000)]))
check("...and such a run notes no install", rows(m, "SELECT COUNT(*) FROM installs"), [(0,)])
r = m.app.test_client().get("/api/board?map=surf_test&track=0",
                            environ_base={"REMOTE_ADDR": "127.0.0.1"})
check("...and is on no board a client is shown by default",
      [row.get("player") for row in (r.get_json() or {}).get("rows", [])], [])

print("\n--- 3. a banned account")
m = fresh()
account(m, SID, "Lex", banned=NOW)
linked(m, PUB1, SID)
r = submit(m, GUID1, 3000, PUB1, rec=leaf(3000, GUID1))
check("a banned account's run is not stored, on any tier, and the answer says so",
      (answer(r), rows(m, "SELECT COUNT(*) FROM runs"), rows(m, "SELECT COUNT(*) FROM replays"),
       rows(m, "SELECT COUNT(*) FROM installs")),
      ((200, False, "ranked", "banned", 0), [(0,)], [(0,)], [(0,)]))
run_sql(m, "UPDATE accounts SET banned_at = 0")
check("CONTROL the same run once the ban is lifted is stored",
      answer(submit(m, GUID1, 3000, PUB1)), (200, True, "ranked", "", 1))

print("\n--- 4. the link is read when the run arrives")
m = fresh()
account(m, SID, "Lex")
account(m, SID2, "Other")
check("before its key is linked a run is the community's",
      answer(submit(m, GUID1, 5000, PUB1)), (200, True, "community", "unlinked", 1))
linked(m, PUB1, SID)
check("...and the next one, after the link, is ranked: no reconnect needed",
      (answer(submit(m, GUID1, 5100, PUB1)), board(m)),
      ((200, True, "ranked", "", 1), [("ranked", SID, 51000)]))
linked(m, PUB1, SID2)
check("a key moved to another account ranks under that one from then on",
      (answer(submit(m, GUID1, 5200, PUB1)), board(m)),
      ((200, True, "ranked", "", 2), [("ranked", SID, 51000), ("ranked", SID2, 52000)]))
run_sql(m, "DELETE FROM keylinks WHERE pub = ?", (PUB1,))
check("...and an unlinked key ranks nothing again",
      answer(submit(m, GUID1, 4000, PUB1))[2:4], ("community", "unlinked"))

print("\n--- 5. the recording is named for the install, the row for the account")
m = fresh()
account(m, SID, "Lex")
linked(m, PUB1, SID)
r = submit(m, GUID1, 5000, PUB1, rec=leaf(5000, GUID1))
check("a linked run's recording, named by its install's digest, is indexed under the account",
      (answer(r)[:3], rows(m, "SELECT player, tier, leaf FROM replays")),
      ((200, True, "ranked"), [(SID, "ranked", leaf(5000, GUID1))]))
r = submit(m, GUID1, 4900, PUB1, rec=leaf(4900, SID))
check("a recording named by the ACCOUNT's digest is not this install's: the leaf is dropped, "
      "the time lands",
      (answer(r)[:3], [x[0] for x in rows(m, "SELECT leaf FROM replays ORDER BY id")]),
      ((200, True, "ranked"), [leaf(5000, GUID1)]))
r = submit(m, GUID1, 900, PUB1, leg=2, runid="r5000")
check("a stage row is the account's too",
      (answer(r)[:3], rows(m, "SELECT player, leg FROM runs WHERE leg > 0")),
      ((200, True, "ranked"), [(SID, 2)]))
TF_NOJOURNAL = 512
r = submit(m, GUID1, 4000, PUB1, flags=TF_NOJOURNAL)
check("an uncertifiable run of a linked install is the ACCOUNT's on the community board, and "
      "the reason is the run's, not the account's",
      (answer(r), board(m, "community")),
      ((200, True, "community", "", 1), [("community", SID, 40000)]))

print("\n--- 6. the switch")
m = fresh(linked=None)
check("with the setting ABSENT it is on: a deploy that forgets the line ranks nobody by guid",
      (m.RANKED_LINKED, answer(submit(m, GUID1, 5000))[2:4]), (True, ("community", "unproven")))
check("only 0 turns it off", [fresh(linked=v).RANKED_LINKED for v in ("0", " 0 ", "1", "", "off")],
      [False, False, True, True, True])
m = fresh(linked="0")
account(m, SID, "Lex")
linked(m, PUB1, SID)
check("off, a run is its submitter's guid on the ranked board, key or no key",
      (m.RANKED_LINKED, answer(submit(m, GUID1, 5000, PUB1)), answer(submit(m, GUID2, 5100)),
       board(m)),
      (False, (200, True, "ranked", "", 1), (200, True, "ranked", "", 2),
       [("ranked", GUID1, 50000), ("ranked", GUID2, 51000)]))
home = m._home
# What that spell leaves, and two shapes the live board has: a set-aside copy
# and a recording.  Then a real account's row beside them.
run_sql(m, "INSERT INTO runs (map, track, leg, tier, style, player, name, ticks, tickrate,"
           " millis, flags, node, runid, submitted, replay_id) SELECT map, track, 3,"
           " 'ranked@r9', style, player, name, ticks, tickrate, millis, flags, node, 'r9',"
           " submitted, 0 FROM runs WHERE player = ?", (GUID1,))
submit(m, GUID1, 4800, rec=leaf(4800, GUID1))
run_sql(m, "INSERT INTO runs (map, track, leg, tier, style, player, name, ticks, tickrate,"
           " millis, flags, node, runid, submitted, replay_id) VALUES ('surf_test', 0, 0,"
           " 'ranked', 'clean', ?, 'Lex', 4700, 100, 47000, 0, 'p27510', 'r4700', ?, 0)",
        (SID, NOW))
m = fresh(linked="0", home=home)
check("CONTROL a start with the switch off moves nothing",
      [t for (t,) in rows(m, "SELECT DISTINCT tier FROM runs ORDER BY tier")],
      ["ranked", "ranked@r9"])
m = fresh(home=home)
check("a start with it on moves every ranked row that is not an account's to the community "
      "tier, hidden copies and recordings with them, and leaves the account's",
      (rows(m, "SELECT tier, player FROM runs ORDER BY tier, player"),
       rows(m, "SELECT tier, player FROM replays")),
      ([("community", GUID2), ("community", GUID1), ("community@r9", GUID1), ("ranked", SID)]
       if GUID2 < GUID1 else
       [("community", GUID1), ("community", GUID2), ("community@r9", GUID1), ("ranked", SID)],
       [("community", GUID1)]))
m = fresh(home=home)
check("...and the next start finds nothing left to move",
      [t for (t,) in rows(m, "SELECT DISTINCT tier FROM runs ORDER BY tier")],
      ["community", "community@r9", "ranked"])
# A community row already where a moved one would land: the ranked one takes its place.
m = fresh(linked="0")
home = m._home
submit(m, GUID1, 5000)
run_sql(m, "INSERT INTO runs (map, track, leg, tier, style, player, name, ticks, tickrate,"
           " millis, flags, node, runid, submitted, replay_id) SELECT map, track, leg,"
           " 'community', style, player, name, 9000, tickrate, 90000, flags, node, 'r9000',"
           " submitted, 0 FROM runs")
m = fresh(home=home)
check("a moved row that meets a community row of the same player takes its place, and "
      "nothing breaks",
      rows(m, "SELECT tier, player, millis FROM runs"), [("community", GUID1, 50000)])

print("\n--- 6b. the move, once a switch-on, by who is an account")
m = fresh(linked="0")
home = m._home
account(m, SID, "Lex")
submit(m, GUID1, 5000)
run_sql(m, "INSERT INTO runs (map, track, leg, tier, style, player, name, ticks, tickrate,"
           " millis, flags, node, runid, submitted, replay_id) SELECT map, track, leg,"
           " 'community', style, player, name, 4000, tickrate, 40000, flags, node, 'r4000',"
           " submitted, 0 FROM runs")
# A row under an id that LOOKS like a SteamID and is nobody's account.
run_sql(m, "INSERT INTO runs (map, track, leg, tier, style, player, name, ticks, tickrate,"
           " millis, flags, node, runid, submitted, replay_id) VALUES ('surf_test', 0, 0,"
           " 'ranked', 'clean', '76561198000000099', 'Squat', 3000, 100, 30000, 0, 'p', 'x', 1, 0)")
HIGH = "76561200000000005"              # an account past where the ids begin 7656119
account(m, HIGH, "Newer")
run_sql(m, "INSERT INTO runs (map, track, leg, tier, style, player, name, ticks, tickrate,"
           " millis, flags, node, runid, submitted, replay_id) VALUES ('surf_test', 0, 0,"
           " 'ranked', 'clean', ?, 'Newer', 5100, 100, 51000, 0, 'p', 'y', 1, 0)", (HIGH,))
m = fresh(home=home)
check("a moved row that meets a FASTER community row of the same install gives way to it; "
      "a row shaped like a SteamID that is no account's moves too; an account's stays, "
      "wherever in the id range it is",
      rows(m, "SELECT tier, player, millis FROM runs ORDER BY tier, millis"),
      [("community", "76561198000000099", 30000), ("community", GUID1, 40000),
       ("ranked", HIGH, 51000)])
run_sql(m, "INSERT INTO runs (map, track, leg, tier, style, player, name, ticks, tickrate,"
           " millis, flags, node, runid, submitted, replay_id) VALUES ('surf_test', 0, 0,"
           " 'ranked', 'clean', ?, 'G', 4400, 100, 44000, 0, 'p', 'z', 1, 0)", (GUID2,))
m = fresh(linked="0", home=home)
check("CONTROL a start with the switch off leaves a guid's ranked row where it is",
      rows(m, "SELECT tier FROM runs WHERE player = ?", (GUID2,)), [("ranked",)])
m = fresh(home=home)
check("EVERY start with the switch on moves what it finds: there is no marker for whichever "
      "process starts first to flip",
      rows(m, "SELECT tier FROM runs WHERE player = ?", (GUID2,)), [("community",)])
plan = " ".join(r[3] for r in rows(
    m, "EXPLAIN QUERY PLAN SELECT rowid FROM runs WHERE tier NOT IN ('momentum', 'ksf')"
       " AND (tier = 'ranked' OR tier LIKE 'ranked@%' OR tier LIKE 'ranked^%')"
       " AND player NOT IN (SELECT steamid FROM accounts)"))
check("...and what it reads is an index of the rows that are no imported tier's, not the board",
      ("runs_live" in plan, "SCAN runs" in plan and "runs_live" not in plan), (True, False))
# Two starts at once.  Each used to read the list, then write: the second found,
# where a row was going, the row the first had just moved there, and deleted it.
m = fresh(linked="0")
home2 = m._home
conn = sqlite3.connect(m._db)
conn.executemany(
    "INSERT INTO runs (map, track, leg, tier, style, player, name, ticks, tickrate, millis,"
    " flags, node, runid, submitted, replay_id) VALUES ('surf_test', 0, ?, 'ranked', 'clean', ?,"
    " 'G', 1, 100, ?, 0, 'p', 'r', 1, 0)",
    [(leg, "%032x" % g, 1000 + g) for g in range(1, 301) for leg in range(0, 8)])
conn.commit()
conn.close()
import threading     # noqa: E402
done = []


def starter():
    c = m.connect()
    try:
        done.append(accounts_mod.ranked_now(c, m.TIERS_IMPORTED))
    finally:
        c.close()


import accounts as accounts_mod     # noqa: E402
threads = [threading.Thread(target=starter) for _ in range(4)]
for t in threads:
    t.start()
for t in threads:
    t.join()
check("four starts at once move every row once, and lose none",
      (rows(m, "SELECT tier, COUNT(*) FROM runs GROUP BY tier"), sorted(d[0] for d in done)),
      ([("community", 2400)], [0, 0, 0, 2400]))
m = fresh(home=home)
linked(m, PUB1, HIGH)
check("an account whose id begins 7656120 ranks, and still does after two starts",
      (answer(submit(m, GUID1, 5000, PUB1))[1:3], [fresh(home=home), fresh(home=home)] and
       rows(m, "SELECT tier, millis FROM runs WHERE player = ?", (HIGH,))),
      ((True, "ranked"), [("ranked", 50000)]))

print("\n--- 6c. an install is never named like an account")
for mode in ("1", "0"):
    m = fresh(linked=mode)
    account(m, SID, "Lex")
    linked(m, PUB1, SID)
    got = [submit(m, g, 3000)[0] for g in (SID, HIGH, "76561198000000099", "1" * 17)]
    check("switch %s: a run whose install is named like a SteamID64 is refused, with or "
          "without a key" % mode,
          (got, submit(m, SID, 3000, PUB1)[0], rows(m, "SELECT COUNT(*) FROM runs")),
          ([400] * 4, 400, [(0,)]))
m = fresh()
check("on, an install is named as the engine names one, 32 hex, or the run is refused",
      [submit(m, g, 3000)[0] for g in ("alice", GUID1.upper(), GUID1[:31], GUID1 + "0", GUID1)],
      [400, 400, 400, 400, 200])
check("...and a second seat on one machine is the first seat's guid with its number",
      [submit(m, GUID1 + suffix, 3000 + i)[0] for i, suffix in enumerate((":1", ":12", ":", ":123", ":x"))],
      [200, 200, 400, 400, 400])
m = fresh(linked="0")
check("off, a run is under whatever its submitter is called, as it was",
      (submit(m, "alice", 3000)[0], board(m)), (200, [("ranked", "alice", 30000)]))

print("\n--- 6d. the key is a trusted lobby's word")
m = fresh()
account(m, SID, "Lex")
linked(m, PUB1, SID)
check("a key holder outside the trusted addresses can file a time, and cannot say whose "
      "account it is",
      (answer(submit(m, GUID1, 3000, PUB1, src="203.0.113.5")), board(m)),
      ((200, True, "community", "unproven", 1), []))
check("...nor pin a run's identity: its run id is not taken either",
      rows(m, "SELECT COUNT(*) FROM runpins"), [(0,)])
check("CONTROL the same post from a lobby's address is the account's",
      answer(submit(m, GUID1, 3100, PUB1))[1:4], (True, "ranked", ""))

print("\n--- 6e. a run has ONE identity")
m = fresh()
account(m, SID, "Lex")
account(m, SID2, "Other")
# The proof lands after the run's first post.
linked(m, PUB1, SID)
linked(m, PUB2, SID2)
a1 = answer(submit(m, GUID1, 900, None, leg=1, runid="rA"))
a2 = answer(submit(m, GUID1, 950, PUB1, leg=2, runid="rA"))
a3 = answer(submit(m, GUID1, 5000, PUB1, runid="rA"))
check("a run whose first post had no key is nobody's to its last post, stages and finish",
      ([a1[2:4], a2[2:4], a3[2:4]],
       rows(m, "SELECT DISTINCT tier, player FROM runs WHERE runid = 'rA'")),
      ([("community", "unproven")] * 3, [("community", GUID1)]))
check("...and the NEXT run of that connection is the account's",
      answer(submit(m, GUID1, 5100, PUB1, runid="rB"))[1:4], (True, "ranked", ""))
# The link is made, moved and removed in the middle of a run.
m = fresh()
account(m, SID, "Lex")
account(m, SID2, "Other")
submit(m, GUID1, 900, PUB1, leg=1, runid="rC")
linked(m, PUB1, SID)
check("a link made mid-run ranks the next run, not the rest of this one",
      (answer(submit(m, GUID1, 950, PUB1, leg=2, runid="rC"))[2:4],
       answer(submit(m, GUID1, 5000, PUB1, runid="rC"))[2:4],
       answer(submit(m, GUID1, 5100, PUB1, runid="rD"))[2:4]),
      (("community", "unlinked"), ("community", "unlinked"), ("ranked", "")))
submit(m, GUID1, 800, PUB1, leg=1, runid="rE")
linked(m, PUB1, SID2)
check("a key moved to another account mid-run finishes the run it started under the first",
      (answer(submit(m, GUID1, 4000, PUB1, runid="rE"))[2:4],
       rows(m, "SELECT DISTINCT player FROM runs WHERE runid = 'rE'")),
      (("ranked", ""), [(SID,)]))
submit(m, GUID1, 700, PUB1, leg=1, runid="rF")
run_sql(m, "DELETE FROM keylinks WHERE pub = ?", (PUB1,))
check("...and so does one whose key was unlinked mid-run; the run after is nobody's",
      (answer(submit(m, GUID1, 3900, PUB1, runid="rF"))[2:4],
       rows(m, "SELECT DISTINCT player FROM runs WHERE runid = 'rF'"),
       answer(submit(m, GUID1, 3800, PUB1, runid="rG"))[2:4]),
      (("ranked", ""), [(SID2,)], ("community", "unlinked")))
linked(m, PUB1, SID)
submit(m, GUID1, 600, PUB1, leg=1, runid="rH")
run_sql(m, "UPDATE accounts SET banned_at = ? WHERE steamid = ?", (NOW, SID))
n = rows(m, "SELECT COUNT(*) FROM runs")
check("a ban is read when each post arrives: the rest of a run in progress is not stored",
      (answer(submit(m, GUID1, 3000, PUB1, runid="rH"))[1:4], rows(m, "SELECT COUNT(*) FROM runs")),
      ((False, "ranked", "banned"), n))
run_sql(m, "UPDATE accounts SET banned_at = 0")
run_sql(m, "DELETE FROM keylinks WHERE pub = ?", (PUB1,))
check("an unlinked install's run that is unranked for the RUN's own reason says nothing of "
      "the account: the lobby has that reason's words already",
      answer(submit(m, GUID1, 2700, PUB1, flags=512, runid="rJ"))[2:4], ("community", ""))
linked(m, PUB1, SID)
check("a post with no run id is read as it arrives",
      (answer(submit(m, GUID1, 2900, None, runid=""))[2:4],
       answer(submit(m, GUID1, 2800, PUB1, runid=""))[2:4]),
      (("community", "unproven"), ("ranked", "")))
# AN ACCOUNT'S PIN IS ITS KEY'S.  The run rE is account SID's, begun under PUB1.
n = rows(m, "SELECT COUNT(*) FROM runs")
held = (200, False, "community", "held", 0)
check("a later post of an account's run with NO key, with another linked key, or with a key "
      "that is nobody's is not stored at all: not the account's, and not split off under the guid",
      ([answer(submit(m, GUID1, 3600 + i, k, leg=3, runid="rE"))
        for i, k in enumerate((None, PUB2, PUB4, "ab" * 31))],
       rows(m, "SELECT COUNT(*) FROM runs"), rows(m, "SELECT player, pub FROM runpins WHERE runid = 'rE'")),
      ([held] * 4, n, [(SID, PUB1)]))
check("CONTROL the same post with the key the run began under is the account's",
      answer(submit(m, GUID1, 3700, PUB1, leg=3, runid="rE"))[1:4], (True, "ranked", ""))
check("a pin is its install's: another install naming the same run id is read on its own, "
      "and does not take the pin",
      (answer(submit(m, GUID2, 4100, None, runid="rE"))[1:4],
       rows(m, "SELECT tier, millis FROM runs WHERE player = ?", (GUID2,)),
       rows(m, "SELECT install, player FROM runpins WHERE runid = 'rE'")),
      ((True, "community", "unproven"), [("community", 41000)], [(GUID1, SID)]))
check("one pin a run, whatever the posts",
      rows(m, "SELECT runid, player, why FROM runpins WHERE runid IN ('rC', 'rE') ORDER BY runid"),
      [("rC", GUID1, "unlinked"), ("rE", SID, "")])
run_sql(m, "UPDATE runpins SET at = 1 WHERE runid IN ('rC', 'rE')")
submit(m, GUID1, 3750, PUB1, leg=4, runid="rE")
m2 = fresh(home=m._home)
check("a pin not used for ninety days goes at the next start; one a post used is kept from "
      "that post (a paused run lives for weeks)",
      rows(m2, "SELECT runid FROM runpins WHERE runid IN ('rC', 'rE')"), [("rE",)])

# A file an earlier cut of this patch started on: schema 16, pins with no key.
run_sql(m2, "ALTER TABLE runpins RENAME TO pins_now")
run_sql(m2, "CREATE TABLE runpins (runid TEXT NOT NULL, map TEXT NOT NULL, track INTEGER NOT NULL, "
            "install TEXT NOT NULL, player TEXT NOT NULL, why TEXT NOT NULL, at INTEGER NOT NULL, "
            "PRIMARY KEY (runid, map, track))")
run_sql(m2, "INSERT INTO runpins SELECT runid, map, track, install, player, why, at FROM pins_now")
run_sql(m2, "DROP TABLE pins_now")
m3 = fresh(home=m2._home)
check("a file an earlier cut started on gets the pin's key column at the next start, and "
      "loses its keyless pins (an account's would be held for ever)",
      ("pub" in [r[1] for r in rows(m3, "PRAGMA table_info(runpins)")],
       rows(m3, "SELECT COUNT(*) FROM runpins")), (True, [(0,)]))
check("...and a run with an id is stored on it (it answered 500)",
      answer(submit(m3, GUID1, 3900, PUB1, leg=5, runid="rU"))[:4], (200, True, "ranked", ""))

print("\n--- 6f. small things an account's row must not carry or cost")
m = fresh()
account(m, SID, "Lex")
linked(m, PUB1, SID)
submit(m, GUID1, 5000, PUB1, name="  ")
submit(m, GUID2, 5001, None, name="  ")
check("a name that cleans to nothing is not the guid beside an account's id",
      rows(m, "SELECT tier, name FROM runs ORDER BY tier"),
      [("community", GUID2), ("ranked", "player")])
for i in range(m.accounts.INSTALLS_MAX + 6):
    submit(m, "%032x" % (i + 1), 4000 + i, PUB1, runid="cap%d" % i)
check("an account's ledger of installs stops at its cap, and the runs still land",
      (rows(m, "SELECT COUNT(*) FROM installs WHERE steamid = ?", (SID,)),
       rows(m, "SELECT COUNT(*) FROM runpins WHERE runid LIKE 'cap%'")),
      ([(m.accounts.INSTALLS_MAX,)], [(m.accounts.INSTALLS_MAX + 6,)]))
# A Momentum player who also has a ranked row keeps the link to their profile.
run_sql(m, "INSERT INTO runs (map, track, leg, tier, style, player, name, ticks, tickrate,"
           " millis, flags, node, runid, submitted, replay_id) VALUES ('surf_test', 0, 0,"
           " 'momentum', 'clean', ?, 'Lex', 4000, 100, 40000, 0, 'mom', '', 1, 0)", (SID,))
handle = hashlib.sha256(SID.encode()).hexdigest()[:m.WEB_HANDLE_LEN]
r = m.app.test_client().get("/board/api/player/" + handle,
                            environ_base={"REMOTE_ADDR": "127.0.0.1"})
body = r.get_json() or {}
check("a player with imported rows keeps their outbound id on the profile once they have a "
      "ranked row", (r.status_code, body.get("ext"), body.get("by_tier", {}).get("ranked", 0) > 0),
      (200, SID, True))

print("\n--- 7. the game's mark for an account's rows")
import accounts     # noqa: E402  (after the path is set)
check("who_of is the digest the game takes of a row's player (FS_GuidId: SHA-256, 8 hex)",
      accounts.who_of(SID), hashlib.sha256(SID.encode()).hexdigest()[:8])

print("\n--- 8. a ban (Patch 633)")
ADMIN_ENV = {"SURFD_ADMIN_SECRET": "s" * 48, "SURFD_ADMIN_INSECURE_COOKIE": "1"}


def fresh_admin(linked="1"):
    """fresh(), with the admin panel on.  -> (module, a signed-in client, csrf)."""
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import admin as adm
    os.environ.update(ADMIN_ENV, SURFD_ADMIN_HASH=adm.hash_password("correct horse", n=2 ** 10))
    m = fresh(linked)
    c = m.app.test_client()
    page = c.get("/admin/login").get_data(as_text=True)
    token = page.split('name="csrf" value="')[1].split('"')[0]
    c.post("/admin/login", data={"csrf": token, "password": "correct horse"})
    page = c.get("/admin/accounts")
    token = page.get_data(as_text=True).split('name="csrf" value="')[1].split('"')[0]
    return m, c, token, page.status_code


def ban(c, token, sid, action="ban", note="speed hack, replay 12", seen=None):
    form = {"csrf": token, "steamid": sid, "action": action, "note": note}
    if seen is not None:
        form["seen"] = str(seen)
    r = c.post("/admin/api/ban", data=form)
    body = r.get_json() or {}
    return r.status_code, body.get("ok"), body.get("message") or body.get("error")


def tiers_of(m, sid):
    return sorted(rows(m, "SELECT leg, tier, millis FROM runs WHERE player = ?", (sid,)))


def public(m, rid):
    """What the public routes say of the board and of one recording.  No file
    is on disk here, so a recording that IS public answers "no recording on
    this node" and one that is not answers as if there were no such row."""
    c = m.app.test_client()
    b = c.get("/api/board?map=surf_test").get_json() or {}
    w = c.get("/board/api/map?map=surf_test").get_json() or {}
    return ([r.get("ms") for r in b.get("rows", [])], [r.get("ms") for r in w.get("rows", [])],
            (c.get("/board/api/run/%d" % rid).get_json() or {}).get("error"),
            (c.get("/api/replay/%d" % rid).get_json() or {}).get("error") == "no such replay")


m, c, token, page_status = fresh_admin()
account(m, SID, "Lex")
account(m, SID2, "Other")
linked(m, PUB1, SID)
linked(m, PUB2, SID2, "g2")
submit(m, GUID1, 5000, PUB1, rec=leaf(5000, GUID1))
submit(m, GUID1, 900, PUB1, leg=2, runid="r5000")
submit(m, GUID1, 4000, PUB1, flags=512)                 # uncertifiable: community, the account's
submit(m, GUID2, 6000, PUB2, rec=leaf(6000, GUID2))
run_sql(m, "INSERT INTO runs (map, track, leg, tier, style, player, name, ticks, tickrate, millis,"
           " flags, node, runid, submitted, replay_id) VALUES ('surf_test', 0, 0, 'momentum',"
           " 'clean', ?, 'Lex', 4800, 100, 48000, 0, 'import', '', ?, 0)", (SID, NOW))
RID = rows(m, "SELECT id FROM replays WHERE player = ?", (SID,))[0][0]
RID2 = rows(m, "SELECT id FROM replays WHERE player = ?", (SID2,))[0][0]
BEFORE = tiers_of(m, SID)
check("CONTROL before a ban both accounts are on the boards and their recordings are public",
      (page_status, public(m, RID)[:3], public(m, RID2)[2], public(m, RID)[3]),
      (200, ([50000, 60000], [50000, 60000], "no recording on this node"),
       "no recording on this node", False))
anon = m.app.test_client()
check("a ban is the signed-in admin's, with the page's token, a SteamID and a reason",
      (anon.post("/admin/api/ban", data={"csrf": token, "steamid": SID, "action": "ban",
                                         "note": "x"}).status_code,
       ban(c, "forged", SID)[:2], ban(c, token, SID, note="")[:2], ban(c, token, "12345")[:2],
       ban(c, token, "12345678901234567")[:2],          # seventeen digits, not a SteamID64
       ban(c, token, SID, action="erase")[:2], ban(c, token, GUID1)[:2],
       rows(m, "SELECT banned_at FROM accounts WHERE steamid = ?", (SID,)), tiers_of(m, SID) == BEFORE),
      (401, (400, False), (400, False), (400, False), (400, False), (400, False), (400, False),
       [(0,)], True))
check("a ban sets the account's rows and recordings aside, on every board it stood on",
      (ban(c, token, SID),
       tiers_of(m, SID),
       rows(m, "SELECT tier FROM replays WHERE player = ?", (SID,)),
       rows(m, "SELECT banned_at > 0, ban_note FROM accounts WHERE steamid = ?", (SID,))),
      ((200, True, "account %s banned: 3 board rows and 1 recordings set aside" % SID),
       [(0, "banned:community", 40000), (0, "banned:ranked", 50000), (0, "momentum", 48000),
        (2, "banned:ranked", 9000)],
       [("banned:ranked",)], [(1, "speed hack, replay 12")]))
check("...so no board lists them, the run page and the recording answer as if there were none, "
      "and the other account's stand",
      (public(m, RID), public(m, RID2)[2:]),
      (([60000], [60000], "no such run", True), ("no recording on this node", False)))
check("...an imported row under the same SteamID is another board's record and stays",
      rows(m, "SELECT millis FROM runs WHERE player = ? AND tier = 'momentum'", (SID,)), [(48000,)])
check("...and its next run is not stored (Patch 629), on any tier",
      (answer(submit(m, GUID1, 4500, PUB1))[1::2], len(tiers_of(m, SID))), ((False, "banned"), 4))
listed = {a["steamid"]: a for a in (c.get("/admin/api/accounts").get_json() or {}).get("accounts", [])}
check("the admin's list says who is banned, why, and how many rows are set aside",
      ([(k, bool(v["banned"]), v["note"], v["installs"], v["shown"], v["hidden"])
        for k, v in sorted(listed.items())], anon.get("/admin/api/accounts").status_code),
      ([(SID, True, "speed hack, replay 12", 1, 0, 3), (SID2, False, "", 1, 1, 0)], 401))
at = rows(m, "SELECT banned_at FROM accounts WHERE steamid = ?", (SID,))[0][0]
run_sql(m, "UPDATE accounts SET banned_at = 77 WHERE steamid = ?", (SID,))
check("a ban on a banned account keeps its date and takes the newer note; nothing moves twice",
      (ban(c, token, SID, note="and alt accounts")[2],
       rows(m, "SELECT banned_at, ban_note FROM accounts WHERE steamid = ?", (SID,))),
      ("account %s banned: 0 board rows and 0 recordings set aside (it already was; the note "
       "is replaced)" % SID,
       [(77, "and alt accounts")]))
check("an action that is neither ban nor unban is refused, and a banned account stays banned",
      (ban(c, token, SID, action="erase")[:2],
       rows(m, "SELECT banned_at FROM accounts WHERE steamid = ?", (SID,))), ((400, False), [(77,)]))
# A review of a banned account's recording re-derives its row INSIDE the set-aside family.
sub = rows(m, "SELECT submitted FROM replays WHERE id = ?", (RID,))[0][0]
r1 = c.post("/admin/api/review", data={"csrf": token, "rid": str(RID), "action": "reject",
                                       "submitted": str(sub), "note": "n"}).get_json() or {}
mid = tiers_of(m, SID)
r2 = c.post("/admin/api/review", data={"csrf": token, "rid": str(RID), "action": "clear",
                                       "submitted": str(sub)}).get_json() or {}
check("a review of a banned account's recording puts nothing back on a board",
      (r1.get("ok"), r2.get("ok"), [t for t in mid if t[1] in ("ranked", "community")],
       [t for t in tiers_of(m, SID) if t[1] in ("ranked", "community")], public(m, RID)[:2]),
      (True, True, [], [], ([60000], [60000])))
# Something stored under the SteamID on a plain tier while it was banned (it
# should not be): the unban keeps the faster of the two.
run_sql(m, "INSERT INTO runs (map, track, leg, tier, style, player, name, ticks, tickrate, millis,"
           " flags, node, runid, submitted, replay_id) VALUES ('surf_test', 0, 0, 'ranked',"
           " 'clean', ?, 'Lex', 5500, 100, 55000, 0, 'p27510', 'rX', ?, 0)", (SID, NOW))
run_sql(m, "INSERT INTO runs (map, track, leg, tier, style, player, name, ticks, tickrate, millis,"
           " flags, node, runid, submitted, replay_id) VALUES ('surf_test', 0, 2, 'ranked',"
           " 'clean', ?, 'Lex', 800, 100, 8000, 0, 'p27510', 'rY', ?, 0)", (SID, NOW))
run_sql(m, "INSERT INTO runs (map, track, leg, tier, style, player, name, ticks, tickrate, millis,"
           " flags, node, runid, submitted, replay_id) VALUES ('surf_test', 0, 0, 'community',"
           " 'clean', ?, 'Lex', 4000, 100, 40000, 0, 'p27510', 'rZ', ?, 0)", (SID, NOW))
BEFORE = [(0, "community", 40000), (0, "momentum", 48000), (0, "ranked", 50000), (2, "ranked", 8000)]
check("an unban puts every row and recording back where it stood, keeping the faster where a "
      "row is in the way (main: the returning row; the stage: the one in the way; an exact "
      "tie: the earlier, as the board orders)",
      (ban(c, token, SID, action="unban", note="appeal upheld"),
       tiers_of(m, SID), rows(m, "SELECT tier FROM replays WHERE player = ?", (SID,)),
       rows(m, "SELECT banned_at, ban_note FROM accounts WHERE steamid = ?", (SID,)),
       public(m, RID), rows(m, "SELECT runid FROM runs WHERE player = ? AND tier = 'community'",
                            (SID,))),
      ((200, True, "account %s unbanned: 2 board rows and 1 recordings back" % SID),
       BEFORE, [("ranked",)], [(0, "appeal upheld")],
       ([50000, 60000], [50000, 60000], "no recording on this node", False), [("r4000",)]))
check("...and its next run is stored again",
      answer(submit(m, GUID1, 4950, PUB1))[1:4], (True, "ranked", ""))
SID9 = "76561198000000077"
check("a SteamID that never signed in can be banned before it does; an unban of nobody is "
      "refused",
      (ban(c, token, "76561198000000078", action="unban")[:2], ban(c, token, SID9)[:2],
       rows(m, "SELECT name, banned_at > 0 FROM accounts WHERE steamid = ?", (SID9,)),
       rows(m, "SELECT COUNT(*) FROM accounts WHERE steamid = '76561198000000078'")),
      ((400, False), (200, True), [("", 1)], [(0,)]))
import accounts as _acc   # noqa: E402
conn = sqlite3.connect(m._db)
plan = " ".join(r[3] for r in conn.execute(
    "EXPLAIN QUERY PLAN SELECT rowid FROM runs WHERE player = ? AND tier NOT IN ('momentum', 'ksf')"
    " AND NOT tier LIKE 'banned:%'", (SID,)))
conn.close()
check("the rows of one account are found off an index (by player since Patch 636, or the "
      "one of non-imported rows), not by reading three million imported ones",
      "runs_player" in plan or "runs_live" in plan, True)

m, c, token, _ = fresh_admin("0")
account(m, SID, "Lex")
linked(m, PUB1, SID)
submit(m, GUID1, 5000, PUB1)
check("with ranked-means-linked OFF a ban is recorded and the page says what it does not do: "
      "the install's rows are its guid's and stay",
      (ban(c, token, SID)[:2], board(m),
       (c.get("/admin/api/accounts").get_json() or {}).get("ranked_linked"),
       rows(m, "SELECT banned_at > 0 FROM accounts WHERE steamid = ?", (SID,))),
      ((200, True), [("ranked", GUID1, 50000)], False, [(1,)]))

print("\n--- 8b. a ban, a review and a run in flight (Patch 633's review)")


def wrec(m, ticks, guid, runid, leg=0):
    """A minimal honest recording where replay_file() looks, so the replay is
    BOUND to its file and a reject of it is a reject of the run."""
    d = os.path.join(m.RUNS_DIR, "surf_test", m.leg_dir(0, leg))
    os.makedirs(d, exist_ok=True)
    name = leaf(ticks, guid)
    with open(os.path.join(d, name), "w", encoding="utf-8", newline="\n") as fh:
        fh.write("FTESURF-REC 9\nmap surf_test\ntrack 0\nleg %d\nowner Proto\nrunid %s\n"
                 "tickrate 0.01\nclock counted\nflags 0         \nbegin\n" % (leg, runid))
        fh.write("end %d 0 0 0 0 0 0 0 0 0 1\n" % ticks)
    return name


def review(m, c, token, rid, action):
    sub = rows(m, "SELECT submitted FROM replays WHERE id = ?", (rid,))[0][0]
    return (c.post("/admin/api/review", data={"csrf": token, "rid": str(rid), "action": action,
                                              "submitted": str(sub), "note": "n"}).get_json()
            or {}).get("ok")


def stage_board(m):
    r = m.app.test_client().get("/api/board?map=surf_test&leg=2").get_json() or {}
    return [x.get("ms") for x in r.get("rows", [])]


def staged():
    """An account with a recorded main run and a stage time of that run, and
    somebody else's stage time beside it."""
    m, c, token, _ = fresh_admin()
    account(m, SID, "Lex")
    account(m, SID2, "Other")
    linked(m, PUB1, SID)
    linked(m, PUB2, SID2, "g2")
    submit(m, GUID1, 5000, PUB1, rec=wrec(m, 5000, GUID1, "r5000"))
    submit(m, GUID1, 900, PUB1, leg=2, runid="r5000")
    submit(m, GUID2, 950, PUB2, leg=2, runid="r6000")
    rid = rows(m, "SELECT id FROM replays WHERE player = ?", (SID,))[0][0]
    return m, c, token, rid


def stages_of(m):
    return sorted(rows(m, "SELECT tier FROM runs WHERE player = ? AND leg = 2", (SID,)))


m, c, token, rid = staged()
got = [rows(m, "SELECT bound FROM replays WHERE id = ?", (rid,)), review(m, c, token, rid, "reject"),
       stages_of(m), stage_board(m), review(m, c, token, rid, "clear"), stages_of(m), stage_board(m)]
check("CONTROL with no ban, a reject of a run parks its stage time and a clear restores it",
      got, [[(1,)], True, [("ranked@r5000",)], [9500], True, [("ranked",)], [9000, 9500]])
m, c, token, rid = staged()
got = [ban(c, token, SID)[1], review(m, c, token, rid, "reject"), stages_of(m),
       ban(c, token, SID, action="unban")[1], stages_of(m), stage_board(m)]
check("a reject made WHILE BANNED parks the stage time inside the set-aside rows, so the unban "
      "does not put it on the board", got,
      [True, True, [("banned:ranked@r5000",)], True, [("ranked@r5000",)], [9500]])
m, c, token, rid = staged()
got = [review(m, c, token, rid, "reject"), ban(c, token, SID)[1], stages_of(m),
       review(m, c, token, rid, "clear"), stages_of(m),
       ban(c, token, SID, action="unban")[1], stages_of(m), stage_board(m)]
check("a reject cleared WHILE BANNED restores it there, so the unban shows it", got,
      [True, True, [("banned:ranked@r5000",)], True, [("banned:ranked",)], True, [("ranked",)],
       [9000, 9500]])
conn = sqlite3.connect(m._db)
conn.row_factory = sqlite3.Row
ban(c, token, SID)
banned_counts = m.stage_counts(conn, rid)
conn.close()
check("the admin's stage counts read a banned run's rows where they are", banned_counts, (1, 0, 0))

# The recording behind an account's stage rows (kind 'evidence') has no tier.
EV = "20260918-142825-0-p27510"
m, c, token, rid = staged()
submit(m, GUID1, 800, PUB1, leg=3, runid=EV)
os.makedirs(os.path.join(m.EVIDENCE_DIR, "surf_test"), exist_ok=True)
with open(os.path.join(m.EVIDENCE_DIR, "surf_test", EV + ".rec"), "w", newline="\n") as fh:
    fh.write("FTESURF-REC 9\nmap surf_test\ntrack 0\nstartseg 0\nleg 0\ntickrate 0.01\n"
             "movetickrate 0.01\nclock counted\nowner Proto\nrunid %s\nflags 0         \n"
             "begin\nstagepost 2 800\nabandon 4000\nend 4000 4000 0 0 4000 4 1 0 1 0\n" % EV)
conn = m.connect()
indexed = m.index_evidence(conn)["indexed"]
conn.close()
ev = rows(m, "SELECT id, tier FROM replays WHERE kind = 'evidence'")


def fetch(m, rid, client=None):
    r = (client or m.app.test_client()).get("/api/replay/%d" % rid)
    return r.status_code, (r.get_json() or {}).get("error") if r.is_json else len(r.get_data())


anon = m.app.test_client()
pre = (indexed, [t for _i, t in ev], fetch(m, rid)[0], fetch(m, ev[0][0])[0] if ev else None)
run_sql(m, "INSERT INTO replays (map, map_dir, track, leg, tier, style, player, name, ticks,"
           " tickrate, millis, flags, node, runid, leaf, bytes, submitted, kind) VALUES ('surf_test',"
           " 'surf_test', 0, 0, 'momentum', 'clean', ?, 'Lex', 4800, 100, 48000, 0, 'import', '',"
           " '0004800_lex-00000000_run.rec', 10, ?, 'momentum')", (SID, NOW))
demo = rows(m, "SELECT id FROM replays WHERE kind = 'momentum'")[0][0]
ban(c, token, SID)
detail = (c.get("/admin/api/run/%d" % rid).get_json() or {})
got = (pre, fetch(m, rid), fetch(m, ev[0][0]) if ev else None,
       detail.get("download"), c.get("/admin/api/run/%d/file" % rid).status_code,
       len(c.get("/admin/api/run/%d/file" % rid).get_data()) > 50,
       anon.get("/admin/api/run/%d/file" % rid).status_code, fetch(m, demo)[1] == "no such replay")
check("a banned account's recordings, the one behind its stage rows too, answer the public as "
      "if there were none; the admin's own route still hands the file over",
      got, ((1, [""], 200, 200), (404, "no such replay"), (404, "no such replay"),
            "/admin/api/run/%d/file" % rid, 200, True, 401, False))
ban(c, token, SID, action="unban")
check("...and both are public again after the unban",
      (fetch(m, rid)[0], fetch(m, ev[0][0])[0] if ev else None), (200, 200))

# A ban committed between a run's identity being read and its row being written.
m, c, token, rid = staged()
ban(c, token, SID)
real = m.accounts.run_identity
m.accounts.run_identity = lambda *a, **k: ("", SID)        # as it read BEFORE the ban
late = answer(submit(m, GUID1, 4800, PUB1, rec=wrec(m, 4800, GUID1, "r4800")))[:3]
m.accounts.run_identity = real
check("a run filed across a ban ends set aside with the rest: no row, no recording on a tier "
      "anybody reads",
      (late[0], sorted(set(t for (t,) in rows(m, "SELECT tier FROM runs WHERE player = ?", (SID,)))),
       sorted(set(t for (t,) in rows(m, "SELECT tier FROM replays WHERE player = ?", (SID,)))),
       [x for x in board(m)]),
      (200, ["banned:ranked"], ["banned:ranked"], []))
m, c, token, rid = staged()
m.accounts.run_identity, real = (lambda *a, **k: ("", SID)), m.accounts.run_identity
kept = answer(submit(m, GUID1, 4800, PUB1))[1:3]
m.accounts.run_identity = real
check("CONTROL the same post for an account that is not banned stands on the ranked board",
      (kept, board(m)), ((True, "ranked"), [("ranked", SID, 48000)]))

# The late pass reads the ban again once it holds the lock.
class Unbanned(object):
    """A connection whose first BEGIN IMMEDIATE finds an unban just committed."""
    def __init__(self, conn, path):
        self.conn, self.path, self.done = conn, path, False

    def execute(self, sql, *a):
        if sql == "BEGIN IMMEDIATE" and not self.done:
            self.done = True
            other = sqlite3.connect(self.path)
            other.execute("UPDATE accounts SET banned_at = 0 WHERE steamid = ?", (SID,))
            other.commit()
            other.close()
        return self.conn.execute(sql, *a)

    def __enter__(self):
        return self.conn.__enter__()

    def __exit__(self, *a):
        return self.conn.__exit__(*a)


m, c, token, rid = staged()
run_sql(m, "UPDATE accounts SET banned_at = 5 WHERE steamid = ?", (SID,))    # banned, nothing moved
conn = sqlite3.connect(m._db)
m._ban_late(Unbanned(conn, m._db), SID)
conn.close()
check("an unban that commits while the late pass waits for the lock is not followed by a "
      "set-aside", sorted(set(t for (t,) in rows(m, "SELECT tier FROM runs WHERE player = ?", (SID,)))),
      ["ranked"])
run_sql(m, "UPDATE accounts SET banned_at = 5 WHERE steamid = ?", (SID,))
conn = sqlite3.connect(m._db)
m._ban_late(conn, SID)
conn.close()
check("CONTROL with the ban still standing the same pass sets the rows aside",
      sorted(set(t for (t,) in rows(m, "SELECT tier FROM runs WHERE player = ?", (SID,)))),
      ["banned:ranked"])

# A start finds what a late pass missed.
m, c, token, rid = staged()
run_sql(m, "UPDATE accounts SET banned_at = 5 WHERE steamid = ?", (SID,))    # banned, nothing moved
m2 = fresh(home=m._home)
check("a start sets aside what a banned account still has on a tier readers name, and "
      "leaves everybody else's",
      (sorted(set(t for (t,) in rows(m2, "SELECT tier FROM runs WHERE player = ?", (SID,)))),
       rows(m2, "SELECT tier FROM replays WHERE player = ?", (SID,)),
       sorted(set(t for (t,) in rows(m2, "SELECT tier FROM runs WHERE player = ?", (SID2,))))),
      (["banned:ranked"], [("banned:ranked",)], ["ranked"]))
m, c, token, rid = staged()
m2 = fresh(home=m._home)
check("CONTROL a start with nobody banned moves nothing",
      sorted(set(t for (t,) in rows(m2, "SELECT tier FROM runs"))), ["ranked"])
m, c, token, rid = staged()
ban(c, token, SID, note="the reason")
ban(c, token, SID, action="unban", note="")
check("an unban with an empty note box keeps the ban's reason",
      rows(m, "SELECT banned_at, ban_note FROM accounts WHERE steamid = ?", (SID,)),
      [(0, "the reason")])

# What the page showed, and what the admin is told.
at = lambda: rows(m, "SELECT banned_at FROM accounts WHERE steamid = ?", (SID,))[0][0]
got = [ban(c, token, SID, action="unban", seen=0)[:2], ban(c, token, SID, action="unban")[:2],
       ban(c, token, SID, seen=0)[:2]]
stamp = at()
got += [ban(c, token, SID, seen=0)[0], ban(c, token, SID, action="unban", seen=stamp + 1)[0], at() == stamp,
        ban(c, token, SID, action="unban", seen=stamp)[:2], at()]
check("a row's button carries the state the page showed, and a stale one is refused; an unban "
      "of an account that is not banned is refused, and writes nothing",
      got, [(400, False), (400, False), (200, True), 409, 409, True, (200, True), 0])
check("a ban of a SteamID nobody has signed in with says so",
      ban(c, token, "76561198000000055")[2],
      "nobody has signed in as 76561198000000055: banned in advance (check the number)")
check("a blueprint with no ban functions has no ban routes, and the other pages no dead link",
      ("/admin/accounts" in c.get("/admin/runs").get_data(as_text=True),
       "{% if have_bans %}" in open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                                 "templates", "admin_runs.html")).read()),
      (True, True))

# The release's map-record file is made from the same table.
import contextlib          # noqa: E402
import io as _io           # noqa: E402
import pathlib             # noqa: E402
TOOLS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools")
if not os.path.isfile(os.path.join(TOOLS, "mapwr.py")):
    # A copy of surfd/ alone (tools/accounts_mutants.py makes one a mutant):
    # not a pass, and it says so.
    print("skip the map-record file names its tiers too: NOT MEASURED, no tools/ beside this copy")
else:
    sys.path.insert(0, TOOLS)
    import mapwr               # noqa: E402

    def map_records(m):
        out = _io.StringIO()
        with contextlib.redirect_stdout(out):
            exec(mapwr.REMOTE % {"db": pathlib.Path(m._db).as_uri()[len("file:"):]}, {})
        return [l for l in out.getvalue().splitlines() if l.startswith("wr surf_test ")]

    m, c, token, rid = staged()
    before = map_records(m)
    ban(c, token, SID)
    check("the map-record file names its tiers too: a banned account's time is no map's best",
          (before, map_records(m)), (["wr surf_test 50000 ranked Proto"], []))

for k in list(ADMIN_ENV) + ["SURFD_ADMIN_HASH"]:
    os.environ.pop(k, None)

logging.shutdown()                      # Windows: the log files are held open
for h in HOMES:
    shutil.rmtree(h, ignore_errors=True)
print()
if FAILS:
    print("%d FAILURE(S)" % len(FAILS))
    sys.exit(1)
print("all ranked checks passed")
