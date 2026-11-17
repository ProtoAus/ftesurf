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
        self.tiercode = {}      # name -> an HTTP status for its tier request

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
        if url.endswith("?expand=leaderboards") and url.startswith(W.MOM_API + "/maps/"):
            mid = int(url[len(W.MOM_API + "/maps/"):].split("?")[0])
            n = [k for k, v in self.ids.items() if v == mid][0]
            if n in self.tiercode:
                self.asked.append(url)
                raise T.http(url, self.tiercode[n])
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
    """Move one of mapnew's holds or waits (or, table None, its last KSF ask) `by` s into the past."""
    p = os.path.join(state, "mapnew.json")
    d = mine(state)
    if table is None:
        d[key] -= by
    elif key in d.get(table, {}):       # absent: nothing to age, and the checks say what is wrong
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
    check("mapwatch's state and hash cache are byte for byte as they were",
          snap(state, "state.json", "hash.json") == {k: before[k] for k in ("state.json", "hash.json")}, True)
    c0, c1 = json.loads(before["catalogue.json"]), json.load(io.open(os.path.join(state, "catalogue.json")))
    check("catalogue.json gains the two maps' entries and nothing else changes",
          (sorted(set(c1["maps"]) - set(c0["maps"])), {k: c1["maps"][k] for k in c0["maps"]} == c0["maps"],
           c1["at"] == c0["at"], set(c0["momnames"]) <= set(c1["momnames"])),
          (["surf_knew", "surf_new"], True, True, True))
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
    bkey = "surf_b:%s" % T.sha(w.mom["surf_b"]["bsp"])[:12]
    check("a 403 holds the CDN HOST_HOLD, and the file waits FILE_WAIT",
          (round((h["cdn"][0] - T.REAL_TIME()) / 60), mine(state)["files"].get(bkey, [0, 0])[1]),
          (N.HOST_HOLD // 60, 1))
    w.asked = []
    new(maps, state)
    check("held: the lists are read, the CDN is not asked", (len(w.files()), sum("/maps?" in u for u in w.asked)),
          (0, 3))
    age(state, "hosts", "cdn", N.HOST_HOLD + 1)
    age(state, "files", bkey, N.FILE_WAIT + 1)
    new(maps, state)
    check("a second refusal holds it twice as long", round((mine(state)["hosts"]["cdn"][0] - T.REAL_TIME()) / 60),
          2 * N.HOST_HOLD // 60)
    w.cdn.pop("surf_b")
    age(state, "hosts", "cdn", 10 * N.HOST_HOLD)
    age(state, "files", bkey, 10 * N.FILE_WAIT)
    new(maps, state)
    check("its next good answer installs; the hold is over but remembered until HOST_FORGET",
          (os.path.exists(os.path.join(maps, "surf_b.bsp")), mine(state)["hosts"]["cdn"][0] <= T.REAL_TIME()),
          (True, True))
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
    w.asked = []
    new(maps, state)
    check("its hold over, KSF still waits KSF_EVERY from the last ask",
          ([u for u in w.asked if u.startswith(W.KSF_BASE)], os.path.exists(os.path.join(maps, "surf_kq.bsp"))),
          ([], False))
    age(state, None, "ksf_at", N.KSF_EVERY + 1)
    new(maps, state)
    check("after both, KSF's new map comes in", os.path.exists(os.path.join(maps, "surf_kq.bsp")), True)
    w.ksf["surf_kz"] = T.Z("surf_kz", "kz")
    w.newest = ["surf_kz"]
    age(state, None, "ksf_at", N.KSF_EVERY - 600)
    w.asked = []
    new(maps, state)
    check("a good read too: KSF is not asked again within KSF_EVERY",
          [u for u in w.asked if u.startswith(W.KSF_BASE)], [])


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


def case_mapwatch_cannot_read():
    """Review 1: mapwatch's run without a list rebuilds rows from catalogue.json."""
    for down in ("mom", "ksf"):
        w, maps, state = setup({"surf_a": T.M("a")}, {"surf_ka": T.Z("surf_ka", "ka")})
        watch(maps, state)
        w.add("surf_new", T.M("new", tier=3))
        nat = T.M("nat", tier=2)
        nat["gamemode"] = 2
        w.add("ahop_nat", nat)
        w.ksf["surf_knew"] = T.Z("surf_knew", "kn")
        w.newest = ["surf_knew"]
        new(maps, state)
        rows = {n: row_of(state, n) for n in ("surf_new", "ahop_nat", "surf_knew")}
        w.down.add(down)
        watch(maps, state)
        check("%s unread at mapwatch's next run: mapnew's three rows stand as written" % down,
              ({n: row_of(state, n) for n in rows} == rows, all(len(v) == 1 for v in rows.values())), (True, True))


def case_port_row():
    """Review 2: a KSF port's row names the map it is a build of, as mapwatch's does."""
    w, maps, state = setup({"surf_x": T.M("x")}, {"surf_ka": T.Z("surf_ka", "ka")})
    watch(maps, state)
    w.ksf["surf_x_ksf"] = T.Z("surf_x_ksf", "xk")
    w.ksf["surf_x_ksf"]["tier"] = 5
    w.newest = ["surf_x_ksf"]
    base0 = row_of(state, "surf_x")
    new(maps, state)
    port = row_of(state, "surf_x_ksf")
    check("the port's row ends with its base map; the base's row is left as mapwatch wrote it",
          ([r.split()[-1] for r in port], row_of(state, "surf_x")), (["surf_x"], base0))
    watch(maps, state)
    check("...and mapwatch's next run writes the port's row the same", row_of(state, "surf_x_ksf"), port)


def case_owed_rows():
    """Review 3: a row not written in the installing run is written by a later one."""
    w, maps, state = setup({"surf_a": T.M("a")}, {})
    watch(maps, state)
    dl = os.path.join(state, "mapdl.txt")
    os.rename(dl, dl + ".away")
    w.add("surf_new", T.M("new"))
    try:
        new(maps, state)
    finally:
        os.rename(dl + ".away", dl)
    check("mapdl.txt unreadable: the map is installed and its row owed",
          (os.path.exists(os.path.join(maps, "surf_new.bsp")), sorted(mine(state)["owed"])), (True, ["surf_new"]))
    with open(dl, "a") as fh:
        fh.write("dl \n")
    check("the next run, with a nameless dl line in the list, runs", new(maps, state), 0)
    check("...writes the owed row and keeps the odd line",
          (len(row_of(state, "surf_new")), "dl " in dl_rows(state), mine(state)["owed"]), (1, True, {}))


def case_round2():
    """Review round 2: KSF's names need a fresh whole reading; tier-less entries stay out of
    the catalogue; an owed row yields to mapwatch's newer whole reading."""
    w, maps, state = setup({"surf_a": T.M("a")}, {"surf_ka": T.Z("surf_ka", "ka")})
    watch(maps, state)
    cp = os.path.join(state, "catalogue.json")
    doc = json.load(io.open(cp))
    doc["at"] -= N.CATALOGUE_FRESH + 60
    with open(cp, "w") as fh:
        json.dump(doc, fh)
    w.ksf["surf_kn"] = T.Z("surf_kn", "kn")
    w.newest = ["surf_kn"]
    new(maps, state)
    check("mapwatch's whole reading is old: KSF's new map waits",
          os.path.exists(os.path.join(maps, "surf_kn.bsp")), False)

    w, maps, state = setup({"surf_a": T.M("a")}, {"surf_ka": T.Z("surf_ka", "ka")})
    watch(maps, state)
    w.add("surf_t", T.M("t", tier=3))
    w.tiercode["surf_t"] = 404
    new(maps, state)
    cp = os.path.join(state, "catalogue.json")
    check("its tier unknown: the map is listed, its entry kept out of the catalogue",
          (len(row_of(state, "surf_t")), "surf_t" in json.load(io.open(cp))["maps"]), (1, False))
    w.down.add("ksf")
    watch(maps, state)
    check("...so mapwatch's next run (Momentum read, KSF not) gives its tier",
          [r.split()[4] for r in row_of(state, "surf_t")], ["3"])

    w, maps, state = setup({"surf_a": T.M("a")}, {"surf_ka": T.Z("surf_ka", "ka")})
    watch(maps, state)
    dl = os.path.join(state, "mapdl.txt")
    os.rename(dl, dl + ".away")
    w.add("surf_o", T.M("o", tier=3))
    try:
        new(maps, state)
    finally:
        os.rename(dl + ".away", dl)
    d = mine(state)
    d["owed"]["surf_o"]["at"] -= 10
    with open(os.path.join(state, "mapnew.json"), "w") as fh:
        json.dump(d, fh)
    w.mom["surf_o"]["tier"] = 6
    watch(maps, state)
    row = row_of(state, "surf_o")
    new(maps, state)
    check("owed, then mapwatch read both lists: its row (the new tier) stands and nothing is owed",
          (row_of(state, "surf_o"), [r.split()[4] for r in row], mine(state)["owed"]), (row, ["6"], {}))


def case_round2_hosts():
    """Review round 2, host safety."""
    w, maps, state = setup({"surf_a": T.M("a")}, {"surf_ka": T.Z("surf_ka", "ka")})
    watch(maps, state)
    w.add("surf_f", T.M("f"))
    fk = "surf_f:%s" % T.sha(w.mom["surf_f"]["bsp"])[:12]
    seen_then = []
    w.hook = lambda n: seen_then.append(mine(state).get("asking"))
    new(maps, state)
    w.hook = None
    check("the request in flight is saved before it is made", seen_then, [["cdn", fk]])
    d = mine(state)
    d["asking"] = ["cdn", "surf_g:abc"]
    with open(os.path.join(state, "mapnew.json"), "w") as fh:
        json.dump(d, fh)
    new(maps, state)
    m = mine(state)
    check("a run ended inside a request: that host held, that file waits, the record gone",
          ("cdn" in m["hosts"] and m["hosts"]["cdn"][0] > T.REAL_TIME(), m["files"].get("surf_g:abc", [0, 0])[1],
           "asking" in m), (True, 1, False))

    w, maps, state = setup({"surf_a": T.M("a")}, {"surf_ka": T.Z("surf_ka", "ka")})
    w.ksf["surf_kn"] = T.Z("surf_kn", "kn")
    w.newest = ["surf_kn"]
    os.makedirs(state)
    w.asked = []
    new(maps, state)
    check("no catalogue at all: KSF is not asked", [u for u in w.asked if u.startswith(W.KSF_BASE)], [])

    w, maps, state = setup({"surf_a": T.M("a")}, {"surf_ka": T.Z("surf_ka", "ka")})
    watch(maps, state)
    w.ksf["surf_kn"] = T.Z("surf_kn", "kn")
    w.newest = ["surf_kn"]
    w.kcode = 403
    N.main(["--maps", maps, "--state", state, "--delay", "0"])          # a dry run
    w.asked = []
    new(maps, state)
    check("a dry run's refusal is kept as it was: the run after it does not ask KSF",
          (mine(state)["hosts"].get("ksf", [0, 0, ""])[2], [u for u in w.asked if u.startswith(W.KSF_BASE)]),
          ("HTTP 403", []))

    w, maps, state = setup({"surf_a": T.M("a")}, {})
    watch(maps, state)
    got = []
    for n in ("surf_q1", "surf_q2"):
        w.add(n, T.M(n))
        w.tiercode[n] = 429
        new(maps, state)
        got.append(mine(state)["hosts"]["api"][1])
        age(state, "hosts", "api", N.HOST_HOLD_MAX)
    check("per-map refusals under good list reads: the API's hold still doubles", got, [1, 2])

    w, maps, state = setup({"surf_a": T.M("a")}, {})
    watch(maps, state)
    w.add("surf_e", T.M("e"))
    with open(os.path.join(state, "mapnew.json"), "w") as fh:
        fh.write('{"hosts": {"cdn": [Infinity, 1, "x"], "api": [%d, -5, "x"]}, "ksf_at": NaN}'
                 % (T.REAL_TIME() + 3600))
    check("hand-edited holds (infinite, negative): the run goes on", new(maps, state), 0)
    check("...and those entries are dropped, so the map comes in",
          os.path.exists(os.path.join(maps, "surf_e.bsp")), True)


def case_tier_refusals():
    """Review 4: a tier the API cannot give costs the install nothing else."""
    w, maps, state = setup({"surf_a": T.M("a")}, {})
    watch(maps, state)
    w.add("surf_t", T.M("t"))
    w.tiercode["surf_t"] = 404
    new(maps, state)
    check("a 404 for its tier: installed, zones written, the API not held",
          (os.path.exists(os.path.join(maps, "surf_t.bsp")),
           os.path.exists(os.path.join(T.zdir_of(maps), "surf_t.json")), "api" in mine(state)["hosts"]),
          (True, True, False))
    w.add("surf_u", T.M("u"))
    w.tiercode["surf_u"] = 503
    new(maps, state)
    check("a 503 for its tier: installed, the API held, so no zone request",
          (os.path.exists(os.path.join(maps, "surf_u.bsp")),
           os.path.exists(os.path.join(T.zdir_of(maps), "surf_u.json")), "api" in mine(state)["hosts"]),
          (True, False, True))


def case_ksf_rules():
    w, maps, state = setup({"surf_a": T.M("a")}, {"surf_ka": T.Z("surf_ka", "ka")})
    watch(maps, state)
    w.ksf["surf_kn"] = T.Z("surf_kn", "kn")
    w.newest = ["surf_kn"]
    w.down.add("mom")
    w.asked = []
    new(maps, state)
    check("review 5: Momentum unread, KSF is not asked", [u for u in w.asked if u.startswith(W.KSF_BASE)], [])
    w.down.discard("mom")
    age(state, "hosts", "api", 10 * N.HOST_HOLD)
    park = os.path.join(S.DATA_DIR, "ksf", ".refused")
    os.makedirs(os.path.dirname(park), exist_ok=True)
    for ago, want in ((3600, 0), (N.KSF_AFTER_PARK + 3600, 1)):
        with open(park, "w") as fh:
            json.dump({"until": T.REAL_TIME() - ago, "why": "HTTP 403"}, fh)
        w.asked = []
        try:
            new(maps, state)
        finally:
            os.remove(park)
        check("ksfimport's park over %d h ago: KSF's list asked %d time(s)" % (ago // 3600, want),
              sum(u.endswith(N.KSF_HEAD) for u in w.asked), want)
    check("...and its new map comes in", os.path.exists(os.path.join(maps, "surf_kn.bsp")), True)


def case_ksf_archive_refused():
    """Review B1: an archive refusal holds KSF's archives; a good list does not lift it."""
    w, maps, state = setup({"surf_a": T.M("a")}, {"surf_ka": T.Z("surf_ka", "ka")})
    watch(maps, state)
    w.ksf["surf_kb"] = {"tier": 1, "zip": 403}
    w.newest = ["surf_kb"]
    key = "surf_kb:ksf"
    held = []
    for _ in range(2):
        new(maps, state)
        h = mine(state)["hosts"]
        held.append((h.get("ksfdl", [0, 0])[1], "ksf" in h))
        age(state, "hosts", "ksfdl", 10 * N.HOST_HOLD)
        age(state, "files", key, 10 * N.FILE_WAIT)
        age(state, None, "ksf_at", N.KSF_EVERY + 1)
    check("two archive 403s under good lists: the archive hold doubles, the list is not held",
          held, [(1, False), (2, False)])


def case_cdn_refusal_others_go():
    """Review B2: one file the CDN refuses does not block the maps after it."""
    w, maps, state = setup({"surf_a": T.M("a")}, {})
    watch(maps, state)
    w.add("surf_b", T.M("b"))
    w.cdn["surf_b"] = 403
    w.add("surf_c", T.M("c"))
    new(maps, state)
    age(state, "hosts", "cdn", N.HOST_HOLD + 1)
    w.asked = []
    new(maps, state)
    check("past the CDN's hold the next map is taken; the refused one waits",
          (os.path.exists(os.path.join(maps, "surf_c.bsp")), len(w.asked_for("surf_b"))), (True, 0))


def case_ksf_bytes():
    """Review B3: a KSF archive that fails its checks still counts its bytes."""
    w, maps, state = setup({"surf_a": T.M("a")}, {"surf_ka": T.Z("surf_ka", "ka")})
    watch(maps, state)
    for n in ("surf_w1", "surf_w2", "surf_w3"):
        w.ksf[n] = T.Z("surf_other", n)          # one .bsp, named for another map
    w.newest = ["surf_w1", "surf_w2", "surf_w3"]
    w.asked = []
    new(maps, state, "--max-gb", "0.000000001")
    check("archives with the wrong member, a tiny byte budget: one fetched", len(w.files()), 1)


def case_publish_raises():
    """Review B4: a failure after the download puts the file on a wait, and is saved."""
    w, maps, state = setup({"surf_a": T.M("a")}, {})
    watch(maps, state)
    w.add("surf_p", T.M("p"))
    real = W.publish

    def busy(*_a, **_k):
        raise ValueError("content lease busy")
    W.publish = busy
    try:
        new(maps, state)
    finally:
        W.publish = real
    key = "surf_p:%s" % T.sha(w.mom["surf_p"]["bsp"])[:12]
    check("it waits, nothing is left behind, and mapnew.json says so",
          (mine(state)["files"].get(key, [0, 0])[1], [f for f in os.listdir(maps) if "surf_p" in f]), (1, []))
    w.asked = []
    new(maps, state)
    check("...and is not downloaded again next run", w.asked_for("surf_p"), [])


def case_mapwatch_hosts():
    """Main's mapwatch keeps host holds in state.json: honoured where they exist."""
    w, maps, state = setup({"surf_a": T.M("a")}, {})
    watch(maps, state)
    st = T.state_of(state)
    st["hosts"] = {"cdn": [int(T.REAL_TIME()) + 3600, 21600, "HTTP 429"]}
    with open(os.path.join(state, "state.json"), "w") as fh:
        json.dump(st, fh)
    w.add("surf_h", T.M("h"))
    w.asked = []
    new(maps, state)
    check("mapwatch holds the CDN: the lists are read, no file is asked",
          (sum("/maps?" in u for u in w.asked), w.files()), (3, []))


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
                 case_zones_looks, case_mapwatch_cannot_read, case_port_row, case_owed_rows, case_round2,
                 case_round2_hosts,
                 case_tier_refusals, case_ksf_rules, case_ksf_archive_refused, case_cdn_refusal_others_go,
                 case_ksf_bytes, case_publish_raises, case_mapwatch_hosts, case_lock_and_budget):
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
