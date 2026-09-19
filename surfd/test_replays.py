#!/usr/bin/env python3
"""
test_replays.py -- the falsifier for the replay ledger (schema 3).

Run it anywhere Flask is installed, against a THROWAWAY home directory:

    SURFD_HOME=/tmp/surfd-test python3 test_replays.py

It never touches a live instance: every case re-imports surfd with a fresh
SURFD_HOME, its own DB and its own env file -- the same harness test_board.py
and test_surfd.py use, and for the same reason.

WHAT IT IS FOR.  Since build 66 the lobbies DELETE NOTHING: rec_runs_keep 0
returns out of SV_RecPrune before it opens the directory, so every finish keeps
its .rec forever.  `runs` cannot represent that, and was never meant to -- its
primary key is the board key plus the player, and an improvement OVERWRITES the
row that described the run it beat.  So without a second table the bytes of a
beaten run survive on disk while the only record of whose run they were, under
what name, on which board, is gone.  A kept file nothing can attribute is not
kept in any useful sense.

The cases that matter are therefore the ones where the ledger would LOSE a
recording or POINT AT THE WRONG ONE:

  * a beaten run losing its row when the player improves (s1),
  * an exact tie -- which is a FILE collision, not just a row one, because
    SV_RecClose does fremove(dst) then frename -- leaving a row that describes
    bytes that are not there (s2),
  * the board row pointing at the file of a run it did not describe (s3),
  * a superseded file's slug being unrecoverable because runs.name moved on,
    which is the concrete reason the leaf is SENT and never DERIVED (s4),
  * a path built from the lowercased board key, which misses every recording on
    the six capitalised maps in the library, silently, and reads as "no
    replay" (s5) -- the defect three independent designs all shipped,
  * a filename from the wire reaching a path (s7),
  * a legitimate leaf shape being refused and quietly zeroing those rows (s8),
  * a run being REFUSED because of anything to do with an index (s7, s8, s9).

Section 11 exercises the 2 -> 3 upgrade against a seeded v2 database, because
surfd migrates at import time and a database created afterwards is never a v2
one.  Section 12 pins the leaf grammar against src/shared/sh_defs.qc itself:
every check in this file is arithmetic on a filename that QC builds, and a
change there would silently stop the ledger indexing anything rather than fail.
"""

import hashlib
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


def fresh(key="testkey", seed_v2=False):
    """Import surfd with a clean home dir.

    `seed_v2` builds a schema-2 database, with the board rows a live instance
    would already hold, BEFORE the import -- the only way to exercise the
    2 -> 3 upgrade, since surfd migrates at import time.
    """
    home = tempfile.mkdtemp(prefix="surfd-replay-")
    db = os.path.join(home, "test.db")
    with open(os.path.join(home, "surfd.env"), "w") as fh:
        fh.write("SURFD_KEY=%s\n" % key)

    if seed_v2:
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
            CREATE TABLE runs (
                map        TEXT    NOT NULL,
                track      INTEGER NOT NULL,
                leg        INTEGER NOT NULL,
                tier       TEXT    NOT NULL,
                style      TEXT    NOT NULL,
                player     TEXT    NOT NULL,
                name       TEXT    NOT NULL,
                ticks      INTEGER NOT NULL,
                tickrate   REAL    NOT NULL,
                millis     INTEGER NOT NULL,
                flags      INTEGER NOT NULL,
                node       TEXT    NOT NULL,
                runid      TEXT    NOT NULL,
                submitted  INTEGER NOT NULL,
                PRIMARY KEY (map, track, leg, tier, style, player)
            );
            INSERT INTO runs VALUES
                ('surf_test',0,0,'ranked','clean','old','Old',
                 5000,66.666667,75000,0,'b64probe','b64s2-p_bob',2000000000);
            PRAGMA user_version=2;
            """
        )
        conn.commit()
        conn.close()

    # The run tree is per-case too, and it MUST be set before the import:
    # RUNS_DIR is a module constant read once at import time, which is exactly
    # what stops a test ever reaching the live /srv/nvme default.
    runs = os.path.join(home, "runs")
    os.makedirs(runs, exist_ok=True)

    os.environ["SURFD_HOME"] = home
    os.environ["SURFD_DB"] = db
    os.environ["SURFD_RUNS"] = runs
    os.environ["SURFD_ENV"] = os.path.join(home, "surfd.env")
    os.environ.pop("SURFD_PUBLIC_HOST", None)
    os.environ.pop("SURFD_TRUSTED", None)
    sys.modules.pop("surfd", None)
    mod = importlib.import_module("surfd")
    mod._test_home = home
    mod._test_db = db
    mod._test_runs = runs
    return mod


def put_rec(mod, map_dir, track, leg, leaf_name, body):
    """Write a recording where a lobby on this box would have left it."""
    d = os.path.join(mod._test_runs, map_dir, mod.leg_dir(track, leg))
    os.makedirs(d, exist_ok=True)
    path = os.path.join(d, leaf_name)
    # newline="" OR THIS TEST CANNOT MEAN WHAT IT SAYS ON WINDOWS.  Text mode
    # translates every \n to \r\n on this platform, so section 13's "the file's
    # exact bytes" check was comparing the route's faithful output against bytes
    # the HARNESS had rewritten -- it failed on Windows and passed on the Pi, for
    # a defect that exists in neither.  A fixture that differs by platform makes
    # a byte-exactness claim untestable on exactly one of them, which is worse
    # than not making it.
    with open(path, "w", encoding="utf-8", newline="") as fh:
        fh.write(body)
    return path


def fetch(mod, rid, src="127.0.0.1"):
    """GET /api/replay/<rid>. Returns (status, body-bytes)."""
    resp = mod.app.test_client().get(
        "/api/replay/%s" % rid, environ_base={"REMOTE_ADDR": src})
    return resp.status_code, resp.data


def who(player, slug="alice"):
    """FS_PlayerSeg(netname, guid) as the game builds it.

    Recomputed here from the SAME guid surfd is sent, which is the property
    that makes surfd's own digest check possible -- and this test is where the
    two implementations of it are compared.
    """
    ident = hashlib.sha256(player.encode("utf-8")).hexdigest()[:8]
    return ("%s-%s" % (slug, ident)) if slug else ident


def leaf(ticks, player="alice", slug="alice", tag="run"):
    """FS_RunLeaf(ticks, who, tag, "rec")."""
    seg = who(player, slug)
    return "%s_%s_%s.rec" % (str(int(ticks)).zfill(7), seg, tag)


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
    args = {"map": "surf_test"}
    args.update({k: str(v) for k, v in kw.items()})
    resp = mod.app.test_client().get(
        "/api/board", query_string=args, environ_base={"REMOTE_ADDR": src}
    )
    if resp.status_code != 200:
        return "HTTP %d" % resp.status_code
    return resp.get_json()


def rows(mod, sql, args=()):
    conn = sqlite3.connect(mod._test_db)
    conn.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in conn.execute(sql, args).fetchall()]
    finally:
        conn.close()


def one(mod, sql, args=()):
    got = rows(mod, sql, args)
    return got[0] if got else None


def user_version(mod):
    conn = sqlite3.connect(mod._test_db)
    try:
        return conn.execute("PRAGMA user_version").fetchone()[0]
    finally:
        conn.close()


QC = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                  "..", "src", "shared", "sh_defs.qc")


# --------------------------------------------------------------------------
print("\n--- 1. a beaten run keeps its own row ------------------------------")

m = fresh()
slow = leaf(6000)
fast = leaf(4108)
submit(m, ticks=6000, rec=slow)
submit(m, ticks=4108, rec=fast)

check("both recordings are in the ledger",
      [r["leaf"] for r in rows(m, "SELECT leaf FROM replays ORDER BY ticks")],
      [fast, slow])
check("...and the board still holds one row for the player",
      len(rows(m, "SELECT 1 FROM runs")), 1)
check("...and the beaten run kept its own ticks",
      one(m, "SELECT ticks FROM replays WHERE leaf=?", (slow,))["ticks"], 6000)

# The control. Without it this section could pass on a ledger that indexes
# every submission regardless of whether a file was named.
m2 = fresh()
submit(m2, ticks=6000)
submit(m2, ticks=4108)
check("CONTROL: a run that names no file is not indexed",
      len(rows(m2, "SELECT 1 FROM replays")), 0)
check("...and is still on the board",
      len(rows(m2, "SELECT 1 FROM runs")), 1)


# --------------------------------------------------------------------------
print("\n--- 2. an exact tie is recorded and does not move the board --------")

m = fresh()
submit(m, ticks=4108, rec=leaf(4108))
first = one(m, "SELECT replay_id FROM runs")["replay_id"]
# A tie from another lobby: same time, a file of its own because the other
# player's id differs.  SV_RecClose would have overwritten the name only if it
# were the SAME player on the SAME leg -- that case is section 6.
tied = leaf(4108, player="bob", slug="bob")
submit(m, ticks=4108, player="bob", name="Bob", node="p27540", rec=tied)

check("the tie has its own ledger row",
      len(rows(m, "SELECT 1 FROM replays")), 2)
check("...and did not disturb the standing row's handle",
      one(m, "SELECT replay_id FROM runs WHERE player='alice'")["replay_id"],
      first)
check("...and the tied player got a row of their own",
      one(m, "SELECT leaf FROM replays WHERE player='bob'")["leaf"], tied)


# --------------------------------------------------------------------------
print("\n--- 3. the board row points at the STANDING run's file -------------")

m = fresh()
submit(m, ticks=6000, rec=leaf(6000))
beaten = one(m, "SELECT id FROM replays WHERE ticks=6000")["id"]
submit(m, ticks=4108, rec=leaf(4108))
standing = one(m, "SELECT id FROM replays WHERE ticks=4108")["id"]
held = one(m, "SELECT replay_id FROM runs")["replay_id"]

check("the standing row names the faster file", held, standing)
check("CONTROL: and NOT the file it beat", held == beaten, False)
check("the handle resolves to a leaf with the board row's ticks",
      one(m, "SELECT ticks FROM replays WHERE id=?", (held,))["ticks"], 4108)


# --------------------------------------------------------------------------
print("\n--- 4. a superseded run keeps the name that built its filename -----")

m = fresh()
submit(m, ticks=6000, name="^1lex", rec=leaf(6000))
submit(m, ticks=4108, name="notlex", rec=leaf(4108))

check("the beaten run remembers the netname it was set under",
      one(m, "SELECT name FROM replays WHERE ticks=6000")["name"], "^1lex")
check("CONTROL: while the board row has moved on",
      one(m, "SELECT name FROM runs")["name"], "notlex")
check("...and the improving run recorded its own name too",
      one(m, "SELECT name FROM replays WHERE ticks=4108")["name"], "notlex")


# --------------------------------------------------------------------------
print("\n--- 5. map case reaches the PATH and not the KEY -------------------")
# Six maps in the shipped library are capitalised (Bhop_Mukiology, bhop_HaddocK,
# bhop_HeLL, bhop_addict_V2, surf_Rebel_Resistance_Revamp,
# surf_prottos_NightMare).  ext4 is case-sensitive and the game builds
# data/runs/<mapname>/ from the engine's untouched spelling, so a path rebuilt
# from the lowercased board key misses every recording on them -- silently, and
# it reads as "this run has no replay".

m = fresh()
submit(m, map="Bhop_Mukiology", ticks=4108, rec=leaf(4108))
r = one(m, "SELECT map, map_dir FROM replays")

check("the ledger's board key is lowercased", r["map"], "bhop_mukiology")
check("...and its PATH component keeps the disk's spelling",
      r["map_dir"], "Bhop_Mukiology")
check("the board row is under the lowercased key",
      one(m, "SELECT map FROM runs")["map"], "bhop_mukiology")

# The control that proves the key still MERGES the two spellings -- which is
# what clean_map's lowercasing is for, and must not be broken by fixing the path.
submit(m, map="bhop_mukiology", ticks=3000, rec=leaf(3000))
check("CONTROL: the other spelling lands on the SAME board row",
      len(rows(m, "SELECT 1 FROM runs WHERE map='bhop_mukiology'")), 1)
check("...and is a second, separate recording",
      len(rows(m, "SELECT 1 FROM replays")), 2)


# --------------------------------------------------------------------------
print("\n--- 6. the same filename twice UPSERTS, never duplicates -----------")
# SV_RecClose does fremove(dst) then frename(part, dst), so the same player
# finishing the same leg on the same tick count REPLACES the bytes.  Two rows
# for one file would mean one of them describes bytes that are not there.

m = fresh()
same = leaf(4108)
submit(m, ticks=4108, rec=same, node="p27510")
submit(m, ticks=4108, name="Alice2", rec=same, node="p27540")

check("one file, one row", len(rows(m, "SELECT 1 FROM replays")), 1)
r = one(m, "SELECT node, name FROM replays")
check("...describing the bytes that survived (node)", r["node"], "p27540")
check("...and the name that wrote them", r["name"], "Alice2")

submit(m, ticks=4109, rec=leaf(4109))
check("CONTROL: a different leaf in the same directory is a second row",
      len(rows(m, "SELECT 1 FROM replays")), 2)


# --------------------------------------------------------------------------
print("\n--- 7. a hostile or wrong leaf is dropped, the RUN is not ----------")

for label, bad in (
    ("traversal", "../../../etc/passwd"),
    ("a path separator", "0004108_alice-11111111_run/x.rec"),
    ("an over-long slug", "0004108_" + "a" * 20 + "-11111111_run.rec"),
    ("an unarchived tag", "0004108_alice-11111111_cheat.rec"),
    ("a fixed name", "alice-11111111_last.rec"),
    ("the wrong extension", "0004108_alice-11111111_run.view"),
):
    m = fresh()
    got = submit(m, ticks=4108, rec=bad)
    stored = isinstance(got, dict) and got.get("stored") is True
    check("%s: the run is still stored" % label, stored, True)
    check("...and nothing is indexed",
          len(rows(m, "SELECT 1 FROM replays")), 0)
    check("...and the row reports no replay",
          one(m, "SELECT replay_id FROM runs")["replay_id"], 0)

# The stamp check: SV_RecClose stamps the file with the same `ticks` it then
# submits, so a disagreement means one of the two is wrong and the row must not
# claim the file.
m = fresh()
submit(m, ticks=4108, rec=leaf(9999))
check("a stamp that disagrees with ticks is refused",
      len(rows(m, "SELECT 1 FROM replays")), 0)
check("CONTROL: the matching stamp is accepted", True, True)
m = fresh()
submit(m, ticks=4108, rec=leaf(4108))
check("...proved by the same submission with the right stamp",
      len(rows(m, "SELECT 1 FROM replays")), 1)


# --------------------------------------------------------------------------
print("\n--- 8. every shape FS_RunLeaf can emit is accepted -----------------")
# SV_RecWho returns slug-id, a bare id when the netname slugs to nothing,
# "s<slot>" when the GUID is empty, and "" whenever Lobby_Active() is false.
# A pattern that demanded the 8 hex would have zeroed every row from the last
# two cases in silence.

ident = hashlib.sha256(b"alice").hexdigest()[:8]
for label, name in (
    ("slug and id", "0004108_alice-%s_run.rec" % ident),
    ("a bare id (name slugs to nothing)", "0004108_%s_run.rec" % ident),
    ("the s<slot> fallback (no guid)", "0004108_s3_run.rec"),
    ("no who at all (lobby_enable 0)", "0004108_run.rec"),
    ("a pb", "0004108_alice-%s_pb.rec" % ident),
    ("a shadow", "0004108_alice-%s_shadow.rec" % ident),
    ("a stamp longer than 7 digits", "12345678_alice-%s_run.rec" % ident),
):
    m = fresh()
    ticks = 12345678 if "longer" in label else 4108
    submit(m, ticks=ticks, rec=name)
    check("accepted: %s" % label,
          len(rows(m, "SELECT 1 FROM replays")), 1)

m = fresh()
submit(m, ticks=4108, rec="0004108_ALICE-%s_run.rec" % ident.upper())
check("CONTROL: an uppercase who is refused (FS_NameSlug is lowercase)",
      len(rows(m, "SELECT 1 FROM replays")), 0)


# --------------------------------------------------------------------------
print("\n--- 9. an untrusted source files a time but never a path -----------")
# Port 8084 answers the internet with the shared key as its only barrier.  A
# filesystem path is only evidence for a node we own.

m = fresh()
got = submit(m, src="203.0.113.9", ticks=4108, rec=leaf(4108))
check("the run is stored", isinstance(got, dict) and got.get("stored"), True)
check("...but no path was taken from it",
      len(rows(m, "SELECT 1 FROM replays")), 0)
check("...and the row says so", one(m, "SELECT replay_id FROM runs")["replay_id"], 0)

m = fresh()
submit(m, src="127.0.0.1", ticks=4108, rec=leaf(4108))
check("CONTROL: the identical submission from a trusted source is indexed",
      len(rows(m, "SELECT 1 FROM replays")), 1)


# --------------------------------------------------------------------------
print("\n--- 10. the board carries the handle -------------------------------")

m = fresh()
submit(m, ticks=4108, rec=leaf(4108))
rid = one(m, "SELECT replay_id FROM runs")["replay_id"]
body = board(m)
row = body["rows"][0]

check("the row carries rep", row.get("rep"), rid)
check("...and rep is not zero", rid > 0, True)
check("the existing row keys are untouched",
      sorted(row.keys()),
      sorted(["r", "player", "name", "ticks", "rate", "ms", "flags", "when",
              "rep", "run", "ver"]))
check("...in their documented order, with ver last", list(row.keys()),
      ["r", "player", "name", "ticks", "rate", "ms", "flags", "when", "rep",
       "run", "ver"])

# A missing recording must never hide a time -- and this also catches the
# failure where a column is added to the row dict but not to the SELECT, which
# raises KeyError inside board()'s own `except sqlite3.Error` and returns an
# EMPTY board rather than an error.
m = fresh()
submit(m, ticks=4108)
body = board(m)
check("a run with no recording still appears on the board",
      len(body["rows"]), 1)
check("...reporting rep 0", body["rows"][0]["rep"], 0)


# --------------------------------------------------------------------------
print("\n--- 11. the 2 -> 3 migration adds and does not rebuild -------------")

m = fresh()
check("a fresh database is stamped schema 6", user_version(m), 6)
check("...and SCHEMA_VERSION agrees", m.SCHEMA_VERSION, 6)

m = fresh(seed_v2=True)
check("a schema-2 database upgrades to 6", user_version(m), 6)
check("...keeping the board rows it already held",
      [r["player"] for r in rows(m, "SELECT player FROM runs")], ["old"])
check("...defaulting them to no replay",
      one(m, "SELECT replay_id FROM runs")["replay_id"], 0)
check("...and the ledger starts empty",
      len(rows(m, "SELECT 1 FROM replays")), 0)

cols = [r["name"] for r in rows(m, "PRAGMA table_info(runs)")]
check("the runs table gained exactly one column", "replay_id" in cols, True)
check("...and kept its primary key",
      [r["name"] for r in rows(m, "PRAGMA table_info(runs)") if r["pk"]],
      ["map", "track", "leg", "tier", "style", "player"])

fresh_cols = [r["name"] for r in rows(fresh(), "PRAGMA table_info(runs)")]
check("CONTROL: a fresh database has the identical runs shape",
      fresh_cols, cols)


# --------------------------------------------------------------------------
print("\n--- 12. the leaf grammar is pinned to the QC that builds it --------")
# Every check above is arithmetic on a filename the GAME builds.  If sh_defs.qc
# changes the shape, this suite would keep passing against its own fixtures
# while the ledger silently indexed nothing in production.

if not os.path.exists(QC):
    print("skip  src/shared/sh_defs.qc not beside this checkout")
else:
    qc = open(QC, encoding="utf-8", errors="replace").read()

    def define(nm):
        hit = re.search(r"#define\s+%s\s+(\d+)" % nm, qc)
        return int(hit.group(1)) if hit else None

    check("FS_WHO_IDLEN is the 8 hex the pattern expects", define("FS_WHO_IDLEN"), 8)
    check("FS_WHO_NAMEMAX is the 12 the pattern allows", define("FS_WHO_NAMEMAX"), 12)

    # FS_RunStamp pads to 7.
    hit = re.search(r"FS_RunStamp\s*=\s*\{.*?strlen\(s\)\s*<\s*(\d+)", qc, re.S)
    check("FS_RunStamp left-pads to 7", int(hit.group(1)) if hit else None, 7)

    # FS_NameSlug keeps only [a-z0-9]: 48-57 and 97-122.
    hit = re.search(r"FS_NameSlug\s*=\s*\{(.*?)\n\};", qc, re.S)
    body = hit.group(1) if hit else ""
    check("FS_NameSlug keeps digits only via 48..57",
          ("ch >= 48" in body and "ch <= 57" in body), True)
    check("...and lowercase only via 97..122",
          ("ch >= 97" in body and "ch <= 122" in body), True)

    # FS_TagArchived's set is exactly what the ledger's pattern accepts.
    hit = re.search(r"FS_TagArchived\s*=\s*\{(.*?)\n\};", qc, re.S)
    body = hit.group(1) if hit else ""
    archived = set(re.findall(r"tag == (RT_[A-Z]+)\)\s*return TRUE", body))
    check("FS_TagArchived is exactly PB, SHADOW, RUN, LOBBY",
          archived, {"RT_PB", "RT_SHADOW", "RT_RUN", "RT_LOBBY"})

    # RT_LOBBY is archived but is written by the CLIENT to its own disk, so it
    # never reaches a lobby's data/runs and is deliberately not in the pattern.
    import surfd as _s
    for tag, want in (("run", True), ("pb", True), ("shadow", True),
                      ("lobby", False), ("last", False), ("cheat", False)):
        nm = "0004108_alice-%s_%s.rec" % (ident, tag)
        check("pattern accepts %-7s == %s" % (tag, want),
              bool(_s._LEAF_OK.match(nm)), want)


# --------------------------------------------------------------------------
print("\n--- 13. the download route serves the row, and only the row -------")
# R4.  The board hands out `rep`; this is what `rep` is worth.  The cases are
# the ones where the route would serve THE WRONG FILE or refuse a real one --
# and the one where it would serve a file from outside the run tree, which is
# the only genuinely dangerous thing in this feature.

m = fresh()
BODY = "FTESURF-REC 4\nmap surf_test\nowner Alice\n" + ("x 1 2 3\n" * 400)

# The whole journey a player takes: finish -> board row -> click -> bytes.
got = submit(m, ticks=4108, rec=leaf(4108))
put_rec(m, "surf_test", 0, 0, leaf(4108), BODY)
rid = got["rep"]
check("a finish hands back a replay handle", rid, 1)

b = board(m)
check("the board row carries the same handle", b["rows"][0]["rep"], rid)

st, data = fetch(m, rid)
check("fetching it returns 200", st, 200)
check("...with the file's exact bytes", data.decode("utf-8"), BODY)
check("...and the byte count agrees with the disk", len(data), len(BODY))

# An id nobody issued.  404 and not 500, and not a stack trace.
check("an unknown id is 404", fetch(m, 9999)[0], 404)
check("id 0 -- what a row with no replay carries -- is 404",
      fetch(m, 0)[0], 404)

# A row whose file is gone.  This is the drift case: nothing prunes, so it
# should not happen, and the route must still say so rather than 500.
os.remove(os.path.join(m._test_runs, "surf_test", "main", leaf(4108)))
st, data = fetch(m, rid)
check("an indexed row whose file is gone is 404", st, 404)
check("...and says it is the FILE that is missing, not the row",
      json.loads(data)["error"], "replay not on this node")
put_rec(m, "surf_test", 0, 0, leaf(4108), BODY)          # control: restored
check("...and the same id works again once the file is back",
      fetch(m, rid)[0], 200)

# CONTAINMENT.  A leaf that passes the grammar but resolves outside the tree.
# A symlink is the only way to build one -- which is the point: the handle is
# an integer, so there is no attacker-supplied path component at all, and this
# tests the second lock rather than the first.
m2 = fresh()
submit(m2, ticks=4108, rec=leaf(4108))
outside = os.path.join(m2._test_home, "not-a-replay.txt")
with open(outside, "w") as fh:
    fh.write("SECRET")
link_dir = os.path.join(m2._test_runs, "surf_test", "main")
os.makedirs(link_dir, exist_ok=True)
link = os.path.join(link_dir, leaf(4108))
try:
    os.symlink(outside, link)
except (OSError, NotImplementedError, AttributeError):
    print("skip  symlinks unavailable here (containment untested)")
else:
    # The control: the target really is readable, so a 404 below is the guard
    # doing its job and not the file merely being absent.
    check("control -- the escape target is readable",
          open(link).read(), "SECRET")
    st, data = fetch(m2, 1)
    check("a leaf resolving outside the run tree is refused", st, 404)
    check("...and its contents are never in the body", b"SECRET" in data, False)

# MAP CASE, again -- the defect three designs shipped.  The row's map_dir is
# the capitalised spelling; the board key is the lowercased one.
m3 = fresh()
submit(m3, map="Bhop_Mukiology", ticks=4108, rec=leaf(4108))
put_rec(m3, "Bhop_Mukiology", 0, 0, leaf(4108), BODY)
r = one(m3, "SELECT map, map_dir FROM replays")
check("the row keeps both spellings", (r["map"], r["map_dir"]),
      ("bhop_mukiology", "Bhop_Mukiology"))
check("and the route finds the capitalised directory", fetch(m3, 1)[0], 200)

# A leg that is not the main track, so leg_dir is actually exercised.
m4 = fresh()
submit(m4, track=2, leg=3, ticks=4108, rec=leaf(4108))
put_rec(m4, "surf_test", 2, 3, leaf(4108), BODY)
check("a bonus-track stage files under bonus_2_stage_3",
      os.path.isdir(os.path.join(m4._test_runs, "surf_test", "bonus_2_stage_3")),
      True)
check("...and the route follows it there", fetch(m4, 1)[0], 200)

# The limiter.  A public route that moves ~1 MB a call needs one, and a cap
# that never fires is not a cap.
m5 = fresh()
submit(m5, ticks=4108, rec=leaf(4108))
put_rec(m5, "surf_test", 0, 0, leaf(4108), BODY)
codes = [fetch(m5, 1, src="10.0.0.9")[0]
         for _ in range(m5.REPLAY_RATE_MAX + 2)]
check("the first fetch is served", codes[0], 200)
check("the cap eventually refuses", codes[-1], 429)
check("...exactly at REPLAY_RATE_MAX", codes.count(200), m5.REPLAY_RATE_MAX)
check("and a different source is unaffected",
      fetch(m5, 1, src="10.0.0.10")[0], 200)

# A run with no recording must still file a TIME, and its row must be
# unclickable rather than broken.
m6 = fresh()
got = submit(m6, ticks=4108, rec="")
check("a finish with no recording still ranks", got["ok"], True)
check("...and carries no handle", got["rep"], 0)
check("...and the board says so", board(m6)["rows"][0]["rep"], 0)


# --------------------------------------------------------------------------
print("\n--- 14. leg_dir is pinned to the QC that names the directory ------")
# surfd rebuilds a path the GAME chose the spelling of.  Two independent
# spellings of one directory is how every recording on a bonus track goes
# missing while every row still says it is there.

if not os.path.exists(QC):
    print("skip  src/shared/sh_defs.qc not beside this checkout")
else:
    qc = open(QC, encoding="utf-8", errors="replace").read()
    hit = re.search(r"FS_LegDir\s*=\s*\{(.*?)\n\};", qc, re.S)
    body = hit.group(1) if hit else ""
    check("FS_LegDir spells the full run 'main'", '"main"' in body, True)
    check("...a stage 'stage_%g'", '"stage_%g"' in body, True)
    check("...a bonus 'bonus_%g'", '"bonus_%g"' in body, True)
    check("...and a bonus stage 'bonus_%g_stage_%g'",
          '"bonus_%g_stage_%g"' in body, True)

    import surfd as _s
    for (track, leg), want in (((0, 0), "main"), ((0, 4), "stage_4"),
                               ((1, 0), "bonus_1"), ((2, 3), "bonus_2_stage_3")):
        check("leg_dir(%d,%d) == %s" % (track, leg, want),
              _s.leg_dir(track, leg), want)


# --------------------------------------------------------------------------
print("")
if FAILED:
    print("%d FAILURE(S):" % len(FAILED))
    for f in FAILED:
        print("  " + f)
    sys.exit(1)
print("all replay-ledger checks passed")
