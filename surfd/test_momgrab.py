#!/usr/bin/env python3
"""
test_momgrab.py -- the falsifier for momgrab.py.

    python surfd/test_momgrab.py

No network: `download` is driven through a fake urlopen, and the main loop's
fetches through a fake that copies a fixture.  The conversion cases need one
real Momentum demo, which is not committed (it is someone's run): set
MOMGRAB_FIXTURE to a .mtv, or they are skipped and say so.
"""

import hashlib
import http.client
import io
import json
import os
import shutil
import sqlite3
import sys
import tempfile
import time
import urllib.error

FAILED = []
SKIPPED = []
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)


def check(label, got, want):
    ok = got == want
    print("%-4s %-62s %r" % ("ok" if ok else "FAIL", label, got))
    if not ok:
        FAILED.append("%s: got %r, want %r" % (label, got, want))


HOME = tempfile.mkdtemp(prefix="surfd-grab-")
os.environ.update(SURFD_HOME=HOME, SURFD_DB=os.path.join(HOME, "test.db"),
                  SURFD_MOMENTUM=os.path.join(HOME, "momentum"))
import surfd as S        # noqa: E402
import momgrab as G      # noqa: E402

FIXTURE = os.environ.get("MOMGRAB_FIXTURE", "")
for _p in (FIXTURE, "C:/tmp/probe.mtv"):
    if _p and os.path.isfile(_p):
        FIXTURE = _p
        break
else:
    FIXTURE = ""

SID = "76561198356066955"
NOW = int(time.time())


def board_file(d, name, mp, tt, tn, rows):
    with io.open(os.path.join(d, name), "w", encoding="utf-8") as fh:
        json.dump({"map": mp, "mapid": 1, "gamemode": 1, "trackType": tt, "trackNum": tn,
                   "total": len(rows), "fetched": 1, "rows": rows}, fh)


def row(h, sid, t):
    return {"rank": 0, "time": t, "hash": h, "steamid": sid, "alias": "a",
            "created": "", "url": G.CDN + h}


def picks(q, done=None, later=None, held=None, prio=(), n=10, zstd=True):
    return [c[3][0] for c in G.pick(q, done or {}, later or {}, held or {}, set(prio),
                                     n, NOW, zstd)]


def case_queue_and_pick():
    bd = tempfile.mkdtemp(prefix="boards-", dir=HOME)
    st = tempfile.mkdtemp(prefix="state-", dir=HOME)
    board_file(bd, "1_g1_t01.json", "surf_a", 0, 1,
               [row("a" * 40, SID, 40.0), row("b" * 40, "76561198000000001", 41.0),
                row("c" * 40, "76561198000000002", 42.0), row("d" * 40, SID, 39.5),
                row("e" * 39 + "Z", "76561198000000003", 43.0),
                row("f" * 40, "notasteamid", 44.0)])
    board_file(bd, "2_g1_t11.json", "surf_b", 1, 2, [row("9" * 40, SID, 10.0)])
    q, read, unread = G.refresh_queue(bd, os.path.join(st, "queue.json"), 2, 100)
    b1 = q["boards"]["1_g1_t01.json"]["rows"]
    check("a player's superseded time is not queued, only their best",
          [r[0][0] for r in b1], ["d", "b"])
    check("...and a stage board files as its stage",
          (q["boards"]["2_g1_t11.json"]["track"], q["boards"]["2_g1_t11.json"]["leg"]), (0, 2))
    q, read, unread = G.refresh_queue(bd, os.path.join(st, "queue.json"), 2, 100)
    check("an unchanged board file is not read again", read, 0)
    q5, _, _ = G.refresh_queue(bd, os.path.join(st, "queue5.json"), 5, 100)
    check("a hash that is not 40 hex, or no SteamID, is never queued",
          sorted(r[0][0] for r in q5["boards"]["1_g1_t01.json"]["rows"]), ["b", "c", "d"])
    check("best place first, across boards", picks(q), ["d", "9", "b"])
    check("a wanted map goes first", picks(q, prio={"surf_a"}), ["d", "b", "9"])
    held = {("surf_a", 0, 0, SID): [39500], ("surf_b", 0, 2, SID): [9000]}
    check("a held RUN is skipped; the same player's other run is not",
          picks(q, held=held), ["9", "b"])
    check("a settled demo is skipped",
          picks(q, done={"d" * 40: "ok", "9" * 40: "gone"}), ["b"])
    later = {"d" * 40: [G.STRIKES, NOW, "cut short"], "9" * 40: [1, NOW, "cut short"]}
    check("one that failed STRIKES times waits; one that failed once does not",
          picks(q, later=later), ["9", "b"])
    check("...and after RETRY_DAYS it is asked again",
          picks(q, later={"d" * 40: [G.STRIKES, NOW - (G.RETRY_DAYS + 1) * 86400, "x"]})[0], "d")
    check("a zstd demo waits only while there is no zstandard",
          (picks(q, later={"d" * 40: [1, NOW, "zstd"]}, zstd=False)[0],
           picks(q, later={"d" * 40: [1, NOW, "zstd"]}, zstd=True)[0]), ("9", "d"))
    old = G.MAX_SECONDS
    G.MAX_SECONDS = 20
    check("a run longer than MAX_SECONDS is never fetched", picks(q), ["9"])
    G.MAX_SECONDS = old


class FakeResp(object):
    def __init__(self, body, status=200, length=None, cut=None):
        self.body, self.status, self.pos = body, status, 0
        self.headers = {"Content-Length": str(len(body) if length is None else length)}
        self.cut = cut

    def read(self, n):
        if self.cut is not None and self.pos >= self.cut:
            raise http.client.IncompleteRead(b"")
        b = self.body[self.pos:self.pos + n]
        self.pos += n
        return b

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def case_download():
    real = G.urllib.request.urlopen
    d = tempfile.mkdtemp(prefix="dl-", dir=HOME)
    body = b"x" * 200000
    h = hashlib.sha1(body).hexdigest()
    try:
        G.urllib.request.urlopen = lambda req, timeout=None: FakeResp(body)
        check("a file that hashes to its name is kept",
              (G.download(h, os.path.join(d, h + ".mtv")),
               os.path.exists(os.path.join(d, h + ".mtv"))), ("ok", True))
        check("one that does not is refused and removed",
              (G.download("0" * 40, os.path.join(d, "z.mtv")),
               sorted(os.listdir(d))), ("badhash", [h + ".mtv"]))
        G.urllib.request.urlopen = lambda req, timeout=None: FakeResp(body[:5000],
                                                                     length=len(body))
        try:
            G.download(h, os.path.join(d, "s.mtv"))
            got = "settled"
        except G.Transient:
            got = "tried again"
        check("a body short of its Content-Length is tried again, not settled", got,
              "tried again")
        G.urllib.request.urlopen = lambda req, timeout=None: FakeResp(body, cut=65536)
        try:
            G.download(h, os.path.join(d, "i.mtv"))
            got = "settled"
        except G.Transient:
            got = "tried again"
        check("...and so is one cut off mid-read", got, "tried again")

        def http(code):
            def f(req, timeout=None):
                raise urllib.error.HTTPError(req.full_url, code, "x", {}, None)
            return f

        for code in (403, 404, 410):
            G.urllib.request.urlopen = http(code)
            check("HTTP %d is the CDN's answer that it has no such file" % code,
                  G.download(h, os.path.join(d, "g.mtv")), "gone")
        for code, obj in ((429, False), (503, False), (500, True), (502, True)):
            G.urllib.request.urlopen = http(code)
            try:
                G.download(h, os.path.join(d, "r.mtv"))
                got = "kept going"
            except G.Refused as e:
                got = ("parks", e.obj)
            check("HTTP %d parks the grab%s" % (code, ", and counts against the file" if obj else ""),
                  got, ("parks", obj))
        old = G.MAX_BYTES
        G.MAX_BYTES = 100
        G.urllib.request.urlopen = lambda req, timeout=None: FakeResp(body)
        check("a file over MAX_BYTES is refused and not kept",
              (G.download(h, os.path.join(d, "big.mtv")),
               os.path.exists(os.path.join(d, "big.mtv.part"))), ("toobig", False))
        G.MAX_BYTES = old
    finally:
        G.urllib.request.urlopen = real


def case_bsp_case():
    d = tempfile.mkdtemp(prefix="maps-", dir=HOME)
    io.open(os.path.join(d, "bhop_HaddocK.bsp"), "wb").write(b"bsp")
    got = G.bsp_sha1("bhop_haddock", d, os.path.join(d, "bsp.json"))
    check("a BSP named with capitals is found for its lowercased board name",
          got, hashlib.sha1(b"bsp").hexdigest().upper())


def run(argv):
    import argparse
    old = sys.argv
    sys.argv = ["momgrab.py"] + argv
    try:
        return G.main()
    finally:
        sys.argv = old


def db():
    return sqlite3.connect(os.environ["SURFD_DB"])


def case_convert_and_file():
    if not FIXTURE:
        SKIPPED.append("conversion: no MOMGRAB_FIXTURE .mtv on this box")
        print("skip conversion cases: no fixture demo (set MOMGRAB_FIXTURE)")
        return
    S.migrate()
    head = G.momreplay.read_header(open(FIXTURE, "rb").read(0x200))
    sha = hashlib.sha1(open(FIXTURE, "rb").read()).hexdigest()
    st = tempfile.mkdtemp(prefix="state-", dir=HOME)
    demo = os.path.join(st, sha + ".mtv")
    shutil.copy(FIXTURE, demo)
    track, leg = G.momimport.track_leg(head["track_type"], head["track_number"])
    ti = head["tick_interval"]
    ms = int(round(round(head["run_time"] / ti) * ti * 1000.0))
    mp = head["map"].lower()
    board = {"map": mp, "track": track, "leg": leg}
    out = os.path.join(HOME, "momentum")
    real = G.bsp_sha1
    try:
        G.bsp_sha1 = lambda m, d, c: "0" * 40
        check("a demo on another build of the map is refused",
              G.convert_demo(demo, board, ms, "", "", out), ("otherbuild", None))
        G.bsp_sha1 = lambda m, d, c: head["map_sha1"].upper()
        check("one whose time disagrees with its row is refused",
              G.convert_demo(demo, board, ms + 500, "", "", out)[0], "othertime")
        check("one for another track is refused",
              G.convert_demo(demo, dict(board, leg=board["leg"] + 1), ms, "", "", out)[0],
              "othertrack")
        old = G.MAX_SECONDS
        G.MAX_SECONDS = 10
        check("one longer than MAX_SECONDS is refused before converting",
              G.convert_demo(demo, board, ms, "", "", out)[0], "toolong")
        G.MAX_SECONDS = old
        status, rec = G.convert_demo(demo, board, ms, "", "", out)
        check("the build that matches is converted", status, "ok")
        info, why = G.momindex.read_one(rec)
        check("momindex reads what it wrote", (why, info["millis"] if info else None),
              (None, ms))
        hdr = io.open(rec, encoding="utf-8").read().split("\nbegin\n")[0].split("\n")
        keys = [s.split(" ", 1)[0] for s in hdr]
        check("the header carries the demo's provenance and moves",
              [k for k in ("foreign", "mapbuild", "momdemo", "moves", "momquality") if k in keys],
              ["foreign", "mapbuild", "momdemo", "moves", "momquality"])
        check("a second grab of the same run is the one already held",
              G.convert_demo(demo, board, ms, "", "", out)[0], "have")

        # Filing: the replays row, and the board row linked only by its own time.
        c = db()
        c.execute("DELETE FROM runs WHERE tier='momentum'")
        c.execute("DELETE FROM replays WHERE kind='momentum'")
        c.execute("INSERT INTO replays (map, map_dir, track, leg, leaf, tier, style, player,"
                  " name, ticks, tickrate, millis, flags, node, submitted, bytes, kind, bound,"
                  " runid) VALUES (?,?,?,?,'0009999_old-00000000_run.rec','momentum','clean',?,"
                  " 'x',1,66.67,?,0,'import',1,1,'momentum',1,'old')",
                  (mp, head["map"], track, leg, str(head["steam_id"]), ms + 5000))
        old_rid = c.execute("SELECT id FROM replays WHERE leaf LIKE '%old%'").fetchone()[0]
        c.execute("INSERT INTO runs (map, track, leg, tier, style, player, name, ticks,"
                  " tickrate, millis, flags, node, runid, submitted, replay_id)"
                  " VALUES (?,?,?,'momentum','clean',?,'x',1,66.67,?,0,'mom','',111,?)",
                  (mp, track, leg, str(head["steam_id"]), ms + 4, old_rid))
        c.commit()
        conn = S.connect()
        try:
            added, linked = G.file_rec(conn, rec)
        finally:
            conn.close()
        r = c.execute("SELECT replay_id, millis, submitted FROM runs WHERE tier='momentum'"
                      " AND map=?", (mp,)).fetchone()
        new_rid = c.execute("SELECT id FROM replays WHERE leaf=?",
                            (os.path.basename(rec),)).fetchone()[0]
        check("a player who improved: their row is moved off the old run's demo",
              (linked, r[0] == new_rid), (1, True))
        check("...and the row itself is not re-dated or re-timed", (r[1], r[2]), (ms + 4, 111))
        conn = S.connect()
        try:
            again = G.link_exact(conn, 999999, mp, track, leg, str(head["steam_id"]), ms + 4)
            conn.commit()
        finally:
            conn.close()
        check("a row whose link is already its own run is never relinked", again, 0)

        # The tick end to end, with a capitalised BSP name standing in for the map.
        bd = tempfile.mkdtemp(prefix="boards-", dir=HOME)
        board_file(bd, "9_g1_t01.json", head["map"], head["track_type"], head["track_number"],
                   [row(sha, str(head["steam_id"]), ms / 1000.0)])
        c.execute("DELETE FROM runs WHERE tier='momentum'")
        c.execute("DELETE FROM replays WHERE kind='momentum'")
        c.execute("INSERT INTO runs (map, track, leg, tier, style, player, name, ticks,"
                  " tickrate, millis, flags, node, runid, submitted, replay_id)"
                  " VALUES (?,?,?,'momentum','clean',?,'x',1,66.67,?,0,'mom','',1,0)",
                  (mp, track, leg, str(head["steam_id"]), ms))
        c.commit()
        os.remove(rec)
        state = tempfile.mkdtemp(prefix="state-", dir=HOME)
        demos = tempfile.mkdtemp(prefix="demos-", dir=HOME)

        def fake_download(h, dest):
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            shutil.copy(FIXTURE, dest)
            return "ok"

        realdl = G.download
        G.download = fake_download
        try:
            run(["--boards", bd, "--state", state, "--demos", demos, "--out", out,
                 "--maps", HOME, "--delay", "0", "--go"])
        finally:
            G.download = realdl
        got = c.execute("SELECT replay_id > 0 FROM runs WHERE tier='momentum' AND map=?",
                        (mp,)).fetchone()
        check("a tick downloads, files and links the board row's demo", got, (1,))
        st = json.load(io.open(os.path.join(state, "state.json"), encoding="utf-8"))
        check("...and settles it, so it is never asked again", st["done"].get(sha), "ok")
        c.close()

        # A conversion the OS killed: the next tick counts it as a try.
        st["inflight"] = "e" * 40
        io.open(os.path.join(state, "state.json"), "w").write(json.dumps(st))
        run(["--boards", bd, "--state", state, "--demos", demos, "--out", out,
             "--maps", HOME, "--delay", "0"])
        st = json.load(io.open(os.path.join(state, "state.json"), encoding="utf-8"))
        check("a demo left in flight by a killed tick counts a try",
              (st["inflight"], st["later"].get("e" * 40, [0])[0]), (None, 1))
    finally:
        G.bsp_sha1 = real


def case_park_and_lock():
    S.migrate()
    bd = tempfile.mkdtemp(prefix="boards-", dir=HOME)
    board_file(bd, "1_g1_t01.json", "surf_p", 0, 1,
               [row("1" * 40, SID, 40.0), row("2" * 40, "76561198000000001", 41.0)])
    state = tempfile.mkdtemp(prefix="state-", dir=HOME)
    demos = tempfile.mkdtemp(prefix="demos-", dir=HOME)
    asked = []

    def refuse(code, obj):
        def f(h, dest):
            asked.append(h)
            raise G.Refused("HTTP %d" % code, obj=obj)
        return f

    realdl = G.download
    args = ["--boards", bd, "--state", state, "--demos", demos, "--out", HOME,
            "--maps", HOME, "--delay", "0", "--go"]
    sp = os.path.join(state, "state.json")
    try:
        G.download = refuse(429, False)
        run(args)
        check("a refusal stops the tick at once", len(asked), 1)
        st = json.load(io.open(sp, encoding="utf-8"))
        check("...and parks the grab", (st["park"]["n"], st["park"]["until"] - st["park"]["at"]),
              (1, G.COOLDOWN))
        check("...without settling or striking the demo it was refused",
              ("1" * 40 in st["done"], "1" * 40 in st["later"]), (False, False))
        asked.clear()
        run(args)
        check("a parked tick asks nothing", asked, [])
        for _ in range(G.STRIKES):
            st = json.load(io.open(sp, encoding="utf-8"))
            st["park"]["until"] = 1
            io.open(sp, "w").write(json.dumps(st))
            G.download = refuse(500, True)
            run(args)
        st = json.load(io.open(sp, encoding="utf-8"))
        check("a file the CDN keeps failing is struck, and left after STRIKES",
              st["later"].get("1" * 40, [0])[0], G.STRIKES)
        st["park"]["until"] = 1
        io.open(sp, "w").write(json.dumps(st))
        asked.clear()
        G.download = lambda h, dest: (asked.append(h), "gone")[1]
        run(args)
        check("...so the next tick moves on to the others", asked, ["2" * 40])
        st = json.load(io.open(sp, encoding="utf-8"))
        check("an answered tick lifts the park", st["park"], {})
        check("...and a file the CDN no longer has is settled as gone",
              st["done"].get("2" * 40), "gone")
    finally:
        G.download = realdl
    first = G.take_lock(state)
    second = G.take_lock(state)
    check("a second momgrab cannot take the lock", (first is not None, second), (True, None))
    first.close()


def main():
    for case in (case_queue_and_pick, case_download, case_bsp_case,
                 case_convert_and_file, case_park_and_lock):
        print("\n%s:" % case.__name__)
        case()
    print("\n%d failed%s" % (len(FAILED), (", skipped: " + "; ".join(SKIPPED)) if SKIPPED else ""))
    for f in FAILED:
        print("  " + f)
    return 1 if FAILED else 0


if __name__ == "__main__":
    raise SystemExit(main())
