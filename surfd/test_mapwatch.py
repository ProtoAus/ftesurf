#!/usr/bin/env python3
"""
test_mapwatch.py -- the falsifier for mapwatch.py (and tools/mapscan.py's
reading of its catalogue).

    python surfd/test_mapwatch.py

No network: `opener` is replaced by a fake Momentum API, CDN and ksf.surf that
record every URL asked.  surfd is imported against a throwaway home, removed at
exit, and every case gets its own library directory.  File modes are graded on
Linux only (the Pi's run of this suite); Windows says so instead of passing.
"""

import atexit
import hashlib
import io
import json
import logging
import os
import shutil
import signal
import stat
import struct
import sys
import tempfile
import time
import urllib.error
import zipfile

FAILED = []
SKIPPED = []
UNBOUNDED = []          # replies read with no size: there must be none
UNEXPECTED = []         # urls the fake has no answer for: there must be none.  The
                        # tool survives whatever a reply raises, so a wrong url no
                        # longer shows as a crash -- it shows here.
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)


def check(label, got, want):
    ok = got == want
    print("%-4s %-66s %r" % ("ok" if ok else "FAIL", label, got))
    if not ok:
        FAILED.append("%s: got %r, want %r" % (label, got, want))


HOME = tempfile.mkdtemp(prefix="surfd-mapwatch-")
os.environ.update(SURFD_HOME=HOME, SURFD_DB=os.path.join(HOME, "test.db"),
                  SURFD_RUNS=os.path.join(HOME, "game", "data", "runs"))
import contextlib        # noqa: E402
import surfd as S        # noqa: E402
import mapwatch as W     # noqa: E402
import test_zonefit as TZ   # noqa: E402  (vbsp, zones: files of the real shape)


@atexit.register
def _cleanup():
    logging.shutdown()      # the logger holds a file in HOME on Windows
    shutil.rmtree(HOME, ignore_errors=True)


W.MOM_TAKE = 2           # so the list pages
W.KSF_MIN = 1
W.MOM_MIN = 0            # the fixture worlds are a handful of maps
W.GET_DELAY = 0.0
W.FLOOR_GB = 0           # this box's free space is not under test (the Pi's /tmp has 4 GB)
W.KSF_LOCK = os.path.join(HOME, "ksfwatch.lock")    # not the live crawl's
os.makedirs(os.path.dirname(S.RUNS_DIR))    # the game's data folder: without one, played() cannot tell
REAL_CONNECT = S.connect
REAL_TIME = time.time
REAL_SLEEP = time.sleep


def bsp(seed, n=4096):
    return b"VBSP" + (hashlib.sha256(seed.encode()).digest() * (n // 32 + 1))[:n - 4]


def sha(b):
    return hashlib.sha1(b).hexdigest()


def zones_of(seed):
    return {"dataTimestamp": 1789555292148, "formatVersion": 1,
            "tracks": {"main": {"zones": {"segments": [{"points": [[-15807.90234375, 13935.25], [12, -3]],
                                                        "name": seed}]}}},
            "globalRegions": []}


def ztext(z):
    return json.dumps(z, separators=(",", ":"))


def uuid_of(name):
    h = hashlib.md5(name.encode()).hexdigest()
    return "%s-%s-%s-%s-%s" % (h[:8], h[8:12], h[12:16], h[16:20], h[20:32])


def kzip(members, method=zipfile.ZIP_DEFLATED):
    b = io.BytesIO()
    with zipfile.ZipFile(b, "w", method) as z:
        for n, data in members:
            z.writestr(n, data)
    return b.getvalue()


def zip64ify(data):
    """The same archive with a zip64 end record and locator in front of its
    end record: zipfile then takes its counts from those."""
    at = data.rfind(b"PK\x05\x06")
    here, total, cdsize, cdoff = struct.unpack("<HHLL", data[at + 8:at + 20])
    z64 = struct.pack("<4sQHHLLQQQQ", b"PK\x06\x06", 44, 45, 45, 0, 0, here, total, cdsize, cdoff)
    loc = struct.pack("<4sLQL", b"PK\x06\x07", 0, at, 1)
    return data[:at] + z64 + loc + data[at:]


class Resp(object):
    def __init__(self, body, length=None, drip=0):
        self.status = 200
        self.b = io.BytesIO(body)
        self.drip = drip
        self.headers = {"Content-Length": str(len(body) if length is None else length)}

    def read1(self, n=-1):
        if n is None or n < 0:
            UNBOUNDED.append("read1")
        return self.b.read(min(self.drip or n, 1 << 16))    # a receive is not a megabyte

    def read(self, n=-1):
        # What a real socket does for read(n): everything asked for, however
        # slowly it comes.  With no n it is also a reply read with no cap.
        if n is None or n < 0:
            UNBOUNDED.append("read")
        return self.b.read(n)

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def http(url, code):
    return urllib.error.HTTPError(url, code, "x", {}, None)


class World(object):
    """Momentum's list and CDN and ksf.surf, from two dicts.
    mom[name]  = {"bsp": bytes, "zones": dict or None, "tier": n}
    ksf[name]  = {"tier": n, "zip": bytes, an HTTP status, or None for no archive}"""

    def __init__(self, mom, ksf):
        self.mom, self.ksf = mom, ksf
        self.ids = {n: 100 + i for i, n in enumerate(sorted(mom))}
        self.asked = []
        self.cdn = {}           # name -> bytes served instead, or an HTTP status
        self.lie = {}           # name -> a Content-Length that is not the body's
        self.drip = {}          # name -> bytes a read1 of its file gives
        self.zonefix = {}       # name -> the text served as its zones instead
        self.zonecode = {}      # name -> an HTTP status for its zone request
        self.nozones = set()    # names whose zone reply carries no zones at all
        self.down = set()       # "mom" / "ksf": that list answers 500
        self.hidden = set()     # on the CDN, not in the public list (a Beta map)
        self.rawrows = []       # rows added to the surf list as they are
        self.short = False      # the surf list ends on an empty page, early
        self.stuck = False      # the surf list ignores `skip`
        self.hook = None        # f(name), called as a CDN file is asked for
        self.zhook = None       # f(name), called as its zones are asked for
        self.khook = None       # f(url), called at every request to ksf.surf

    def row(self, n):
        m = self.mom[n]
        cv = {"bspHash": m.get("hash") or sha(m["bsp"]),
              "downloadURL": m.get("url") or W.MOM_CDN + uuid_of(n) + ".bsp",
              "zoneHash": sha(ztext(m["zones"]).encode()) if m.get("zones") else None}
        lb = [{"gamemode": 1 if n.startswith("surf_") else 2, "trackType": 0,
               "trackNum": 1, "style": 0, "tier": m.get("tier"), "type": 0}]
        return {"id": self.ids[n], "name": n, "status": 0, "currentVersion": cv,
                "leaderboards": m.get("leaderboards", lb)}

    def __call__(self, url):
        self.asked.append(url)
        if url.startswith(W.MOM_API + "/maps?"):
            if "mom" in self.down:
                raise http(url, 500)
            q = dict(kv.split("=") for kv in url.split("?", 1)[1].split("&"))
            surf = q["gamemode"] == "1"
            rows = [self.row(n) for n in sorted(self.mom) if n not in self.hidden
                    and n.startswith("surf_") == surf]
            if surf:
                rows += self.rawrows
            skip, take = int(q["skip"]), int(q["take"])
            if self.stuck and surf:
                skip = 0
            if self.short and surf and skip:
                return Resp(json.dumps({"totalCount": len(rows) + 5, "data": []}).encode())
            return Resp(json.dumps({"totalCount": len(rows) + (5 if self.short and surf else 0),
                                    "data": rows[skip:skip + take]}).encode())
        if url.startswith(W.MOM_API + "/maps/"):
            mid = int(url[len(W.MOM_API + "/maps/"):].split("?")[0])
            n = [k for k, v in self.ids.items() if v == mid][0]
            if self.zhook:
                self.zhook(n)
            if n in self.zonecode:
                raise http(url, self.zonecode[n])
            doc = json.dumps(self.row(n), separators=(",", ":"))
            if n in self.nozones:
                return Resp(doc.encode())
            zt = self.zonefix.get(n) or ztext(self.mom[n]["zones"])
            # as their API writes it: zones inside currentVersion, compact
            doc = doc.replace('"zoneHash":', '"zones":%s,"zoneHash":' % zt, 1)
            return Resp(doc.encode())
        if url.startswith(W.MOM_CDN):
            known = [k for k in self.mom if url == W.MOM_CDN + uuid_of(k) + ".bsp"]
            if not known:
                UNEXPECTED.append(url)
                raise AssertionError("unexpected url " + repr(url))
            n = known[0]
            if self.hook:
                self.hook(n)
            body = self.cdn.get(n, self.mom[n]["bsp"])
            if isinstance(body, int):
                raise http(url, body)
            return Resp(body, self.lie.get(n), self.drip.get(n, 0))
        if url.startswith(W.KSF_BASE) and self.khook:
            self.khook(url)
        if url == W.KSF_BASE + "/maps":
            if "ksf" in self.down:
                raise http(url, 500)
            objs = [{"mapID": i, "name": n, "tier": k["tier"],
                     "link": "/files/%s.zip" % n if k.get("zip") is not None else None}
                    for i, (n, k) in enumerate(sorted(self.ksf.items()))]
            payload = "5:" + json.dumps({"maps": objs}, separators=(",", ":"))
            return Resp(("<html><script>self.__next_f.push([1,%s])</script></html>"
                         % json.dumps(payload)).encode())
        if url.startswith(W.KSF_BASE + "/files/"):
            n = url[len(W.KSF_BASE + "/files/"):-4]
            body = self.ksf[n]["zip"]
            if isinstance(body, int):
                raise http(url, body)
            return Resp(body)
        UNEXPECTED.append(url)
        raise AssertionError("unexpected url " + repr(url))

    def files(self):
        return [u for u in self.asked if u.startswith(W.MOM_CDN) or "/files/" in u]

    def asked_for(self, name):
        return [u for u in self.files() if uuid_of(name) in u or u.endswith("/%s.zip" % name)]

    def zone_asks(self):
        return [u for u in self.asked if "WithZones" in u]


def setup(mom, ksf, held=()):
    """-> (world, maps dir, state dir).  `held` is (filename stem, bytes)."""
    w = World(mom, ksf)
    W.opener = w
    sql("DELETE FROM lobbies")
    lobby("p0", "surf_elsewhere")
    d = tempfile.mkdtemp(prefix="lib-", dir=HOME)
    maps, state = os.path.join(d, "maps"), os.path.join(d, "state")
    os.makedirs(maps)
    for stem, data in held:
        with open(os.path.join(maps, stem + ".bsp"), "wb") as fh:
            fh.write(data)
    return w, maps, state


def tick(maps, state, *extra):
    old = sys.argv
    sys.argv = ["mapwatch.py", "--maps", maps, "--state", state, "--delay", "0"] + list(extra)
    try:
        return W.main()
    finally:
        sys.argv = old


def lib(maps):
    return sorted(os.listdir(maps))


def read(p):
    with open(p, "rb") as fh:
        return fh.read()


def state_of(state):
    return json.load(io.open(os.path.join(state, "state.json"), encoding="utf-8"))


def strikes(state):
    """[(what, map, count, the reason's first word)] of everything struck."""
    out = []
    for k, v in state_of(state)["later"].items():
        f = k.split(":")
        out.append(("zones" if f[0] == "z" else "variant" if f[0] == "v" else "map",
                    f[1] if f[0] in ("z", "v") else f[0], v[0], v[2].split()[0]))
    return sorted(out)


def sql(q, args=()):
    conn = REAL_CONNECT()
    try:
        conn.execute(q, args)
        conn.commit()
    finally:
        conn.close()


def lobby(node, mp, ago=0):
    sql("INSERT OR REPLACE INTO lobbies (node, map, players, maxplayers, addr, name, last_seen)"
        " VALUES (?, ?, 0, 32, ?, 'n', ?)", (node, mp, "x:" + node, int(REAL_TIME()) - ago))


def M(seed, zones=True, tier=1):
    return {"bsp": bsp(seed), "zones": zones_of(seed) if zones else None, "tier": tier}


def Z(name, seed):
    return {"tier": 1, "zip": kzip([(name + ".bsp", bsp(seed))])}


def zdir_of(maps):
    return os.path.join(maps, "zones", "online")


def zlist(maps):
    try:
        return sorted(os.listdir(zdir_of(maps)))
    except OSError:
        return []


MOM = {"surf_a": M("a", tier=2), "surf_b": M("b", tier=5), "surf_c": M("c", zones=False),
       "bhop_d": M("d", tier=3)}
KSF = {"surf_k": dict(Z("surf_k", "k"), tier=4), "surf_a": Z("surf_a", "ksf-a")}


def case_plan_and_install():
    w, maps, state = setup(MOM, KSF)
    io.open(os.path.join(maps, ".mapwatch.surf_dead.part"), "w").close()
    os.makedirs(os.path.join(state, "tmp"))
    io.open(os.path.join(state, "tmp", "surf_dead.zip"), "w").close()
    check("dry run exits 0", tick(maps, state), 0)
    check("...asks for the lists and no file", w.files(), [])
    check("...the surf list was paged (3 maps, 2 a page), then bhop, then ksf",
          [u.split("?")[1].split("&expand")[0] if "?" in u else u for u in w.asked],
          ["gamemode=1&take=2&skip=0", "gamemode=1&take=2&skip=2",
           "gamemode=2&take=2&skip=0", W.KSF_BASE + "/maps"])
    check("...and writes nothing into the library, a killed run's leftovers included",
          (lib(maps), os.listdir(os.path.join(state, "tmp"))),
          ([".mapwatch.surf_dead.part"], ["surf_dead.zip"]))

    site = os.path.join(os.path.dirname(maps), "site")
    os.makedirs(site)
    with open(os.path.join(site, "surf_b.json"), "wb") as fh:
        fh.write(b"shipped")
    io.open(os.path.join(site, ".mapwatch.surf_x.json.part"), "w").close()
    w.asked = []
    tick(maps, state, "--go", "--site-zones", site)
    check("--go installs every new map and sweeps the leftovers",
          (lib(maps), os.listdir(os.path.join(state, "tmp"))),
          (["bhop_d.bsp", "surf_a.bsp", "surf_b.bsp", "surf_c.bsp", "surf_k.bsp", "zones"], []))
    check("a Momentum file is the published bytes",
          sha(read(os.path.join(maps, "surf_b.bsp"))), sha(MOM["surf_b"]["bsp"]))
    check("a name both list gets Momentum's build, and KSF's archive is not asked",
          (sha(read(os.path.join(maps, "surf_a.bsp"))) == sha(MOM["surf_a"]["bsp"]),
           [u for u in w.asked if u.endswith("/files/surf_a.zip")]), (True, []))
    check("a KSF archive's one .bsp is installed",
          sha(read(os.path.join(maps, "surf_k.bsp"))), sha(bsp("k")))
    zd = zdir_of(maps)
    check("zones are written for every Momentum map that publishes them",
          zlist(maps), ["bhop_d.json", "surf_a.json", "surf_b.json"])
    check("...as the bytes whose SHA1 is zoneHash",
          sha(read(os.path.join(zd, "surf_a.json"))), sha(ztext(MOM["surf_a"]["zones"]).encode()))
    check("a zone file is copied to the site only where it holds none, and its leftovers go",
          (sorted(os.listdir(site)), read(os.path.join(site, "surf_b.json"))),
          (["bhop_d.json", "surf_a.json", "surf_b.json"], b"shipped"))
    if os.name == "nt":
        SKIPPED.append("file modes (Windows has none): the Pi's run of this suite grades them")
    else:
        modes = [stat.S_IMODE(os.stat(p).st_mode) for p in (
            os.path.join(maps, "surf_b.bsp"), os.path.join(maps, "surf_k.bsp"),
            os.path.join(zd, "surf_a.json"), os.path.join(site, "surf_a.json"))]
        check("control: surfd's import left this process a umask of 077",
              os.umask(0o077), 0o077)
        check("...and maps and zones are world-readable all the same (nginx serves them)",
              modes, [0o644] * 4)
    cat = json.load(io.open(os.path.join(state, "catalogue.json"), encoding="utf-8"))
    check("the catalogue keeps both tiers of a map both list, and Momentum's names",
          (cat["maps"]["surf_a"]["src"], cat["maps"]["surf_a"]["mtier"],
           cat["maps"]["surf_a"]["ktier"], cat["momnames"]),
          ("km", 2, 1, ["bhop_d", "surf_a", "surf_b", "surf_c"]))

    w.asked = []
    tick(maps, state, "--go")
    check("a second run asks for the lists and nothing else",
          (len(w.asked), w.files()), (4, []))
    os.remove(os.path.join(site, "surf_a.json"))
    tick(maps, state, "--go", "--site-zones", site)
    check("a zone file the site has lost is copied again, from the one held",
          sha(read(os.path.join(site, "surf_a.json"))), sha(ztext(MOM["surf_a"]["zones"]).encode()))


def case_bad_files():
    mom = {"surf_bad": M("bad", zones=False), "surf_gone": M("gone", zones=False),
           "surf_cut": M("cut", zones=False), "surf_ok": M("ok", zones=False),
           "surf_text": dict(M("text", zones=False), bsp=b"<html>" * 400),
           "surf_else": dict(M("else", zones=False),
                             url="https://example.org/maps/" + uuid_of("surf_else") + ".bsp")}
    w, maps, state = setup(mom, {})
    w.cdn = {"surf_bad": bsp("not what was published"), "surf_gone": 404}
    w.lie = {"surf_cut": 99999}
    asked = []
    for _ in range(W.STRIKES + 1):
        w.asked = []
        tick(maps, state, "--go")
        asked.append(len(w.files()))
        if len(asked) == 1:
            check("a BSP with the wrong hash, a 404, a body cut short and a 200 that is no "
                  "BSP install nothing; the good one lands", lib(maps), ["surf_ok.bsp"])
            check("a row whose file is not on Momentum's CDN is never asked for",
                  [u for u in w.asked if "example.org" in u], [])
            check("only what is the FILE'S is struck: not the cut transfer, not the page",
                  strikes(state), [("map", "surf_bad", 1, "badhash"), ("map", "surf_gone", 1, "gone")])
    check("a failing file is asked STRIKES times and then left alone; the cut one and the "
          "one behind a page are tried each run, last", asked, [5, 4, 4, 2])
    check("...struck exactly STRIKES times",
          strikes(state), [("map", "surf_bad", 3, "badhash"), ("map", "surf_gone", 3, "gone")])
    w.cdn, w.lie = {}, {}
    st = state_of(state)
    for v in st["later"].values():
        v[1] = int(time.time()) - W.RETRY_DAYS * 86400 + 3600
    io.open(os.path.join(state, "state.json"), "w").write(json.dumps(st))
    w.asked = []
    tick(maps, state, "--go")
    check("...for RETRY_DAYS, an hour short of which it still is",
          (w.asked_for("surf_bad"), w.asked_for("surf_gone"), "surf_cut.bsp" in lib(maps)),
          ([], [], True))
    st = state_of(state)
    for v in st["later"].values():
        v[1] = int(time.time()) - W.RETRY_DAYS * 86400 - 1
    io.open(os.path.join(state, "state.json"), "w").write(json.dumps(st))
    tick(maps, state, "--go")
    check("...and asked again after them",
          lib(maps), ["surf_bad.bsp", "surf_cut.bsp", "surf_gone.bsp", "surf_ok.bsp"])

    # A new build of a shelved map is another file.
    w, maps, state = setup({"surf_v": M("v1", zones=False)}, {})
    w.cdn = {"surf_v": bsp("never the published bytes")}
    for _ in range(W.STRIKES + 1):
        tick(maps, state, "--go")
    w.mom["surf_v"] = M("v2", zones=False)
    w.cdn = {}
    tick(maps, state, "--go")
    check("a shelved map's NEW build is tried at once", lib(maps), ["surf_v.bsp"])

    ksf = {"surf_two": {"tier": 1, "zip": kzip([("surf_two.bsp", bsp("1")), ("x/other.bsp", bsp("2"))])},
           "surf_named": {"tier": 1, "zip": kzip([("surf_other.bsp", bsp("3"))])},
           "surf_text": {"tier": 1, "zip": kzip([("surf_text.bsp", b"<html>" * 400)])},
           "surf_junk": {"tier": 1, "zip": b"<html>scan warning</html>" * 50},
           "surf_none": {"tier": 1, "zip": None},
           "surf_dir": {"tier": 1, "zip": kzip([("maps/surf_dir.bsp", bsp("4")), ("readme.txt", b"hi")])}}
    w, maps, state = setup({}, ksf)
    tick(maps, state, "--go")
    check("a 200 from KSF that is no archive ends KSF for the run, and strikes nothing",
          (lib(maps), len(w.files()), strikes(state)), (["surf_dir.bsp"], 2, []))
    tick(maps, state, "--go")
    check("of six KSF archives only the one holding exactly its own VBSP is installed",
          lib(maps), ["surf_dir.bsp"])
    check("...the three that are archives and wrong are struck, the page is not",
          strikes(state), [("map", "surf_named", 1, "wrongname"), ("map", "surf_text", 1, "notvbsp"),
                           ("map", "surf_two", 1, "bsps=2")])
    check("...from a path inside the archive, as the bare file",
          sha(read(os.path.join(maps, "surf_dir.bsp"))), sha(bsp("4")))
    check("...and no archive is left behind", os.listdir(os.path.join(state, "tmp")), [])

    # Archives zipfile raises something other than BadZipFile on, ones whose
    # size is a lie, and one whose directory is counted in a zip64 record the
    # plain end record does not show: each is that map's, and the run goes on.
    enc = bytearray(kzip([("surf_enc.bsp", bsp("enc"))]))
    for sig, off in ((b"PK\x03\x04", 6), (b"PK\x01\x02", 8)):
        enc[bytes(enc).find(sig) + off] |= 1            # the "encrypted" flag
    meth = bytearray(kzip([("surf_meth.bsp", bsp("meth"))]))
    for sig, off in ((b"PK\x03\x04", 8), (b"PK\x01\x02", 10)):
        struct.pack_into("<H", meth, bytes(meth).find(sig) + off, 9)    # deflate64
    torn = bytearray(kzip([("surf_torn.bsp", bsp("torn", 60000))]))
    torn[len(torn) // 2] ^= 0xFF
    many = kzip([("surf_many.bsp", bsp("many"))] + [("f%d.txt" % i, b"x") for i in range(W.MAX_ZIP_FILES)])
    ksf = {"surf_enc": {"tier": 1, "zip": bytes(enc)}, "surf_meth": {"tier": 1, "zip": bytes(meth)},
           "surf_torn": {"tier": 1, "zip": bytes(torn)}, "surf_many": {"tier": 1, "zip": many},
           "surf_tiny": {"tier": 1, "zip": kzip([("surf_tiny.bsp", b"VBSP" + b"x" * 100)])},
           "surf_z64": {"tier": 1, "zip": zip64ify(kzip([("surf_z64.bsp", bsp("z64"))]))},
           "surf_bz": {"tier": 1, "zip": kzip([("surf_bz.bsp", bsp("bz"))], zipfile.ZIP_BZIP2)},
           "surf_z9": Z("surf_z9", "z9")}
    check("control: zipfile itself opens the zip64 archive and finds its map",
          zipfile.ZipFile(io.BytesIO(ksf["surf_z64"]["zip"])).namelist(), ["surf_z64.bsp"])
    w, maps, state = setup({}, ksf)
    rc = tick(maps, state, "--go")
    check("an encrypted, an unsupported, a torn, a crowded, a zip64, a bzip2 and a 104-byte "
          "archive each cost only their own map",
          (rc, lib(maps), os.listdir(os.path.join(state, "tmp"))), (0, ["surf_z9.bsp"], []))
    check("...and each is struck",
          [(s[1], s[3]) for s in strikes(state)],
          [("surf_bz", "method"), ("surf_enc", "badzip"), ("surf_many", "badzip"),
           ("surf_meth", "method"), ("surf_tiny", "size"), ("surf_torn", "badzip"),
           ("surf_z64", "badzip")])
    check("control: zipfile itself reads the bzip2 archive whole",
          zipfile.ZipFile(io.BytesIO(ksf["surf_bz"]["zip"])).read("surf_bz.bsp") == bsp("bz"), True)


def case_page_scan():
    page = ('<script>self.__next_f.push([1,"a \\"quoted\\" word, a backslash \\\\"])</script>'
            '<script>self.__next_f.push([0,"not a payload"])</script>'
            '<script>self.__next_f.push([1,"second\\n"])</script>'
            '<script>self.__next_f.push([1,"cut off, with an escaped quote \\" and no end')
    check("the page's payload strings are read whole: an escaped quote does not end one, "
          "a backslash before the closing quote does not hide it, and a cut one is dropped",
          W.next_chunks(page), ['a "quoted" word, a backslash \\', "second\n"])
    check("...and a page with none gives none", W.next_chunks("<html>nothing</html>"), [])


def case_limits_on_a_reply():
    class Page(object):
        made = 0

        def json(self, url):
            return {"totalCount": 3, "data": [{}, {}, {}]}
    try:
        W.mom_list(Page())
        got = "read"
    except W.Refused as e:
        got = str(e)
    check("a list page holding more maps than were asked for is refused (MOM_TAKE is 2 here)",
          got, "a page of 3 maps where 2 were asked for")

    w, maps, state = setup({"surf_m1": M("m1")}, {})
    real = W.json.loads

    def too_big(text, *a, **k):
        raise MemoryError()
    W.json.loads = too_big
    try:
        try:
            W.Pacer(0).json(W.MOM_API + "/maps?gamemode=1&take=2&skip=0")
            got = "parsed"
        except W.Refused as e:
            got = str(e)
    finally:
        W.json.loads = real
    check("a reply too large to parse is a refusal, not the end of the run",
          got, "the reply was too much to parse")

    # The wait for a reply's headers has its own clock (SIGALRM: Linux only).
    if not hasattr(signal, "SIGALRM"):
        SKIPPED.append("the header deadline (no SIGALRM)")
        return
    w, maps, state = setup({"surf_slow": M("slow")}, {"surf_kk": Z("surf_kk", "kk")})
    w.hook = lambda n: REAL_SLEEP(3)
    keep, W.OPEN_SECONDS = W.OPEN_SECONDS, 1
    t0 = REAL_TIME()
    try:
        rc = tick(maps, state, "--go")
    finally:
        W.OPEN_SECONDS = keep
    check("a host that sends no reply in OPEN_SECONDS is that host's for the run: nothing "
          "struck, the other host's map installed, and the wait was not sat out",
          (rc, lib(maps), strikes(state), REAL_TIME() - t0 < 2.5,
           sorted(state_of(state)["back"])),
          (0, ["surf_kk.bsp"], [], True, ["surf_slow:" + sha(bsp("slow"))[:12]]))


def case_turns_with_the_crawl():
    # ksfimport --watch talks to the same host: never beside it, never while
    # it is parked after a refusal.
    def asked_ksf(w):
        return sorted(u for u in w.asked if u.startswith(W.KSF_BASE))

    mom, ksf = {"surf_m1": M("m1")}, {"surf_k1": Z("surf_k1", "k1")}
    pf = os.path.join(S.DATA_DIR, "ksf", ".refused")
    os.makedirs(os.path.dirname(pf), exist_ok=True)
    w, maps, state = setup(mom, ksf)
    with io.open(pf, "w", encoding="utf-8") as fh:
        json.dump({"at": int(REAL_TIME()) - 60, "until": int(REAL_TIME()) + 3600, "n": 1,
                   "why": "no answer: The read operation timed out"}, fh)
    rc = tick(maps, state, "--go")
    check("while KSF's crawl is parked after a refusal, KSF is asked nothing; Momentum's "
          "map still lands", (rc, asked_ksf(w), lib(maps)), (0, [], ["surf_m1.bsp", "zones"]))
    with io.open(pf, "w", encoding="utf-8") as fh:
        json.dump({"at": int(REAL_TIME()) - 7200, "until": int(REAL_TIME()) - 60, "n": 1,
                   "why": "x"}, fh)
    tick(maps, state, "--go")
    check("...and once the park is over it is asked again",
          (asked_ksf(w), lib(maps)),
          ([W.KSF_BASE + "/files/surf_k1.zip", W.KSF_BASE + "/maps"],
           ["surf_k1.bsp", "surf_m1.bsp", "zones"]))
    os.remove(pf)

    # The crawl is refused after the page was read: the archives are left too.
    w, maps, state = setup({}, {"surf_k3": Z("surf_k3", "k3")})

    def refused_meanwhile(url):
        with io.open(pf, "w", encoding="utf-8") as fh:
            json.dump({"at": int(REAL_TIME()), "until": int(REAL_TIME()) + 3600, "n": 1,
                       "why": "HTTP 429"}, fh)
    w.khook = refused_meanwhile
    rc = tick(maps, state, "--go")
    check("a park that begins after the page was read stops the archives as well, "
          "and strikes nothing", (rc, asked_ksf(w), lib(maps), strikes(state)),
          (0, [W.KSF_BASE + "/maps"], [], []))
    os.remove(pf)

    try:
        import fcntl
    except ImportError:
        SKIPPED.append("turns with the crawl's lock (no flock)")
        return
    w, maps, state = setup(mom, ksf)
    keep, W.KSF_WAIT = W.KSF_WAIT, 0
    crawl = open(W.KSF_LOCK, "a")
    fcntl.flock(crawl.fileno(), fcntl.LOCK_EX)
    try:
        rc = tick(maps, state, "--go")
    finally:
        crawl.close()
    check("while the crawl holds its lock KSF is asked nothing, and nothing is struck",
          (rc, asked_ksf(w), strikes(state)), (0, [], []))
    tick(maps, state, "--go")
    W.KSF_WAIT = keep
    check("...and with the lock free it is", lib(maps), ["surf_k1.bsp", "surf_m1.bsp", "zones"])

    # Its own requests hold that lock: a crawl tick starting meanwhile is skipped.
    w, maps, state = setup({}, {"surf_k2": Z("surf_k2", "k2")})
    seen = []

    def probe(url):
        fh = open(W.KSF_LOCK, "a")
        try:
            fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            seen.append("free")
        except OSError:
            seen.append("held")
        finally:
            fh.close()
    w.khook = probe
    tick(maps, state, "--go")
    check("the lock is held during every request to KSF (the page and the archive)",
          seen, ["held", "held"])


WORLD = ((-4096, -4096, -512), (4096, 4096, 2048))


def build(tag, mins=WORLD[0], names=("start_dest",)):
    """A VBSP zonefit can read; `tag` makes two builds of one world differ."""
    return TZ.vbsp(mins, WORLD[1], names,
                   extra=b'{\n"classname" "info_null"\n"targetname" "tag_%s"\n}\n' % tag)


def zfile(maps, name):
    try:
        return read(os.path.join(maps, "zones", "online", name + ".json"))
    except OSError:
        return None


def case_given_zones():
    gz = json.loads(TZ.zones().decode())
    gz2 = json.loads(TZ.zones(end=(1500, 0)).decode())
    raw, raw2 = ztext(gz).encode(), ztext(gz2).encode()

    def given(state):
        return sorted(state_of(state).get("given", {}))

    def ranked(name):
        sql("INSERT OR REPLACE INTO runs (map, track, leg, tier, style, player, name, ticks,"
            " tickrate, millis, flags, node, runid, submitted, replay_id) VALUES (?, 0, 0,"
            " 'ranked', 'clean', 'p', 'n', 100, 100, 1000, 0, 'p1', '', 1, 0)", (name,))

    # KSF's archive of a map Momentum zones takes those zones, in the run it arrives.
    mom = {"surf_g": {"bsp": build(b"mom"), "zones": gz, "tier": 1}}
    ksf = {"surf_g": {"tier": 1, "zip": kzip([("surf_g.bsp", build(b"ksf"))])}}
    w, maps, state = setup(mom, ksf)
    tick(maps, state, "--go", "--variants", "5")
    check("KSF's build of a map Momentum zones is given those zones when the builds fit",
          (lib(maps), zlist(maps), zfile(maps, "surf_g_css") == raw, given(state)),
          (["surf_g.bsp", "surf_g_css.bsp", "zones"], ["surf_g.json", "surf_g_css.json"],
           True, ["surf_g_css"]))

    # A build in another frame is given nothing, and is measured once.
    ksf = {"surf_g": {"tier": 1, "zip": kzip([("surf_g.bsp",
                                               build(b"ksf", mins=(-3000, -4096, -512)))])}}
    w, maps, state = setup(mom, ksf)
    calls, real_fit = [], W.zonefit.fit

    def counted(*a):
        calls.append(1)
        return real_fit(*a)
    W.zonefit.fit = counted
    try:
        tick(maps, state, "--go", "--variants", "5")
        tick(maps, state, "--go", "--variants", "5")
    finally:
        W.zonefit.fit = real_fit
    check("a build whose world sits elsewhere is given nothing, and is measured once",
          (zlist(maps), len(calls), sorted(state_of(state)["nofit"]), given(state)),
          (["surf_g.json"], 1, ["surf_g_css"], []))

    # A port by its suffix; a version is not a port; a port missing a restart
    # point is not given; Momentum's own map keeps its own zones.
    mom = {"surf_p": {"bsp": build(b"mom"), "zones": gz, "tier": 1},
           "surf_q": {"bsp": build(b"q"), "zones": gz, "tier": 1},
           "surf_q_fix": {"bsp": build(b"qfix"), "zones": gz2, "tier": 1},
           "surf_q_ksf": {"bsp": build(b"qksf"), "zones": None, "tier": 1}}
    own_timer = TZ.vbsp(WORLD[0], WORLD[1], ("start_dest",), extra=(
        b'{\n"classname" "trigger_momentum_timer_start"\n"model" "*1"\n}\n'))
    held = [("surf_p_fix", build(b"fix")), ("surf_p_v2", build(b"v2")),
            ("surf_p_ksf", build(b"ksf", names=())), ("surf_p_njv", build(b"njv")),
            ("surf_p_go", build(b"go")), ("surf_p_csgo", build(b"csgo")),
            ("surf_p_css", build(b"somebody's own css")), ("surf_p_mom", build(b"pm")),
            ("surf_p_fixed", own_timer)]
    w, maps, state = setup(mom, {}, held=held)
    # Momentum lists surf_p_mom itself, with a row this tool cannot use.
    w.rawrows = [{"id": 7, "name": "surf_p_mom", "status": 0, "leaderboards": [],
                  "currentVersion": {"bspHash": "zz", "downloadURL": "http://elsewhere/x.bsp",
                                     "zoneHash": None}}]
    os.makedirs(os.path.join(maps, "zones", "online"))
    with open(os.path.join(maps, "zones", "online", "surf_p_njv.json"), "wb") as fh:
        fh.write(b'{"somebody":"made these"}')
    local = os.path.join(os.path.dirname(os.path.dirname(S.RUNS_DIR)), "maps", "zones", "local")
    os.makedirs(local, exist_ok=True)
    with open(os.path.join(local, "surf_p_go.json"), "wb") as fh:
        fh.write(b"{}")
    ranked("surf_p_csgo")
    tick(maps, state, "--go")
    os.remove(os.path.join(local, "surf_p_go.json"))
    check("a port by its suffix is given the zones; a version, a port missing the restart "
          "point, one with zones of its own, one with a local override and one with runs "
          "are not; Momentum's own map of such a name keeps its own",
          (zlist(maps), zfile(maps, "surf_p_fix") == raw, zfile(maps, "surf_q_fix") == raw2,
           zfile(maps, "surf_q_ksf"), zfile(maps, "surf_p_njv"), given(state)),
          (["surf_p.json", "surf_p_fix.json", "surf_p_njv.json", "surf_q.json", "surf_q_fix.json"],
           True, True, None, b'{"somebody":"made these"}', ["surf_p_fix"]))
    check("...nor is a _css file that is not KSF's archive, a name Momentum lists itself "
          "with a row that cannot be used, or a port with timer triggers of its own",
          (zfile(maps, "surf_p_css"), zfile(maps, "surf_p_mom"), zfile(maps, "surf_p_fixed"),
           sorted(k for k, v in state_of(state)["nofit"].items() if v[2] == "OWN-TIMER")),
          (None, None, None, ["surf_p_fixed"]))
    lobby("p4", "surf_p_go")
    tick(maps, state, "--go", "--updates")
    check("with --updates the one with runs is given them; one a lobby is on still waits; "
          "zones of its own are still its own",
          (zfile(maps, "surf_p_csgo") == raw, zfile(maps, "surf_p_go"),
           zfile(maps, "surf_p_njv")), (True, None, b'{"somebody":"made these"}'))
    lobby("p4", "surf_elsewhere")
    sql("DELETE FROM runs WHERE map = 'surf_p_csgo'")

    # The donor's zones change: what was given follows with --updates, what
    # somebody edited since does not, and the site's copy follows where it
    # was the old file.
    site = os.path.join(os.path.dirname(maps), "site")
    os.makedirs(site)
    for n, data in (("surf_p", raw), ("surf_p_fix", b'{"shipped":"another"}')):
        with open(os.path.join(site, n + ".json"), "wb") as fh:
            fh.write(data)
    with open(os.path.join(maps, "zones", "online", "surf_p_csgo.json"), "wb") as fh:
        fh.write(b'{"edited":"by hand"}')
    w.mom["surf_p"]["zones"] = gz2
    tick(maps, state, "--go", "--site-zones", site)
    check("the donor's zones changed: without --updates nothing follows",
          (zfile(maps, "surf_p") == raw, zfile(maps, "surf_p_fix") == raw), (True, True))
    lobby("p4", "surf_p_fix")
    tick(maps, state, "--go", "--updates", "--site-zones", site)
    lobby("p4", "surf_elsewhere")
    tick(maps, state, "--go", "--site-zones", site)
    check("...with it the donor's file follows; a build given the old one, on which a "
          "lobby sat during that run, does not follow in a later run without --updates",
          (zfile(maps, "surf_p") == raw2, zfile(maps, "surf_p_fix") == raw), (True, True))
    tick(maps, state, "--go", "--updates", "--site-zones", site)
    check("...with it the donor's file, the build given it, and the site's copy of the old "
          "file follow; a given file edited since and a different file on the site are kept",
          (zfile(maps, "surf_p") == raw2, zfile(maps, "surf_p_fix") == raw2,
           zfile(maps, "surf_p_csgo"), read(os.path.join(site, "surf_p.json")) == raw2,
           read(os.path.join(site, "surf_p_fix.json"))),
          (True, True, b'{"edited":"by hand"}', True, b'{"shipped":"another"}'))

    # The build that was given zones is swapped for another: still fitting, it
    # keeps them; in another frame, they are moved aside -- with --updates.
    def swap(name, data):
        with open(os.path.join(maps, name + ".bsp"), "wb") as fh:
            fh.write(data)

    swap("surf_p_fix", build(b"fix, recompiled"))
    tick(maps, state, "--go", "--updates", "--site-zones", site)
    check("a build given zones is replaced by one that still fits: the zones stay",
          (zfile(maps, "surf_p_fix") == raw2, given(state)), (True, ["surf_p_csgo", "surf_p_fix",
                                                                     "surf_p_go"]))
    swap("surf_p_fix", build(b"fix, moved", mins=(-3000, -4096, -512)))
    tick(maps, state, "--go", "--site-zones", site)
    check("...by one in another frame: without --updates they are left, and said to be",
          zfile(maps, "surf_p_fix") == raw2, True)
    lobby("p4", "surf_p_fix")
    tick(maps, state, "--go", "--updates", "--site-zones", site)
    check("...with it, not while a lobby is on the map",
          zfile(maps, "surf_p_fix") == raw2, True)
    lobby("p4", "surf_elsewhere")
    tick(maps, state, "--go", "--updates", "--site-zones", site)
    aside = os.path.join(maps, "zones", "online", ".old")
    check("...and then they are moved aside, kept, and no longer recorded as given; the "
          "site keeps its own file of that name (it never was ours)",
          (zfile(maps, "surf_p_fix"),
           [f for f in os.listdir(aside) if read(os.path.join(aside, f)) == raw2],
           given(state), read(os.path.join(site, "surf_p_fix.json"))),
          (None, ["surf_p_fix.%s.json" % sha(raw2)[:12]], ["surf_p_csgo", "surf_p_go"],
           b'{"shipped":"another"}'))
    # The same again where the site's copy IS the file given: it goes too.
    swap("surf_p_go", build(b"go, moved", mins=(-3000, -4096, -512)))
    had = os.path.exists(os.path.join(site, "surf_p_go.json"))
    tick(maps, state, "--go", "--updates", "--site-zones", site)
    check("...and where the site's copy is the file that was given, it is removed with it",
          (had, zfile(maps, "surf_p_go"), os.path.exists(os.path.join(site, "surf_p_go.json"))),
          (True, None, False))

    # Whatever the fit check raises is that pair's, not the run's.
    def broken(*a):
        raise RuntimeError("a BSP nothing expected")
    mom = {"surf_e": {"bsp": build(b"mom"), "zones": gz, "tier": 1}}
    w, maps, state = setup(mom, {}, held=[("surf_e_fix", build(b"fix"))])
    real_fit, W.zonefit.fit = W.zonefit.fit, broken
    try:
        rc = tick(maps, state, "--go")
    finally:
        W.zonefit.fit = real_fit
    check("a fit check that raises costs that one pair this run: the run ends well, the "
          "map is in the list, and the pair is not written off",
          (rc, zlist(maps), state_of(state)["nofit"], os.path.exists(os.path.join(state, "mapdl.txt"))),
          (0, ["surf_e.json"], {}, True))
    tick(maps, state, "--go")
    check("...so the next run measures it and gives the zones", zlist(maps),
          ["surf_e.json", "surf_e_fix.json"])
    # Given, then the target is recompiled (it still fits) and the measurement
    # fails once: what was given stays, and is confirmed by the run after.
    with open(os.path.join(maps, "surf_e_fix.bsp"), "wb") as fh:
        fh.write(build(b"fix, recompiled"))
    W.zonefit.fit = broken
    try:
        tick(maps, state, "--go", "--updates")
    finally:
        W.zonefit.fit = real_fit
    check("a measurement that fails on a build swapped since is not \"no longer fits\": "
          "the zones given stay", (zlist(maps), sorted(state_of(state)["given"])),
          (["surf_e.json", "surf_e_fix.json"], ["surf_e_fix"]))
    # A table of its own state in another shape starts again, it does not end the run.
    st = state_of(state)
    st["nofit"], st["given"]["surf_e_fix"], st["later"] = {"surf_e_fix": 7}, "ours", [1, 2]
    with io.open(os.path.join(state, "state.json"), "w", encoding="utf-8") as fh:
        json.dump(st, fh)
    rc = tick(maps, state, "--go", "--updates")
    check("state.json's own tables in another shape do not end the run; a zone file whose "
          "record is lost is somebody's, and kept",
          (rc, zlist(maps)), (0, ["surf_e.json", "surf_e_fix.json"]))
    # A record that names no build is measured, not taken on trust.
    st = state_of(state)
    st["given"] = {"surf_e_fix": {"of": "surf_e", "zh": sha(raw)}}
    with io.open(os.path.join(state, "state.json"), "w", encoding="utf-8") as fh:
        json.dump(st, fh)
    with open(os.path.join(maps, "surf_e_fix.bsp"), "wb") as fh:
        fh.write(build(b"fix, moved", mins=(-3000, -4096, -512)))
    tick(maps, state, "--go", "--updates")
    check("a record of zones given that names no build is measured again: on a build in "
          "another frame they are taken back (moved aside)", zlist(maps),
          [".old", "surf_e.json"])

    # A donor at the published build whose zone file is not the published
    # bytes (Momentum's hash did not match its own zones for 92 maps) still
    # gives the file this box times it by.
    mom = {"surf_u": {"bsp": build(b"mom"), "zones": gz2, "tier": 1}}
    w, maps, state = setup(mom, {}, held=[("surf_u", mom["surf_u"]["bsp"]),
                                          ("surf_u_fix", build(b"fix"))])
    os.makedirs(os.path.join(maps, "zones", "online"))
    with open(os.path.join(maps, "zones", "online", "surf_u.json"), "wb") as fh:
        fh.write(raw)
    tick(maps, state, "--go")
    check("a map at the published build gives the zone file it is timed by here, "
          "published bytes or not",
          (zfile(maps, "surf_u") == raw, zfile(maps, "surf_u_fix") == raw, given(state)),
          (True, True, ["surf_u_fix"]))

    # A donor held at another build than the published one gives nothing: its
    # zone file is not known to be that build's.
    mom = {"surf_d": {"bsp": build(b"mom"), "zones": gz, "tier": 1}}
    w, maps, state = setup(mom, {}, held=[("surf_d", build(b"older")),
                                          ("surf_d_fix", build(b"fix"))])
    os.makedirs(os.path.join(maps, "zones", "online"))
    with open(os.path.join(maps, "zones", "online", "surf_d.json"), "wb") as fh:
        fh.write(raw)
    tick(maps, state, "--go")
    check("a donor held at another build than the published one gives nothing",
          (zlist(maps), given(state)), (["surf_d.json"], []))


def case_map_list():
    def rows(state):
        with io.open(os.path.join(state, "mapdl.txt"), encoding="utf-8") as fh:
            lines = fh.read().split("\n")
        return lines[0], [ln for ln in lines if ln.startswith("dl ")]

    day = time.strftime("%Y-%m-%d", time.gmtime())
    mom = {"surf_m1": M("m1", tier=3), "bhop_m2": M("m2", tier=2)}
    ksf = {"surf_m1": Z("surf_m1", "ksf's m1"), "surf_k1": Z("surf_k1", "k1")}
    w, maps, state = setup(mom, ksf, held=[("de_dust2", bsp("dust")),
                                           ("surf_Old", bsp("old", 5000))])
    tick(maps, state)
    check("a dry run writes no list", os.path.exists(os.path.join(state, "mapdl.txt")), False)
    tick(maps, state, "--go", "--variants", "5")
    check("the list: a row for every surf/bhop map held, as the file is named, with its "
          "mode, lists, tier, size in KB and tiers; KSF's build names the map it is a build of",
          rows(state),
          ("FTESURF-MAPDL 1",
           ["dl bhop_m2 bhop m 2 4 %s 0 2 0" % day,
            "dl surf_k1 surf k 1 4 %s 0 0 1" % day,
            "dl surf_m1 surf km 3 4 %s 0 3 1" % day,
            "dl surf_m1_css surf k 1 4 %s 0 0 1 surf_m1" % day,
            "dl surf_Old surf - 0 5 %s 0 0 0" % day]))
    w.mom["surf_n9"] = M("n9", tier=5)
    w.ids["surf_n9"] = 999
    tick(maps, state, "--go")
    check("a map that arrives later wears New; the ones the list began with do not",
          [ln.split()[1] + ":" + ln.split()[7] for ln in rows(state)[1]],
          ["bhop_m2:0", "surf_k1:0", "surf_m1:0", "surf_m1_css:0", "surf_n9:1", "surf_Old:0"])
    # KSF not read (its crawl parked): the last whole reading stands for the
    # rows it described, and a map that is new now is listed all the same.
    pf = os.path.join(S.DATA_DIR, "ksf", ".refused")
    os.makedirs(os.path.dirname(pf), exist_ok=True)
    with io.open(pf, "w", encoding="utf-8") as fh:
        json.dump({"at": int(REAL_TIME()), "until": int(REAL_TIME()) + 3600, "n": 1, "why": "x"}, fh)
    w.mom["surf_n8"] = M("n8", tier=4)
    w.ids["surf_n8"] = 998
    try:
        tick(maps, state, "--go")
    finally:
        os.remove(pf)
    check("with one list unread the rows keep what the last whole reading said, and a "
          "map new this run is listed",
          [" ".join(ln.split()[1:5]) for ln in rows(state)[1]],
          ["bhop_m2 bhop m 2", "surf_k1 surf k 1", "surf_m1 surf km 3", "surf_m1_css surf k 1",
           "surf_n8 surf m 4", "surf_n9 surf m 5", "surf_Old surf - 0"])
    check("...and KSF's build still names the map it is a build of",
          [ln.split()[10] for ln in rows(state)[1] if len(ln.split()) > 10], ["surf_m1"])
    # The tool's own files in another shape cost a row its history, not the run.
    st = state_of(state)
    st["seen"]["surf_k1"] = "yesterday\ndl evil surf m 1 1 2026-01-01 0 0 0"
    st["seen"]["bhop_m2"] = ["2026-01-01\ndl evil2 surf m 1 1 2026-01-01 0 0 0", "scan"]
    with io.open(os.path.join(state, "state.json"), "w", encoding="utf-8") as fh:
        json.dump(st, fh)
    cat = json.load(io.open(os.path.join(state, "catalogue.json"), encoding="utf-8"))
    cat["maps"]["surf_m1"] = "not a row"
    cat["maps"]["surf_n9"]["src"] = 5
    cat["maps"]["surf_m1_css"]["of"] = "surf_m1 x"
    with io.open(os.path.join(state, "catalogue.json"), "w", encoding="utf-8") as fh:
        json.dump(cat, fh)
    with io.open(pf, "w", encoding="utf-8") as fh:      # KSF unread: that catalogue stands
        json.dump({"at": int(REAL_TIME()), "until": int(REAL_TIME()) + 3600, "n": 1, "why": "x"}, fh)
    try:
        rc = tick(maps, state, "--go")
    finally:
        os.remove(pf)
    got = rows(state)[1]
    check("a seen record, a catalogue row or a build's map of another shape costs the row "
          "what it said, never a second row or the run",
          (rc, len(got), [ln for ln in got if "evil" in ln or " x" in ln],
           [ln.split()[1:4] + ln.split()[6:7] for ln in got
            if ln.split()[1] in ("surf_k1", "bhop_m2", "surf_m1", "surf_n9")]),
          (0, 7, [], [["bhop_m2", "bhop", "m", day], ["surf_k1", "surf", "k", day],
                      ["surf_m1", "surf", "-", day], ["surf_n9", "surf", "-", day]]))
    os.remove(os.path.join(maps, "surf_Old.bsp"))
    tick(maps, state, "--go")
    check("a map no longer held leaves the list",
          [ln.split()[1] for ln in rows(state)[1]],
          ["bhop_m2", "surf_k1", "surf_m1", "surf_m1_css", "surf_n8", "surf_n9"])


def case_bad_names_and_shapes():
    mom = {"surf_ok": M("ok", zones=False),
           "surf_lb": dict(M("lb", zones=False), leaderboards=5)}
    w, maps, state = setup(mom, {"surf_kk": Z("surf_kk", "kk")})
    for i, nm in enumerate(["surf_a\nquit", "surf_sp ", "surf_nul\x00", "surf_nb\xa0", "surf_dot.x",
                            "surf_" + "x" * 64, "../surf_up", 7, None]):
        w.rawrows.append({"id": 900 + i, "name": nm, "currentVersion": {
            "bspHash": sha(b"x"), "downloadURL": W.MOM_CDN + uuid_of("raw%d" % i) + ".bsp"}})
    w.rawrows.append({"id": 950, "name": "surf_nl", "currentVersion": {
        "bspHash": sha(b"x"), "downloadURL": W.MOM_CDN + uuid_of("nl") + ".bsp\n"}})
    w.rawrows.append("not a row")
    w.ksf["surf_kn\n"] = Z("surf_kn", "kn")
    w.ksf["surf_k sp"] = Z("surf_ksp", "ksp")
    rc = tick(maps, state, "--go")
    check("names that are not exactly a map name are never a path or a url, a row whose "
          "leaderboards are not a list still installs, and the run finishes",
          (rc, lib(maps)), (0, ["surf_kk.bsp", "surf_lb.bsp", "surf_ok.bsp"]))

    # A list that ends early, is short, or repeats itself is not Momentum's list.
    six = {"surf_p": M("p"), "surf_q": M("q"), "surf_r": M("r"),
           "bhop_x": M("x"), "bhop_y": M("y"), "bhop_z": M("z")}
    w, maps, state = setup(six, {"surf_k1": Z("surf_k1", "k1")})
    w.short = True
    tick(maps, state, "--go")
    check("a list that ends before its own count is not believed", (lib(maps), w.files()), ([], []))
    w.short, w.stuck = False, True
    W.MOM_MIN = 3
    try:
        tick(maps, state, "--go")
        check("...nor one that answers every `skip` with its first page: 2 names are not 3",
              (lib(maps), w.files()), ([], []))
        w.stuck = False
        tick(maps, state, "--go", "--zones", "0", "--max", "0")
        check("control: the same floor believes the list read whole",
              os.path.exists(os.path.join(state, "catalogue.json")), True)
    finally:
        W.MOM_MIN = 0
    os.remove(os.path.join(state, "catalogue.json"))
    w, maps, state = setup({"surf_p": M("p"), "surf_q": M("q")}, {"surf_k1": Z("surf_k1", "k1")})
    W.MOM_MIN = 2
    try:
        tick(maps, state, "--go")
    finally:
        W.MOM_MIN = 0
    check("...nor one with too few maps in ONE gamemode (bhop is empty here)",
          (lib(maps), w.files()), ([], []))
    floor, W.KSF_MIN = W.KSF_MIN, 5
    try:
        tick(maps, state, "--go", "--zones", "0")
    finally:
        W.KSF_MIN = floor
    check("...nor a KSF page with fewer than KSF_MIN maps",
          (lib(maps), w.asked_for("surf_k1")), (["surf_p.bsp", "surf_q.bsp", "zones"], []))

    # A row we cannot install is still Momentum's NAME: KSF's build must not
    # take the plain name.
    mom = {"surf_both": dict(M("both"), url="https://example.org/maps/" + uuid_of("x") + ".bsp")}
    w, maps, state = setup(mom, {"surf_both": Z("surf_both", "ksf's"), "surf_only": Z("surf_only", "o")})
    tick(maps, state, "--go")
    check("a name Momentum lists with a row we cannot use does not get KSF's build",
          (lib(maps), w.asked_for("surf_both")), (["surf_only.bsp"], []))

    # An entry the lists name that cannot be read: said, not fatal, not fetched over.
    w, maps, state = setup({"surf_dir": M("dir"), "surf_cap": M("cap"), "surf_fine": M("fine", zones=False)}, {})
    os.makedirs(os.path.join(maps, "surf_dir.bsp"))
    with open(os.path.join(maps, "surf_cap.BSP"), "wb") as fh:
        fh.write(b"held some other way")
    rc = tick(maps, state, "--go")
    check("a held entry that is no plain .bsp file is left, not fetched over, and the run goes on",
          (rc, lib(maps), read(os.path.join(maps, "surf_cap.BSP")), len(w.files()), w.zone_asks()),
          (0, ["surf_cap.BSP", "surf_dir.bsp", "surf_fine.bsp"], b"held some other way", 1, []))

    # A held file that cannot be opened: no hash, so neither "the published
    # build" nor "another": no zones, no replacement, and the run goes on.
    w, maps, state = setup({"surf_lock": M("lock"), "surf_free": M("free")}, {},
                           held=[("surf_lock", bsp("lock")), ("surf_free", bsp("free"))])

    def no_open(path, *a, **kw):
        if str(path).endswith("surf_lock.bsp"):
            raise PermissionError(13, "denied", str(path))
        return open(path, *a, **kw)
    W.open = no_open
    try:
        rc = tick(maps, state, "--go", "--updates")
    finally:
        del W.open
    check("a held file that cannot be opened ends nothing and is given nothing",
          (rc, w.files(), zlist(maps)), (0, [], ["surf_free.json"]))


def case_hosts():
    # 503 is about the host: no strike, nothing more asked of it, the file to the back.
    mom = {"surf_h1": M("h1", zones=False), "surf_h2": M("h2", zones=False), "surf_h3": M("h3", zones=False)}
    w, maps, state = setup(mom, {"surf_k1": Z("surf_k1", "k1")})
    w.cdn = {"surf_h1": 503}
    tick(maps, state, "--go")
    check("a 503 ends that host for the run, strikes nothing, and KSF goes on",
          (lib(maps), [u for u in w.files() if W.MOM_CDN in u], strikes(state)),
          (["surf_k1.bsp"], [W.MOM_CDN + uuid_of("surf_h1") + ".bsp"], []))
    w.asked = []
    tick(maps, state, "--go")
    check("...and the next run asks for it LAST, so it cannot block the others",
          (lib(maps), w.files()[-1]),
          (["surf_h2.bsp", "surf_h3.bsp", "surf_k1.bsp"], W.MOM_CDN + uuid_of("surf_h1") + ".bsp"))

    # A 403 for everything, or a page in every file's place, run after run, shelves nothing.
    for what, body in (("a 403", 403), ("a block page", b"<html>blocked</html>" * 40),
                       ("two bytes", b"no")):
        w, maps, state = setup(mom, {})
        w.cdn = {n: body for n in mom}
        asked = []
        for _ in range(W.STRIKES + 1):
            w.asked = []
            tick(maps, state, "--go")
            asked.append(len(w.files()))
        struck = strikes(state)
        w.cdn = {}
        tick(maps, state, "--go")
        check("%s for every file: one request a run, nothing struck, and all of them "
              "arrive when the host is well" % what,
              (asked, struck, lib(maps)),
              ([1, 1, 1, 1], [], ["surf_h1.bsp", "surf_h2.bsp", "surf_h3.bsp"]))

    w, maps, state = setup(mom, {})
    w.cdn = {"surf_h1": b"<html>blocked</html>" * 100000}      # 2 MB
    seen = []
    real_resp = Resp.read1

    def counting(self, n=-1):
        b = real_resp(self, n)
        seen.append(len(b))
        return b
    Resp.read1 = counting
    try:
        try:
            W.download(W.MOM_CDN + uuid_of("surf_h1") + ".bsp", os.path.join(maps, ".x.part"),
                       magic=b"VBSP")
            got = "no refusal"
        except W.Refused:
            got = "refused"
    finally:
        Resp.read1 = real_resp
    check("a page in a file's place is refused at its first bytes, not read to its end",
          (got, sum(seen) <= 1 << 16, lib(maps)), ("refused", True, []))

    # An object's own 500 is counted against it; a gateway's 502 is not.
    w, maps, state = setup(mom, {})
    w.cdn = {"surf_h1": 500}
    tick(maps, state, "--go")
    check("a 500 is that file's, and still ends the host for the run",
          (lib(maps), strikes(state)), ([], [("map", "surf_h1", 1, "HTTP")]))
    w, maps, state = setup(mom, {})
    w.cdn = {"surf_h1": 502}
    tick(maps, state, "--go")
    check("a 502 is the gateway's: no strike", (lib(maps), strikes(state)), ([], []))

    # Five 404s are five files gone, each struck, and none blocks the next.
    five = dict(("surf_g%d" % i, M("g%d" % i, zones=False)) for i in range(5))
    w, maps, state = setup(dict(five, surf_gz=M("gz", zones=False)), {})
    w.cdn = {n: 404 for n in five}
    for _ in range(W.STRIKES):
        tick(maps, state, "--go")
    w.asked = []
    tick(maps, state, "--go")
    check("404s are each their own file's: all struck out after STRIKES runs, the good one in",
          (lib(maps), w.files(), [s[2] for s in strikes(state)]), (["surf_gz.bsp"], [], [3] * 5))

    # Budgets, and the pause between downloads.
    six = dict(("surf_s%d" % i, M("s%d" % i, zones=False)) for i in range(6))
    w, maps, state = setup(six, {})
    tick(maps, state, "--go", "--max-gb", "0")
    check("--max-gb 0 takes nothing", (lib(maps), w.files()), ([], []))
    tick(maps, state, "--go", "--max-gb", "0.000005")       # 5 kB: a 4 kB map, one more, then full
    check("--max-gb stops at the first download past it", lib(maps), ["surf_s0.bsp", "surf_s1.bsp"])
    w, maps, state = setup(six, {})
    w.cdn = {n: bsp("wrong") for n in ("surf_s0", "surf_s1")}
    tick(maps, state, "--go", "--max", "3")
    check("--max counts downloads, failed ones too", (len(w.files()), lib(maps)), (3, ["surf_s2.bsp"]))
    naps, real_sleep = [], W.time.sleep
    W.GET_DELAY, W.time.sleep = 0.0123, naps.append
    try:
        w, maps, state = setup(six, {})
        w.cdn = {n: bsp("wrong") for n in ("surf_s0", "surf_s1", "surf_s2")}
        tick(maps, state, "--go", "--max", "4")
    finally:
        W.GET_DELAY, W.time.sleep = 0.0, real_sleep
    check("GET_DELAY is slept before every download but the first, failed ones too",
          naps.count(0.0123), 3)
    late, W.RUN_SECONDS = W.RUN_SECONDS, -1
    try:
        w, maps, state = setup(six, {})
        tick(maps, state, "--go")
    finally:
        W.RUN_SECONDS = late
    check("past RUN_SECONDS nothing is started", (lib(maps), w.files(), w.zone_asks()), ([], [], []))

    # A host that drips: read() would wait for the whole body; the clock must
    # be looked at between receives.  Each look at this clock is 10 s later.
    w, maps, state = setup({"surf_slow": M("slow", zones=False)}, {})
    w.drip = {"surf_slow": 1}
    ticks = [1000.0]

    def clock():
        ticks[0] += 10
        return ticks[0]
    slow, W.FILE_SECONDS = W.FILE_SECONDS, 25
    time.time = clock
    try:
        try:
            got = W.download(W.MOM_CDN + uuid_of("surf_slow") + ".bsp", os.path.join(maps, ".x.part"))
        except W.Transient as e:
            got = "Transient: " + str(e).split(":")[0]
    finally:
        time.time = REAL_TIME
        W.FILE_SECONDS = slow
    check("a file dripped a byte at a time is dropped at FILE_SECONDS, not at its end",
          (got, lib(maps)), ("Transient: too slow", []))
    w.asked = []
    slow, W.FILE_SECONDS = W.FILE_SECONDS, -1
    try:
        tick(maps, state, "--go")
        tick(maps, state, "--go")
    finally:
        W.FILE_SECONDS = slow
    check("...is nobody's strike, and is asked for again another run",
          (lib(maps), strikes(state), len(w.files())), ([], [], 2))
    api, W.API_SECONDS = W.API_SECONDS, 25
    time.time = clock
    try:
        tick(maps, state, "--go")
    finally:
        time.time = REAL_TIME
        W.API_SECONDS = api
    w.asked = []
    check("control: with the clock put back the same world installs it",
          (tick(maps, state, "--go"), lib(maps)), (0, ["surf_slow.bsp"]))


def case_held_builds():
    old = bsp("the build before")
    mom = {"surf_up": M("up"), "bhop_mix": M("mix"), "surf_live": M("live", zones=False),
           "surf_nz": M("nz"), "surf_zbad": M("zbad"), "surf_zgone": M("zgone", zones=False)}
    ksf = {"surf_up": Z("surf_up", "k")}
    w, maps, state = setup(mom, ksf, held=[("surf_up", old), ("Bhop_Mix", old), ("surf_live", old),
                                           ("surf_nz", old), ("surf_zbad", old), ("surf_zgone", old)])
    zd = zdir_of(maps)
    os.makedirs(zd)
    for stem in ("surf_up", "Bhop_Mix", "surf_zbad", "surf_zgone"):
        with open(os.path.join(zd, stem + ".json"), "wb") as fh:
            fh.write(b"{}")
    w.zonefix = {"surf_zbad": ztext(zones_of("not the published zones"))}
    before = lib(maps)
    sql("DELETE FROM lobbies")
    lobby("p9", "surf_elsewhere")       # heard, and on none of these: only the flag holds it
    tick(maps, state, "--go")
    sql("DELETE FROM lobbies")
    check("a held build that differs is left byte-identical without --updates",
          (lib(maps) == before, read(os.path.join(maps, "surf_up.bsp")) == old, w.files()),
          (True, True, []))
    check("...and so is its zone file", read(os.path.join(zd, "surf_up.json")), b"{}")
    check("...and a build that is not the published one is given no zones",
          (zlist(maps), w.zone_asks()),
          (["Bhop_Mix.json", "surf_up.json", "surf_zbad.json", "surf_zgone.json"], []))
    check("a name held under another spelling is not fetched again", w.asked_for("bhop_mix"), [])

    lobby("p1", "surf_live")
    w.asked = []
    tick(maps, state, "--go", "--updates")
    check("--updates replaces it with the published build, under the spelling held",
          (sha(read(os.path.join(maps, "surf_up.bsp"))), sha(read(os.path.join(maps, "Bhop_Mix.bsp"))),
           [f for f in lib(maps) if f.lower() == "bhop_mix.bsp"]),
          (sha(mom["surf_up"]["bsp"]), sha(mom["bhop_mix"]["bsp"]), ["Bhop_Mix.bsp"]))
    check("...keeps the old BYTES under the old build's hash",
          sorted((f, read(os.path.join(maps, ".old", f)) == old)
                 for f in os.listdir(os.path.join(maps, ".old"))),
          [("%s.%s.bsp" % (s, sha(old)[:12]), True) for s in ("Bhop_Mix", "surf_nz", "surf_up")])
    check("...replaces the zone file with the published one, in the spelling held",
          (sha(read(os.path.join(zd, "surf_up.json"))), sha(read(os.path.join(zd, "Bhop_Mix.json"))),
           sorted(f for f in os.listdir(zd) if f.lower() == "bhop_mix.json")),
          (sha(ztext(mom["surf_up"]["zones"]).encode()), sha(ztext(mom["bhop_mix"]["zones"]).encode()),
           ["Bhop_Mix.json"]))
    check("...and the zones follow the build they were published for",
          sha(read(os.path.join(zd, "surf_nz.json"))), sha(ztext(mom["surf_nz"]["zones"]).encode()))
    check("a build whose own zones are not the published ones stays on its old build AND old "
          "zones, is struck for it, and is not even downloaded",
          (read(os.path.join(maps, "surf_zbad.bsp")) == old, read(os.path.join(zd, "surf_zbad.json")),
           w.asked_for("surf_zbad"), [s for s in strikes(state) if s[1] == "surf_zbad"]),
          (True, b"{}", [], [("zones", "surf_zbad", 1, "zoneshape")]))
    check("...nor is one that publishes no zones where a zone file is held",
          (read(os.path.join(maps, "surf_zgone.bsp")) == old, w.asked_for("surf_zgone")), (True, []))
    check("a map a lobby is on waits, and is not downloaded to find that out",
          (read(os.path.join(maps, "surf_live.bsp")) == old, w.asked_for("surf_live")), (True, []))
    # No lobby is on it now -- but one, on another map, has gone silent.
    sql("DELETE FROM lobbies")
    lobby("p2", "surf_elsewhere", ago=600)
    tick(maps, state, "--go", "--updates")
    check("...and with a lobby silent, where the others are cannot be told: it waits",
          read(os.path.join(maps, "surf_live.bsp")) == old, True)
    sql("DELETE FROM lobbies")
    tick(maps, state, "--go", "--updates")
    check("...and an empty lobbies table is not 'nobody': it waits",
          read(os.path.join(maps, "surf_live.bsp")) == old, True)

    def broken():
        raise RuntimeError("database is locked")
    S.connect = broken
    try:
        tick(maps, state, "--go", "--updates")
    finally:
        S.connect = REAL_CONNECT
    check("...and with the lobbies unreadable nothing held is replaced",
          read(os.path.join(maps, "surf_live.bsp")) == old, True)
    lobby("p2", "surf_elsewhere")
    tick(maps, state, "--go", "--updates")
    check("...until the lobbies are heard, and none is on it",
          sha(read(os.path.join(maps, "surf_live.bsp"))), sha(mom["surf_live"]["bsp"]))

    # A lobby that changes onto the map while its new build is downloading.
    w, maps, state = setup({"surf_mid": M("mid", zones=False)}, {}, held=[("surf_mid", old)])
    w.hook = lambda n: lobby("p3", n)
    tick(maps, state, "--go", "--updates")
    check("a map a lobby came onto during the download keeps its build",
          (read(os.path.join(maps, "surf_mid.bsp")) == old, len(w.files()), lib(maps)),
          (True, 1, ["surf_mid.bsp"]))
    sql("DELETE FROM lobbies")

    # extra.tsv never replaces a held build: a stale line would put an OLDER one in.
    w, maps, state = setup({}, {}, held=[("surf_beta", bsp("the newer beta"))])
    w.mom["surf_beta"] = M("the older beta", zones=False)
    w.hidden = {"surf_beta"}
    os.makedirs(state)
    with io.open(os.path.join(state, "extra.tsv"), "w", newline="\n") as fh:
        fh.write("surf_beta %s %s%s.bsp\n" % (sha(bsp("the older beta")), W.MOM_CDN, uuid_of("surf_beta")))
    lobby("p2", "surf_elsewhere")
    tick(maps, state, "--go", "--updates")
    sql("DELETE FROM lobbies")
    check("a Beta line never replaces a held build, --updates or not",
          (sha(read(os.path.join(maps, "surf_beta.bsp"))), w.files()), (sha(bsp("the newer beta")), []))

    # A file put under the name during the run is not overwritten.
    w, maps, state = setup({"surf_race": M("race", zones=False)}, {})

    def other_tool(n):
        with open(os.path.join(maps, n + ".bsp"), "wb") as fh:
            fh.write(b"another tool's copy")
    w.hook = other_tool
    tick(maps, state, "--go")
    check("a name taken while its file was downloading keeps the file that took it",
          (lib(maps), read(os.path.join(maps, "surf_race.bsp"))),
          (["surf_race.bsp"], b"another tool's copy"))


def case_kept_build():
    mom = {"bhop_eazy": M("published now"), "surf_other": M("published now too")}
    w, maps, state = setup(mom, {}, held=[("bhop_eazy", bsp("the gate's build")),
                                          ("surf_other", bsp("an older build"))])
    keep, W.KEEP_BUILD = W.KEEP_BUILD, ("bhop_eazy",)
    try:
        tick(maps, state, "--go", "--updates")
    finally:
        W.KEEP_BUILD = keep
    check("--updates replaces a build that is not the published one, and never a map "
          "named in KEEP_BUILD",
          (sha(read(os.path.join(maps, "bhop_eazy.bsp"))) == sha(bsp("the gate's build")),
           sha(read(os.path.join(maps, "surf_other.bsp"))) == sha(mom["surf_other"]["bsp"]),
           [u for u in w.files() if uuid_of("bhop_eazy") in u], zlist(maps)),
          (True, True, [], ["surf_other.json"]))
    tick(maps, state, "--go", "--updates")
    check("...and with the name off that list (as shipped: nothing is on it) the map follows",
          (W.KEEP_BUILD, sha(read(os.path.join(maps, "bhop_eazy.bsp"))) == sha(mom["bhop_eazy"]["bsp"])),
          ((), True))


def case_unhashed_zones():
    # Momentum's zoneHash is not the hash of its own zones for some maps (92 on
    # 12 Oct 2026): it saved them again and left the hash behind.
    old = TZ.zones(end=(1500, 0))                           # the zone file held

    def resave(zb=old, stamp=2, bhop=((100, 100),), **more):
        z = json.loads(zb.decode())
        z["dataTimestamp"] = stamp
        z["globalRegions"] = {"allowBhop": [TZ.region(x, y) for x, y in bhop]}
        z.update(more)
        return z

    def canon(z):
        return json.dumps(z, separators=(",", ":"), ensure_ascii=False).encode()

    listed = json.loads(TZ.zones(end=(1000, 0)).decode())  # what zoneHash names: neither
    zh = sha(ztext(listed).encode())
    stale = {"bsp": build(b"u"), "zones": listed, "tier": 1}
    sent = resave()
    now = int(REAL_TIME())

    def world(name, zf=old, held=True, served=sent, bsp_held=None, st=None, m=None):
        """A map whose zones do not hash: held or not, with zone file `zf`."""
        m = m or stale
        w, maps, state = setup({name: dict(m)}, {},
                               held=[(name, bsp_held or m["bsp"])] if held else [])
        if zf is not None:
            os.makedirs(zdir_of(maps))
            with open(os.path.join(zdir_of(maps), name + ".json"), "wb") as fh:
                fh.write(zf)
        if st is not None:
            os.makedirs(state)
            with io.open(os.path.join(state, "state.json"), "w", encoding="utf-8") as fh:
                json.dump(st, fh)
        w.zonefix = {name: served if isinstance(served, str) else ztext(served)}
        return w, maps, state

    def un(state):
        return {k: (v["zh"] == zh, v["sha"][:8]) for k, v in
                state_of(state).get("unhashed", {}).items()}

    def age(state, k, days):
        st = state_of(state)
        st["unhashed"][k]["at"] -= days * 86400
        with io.open(os.path.join(state, "state.json"), "w", encoding="utf-8") as fh:
            json.dump(st, fh)

    def aside(maps):
        try:
            return sorted(os.listdir(os.path.join(zdir_of(maps), ".old")))
        except OSError:
            return []

    def zkey(name):
        return "z:%s:%s" % (name, zh[:12])

    def struck(name, why="zonehash"):
        return {"later": {zkey(name): [3, now, why]}}

    def approve(state, doc):
        os.makedirs(state, exist_ok=True)
        with io.open(os.path.join(state, "approved.json"), "w", encoding="utf-8") as fh:
            json.dump(doc, fh)

    def start_with(**more):
        """The zone file held, its start region given `more`."""
        z = json.loads(old.decode())
        z["tracks"]["main"]["zones"]["segments"][0]["checkpoints"][0]["regions"][0].update(more)
        return ztext(z).encode()

    def kept(name, zb):
        return "%s.%s.json" % (name, sha(zb)[:12])

    # ---- the file held, saved again: taken, by a run with --updates
    w, maps, state = world("surf_un")
    tick(maps, state, "--go")
    check("zones that do not hash are not even asked for by a run without --updates",
          (zfile(maps, "surf_un") == old, len(w.zone_asks())), (True, 0))
    tick(maps, state, "--go", "--updates")
    check("zones that do not hash but are the file held, saved again, are taken: written as "
          "this parse of them, recorded, and the file they replace kept aside",
          (zfile(maps, "surf_un") == canon(sent), strikes(state), un(state), aside(maps),
           read(os.path.join(zdir_of(maps), ".old", kept("surf_un", old))) == old),
          (True, [], {"surf_un": (True, sha(canon(sent))[:8])}, [kept("surf_un", old)], True))
    n = len(w.zone_asks())
    tick(maps, state, "--go", "--updates")
    check("...and are not asked for again the next run", len(w.zone_asks()) - n, 0)
    zp = os.path.join(zdir_of(maps), "surf_un.json")
    os.utime(zp, (1000000000, 1000000000))
    age(state, "surf_un", 8)
    tick(maps, state, "--go", "--updates")
    check("...but after UNHASHED_DAYS they are: the same zones are nothing to write, and the "
          "file is not touched",
          (len(w.zone_asks()) - n, zfile(maps, "surf_un") == canon(sent),
           int(os.stat(zp).st_mtime)), (1, True, 1000000000))
    n = len(w.zone_asks())
    tick(maps, state, "--go", "--updates")
    check("...and that reading counts from then", len(w.zone_asks()) - n, 0)
    w.zonefix = {"surf_un": ztext(resave(stamp=3))}
    age(state, "surf_un", 8)
    tick(maps, state, "--go", "--updates")
    check("a later re-save that moved only the stamp is nothing to write either",
          (len(w.zone_asks()) - n, zfile(maps, "surf_un") == canon(sent),
           int(os.stat(zp).st_mtime), un(state)),
          (1, True, 1000000000, {"surf_un": (True, sha(canon(sent))[:8])}))
    more = resave(stamp=4, bhop=((100, 100), (300, 300)))
    w.zonefix = {"surf_un": ztext(more)}
    age(state, "surf_un", 8)
    n, said = len(w.zone_asks()), io.StringIO()
    with contextlib.redirect_stdout(said):
        tick(maps, state, "--go")
    check("an aged reading is not asked again by a run that could not replace it, and is not "
          "called a difference",
          (len(w.zone_asks()) - n, "differ" in said.getvalue(),
           zfile(maps, "surf_un") == canon(sent)), (0, False, True))
    tick(maps, state, "--go", "--updates")
    check("one that changed globalRegions is taken by a run with --updates, the file before "
          "it kept aside too",
          (zfile(maps, "surf_un") == canon(more), un(state), aside(maps)),
          (True, {"surf_un": (True, sha(canon(more))[:8])},
           sorted([kept("surf_un", old), kept("surf_un", canon(sent))])))
    age(state, "surf_un", -3650)
    n = len(w.zone_asks())
    tick(maps, state, "--go", "--updates")
    check("a reading dated in the future is not believed: asked for again",
          len(w.zone_asks()) - n, 1)
    fixed = json.loads(TZ.zones(end=(1200, 0)).decode())
    w.mom["surf_un"]["zones"] = fixed           # new zones, and their hash IS theirs
    w.zonefix = {}
    n = len(w.zone_asks())
    tick(maps, state, "--go", "--updates")
    check("a new zoneHash is asked for at once, whatever was read under the old one; zones "
          "that hash are written as sent, and the record goes",
          (len(w.zone_asks()) - n, zfile(maps, "surf_un") == ztext(fixed).encode(), un(state)),
          (1, True, {}))

    w, maps, state = world("surf_ue")
    tick(maps, state, "--go", "--updates")
    zp = os.path.join(zdir_of(maps), "surf_ue.json")
    with open(zp, "wb") as fh:
        fh.write(old)                           # somebody puts the file from before back
    n = len(w.zone_asks())
    tick(maps, state, "--go", "--updates")
    check("a file changed since it was read is not the one read: asked for again at once, "
          "and put back",
          (len(w.zone_asks()) - n, read(zp) == canon(sent)), (1, True))

    w, maps, state = world("surf_ub", bsp_held=build(b"older"))
    tick(maps, state, "--go", "--updates")
    check("a build that is not the published one is replaced, with zones taken that way",
          (sha(read(os.path.join(maps, "surf_ub.bsp"))) == sha(stale["bsp"]),
           zfile(maps, "surf_ub") == canon(sent), sorted(un(state)), aside(maps)),
          (True, True, ["surf_ub"], [kept("surf_ub", old)]))

    # ---- nothing held vouches for them: not taken
    other = TZ.zones(end=(1700, 0))
    three = [(1, [(1, "zonetiming")]), (2, [(2, "zonetiming")]), (3, [(3, "zonetiming")]),
             (3, [(3, "zonetiming")]), (3, [(3, "zonetiming")])]
    for label, kw, want in (("a map that is new here", dict(held=False, zf=None), ["surf_nt.bsp"]),
                            ("a map held with no zone file", dict(zf=None), ["surf_nt.bsp"]),
                            ("a zone file held that times the map otherwise", dict(zf=other),
                             ["surf_nt.bsp", "zones"])):
        w, maps, state = world("surf_nt", **kw)
        seen = []
        for _ in range(5):
            tick(maps, state, "--go", "--updates")
            seen.append((len(w.zone_asks()), [s[2:] for s in strikes(state)]))
        check("zones that do not hash for %s are not taken: struck three times, then left"
              % label,
              (lib(maps), zfile(maps, "surf_nt") == kw["zf"], un(state), aside(maps), seen),
              (want, True, {}, [], three))
    w, maps, state = world("surf_nb", zf=other, bsp_held=build(b"older"))
    olds = sha(read(os.path.join(maps, "surf_nb.bsp")))
    tick(maps, state, "--go", "--updates")
    check("...nor is a build replaced for zones like that: old build, and no download",
          (sha(read(os.path.join(maps, "surf_nb.bsp"))) == olds, w.files(), strikes(state)),
          (True, [], [("zones", "surf_nb", 1, "zonetiming")]))

    # ---- approved.json: the very zones a person looked at, by map and zoneHash
    yes = {zkey("surf_ap"): sha(canon(sent))}
    w, maps, state = world("surf_ap", zf=None)
    approve(state, yes)
    tick(maps, state, "--go")
    check("zones a person approved are taken with no file here to compare, and "
          "approved.json is only read",
          (zfile(maps, "surf_ap") == canon(sent), strikes(state), sorted(un(state)),
           json.load(io.open(os.path.join(state, "approved.json"), encoding="utf-8"))),
          (True, [], ["surf_ap"], yes))
    w.zonefix = {"surf_ap": ztext(resave(TZ.zones(end=(1800, 0)), stamp=5))}
    age(state, "surf_ap", 8)
    tick(maps, state, "--go", "--updates")
    check("...and only those: other zones under the same zoneHash later are not taken",
          (zfile(maps, "surf_ap") == canon(sent), strikes(state)),
          (True, [("zones", "surf_ap", 1, "zonetiming")]))
    w, maps, state = world("surf_ad", zf=other)
    approve(state, {zkey("surf_ad"): sha(canon(sent))})
    tick(maps, state, "--go", "--updates")
    check("approved zones replace a zone file that times the map otherwise, which is kept "
          "aside",
          (zfile(maps, "surf_ad") == canon(sent), aside(maps),
           read(os.path.join(zdir_of(maps), ".old", kept("surf_ad", other))) == other),
          (True, [kept("surf_ad", other)], True))
    w, maps, state = world("surf_ab", zf=None, bsp_held=build(b"older"))
    approve(state, {zkey("surf_ab"): sha(canon(sent))})
    tick(maps, state, "--go", "--updates")
    check("approved zones let their build be replaced, and come with it",
          (sha(read(os.path.join(maps, "surf_ab.bsp"))) == sha(stale["bsp"]),
           zfile(maps, "surf_ab") == canon(sent)), (True, True))
    for served, want in ((sent, (["surf_an.bsp", "zones"], [], ["surf_an"])),
                         (resave(TZ.zones(end=(1500, 0), dest="nowhere")),
                          (["surf_an.bsp"], [("zones", "surf_an", 1, "zonebuild")], []))):
        w, maps, state = world("surf_an", zf=None, held=False, served=served)
        approve(state, {zkey("surf_an"): sha(canon(served))})
        tick(maps, state, "--go")
        check("approved zones of a map that is new here are measured on the build it "
              "installs: %s" % ("taken" if not want[1] else "a restart point it lacks, not taken"),
              (lib(maps), strikes(state), sorted(un(state))), want)
    timing = [("zones", "surf_na", 1, "zonetiming")]
    for label, doc, st, want in (
            ("approved as other zones", {zkey("surf_na"): sha(canon(more))}, None, timing),
            ("approved under another zoneHash", {"z:surf_na:000000000000": sha(canon(sent))},
             None, timing),
            ("named in an approved.json that is a list", [zkey("surf_na")], None, timing),
            ("whose approval is not a hash", {zkey("surf_na"): 5}, None, timing),
            ("struck for its hash alone before this version (asked again, by its rules)",
             None, struck("surf_na"), timing),
            ("struck three times for something else (not asked)", None,
             struck("surf_na", why="HTTP 404"), [("zones", "surf_na", 3, "HTTP")])):
        w, maps, state = world("surf_na", zf=None, st=st)
        if doc is not None:
            approve(state, doc)
        tick(maps, state, "--go")
        check("a zone file %s is not taken" % label,
              (zfile(maps, "surf_na"), strikes(state)), (None, want))

    # ---- the reply must be of the version the list named
    for label, move in (("another map", lambda w, n: w.ids.__setitem__(n, 987654)),
                        ("another build", lambda w, n: w.mom[n].__setitem__("hash", "f" * 40)),
                        ("another zoneHash", lambda w, n: w.mom[n].__setitem__(
                            "zones", json.loads(TZ.zones(end=(1100, 0)).decode())))):
        w, maps, state = world("surf_vr")
        w.zhook = lambda n, w=w, move=move: move(w, n)
        tick(maps, state, "--go", "--updates")
        check("zones without their hash in a reply that names %s than the list did are not "
              "taken; no strike, it goes to the back" % label,
              (zfile(maps, "surf_vr") == old, strikes(state), un(state),
               sorted(state_of(state)["back"])), (True, [], {}, [zkey("surf_vr")]))

    # ---- ...and a file the game loads whole
    reg = TZ.region(100, 100)

    def with_global(g):
        return dict(resave(), globalRegions=g)

    for label, served, cap in (
            ("globalRegions that is a list", with_global([reg]), {}),
            ("an allowBhop that is no list", with_global({"allowBhop": {"points": 1}}), {}),
            ("a cancel region of two points",
             with_global({"cancel": [dict(reg, points=reg["points"][:2])]}), {}),
            ("an allowBhop region whose points are not numbers",
             with_global({"allowBhop": [dict(reg, points=[["a", "b"]] * 3)]}), {}),
            ("an overbounce region that is not finite",
             with_global({"overbounce": [dict(reg, bottom=float("nan"))]}), {}),
            ("an allowBhop region a billion units out",
             with_global({"allowBhop": [dict(reg, bottom=1e9)]}), {}),
            ("a cancel region with a coordinate that is text",
             with_global({"cancel": [dict(reg, points=[[100, 100], ["164", 100], [164, 164]])]}),
             {}),
            ("a cancel region with a later vertex that is text nan",
             with_global({"cancel": [dict(reg, points=[[100, 100], ["nan", "nan"], [164, 164]])]}),
             {}),
            ("an allowBhop region with a point that is text",
             with_global({"allowBhop": [dict(reg, points=[[100, 100], [164, 100], "12"])]}), {}),
            ("an allowBhop region whose height is text",
             with_global({"allowBhop": [dict(reg, height="128")]}), {}),
            ("an overbounce region whose bottom is true",
             with_global({"overbounce": [dict(reg, bottom=True)]}), {}),
            ("an allowBhop region whose height is true",
             with_global({"allowBhop": [dict(reg, height=True)]}), {}),
            ("a stamp that is not finite", resave(stamp=float("inf")), {}),
            ("more regions than the game loads", sent, {"GAME_ZONES": 2}),
            ("more points than the game loads", sent, {"GAME_POINTS": 11}),
            ("more bytes than a zone file", sent, {"MAX_ZONE_BYTES": 300})):
        w, maps, state = world("surf_sh", served=served)
        keep = {k: getattr(W, k) for k in cap}
        for k, v in cap.items():
            setattr(W, k, v)
        try:
            tick(maps, state, "--go", "--updates")
        finally:
            for k, v in keep.items():
                setattr(W, k, v)
        check("zones without their hash with %s are not taken%s"
              % (label, " (the cap lowered to %r here)" % list(cap.values())[0] if cap else ""),
              (zfile(maps, "surf_sh") == old, strikes(state), un(state)),
              (True, [("zones", "surf_sh", 1, "zoneshape")], {}))
    main = sent["tracks"]["main"]
    two = json.loads(ztext(sent))
    two["tracks"]["main"]["zones"]["segments"][0]["checkpoints"][0]["regions"][0]["points"] = \
        reg["points"][:2]
    for label, z in (("a start whose x is the text 9000_0e-9",
                      resave(start_with(points=[["9000_0e-9", 0], [64, 0], [64, 64]]))),
                     ("a restart position that is not three numbers",
                      resave(start_with(teleDestPos=[1e30, "x", {}]))),
                     ("a restart yaw that is text", resave(start_with(teleDestYaw="north"))),
                     ("a restart name that is a number", resave(start_with(teleDestTargetname=7))),
                     ("no end", dict(sent, tracks={"main": {"zones": {
                         "segments": main["zones"]["segments"]}}})),
                     ("no start", dict(sent, tracks={"main": {"zones": {
                         "segments": [], "end": main["zones"]["end"]}}})),
                     ("a start of two points", two),
                     ("only a bonus", dict(sent, tracks={"main": {"zones": {}},
                                                         "bonuses": [main]}))):
        w, maps, state = world("surf_ns", zf=None, served=z)
        approve(state, {zkey("surf_ns"): sha(canon(z))})
        tick(maps, state, "--go")
        check("approved zones with %s are not a zone file: nothing written, struck" % label,
              (zlist(maps), strikes(state), un(state)),
              ([], [("zones", "surf_ns", 1, "zoneshape")], {}))

    # ---- what is written is the document that was checked
    tr, gl = ztext(json.loads(old.decode())["tracks"]), ztext(sent["globalRegions"])
    twice = ('{"tracks":{"main":{"zones":{}}},"formatVersion":1,"dataTimestamp":2,'
             '"globalRegions":%s,"tracks":%s}' % (gl, tr))
    w, maps, state = world("surf_dk", served=twice)
    tick(maps, state, "--go", "--updates")
    got = zfile(maps, "surf_dk")
    check("a reply that names `tracks` twice is written with the one that was checked, once",
          (got.count(b'"tracks"'), got == canon(json.loads(twice))), (1, True))
    w, maps, state = world("surf_ek", served=ztext(sent).replace('"tracks"', '"tr\\u0061cks"', 1))
    tick(maps, state, "--go", "--updates")
    check("...and a key written with an escape is written plainly",
          zfile(maps, "surf_ek") == canon(sent), True)

    # ---- measured on the build
    out = TZ.zones(end=(9000, 0))
    for label, zf, served in (
            ("an end outside the world", out, resave(out)),
            ("an end outside the world and nothing but the stamp new", out,
             dict(json.loads(out.decode()), dataTimestamp=2)),
            ("a start outside the world", TZ.zones(start=(9000, 0), end=(1500, 0)), None),
            ("a restart point the build lacks", TZ.zones(end=(1500, 0), dest="nowhere"), None)):
        w, maps, state = world("surf_ob", zf=zf, served=served or resave(zf))
        tick(maps, state, "--go", "--updates")
        check("zones without their hash with %s are not this build's: the file held stays, "
              "nothing is recorded" % label,
              (zfile(maps, "surf_ob") == zf, strikes(state), un(state), aside(maps)),
              (True, [("zones", "surf_ob", 1, "zonebuild")], {}, []))
    for where, want in (([9000, 0, 0], [("zones", "surf_op", 1, "zonebuild")]), ([10, 10, 10], [])):
        zf = start_with(teleDestPos=where, teleDestYaw=90)
        w, maps, state = world("surf_op", zf=zf, served=resave(zf))
        tick(maps, state, "--go", "--updates")
        check("zones without their hash with a restart position at %s: outside the world "
              "they are not this build's, inside they are taken" % (where,),
              (zfile(maps, "surf_op") == (zf if want else canon(resave(zf))), strikes(state)),
              (True, want))
    staged = dict(stale, bsp=build(b"s", names=("start_dest", "stage2")))
    for where, want in (((9000, 0), [("zones", "surf_os", 1, "zonebuild")]), ((500, 0), [])):
        zf = TZ.zones(end=(1500, 0), stage=where)
        w, maps, state = world("surf_os", zf=zf, served=resave(zf), m=staged)
        tick(maps, state, "--go", "--updates")
        check("zones without their hash with a stage at %s: outside the world they are not "
              "this build's, inside they are taken" % (where,),
              (zfile(maps, "surf_os") == (zf if want else canon(resave(zf))), strikes(state)),
              (True, want))
    w, maps, state = world("surf_om", m=dict(stale, bsp=bsp("no world in it")))
    tick(maps, state, "--go", "--updates")
    check("...and on a build that cannot be read they could not be measured: nothing "
          "written, and said apart",
          (zfile(maps, "surf_om") == old, strikes(state), un(state)),
          (True, [("zones", "surf_om", 1, "zonemeasure")], {}))
    w, maps, state = setup({"surf_oh": {"bsp": bsp("no world in it"),
                                        "zones": json.loads(old.decode()), "tier": 1}}, {})
    tick(maps, state, "--go")
    check("zones that DO hash are written whatever the build reads as (as before)",
          (zfile(maps, "surf_oh") == ztext(json.loads(old.decode())).encode(), strikes(state)),
          (True, []))
    newer = dict(stale, bsp=build(b"newer", names=()))
    w, maps, state = world("surf_or", bsp_held=stale["bsp"], m=newer)
    seen = []
    for _ in range(5):
        tick(maps, state, "--go", "--updates")
        seen.append((len(w.zone_asks()), len([u for u in w.files() if uuid_of("surf_or") in u]),
                     [s[2:] for s in strikes(state)]))
    check("a build whose zones would not be its own is not replaced, and is struck run after "
          "run until it is left: three requests, three downloads, no more",
          (sha(read(os.path.join(maps, "surf_or.bsp"))) == sha(stale["bsp"]),
           zfile(maps, "surf_or") == old, [f for f in os.listdir(maps) if f.endswith(".part")],
           seen),
          (True, True, [], [(1, 1, [(1, "zonebuild")]), (2, 2, [(2, "zonebuild")]),
                            (3, 3, [(3, "zonebuild")]), (3, 3, [(3, "zonebuild")]),
                            (3, 3, [(3, "zonebuild")])]))
    w, maps, state = world("surf_oq", zf=out, served=resave(out))
    seen = []
    for _ in range(5):
        tick(maps, state, "--go", "--updates")
        seen.append((len(w.zone_asks()), [s[2:] for s in strikes(state)]))
    check("...and so is a zone file held: three requests, no more",
          seen, [(1, [(1, "zonebuild")]), (2, [(2, "zonebuild")]), (3, [(3, "zonebuild")]),
                 (3, [(3, "zonebuild")]), (3, [(3, "zonebuild")])])
    w, maps, state = world("surf_b2")
    tick(maps, state, "--go", "--updates")
    b2 = build(b"another build of it", names=())
    w.mom["surf_b2"]["bsp"] = b2
    with open(os.path.join(maps, "surf_b2.bsp"), "wb") as fh:
        fh.write(b2)
    n = len(w.zone_asks())
    tick(maps, state, "--go", "--updates")
    check("what was read on one build is not believed on another: asked for again at once, "
          "and measured there",
          (len(w.zone_asks()) - n, strikes(state)), (1, [("zones", "surf_b2", 1, "zonebuild")]))

    # ---- a zone file is kept aside before it is replaced, or it is not replaced
    for label, kw, hashed in (("a zone file held", {}, False),
                              ("the zone file of a build to replace", dict(bsp_held=build(b"older")),
                               False),
                              ("a zone file whose zones DO hash", {}, True)):
        w, maps, state = world("surf_kf", **kw)
        if hashed:
            w.mom["surf_kf"]["zones"], w.zonefix = sent, {}
        with open(os.path.join(zdir_of(maps), ".old"), "wb") as fh:
            fh.write(b"not a folder")
        olds = sha(read(os.path.join(maps, "surf_kf.bsp")))
        tick(maps, state, "--go", "--updates")
        check("where zones/online/.old cannot take a file, %s is left, with its build, and "
              "nothing is asked for" % label,
              (zfile(maps, "surf_kf") == old, sha(read(os.path.join(maps, "surf_kf.bsp"))) == olds,
               len(w.zone_asks()), w.files(), strikes(state)), (True, True, 0, [], []))
    w, maps, state = world("surf_kc")
    real_link = os.link

    def no_links(src, dst):
        if os.path.basename(os.path.dirname(dst)) == ".old" and dst.endswith(".json"):
            raise OSError("no links on this disk")
        return real_link(src, dst)
    os.link = no_links
    try:
        tick(maps, state, "--go", "--updates")
    finally:
        os.link = real_link
    check("where a zone file cannot be linked aside it is copied",
          (zfile(maps, "surf_kc") == canon(sent), aside(maps),
           read(os.path.join(zdir_of(maps), ".old", kept("surf_kc", old))) == old),
          (True, [kept("surf_kc", old)], True))
    w, maps, state = world("surf_kd", bsp_held=build(b"older"))
    olds, real_mk = sha(read(os.path.join(maps, "surf_kd.bsp"))), os.makedirs

    def no_old(path, *a, **kw):
        if os.path.basename(path) == ".old" and "zones" in path:
            raise OSError("no room for a folder")
        return real_mk(path, *a, **kw)
    os.makedirs = no_old
    try:
        tick(maps, state, "--go", "--updates")
    finally:
        os.makedirs = real_mk
    check("where the zone file cannot be kept at the moment of the swap, the build is left "
          "too: old build, old zones, no part",
          (sha(read(os.path.join(maps, "surf_kd.bsp"))) == olds, zfile(maps, "surf_kd") == old,
           [f for f in os.listdir(maps) if f.endswith(".part")]), (True, True, []))
    w, maps, state = world("surf_km", zf=None, bsp_held=build(b"older"))
    approve(state, {zkey("surf_km"): sha(canon(sent))})
    came = b'{"arrived":"meanwhile"}'

    def arrives(name):
        os.makedirs(zdir_of(maps), exist_ok=True)
        with open(os.path.join(zdir_of(maps), "surf_km.json"), "wb") as fh:
            fh.write(came)
    w.hook = arrives
    tick(maps, state, "--go", "--updates")
    check("a zone file that arrives while its build is downloading is kept aside too",
          (zfile(maps, "surf_km") == canon(sent), aside(maps),
           read(os.path.join(zdir_of(maps), ".old", kept("surf_km", came))) == came),
          (True, [kept("surf_km", came)], True))

    # ---- state of another shape
    w, maps, state = setup({"surf_st": {"bsp": build(b"u"), "zones": json.loads(old.decode()),
                                        "tier": 1}}, {})
    os.makedirs(state)
    with io.open(os.path.join(state, "state.json"), "w", encoding="utf-8") as fh:
        json.dump({"later": {"z:a:b": "text", "c": [1], "d": [1, "when", "why"], "e": None,
                             "f": [3, float("inf"), "HTTP 404"],
                             "z:ok:abc": [3, now, "HTTP 404"]},
                   "back": {"q": "text", "r": float("inf"), "ok": now}, "unhashed": [1]}, fh)
    rc = tick(maps, state, "--go")
    check("strikes of another shape in state.json are dropped, not raised on",
          (rc, sorted(state_of(state)["later"]), sorted(state_of(state)["back"]), lib(maps),
           state_of(state)["unhashed"]),
          (0, ["z:ok:abc"], ["ok"], ["surf_st.bsp", "zones"], {}))


def case_first_zones():
    # A held map at the published build with no zone file: written, unless it
    # already has runs -- then the rule under them would change.
    mom = {"surf_new": M("new"), "surf_run": M("run"), "surf_dir": M("dir"), "surf_idle": M("idle")}
    w, maps, state = setup(mom, {}, held=[(n, mom[n]["bsp"]) for n in ("surf_run", "surf_dir", "surf_idle")])
    sql("INSERT OR REPLACE INTO runs (map, track, leg, tier, style, player, name, ticks, tickrate,"
        " millis, flags, node, runid, submitted, replay_id) VALUES ('surf_run', 0, 0, 'ranked',"
        " 'clean', 'p', 'n', 100, 100, 1000, 0, 'p1', '', 1, 0)")
    sql("INSERT OR REPLACE INTO runs (map, track, leg, tier, style, player, name, ticks, tickrate,"
        " millis, flags, node, runid, submitted, replay_id) VALUES ('surf_idle', 0, 0, 'ksf',"
        " 'clean', '7', 'n', 100, 66.67, 1500, 0, 'ksf', '', 1, 0)")
    data = os.path.dirname(S.RUNS_DIR)
    os.makedirs(os.path.join(data, "resume", "surf_dir"))
    io.open(os.path.join(data, "resume", "surf_dir", "@parked"), "w").close()
    os.makedirs(os.path.join(data, "saves", "surf_idle"))        # empty: nothing was saved
    tick(maps, state, "--go")
    check("a first zone file goes to a new map and to a held one nobody has a run on -- "
          "imported times and an empty folder are not runs -- and not under a ranked run "
          "or a parked one", zlist(maps), ["surf_idle.json", "surf_new.json"])
    tick(maps, state, "--go", "--updates")
    check("...which --updates allows", zlist(maps),
          ["surf_dir.json", "surf_idle.json", "surf_new.json", "surf_run.json"])

    def broken():
        raise RuntimeError("database is locked")
    w, maps, state = setup(mom, {}, held=[("surf_idle", mom["surf_idle"]["bsp"])])
    S.connect = broken
    try:
        tick(maps, state, "--go", "--max", "1")
    finally:
        S.connect = REAL_CONNECT
    check("with the board unreadable no first zone file is written, a new map's included",
          (lib(maps), zlist(maps)), (["surf_dir.bsp", "surf_idle.bsp"], []))
    # A tree of runs that cannot be listed is "cannot tell", not "none".
    w, maps, state = setup(mom, {}, held=[("surf_idle", mom["surf_idle"]["bsp"])])
    real_listdir = os.listdir

    def no_resume(path="."):
        if str(path).endswith("resume"):
            raise PermissionError(13, "denied", str(path))
        return real_listdir(path)
    os.listdir = no_resume
    try:
        tick(maps, state, "--go", "--max", "0")
    finally:
        os.listdir = real_listdir
    check("...nor when a folder of parked runs cannot be listed", zlist(maps), [])

    # A map whose BSP was lost and comes back still has its runs: its build is
    # installed and said, and it gets no first zone file.
    w, maps, state = setup({"surf_run": mom["surf_run"], "surf_new": mom["surf_new"]}, {})
    tick(maps, state, "--go")
    check("a map installed under a name that already has runs gets no zones of ours, "
          "and they are not asked for",
          (lib(maps), zlist(maps), len(w.zone_asks())),
          (["surf_new.bsp", "surf_run.bsp", "zones"], ["surf_new.json"], 1))

    # A first zone file never lands while a lobby is on the map, or unheard.
    w, maps, state = setup({"surf_on": M("on")}, {}, held=[("surf_on", bsp("on"))])
    lobby("p7", "surf_on")
    tick(maps, state, "--go")
    sql("DELETE FROM lobbies")
    tick(maps, state, "--go")
    check("a first zone file waits while a lobby is on the map, and while none is heard",
          (zlist(maps), w.zone_asks()), ([], []))
    lobby("p0", "surf_elsewhere")
    tick(maps, state, "--go")
    check("...and is written once they are heard and elsewhere", zlist(maps), ["surf_on.json"])

    # History and lobbies are looked at again at the write: a first run can be
    # set, or a lobby arrive, while this run is downloading or asking.
    def ranked(name):
        sql("INSERT OR REPLACE INTO runs (map, track, leg, tier, style, player, name, ticks,"
            " tickrate, millis, flags, node, runid, submitted, replay_id) VALUES (?, 0, 0,"
            " 'ranked', 'clean', 'p', 'n', 100, 100, 1000, 0, 'p1', '', 1, 0)", (name,))

    two = {"surf_dl": M("dl"), "surf_h2": M("h2")}
    w, maps, state = setup(two, {}, held=[("surf_h2", two["surf_h2"]["bsp"])])
    w.hook = lambda n: ranked("surf_h2")
    tick(maps, state, "--go")
    check("a held map whose first run is set while another map downloads gets no zone file",
          zlist(maps), ["surf_dl.json"])
    sql("DELETE FROM runs WHERE map = 'surf_h2'")

    w, maps, state = setup({"surf_h3": M("h3")}, {}, held=[("surf_h3", bsp("h3"))])
    w.zhook = ranked
    tick(maps, state, "--go")
    check("...nor one whose first run is set while its zones are being asked for",
          (zlist(maps), len(w.zone_asks())), ([], 1))
    sql("DELETE FROM runs WHERE map = 'surf_h3'")

    w, maps, state = setup({"surf_h4": M("h4")}, {}, held=[("surf_h4", bsp("h4"))])
    w.zhook = lambda n: lobby("p9", n)
    tick(maps, state, "--go")
    check("...nor one a lobby moves onto meanwhile", (zlist(maps), len(w.zone_asks())), ([], 1))

    # The lobby comes during the request; its run lands just after the history
    # read and it is gone before the next look at the lobbies.
    w, maps, state = setup({"surf_h6": M("h6")}, {}, held=[("surf_h6", bsp("h6"))])
    w.zhook = lambda n: lobby("p0", n)
    real_played = W.played

    def played_then_run():
        out = real_played()
        if w.zone_asks():
            ranked("surf_h6")
            lobby("p0", "surf_elsewhere")
        return out
    W.played = played_then_run
    try:
        tick(maps, state, "--go")
    finally:
        W.played = real_played
    check("...nor one whose lobby came during the request and left, its run set, "
          "inside the history read", zlist(maps), [])
    sql("DELETE FROM runs WHERE map = 'surf_h6'")

    w, maps, state = setup({"surf_h8": M("h8")}, {}, held=[("surf_h8", bsp("h8"))])

    def played_then_lobby():
        out = real_played()
        if w.zone_asks():
            lobby("p0", "surf_h8")
        return out
    W.played = played_then_lobby
    try:
        tick(maps, state, "--go")
    finally:
        W.played = real_played
    check("...nor one a lobby moves onto during the history read itself", zlist(maps), [])

    # A history folder that is listed and then cannot be opened is "cannot tell".
    w, maps, state = setup({"surf_h7": M("h7")}, {}, held=[("surf_h7", bsp("h7"))])
    real_listdir = os.listdir

    def gone(path="."):
        if str(path).endswith("resume"):
            raise FileNotFoundError(2, "No such file or directory", str(path))
        return real_listdir(path)
    os.listdir = gone
    try:
        tick(maps, state, "--go")
    finally:
        os.listdir = real_listdir
    check("...nor any map while a folder of parked runs is listed and will not open",
          zlist(maps), [])
    keep, S.RUNS_DIR = S.RUNS_DIR, os.path.join(HOME, "no-such-game", "data", "runs")
    try:
        tick(maps, state, "--go")
    finally:
        S.RUNS_DIR = keep
    check("...nor on a box whose game data folder is not there at all", zlist(maps), [])
    tick(maps, state, "--go")
    check("control: with the folders readable that same map gets its zones",
          zlist(maps), ["surf_h7.json"])

    w, maps, state = setup({"surf_n5": M("n5")}, {})
    w.zhook = ranked
    tick(maps, state, "--go")
    check("...and a map installed this run is looked at again the same way",
          (lib(maps), zlist(maps), len(w.zone_asks())), (["surf_n5.bsp"], [], 1))
    sql("DELETE FROM runs WHERE map = 'surf_n5'")

    sql("DELETE FROM runs WHERE map IN ('surf_run', 'surf_idle')")
    shutil.rmtree(os.path.join(data, "resume"))
    shutil.rmtree(os.path.join(data, "saves"))

    # Zone requests: a 404 is that map's, a 503 the host's, a reply with no
    # zones in it the host's too, zones on the wrong hash that map's.
    mom = dict(("surf_z%d" % i, M("z%d" % i)) for i in range(4))
    w, maps, state = setup(mom, {}, held=[(n, mom[n]["bsp"]) for n in mom])
    w.zonecode = {"surf_z0": 404, "surf_z2": 503}
    tick(maps, state, "--go")
    check("a 404 for one map's zones is struck once and the next map is asked; a 503 ends them",
          (zlist(maps), len(w.zone_asks()), strikes(state)),
          (["surf_z1.json"], 3, [("zones", "surf_z0", 1, "HTTP")]))
    w.asked = []
    tick(maps, state, "--go")
    check("...and the refused one goes last next run, behind the one it blocked",
          [u.split("/maps/")[1].split("?")[0] for u in w.zone_asks()],
          [str(w.ids[n]) for n in ("surf_z0", "surf_z3", "surf_z2")])
    w, maps, state = setup(mom, {}, held=[(n, mom[n]["bsp"]) for n in mom])
    w.nozones = set(mom)
    for _ in range(W.STRIKES + 1):
        w.asked = []
        tick(maps, state, "--go")
    check("a reply with no zones in it is the host's: one request a run, nothing struck",
          (len(w.zone_asks()), strikes(state), zlist(maps)), (1, [], []))

    # A zone file that arrives while this run is at work (mapsync copies them
    # in) is somebody's, and is kept.
    w, maps, state = setup({"surf_za": M("za")}, {}, held=[("surf_za", bsp("za"))])

    def mapsync_copy(n):
        os.makedirs(zdir_of(maps), exist_ok=True)
        with open(os.path.join(zdir_of(maps), n + ".json"), "wb") as fh:
            fh.write(b"mapsync's copy")
    w.zhook = mapsync_copy
    tick(maps, state, "--go")
    check("a zone file that arrived while its zones were being fetched is kept",
          read(os.path.join(zdir_of(maps), "surf_za.json")), b"mapsync's copy")

    # A zone file held for a map whose BSP is not: installing the map must not
    # write over it.
    w, maps, state = setup({"surf_zi": M("zi")}, {})
    os.makedirs(zdir_of(maps))
    with open(os.path.join(zdir_of(maps), "surf_zi.json"), "wb") as fh:
        fh.write(b"an operator's")
    tick(maps, state, "--go")
    check("installing a map whose zone file was already here leaves that file alone",
          (lib(maps), read(os.path.join(zdir_of(maps), "surf_zi.json")), w.zone_asks()),
          (["surf_zi.bsp", "zones"], b"an operator's", []))
    w, maps, state = setup({"surf_zt": M("zt")}, {})
    w.zonefix = {"surf_zt": ztext(zones_of("wrong"))}
    tick(maps, state, "--go")
    check("a new map whose zones fail is asked for them once that run, not twice",
          (len(w.zone_asks()), strikes(state)), (1, [("zones", "surf_zt", 1, "zoneshape")]))
    w, maps, state = setup({"surf_u0": M("u0"), "surf_u1": M("u1")}, {})
    w.zonefix = {"surf_u0": '{"name":"\\ud800 half a character"}'}
    rc = tick(maps, state, "--go")
    check("zones that cannot even be written as bytes are that map's: struck, and the run goes on",
          (rc, zlist(maps), strikes(state)), (0, ["surf_u1.json"], [("zones", "surf_u0", 1, "zoneshape")]))


def case_variants():
    long = "surf_" + "l" * 57                        # 62: its _css name would be 66
    mom = {"surf_a": M("a", tier=2), "surf_s": M("s", zones=False, tier=3),
           "surf_x": M("x", zones=False, tier=4), long: M("long", zones=False)}
    ksf = {"surf_a": Z("surf_a", "ksf's a"), "surf_s": Z("surf_s", "s"),
           "surf_k": dict(Z("surf_k", "k"), tier=5), "surf_x": dict(Z("surf_x", "ksf's x"), tier=6),
           "surf_x_css": dict(Z("surf_x_css", "a map of that name"), tier=7),
           long: Z(long, "ksf's long")}
    w, maps, state = setup(mom, ksf)
    tick(maps, state, "--go")
    whole = sorted(["surf_a.bsp", "surf_k.bsp", "surf_s.bsp", "surf_x.bsp", "surf_x_css.bsp",
                    long + ".bsp", "zones"])
    check("without --variants no second build is fetched",
          (lib(maps), [u for u in w.asked if u.endswith(("surf_a.zip", "surf_s.zip", "surf_x.zip"))]),
          (whole, []))
    now = int(time.time())
    sql("INSERT OR REPLACE INTO mapwant (map, asked, first, last) VALUES ('surf_s', 1, ?, ?)",
        (now, now))
    w.asked = []
    tick(maps, state, "--go", "--variants", "1")
    check("--variants 1 compares one archive, a viewed map's first",
          (w.files(), lib(maps)), ([W.KSF_BASE + "/files/surf_s.zip"], whole))
    w.asked = []
    tick(maps, state, "--go", "--variants", "5")
    check("KSF's build of a name Momentum lists is kept beside it as <name>_css",
          (w.files(), sha(read(os.path.join(maps, "surf_a_css.bsp"))),
           sha(read(os.path.join(maps, "surf_a.bsp")))),
          ([W.KSF_BASE + "/files/surf_a.zip"], sha(bsp("ksf's a")), sha(mom["surf_a"]["bsp"])))
    check("...an archive that is the build held makes none, a map really named <name>_css "
          "is not taken for one, and a name too long to carry the suffix is not tried",
          (lib(maps), sha(read(os.path.join(maps, "surf_x_css.bsp")))),
          (sorted(whole + ["surf_a_css.bsp"]), sha(bsp("a map of that name"))))
    check("...and it is given no zones", zlist(maps), ["surf_a.json"])
    cat = json.load(io.open(os.path.join(state, "catalogue.json"), encoding="utf-8"))["maps"]
    check("the catalogue names it as KSF's build of that map, and not the namesake",
          (cat["surf_a_css"].get("of"), cat["surf_a_css"]["src"], cat["surf_a_css"]["ktier"],
           cat["surf_x_css"].get("of")), ("surf_a", "k", 1, None))
    w.asked = []
    tick(maps, state, "--go", "--variants", "5")
    check("a later run asks for no archive again", w.files(), [])
    os.remove(os.path.join(state, "state.json"))
    os.remove(os.path.join(state, "catalogue.json"))
    tick(maps, state, "--go")
    cat = json.load(io.open(os.path.join(state, "catalogue.json"), encoding="utf-8"))["maps"]
    check("with its state lost, a _css file is not CALLED KSF's build until compared again",
          "surf_a_css" in cat, False)
    w.asked = []
    tick(maps, state, "--go", "--variants", "5")
    cat = json.load(io.open(os.path.join(state, "catalogue.json"), encoding="utf-8"))["maps"]
    check("...which the next --variants run does, against KSF's archive, writing nothing",
          (sorted(w.files()), cat["surf_a_css"].get("of"),
           sha(read(os.path.join(maps, "surf_a_css.bsp")))),
          ([W.KSF_BASE + "/files/surf_a.zip", W.KSF_BASE + "/files/surf_s.zip"], "surf_a",
           sha(bsp("ksf's a"))))
    sql("DELETE FROM mapwant")

    # Somebody's own file under that name is neither KSF's build nor ours to replace.
    w, maps, state = setup({"surf_f": M("f", zones=False)}, {"surf_f": Z("surf_f", "ksf's f")},
                           held=[("surf_f", bsp("f")), ("surf_f_css", bsp("somebody's own"))])
    tick(maps, state, "--go", "--variants", "5")
    cat = json.load(io.open(os.path.join(state, "catalogue.json"), encoding="utf-8"))["maps"]
    check("a _css file that is not KSF's archive is left, and not listed as its build",
          (sha(read(os.path.join(maps, "surf_f_css.bsp"))), "surf_f_css" in cat, strikes(state)),
          (sha(bsp("somebody's own")), False, []))
    w.asked = []
    tick(maps, state, "--go", "--variants", "5")
    check("...and KSF is not asked for that archive again while the file stays", w.files(), [])


def case_zones_and_limits():
    mom = {"surf_z1": M("z1"), "surf_z2": M("z2"), "surf_z3": M("z3")}
    w, maps, state = setup(mom, {})
    w.zonefix = {"surf_z2": ztext(zones_of("somebody else's"))}
    tick(maps, state, "--go", "--max", "2")
    check("--max 2 takes two maps", lib(maps), ["surf_z1.bsp", "surf_z2.bsp", "zones"])
    check("zones that neither hash to zoneHash nor have a zone file's shape are not "
          "written, and that is counted once",
          (zlist(maps), strikes(state)), (["surf_z1.json"], [("zones", "surf_z2", 1, "zoneshape")]))
    w.zonefix = {}
    tick(maps, state, "--go", "--zones", "0")
    check("--zones 0 asks for no held map's zones; a map installed now gets its own at once",
          zlist(maps), ["surf_z1.json", "surf_z3.json"])
    tick(maps, state, "--go")
    check("the next run takes the zones still owed",
          (lib(maps), zlist(maps)),
          (["surf_z1.bsp", "surf_z2.bsp", "surf_z3.bsp", "zones"],
           ["surf_z1.json", "surf_z2.json", "surf_z3.json"]))

    ksf = {"surf_k1": dict(Z("surf_k1", "k1"), tier=2), "surf_z1": dict(Z("surf_z1", "ksf's z1"), tier=2)}
    w, maps, state = setup(mom, ksf)
    w.down = {"mom"}
    tick(maps, state, "--go")
    check("with Momentum's names never read, KSF's new maps wait", (lib(maps), w.files()), ([], []))
    check("...and no catalogue is written from half the lists",
          os.path.exists(os.path.join(state, "catalogue.json")), False)
    w.down = set()
    tick(maps, state, "--go", "--max", "0")     # both lists read: a catalogue
    w.down = {"mom"}
    w.asked = []
    tick(maps, state, "--go")
    check("with an earlier reading, KSF's own map lands and a name Momentum lists does not",
          (lib(maps), w.asked_for("surf_z1")), (["surf_k1.bsp"], []))

    w, maps, state = setup(mom, {})
    floor, W.FLOOR_GB = W.FLOOR_GB, 10 ** 9
    try:
        tick(maps, state, "--go")
    finally:
        W.FLOOR_GB = floor
    check("under the free-space floor nothing is taken", (lib(maps), w.files()), ([], []))

    w, maps, state = setup(mom, {})
    got = W.download(W.MOM_CDN + uuid_of("surf_z1") + ".bsp",
                     os.path.join(maps, ".x.part"), cap=1000)
    check("a body past the size cap is refused and leaves nothing", (got[0], lib(maps)), ("toobig", []))
    w.asked = []
    cap, W.MAX_API_BYTES = W.MAX_API_BYTES, 64
    try:
        tick(maps, state, "--go")
    finally:
        W.MAX_API_BYTES = cap
    check("a list reply past MAX_API_BYTES is not believed", (lib(maps), w.files()), ([], []))


def case_extra_and_lock():
    mom = {"surf_app": M("app", zones=False)}
    beta = bsp("beta")
    w, maps, state = setup(dict(mom, surf_beta={"bsp": beta, "zones": None, "tier": None},
                                surf_both={"bsp": bsp("beta's both"), "zones": None, "tier": None}),
                           {"surf_both": Z("surf_both", "ksf's both")})
    w.hidden = {"surf_beta", "surf_both"}
    os.makedirs(state)

    def lines(st, *rows):
        with io.open(os.path.join(st, "extra.tsv"), "w", newline="\n") as fh:
            fh.write("# name sha1 url\n")
            for r in rows:
                fh.write(r + "\n")
    lines(state,
          "surf_beta %s %s%s.bsp" % (sha(beta), W.MOM_CDN, uuid_of("surf_beta")),
          "surf_both %s %s%s.bsp" % (sha(bsp("beta's both")), W.MOM_CDN, uuid_of("surf_both")),
          "surf_app %s %s%s.bsp" % ("0" * 40, W.MOM_CDN, uuid_of("surf_app")),
          "surf_evil %s https://example.org/x.bsp" % ("1" * 40),
          # as long as the CDN's prefix, so only the prefix test refuses it
          "surf_evil2 %s https://cdn.momentum-mod.biz/maps/%s.bsp" % ("4" * 40, uuid_of("surf_evil2")),
          "../etc %s %s%s.bsp" % ("2" * 40, W.MOM_CDN, uuid_of("x")),
          "kz_other %s %s%s.bsp" % ("3" * 40, W.MOM_CDN, uuid_of("kz_other")))
    tick(maps, state, "--go")
    check("a Beta map from extra.tsv is installed on its published hash",
          sha(read(os.path.join(maps, "surf_beta.bsp"))), sha(beta))
    check("...a map approved since is taken from the public list, not from the stale line",
          (sha(read(os.path.join(maps, "surf_app.bsp"))) == sha(mom["surf_app"]["bsp"]),
           len(w.asked_for("surf_app"))), (True, 1))
    check("...a name KSF lists too gets the Beta build, and KSF's archive is not asked",
          (sha(read(os.path.join(maps, "surf_both.bsp"))), [u for u in w.files() if "/files/" in u]),
          (sha(bsp("beta's both")), []))
    check("...and lines off the CDN, off the name rules or off surf/bhop install nothing",
          lib(maps), ["surf_app.bsp", "surf_beta.bsp", "surf_both.bsp"])

    # Held extra/beta zones can seed a named port, but not a shifted course.
    beta_build = TZ.vbsp((-4096, -4096, -4096), (4096, 4096, 4096), ("start_dest",))
    shifted = TZ.vbsp((20000, 20000, 20000), (30000, 30000, 30000), ("start_dest",))
    wb, mb, sb = setup({"surf_beta": {"bsp": beta_build, "zones": None, "tier": None}},
                       {"surf_beta_ksf": Z("surf_beta_ksf", "port"),
                        "surf_beta_fix": Z("surf_beta_fix", "shifted")},
                       held=[("surf_beta", beta_build), ("surf_beta_ksf", beta_build),
                             ("surf_beta_fix", shifted)])
    wb.hidden = {"surf_beta"}
    os.makedirs(sb)
    lines(sb, "surf_beta %s %s%s.bsp" % (sha(beta_build), W.MOM_CDN, uuid_of("surf_beta")))
    os.makedirs(os.path.join(mb, "zones", "online"))
    with open(os.path.join(mb, "zones", "online", "surf_beta.json"), "wb") as fh:
        fh.write(TZ.zones())
    tick(mb, sb, "--go")
    cb = json.load(io.open(os.path.join(sb, "catalogue.json"), encoding="utf-8"))["maps"]
    check("held extra donor links KSF ports; compatible zones copy, shifted zones do not",
          (cb["surf_beta_ksf"].get("of"), cb["surf_beta_ksf"].get("port"),
           zfile(mb, "surf_beta_ksf") == TZ.zones(), zfile(mb, "surf_beta_fix")),
          ("surf_beta", True, True, None))

    # ...even on a run where the CDN refuses the Beta file and KSF is answering.
    w3, maps3, state3 = setup({"surf_bk": {"bsp": bsp("beta's"), "zones": None, "tier": None}},
                              {"surf_bk": Z("surf_bk", "ksf's")})
    w3.hidden = {"surf_bk"}
    w3.cdn = {"surf_bk": 503}
    os.makedirs(state3)
    lines(state3, "surf_bk %s %s%s.bsp" % (sha(bsp("beta's")), W.MOM_CDN, uuid_of("surf_bk")))
    tick(maps3, state3, "--go")
    check("a Beta name the CDN refuses is not filled from KSF's archive instead",
          (lib(maps3), [u for u in w3.files() if "/files/" in u]), ([], []))

    # Momentum unread: the last reading of its names still tells a stale Beta
    # line.  The stale line's own bytes are on the CDN, so only the names stop it.
    late = {"bsp": bsp("late, as a beta"), "zones": None, "tier": None}
    w2, maps2, state2 = setup({"surf_late": late}, {"surf_kx": Z("surf_kx", "kx")},
                              held=[("surf_kx", bsp("kx"))])
    tick(maps2, state2, "--go", "--max", "0")
    cat = json.load(io.open(os.path.join(state2, "catalogue.json"), encoding="utf-8"))
    check("control: the earlier run read both lists, and Momentum's names are on record",
          cat["momnames"], ["surf_late"])
    w2.down = {"mom"}
    lines(state2, "surf_late %s %s%s.bsp" % (sha(late["bsp"]), W.MOM_CDN, uuid_of("surf_late")))
    w2.asked = []
    tick(maps2, state2, "--go")
    check("with Momentum unread, a Beta line for a name it listed last time is still stale",
          (lib(maps2), w2.files()), (["surf_kx.bsp"], []))

    first = W.take_lock(state)
    second = W.take_lock(state)
    check("a second run cannot take the lock", (first is not None, second), (True, None))
    w.asked = []
    check("...and main beside it asks nothing", (tick(maps, state, "--go"), w.asked), (0, []))
    first.close()


def case_beta_zones():
    """P1093: a Beta line with an id and zoneHash gets the map's zones, and with
    --updates its build, but only while the map's own reply names that build."""
    def lines(st, *rows):
        os.makedirs(st, exist_ok=True)
        with io.open(os.path.join(st, "extra.tsv"), "w", newline="\n") as fh:
            fh.write("# name sha1 url id zoneHash\n")
            for r in rows:
                fh.write(r + "\n")

    def line(w, n, seed, zh=True):
        m = w.mom[n]
        z = sha(ztext(m["zones"]).encode()) if zh and m.get("zones") else "-"
        return "%s %s %s%s.bsp %d %s" % (n, sha(bsp(seed)), W.MOM_CDN, uuid_of(n), w.ids[n], z)

    # Held at the line's build, which the reply names: its zones are written.
    w, maps, state = setup({"surf_bz": M("bz")}, {}, held=[("surf_bz", bsp("bz"))])
    w.hidden = {"surf_bz"}
    lines(state, line(w, "surf_bz", "bz"))
    tick(maps, state, "--go")
    check("a held Beta map at its line's build gets the zones its own reply hashes to",
          (sha(zfile(maps, "surf_bz") or b""), w.files()),
          (sha(ztext(w.mom["surf_bz"]["zones"]).encode()), []))

    # The line names the held build, the reply a newer one: the line is stale.
    w, maps, state = setup({"surf_bs": M("bs new")}, {}, held=[("surf_bs", bsp("bs old"))])
    w.hidden = {"surf_bs"}
    lines(state, "surf_bs %s %s%s.bsp %d %s" % (sha(bsp("bs old")), W.MOM_CDN, uuid_of("surf_bs"),
                                                 w.ids["surf_bs"], "5" * 40))
    tick(maps, state, "--go", "--updates")
    check("...a stale line (the reply names another build) writes no zones and swaps nothing",
          (zlist(maps), sha(read(os.path.join(maps, "surf_bs.bsp"))), w.files(), strikes(state)),
          ([], sha(bsp("bs old")), [], []))

    # Held on an older build; the line and the reply both name the new one.
    w, maps, state = setup({"surf_bu": M("bu new")}, {}, held=[("surf_bu", bsp("bu old"))])
    w.hidden = {"surf_bu"}
    lines(state, line(w, "surf_bu", "bu new"))
    tick(maps, state, "--go")
    check("control: without --updates a held Beta build is left",
          (sha(read(os.path.join(maps, "surf_bu.bsp"))), w.files()), (sha(bsp("bu old")), []))
    tick(maps, state, "--go", "--updates")
    check("...with --updates it is replaced, with its zones, and the old build kept aside",
          (sha(read(os.path.join(maps, "surf_bu.bsp"))), sha(zfile(maps, "surf_bu") or b""),
           sorted(os.listdir(os.path.join(maps, ".old")))),
          (sha(bsp("bu new")), sha(ztext(w.mom["surf_bu"]["zones"]).encode()),
           ["surf_bu.%s.bsp" % sha(bsp("bu old"))[:12]]))

    # The line names a build the reply does not (newer than held, older than published).
    w, maps, state = setup({"surf_bm": M("bm now")}, {}, held=[("surf_bm", bsp("bm old"))])
    w.hidden = {"surf_bm"}
    lines(state, "surf_bm %s %s%s.bsp %d %s" % (sha(bsp("bm mid")), W.MOM_CDN, uuid_of("surf_bm"),
                                                 w.ids["surf_bm"],
                                                 sha(ztext(w.mom["surf_bm"]["zones"]).encode())))
    tick(maps, state, "--go", "--updates")
    check("...and not when the reply names another build than the line, zones hashing or not",
          (sha(read(os.path.join(maps, "surf_bm.bsp"))), w.files(), zlist(maps)),
          (sha(bsp("bm old")), [], []))

    # A new Beta name with an id is installed with its zones at once.
    w, maps, state = setup({"surf_bn": M("bn")}, {})
    w.hidden = {"surf_bn"}
    lines(state, line(w, "surf_bn", "bn"))
    tick(maps, state, "--go")
    check("a new Beta name with an id is installed with its zones",
          (lib(maps), sha(zfile(maps, "surf_bn") or b"")),
          (["surf_bn.bsp", "zones"], sha(ztext(w.mom["surf_bn"]["zones"]).encode())))

    st = os.path.join(tempfile.mkdtemp(prefix="extra-", dir=HOME))
    lines(st, "surf_ok %s %s%s.bsp 12 -" % ("a" * 40, W.MOM_CDN, uuid_of("surf_ok")),
          "surf_old %s %s%s.bsp" % ("b" * 40, W.MOM_CDN, uuid_of("surf_old")),
          "surf_id0 %s %s%s.bsp 0 %s" % ("c" * 40, W.MOM_CDN, uuid_of("surf_id0"), "d" * 40),
          "surf_idx %s %s%s.bsp 1e3 %s" % ("c" * 40, W.MOM_CDN, uuid_of("surf_idx"), "d" * 40),
          "surf_zh %s %s%s.bsp 9 %s" % ("c" * 40, W.MOM_CDN, uuid_of("surf_zh"), "d" * 39),
          "surf_four %s %s%s.bsp 9" % ("c" * 40, W.MOM_CDN, uuid_of("surf_four")))
    got, bad = W.extra_list(os.path.join(st, "extra.tsv"))
    check("extra.tsv: 3 or 5 fields; an id is a positive integer, a zoneHash 40 hex or -",
          (sorted(got), got["surf_ok"]["id"], got["surf_ok"]["zh"], got["surf_old"]["id"], bad),
          (["surf_ok", "surf_old"], 12, None, None, 4))


def case_mapscan():
    tools = os.path.join(os.path.dirname(HERE), "tools")
    if not os.path.exists(os.path.join(tools, "mapscan.py")):
        SKIPPED.append("mapscan's catalogue merge (no tools/ beside surfd/ here)")
        return
    sys.path.insert(0, tools)
    import mapscan
    ros = {"surf_a": ("surf", "km", "2", "2", "-"), "Bhop_X": ("bhop", "-", "-", "-", "-"),
           "surf_k": ("surf", "k", "3", "-", "3"), "surf_m": ("surf", "km", "4", "4", "2")}
    cat = {"surf_a": {"name": "surf_a", "mode": "surf", "src": "km", "mtier": 3, "ktier": 1},
           "surf_a_css": {"name": "surf_a_css", "mode": "surf", "src": "k", "ktier": 1, "of": "surf_a"},
           "bhop_x": {"name": "bhop_x", "mode": "bhop", "src": "m", "mtier": 4},
           "surf_k": {"name": "surf_k", "mode": "surf", "src": "k", "ktier": 9},
           "surf_new": {"name": "surf_new", "mode": "surf", "src": "k", "ktier": 5},
           "surf_beta": {"name": "surf_beta", "mode": "surf", "src": "b", "mtier": None},
           # a row that only CLAIMS to be another map's second build
           "surf_liar": {"name": "surf_liar", "mode": "surf", "src": "k", "ktier": 2, "of": "surf_m"},
           "surf_inj": {"name": "surf_inj", "mode": "bhop k 1000 2026-01-01 0 0 0\ndl ../../x",
                        "src": "k"},
           "surf_nl": {"name": "surf_nl\ndl evil surf k 1 1 2026-01-01 0 0 0", "mode": "surf", "src": "k"},
           "surf_num": {"name": 7, "mode": "surf", "src": "k"},
           "surf_tier": {"name": "surf_tier", "mode": "surf", "src": "k", "ktier": 10 ** 9,
                         "mtier": "3\n"},
           "junk": "not a dict"}
    added = mapscan.merge_catalogue(ros, cat)
    check("the Pi's catalogue adds the names the roster lacks, with their tiers",
          (added, ros["surf_new"], ros["surf_beta"], ros["surf_a_css"]),
          (5, ("surf", "k", "5", "-", "5"), ("surf", "m", "-", "-", "-"),
           ("surf", "k", "1", "-", "1")))
    check("a held tier is kept, a missing one filled, and the letters are joined",
          (ros["surf_a"][2:], ros["Bhop_X"], ros["surf_k"]),
          (("2", "2", "1"), ("bhop", "m", "4", "4", "-"), ("surf", "k", "3", "-", "3")))
    check("where KSF's build has its own row, the plain row is Momentum's alone -- and only "
          "a row named <name>_css can say so",
          (ros["surf_a"][1], ros["surf_m"][1]), ("m", "km"))
    check("...and it is recorded as a build of that map, for the list's tenth column",
          mapscan.VARIANT_OF, {"surf_a_css": "surf_a"})
    check("a row whose name or mode is not exactly one is not a row; a tier out of range is none",
          (sorted(n for n in ros if not isinstance(n, str) or "\n" in n or n in ("surf_inj", "surf_num")),
           ros["surf_tier"]), ([], ("surf", "k", "-", "-", "-")))


def main():
    for case in (case_plan_and_install, case_bad_files, case_page_scan, case_limits_on_a_reply,
                 case_turns_with_the_crawl, case_given_zones, case_map_list, case_kept_build,
                 case_unhashed_zones,
                 case_bad_names_and_shapes, case_hosts,
                 case_held_builds, case_first_zones, case_variants, case_zones_and_limits,
                 case_extra_and_lock, case_beta_zones, case_mapscan):
        print("\n%s:" % case.__name__)
        case()
    print()
    check("no reply was read without a size, in any case above", UNBOUNDED, [])
    check("no url was asked that the lists did not give, whole and unaltered", UNEXPECTED, [])
    print("\n%d failed%s" % (len(FAILED), (", skipped: " + "; ".join(SKIPPED)) if SKIPPED else ""))
    for f in FAILED:
        print("  " + f)
    return 1 if FAILED else 0


if __name__ == "__main__":
    raise SystemExit(main())
