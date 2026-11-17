#!/usr/bin/env python3
"""
test_mapnew.py -- the falsifier for mapnew.py (P1601).

    python surfd/test_mapnew.py

test_mapwatch.py's fake Momentum API, CDN and ksf.surf (no network), its
throwaway surfd home, and the real mapwatch run before and after mapnew: what
mapnew installs must be what mapwatch would have, and mapwatch's state must be
untouched by it.
"""

import hashlib
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import test_mapwatch as T   # noqa: E402  (sets up the throwaway home first)
import mapnew as N          # noqa: E402

W, S, check = T.W, T.S, T.check


class World(T.World):
    """test_mapwatch's world, plus KSF's newest-maps list (`newest`, newest first)."""

    def __init__(self, mom, ksf):
        T.World.__init__(self, mom, ksf)
        self.newest = None
        self.kcode = None       # an HTTP status for the newest-maps list

    def add(self, name, m):
        self.mom[name] = m
        self.ids[name] = 500 + len(self.ids)

    def __call__(self, url):
        if url.startswith(W.MOM_API + "/maps?") and "leaderboards" not in url:
            r = T.World.__call__(self, url)     # as their API: no expand, no leaderboards
            d = json.loads(r.b.getvalue())
            for m in d["data"]:
                m.pop("leaderboards", None)
            return T.Resp(json.dumps(d).encode())
        if url == W.KSF_BASE + N.KSF_HEAD:
            self.asked.append(url)
            if self.kcode:
                raise T.http(url, self.kcode)
            names = self.newest if self.newest is not None else sorted(self.ksf)
            return T.Resp(json.dumps([{"mapID": i, "name": n, "tier": self.ksf[n]["tier"]}
                                      for i, n in enumerate(names)]).encode())
        return T.World.__call__(self, url)


def setup(mom, ksf, held=()):
    _w, maps, state = T.setup(mom, ksf, held)
    w = World(mom, ksf)
    W.opener = w
    return w, maps, state


def watch(maps, state):
    return T.tick(maps, state, "--go", "--updates")


def new(maps, state, *extra):
    return N.main(["--maps", maps, "--state", state, "--delay", "0", "--go"] + list(extra))


def snap(state, *names):
    out = {}
    for n in names:
        try:
            out[n] = T.read(os.path.join(state, n))
        except OSError:
            out[n] = None
    return out


def mine(state):
    return json.load(io.open(os.path.join(state, "mapnew.json"), encoding="utf-8"))


def age(state, table, key, by):
    """Move one of mapnew's holds or waits `by` seconds into the past."""
    p = os.path.join(state, "mapnew.json")
    d = mine(state)
    d[table][key][0] -= by
    with open(p, "w") as fh:
        json.dump(d, fh)


def dl_rows(state):
    with io.open(os.path.join(state, "mapdl.txt"), encoding="utf-8") as fh:
        return fh.read().splitlines()


def row_of(state, name):
    return [ln for ln in dl_rows(state) if ln.startswith("dl %s " % name)]


def case_installs_as_mapwatch():
    w, maps, state = setup({"surf_old": T.M("old"), "bhop_old": T.M("bo")},
                           {"surf_kold": T.Z("surf_kold", "ko")})
    watch(maps, state)
    before = snap(state, "state.json", "catalogue.json", "hash.json")
    rows0 = dl_rows(state)
    w.add("surf_new", T.M("new", tier=3))
    w.ksf["surf_knew"] = T.Z("surf_knew", "kn")
    w.ksf["surf_knew"]["tier"] = 4
    w.newest = ["surf_knew", "surf_kold"]
    w.asked = []
    check("mapnew runs", new(maps, state), 0)
    check("both new maps are in the library, as the lists publish them",
          (T.read(os.path.join(maps, "surf_new.bsp")) == w.mom["surf_new"]["bsp"],
           T.read(os.path.join(maps, "surf_knew.bsp")) == T.bsp("kn")), (True, True))
    zf = os.path.join(T.zdir_of(maps), "surf_new.json")
    check("the Momentum map's zones are written, the bytes that hash to zoneHash",
          T.sha(T.read(zf)) == T.sha(T.ztext(w.mom["surf_new"]["zones"]).encode()), True)
    check("requests: three list heads, KSF's head, the new map's tier, one file each, one zone reply",
          (sum("/maps?" in u for u in w.asked), sum(N.KSF_HEAD in u for u in w.asked),
           sum(u.endswith("?expand=leaderboards") for u in w.asked), len(w.files()), len(w.zone_asks())),
          (3, 1, 1, 2, 1))
    check("mapwatch's state, catalogue and hash cache are byte for byte as they were",
          snap(state, "state.json", "catalogue.json", "hash.json") == before, True)
    rows1 = dl_rows(state)
    check("mapdl.txt: every line mapwatch wrote is kept, and two rows are added",
          ([ln for ln in rows1 if ln in rows0] == rows0, len(rows1) - len(rows0)), (True, 2))
    mrow, krow = row_of(state, "surf_new"), row_of(state, "surf_knew")
    check("the rows name the map's mode, source and tier",
          ([r.split()[2:5] for r in mrow], [r.split()[2:5] for r in krow]),
          ([["surf", "m", "3"]], [["surf", "k", "4"]]))
    check("rows stay in list_rows' order", [ln for ln in rows1 if ln.startswith("dl ")],
          sorted([ln for ln in rows1 if ln.startswith("dl ")], key=lambda ln: ln.split()[1].lower()))
    w.asked = []
    zbytes = T.read(zf)
    watch(maps, state)
    check("mapwatch's next run fetches neither again and strikes nothing",
          (len(w.files()), T.strikes(state)), (0, []))
    check("...and writes the same rows for them", (row_of(state, "surf_new"), row_of(state, "surf_knew")),
          (mrow, krow))
    check("...and leaves the zone file as mapnew wrote it", T.read(zf) == zbytes, True)


def case_left_alone():
    w, maps, state = setup({"surf_a": T.M("a")}, {"surf_ka": T.Z("surf_ka", "ka")})
    watch(maps, state)
    st = T.state_of(state)
    w.add("surf_struck", T.M("st"))
    key = "surf_struck:%s" % T.sha(w.mom["surf_struck"]["bsp"])[:12]
    st["later"][key] = [1, int(T.REAL_TIME()), "badhash"]
    with open(os.path.join(state, "state.json"), "w") as fh:
        json.dump(st, fh)
    w.ksf["surf_a"] = T.Z("surf_a", "kdup")            # Momentum's name: its build is Momentum's
    w.ksf["surf_beta"] = T.Z("surf_beta", "kb")        # a Beta line holds it
    with open(os.path.join(state, "extra.tsv"), "w") as fh:
        fh.write("surf_beta %s %s%s.bsp\n" % ("ab" * 20, W.MOM_CDN, T.uuid_of("surf_beta")))
    w.newest = ["surf_a", "surf_beta", "surf_ka"]
    w.asked = []
    new(maps, state)
    check("a file mapwatch struck, a held name, Momentum's name and a Beta line: none fetched",
          w.files(), [])
    check("...and mapnew keeps no wait for any of them", mine(state)["files"], {})


def case_files_wait():
    w, maps, state = setup({"surf_a": T.M("a")}, {})
    watch(maps, state)
    before = snap(state, "state.json")
    w.add("surf_bad", T.M("bad"))
    w.cdn["surf_bad"] = T.bsp("other")                  # the wrong hash
    w.add("surf_page", T.M("page"))
    w.cdn["surf_page"] = b"<html>blocked</html>" * 300  # a 200 that is not the file
    w.add("surf_gone", T.M("gone"))
    w.cdn["surf_gone"] = 404
    w.asked = []
    new(maps, state)
    f = mine(state)["files"]
    keys = {n: "%s:%s" % (n, T.sha(w.mom[n]["bsp"])[:12]) for n in ("surf_bad", "surf_page", "surf_gone")}
    check("a wrong hash and a 404 each wait FILE_WAIT; nothing is struck in mapwatch's state",
          ([f.get(keys[n], [0, 0])[1] for n in ("surf_bad", "surf_gone")],
           snap(state, "state.json") == before), ([1, 1], True))
    check("a 200 that is not the file waits too, and holds no host (it ends the CDN for the run)",
          (f.get(keys["surf_page"], [0, 0])[1], mine(state)["hosts"]), (1, {}))
    w.asked = []
    new(maps, state)
    check("the next run asks none of them", w.files(), [])
    age(state, "files", keys["surf_bad"], N.FILE_WAIT + 1)
    new(maps, state)
    f = mine(state)["files"][keys["surf_bad"]]
    check("past its wait it is asked again; a second failure waits twice as long",
          (len(w.asked_for("surf_bad")), f[1], round((f[0] - T.REAL_TIME()) / 3600)),
          (1, 2, 2 * N.FILE_WAIT // 3600))
    w.cdn.pop("surf_bad")
    age(state, "files", keys["surf_bad"], 3 * N.FILE_WAIT)
    new(maps, state)
    check("once it comes right it is installed and its wait forgotten",
          (os.path.exists(os.path.join(maps, "surf_bad.bsp")), keys["surf_bad"] in mine(state)["files"]),
          (True, False))


def case_hosts_held():
    w, maps, state = setup({"surf_a": T.M("a")}, {})
    watch(maps, state)
    w.add("surf_b", T.M("b"))
    w.cdn["surf_b"] = 403
    w.asked = []
    new(maps, state)
    h = mine(state)["hosts"]
    check("a 403 holds the CDN HOST_HOLD and puts no wait on the file",
          (round((h["cdn"][0] - T.REAL_TIME()) / 60), mine(state)["files"]), (N.HOST_HOLD // 60, {}))
    w.asked = []
    new(maps, state)
    check("held: the lists are read, the CDN is not asked", (len(w.files()), sum("/maps?" in u for u in w.asked)),
          (0, 3))
    age(state, "hosts", "cdn", N.HOST_HOLD + 1)
    new(maps, state)
    check("a second refusal holds it twice as long", round((mine(state)["hosts"]["cdn"][0] - T.REAL_TIME()) / 60),
          2 * N.HOST_HOLD // 60)
    w.cdn.pop("surf_b")
    age(state, "hosts", "cdn", 10 * N.HOST_HOLD)
    new(maps, state)
    check("its next good answer installs and clears the hold",
          (os.path.exists(os.path.join(maps, "surf_b.bsp")), "cdn" in mine(state)["hosts"]), (True, False))
    w.down.add("mom")
    w.asked = []
    new(maps, state)
    check("a list that answers 500 holds the API", "api" in mine(state)["hosts"], True)
    w.asked = []
    new(maps, state)
    check("held: Momentum is not asked at all", [u for u in w.asked if u.startswith(W.MOM_API)], [])


def case_ksf():
    w, maps, state = setup({"surf_a": T.M("a")}, {"surf_ka": T.Z("surf_ka", "ka")})
    fresh = os.path.join(os.path.dirname(state), "state2")
    w.ksf["surf_kn"] = T.Z("surf_kn", "kn")
    w.newest = ["surf_kn"]
    new(maps, fresh)
    check("no catalogue of Momentum's names: KSF's new map waits",
          os.path.exists(os.path.join(maps, "surf_kn.bsp")), False)
    watch(maps, state)                                   # installs surf_kn itself
    w.ksf["surf_kq"] = T.Z("surf_kq", "kq")
    w.newest = ["surf_kq"]
    park = os.path.join(S.DATA_DIR, "ksf", ".refused")
    os.makedirs(os.path.dirname(park), exist_ok=True)
    with open(park, "w") as fh:
        json.dump({"until": T.REAL_TIME() + 3600, "why": "HTTP 403"}, fh)
    w.asked = []
    try:
        new(maps, state)
    finally:
        os.remove(park)
    check("while ksfimport is parked, ksf.surf is not asked at all",
          [u for u in w.asked if u.startswith(W.KSF_BASE)], [])
    w.kcode = 403
    new(maps, state)
    check("a 403 on the newest list holds KSF", "ksf" in mine(state)["hosts"], True)
    w.kcode = None
    age(state, "hosts", "ksf", 10 * N.HOST_HOLD)
    new(maps, state)
    check("after the hold KSF's new map comes in", os.path.exists(os.path.join(maps, "surf_kq.bsp")), True)


def case_zones_looks():
    w, maps, state = setup({"surf_a": T.M("a")}, {})
    watch(maps, state)
    w.add("surf_inplay", T.M("ip"))
    T.lobby("p1", "surf_inplay")
    w.add("surf_unhashed", T.M("uh"))
    w.zonefix["surf_unhashed"] = T.TZ.zones(end=(1700, 0)).decode()    # zone-shaped, another hash
    w.asked = []
    new(maps, state)
    zd = T.zdir_of(maps)
    check("both maps install", sorted(n for n in os.listdir(maps) if n.endswith(".bsp")),
          ["surf_a.bsp", "surf_inplay.bsp", "surf_unhashed.bsp"])
    check("a lobby on the map: its zones are not even asked for; unhashed zones are not written",
          (len([u for u in w.zone_asks() if str(w.ids["surf_inplay"]) in u]),
           sorted(os.listdir(zd)) if os.path.isdir(zd) else []), (0, ["surf_a.json"]))
    zk = "z:surf_unhashed:%s" % T.sha(T.ztext(w.mom["surf_unhashed"]["zones"]).encode())[:12]
    check("...they wait as mapnew's (mapwatch's to judge), never struck",
          (mine(state)["files"].get(zk, [0, 0, ""])[2], T.strikes(state)),
          ("zones without their hash: mapwatch's", []))


def case_lock_and_budget():
    w, maps, state = setup({"surf_a": T.M("a")}, {})
    watch(maps, state)
    w.add("surf_b", T.M("b"))
    w.add("surf_c", T.M("c"))
    had = set(os.listdir(state))
    lock = W.take_lock(state)
    w.asked = []
    try:
        new(maps, state)
    finally:
        lock.close()
    check("mapwatch's lock held: nothing is asked", w.asked, [])
    new(maps, state, "--max", "1")
    check("--max 1: one of two", sum(os.path.exists(os.path.join(maps, n + ".bsp")) for n in ("surf_b", "surf_c")), 1)
    old, N.RUN_SECONDS = N.RUN_SECONDS, -1
    w.asked = []
    try:
        new(maps, state)
    finally:
        N.RUN_SECONDS = old
    check("past RUN_SECONDS nothing is started", w.files(), [])
    check("mapnew adds nothing to the state folder but mapnew.json",
          sorted(set(os.listdir(state)) - had - {"tmp", ".lock"}), ["mapnew.json"])


def main():
    for case in (case_installs_as_mapwatch, case_left_alone, case_files_wait, case_hosts_held, case_ksf,
                 case_zones_looks, case_lock_and_budget):
        print("\n%s:" % case.__name__)
        case()
    print()
    check("no url was asked that the lists did not give", T.UNEXPECTED, [])
    check("no reply was read without a size", T.UNBOUNDED, [])
    print("\n%d failed" % len(T.FAILED))
    for f in T.FAILED:
        print("  " + f)
    return 1 if T.FAILED else 0


if __name__ == "__main__":
    raise SystemExit(main())
