#!/usr/bin/env python3
"""
test_evidence.py -- the falsifier for schema 6's evidence behind stage rows.

    SURFD_HOME=/tmp/surfd-test python3 test_evidence.py

A main run posts each stage with its runid and no recording.  When that run is
abandoned (or ends unarchived) the only file is the lobby's
data/evidence/<map>/<runid>.rec, swept after run_evidence_days; surfd indexes
it as a kind 'evidence' replay, hard-links it under SURFD_KEEP and hands it out
as the stage row's `run`.  Every case imports surfd against a throwaway home,
run tree and evidence tree; nothing touches a live instance.
"""

import hashlib
import importlib
import os
import sqlite3
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

FAILED = []


def check(label, got, want):
    ok = got == want
    print("%-4s %-64s %r" % ("ok" if ok else "FAIL", label, got))
    if not ok:
        FAILED.append("%s: got %r, want %r" % (label, got, want))


R = "20260918-142825-0-p27510"          # the live surf_aser abandon
R2 = "20260918-154615-1-p27520"
R3 = "20260918-160000-0-p27510"
PW = "correct horse battery"


def evbody(runid, mapname="surf_Aser", track=0, leg=0, end=True):
    """A v9 file shaped like the live surf_aser abandon: ~54 KB, so the tail
    scan starts mid-line."""
    head = ("FTESURF-REC 9\nmap %s\ntrack %d\nstartseg 0\nleg %d\n"
            "tickrate 0.015\nmovetickrate 0.015\nclock counted\nowner Kap\n"
            "runid %s\nflags 0         \nbegin\n" % (mapname, track, leg, runid))
    rows = "".join("%.4f 1.00 2.00 3.00 0.00 0.00 0.00 0.0 0.0 1\n" % (i * 0.015)
                   for i in range(1200))
    rows += "stagestart 1 1838\nstagepost 1 454\nstage 2 2292\n"
    tail = ("abandon 8262\ninend 8744 0.009\n"
            "end 8262 8519 256 0 8262 4 1 0 1 0\n") if end else ""
    return head + rows + tail


def leaf(ticks, player):
    return "%07d_%s_run.rec" % (ticks, hashlib.sha256(player.encode()).hexdigest()[:8])


def fresh(admin_pw=None, keep=None):
    home = tempfile.mkdtemp(prefix="surfd-evidence-")
    data = os.path.join(home, "game", "ftesurf", "data")
    os.makedirs(os.path.join(data, "runs"))
    os.makedirs(os.path.join(data, "evidence"))
    with open(os.path.join(home, "surfd.env"), "w") as fh:
        fh.write("SURFD_KEY=testkey\n")
    os.environ.update(
        SURFD_HOME=home, SURFD_DB=os.path.join(home, "test.db"),
        SURFD_ENV=os.path.join(home, "surfd.env"),
        SURFD_RUNS=os.path.join(data, "runs"),
        SURFD_MAPS=os.path.join(home, "maps"), SURFD_ZONES=os.path.join(home, "zones"),
        SURFD_LOBBY_CFGS=os.path.join(home, "lobbycfg"),
        SURFD_GAME=os.path.join(home, "game"),
        SURFD_VERIFIER=os.path.join(home, "noengine"))
    for k in ("SURFD_EVIDENCE", "SURFD_KEEP", "SURFD_PUBLIC_HOST", "SURFD_TRUSTED",
              "SURFD_ADMIN_HASH", "SURFD_ADMIN_SECRET", "SURFD_RCON_PASSWORD",
              "SURFD_ADMIN_LOBBIES", "SURFD_ADMIN_INSECURE_COOKIE"):
        os.environ.pop(k, None)
    if keep == "same":                           # a misconfiguration, on purpose
        os.environ["SURFD_KEEP"] = os.path.join(data, "evidence")
    if admin_pw:
        import admin
        os.environ.update(SURFD_ADMIN_HASH=admin.hash_password(admin_pw, n=2 ** 10),
                          SURFD_ADMIN_SECRET="s" * 48, SURFD_ADMIN_INSECURE_COOKIE="1")
    for mod in ("surfd", "sweep", "admin", "rcon"):
        sys.modules.pop(mod, None)
    m = importlib.import_module("surfd")
    m._ev = os.path.join(data, "evidence")
    return m


def submit(m, player="kap", name="Kap", leg=0, ticks=4000, runid=R, rec=None,
           addr="127.0.0.1", **extra):
    form = {"key": "testkey", "map": "surf_Aser", "track": "0", "leg": str(leg),
            "player": player, "name": name, "ticks": str(ticks),
            "tickrate": "66.666667", "flags": "0", "node": "p27510"}
    form.update({k: str(v) for k, v in extra.items()})
    if runid is not None:                        # None: the lobby sent none
        form["runid"] = runid
    if rec:
        form["rec"] = rec
    return m.app.test_client().post("/api/run", data=form,
                                    environ_base={"REMOTE_ADDR": addr}).get_json()


def board(m, leg, path="/api/board"):
    r = m.app.test_client().get(path, query_string={"map": "surf_aser", "leg": leg},
                                environ_base={"REMOTE_ADDR": "127.0.0.1"})
    return r.get_json()


def by_player(m, leg):
    return {x["player"]: x for x in board(m, leg)["rows"]}


def fetch(m, rid):
    r = m.app.test_client().get("/api/replay/%d" % rid,
                                environ_base={"REMOTE_ADDR": "127.0.0.1"})
    return r.status_code, r.get_data()


def q(m, sql, args=()):
    conn = sqlite3.connect(m.DB_PATH)
    try:
        return [tuple(r) for r in conn.execute(sql, args).fetchall()]
    finally:
        conn.close()


def put_ev(m, name, body, d="surf_Aser", age=None):
    path = os.path.join(m._ev, d, name)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="\n") as fh:
        fh.write(body)
    if age is not None:
        t = time.time() - age
        os.utime(path, (t, t))
    return path


def put_run(m, name, body):
    """A main-leg recording under SURFD_RUNS, where a kind 'run' row names it."""
    path = os.path.join(m.RUNS_DIR, "surf_Aser", "main", name)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="\n") as fh:
        fh.write(body)
    return path


def evid(m, runid):
    got = q(m, "SELECT id FROM replays WHERE kind = 'evidence' AND runid = ?", (runid,))
    return got[0][0] if got else 0


def runid_of(m, rid):
    return q(m, "SELECT runid FROM replays WHERE id = ?", (rid,))


TORN = "abandon 8262\ninend 8744 0.009\nend "      # cut right after "end "


# --------------------------------------------------------------------------

def case_index_and_serve():
    """E1/E2: an abandoned run's evidence becomes its stage row's `run`"""
    m = fresh()
    check("E1 control: SURFD_EVIDENCE defaults beside SURFD_RUNS",
          getattr(m, "EVIDENCE_DIR", None), m._ev)
    check("E1 control: SURFD_KEEP defaults under SURFD_HOME",
          getattr(m, "KEEP_DIR", None),
          os.path.join(os.environ["SURFD_HOME"], "data", "evidence"))
    r = submit(m, leg=2, ticks=454)
    check("E1 the leg-2 stage row stores with rep 0", (r["stored"], r["rep"]), (True, 0))
    body = evbody(R)
    src = put_ev(m, R + ".rec", body, age=3600)
    conn = m.connect()
    got = m.index_evidence(conn)
    check("E1 index_evidence indexes one file",
          (got["indexed"], got["bad"], got["deferred"]), (1, 0, 0))
    row = q(m, "SELECT map, map_dir, track, leg, leaf, tier, style, checked, kind,"
               " runid, player, name, ticks, millis, node, bytes FROM replays"
               " WHERE kind = 'evidence'")
    check("E1 ...a leg-0 evidence row, map_dir as on disk, off every board, queued",
          row, [("surf_aser", "surf_Aser", 0, 0, R + ".rec", "", "", 0, "evidence",
                 R, "kap", "Kap", 8262, 123930, "p27510", len(body))])
    eid = evid(m, R)
    keep = os.path.join(m.KEEP_DIR, "surf_Aser", R + ".rec")
    check("E1 ...hard-linked under SURFD_KEEP (one inode)",
          os.path.exists(keep) and os.stat(keep).st_ino == os.stat(src).st_ino, True)
    b = by_player(m, 2)["kap"]
    check("E1 the leg-2 row: rep 0, run = the evidence row",
          (b["rep"], b.get("run")), (0, eid))
    check("E1 control: that id is a real row", eid > 0, True)
    st, data = fetch(m, eid)
    check("E1 /api/replay/<run> is 200 and byte-exact",
          (st, data == body.encode()), (200, True))
    check("E1 a second pass indexes nothing more", m.index_evidence(conn)["indexed"], 0)
    os.unlink(src)                                  # the lobby's SV_EvidenceSweep
    st, data = fetch(m, eid)
    check("E2 after the lobby sweeps its copy the replay still serves",
          (st, data == body.encode()), (200, True))
    check("E2 ...and the stage row still names it", by_player(m, 2)["kap"].get("run"), eid)


def case_what_is_not_indexed():
    """E3: only a well-formed file that backs a leafless stage row"""
    m = fresh()
    RB, RL = "20260918-142900-1-p27510", "20260918-142901-1-p27510"
    RD, RO = "20260918-143000-2-p27510", "20260918-143100-3-p27510"
    RU = "20260918-144000-4-p27510"
    submit(m, leg=2, ticks=454, runid=R)
    for who, rid in (("bb", RB), ("ll", RL), ("dd", RD), ("oo", RO)):
        submit(m, player=who, name=who, leg=2, ticks=500, runid=rid)
    put_ev(m, RU + ".rec", evbody(RU), age=3600)            # no stage row names it
    put_ev(m, "foo.rec", evbody(R), age=3600)               # not a runid
    put_ev(m, R + ";x.rec", evbody(R), age=3600)            # not a runid either
    put_ev(m, RB + ".rec", evbody(R), age=3600)             # header says another run
    put_ev(m, RL + ".rec", evbody(RL, leg=3), age=3600)     # not a leg-0 file
    fresh_rd = put_ev(m, RD + ".rec", evbody(RD, end=False))  # no `end`, just written
    put_ev(m, RO + ".rec", evbody(RO, end=False), age=700)  # no `end`, settled
    conn = m.connect()
    got = m.index_evidence(conn, now=int(time.time()))
    check("E3 one indexed, two bad, one deferred",
          (got["indexed"], got["bad"], got["deferred"]), (1, 2, 1))
    check("E3 ...the settled file with no `end`, ticks 0",
          q(m, "SELECT runid, ticks FROM replays WHERE kind = 'evidence'"), [(RO, 0)])
    kept = sorted(os.listdir(os.path.join(m.KEEP_DIR, "surf_Aser")))
    check("E3 ...and only it is kept", kept, [RO + ".rec"])
    check("E3 the file no stage row names is not indexed", evid(m, RU), 0)
    got = m.index_evidence(conn, now=int(os.stat(fresh_rd).st_mtime) + m.EVIDENCE_SETTLE + 1)
    check("E3 control: the deferred file is indexed once it has settled",
          (got["indexed"], evid(m, RD) > 0), (1, True))
    check("E3 control: kap's stage row really does name R",
          q(m, "SELECT runid FROM runs WHERE player = 'kap'"), [(R,)])


def case_gc():
    """E4: evidence no stage row references is dropped, file and all"""
    m = fresh()
    submit(m, leg=2, ticks=454, runid=R)
    submit(m, player="bob", name="Bob", leg=3, ticks=600, runid=R2)
    src = put_ev(m, R + ".rec", evbody(R), age=3600)
    put_ev(m, R2 + ".rec", evbody(R2), age=3600)
    conn = m.connect()
    check("E4 control: both files indexed", m.index_evidence(conn)["indexed"], 2)
    e1, e2 = evid(m, R), evid(m, R2)
    check("E4 control: gc with both still referenced drops nothing", m.gc_evidence(conn), 0)
    with conn:
        conn.execute("INSERT INTO verdicts (replay_id, verdict, reason, ticks, engine,"
                     " progs, at) VALUES (?, 'HOLD', 'x', -1, 'e', 'p', 1)", (e1,))
    submit(m, leg=2, ticks=400, runid=R3)             # kap's next run: faster stage 2
    main = submit(m, leg=0, ticks=4000, runid=R3, rec=leaf(4000, "kap"))["rep"]
    check("E4 the stage row now names the kept run",
          by_player(m, 2)["kap"].get("run"), main)
    check("E4 gc_evidence drops the one nothing references", m.gc_evidence(conn), 1)
    check("E4 ...its row and verdicts are gone",
          (q(m, "SELECT 1 FROM replays WHERE id = ?", (e1,)),
           q(m, "SELECT 1 FROM verdicts WHERE replay_id = ?", (e1,))), ([], []))
    check("E4 ...its kept link is gone",
          os.path.exists(os.path.join(m.KEEP_DIR, "surf_Aser", R + ".rec")), False)
    check("E4 ...and /api/replay/<id> is 404", fetch(m, e1)[0], 404)
    check("E4 control: the still-referenced evidence row survives and serves",
          (evid(m, R2) == e2, fetch(m, e2)[0], by_player(m, 3)["bob"].get("run")),
          (True, 200, e2))
    check("E4 control: the lobby's own copy is untouched",
          (os.path.exists(src), open(src).read() == evbody(R)), (True, True))

    d = os.path.join(m.KEEP_DIR, "surf_x")
    os.makedirs(d)
    old = os.path.join(d, "20260101-000000-0-p1.rec")
    new = os.path.join(d, "20260101-000001-0-p1.rec")
    tmp = os.path.join(d, "20260101-000002-0-p1.rec.tmp")
    for p, age in ((old, 7200), (new, 0), (tmp, 7200)):
        open(p, "w").write("x")
        os.utime(p, (time.time() - age, time.time() - age))
    m.gc_evidence(conn)
    check("E4 orphans: an hour-old kept file and .tmp go, a fresh one waits",
          (os.path.exists(old), os.path.exists(tmp), os.path.exists(new)),
          (False, False, True))


def case_keep_is_not_evidence():
    """E4b: SURFD_KEEP pointed at the lobbies' own tree never sweeps it"""
    m = fresh(keep="same")
    check("E4b control: SURFD_KEEP is the evidence tree",
          os.path.realpath(getattr(m, "KEEP_DIR", "")) == os.path.realpath(m._ev), True)
    lone = put_ev(m, "20260918-144000-4-p27510.rec", evbody(R), age=7200)
    m.gc_evidence(m.connect())
    check("E4b the orphan pass leaves the lobby's unindexed file", os.path.exists(lone), True)


def admin_client(m):
    c = m.app.test_client()
    page = c.get("/admin/login").get_data(as_text=True)
    csrf = page.split('name="csrf" value="')[1].split('"')[0]
    check("control: admin login", c.post("/admin/login", data={
        "csrf": csrf, "password": PW}).status_code, 302)
    page = c.get("/admin/runs").get_data(as_text=True)
    return c, page.split('name="csrf" value="')[1].split('"')[0]


def review(m, c, csrf, rid, action):
    sub = q(m, "SELECT submitted FROM replays WHERE id = ?", (rid,))[0][0]
    r = c.post("/admin/api/review", headers={"Sec-Fetch-Site": "same-origin"},
               data={"rid": str(rid), "action": action, "submitted": str(sub),
                     "csrf": csrf})
    return r.status_code, (r.get_json() or {}).get("ok"), (r.get_json() or {}).get("message", "")


def stage(m, player="kap"):
    """kap's leg-2 row as the board shows it: (ticks, runid) or None."""
    row = by_player(m, 2).get(player)
    if row is None:
        return None
    return (row["ticks"], q(m, "SELECT runid FROM runs WHERE leg = 2 AND player = ?"
                               " AND tier = 'ranked'", (player,))[0][0])


def case_exclusion():
    """E5: stage evidence is verified, listed and reviewed; a reject hides the
    stage times its run set, and a clear restores them (Patch 425)"""
    m = fresh(admin_pw=PW)
    sweep = importlib.import_module("sweep")
    submit(m, leg=2, ticks=454)
    put_ev(m, R + ".rec", evbody(R), age=3600)
    conn = m.connect()
    m.index_evidence(conn)
    eid = evid(m, R)
    zed = submit(m, player="zed", name="Zed", ticks=5000, runid="Rz",
                 rec=leaf(5000, "zed"))["rep"]
    ids = [r["id"] for r in sweep.pending(conn, 100)]
    check("E5 sweep.pending lists the evidence row as indexed", eid in ids, True)
    check("E5 control: ...and the run", zed in ids, True)
    before = q(m, "SELECT * FROM runs ORDER BY map, leg, player")
    with conn:
        res = m.restand(conn, eid)
    check("E5 restand(evidence) is none, the runs table byte-identical",
          (res, q(m, "SELECT * FROM runs ORDER BY map, leg, player") == before),
          ("none", True))

    c, csrf = admin_client(m)
    rows = {x["id"]: x for x in c.get("/admin/api/runs",
                                      query_string={"state": "all"}).get_json()["rows"]}
    check("E5 the admin run list holds it, as stage evidence backing a stage time",
          (rows.get(eid, {}).get("kind"), rows.get(eid, {}).get("standing")),
          ("evidence", True))
    check("E5 control: ...and lists the run", zed in rows, True)
    check("E5 the admin path route reads it from SURFD_KEEP",
          c.get("/admin/api/run/%d/path" % eid).status_code, 200)
    det = c.get("/admin/api/run/%d" % eid).get_json()
    check("E5 the run page counts the stage time it backs",
          (det["standing"]["stages"], det["standing"]["stages_hidden"]), (1, 0))

    check("E5 approve: accepted", review(m, c, csrf, eid, "approve")[:2], (200, True))
    check("E5 ...and the stage time stands", stage(m), (454, R))
    code, ok, msg = review(m, c, csrf, eid, "reject")
    check("E5 reject: accepted, and says what it hid", (code, ok, "1 hidden" in msg),
          (200, True, True))
    check("E5 ...the stage time is off the board", stage(m), None)
    check("E5 ...parked, not deleted",
          q(m, "SELECT tier, ticks, runid FROM runs WHERE leg = 2 AND player = 'kap'"),
          [("ranked@" + R, 454, R)])
    det = c.get("/admin/api/run/%d" % eid).get_json()
    check("E5 ...and the run page says so",
          (det["standing"]["stages"], det["standing"]["stages_hidden"]), (0, 1))
    check("E5 gc keeps the evidence while a parked row names it",
          (m.gc_evidence(conn), evid(m, R)), (0, eid))

    # Meanwhile the player's next stage time takes the live slot.
    submit(m, leg=2, ticks=500, runid="R4")
    check("E5 a slower time meanwhile takes the slot", stage(m), (500, "R4"))
    check("E5 clear: accepted", review(m, c, csrf, eid, "clear")[:2], (200, True))
    check("E5 ...the better (parked) time is back, the slower one set aside",
          (stage(m), q(m, "SELECT tier, ticks FROM runs WHERE leg = 2 AND player = 'kap'"
                          " AND tier <> 'ranked'")),
          ((454, R), [("ranked^" + R, 500)]))
    review(m, c, csrf, eid, "reject")
    check("E5 re-rejecting gives the set-aside time its slot back", stage(m), (500, "R4"))
    review(m, c, csrf, eid, "clear")

    review(m, c, csrf, eid, "reject")
    submit(m, leg=2, ticks=400, runid="R5")
    check("E5 control: a faster time meanwhile", stage(m), (400, "R5"))
    check("E5 approve lapses the reject", review(m, c, csrf, eid, "approve")[:2], (200, True))
    check("E5 ...and the faster live time keeps the slot, the parked one dropped",
          (stage(m), q(m, "SELECT COUNT(*) FROM runs WHERE leg = 2 AND player = 'kap'")),
          ((400, "R5"), [(1,)]))

    check("E5 recheck: accepted", review(m, c, csrf, eid, "recheck")[:2], (200, True))
    check("E5 ...and queued", q(m, "SELECT checked FROM replays WHERE id = ?", (eid,)),
          [(0,)])
    b = by_player(m, 2)["kap"]
    check("E5 a stage row still carries no badge of its own", b["ver"], 0)


def case_run_reject_hides_stages():
    """E5b: rejecting a finished run hides its stage times too; its leaf re-filed
    by another run (an exact tie) does not bring them back"""
    m = fresh(admin_pw=PW)
    lf = leaf(4000, "kap")
    put_run(m, lf, evbody(R).replace("abandon 8262\n", "").replace(
        "end 8262", "end 4000").replace("tickrate 0.015\n", "tickrate 0.015\n"))
    submit(m, leg=2, ticks=454)
    rid = submit(m, ticks=4000, rec=lf)["rep"]
    check("E5b control: the run is filed with its recording", rid > 0, True)
    c, csrf = admin_client(m)
    check("E5b control: its stage time stands", stage(m), (454, R))
    code, ok, msg = review(m, c, csrf, rid, "reject")
    check("E5b reject the run: its main row and its stage time are off the boards",
          (ok, "kap" in by_player(m, 0), stage(m)), (True, False, None))
    check("E5b clear: both back", (review(m, c, csrf, rid, "clear")[1],
                                   "kap" in by_player(m, 0), stage(m)), (True, True, (454, R)))
    review(m, c, csrf, rid, "reject")
    submit(m, ticks=4000, rec=lf)
    check("E5b control: an identical re-post leaves it hidden", stage(m), None)
    # The same run's evidence re-filed (the file changed) after the reject: it
    # lapses (reviews count only at or after `submitted`), so the time is back.
    with sqlite3.connect(m.DB_PATH) as db:  # filed, and rejected, 10 s ago
        db.execute("UPDATE reviews SET at = at - 10 WHERE replay_id = ?", (rid,))
        db.execute("UPDATE replays SET submitted = submitted - 10 WHERE id = ?", (rid,))
    put_run(m, lf, evbody(R).replace("abandon 8262\n", "").replace(
        "end 8262", "end 4000") + "x 1\n")
    submit(m, ticks=4000, rec=lf)
    check("E5b the same run re-filed with new evidence lapses the reject: back",
          stage(m), (454, R))
    review(m, c, csrf, rid, "reject")
    # The same leaf filed again by another run (an exact tie): new evidence.
    put_run(m, lf, evbody("R9").replace("abandon 8262\n", "").replace("end 8262", "end 4000"))
    again = submit(m, ticks=4000, rec=lf, runid="R9")
    check("E5b control: the re-filed leaf is the same replay row", again["rep"], rid)
    check("E5b ...and the rejected run's stage time stays hidden",
          (stage(m), q(m, "SELECT tier FROM runs WHERE leg = 2 AND player = 'kap'")),
          (None, [("ranked@" + R,)]))
    # A key holder then names R on a leaf with no file behind it, twice (the
    # second is a re-post of a held leaf): a replay of R with no reject, but no
    # new evidence of the run the reject stands on.
    submit(m, ticks=4001, rec=leaf(4001, "kap"), runid=R)
    with sqlite3.connect(m.DB_PATH) as db:       # filed 10 s ago, so the next moves it
        db.execute("UPDATE replays SET submitted = submitted - 10 WHERE leaf = ?",
                   (leaf(4001, "kap"),))
    submit(m, ticks=4001, rec=leaf(4001, "kap"), runid=R, recbytes=12345)
    check("E5b ...a file-less leaf naming R does not bring it back",
          (stage(m), q(m, "SELECT tier FROM runs WHERE leg = 2 AND player = 'kap'")),
          (None, [("ranked@" + R,)]))

    # A stale snapshot (the slot's row changed under it) moves nothing.
    conn = m.connect()
    snap = conn.execute("SELECT * FROM runs WHERE leg = 2 AND player = 'kap'").fetchone()
    with conn:
        conn.execute("UPDATE runs SET runid = 'Rother' WHERE leg = 2 AND player = 'kap'")
        moved = m._stage_move(conn, snap, "ranked")
    check("E5b _stage_move of a stale snapshot moves nothing",
          (moved, q(m, "SELECT tier, runid FROM runs WHERE leg = 2 AND player = 'kap'")),
          (0, [("ranked@" + R, "Rother")]))


def case_recorded_stage_stands_in():
    """E5c: while a stage time is hidden, the player's recorded run of that leg
    stands in its place (restand's rule); a clear gives the slot back"""
    m = fresh(admin_pw=PW)
    sl = leaf(600, "kap")
    path = os.path.join(m.RUNS_DIR, "surf_Aser", m.leg_dir(0, 2), sl)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="\n") as fh:
        fh.write(evbody("Rs", leg=2))
    srep = submit(m, leg=2, ticks=600, rec=sl, runid="Rs")["rep"]
    check("E5c control: a recorded stage run of leg 2 stands", stage(m), (600, "Rs"))
    submit(m, leg=2, ticks=454)                       # the abandoned run's post
    put_ev(m, R + ".rec", evbody(R), age=3600)
    m.index_evidence(m.connect())
    eid = evid(m, R)
    check("E5c control: the faster stage post took the slot", stage(m), (454, R))
    c, csrf = admin_client(m)
    review(m, c, csrf, eid, "reject")
    check("E5c reject: the recorded run stands in, with its replay",
          (stage(m), by_player(m, 2)["kap"]["rep"]), ((600, ""), srep))
    review(m, c, csrf, eid, "clear")
    check("E5c clear: the better stage time has its slot back", stage(m), (454, R))


def stage_run(m, ticks, runid):
    """A recorded stage run of leg 2 (its own leaf) -> its replay id."""
    sl = leaf(ticks, "kap")
    path = os.path.join(m.RUNS_DIR, "surf_Aser", m.leg_dir(0, 2), sl)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="\n") as fh:
        fh.write(evbody(runid, leg=2))
    return submit(m, leg=2, ticks=ticks, rec=sl, runid=runid)["rep"]


def case_set_aside():
    """E5d: a set-aside time comes back judged by its own run, a recorded one by
    its own replay (restand), a better recording competes, and none is stranded"""
    m = fresh(admin_pw=PW)
    srep = stage_run(m, 600, "Rs")
    submit(m, leg=2, ticks=454)
    put_ev(m, R + ".rec", evbody(R), age=3600)
    m.index_evidence(m.connect())
    eid = evid(m, R)
    c, csrf = admin_client(m)
    review(m, c, csrf, eid, "reject")
    review(m, c, csrf, eid, "clear")
    check("E5d control: R restored, the recorded 600 set aside",
          (stage(m), q(m, "SELECT tier FROM runs WHERE replay_id = ?", (srep,))),
          ((454, R), [("ranked^" + R,)]))
    check("E5d ...and the admin does not call the set-aside row standing",
          c.get("/admin/api/run/%d" % srep).get_json()["standing"]["on_board"], False)
    review(m, c, csrf, srep, "reject")
    review(m, c, csrf, eid, "reject")
    check("E5d a set-aside recorded run that was rejected does not come back",
          stage(m), None)

    m = fresh(admin_pw=PW)
    submit(m, leg=2, ticks=454)
    put_ev(m, R + ".rec", evbody(R), age=3600)
    m.index_evidence(m.connect())
    eid = evid(m, R)
    c, csrf = admin_client(m)
    review(m, c, csrf, eid, "reject")
    submit(m, leg=2, ticks=500, runid="S")
    review(m, c, csrf, eid, "clear")
    stage_run(m, 480, "Rr")          # not stood: 454 beats it
    check("E5d control: 454 stands over the recorded 480", stage(m), (454, R))
    review(m, c, csrf, eid, "reject")
    check("E5d re-rejecting: the set-aside 500 comes back, and the recorded 480 beats it",
          stage(m), (480, ""))

    m = fresh(admin_pw=PW)
    submit(m, leg=2, ticks=454)
    put_ev(m, R + ".rec", evbody(R), age=3600)
    m.index_evidence(m.connect())
    eid = evid(m, R)
    c, csrf = admin_client(m)
    review(m, c, csrf, eid, "reject")
    submit(m, leg=2, ticks=500, runid="X")
    review(m, c, csrf, eid, "clear")
    submit(m, leg=2, ticks=400, runid=R3)     # a later run beats R's time
    put_ev(m, R3 + ".rec", evbody(R3), age=3600)
    m.index_evidence(m.connect())
    e3 = evid(m, R3)
    review(m, c, csrf, e3, "reject")
    check("E5d rejecting that later run gives back what R's restore set aside",
          stage(m), (500, "X"))


def case_round4():
    """E5e: a stage post of a rejected run goes to its hidden slot; a park the
    hidden copy beats still refills; a recorded stage run's reject brings back
    what a restore set aside"""
    m = fresh(admin_pw=PW)
    sweep = importlib.import_module("sweep")
    submit(m, leg=2, ticks=454)
    put_ev(m, R + ".rec", evbody(R), age=3600)
    conn = m.connect()
    m.index_evidence(conn)
    eid = evid(m, R)
    c, csrf = admin_client(m)
    review(m, c, csrf, eid, "reject")
    submit(m, leg=2, ticks=500, runid="S")
    check("E5e control: the player's 500 holds the slot", stage(m), (500, "S"))
    back = submit(m, leg=2, ticks=440)               # R's stage, posted again
    check("E5e a post of the rejected run leaves the live slot alone",
          (back["stored"], stage(m)), (False, (500, "S")))
    check("E5e ...and lands in R's hidden slot, the better one kept",
          q(m, "SELECT ticks FROM runs WHERE leg = 2 AND tier = ?", ("ranked@" + R,)),
          [(440,)])
    sweep.evidence_step(conn)
    check("E5e ...and the sweep leaves the player's 500", stage(m), (500, "S"))

    # A live row of R that its hidden copy beats (posted while the reject was
    # not yet applied): parking drops it, and the slot still refills.
    m = fresh(admin_pw=PW)
    srep = stage_run(m, 600, "Rs")
    submit(m, leg=2, ticks=454)
    put_ev(m, R + ".rec", evbody(R), age=3600)
    conn = m.connect()
    m.index_evidence(conn)
    eid = evid(m, R)
    c, csrf = admin_client(m)
    review(m, c, csrf, eid, "reject")
    with conn:                        # R's slower post beside its hidden 454
        conn.execute("UPDATE runs SET ticks = 470, millis = 7050, runid = ?,"
                     " replay_id = 0 WHERE leg = 2 AND tier = 'ranked'", (R,))
    sweep.evidence_step(conn)
    check("E5e a park its hidden copy beats still refills (the recorded 600)",
          (stage(m), by_player(m, 2)["kap"]["rep"]), ((600, ""), srep))

    # A restore sets a time aside; a recorded stage run then replaces R's time
    # and is rejected: the set-aside time competes for the slot.
    m = fresh(admin_pw=PW)
    submit(m, leg=2, ticks=454)
    put_ev(m, R + ".rec", evbody(R), age=3600)
    m.index_evidence(m.connect())
    eid = evid(m, R)
    c, csrf = admin_client(m)
    review(m, c, csrf, eid, "reject")
    submit(m, leg=2, ticks=500, runid="S")
    review(m, c, csrf, eid, "clear")
    rec = stage_run(m, 450, "Rq")
    stage_run(m, 700, "Rw")                          # recorded, slower: not stood
    check("E5e control: the recorded 450 took the slot", stage(m), (450, "Rq"))
    review(m, c, csrf, rec, "reject")
    check("E5e rejecting it gives the slot to the set-aside 500, not the recorded 700",
          stage(m), (500, "S"))


def case_bound():
    """E14: "a recording of the run" is decided when it was filed (replays.bound),
    not by the disk now; the column is backfilled on an older database"""
    m = fresh(admin_pw=PW)
    sweep = importlib.import_module("sweep")
    lf = leaf(4000, "kap")
    path = put_run(m, lf, evbody(R).replace("abandon 8262\n", "").replace(
        "end 8262", "end 4000"))
    submit(m, leg=2, ticks=454)
    rid = submit(m, ticks=4000, rec=lf)["rep"]
    c, csrf = admin_client(m)
    review(m, c, csrf, rid, "reject")
    check("E14 control: the rejected run's stage time is hidden", stage(m), None)
    os.unlink(path)                        # the recording goes missing later
    sweep.evidence_step(m.connect())
    check("E14 ...and stays hidden when its file is gone", stage(m), None)
    check("E14 ...the replay still reads as filed against its file",
          q(m, "SELECT bound FROM replays WHERE id = ?", (rid,)), [(1,)])

    m = fresh()
    submit(m, leg=2, ticks=454)
    put_ev(m, R + ".rec", evbody(R), age=3600)
    conn = m.connect()
    m.index_evidence(conn)
    live = put_run(m, leaf(4100, "kap"), evbody("Rb").replace("abandon 8262\n", ""))
    submit(m, ticks=4100, rec=leaf(4100, "kap"), runid="Rb")
    submit(m, player="zed", ticks=4200, rec=leaf(4200, "zed"), runid="Rz")   # no file
    with conn:
        conn.execute("ALTER TABLE replays DROP COLUMN bound")
    m.replays_bound(conn)
    check("E14 backfill: evidence and a run whose file is there are bound, not the rest",
          q(m, "SELECT kind, runid, bound FROM replays ORDER BY id"),
          [("evidence", R, 1), ("run", "Rb", 1), ("run", "Rz", 0)])


def case_restand_sets_aside():
    """E15: re-standing a recorded stage run over the player's interim time sets
    that time aside, and a later reject gives it back (round 5, older)"""
    m = fresh(admin_pw=PW)
    x = stage_run(m, 450, "Rx")
    c, csrf = admin_client(m)
    review(m, c, csrf, x, "reject")
    check("E15 control: the rejected recording's slot is empty", stage(m), None)
    submit(m, leg=2, ticks=500, runid="S")
    review(m, c, csrf, x, "clear")
    check("E15 clearing it re-stands the 450", stage(m), (450, ""))
    review(m, c, csrf, x, "reject")
    check("E15 rejecting it again gives the player's 500 back", stage(m), (500, "S"))


def case_round6():
    """E16: a file-less leg-0 row naming R neither blocks R's evidence nor takes
    its stage row's link; a leafless main time comes back on a re-reject; the
    backfill needs a header that describes the row"""
    m = fresh(admin_pw=PW)
    submit(m, leg=2, ticks=454)
    fake = submit(m, ticks=9999, rec=leaf(9999, "kap"))["rep"]   # no file behind it
    check("E16 control: the fake leg-0 row is filed, unbound",
          q(m, "SELECT bound FROM replays WHERE id = ?", (fake,)), [(0,)])
    put_ev(m, R + ".rec", evbody(R), age=3600)
    conn = m.connect()
    got = m.index_evidence(conn)
    eid = evid(m, R)
    check("E16 R's evidence is still indexed", (got["indexed"], eid > 0), (1, True))
    check("E16 ...and the stage row's run is the evidence, not the fake",
          by_player(m, 2)["kap"].get("run"), eid)

    m = fresh(admin_pw=PW)
    lf = leaf(4000, "kap")
    put_run(m, lf, evbody(R).replace("abandon 8262\n", "").replace("end 8262", "end 4000"))
    rid = submit(m, ticks=4000, rec=lf)["rep"]
    c, csrf = admin_client(m)
    review(m, c, csrf, rid, "reject")
    submit(m, ticks=4500, runid="Rmain")                          # leafless main time
    check("E16 control: the leafless main time stands", "kap" in by_player(m, 0), True)
    review(m, c, csrf, rid, "clear")
    review(m, c, csrf, rid, "reject")
    check("E16 a leafless main time comes back on a re-reject",
          by_player(m, 0).get("kap", {}).get("ms"), 67500)

    m = fresh()
    put_run(m, leaf(4100, "kap"), evbody("Rh").replace("abandon 8262\n", ""))
    submit(m, ticks=4100, rec=leaf(4100, "kap"), runid="Rh")
    put_run(m, leaf(4100, "kap"), evbody("Rother").replace("abandon 8262\n", ""))
    conn = m.connect()
    with conn:
        conn.execute("ALTER TABLE replays DROP COLUMN bound")
    m.replays_bound(conn)
    check("E16 backfill: a file whose header names another run is not bound",
          q(m, "SELECT runid, bound FROM replays"), [("Rh", 0)])


def case_public():
    """E6: public bodies carry `run` and nothing private"""
    m = fresh()
    submit(m, leg=2, ticks=454)
    put_ev(m, R + ".rec", evbody(R), age=3600)
    conn = m.connect()
    m.index_evidence(conn)
    eid = evid(m, R)
    with conn:
        conn.execute("INSERT INTO verdicts (replay_id, verdict, reason, ticks, engine,"
                     " progs, at) VALUES (?, 'HOLD', 'SENTINEL-REASON', -1, 'e', 'p',"
                     " ?)", (eid, int(time.time()) + 5))
    c = m.app.test_client()
    for path in ("/api/board?map=surf_aser&leg=2", "/board/api/map?map=surf_aser&leg=2"):
        resp = c.get(path, environ_base={"REMOTE_ADDR": "127.0.0.1"})
        text = resp.get_data(as_text=True)
        rows = (resp.get_json() or {}).get("rows") or [{}]
        check("E6 %s: 200, row carries run" % path,
              (resp.status_code, rows[0].get("run")), (200, eid))
        low = text.lower()
        leaked = [w for w in ("sentinel", "verdict", "reason", "reject", "approve",
                              "evidence", R.lower()) if w in low] + \
            (["HOLD"] if "HOLD" in text else [])
        check("E6 no private word in %s" % path, leaked, [])


def shadow_of_r(m):
    """kap's clean stage 2 of R, R's evidence, and a TF_SHADOW continuation
    sent with no runid whose rebuilt header still says R.  -> its replay id."""
    submit(m, leg=2, ticks=454, runid=R)
    sh = leaf(4000, "kap").replace("_run.rec", "_shadow.rec")
    rid = submit(m, ticks=4000, runid=None, rec=sh)["rep"]
    hdr = m._rec_meta(put_run(m, sh, evbody(R)))
    put_ev(m, R + ".rec", evbody(R), age=3600)
    check("E7 control: the continuation is a row, its header says R",
          (rid > 0, hdr[0].get("runid") if hdr else hdr), (True, R))
    return rid


def case_no_header_runid():
    """E7: a replay's runid never comes from its .rec header"""
    m = fresh()
    sweep = importlib.import_module("sweep")
    rid = shadow_of_r(m)
    check("E7 a replay sent with no runid is stored '-'", runid_of(m, rid), [("-",)])
    conn = m.connect()
    check("E7 the sweep indexes R's evidence", sweep.evidence_step(conn), (1, 0))
    eid = evid(m, R)
    check("E7 ...the clean stage row plays it, not the continuation",
          (runid_of(m, rid), eid > 0, by_player(m, 2)["kap"].get("run")),
          ([("-",)], True, eid))
    submit(m, leg=4, ticks=300, runid="-")
    check("E7 a stage row whose runid is '-' links to no '-' replay",
          by_player(m, 4)["kap"].get("run"), 0)

    # The same stored before schema 6 (runid ''), then migrate()d.
    m = fresh()
    sweep = importlib.import_module("sweep")
    rid = shadow_of_r(m)
    bl = leaf(5000, "bob")
    old = submit(m, player="bob", name="Bob", ticks=5000, runid=R2, rec=bl)["rep"]
    submit(m, player="bob", name="Bob", leg=3, ticks=600, runid=R2)
    put_run(m, bl, evbody(R2))
    conn = m.connect()
    with conn:
        conn.execute("UPDATE replays SET runid = ''")
    conn.execute("PRAGMA user_version = 5")
    m.migrate()
    check("E7 control: migrate() links bob's parent from runs; the continuation"
          " stays ''", (runid_of(m, old), by_player(m, 3)["bob"].get("run"),
                         runid_of(m, rid)), ([(R2,)], old, [("",)]))
    check("E7 legacy: the sweep indexes R's evidence", sweep.evidence_step(conn), (1, 0))
    eid = evid(m, R)
    check("E7 legacy: ...the continuation keeps '' and the clean stage row plays R",
          (runid_of(m, rid), eid > 0, by_player(m, 2)["kap"].get("run")),
          ([("",)], True, eid))
    check("E7 legacy: a second sweep changes nothing",
          (sweep.evidence_step(conn), runid_of(m, rid)), ((0, 0), [("",)]))


def case_runid_trust():
    """E8: a runid is a trusted node's claim, and a run is one player's"""
    m = fresh()
    submit(m, leg=2, ticks=454, runid=R)
    r = submit(m, player="evil", name="Evil", leg=2, ticks=300, runid=R,
               addr="203.0.113.9")
    check("E8 control: an untrusted keyed source may file a time", r["stored"], True)
    check("E8 ...but not a runid",
          q(m, "SELECT player, runid FROM runs WHERE leg = 2 ORDER BY player"),
          [("evil", ""), ("kap", R)])
    put_ev(m, R + ".rec", evbody(R), age=3600)
    conn = m.connect()
    got = m.index_evidence(conn)
    eid = evid(m, R)
    check("E8 ...so R's evidence is filed under kap and backs kap's row",
          (got["indexed"], q(m, "SELECT player FROM replays WHERE id = ?", (eid,)),
           by_player(m, 2)["kap"].get("run")), (1, [("kap",)], eid))

    m = fresh()
    submit(m, leg=2, ticks=454, runid=R)
    submit(m, player="bob", name="Bob", leg=3, ticks=600, runid=R)
    put_ev(m, R + ".rec", evbody(R), age=3600)
    conn = m.connect()
    got = m.index_evidence(conn)
    check("E8 a file two players' stage rows name is bad, not indexed",
          (got["indexed"], got["bad"], evid(m, R)), (0, 1, 0))
    submit(m, player="bob", name="Bob", leg=3, ticks=500, runid=R2)
    got = m.index_evidence(conn)
    check("E8 control: once only kap's rows name it, it is indexed under kap",
          (got["indexed"], q(m, "SELECT player FROM replays WHERE kind = 'evidence'")),
          (1, [("kap",)]))


def case_torn_index():
    """E9: an evidence file torn after `end ` skips only itself"""
    m = fresh()
    sweep = importlib.import_module("sweep")
    conn = m.connect()
    submit(m, player="carol", name="Carol", leg=4, ticks=700, runid=R3)
    put_ev(m, R3 + ".rec", evbody(R3), age=3600)
    check("E9 control: carol's evidence is indexed", m.index_evidence(conn)["indexed"], 1)
    e3 = evid(m, R3)
    submit(m, player="carol", name="Carol", leg=4, ticks=650,
           runid="20260918-170000-0-p27510")               # nothing names R3 now
    submit(m, leg=2, ticks=454, runid=R)
    torn = put_ev(m, R + ".rec", evbody(R, end=False) + TORN, age=3600)
    submit(m, player="bob", name="Bob", leg=3, ticks=600, runid=R2)
    put_ev(m, R2 + ".rec", evbody(R2), age=3600)
    check("E9 control: the torn file sorts before the good one", R < R2, True)
    check("E9 sweep.evidence_step finishes: +2 -1", sweep.evidence_step(conn), (2, 1))
    check("E9 ...the torn file indexed as a run with no end (ticks 0)",
          q(m, "SELECT ticks FROM replays WHERE kind = 'evidence' AND runid = ?", (R,)),
          [(0,)])
    check("E9 ...the good file after it indexed", evid(m, R2) > 0, True)
    check("E9 ...and gc_evidence ran", (e3 > 0, evid(m, R3)), (True, 0))
    meta = m._rec_meta(torn)
    check("E9 _rec_meta: the header kept, end -1, abandon seen",
          (meta[0].get("runid"), meta[1], meta[2]) if meta else meta, (R, -1, True))


def case_torn_ticks():
    """E10: an `end` torn inside its ticks is no end"""
    m = fresh()
    submit(m, leg=2, ticks=454, runid=R)
    torn = put_ev(m, R + ".rec", evbody(R, end=False)
                  + "abandon 8262\ninend 8744 0.009\nend 82")   # just written
    meta = m._rec_meta(torn)
    check("E10 _rec_meta: end -1, abandon seen",
          (meta[1], meta[2]) if meta else meta, (-1, True))
    conn = m.connect()
    got = m.index_evidence(conn)
    check("E10 index_evidence defers it and indexes nothing",
          (got["indexed"], got["deferred"], evid(m, R)), (0, 1, 0))
    with open(torn, "a", newline="\n") as fh:           # the writer finishes the line
        fh.write("62 8519 256 0 8262 4 1 0 1 0\n")
    got = m.index_evidence(conn)
    check("E10 control: once whole it is indexed at once, with its end's ticks",
          (got["indexed"], q(m, "SELECT ticks FROM replays WHERE kind = 'evidence'")),
          (1, [(8262,)]))


def case_keep_same_gc():
    """E11: SURFD_KEEP at the lobbies' tree: gc drops the row, not their file"""
    m = fresh(keep="same")
    submit(m, leg=2, ticks=454, runid=R)
    src = put_ev(m, R + ".rec", evbody(R), age=3600)
    conn = m.connect()
    check("E11 control: indexed in place", m.index_evidence(conn)["indexed"], 1)
    submit(m, leg=2, ticks=400, runid=R3)                  # nothing names R now
    check("E11 control: gc_evidence drops the row", (m.gc_evidence(conn), evid(m, R)),
          (1, 0))
    check("E11 ...and leaves the lobby's file", os.path.exists(src), True)

    m = fresh()                                  # KEEP apart, one map dir linked in
    os.makedirs(os.path.join(m._ev, "surf_Aser"), exist_ok=True)
    os.makedirs(m.KEEP_DIR, exist_ok=True)
    os.symlink(os.path.join(m._ev, "surf_Aser"), os.path.join(m.KEEP_DIR, "surf_Aser"))
    lone = put_ev(m, R + ".rec", evbody(R), age=7200)
    m.gc_evidence(m.connect())
    check("E11 the orphan pass leaves a lobby file reached through a link",
          os.path.exists(lone), True)


def case_siblings_and_old_rejects():
    """E13: two replays of one run hide its stage times until neither reject
    stands; a reject from before Patch 425 is applied by the sweeper's step"""
    m = fresh(admin_pw=PW)
    sweep = importlib.import_module("sweep")
    submit(m, leg=2, ticks=454)
    put_ev(m, R + ".rec", evbody(R), age=3600)
    conn = m.connect()
    m.index_evidence(conn)
    eid = evid(m, R)
    sib = leaf(9000, "kap")          # a kept run of the same runid (a sibling)
    put_run(m, sib, evbody(R).replace("abandon 8262\n", ""))
    with conn:
        rid = conn.execute(
            "INSERT INTO replays (map, map_dir, track, leg, leaf, tier, style, player,"
            " name, ticks, tickrate, millis, flags, node, submitted, runid, kind, bound)"
            " VALUES ('surf_aser', 'surf_Aser', 0, 0, ?, 'ranked', 'clean', 'kap',"
            " 'Kap', 9000, 66.666667, 135000, 0, 'p27510', 1, ?, 'run', 1)",
            (sib, R)).lastrowid
    c, csrf = admin_client(m)
    review(m, c, csrf, eid, "reject")
    review(m, c, csrf, rid, "reject")
    check("E13 control: both rejected, the stage time hidden", stage(m), None)
    review(m, c, csrf, eid, "clear")
    check("E13 clearing one sibling keeps it hidden while the other stands",
          stage(m), None)
    review(m, c, csrf, rid, "clear")
    check("E13 ...and clearing both restores it", stage(m), (454, R))

    with conn:                       # a reject stored before Patch 425
        conn.execute("INSERT INTO reviews (replay_id, decision, note, at)"
                     " VALUES (?, 'reject', '', ?)", (eid, int(time.time())))
    check("E13 control: a bare reject hides nothing yet", stage(m), (454, R))
    sweep.evidence_step(conn)
    check("E13 the sweeper's evidence step applies it", stage(m), None)
    with conn:
        conn.execute("DELETE FROM reviews")
    review(m, c, csrf, eid, "clear")
    check("E13 control: back after the clear", stage(m), (454, R))

    # A file-less row naming R (anyone's to post with the key) is no recording
    # of R: rejecting it must not hide R's honest stage time (round 4).
    fake = submit(m, ticks=4050, rec=leaf(4050, "kap"), runid=R)["rep"]
    code, ok, msg = review(m, c, csrf, fake, "reject")
    check("E13 rejecting a file-less row naming R leaves R's stage time",
          (ok, stage(m)), (True, (454, R)))


def main():
    for case in (case_index_and_serve, case_what_is_not_indexed, case_gc,
                 case_keep_is_not_evidence, case_exclusion,
                 case_run_reject_hides_stages, case_recorded_stage_stands_in,
                 case_set_aside, case_round4, case_bound, case_restand_sets_aside,
                 case_round6,
                 case_public,
                 case_no_header_runid, case_runid_trust, case_torn_index,
                 case_torn_ticks, case_keep_same_gc, case_siblings_and_old_rejects):
        print("\n--- %s" % case.__doc__)
        try:
            case()
        except Exception as exc:                 # a pre-schema-6 surfd lands here
            check("%s ran to the end" % case.__name__,
                  "%s: %s" % (type(exc).__name__, exc), "no exception")
    print("")
    if FAILED:
        print("%d FAILED" % len(FAILED))
        for line in FAILED:
            print("  " + line)
        return 1
    print("all evidence checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
