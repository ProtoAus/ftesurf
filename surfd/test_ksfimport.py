#!/usr/bin/env python3
"""
test_ksfimport.py -- the falsifier for ksfimport.py's map-seeded path.

    python surfd/test_ksfimport.py

No network: `fetch` is replaced by a fake KSF that serves canned pages and
records every path asked, so a case can say what was REQUESTED as well as what
was written.  surfd is imported against a throwaway home.
"""

import argparse
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

STAGED = {"isLinear": False, "cp_count": 2, "b_count": 1}
LINEAR = {"isLinear": True, "cp_count": 4, "b_count": 0}


class FakeKSF(object):
    """Search rows by prefix (a typeahead, like theirs) and boards by size."""

    def __init__(self, maps, boards, refuse_after=None, slow=0.0):
        self.maps, self.boards = maps, boards
        self.refuse_after, self.slow = refuse_after, slow
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
        m = re.match(r"/api/maps/([^/]+)/records/zone/(\d+)/(\d+)\?game=css&mode=0$",
                     path)
        mp, zone, start = urllib.parse.unquote(m.group(1)), int(m.group(2)), int(m.group(3))
        total = self.boards.get((mp, zone), 0)
        rows = [{"rank": r, "name": "p%d" % r, "steamID": "STEAM_0:1:%d" % r,
                 "time": 30.0 + zone + r * 0.01 + self.slow, "date": 1790000000 + r}
                for r in range(start, min(total, start + K.KSF_PAGE - 1) + 1)]
        return json.dumps(rows)


def pages(fake):
    """Board requests as (map, zone, startRank), in the order asked."""
    out = []
    for p in fake.asked:
        m = re.match(r"/api/maps/([^/]+)/records/zone/(\d+)/(\d+)", p)
        if m:
            out.append((m.group(1), int(m.group(2)), int(m.group(3))))
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
                   "--maps", mapsdir, "--go"])
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
              "--maps", mapsdir, "--go"])
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
    rows = K.maps_mode(write_args(listfile, cache, mapsdir), {"surf_r"}, cache)
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


def main():
    for case in (case_mapping, case_exact_name, case_paging_and_depth,
                 case_shallowest_first_and_cursor, case_linear_asks_no_stages,
                 case_write_and_filter, case_refusal):
        print("\n%s:" % case.__name__)
        case()
    print("\n%d failed" % len(FAILED))
    for f in FAILED:
        print("  " + f)
    return 1 if FAILED else 0


if __name__ == "__main__":
    raise SystemExit(main())
