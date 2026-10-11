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
import surfd as S        # noqa: E402
import mapwatch as W     # noqa: E402


@atexit.register
def _cleanup():
    logging.shutdown()      # the logger holds a file in HOME on Windows
    shutil.rmtree(HOME, ignore_errors=True)


W.MOM_TAKE = 2           # so the list pages
W.KSF_MIN = 1
W.MOM_MIN = 0            # the fixture worlds are a handful of maps
W.GET_DELAY = 0.0
W.FLOOR_GB = 0           # this box's free space is not under test (the Pi's /tmp has 4 GB)
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
          (True, b"{}", [], [("zones", "surf_zbad", 1, "zonehash")]))
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
          (len(w.zone_asks()), strikes(state)), (1, [("zones", "surf_zt", 1, "zonehash")]))
    w, maps, state = setup({"surf_u0": M("u0"), "surf_u1": M("u1")}, {})
    w.zonefix = {"surf_u0": '{"name":"\\ud800 half a character"}'}
    rc = tick(maps, state, "--go")
    check("zones that cannot even be written as bytes are that map's: struck, and the run goes on",
          (rc, zlist(maps), strikes(state)), (0, ["surf_u1.json"], [("zones", "surf_u0", 1, "zonehash")]))


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
    check("zones that do not hash to zoneHash are not written, and that is counted once",
          (zlist(maps), strikes(state)), (["surf_z1.json"], [("zones", "surf_z2", 1, "zonehash")]))
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
    check("a row whose name or mode is not exactly one is not a row; a tier out of range is none",
          (sorted(n for n in ros if not isinstance(n, str) or "\n" in n or n in ("surf_inj", "surf_num")),
           ros["surf_tier"]), ([], ("surf", "k", "-", "-", "-")))


def main():
    for case in (case_plan_and_install, case_bad_files, case_page_scan, case_limits_on_a_reply,
                 case_bad_names_and_shapes, case_hosts,
                 case_held_builds, case_first_zones, case_variants, case_zones_and_limits,
                 case_extra_and_lock, case_mapscan):
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
