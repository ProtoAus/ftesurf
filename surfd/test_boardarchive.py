"""
test_boardarchive.py -- P1379: boardarchive.py parks and restores one map's WOS times.

    SURFD_HOME=/tmp/surfd-test python3 test_boardarchive.py

A fresh surfd import builds the schema in a temp DB (test_board.py's harness); rows are planted
directly.  What it pins: dry runs write nothing; archive parks every live WOS row and run recording
of the map (stage forms and bans included) and nothing else; the board API shows none of them;
restand keeps a parked replay parked; a label in use and live rows on restore are refused; restore
with --park-live-as swaps exactly; a ban nests outside the park and an unban keeps it parked.
"""

import contextlib
import importlib
import io
import atexit
import logging
import os
import shutil
import sqlite3
import sys
import tempfile

os.environ.setdefault("SURFD_RANKED_LINKED", "0")
FAILED = []
_HOMES = []


def _drop():
    if os.environ.get("SURFD_TEST_KEEP"):
        return
    logging.shutdown()
    for h in _HOMES:
        shutil.rmtree(h, ignore_errors=True)


atexit.register(_drop)


def check(label, got, want):
    ok = got == want
    print("%s  %s%s" % ("ok  " if ok else "FAIL", label, "" if ok else "  -- got %r want %r" % (got, want)))
    if not ok:
        FAILED.append(label)


def fresh():
    home = tempfile.mkdtemp(prefix="surfd-boardarchive-")
    _HOMES.append(home)
    db = os.path.join(home, "test.db")
    with open(os.path.join(home, "surfd.env"), "w") as fh:
        fh.write("SURFD_KEY=testkey\n")
    os.environ.update(SURFD_HOME=home, SURFD_DB=db, SURFD_ENV=os.path.join(home, "surfd.env"),
                      SURFD_RUNS=os.path.join(home, "runs"))
    os.makedirs(os.environ["SURFD_RUNS"], exist_ok=True)
    for k in ("SURFD_EVIDENCE", "SURFD_KEEP", "SURFD_PUBLIC_HOST", "SURFD_TRUSTED"):
        os.environ.pop(k, None)
    sys.modules.pop("surfd", None)
    mod = importlib.import_module("surfd")
    mod._test_db = db
    return mod


def plant(db, mapname, player, tier, millis, leg=0, runid="r", kind="run"):
    c = sqlite3.connect(db)
    c.execute("INSERT INTO replays (map, map_dir, track, leg, leaf, tier, style, player, name, ticks,"
              " tickrate, millis, flags, node, submitted, kind, runid) VALUES (?,?,0,?,?,?,'clean',?,?,?,100,?,0,'n',1,?,?)",
              (mapname, mapname, leg, "%s_%s_%d.rec" % (player, tier.replace(":", "-"), millis), tier, player,
               player, millis // 10, millis, kind, runid))
    rid = c.execute("SELECT last_insert_rowid()").fetchone()[0]
    c.execute("INSERT INTO runs (map, track, leg, tier, style, player, name, ticks, tickrate, millis,"
              " flags, node, runid, submitted, replay_id) VALUES (?,0,?,?,'clean',?,?,?,100,?,0,'n',?,1,?)",
              (mapname, leg, tier, player, player, millis // 10, millis, runid, rid))
    c.commit()
    c.close()
    return rid


def tiers(db, table, mapname):
    c = sqlite3.connect(db)
    try:
        return sorted(r[0] for r in c.execute("SELECT tier FROM %s WHERE map = ?" % table, (mapname,)))
    finally:
        c.close()


def run(db, *args):
    import boardarchive
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = boardarchive.main(["--db", db] + list(args))
    return code, out.getvalue().strip()


m = fresh()
db = m._test_db
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
rid_a = plant(db, "surf_x", "alice", "ranked", 40000)
plant(db, "surf_x", "bob", "community", 41000)
plant(db, "surf_x", "carol", "ranked@rC", 9000, leg=1, runid="rC")
plant(db, "surf_x", "eve", "banned:ranked", 39000)
check("control: before archiving, surf_x's ranked board has alice",
      [r.get("player", r.get("name")) for r in (m.app.test_client().get("/api/board?map=surf_x&tier=ranked").get_json() or {})["rows"]][:1] != [], True)
plant(db, "surf_x", "mo", "momentum", 38000)
plant(db, "surf_y", "dan", "ranked", 30000)
before = tiers(db, "runs", "surf_x")

print("--- dry run ---")
code, msg = run(db, "archive", "--map", "surf_x", "--label", "surf")
check("dry run answers 0", code, 0)
check("dry run counts 4 rows / 4 recordings", "4 rows / 4 recordings" in msg, True)
check("dry run writes nothing", tiers(db, "runs", "surf_x"), before)

print("--- archive ---")
code, msg = run(db, "archive", "--map", "SURF_X", "--label", "surf", "--apply")
check("archive answers 0", code, 0)
check("runs parked, imported untouched", tiers(db, "runs", "surf_x"),
      ["banned:mode:surf:ranked", "mode:surf:community", "mode:surf:ranked", "mode:surf:ranked@rC", "momentum"])
check("recordings parked the same", tiers(db, "replays", "surf_x"),
      ["banned:mode:surf:ranked", "mode:surf:community", "mode:surf:ranked", "mode:surf:ranked@rC", "momentum"])
check("another map untouched", tiers(db, "runs", "surf_y"), ["ranked"])
check("the log has the line", "archive surf_x parked 4 rows" in open(os.path.join(os.path.dirname(db), "boardarchive.log")).read(), True)
rows_of = lambda mp: (m.app.test_client().get("/api/board?map=%s&tier=ranked" % mp).get_json() or {})["rows"]
check("control: surf_y's live ranked row is on its board", len(rows_of("surf_y")), 1)
check("the ranked board of surf_x shows no parked row", len(rows_of("surf_x")), 0)
c = m.connect()
with c:
    res = m.restand(c, rid_a)
check("restand on a parked replay stays in the parked family", tiers(db, "runs", "surf_x").count("mode:surf:ranked"), 1)
code, msg = run(db, "archive", "--map", "surf_x", "--label", "surf", "--apply")
check("nothing live: archive refused", code, 1)

print("--- a ban nests outside the park ---")
c = m.connect()
with c:
    m.accounts.ban_rows(c, "eve", False, m.TIERS_IMPORTED)
check("unban strips banned: only", "mode:surf:ranked" in tiers(db, "runs", "surf_x")
      and "banned:mode:surf:ranked" not in tiers(db, "runs", "surf_x"), True)

print("--- new runs, then restore ---")
plant(db, "surf_x", "alice", "ranked", 35000, runid="rN")
code, msg = run(db, "archive", "--map", "surf_x", "--label", "surf", "--apply")
check("a label in use is refused", (code, "already holds" in msg), (1, True))
code, msg = run(db, "restore", "--map", "surf_x", "--label", "surf", "--apply")
check("restore with live rows is refused", (code, "--park-live-as" in msg), (1, True))
code, msg = run(db, "restore", "--map", "surf_x", "--label", "surf", "--park-live-as", "bhop")
check("restore dry run writes nothing", tiers(db, "runs", "surf_x").count("ranked"), 1)
code, msg = run(db, "restore", "--map", "surf_x", "--label", "surf", "--park-live-as", "bhop", "--apply")
check("restore with --park-live-as answers 0", code, 0)
check("the swap is exact", tiers(db, "runs", "surf_x"),
      ["community", "mode:bhop:ranked", "momentum", "ranked", "ranked", "ranked@rC"])
code, msg = run(db, "list", "--map", "surf_x")
check("list names live and the bhop label", ("live" in msg, "label bhop" in msg), (True, True))
code, msg = run(db, "archive", "--map", "surf_x", "--label", "Bad:Label")
check("a bad label is refused", code, 2)

print("--- a review cleared while parked is named on restore ---")
rid_f = plant(db, "surf_r", "fay", "ranked", 50000, runid="rF")
plant(db, "surf_r", "fay", "ranked@rF", 9000, leg=1, runid="rF")
c = sqlite3.connect(db)
c.execute("UPDATE replays SET bound = 1 WHERE id = ?", (rid_f,))
c.execute("INSERT INTO reviews (replay_id, decision, at) VALUES (?, 'reject', 5)", (rid_f,))
c.commit()
code, msg = run(db, "restore", "--map", "surf_r", "--label", "zz")
check("control: nothing parked as zz", code, 1)
code, msg = run(db, "archive", "--map", "surf_r", "--label", "surf", "--apply")
check("archive with a rejected run's hidden stage", code, 0)
c.execute("DELETE FROM reviews WHERE replay_id = ?", (rid_f,))
c.commit()
c.close()
code, msg = run(db, "restore", "--map", "surf_r", "--label", "surf", "--apply")
check("restore answers 0", code, 0)
check("restore names the run whose stage stays hidden", "run rF (fay, track 0) are hidden" in msg, True)
code, msg = run(db, "archive", "--map", "surf+plus", "--label", "surf")
check("a '+' map name is accepted (nothing live there)", (code, "no live WOS times" in msg), (1, True))

print("\n%d failed" % len(FAILED) if FAILED else "\nall passed")
sys.exit(1 if FAILED else 0)
