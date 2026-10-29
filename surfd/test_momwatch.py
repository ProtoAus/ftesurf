#!/usr/bin/env python3
"""
test_momwatch.py -- the falsifier for P1117's Momentum rotation and re-walk.

    python surfd/test_momwatch.py

No network: momfetch.get is a fake leaderboard that records every page asked,
and momwatch's momfetch children are captured rather than run.  surfd is
imported against a throwaway home.
"""

import contextlib
import io
import json
import logging
import os
import re
import shutil
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


HOME = tempfile.mkdtemp(prefix="surfd-momw-")
os.environ.update(SURFD_HOME=HOME, SURFD_DB=os.path.join(HOME, "test.db"))
import surfd as S          # noqa: E402
import momwatch as MW      # noqa: E402
import momfetch as MF      # noqa: E402

# map -> (mapid, [(gamemode, trackType, trackNum)]); the gm-2 rows of surf_a are
# boards momfetch must never ask for (gm_of says surf).
CAT = {"surf_a": (1, [(1, 0, 1), (1, 1, 1), (1, 1, 2), (2, 0, 1)]),
       "surf_b": (2, [(1, 0, 1), (1, 2, 1)]),
       "bhop_c": (3, [(2, 0, 1)])}


def home(tag):
    d = tempfile.mkdtemp(prefix=tag + "-", dir=HOME)
    tsv = os.path.join(d, "momtracks.tsv")
    with io.open(tsv, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("# map\tmapid\ttier\tgamemode\ttrackType\ttrackNum\n")
        for name, (mid, boards) in sorted(CAT.items()):
            for gm, tt, tn in boards:
                fh.write("%s\t%d\t1\t%d\t%d\t%d\n" % (name, mid, gm, tt, tn))
    boards = os.path.join(d, "boards")
    os.makedirs(boards)
    return tsv, boards


def place(mid, tt, tn, rank):
    return {"rank": rank, "time": 10.0 + rank * 0.1,
            "hash": "%040x" % (mid * 10 ** 9 + tt * 10 ** 7 + tn * 10 ** 5 + rank),
            "steamid": str(76561198000000000 + rank), "alias": "p%d" % rank,
            "created": "2026-10-01T00:00:00.000Z", "url": ""}


def write_board(boards, mid, gm, tt, tn, ranks, total, mtime=None, **extra):
    rec = {"map": next(n for n, (i, _) in CAT.items() if i == mid), "mapid": mid,
           "gamemode": gm, "trackType": tt, "trackNum": tn, "total": total,
           "fetched": int(mtime or time.time()),
           "rows": [place(mid, tt, tn, r) for r in ranks]}
    rec.update(extra)
    p = os.path.join(boards, MF.board_key(mid, gm, tt, tn) + ".json")
    with io.open(p, "w", encoding="utf-8") as fh:
        json.dump(rec, fh)
    if mtime:
        os.utime(p, (mtime, mtime))
    return p


class FakeMomentum(object):
    """Every board has `size[(mid, tt, tn)]` places (default 10), ranked by time."""

    def __init__(self, size=None):
        self.size, self.asked = size or {}, []

    def __call__(self, url):
        m = re.match(r".*/maps/(\d+)/leaderboard\?gamemode=(\d)&trackType=(\d)"
                     r"&trackNum=(\d+)&take=(\d+)&skip=(\d+)$", url)
        mid, gm, tt, tn, take, skip = (int(x) for x in m.groups())
        self.asked.append((mid, tt, tn, skip))
        if (mid, tt, tn, skip) in getattr(self, "gone", ()) or                 (mid, tt, tn) in getattr(self, "ends", {}) and skip >= self.ends[(mid, tt, tn)]:
            raise MF.NoSuchBoard("HTTP 404")
        n = self.size.get((mid, tt, tn), 10)
        data = []
        for r in range(skip + 1, min(n, skip + take) + 1):
            p = place(mid, tt, tn, r)
            data.append({"rank": r, "time": p["time"], "replayHash": p["hash"],
                         "createdAt": p["created"],
                         "user": {"id": r, "steamID": p["steamid"], "alias": p["alias"]}})
        return json.dumps({"totalCount": n, "data": data}).encode()


def fetch(fake, argv):
    with patch.object(MF, "get", fake), patch.object(sys, "argv", ["momfetch.py"] + argv), \
            contextlib.redirect_stdout(io.StringIO()):
        return MF.main()


def walk_state(boards, key):
    """(re-walk cursor or None, when last walked) from momfetch's state file."""
    st = MF.rewalk_state(boards)
    return st["walking"].get(key), st["walked"].get(key, 0)


def set_walk(boards, walking=None, walked=None):
    MF.write_board(os.path.join(boards, MF.REWALK), {"walking": walking or {}, "walked": walked or {}})


def board(boards, mid, gm, tt, tn):
    return MF.load_board(os.path.join(boards, MF.board_key(mid, gm, tt, tn) + ".json"))


def case_tail_past_the_deepest_rank():
    """surf_believe: 661 rows held ranks to 861 of 861, and the tail re-asked 662-861."""
    tsv, boards = home("tail")
    # every board complete except surf_a main: 7 rows, ranks to 10, total 10
    for name, (mid, bl) in CAT.items():
        for gm, tt, tn in bl:
            write_board(boards, mid, gm, tt, tn, range(1, 11), 10)
    write_board(boards, 1, 1, 0, 1, [1, 2, 3, 6, 7, 9, 10], 10)
    fake = FakeMomentum()
    fetch(fake, ["--tracks", tsv, "--out", boards, "--take", "2", "--depth", "-1",
                 "--delay", "0", "--max", "10", "--go"])
    check("a board holding its deepest rank asks no tail page (the stuck loop)", fake.asked, [])
    write_board(boards, 1, 1, 0, 1, [1, 2, 3, 4], 10)
    fetch(fake, ["--tracks", tsv, "--out", boards, "--take", "2", "--depth", "-1",
                 "--delay", "0", "--max", "10", "--go"])
    check("...and a board that really is short still pages its tail",
          fake.asked, [(1, 0, 1, 4), (1, 0, 1, 6), (1, 0, 1, 8)])


def case_rewalk():
    tsv, boards = home("rewalk")
    now = int(time.time())
    for name, (mid, bl) in CAT.items():
        for gm, tt, tn in bl:
            write_board(boards, mid, gm, tt, tn, range(1, 11), 10)
    # two holed boards; surf_b main was walked longer ago, so it goes first
    write_board(boards, 1, 1, 0, 1, [1, 2, 3, 6, 7, 9, 10], 10)
    write_board(boards, 2, 1, 0, 1, [1, 5, 10], 10)
    set_walk(boards, walked={"1_g1_t01": now - 100, "2_g1_t01": now - 1000})
    args = ["--tracks", tsv, "--out", boards, "--take", "2", "--depth", "-1",
            "--delay", "0", "--rewalk", "--go"]
    fake = FakeMomentum()
    fetch(fake, args + ["--max", "2"])
    check("--rewalk walks the holed board walked longest ago, from rank 1",
          fake.asked, [(2, 0, 1, 0), (2, 0, 1, 2)])
    check("...and keeps its cursor in its own state, not the board file (P1117r3)",
          (walk_state(boards, "2_g1_t01")[0], "rewalk" in board(boards, 2, 1, 0, 1)), (4, False))
    fake.asked = []
    fetch(fake, args + ["--max", "10"])
    check("the next run resumes the same board where it stopped",
          fake.asked, [(2, 0, 1, 4), (2, 0, 1, 6), (2, 0, 1, 8)])
    b = board(boards, 2, 1, 0, 1)
    w = walk_state(boards, "2_g1_t01")
    check("...which then holds every place, walked and no longer under re-walk",
          (sorted(r["rank"] for r in b["rows"]), w[0], w[1] >= now),
          (list(range(1, 11)), None, True))
    fake.asked = []
    fetch(fake, args + ["--max", "10"])
    check("then the other holed board", [s for _, _, _, s in fake.asked], [0, 2, 4, 6, 8])
    fake.asked = []
    fetch(fake, args + ["--max", "10"])
    check("and with no hole left, nothing", fake.asked, [])
    fake.asked = []
    write_board(boards, 1, 1, 0, 1, [1, 2, 3, 6, 7, 9, 10], 10)
    fetch(fake, ["--tracks", tsv, "--out", boards, "--take", "2", "--depth", "-1",
                 "--delay", "0", "--max", "10", "--go"])
    check("without --rewalk a holed board is left alone", fake.asked, [])


def case_board_selector():
    tsv, boards = home("sel")
    for name, (mid, bl) in CAT.items():
        for gm, tt, tn in bl:
            write_board(boards, mid, gm, tt, tn, range(1, 11), 10)
    fake = FakeMomentum()
    fetch(fake, ["--tracks", tsv, "--out", boards, "--take", "2", "--depth", "0",
                 "--delay", "0", "--max", "3", "--refresh", "--go",
                 "--board", "1_g1_t11", "--board", "2_g1_t21", "--board", "1_g2_t01"])
    check("--board --refresh --depth 0 asks page 1 of exactly the boards named (gm-2 of a "
          "surf map is never one)", sorted(fake.asked), [(1, 1, 1, 0), (2, 2, 1, 0)])


def stale_home(tag):
    tsv, boards = home(tag)
    now = time.time()
    ages = {(2, 0, 1): 10, (2, 2, 1): 9, (1, 0, 1): 5, (1, 1, 1): 3, (1, 1, 2): 4,
            (3, 0, 1): 1.0 / 24}
    for name, (mid, bl) in CAT.items():
        for gm, tt, tn in bl:
            if (mid, tt, tn) in ages and MF.gm_of(name) == gm:
                write_board(boards, mid, gm, tt, tn, range(1, 11), 10,
                            mtime=now - ages[(mid, tt, tn)] * 86400)
    return tsv, boards, now


def case_stalest_boards():
    tsv, boards, now = stale_home("stale")
    cat = MF.read_tracks(tsv)
    cut = now - 86400
    check("rotation: whole maps, the map with the oldest board first, stalest board first",
          MW.stalest_boards(cat, boards, cut, 8),
          ["2_g1_t01", "2_g1_t21", "1_g1_t01", "1_g1_t12", "1_g1_t11"])
    check("...a map that does not fit whole waits for the next tick",
          MW.stalest_boards(cat, boards, cut, 3), ["2_g1_t01", "2_g1_t21"])
    check("...a map bigger than the share goes a share at a time",
          MW.stalest_boards(cat, boards, cut, 1), ["2_g1_t01"])
    os.remove(os.path.join(boards, "2_g1_t01.json"))
    check("...a board never fetched is the backfill's, and fresh ones are not asked",
          MW.stalest_boards(cat, boards, cut, 8), ["2_g1_t21", "1_g1_t01", "1_g1_t12", "1_g1_t11"])


def run_tick(argv, call):
    with patch.object(MW.subprocess, "call", call), patch.object(sys, "argv", argv), \
            contextlib.redirect_stdout(io.StringIO()):
        return MW.main()


def opt(cmd, name):
    return [cmd[i + 1] for i, c in enumerate(cmd) if c == name]


def case_tick_budget():
    tsv, boards, now = stale_home("tick")
    S.migrate()
    calls = []
    argv = ["momwatch.py", "--tracks", tsv, "--boards", boards, "--stale", "24",
            "--max", "40", "--delay", "0", "--depth", "-1", "--want", "25",
            "--backfill", "15", "--go"]
    rc = run_tick(argv, lambda cmd: calls.append(cmd) or 0)
    check("an idle tick runs the rotation, then the backfill", (rc, len(calls)), (0, 2))
    if len(calls) == 2:
        rot, back = calls
        check("the rotation re-asks page 1 of the stalest whole map that fits ROTATE",
              (opt(rot, "--board"), "--refresh" in rot, opt(rot, "--depth")),
              (["2_g1_t01", "2_g1_t21"], True, ["0"]))
        check("...and the extras share EXTRA_MAX of --backfill: 2 + 4, never 15",
              (opt(rot, "--max"), opt(back, "--max")), (["2"], [str(MW.EXTRA_MAX - 2)]))
        check("the backfill re-walks holed boards", "--rewalk" in back, True)
    # P1117 review 2: a refused rotation rests the extras and moves its boards to the
    # back; the backfill and the index still run.
    calls[:] = []
    argv_i = argv + ["--index"]
    rc = run_tick(argv_i, lambda cmd: calls.append(cmd) or (1 if "--board" in cmd else 0))
    check("P1117r2: a refused rotation still runs a plain backfill and the index",
          (rc, [("--board" in c, "--rewalk" in c, "momboards.py" in c[1]) for c in calls]),
          (1, [(True, False, False), (False, False, False), (False, False, True)]))
    asked = MW.rotation_state(boards)
    check("...and its boards go to the back of the rotation, their files left as fetched (P1117r3)",
          (sorted(k for k in asked if asked[k] > time.time() - 60),
           all(os.path.getmtime(os.path.join(boards, k + ".json")) < now - 86400
               for k in ("2_g1_t01", "2_g1_t21")),
           MW.stalest_boards(MF.read_tracks(tsv), boards, time.time() - 86400, 3)),
          (["2_g1_t01", "2_g1_t21"], True, ["1_g1_t01", "1_g1_t12", "1_g1_t11"]))
    os.remove(os.path.join(boards, MW.ROTATION))
    fake = FakeMomentum()
    if calls:
        fetch(fake, calls[0][2:])
    check("run for real, the rotation asks exactly those two first pages",
          sorted(fake.asked), [(2, 0, 1, 0), (2, 2, 1, 0)])
    calls[:] = []
    rc = run_tick(argv, lambda cmd: calls.append(cmd) or 0)
    check("P1117r1: after a refusal the next tick rests: no rotation, a plain backfill",
          (rc, len(calls), calls and "--board" in calls[0], calls and "--rewalk" in calls[0]),
          (0, 1, False, False))
    later = int(time.time()) + MW.QUIET + 1
    with patch.object(MW.time, "time", return_value=later):
        calls[:] = []
        run_tick(argv, lambda cmd: calls.append(cmd) or 0)
    check("...and after QUIET the extras are back", len(calls), 2)
    with patch.object(MW.time, "time", return_value=later + 2 * MW.QUIET):
        calls[:] = []
        rc = run_tick(argv_i, lambda cmd: calls.append(cmd) or
                      (1 if "--board" not in cmd and "momboards.py" not in cmd[1] else 0))
    check("P1117r2: a refused backfill still runs the index, and the tick says so",
          (rc, "momboards.py" in calls[-1][1]), (1, True))


def case_player_walk_refused_carries_on():
    tsv, boards, now = stale_home("walk")
    S.migrate()
    calls = []
    argv = ["momwatch.py", "--tracks", tsv, "--boards", boards, "--delay", "0", "--depth", "-1",
            "--backfill", "15", "--index", "--go"]

    def refused(*a, **k):
        raise MW.momfetch.Refused("HTTP 429")
    with patch.object(MW.momprofile, "step", refused):
        rc = run_tick(argv, lambda cmd: calls.append(cmd) or 0)
    check("P1117r1: a refused player walk rests the extras, the backfill and the index still run",
          (rc, [("--rewalk" in c, "momboards.py" in c[1]) for c in calls[1:]], bool(MW.resting(boards))),
          (0, [(False, False), (False, True)], True))


def case_p1117r2_walk_errors_carry_on():
    import http.client
    tsv, boards, now = stale_home("walkerr")
    S.migrate()
    calls = []
    argv = ["momwatch.py", "--tracks", tsv, "--boards", boards, "--delay", "0", "--depth", "-1",
            "--backfill", "15", "--index", "--go"]

    def broken(*a, **k):
        raise http.client.IncompleteRead(b"part", 10)
    with patch.object(MW.momprofile, "step", broken):
        rc = run_tick(argv, lambda cmd: calls.append(cmd) or 0)
    check("P1117r2: any error in the player walks rests them; backfill and index run",
          (rc, ["momboards.py" in c[1] for c in calls[1:]], bool(MW.resting(boards))),
          (0, [False, True], True))


def case_p1117r2_old_momfetch():
    tsv, boards, now = stale_home("oldfetch")
    S.migrate()
    calls, out = [], io.StringIO()
    argv = ["momwatch.py", "--tracks", tsv, "--boards", boards, "--delay", "0", "--depth", "-1",
            "--backfill", "15", "--go"]
    with patch.object(MW, "has_extras", lambda path: False), \
            patch.object(MW.subprocess, "call", lambda cmd: calls.append(cmd) or 0), \
            patch.object(sys, "argv", argv), contextlib.redirect_stdout(out):
        rc = MW.main()
    check("P1117r2: an older momfetch gets no --board and no --rewalk, and it is said",
          (rc, [("--board" in c, "--rewalk" in c) for c in calls], "predates P1117" in out.getvalue()),
          (0, [(False, False)], True))
    check("...and the shipped one is recognised", MW.has_extras(MW._momfetch_path()), True)


class Chunked(object):
    """A urlopen reply: `chunks` a read1 each, `length` its Content-Length, `clock`
    the monotonic seconds each read takes."""
    status = 200

    def __init__(self, chunks, length=None, clock=0.0):
        self.chunks, self.clock = list(chunks), clock
        self.headers = {"Content-Length": str(length)} if length is not None else {}

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def read1(self, n):
        Chunked.now += self.clock
        return self.chunks.pop(0) if self.chunks else b""


def case_p1117r2_momfetch_replies():
    import http.client
    import urllib.request

    class Reply(object):
        status = 200
        def __init__(self, body=b"", fail=None): self.body, self.fail = body, fail
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def read(self, n=-1):
            Reply.asked = n
            if self.fail:
                raise self.fail
            return self.body[:n] if n >= 0 else self.body
    got = []
    for label, reply in (("over MAX_BYTES", Reply(b"x" * (MF.MAX_BYTES + 5))),
                         ("cut short", Reply(fail=http.client.IncompleteRead(b"p", 9))),
                         ("a read timing out", Reply(fail=TimeoutError("read timed out")))):
        with patch.object(urllib.request, "urlopen", lambda req, timeout=None, r=reply: r):
            try:
                MF.get("https://api.momentum-mod.org/v1/x")
                got.append((label, "returned"))
            except MF.Refused:
                got.append((label, "refused"))
            except Exception as e:
                got.append((label, type(e).__name__))
    check("P1117r2: momfetch.get refuses an oversized, cut or timed-out reply, never crashes",
          [g[1] for g in got], ["refused"] * 3)
    tsv, boards = home("deep")
    write_board(boards, 1, 1, 0, 1, range(1, 11), 20)
    rc = fetch(lambda url: b"[" * 200000, ["--tracks", tsv, "--out", boards, "--take", "2",
                                           "--depth", "-1", "--delay", "0", "--max", "1",
                                           "--board", "1_g1_t01", "--go"])
    check("P1117r2: a reply nested past recursion is 'did not parse' (exit 1), not a crash", rc, 1)
    for name, (mid, bl) in CAT.items():
        for gm, tt, tn in bl:
            write_board(boards, mid, gm, tt, tn, range(1, 11), 10)
    write_board(boards, 1, 1, 0, 1, [1, 2, 3, 6, 7, 9, 10], 10)
    write_board(boards, 2, 1, 0, 1, [1, 5, 10], 10)
    old = time.time() - 5 * 86400
    os.utime(os.path.join(boards, "1_g1_t01.json"), (old, old))
    args = ["--tracks", tsv, "--out", boards, "--take", "2", "--depth", "-1", "--delay", "0",
            "--max", "10", "--rewalk", "--go"]

    def refuse4(code):
        def get(url):
            if "maps/1/" in url and url.endswith("skip=4"):
                raise MF.Refused("HTTP %d" % code, code)
            return FakeMomentum()(url)
        return get
    set_walk(boards, walking={"1_g1_t01": 4})
    fetch(refuse4(429), args)
    check("P1117r3: a host-wide 429 keeps the re-walk's cursor", walk_state(boards, "1_g1_t01")[0], 4)
    fetch(refuse4(500), args)
    fake = FakeMomentum()
    fetch(fake, args)
    w = walk_state(boards, "1_g1_t01")
    check("P1117r2: a re-walk refused by its board ends, and the next run walks another board",
          (w[0], w[1] > 0, sorted({m for m, _, _, _ in fake.asked})), (None, True, [2]))
    check("P1117r3: ...without touching that board's file, which the live refresh reads",
          os.path.getmtime(os.path.join(boards, "1_g1_t01.json")) < time.time() - 86400, True)
    got = []
    for label, reply in (("a trickle past the deadline", Chunked([b"x"] * 100, clock=1.0)),
                         ("a body short of its Content-Length", Chunked([b"[1,"], length=10)),
                         ("a whole one", Chunked([b"[1,", b"2]"], length=5))):
        Chunked.now = 0.0
        with patch.object(urllib.request, "urlopen", lambda req, timeout=None, r=reply: r), \
                patch.object(MF.time, "monotonic", lambda: Chunked.now):
            try:
                got.append(MF.get("https://api.momentum-mod.org/v1/x"))
            except MF.Refused as e:
                got.append(("refused", e.code))
    check("P1117r3: momfetch reads a whole reply in its deadline, and slow or short is no answer",
          got, [("refused", 0), ("refused", 0), b"[1,2]"])


def case_404s():
    tsv, boards = home("gone")
    for name, (mid, bl) in CAT.items():
        for gm, tt, tn in bl:
            write_board(boards, mid, gm, tt, tn, range(1, 11), 10)
    write_board(boards, 1, 1, 0, 1, [1, 2, 3, 6, 7, 9, 10], 10)          # holed
    write_board(boards, 2, 1, 0, 1, [1, 5, 10], 10)                      # holed, walked later
    fake = FakeMomentum()
    fake.ends = {(1, 0, 1): 4}         # surf_a main 404s from skip 4 on: it ends there
    args = ["--tracks", tsv, "--out", boards, "--take", "2", "--depth", "-1", "--delay", "0",
            "--rewalk", "--go"]
    fetch(fake, args + ["--max", "10"])
    b, w = board(boards, 1, 1, 0, 1), walk_state(boards, "1_g1_t01")
    check("P1117r1: a 404 past page 1 ends the re-walk there", (w[0], w[1] > 0, b["total"]),
          (None, True, 4))
    fake.asked = []
    fetch(fake, args + ["--max", "10"])
    check("...and the next run re-walks another board", sorted({(m, s) for m, _, _, s in fake.asked}),
          [(2, 0), (2, 2), (2, 4), (2, 6), (2, 8)])
    fake.ends, fake.gone, fake.asked = {}, {(1, 1, 1, 0)}, []
    fetch(fake, ["--tracks", tsv, "--out", boards, "--take", "2", "--depth", "0", "--delay", "0",
                 "--max", "1", "--refresh", "--go", "--board", "1_g1_t11"])
    b = board(boards, 1, 1, 1, 1)
    check("P1117r1: a page-1 404 on a board we hold rows of keeps them and records it",
          (fake.asked, len(b["rows"]), b.get("absent"), b.get("missing", 0) > 0),
          ([(1, 1, 1, 0)], 10, None, True))
    check("a totalCount past TOTAL_MAX is clamped, a bool is no count",
          (MF.parse_board({"totalCount": 10 ** 12, "data": []})[0],
           MF.parse_board({"totalCount": True, "data": []})[0]), (MF.TOTAL_MAX, 0))


def main():
    try:
        for case in (case_tail_past_the_deepest_rank, case_rewalk, case_board_selector,
                     case_stalest_boards, case_tick_budget, case_player_walk_refused_carries_on,
                     case_404s, case_p1117r2_walk_errors_carry_on, case_p1117r2_old_momfetch,
                     case_p1117r2_momfetch_replies):
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
