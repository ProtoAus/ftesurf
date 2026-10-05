#!/usr/bin/env python3
"""
test_ksfimport.py -- the falsifier for ksfimport.py's map-seeded path.

    python surfd/test_ksfimport.py

No network: `fetch` is replaced by a fake KSF that serves canned pages and
records every path asked, so a case can say what was REQUESTED as well as what
was written.  surfd is imported against a throwaway home.
"""

import argparse
import http.client
import io
import json
import os
import re
import sqlite3
import sys
import tempfile
import urllib.parse

FAILED = []
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)


def check(label, got, want):
    ok = got == want
    print("%-4s %-62s %r" % ("ok" if ok else "FAIL", label, got))
    if not ok:
        FAILED.append("%s: got %r, want %r" % (label, got, want))


HOME = tempfile.mkdtemp(prefix="surfd-ksf-")
os.environ.update(SURFD_HOME=HOME, SURFD_DB=os.path.join(HOME, "test.db"))
import surfd as S        # noqa: E402
import ksfimport as K    # noqa: E402

REAL_FETCH = K.fetch     # the cases below swap in FakeKSF

STAGED = {"isLinear": False, "cp_count": 2, "b_count": 1}
LINEAR = {"isLinear": True, "cp_count": 4, "b_count": 0}


class FakeKSF(object):
    """Search rows by prefix (a typeahead, like theirs), the map list in
    KSF_LIST_PAGE pages, and boards by size: (map, zone) is Forward, and
    (map, zone, mode) any other style.  `top` maps a board to extra players
    ranked above everyone, as if they set times after the board was paged."""

    def __init__(self, maps, boards, refuse_after=None, slow=0.0, listed=None):
        self.maps, self.boards = maps, boards
        self.refuse_after, self.slow = refuse_after, slow
        self.listed = sorted(maps) if listed is None else listed
        self.top = {}
        self.fail = set()           # boards answered with HTTP 500
        self.mangle = None          # f(rows) -> rows, applied to every page
        self.stuck_list = False     # the map list ignores its offset
        self.asked = []

    def __call__(self, url):
        path = url[len(K.KSF_BASE):]
        self.asked.append(path)
        if self.refuse_after is not None and len(self.asked) > self.refuse_after:
            raise K.Refused("HTTP 429")
        if path.startswith("/api/maps/search/"):
            q = urllib.parse.unquote(path[len("/api/maps/search/"):])
            hits = [dict(info, name=n) for n, info in sorted(self.maps.items())
                    if n.startswith(q)]
            return json.dumps(hits[:5])
        m = re.match(r"/api/maps/new\?offset=(\d+)$", path)
        if m:
            off = 0 if self.stuck_list else int(m.group(1))
            return json.dumps([dict(self.maps[n], name=n)
                               for n in self.listed[off:off + K.KSF_LIST_PAGE]])
        m = re.match(r"/api/maps/([^/]+)/records/zone/(\d+)/(\d+)\?game=css&mode=(\d)$",
                     path)
        mp, zone, start = urllib.parse.unquote(m.group(1)), int(m.group(2)), int(m.group(3))
        mode = int(m.group(4))
        key = (mp, zone) if mode == 0 else (mp, zone, mode)
        if (mp, zone, mode) in self.fail:
            raise K.Refused("HTTP 500", 500)
        extra = self.top.get(key, 0)
        board = ([("STEAM_0:0:%d" % (900 + i), 1.0 + i) for i in range(extra)]
                 + [("STEAM_0:1:%d" % r, 30.0 + zone + mode + r * 0.01 + self.slow)
                    for r in range(1, self.boards.get(key, 0) + 1)])
        rows = [{"rank": start + i, "name": "p%s" % sid[10:],
                 "steamID": sid, "time": t, "date": 1790000000 + start + i}
                for i, (sid, t) in enumerate(board[start - 1:start - 1 + K.KSF_PAGE])]
        return json.dumps(self.mangle(rows) if self.mangle else rows)


def pages(fake, modes=False):
    """Board requests as (map, zone, startRank[, mode]), in the order asked."""
    out = []
    for p in fake.asked:
        m = re.match(r"/api/maps/([^/]+)/records/zone/(\d+)/(\d+)\?game=css&mode=(\d)", p)
        if m:
            t = (m.group(1), int(m.group(2)), int(m.group(3)))
            out.append(t + (int(m.group(4)),) if modes else t)
    return out


def fresh_cache():
    return tempfile.mkdtemp(prefix="ksfcache-", dir=HOME)


def case_mapping():
    check("zone 0 is the main track", K.zone_track_leg(0), (0, 0))
    check("zone 2 is stage 2", K.zone_track_leg(2), (0, 2))
    check("zone 30 is stage 30", K.zone_track_leg(30), (0, 30))
    check("zone 31 is bonus 1", K.zone_track_leg(31), (1, 0))
    check("zone 37 is bonus 7", K.zone_track_leg(37), (7, 0))
    check("staged map: main, its stages, its bonus", K.zones_of(STAGED), [0, 1, 2, 31])
    check("linear map: cp_count is checkpoints, no stage boards",
          K.zones_of(LINEAR), [0])
    check("isLinear missing: stages are not guessed",
          K.zones_of({"cp_count": 3, "b_count": 2}), [0, 31, 32])


def case_exact_name():
    fake = FakeKSF({"surf_utopia_njv": LINEAR}, {})
    K.fetch = fake
    cache = fresh_cache()
    got = K.map_info("surf_utopia", cache, K.Pacer(0, 5))
    check("typeahead answer for another map is not this map", got, None)
    K.map_info("surf_utopia", cache, K.Pacer(0, 5))
    check("the search is cached: asked once", len(fake.asked), 1)


def case_paging_and_depth():
    fake = FakeKSF({"surf_a": {"isLinear": True, "cp_count": 0, "b_count": 0}},
                   {("surf_a", 0): 47})
    K.fetch = fake
    cache = fresh_cache()
    infos, absent, left = K.sweep_maps(["surf_a"], cache, -1, K.Pacer(0, 50))
    check("whole board: pages asked at ranks 1, 21, 41",
          [p[2] for p in pages(fake)], [1, 21, 41])
    doc = K.board_load(cache, "surf_a", 0)
    check("whole board: 47 rows held", len(doc["rows"]), 47)
    check("a short page ends the board", doc["done"], True)
    check("nothing left wanting", left, 0)

    fake = FakeKSF({"surf_b": {"isLinear": True, "cp_count": 0, "b_count": 0}},
                   {("surf_b", 0): 100})
    K.fetch = fake
    cache = fresh_cache()
    K.sweep_maps(["surf_b"], cache, 40, K.Pacer(0, 50))
    doc = K.board_load(cache, "surf_b", 0)
    check("depth 40: two pages, 40 rows", (len(pages(fake)), len(doc["rows"])), (2, 40))
    check("depth 40: the board is not marked done", doc["done"], False)


def case_shallowest_first_and_cursor():
    flat = {"isLinear": True, "cp_count": 0, "b_count": 0}
    fake = FakeKSF({"surf_a": flat, "surf_b": flat},
                   {("surf_a", 0): 60, ("surf_b", 0): 60})
    K.fetch = fake
    cache = fresh_cache()
    K.sweep_maps(["surf_a", "surf_b"], cache, -1, K.Pacer(0, 5))  # 2 searches + 3
    check("every board reaches page 2 before any reaches page 3",
          pages(fake), [("surf_a", 0, 1), ("surf_b", 0, 1), ("surf_a", 0, 21)])
    fake.asked = []
    K.sweep_maps(["surf_a", "surf_b"], cache, -1, K.Pacer(0, 3))
    check("the cache is the cursor: a re-run resumes, no search repeated",
          [p for p in fake.asked if "search" in p], [])
    check("...and asks the next pages",
          pages(fake), [("surf_b", 0, 21), ("surf_a", 0, 41), ("surf_b", 0, 41)])


def case_linear_asks_no_stages():
    fake = FakeKSF({"surf_lin": LINEAR}, {("surf_lin", 0): 5})
    K.fetch = fake
    K.sweep_maps(["surf_lin"], fresh_cache(), -1, K.Pacer(0, 20))
    check("a linear map's checkpoints are never asked for",
          sorted({p[1] for p in pages(fake)}), [0])


def write_args(listfile, cache, mapsdir, **kw):
    a = argparse.Namespace(from_maps=listfile, depth=-1, delay=0.0, cache=cache,
                           max=None, maps=mapsdir, go=True, seed=None,
                           from_boards=None)
    for k, v in kw.items():
        setattr(a, k, v)
    return a


def run_main(argv):
    old = sys.argv
    sys.argv = ["ksfimport.py"] + argv
    try:
        return K.main()
    finally:
        sys.argv = old


def case_write_and_filter():
    S.migrate()
    mapsdir = tempfile.mkdtemp(prefix="maps-", dir=HOME)
    io.open(os.path.join(mapsdir, "surf_st.bsp"), "w").close()
    listfile = os.path.join(HOME, "maps.txt")
    with io.open(listfile, "w", encoding="utf-8") as fh:
        fh.write("surf_st\nsurf_notinstalled   # not in the library\n")
    fake = FakeKSF({"surf_st": STAGED, "surf_notinstalled": STAGED},
                   {("surf_st", 0): 3, ("surf_st", 2): 2, ("surf_st", 31): 1,
                    ("surf_notinstalled", 0): 9})
    K.fetch = fake
    cache = fresh_cache()
    rc = run_main(["--from-maps", listfile, "--cache", cache, "--delay", "0",
                   "--maps", mapsdir, "--modes", "0", "--go"])
    check("main exits 0", rc, 0)
    check("a map this install cannot load is never asked about",
          [p for p in fake.asked if "notinstalled" in p], [])
    db = sqlite3.connect(os.environ["SURFD_DB"])
    got = db.execute("SELECT track, leg, COUNT(*) FROM runs WHERE tier='ksf'"
                     " AND map='surf_st' GROUP BY 1, 2 ORDER BY 1, 2").fetchall()
    check("rows filed by board: main 3, stage 2 has 2, bonus 1 has 1",
          got, [(0, 0, 3), (0, 2, 2), (1, 0, 1)])
    pid = db.execute("SELECT player FROM runs WHERE tier='ksf' AND map='surf_st'"
                     " AND track=0 AND leg=0 ORDER BY millis LIMIT 1").fetchone()[0]
    check("player is the steamid64 of STEAM_0:1:1",
          pid, str(76561197960265728 + 1 * 2 + 1))
    best = db.execute("SELECT millis FROM runs WHERE tier='ksf' AND map='surf_st'"
                      " AND track=0 AND leg=0 AND player=?", (pid,)).fetchone()[0]

    # A slower time for the same player must not replace the faster one.
    bf = K.board_path(cache, "surf_st", 0)
    doc = json.load(io.open(bf, encoding="utf-8"))
    for r in doc["rows"]:
        r["time"] += 5.0
    io.open(bf, "w", encoding="utf-8").write(json.dumps(doc))
    fake.asked = []
    run_main(["--from-maps", listfile, "--cache", cache, "--delay", "0",
              "--maps", mapsdir, "--modes", "0", "--go"])
    check("a re-run of a finished cache makes no request", fake.asked, [])
    again = db.execute("SELECT millis FROM runs WHERE tier='ksf' AND map='surf_st'"
                       " AND track=0 AND leg=0 AND player=?", (pid,)).fetchone()[0]
    check("a slower re-import keeps the faster time", again, best)
    db.close()


def case_refusal():
    flat = {"isLinear": True, "cp_count": 0, "b_count": 0}
    fake = FakeKSF({"surf_r": flat}, {("surf_r", 0): 100}, refuse_after=3)
    K.fetch = fake
    cache = fresh_cache()
    mapsdir = tempfile.mkdtemp(prefix="maps-", dir=HOME)
    io.open(os.path.join(mapsdir, "surf_r.bsp"), "w").close()
    listfile = os.path.join(HOME, "maps_r.txt")
    io.open(listfile, "w", encoding="utf-8").write("surf_r\n")
    rows, _ = K.maps_mode(write_args(listfile, cache, mapsdir, modes=[0]), {"surf_r"}, cache)
    check("a refusal stops: nothing asked after the refused request",
          len(fake.asked), 4)
    check("...and what was cached before it is still used", len(rows), 40)

    # A refused SEARCH must stop the sweep and must not be cached as "KSF has
    # no such map" -- that answer would be kept forever.
    fake = FakeKSF({"surf_r": flat, "surf_s": flat}, {}, refuse_after=0)
    K.fetch = fake
    cache = fresh_cache()
    try:
        K.sweep_maps(["surf_r", "surf_s"], cache, -1, K.Pacer(0, 10))
        raised = False
    except K.Refused:
        raised = True
    check("a refused search raises rather than reading as absent", raised, True)
    check("...nothing is asked after it", len(fake.asked), 1)
    check("...and no answer is cached for the refused map",
          os.path.exists(os.path.join(cache, "maps", "surf_r.json")), False)


def case_no_answer():
    """The real fetch, with urlopen failing the ways 2026-10-03's run saw."""
    import urllib.request
    real = urllib.request.urlopen
    for label, exc in (("a read that timed out", TimeoutError("The read operation timed out")),
                       ("a connection dropped mid-reply",
                        http.client.RemoteDisconnected("Remote end closed connection")),
                       ("a reset", ConnectionResetError(104, "Connection reset by peer"))):
        calls = []

        def fail(req, timeout=None, exc=exc):
            calls.append(req.full_url)
            raise exc

        urllib.request.urlopen = fail
        try:
            REAL_FETCH(K.KSF_BASE + "/api/maps/search/surf_x")
            got = "returned"
        except K.Refused:
            got = "refused"
        except Exception as e:      # the crash this case exists for
            got = type(e).__name__
        finally:
            urllib.request.urlopen = real
        check("%s stops as a refusal" % label, got, "refused")
        check("...after one attempt", len(calls), 1)


FLAT = {"isLinear": True, "cp_count": 0, "b_count": 0}


def case_modes():
    """Each KSF style is a board of its own, filed under its own style."""
    fake = FakeKSF({"surf_m": STAGED, "surf_n": STAGED},
                   {("surf_m", 0): 25, ("surf_m", 0, 1): 3, ("surf_m", 1, 1): 2,
                    ("surf_n", 0): 4})
    K.fetch = fake
    cache = fresh_cache()
    got = []
    K.sweep_maps(["surf_m", "surf_n"], cache, -1, K.Pacer(0, 100), [0, 1], fetched=got)
    asked = pages(fake, modes=True)
    check("Sideways main is asked on both maps",
          sorted((p[0], p[1]) for p in asked if p[3] == 1 and p[1] == 0),
          [("surf_m", 0), ("surf_n", 0)])
    check("Sideways stages and bonus only where Sideways main has rows",
          sorted({(p[0], p[1]) for p in asked if p[3] == 1 and p[1] > 0}),
          [("surf_m", 1), ("surf_m", 2), ("surf_m", 31)])
    check("Forward keeps its pre-mode cache name",
          os.path.exists(os.path.join(cache, "boards", "surf_m", "z0.json")), True)
    check("Sideways main is its own file, 3 rows",
          len(K.board_load(cache, "surf_m", 0, 1)["rows"]), 3)
    rows = [r for mp, z, m, page in got
            for r in (K.rec_row(mp, z, m, x) for x in page) if r]
    check("a Sideways row is filed as style sw, on its stage",
          sorted({(r["map"], r["leg"], r["style"]) for r in rows if r["style"] != "clean"}),
          [("surf_m", 0, "sw"), ("surf_m", 1, "sw")])
    check("every style a mode files under is one surfd reads",
          all(v in S.STYLES_READ for v in K.KSF_MODES.values()), True)
    check("...and none of the new ones is one a lobby can submit",
          [v for v in K.KSF_MODES.values() if v in S.STYLES], ["clean"])


def case_merge_and_refresh():
    fake = FakeKSF({"surf_g": FLAT}, {("surf_g", 0): 30})
    K.fetch = fake
    cache = fresh_cache()
    K.sweep_maps(["surf_g"], cache, 20, K.Pacer(0, 5))
    fake.top[("surf_g", 0)] = 1          # a new record lands above everyone
    K.sweep_maps(["surf_g"], cache, -1, K.Pacer(0, 5))
    doc = K.board_load(cache, "surf_g", 0)
    ids = [r["steamID"] for r in doc["rows"]]
    check("a player repeated across a rank shift is held once", len(ids), len(set(ids)))
    check("...and every player paged past is held", len(ids), 30)
    check("...and the short page ended the board", doc["done"], True)
    K.board_page(cache, "surf_g", 0, K.Pacer(0, 1), top=True)
    doc = K.board_load(cache, "surf_g", 0)
    check("a refreshed first page brings the new record in",
          "STEAM_0:0:900" in [r["steamID"] for r in doc["rows"]], True)
    check("...and reopens the board, whose tail moved", doc["done"], False)
    old = [r for r in doc["rows"] if r["steamID"] == "STEAM_0:1:5"][0]["time"]
    fake.slow = -10.0                    # everybody got faster
    K.board_page(cache, "surf_g", 0, K.Pacer(0, 1), top=True)
    doc = K.board_load(cache, "surf_g", 0)
    new = [r for r in doc["rows"] if r["steamID"] == "STEAM_0:1:5"][0]["time"]
    check("a faster time replaces the held one", round(old - new, 3), 10.0)
    fake.slow = 0.0


def watch_setup(n_maps, installed, rows_each=45, prefix="surf_w", **fake_kw):
    S.migrate()
    names = ["%s%02d" % (prefix, i) for i in range(n_maps)]
    fake = FakeKSF({n: FLAT for n in names}, {(n, 0): rows_each for n in names}, **fake_kw)
    K.fetch = fake
    cache = fresh_cache()
    mapsdir = tempfile.mkdtemp(prefix="maps-", dir=HOME)
    for n in names[:installed]:
        io.open(os.path.join(mapsdir, n + ".bsp"), "w").close()
    return fake, cache, mapsdir, names


def tick(cache, mapsdir, budget, go=True):
    argv = ["--watch", "--cache", cache, "--maps", mapsdir, "--delay", "0",
            "--max", str(budget)]
    return run_main(argv + (["--go"] if go else []))


def ksf_rows(where="1=1", args=()):
    db = sqlite3.connect(os.environ["SURFD_DB"])
    try:
        return db.execute("SELECT COUNT(*) FROM runs WHERE tier='ksf' AND " + where,
                          args).fetchone()[0]
    finally:
        db.close()


def case_watch():
    fake, cache, mapsdir, names = watch_setup(12, installed=11)
    db = sqlite3.connect(os.environ["SURFD_DB"])
    now = int(K.time.time())
    db.execute("INSERT OR REPLACE INTO mapwant (map, asked, first, last)"
               " VALUES ('surf_w07', 1, ?, ?)", (now, now))
    db.commit()
    db.close()

    tick(cache, mapsdir, 3)
    check("tick 1: the map list, a page at a time, then the wanted map",
          fake.asked, ["/api/maps/new?offset=0", "/api/maps/new?offset=10",
                       "/api/maps/surf_w07/records/zone/0/1?game=css&mode=0"])
    check("...and only that page's rows are written",
          ksf_rows("map='surf_w07'"), 20)
    fake.asked = []
    tick(cache, mapsdir, 3)
    check("tick 2: the wanted map's other styles before any other map",
          pages(fake, modes=True), [("surf_w07", 0, 1, 1), ("surf_w07", 0, 1, 2),
                                    ("surf_w07", 0, 1, 3)])
    fake.asked = []
    tick(cache, mapsdir, 3)
    check("tick 3: the wanted map to its end, then the shallowest board",
          pages(fake, modes=True), [("surf_w07", 0, 21, 0), ("surf_w07", 0, 41, 0),
                                    ("surf_w00", 0, 1, 0)])
    check("the wanted map is whole on the board", ksf_rows("map='surf_w07'"), 45)
    tick(cache, mapsdir, 400)
    check("a map that is not installed is never asked about",
          [p for p in fake.asked if "surf_w11" in p and "/new?" not in p], [])
    check("...and nothing of it is filed", ksf_rows("map='surf_w11'"), 0)
    check("every installed board ends up whole", ksf_rows("map LIKE 'surf_w%'"), 11 * 45)
    fake.asked = []
    tick(cache, mapsdir, 10)
    check("a finished, fresh crawl asks nothing", fake.asked, [])
    idx = json.load(io.open(os.path.join(cache, "index.json"), encoding="utf-8"))
    check("the index knows every board it paged", len(idx), 11 * 4)


def case_watch_refusal_parks():
    fake, cache, mapsdir, names = watch_setup(3, installed=3, prefix="surf_p",
                                              refuse_after=2)
    tick(cache, mapsdir, 5)
    park = json.load(io.open(os.path.join(cache, ".refused"), encoding="utf-8"))
    check("a refusal parks the crawl", (park["n"], park["until"] - park["at"]),
          (1, K.COOLDOWN))
    check("...after the refused request, nothing", len(fake.asked), 3)
    fake.asked = []
    tick(cache, mapsdir, 5)
    check("a parked tick asks nothing", fake.asked, [])
    park["until"] = park["at"] = 1
    io.open(os.path.join(cache, ".refused"), "w", encoding="utf-8").write(json.dumps(park))
    fake.refuse_after = 0
    tick(cache, mapsdir, 5)
    park = json.load(io.open(os.path.join(cache, ".refused"), encoding="utf-8"))
    check("a second refusal parks twice as long", park["until"] - park["at"], 2 * K.COOLDOWN)
    park["until"] = park["at"] = 1
    io.open(os.path.join(cache, ".refused"), "w", encoding="utf-8").write(json.dumps(park))
    fake.refuse_after = None
    tick(cache, mapsdir, 5)
    check("an answered tick lifts the park",
          os.path.exists(os.path.join(cache, ".refused")), False)


def case_watch_dry_and_owed():
    fake, cache, mapsdir, names = watch_setup(2, installed=2, rows_each=5,
                                              prefix="surf_d")
    tick(cache, mapsdir, 5, go=False)
    check("a dry tick asks nothing: it could not write what it fetched", fake.asked, [])
    real = K.write_rows

    def locked(rows):
        raise sqlite3.OperationalError("database is locked")

    K.write_rows = locked
    try:
        rc = tick(cache, mapsdir, 4)
    finally:
        K.write_rows = real
    check("a failed write leaves its boards owed",
          (rc, sorted(b[0] for b in K.owed_boards(cache))), (1, ["surf_d00"] * 3))
    fake.asked = []
    tick(cache, mapsdir, 0)
    check("the next tick files them whole, asking nothing",
          (ksf_rows("map='surf_d00'"), fake.asked), (5, []))
    check("...and they are owed no more", K.owed_boards(cache), [])

    # A run killed between fetching and filing: watch_mode returns its rows and
    # nothing writes them -- the owed markers are all that survives.
    fake, cache, mapsdir, names = watch_setup(2, installed=2, rows_each=45,
                                              prefix="surf_k")
    args = argparse.Namespace(delay=0.0, max=6)
    K.watch_mode(args, set(names), cache)
    held = len(K.board_load(cache, "surf_k00", 0)["rows"])
    check("control: the killed tick cached rows and filed none",
          (held > 0, ksf_rows("map='surf_k00'")), (True, 0))
    tick(cache, mapsdir, 0)
    check("the next tick files every row the killed one cached",
          ksf_rows("map='surf_k00'"), held)

    # A dry by-hand run caches pages and writes nothing; the crawl files them.
    fake, cache, mapsdir, names = watch_setup(1, installed=1, rows_each=30,
                                              prefix="surf_h")
    listfile = os.path.join(HOME, "maps_h.txt")
    io.open(listfile, "w", encoding="utf-8").write("surf_h00\n")
    run_main(["--from-maps", listfile, "--cache", cache, "--delay", "0",
              "--maps", mapsdir, "--modes", "0"])
    check("control: a dry --from-maps filed nothing", ksf_rows("map='surf_h00'"), 0)
    tick(cache, mapsdir, 0)
    check("...and the next tick files what it cached", ksf_rows("map='surf_h00'"), 30)


def case_review_findings():
    # 1. New players above the cursor must not stall it (60 of 60 requests to
    #    one URL in review).
    fake = FakeKSF({"surf_s": FLAT}, {("surf_s", 0): 100})
    K.fetch = fake
    cache = fresh_cache()
    K.sweep_maps(["surf_s"], cache, 40, K.Pacer(0, 10))
    fake.top[("surf_s", 0)] = 25
    fake.asked = []
    K.sweep_maps(["surf_s"], cache, -1, K.Pacer(0, 8))
    starts = [p[2] for p in pages(fake)]
    check("25 players above the cursor: every request a new rank", starts,
          [41, 61, 81, 101, 121])
    check("...and the board is walked to its end", K.board_load(cache, "surf_s", 0)["done"],
          True)

    # 2. An empty library fetches and files nothing.
    fake = FakeKSF({"surf_e": FLAT}, {("surf_e", 0): 5})
    K.fetch = fake
    empty = tempfile.mkdtemp(prefix="maps-", dir=HOME)
    rc = run_main(["--watch", "--cache", fresh_cache(), "--maps", empty, "--max", "5",
                   "--delay", "0", "--go"])
    check("an empty map library refuses, asking nothing", (rc, fake.asked), (2, []))

    # 3. The cap holds for every request, a torn map file included.
    fake = FakeKSF({"surf_t": FLAT}, {("surf_t", 0): 5})
    K.fetch = fake
    cache = fresh_cache()
    os.makedirs(os.path.join(cache, "maps"))
    io.open(os.path.join(cache, "maps", "surf_t.json"), "w").close()
    K.sweep_maps(["surf_t"], cache, -1, K.Pacer(0, 0))
    check("a zero budget asks nothing, even past a torn map file", fake.asked, [])
    try:
        K.Pacer(0, 0).get("/x")
        got = "asked"
    except K.OverBudget:
        got = "refused"
    check("...because Pacer.get itself refuses past its cap", got, "refused")

    # 4. A park is lifted by an answer, not by a tick that asked nothing.
    fake, cache, mapsdir, names = watch_setup(1, installed=1, prefix="surf_l")
    pf = os.path.join(cache, ".refused")
    io.open(pf, "w").write(json.dumps({"at": 1, "until": 1, "n": 4, "why": "HTTP 429"}))
    tick(cache, mapsdir, 0)
    check("an expired park survives a tick that asked nothing", os.path.exists(pf), True)
    tick(cache, mapsdir, 2)
    check("...and is lifted by one that was answered", os.path.exists(pf), False)

    # 5. One ksfimport at a time.
    cache = fresh_cache()
    first = K.take_lock(cache)
    second = K.take_lock(cache)
    check("a second run cannot take the lock", (first is not None, second), (True, None))
    first.close()
    third = K.take_lock(cache)
    check("...and can once the first lets go", third is not None, True)
    third.close()

    # 6. A board that always fails is set aside after STRIKES parks.
    fake, cache, mapsdir, names = watch_setup(2, installed=2, rows_each=5, prefix="surf_f")
    fake.fail.add(("surf_f00", 0, 0))
    for _ in range(K.STRIKES):
        io.open(os.path.join(cache, ".refused"), "w").write(json.dumps({"until": 0, "n": 0}))
        tick(cache, mapsdir, 20)
    doc = K.board_load(cache, "surf_f00", 0)
    check("a board refused STRIKES times is set aside", bool(doc.get("skip")), True)
    io.open(os.path.join(cache, ".refused"), "w").write(json.dumps({"until": 0, "n": 0}))
    fake.asked = []
    tick(cache, mapsdir, 20)
    check("...and the crawl goes on without it",
          (ksf_rows("map='surf_f01'"), [p for p in fake.asked if "surf_f00/records/zone/0/1?game=css&mode=0" in p]),
          (5, []))

    # 7. One bad field costs its row, not the tick.
    fake, cache, mapsdir, names = watch_setup(1, installed=1, rows_each=5, prefix="surf_b")

    def bad(rows):
        if rows:
            rows[0] = dict(rows[0], date="2026-10-05")
            rows[1] = dict(rows[1], time="31.5")
        return rows

    fake.mangle = bad
    rc = tick(cache, mapsdir, 3)
    check("a page with a text date and a text time still files the rest",
          (rc, ksf_rows("map='surf_b00' AND style='clean'")), (0, 4))

    # 8. A list that ignores its offset cannot spend every tick on itself.
    fake, cache, mapsdir, names = watch_setup(25, installed=25, prefix="surf_c")
    fake.stuck_list = True
    tick(cache, mapsdir, 6)
    check("the map list stops at a page with nothing new",
          [p for p in fake.asked if "/new?" in p],
          ["/api/maps/new?offset=0", "/api/maps/new?offset=10"])

    # 9. A page with no SteamID is a format change: refused, parked.
    fake, cache, mapsdir, names = watch_setup(1, installed=1, prefix="surf_g")
    fake.mangle = lambda rows: [dict(r, steamID=None, steamId=r["steamID"]) for r in rows]
    tick(cache, mapsdir, 3)
    park = json.load(io.open(os.path.join(cache, ".refused"), encoding="utf-8"))
    check("rows without a SteamID park the crawl", "SteamID" in park["why"], True)

    # 10. A refreshed first page that is short is the whole board.
    fake = FakeKSF({"surf_q": FLAT}, {("surf_q", 0): 30})
    K.fetch = fake
    cache = fresh_cache()
    K.sweep_maps(["surf_q"], cache, -1, K.Pacer(0, 5))
    fake.boards[("surf_q", 0)] = 12
    fake.top[("surf_q", 0)] = 1
    K.board_page(cache, "surf_q", 0, K.Pacer(0, 1), top=True)
    check("a short refreshed page 1 leaves the board done",
          K.board_load(cache, "surf_q", 0)["done"], True)


def case_board_reads_ksf_styles():
    c = S.app.test_client()
    db = sqlite3.connect(os.environ["SURFD_DB"])
    db.execute("INSERT OR REPLACE INTO runs (map, track, leg, tier, style, player, name,"
               " ticks, tickrate, millis, flags, node, runid, submitted, replay_id)"
               " VALUES ('surf_hsw', 0, 0, 'ksf', 'hsw', '76561197960265729', 'h',"
               " 100, 66.6667, 1500, 0, 'ksf', '', 1, 0)")
    db.execute("DELETE FROM mapwant WHERE map='surf_hsw'")
    db.commit()
    r = c.get("/api/board?map=surf_hsw&tier=ksf&style=hsw")
    body = json.loads(r.data)
    check("/api/board serves a Half-Sideways board", (r.status_code, len(body["rows"])), (200, 1))
    check("/api/board still refuses a style nobody files",
          c.get("/api/board?map=surf_hsw&tier=ksf&style=zz").status_code, 400)
    got = db.execute("SELECT asked FROM mapwant WHERE map='surf_hsw'").fetchone()
    check("a short imported page queues the map for the crawl", got, (1,))
    c.get("/api/board?map=surf_nothing_here&tier=ksf&style=hsw")
    got = db.execute("SELECT COUNT(*) FROM mapwant WHERE map='surf_nothing_here'").fetchone()
    check("...but a board we hold nothing for queues nothing", got, (0,))
    c.get("/api/board?map=surf_hsw&tier=ranked&style=hsw")
    got = db.execute("SELECT asked FROM mapwant WHERE map='surf_hsw'").fetchone()
    check("...and nor does the ranked board", got, (1,))
    r = c.get("/board/api/map?map=surf_hsw&tier=imported&style=hsw")
    check("the web board opens it too", (r.status_code, json.loads(r.data)["style"]),
          (200, "hsw"))
    db.close()

    # Another writer holds the lock (momwatch does, for seconds): the read that
    # queues a map must not wait the connection's 5 s for it.
    hold = sqlite3.connect(os.environ["SURFD_DB"], timeout=0.1)
    hold.execute("BEGIN IMMEDIATE")
    try:
        t0 = K.time.time()
        r = c.get("/api/board?map=surf_hsw&tier=ksf&style=hsw")
        took = K.time.time() - t0
    finally:
        hold.rollback()
        hold.close()
    check("with the write lock held elsewhere the read still answers, fast",
          (r.status_code, took < 1.0), (200, True))


def main():
    for case in (case_mapping, case_exact_name, case_paging_and_depth,
                 case_shallowest_first_and_cursor, case_linear_asks_no_stages,
                 case_write_and_filter, case_refusal, case_no_answer,
                 case_modes, case_merge_and_refresh, case_watch,
                 case_watch_refusal_parks, case_watch_dry_and_owed,
                 case_review_findings, case_board_reads_ksf_styles):
        print("\n%s:" % case.__name__)
        case()
    print("\n%d failed" % len(FAILED))
    for f in FAILED:
        print("  " + f)
    return 1 if FAILED else 0


if __name__ == "__main__":
    raise SystemExit(main())
