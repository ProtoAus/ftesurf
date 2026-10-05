#!/usr/bin/env python3
"""
test_momgrab.py -- the falsifier for momgrab.py.

    python surfd/test_momgrab.py

No network: `download` is driven through a fake urlopen, and the main loop's
fetches through a fake that copies a fixture.  The conversion cases need one
real Momentum demo, which is not committed (it is someone's run): set
MOMGRAB_FIXTURE to a .mtv, or they are skipped and say so.
"""

import argparse
import hashlib
import io
import json
import os
import shutil
import sqlite3
import sys
import tempfile
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


def board_file(d, name, mp, tt, tn, rows):
    with io.open(os.path.join(d, name), "w", encoding="utf-8") as fh:
        json.dump({"map": mp, "mapid": 1, "gamemode": 1, "trackType": tt, "trackNum": tn,
                   "total": len(rows), "fetched": 1, "rows": rows}, fh)


def row(h, sid, t):
    return {"rank": 0, "time": t, "hash": h, "steamid": sid, "alias": "a",
            "created": "", "url": G.CDN + h}


SID = "76561198356066955"


def case_queue_and_pick():
    bd = tempfile.mkdtemp(prefix="boards-", dir=HOME)
    st = tempfile.mkdtemp(prefix="state-", dir=HOME)
    board_file(bd, "1_g1_t01.json", "surf_a", 0, 1,
               [row("a" * 40, SID, 40.0), row("b" * 40, "76561198000000001", 41.0),
                row("c" * 40, "76561198000000002", 42.0), row("bad", SID, 43.0),
                row("d" * 40, "notasteamid", 44.0)])
    board_file(bd, "2_g1_t11.json", "surf_b", 1, 2, [row("e" * 40, SID, 10.0)])
    q, read, unread = G.refresh_queue(bd, os.path.join(st, "queue.json"), 2, 100)
    check("the queue holds each board's top places only",
          [len(q["boards"][f]["rows"]) for f in sorted(q["boards"])], [2, 1])
    check("...and a stage board files as its stage",
          (q["boards"]["2_g1_t11.json"]["track"], q["boards"]["2_g1_t11.json"]["leg"]), (0, 2))
    q, read, unread = G.refresh_queue(bd, os.path.join(st, "queue.json"), 2, 100)
    check("an unchanged board file is not read again", read, 0)
    q5, _, _ = G.refresh_queue(bd, os.path.join(st, "queue5.json"), 5, 100)
    check("a row with a bad hash or no SteamID is not queued",
          len(q5["boards"]["1_g1_t01.json"]["rows"]), 3)
    got = [c[3][0] for c in G.pick(q, {}, set(), set(), 10, set())]
    check("best place first, across boards", got, ["a", "e", "b"])
    got = [c[3][0] for c in G.pick(q, {}, set(), {"surf_a"}, 10, set())]
    check("a wanted map goes first", got, ["a", "b", "e"])
    got = [c[3][0] for c in G.pick(q, {"a" * 40: "ok"}, {("surf_b", 0, 2, SID)}, set(), 10, set())]
    check("settled demos and rows that hold one are skipped", got, ["b"])


class FakeResp(object):
    def __init__(self, body, status=200):
        self.body, self.status, self.pos = body, status, 0

    def read(self, n):
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
    body = b"x" * 1000
    h = hashlib.sha1(body).hexdigest()
    try:
        G.urllib.request.urlopen = lambda req, timeout=None: FakeResp(body)
        check("a file that hashes to its name is kept",
              (G.download(h, os.path.join(d, h + ".mtv")),
               os.path.exists(os.path.join(d, h + ".mtv"))), ("ok", True))
        check("one that does not is refused and removed",
              (G.download("0" * 40, os.path.join(d, "z.mtv")),
               sorted(os.listdir(d))), ("badhash", [h + ".mtv"]))

        def http(code):
            def f(req, timeout=None):
                raise urllib.error.HTTPError(req.full_url, code, "x", {}, None)
            return f

        G.urllib.request.urlopen = http(404)
        check("a 404 is the CDN's answer that it is gone",
              G.download(h, os.path.join(d, "g.mtv")), "gone")
        for code in (403, 429, 503):
            G.urllib.request.urlopen = http(code)
            try:
                G.download(h, os.path.join(d, "r.mtv"))
                got = "kept going"
            except G.Refused:
                got = "refused"
            check("HTTP %d parks the grab" % code, got, "refused")
        old = G.MAX_BYTES
        G.MAX_BYTES = 100
        G.urllib.request.urlopen = lambda req, timeout=None: FakeResp(body)
        check("a file over MAX_BYTES is refused and not kept",
              (G.download(h, os.path.join(d, "big.mtv")),
               os.path.exists(os.path.join(d, "big.mtv.part"))), ("toobig", False))
        G.MAX_BYTES = old
    finally:
        G.urllib.request.urlopen = real


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
    board = {"map": head["map"].lower(), "track": track, "leg": leg}
    out = os.path.join(HOME, "momentum")
    real = G.bsp_sha1
    try:
        G.bsp_sha1 = lambda mp, d, c: "0" * 40
        check("a demo on another build of the map is refused",
              G.convert_demo(demo, board, ms, "", "", out), ("otherbuild", None))
        G.bsp_sha1 = lambda mp, d, c: head["map_sha1"].upper()
        check("one whose time disagrees with its row is refused",
              G.convert_demo(demo, board, ms + 500, "", "", out)[0], "othertime")
        check("one for another track is refused",
              G.convert_demo(demo, dict(board, leg=board["leg"] + 1), ms, "", "", out)[0],
              "othertrack")
        status, rec = G.convert_demo(demo, board, ms, "", "", out)
        check("the build that matches is converted", status, "ok")
        info, why = G.momindex.read_one(rec)
        check("momindex reads what it wrote", (why, info["millis"] if info else None),
              (None, ms))
        text = io.open(rec, encoding="utf-8").read()
        hdr = text.split("\nbegin\n")[0].split("\n")
        keys = [s.split(" ", 1)[0] for s in hdr]
        check("the header carries the demo's provenance and moves",
              [k for k in ("foreign", "mapbuild", "momdemo", "moves", "momquality") if k in keys],
              ["foreign", "mapbuild", "momdemo", "moves", "momquality"])
        check("...and names the build it was checked against",
              [s for s in hdr if s.startswith("mapbuild")][0].split()[-1], "ok")
        check("a second grab of the same run is the one already held",
              G.convert_demo(demo, board, ms, "", "", out)[0], "have")
        G.bsp_sha1 = lambda mp, d, c: None
        os.remove(rec)
        status, rec = G.convert_demo(demo, board, ms, "", "", out)
        check("a map with no BSP here is filed anyway, marked nomap",
              (status, [s for s in io.open(rec, encoding="utf-8").read().split("\n")
                        if s.startswith("mapbuild")][0].split()[-1]), ("ok", "nomap"))

        # The tick end to end: a board row with no recording gets one.
        bd = tempfile.mkdtemp(prefix="boards-", dir=HOME)
        board_file(bd, "9_g1_t01.json", head["map"], head["track_type"], head["track_number"],
                   [row(sha, str(head["steam_id"]), ms / 1000.0)])
        db = sqlite3.connect(os.environ["SURFD_DB"])
        db.execute("DELETE FROM runs WHERE tier='momentum'")
        db.execute("DELETE FROM replays WHERE kind='momentum'")
        db.execute("INSERT INTO runs (map, track, leg, tier, style, player, name, ticks,"
                   " tickrate, millis, flags, node, runid, submitted, replay_id)"
                   " VALUES (?,?,?,'momentum','clean',?,'x',1,66.67,?,0,'mom','',1,0)",
                   (board["map"], track, leg, str(head["steam_id"]), ms))
        db.commit()
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
        got = db.execute("SELECT replay_id > 0 FROM runs WHERE tier='momentum' AND map=?",
                         (board["map"],)).fetchone()
        check("a tick downloads, files and links the board row's demo", got, (1,))
        st = json.load(io.open(os.path.join(state, "state.json"), encoding="utf-8"))
        check("...and settles it, so it is never asked again", st["done"].get(sha), "ok")
        db.close()
    finally:
        G.bsp_sha1 = real


def run(argv):
    old = sys.argv
    sys.argv = ["momgrab.py"] + argv
    try:
        return G.main()
    finally:
        sys.argv = old


def case_park():
    S.migrate()
    bd = tempfile.mkdtemp(prefix="boards-", dir=HOME)
    board_file(bd, "1_g1_t01.json", "surf_p", 0, 1,
               [row("1" * 40, SID, 40.0), row("2" * 40, "76561198000000001", 41.0)])
    state = tempfile.mkdtemp(prefix="state-", dir=HOME)
    demos = tempfile.mkdtemp(prefix="demos-", dir=HOME)
    asked = []

    def refuse(h, dest):
        asked.append(h)
        raise G.Refused("HTTP 429")

    realdl = G.download
    G.download = refuse
    args = ["--boards", bd, "--state", state, "--demos", demos, "--out", HOME,
            "--maps", HOME, "--delay", "0", "--go"]
    try:
        run(args)
        check("a refusal stops the tick at once", len(asked), 1)
        st = json.load(io.open(os.path.join(state, "state.json"), encoding="utf-8"))
        check("...and parks the grab", (st["park"]["n"], st["park"]["until"] - st["park"]["at"]),
              (1, G.COOLDOWN))
        check("...without settling the demo it was refused", "1" * 40 in st["done"], False)
        asked.clear()
        run(args)
        check("a parked tick asks nothing", asked, [])
        st["park"]["until"] = 1
        io.open(os.path.join(state, "state.json"), "w", encoding="utf-8").write(json.dumps(st))
        G.download = lambda h, dest: "gone"
        run(args)
        st = json.load(io.open(os.path.join(state, "state.json"), encoding="utf-8"))
        check("an answered tick lifts the park", st["park"], {})
        check("...and a demo the CDN no longer has is settled as gone",
              st["done"].get("1" * 40), "gone")
    finally:
        G.download = realdl


def main():
    for case in (case_queue_and_pick, case_download, case_convert_and_file, case_park):
        print("\n%s:" % case.__name__)
        case()
    print("\n%d failed%s" % (len(FAILED), (", skipped: " + "; ".join(SKIPPED)) if SKIPPED else ""))
    for f in FAILED:
        print("  " + f)
    return 1 if FAILED else 0


if __name__ == "__main__":
    raise SystemExit(main())
