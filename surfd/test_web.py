#!/usr/bin/env python3
"""
test_web.py -- the falsifier for the public web leaderboard (/board/).

    SURFD_HOME=/tmp/surfd-test python3 test_web.py

Every case imports surfd against a throwaway home, map library and zone dir
(set before the import: MAPS_DIR and ZONES_DIR are read once).  The library
holds a capitalised map, a BSP with no zone and a zone with no BSP, so the
maps list has to be (zoned AND bsp) OR runs, in the disk's spelling.
"""

import hashlib
import importlib
import json
import os
import re
import sqlite3
import sys
import tempfile
import threading

FAILED = []
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)


def check(label, got, want):
    ok = got == want
    print("%-4s %-62s %r" % ("ok" if ok else "FAIL", label, got))
    if not ok:
        FAILED.append("%s: got %r, want %r" % (label, got, want))


LIBRARY = ["surf_kitsune", "surf_lux", "Bhop_Mukiology", "bhop_eazy", "surf_nozone",
           "surf_localzone"]
ZONED = ["surf_kitsune", "surf_lux", "Bhop_Mukiology", "bhop_eazy", "surf_nobsp"]
# The game's own overrides, which sv_zones.qc reads first (66 maps on the Pi).
ZONED_LOCAL = ["surf_localzone"]


class FakeClock(object):
    def __init__(self, now=1800000000.0):
        self.now = float(now)

    def time(self):
        return self.now

    def monotonic(self):
        return self.now


def fresh(admin_hash=None):
    home = tempfile.mkdtemp(prefix="surfd-web-")
    with open(os.path.join(home, "surfd.env"), "w") as fh:
        fh.write("SURFD_KEY=testkey\n")
    maps = os.path.join(home, "maps")
    zones = os.path.join(maps, "zones", "online")
    os.makedirs(zones)
    for name in LIBRARY:
        open(os.path.join(maps, name + ".bsp"), "wb").close()
    for name in ZONED:
        open(os.path.join(zones, name + ".json"), "wb").close()
    zlocal = os.path.join(home, "zones_local")
    os.makedirs(zlocal)
    for name in ZONED_LOCAL:
        open(os.path.join(zlocal, name + ".json"), "wb").close()
    os.environ.update(SURFD_HOME=home, SURFD_DB=os.path.join(home, "test.db"),
                      SURFD_ENV=os.path.join(home, "surfd.env"),
                      SURFD_MAPS=maps, SURFD_ZONES=zones, SURFD_ZONES_LOCAL=zlocal,
                      SURFD_RUNS=os.path.join(home, "runs"),
                      SURFD_WEBSHOTS=os.path.join(home, "webshots"))
    os.makedirs(os.path.join(home, "webshots"))
    for k in ("SURFD_PUBLIC_HOST", "SURFD_TRUSTED", "SURFD_ADMIN_HASH",
              "SURFD_ADMIN_SECRET", "SURFD_ADMIN_INSECURE_COOKIE",
              "SURFD_RCON_PASSWORD", "SURFD_ADMIN_LOBBIES",
              "SURFD_MOMENTUM", "SURFD_MOMTRACKS"):
        os.environ.pop(k, None)
    if admin_hash:
        os.environ.update(SURFD_ADMIN_HASH=admin_hash,
                          SURFD_ADMIN_SECRET="s" * 48,
                          SURFD_ADMIN_INSECURE_COOKIE="1")
    for mod in ("surfd", "admin", "rcon"):
        sys.modules.pop(mod, None)
    m = importlib.import_module("surfd")
    m.time = FakeClock()
    m._test_db = os.environ["SURFD_DB"]
    return m


def get(m, path, ip=None, method="GET"):
    headers = {"X-Real-IP": ip} if ip else {}
    return m.app.test_client().open(path, method=method, headers=headers,
                                    environ_base={"REMOTE_ADDR": "127.0.0.1"})


def body(resp):
    return json.loads(resp.get_data(as_text=True))


def leaf(ticks, player):
    return "%07d_%s_run.rec" % (ticks, hashlib.sha256(player.encode()).hexdigest()[:8])


def submit(m, mapname, player, ticks, **kw):
    form = {"key": "testkey", "map": mapname, "track": "0", "leg": "0",
            "player": player, "name": player.capitalize(), "ticks": str(ticks),
            "tickrate": "100", "flags": "0", "node": "p27510",
            "rec": leaf(ticks, player)}
    form.update({k: str(v) for k, v in kw.items()})
    resp = m.app.test_client().post("/api/run", data=form,
                                    environ_base={"REMOTE_ADDR": "127.0.0.1"})
    return body(resp)


def api_board(m, mapname, **kw):
    args = {"map": mapname, "limit": "200"}
    args.update({k: str(v) for k, v in kw.items()})
    return body(m.app.test_client().get("/api/board", query_string=args,
                                        environ_base={"REMOTE_ADDR": "127.0.0.1"}))


# A .rec the run viewer can plot, CARRYING THE INTEGRITY KEYS ON PURPOSE: the
# head allowlist is only tested by a file that has something to leak.
REC_BODY = """FTESURF-REC 5
map %(map)s
track %(track)d
leg %(leg)d
startseg 0
tickrate 0.015
movetickrate 0.015
clock sampled
owner P1
runid r-0001
mapcrc 1234567890
zonesrc online
zonecrc 99887766
zonerule strict
instart 1
startjit 0
nonce deadbeefdeadbeefdeadbeefdeadbeef
pmpin trisoup=1 rotboxes=0 portalcsg=1
%(extra)sflags 0
begin
0.0000 100.00 200.00 300.00 250.00 0.00 0.00 0 0 0 0 0 0 0 0 0 0
0.0150 103.75 200.00 300.00 300.00 40.00 0.00 0 0 0 0 0 0 0 0 0 0
0.0300 108.25 200.60 300.00 420.00 -30.00 12.00 0 0 0 0 0 0 0 0 0 0
0.0450 114.55 200.15 300.20 505.00 15.00 -8.00 0 0 0 0 0 0 0 0 0 0
end 3 1 0 0 0
"""


def write_rec(m, kind, mapname, track, leg, name, momdemo=None):
    root = m.RUNS_DIR if kind == "run" else m.MOMENTUM_DIR
    d = os.path.join(root, mapname, m.leg_dir(track, leg))
    os.makedirs(d, exist_ok=True)
    path = os.path.join(d, name)
    with open(path, "w") as fh:
        # `momdemo` goes in the header block, before `begin` -- a recplot reader
        # stops at the body, so appending it to the end of the fixture would put it
        # where nothing reads it and the arm would silently measure its absence.
        fh.write(REC_BODY % {"map": mapname, "track": track, "leg": leg,
                             "extra": "momdemo %s\n" % momdemo if momdemo else ""})
    return path


def imported(m, mapname, player, name, ticks, tier, momdemo=None, track=0, leg=0,
             submitted=1800000000):
    """One imported row plus its replay, the way momindex/momboards file them."""
    conn = sqlite3.connect(m._test_db)
    lf = leaf(ticks, player)
    rid = 0
    if tier == "momentum":
        write_rec(m, "momentum", mapname, track, leg, lf, momdemo=momdemo)
        cur = conn.execute(
            "INSERT INTO replays (map, map_dir, track, leg, leaf, tier, style,"
            " player, name, ticks, tickrate, millis, flags, node, submitted,"
            " kind) VALUES (?,?,?,?,?,?,'clean',?,?,?,100.0,?,0,'import',?, "
            "'momentum')",
            (mapname, mapname, track, leg, lf, tier, player, name, ticks, ticks * 10,
             submitted))
        rid = cur.lastrowid
    conn.execute(
        "INSERT INTO runs (map, track, leg, tier, style, player, name, ticks,"
        " tickrate, millis, flags, node, runid, submitted, replay_id)"
        " VALUES (?,?,?,?,'clean',?,?,?,100.0,?,0,'import',?,?,?)",
        (mapname, track, leg, tier, player, name, ticks, ticks * 10, "i-" + player,
         submitted, rid))
    conn.commit()
    conn.close()
    m.people_reset()
    m.maps_reset()
    return rid


def unplottable(m, kind):
    """A replays row whose file was never written."""
    conn = sqlite3.connect(m._test_db)
    cur = conn.execute(
        "INSERT INTO replays (map, map_dir, track, leg, leaf, tier, style,"
        " player, name, ticks, tickrate, millis, flags, node, submitted, kind)"
        " VALUES ('bhop_eazy','bhop_eazy',0,0,?,'ranked','clean','p9','P9',"
        " 7777,100.0,77770,0,'p27510',1800000000,?)",
        (leaf(7777, "p9"), kind))
    rid = cur.lastrowid
    conn.commit()
    conn.close()
    return rid


def evidence_row(m):
    conn = sqlite3.connect(m._test_db)
    cur = conn.execute(
        "INSERT INTO replays (map, map_dir, track, leg, leaf, tier, style,"
        " player, name, ticks, tickrate, millis, flags, node, submitted, kind)"
        " VALUES ('bhop_eazy','bhop_eazy',0,0,'ev_0001.rec','ranked','clean',"
        " 'p1','P1',3000,100.0,30000,0,'p27510',1800000000,'evidence')")
    rid = cur.lastrowid
    conn.commit()
    conn.close()
    return rid


def community_row(m):
    conn = sqlite3.connect(m._test_db)
    lf = leaf(4100, "pc")
    cur = conn.execute(
        "INSERT INTO replays (map, map_dir, track, leg, leaf, tier, style,"
        " player, name, ticks, tickrate, millis, flags, node, submitted, kind)"
        " VALUES ('bhop_eazy','bhop_eazy',0,0,?,'community','clean','pc','Pc',"
        " 4100,100.0,41000,0,'p27510',1800000000,'run')", (lf,))
    rid = cur.lastrowid
    conn.commit()
    conn.close()
    write_rec(m, "run", "bhop_eazy", 0, 0, lf)
    return rid


def add_review(m, rid, decision):
    conn = sqlite3.connect(m._test_db)
    conn.execute("DELETE FROM reviews WHERE replay_id=?", (rid,))
    conn.execute("INSERT INTO reviews (replay_id, decision, note, at)"
                 " VALUES (?,?,'',?)", (rid, decision, 1900000000))
    conn.commit()
    conn.close()

def add_verdict(m, rid, verdict, at):
    conn = sqlite3.connect(m._test_db)
    conn.execute("INSERT INTO verdicts (replay_id, verdict, reason, ticks,"
                 " engine, progs, at) VALUES (?,?,'r',-1,'e','p',?)",
                 (rid, verdict, at))
    conn.commit()
    conn.close()


def new_worker(m):
    """Nothing in memory, as in a process that has just started."""
    with m._people_lock:
        m._people["at"], m._people["by_handle"], m._people["list"] = -1e9, {}, []


def join_rebuilds():
    for t in threading.enumerate():
        if t.name == "people":
            t.join(30)


def snapshot_temps(m):
    base = os.path.basename(m.PEOPLE_SNAPSHOT)
    return sorted(f for f in os.listdir(os.path.dirname(m.PEOPLE_SNAPSHOT))
                  if f.startswith(base + ".") and f.endswith(".tmp"))


def tally(fn, calls, key, hold=False):
    """fn, counting its calls.  `hold` keeps the first call open up to 1 s for a
    second to start, so any second call that is coming overlaps it."""
    lock, second = threading.Lock(), threading.Event()

    def wrapped(*a, **kw):
        with lock:
            calls[key] += 1
            first = calls[key] == 1
        if hold:
            if first:
                second.wait(1.0)
            else:
                second.set()
        return fn(*a, **kw)
    return wrapped


def together(m, path, n=4):
    """n requests for one path released at once; their status codes."""
    gate, codes = threading.Barrier(n), [None] * n

    def one(i):
        gate.wait()
        codes[i] = get(m, path).status_code
    ts = [threading.Thread(target=one, args=(i,)) for i in range(n)]
    for t in ts:
        t.start()
    for t in ts:
        t.join(30)
    return codes


class Shim(object):
    """A stand-in for one of surfd's module globals (`json`, `threading`) that
    defers to the real module for anything it does not override."""

    def __init__(self, real, **over):
        self._real = real
        self.__dict__.update(over)

    def __getattr__(self, name):
        return getattr(self._real, name)


def main():
    import admin
    pw_hash = admin.hash_password("pw", n=2 ** 10)

    # ---- 1. the page, its files and its headers ---------------------------
    print("\n--- 1. the page and its headers --")
    m = fresh(admin_hash=pw_hash)
    login = get(m, "/admin/login")
    check("control: the admin panel is on and its page sets a cookie",
          (login.status_code, "Set-Cookie" in login.headers), (200, True))
    r = get(m, "/board/")
    csp = r.headers.get("Content-Security-Policy", "")
    check("/board/ is 200 html", (r.status_code, r.mimetype), (200, "text/html"))
    check("...with the board CSP", csp, m.WEB_CSP)
    check("...which allows no inline script or style", "unsafe-inline" in csp, False)
    check("...and sets no cookie with the admin enabled", "Set-Cookie" in r.headers, False)
    check("...nosniff, referrer policy, no-cache",
          (r.headers.get("X-Content-Type-Options"), r.headers.get("Referrer-Policy"),
           r.headers.get("Cache-Control")),
          ("nosniff", "strict-origin-when-cross-origin", "no-cache"))
    etag = r.headers.get("ETag")
    r2 = m.app.test_client().get("/board/", headers={"If-None-Match": etag})
    check("...and revalidates to 304", r2.status_code, 304)
    for name, mime in (("board.js", "text/javascript"), ("board.css", "text/css")):
        r = get(m, "/board/" + name)
        check("/board/%s is 200 %s" % (name, mime), (r.status_code, r.mimetype), (200, mime))
    for path in ("/board/surfd.env", "/board/..%2fsurfd.py", "/board/board.html",
                 "/board/web/board.js", "/board/surfd.py"):
        r = get(m, path)
        check("%s is 404" % path, r.status_code, 404)
    check("...and a 404 still carries the CSP",
          get(m, "/board/surfd.env").headers.get("Content-Security-Policy"), m.WEB_CSP)
    r = get(m, "/board/api/maps")
    check("the API sets no cookie either", "Set-Cookie" in r.headers, False)

    absolute = re.compile(r"""["'(=]\s*/(board|ftesurf|api)\b""")
    check("control: the absolute-URL pattern matches one",
          bool(absolute.search("fetch('/board/api/maps')")), True)
    for name in ("board.html", "board.js"):
        with open(os.path.join(HERE, "web", name), encoding="utf-8") as fh:
            text = fh.read()
        check("no absolute board/site URL in %s" % name,
              [x.group(0) for x in absolute.finditer(text)], [])
    js = open(os.path.join(HERE, "web", "board.js"), encoding="utf-8").read()
    check("board.js never assigns innerHTML", "innerHTML" in js, False)
    rv = open(os.path.join(HERE, "web", "runview.js"), encoding="utf-8").read()
    check("runview.js is served",
          get(m, "/board/runview.js").status_code, 200)
    for name, src in (("board.js", js), ("runview.js", rv)):
        check("%s assigns no markup property" % name,
              [k for k in ("innerHTML", "outerHTML", "insertAdjacentHTML",
                           "document.write") if k in src], [])
    page = open(os.path.join(HERE, "web", "board.html"), encoding="utf-8").read()
    ids = set(re.findall(r'id="([^"]+)"', page))
    want = set(re.findall(r"\$\('([^']+)'\)", js))
    check("every id board.js reaches for is in the page", sorted(want - ids), [])
    check("control: the page declares ids and the script uses them",
          len(ids) > 20 and len(want) > 20, True)

    # ---- 2. the maps list ---------------------------------------------------
    print("\n--- 2. the maps list --")
    m = fresh()
    t0 = int(m.time.now)
    submit(m, "Bhop_Mukiology", "zed", 3000)
    submit(m, "Bhop_Mukiology", "amy", 3000)           # same second, same time
    submit(m, "Bhop_Mukiology", "bob", 3500)
    submit(m, "surf_nobsp", "cat", 4000)                # zoned, no BSP, has runs
    submit(m, "surf_ghost", "dan", 4000)                # neither, has runs
    submit(m, "surf_lux", "eli", 4000, tier="community")
    submit(m, "surf_commonly", "gus", 4000, tier="community")   # neither, community only
    rid = api_board(m, "bhop_mukiology")["rows"][0]["rep"]
    add_verdict(m, rid, "PASS", t0 + 5)
    b = body(get(m, "/board/api/maps"))
    got = {x["map"]: x for x in b["maps"]}
    check("maps = (zoned AND bsp) OR runs, in the disk spelling", sorted(got),
          sorted(["surf_kitsune", "surf_lux", "Bhop_Mukiology", "bhop_eazy",
                  "surf_nobsp", "surf_ghost", "surf_localzone"]))
    check("...a zone in the game's own local folder counts (surf_chaos_fix's case)",
          got["surf_localzone"]["have"], 1)
    check("control: a BSP without a zone and without runs is absent",
          "surf_nozone" in got, False)
    row1 = api_board(m, "bhop_mukiology")["rows"][0]
    check("the WR is /api/board's row 1, tie order included",
          got["Bhop_Mukiology"]["wr"],
          {"name": row1["name"], "ms": row1["ms"], "ver": row1["ver"]})
    check("...which is amy by the player tiebreak, verified",
          (row1["player"], row1["ver"]), ("amy", 1))
    check("runs and last count every board of the map",
          (got["Bhop_Mukiology"]["runs"], got["Bhop_Mukiology"]["last"]), (3, t0))
    check("community runs are not counted on the web",
          (got["surf_lux"]["runs"], got["surf_lux"]["wr"]), (0, None))
    check("...and a map with only community runs is not listed",
          "surf_commonly" in got, False)
    check("an untimed zoned map reads 0 runs, no WR",
          (got["surf_kitsune"]["runs"], got["surf_kitsune"]["wr"]), (0, None))
    text = get(m, "/board/api/maps").get_data(as_text=True)
    check("no player ids in the maps body",
          [p for p in ("zed", "amy", "bob") if '"%s"' % p in text], [])

    # ---- 3. the maps cache --------------------------------------------------
    print("\n--- 3. the maps cache --")
    m = fresh()
    first = get(m, "/board/api/maps")
    check("maps are cacheable for 60 s", first.headers.get("Cache-Control"), "max-age=60")
    submit(m, "surf_kitsune", "fay", 5000)
    m.time.now += 59
    kit = lambda: {x["map"]: x for x in body(get(m, "/board/api/maps"))["maps"]}["surf_kitsune"]["runs"]
    check("within 60 s the list is the cached one", kit(), 0)
    m.time.now += 2
    check("control: after 60 s the new run shows", kit(), 1)

    # ---- 4. one map ---------------------------------------------------------
    print("\n--- 4. one map --")
    m = fresh()
    submit(m, "bhop_eazy", "p1", 3000)
    submit(m, "bhop_eazy", "p2", 3200)
    submit(m, "bhop_eazy", "p3", 2900, tier="community")
    submit(m, "bhop_eazy", "p1", 900, leg=2)
    submit(m, "bhop_eazy", "p4", 1500, track=1)
    b = body(get(m, "/board/api/map?map=bhop_eazy"))
    check("the board list is ranked only, in order",
          [(x["track"], x["leg"], x["style"], x["n"]) for x in b["boards"]],
          [(0, 0, "clean", 2), (0, 2, "clean", 1), (1, 0, "clean", 1)])
    check("no board entry names a tier", ["tier" in x for x in b["boards"]],
          [False, False, False])
    check("...and the body names the tier it served", b["tier"], "ranked")
    check("no parameters open main clean",
          (b["track"], b["leg"], b["style"]), (0, 0, "clean"))
    want = [dict((k, v) for k, v in x.items() if k != "player")
            for x in api_board(m, "bhop_eazy")["rows"]]
    got = [dict((k, v) for k, v in x.items() if k not in ("who", "ext"))
           for x in b["rows"]]
    check("rows are /api/board's rows minus player", got, want)
    check("...and name no player", any("player" in x for x in b["rows"]), False)
    check("...and carry a handle that is not the guid",
          [x["who"] == "p1" or x["who"] == "p2" for x in b["rows"]], [False, False])
    check("...which is web_handle of it",
          [x["who"] for x in b["rows"]],
          [m.web_handle("p1"), m.web_handle("p2")])
    check("a ranked row never carries an outbound id",
          [x["ext"] for x in b["rows"]], [None, None])
    check("ranked count, offset and page size",
          (b["n"], b["offset"], b["limit"]), (2, 0, 50))
    check("control: the community run is on the ranked board nowhere",
          [x["name"] for x in b["rows"]], ["P1", "P2"])
    b = body(get(m, "/board/api/map?map=bhop_eazy&track=0&leg=2&tier=ranked&style=clean"))
    check("explicit parameters pick that board",
          ([x["name"] for x in b["rows"]], b["leg"]), (["P1"], 2))
    b = body(get(m, "/board/api/map?map=bhop_eazy&style=segmented"))
    check("an empty board is 200 with no rows", (b["rows"], b["n"]), ([], 0))
    b = body(get(m, "/board/api/map?map=bhop_eazy&track=0&leg=0&style=clean&tier=community"))
    check("an old link's tier=community still opens the ranked board",
          [x["name"] for x in b["rows"]], ["P1", "P2"])

    submit(m, "surf_lux", "c1", 3000, tier="community")
    b = body(get(m, "/board/api/map?map=surf_lux"))
    check("a zoned map with only community runs shows no board and no rows",
          (b["boards"], b["rows"], b["style"]), ([], [], "clean"))
    submit(m, "surf_kitsune", "s1", 3000, flags=128)          # TF_SEGMENT
    b = body(get(m, "/board/api/map?map=surf_kitsune"))
    check("default falls to segmented", b["style"], "segmented")
    submit(m, "surf_nobsp", "q1", 3000, leg=3)
    b = body(get(m, "/board/api/map?map=surf_nobsp"))
    check("...then the first board in the list",
          (b["track"], b["leg"], b["style"]), (0, 3, "clean"))

    submit(m, "Bhop_Mukiology", "m1", 3000)
    b = body(get(m, "/board/api/map?map=BHOP_MUKIOLOGY"))
    check("the key is lowercase, disp the disk spelling",
          (b["map"], b["disp"]), ("bhop_mukiology", "Bhop_Mukiology"))
    b = get(m, "/board/api/map?map=surf_lux&tier=ranked")
    check("a map view is cacheable for 15 s", b.headers.get("Cache-Control"), "max-age=15")

    m2 = fresh()
    b = get(m2, "/board/api/map?map=surf_kitsune")
    check("a zoned map with no runs is 200 and empty",
          (b.status_code, body(b)["boards"], body(b)["rows"]), (200, [], []))
    for label, path, code in (
            ("an unknown map", "/board/api/map?map=surf_nothing", 404),
            ("a BSP with no zone and no runs", "/board/api/map?map=surf_nozone", 404),
            ("no map", "/board/api/map", 400),
            ("a map with a slash", "/board/api/map?map=a/b", 400),
            ("an ignored tier", "/board/api/map?map=surf_kitsune&tier=elite", 200),
            ("a bad style", "/board/api/map?map=surf_lux&style=free", 400),
            ("a negative track", "/board/api/map?map=surf_lux&track=-1", 400),
            ("a word for a leg", "/board/api/map?map=surf_lux&leg=x", 400)):
        check("%s is %d" % (label, code), get(m2, path).status_code, code)

    m3 = fresh()
    for i in range(55):
        submit(m3, "bhop_eazy", "r%02d" % i, 1000 + i)
    p1 = body(get(m3, "/board/api/map?map=bhop_eazy"))
    p2 = body(get(m3, "/board/api/map?map=bhop_eazy&track=0&leg=0&tier=ranked"
                      "&style=clean&offset=50"))
    check("paging: 50, then the last 5 ranked 51..55",
          (len(p1["rows"]), [x["r"] for x in p2["rows"]]), (50, [51, 52, 53, 54, 55]))

    # ---- 5. the rate bucket -------------------------------------------------
    print("\n--- 5. the rate bucket --")
    m = fresh()
    codes = [get(m, "/board/api/maps", ip="198.51.100.7").status_code
             for _ in range(m.WEB_RATE_MAX)]
    check("WEB_RATE_MAX requests pass", codes.count(200), m.WEB_RATE_MAX)
    r = get(m, "/board/api/maps", ip="198.51.100.7")
    check("...and the next is 429", r.status_code, 429)
    check("...still with the board headers",
          r.headers.get("Content-Security-Policy"), m.WEB_CSP)
    check("...and the map route shares the bucket",
          get(m, "/board/api/map?map=surf_lux", ip="198.51.100.7").status_code, 429)
    check("another address is unaffected",
          get(m, "/board/api/maps", ip="198.51.100.8").status_code, 200)
    check("/api/board's bucket is unaffected",
          get(m, "/api/board?map=surf_lux", ip="198.51.100.7").status_code, 200)
    check("the page itself is not in the bucket",
          get(m, "/board/", ip="198.51.100.7").status_code, 200)
    check("POST to the API is 405", get(m, "/board/api/maps", method="POST").status_code, 405)
    check("POST to the page is 405", get(m, "/board/", method="POST").status_code, 405)


    # ---- 6. the public handle, the imported boards, profiles, the run view --
    print("\n--- 6. the public player surface --")
    m = fresh()
    check("control: a handle is 12 hex of sha256 and not the guid",
          (m.web_handle("p1"),
           hashlib.sha256(b"p1").hexdigest()[:12], len(m.web_handle("p1"))),
          (hashlib.sha256(b"p1").hexdigest()[:12],
           hashlib.sha256(b"p1").hexdigest()[:12], 12))
    check("two players, two handles", m.web_handle("p1") == m.web_handle("p2"), False)
    check("an imported row's outbound id is its steamid",
          m.web_ext("momentum", "76561198064721002"), "76561198064721002")
    check("...a ranked row's is nothing, whatever the value looks like",
          m.web_ext("ranked", "76561198064721002"), None)
    check("...and a non-numeric imported player is not published either",
          m.web_ext("momentum", "9fb676fd2622ef8835cf51dfedcdfcae"), None)

    submit(m, "bhop_eazy", "p1", 3000)            # ours: 30.000
    submit(m, "bhop_eazy", "p2", 3400)
    imported(m, "bhop_eazy", "76561198000000001", "MomOne", 2800, "momentum")
    imported(m, "bhop_eazy", "76561198000000002", "MomTwo", 3200, "momentum")
    imported(m, "bhop_eazy", "76561198000000003", "KsfOne", 2900, "ksf")

    r = body(get(m, "/board/api/map?map=bhop_eazy"))
    check("THE INVARIANT: the ranked board is untouched by the imports",
          ([x["name"] for x in r["rows"]], r["n"]), (["P1", "P2"], 2))
    i = body(get(m, "/board/api/map?map=bhop_eazy&tier=imported"))
    check("the imported board carries both sources, by time",
          [(x["name"], x["tr"]) for x in i["rows"]],
          [("MomOne", "momentum"), ("KsfOne", "ksf"), ("MomTwo", "momentum")])
    check("...and its count is both tiers", i["n"], 3)
    check("...and each row names its source's player publicly",
          [x["ext"] for x in i["rows"]],
          ["76561198000000001", "76561198000000003", "76561198000000002"])
    c = body(get(m, "/board/api/map?map=bhop_eazy&tier=combined"))
    # 28.000, 29.000, 30.000, 32.000, 34.000 -- ours lands third, which is the
    # whole point of the view and was worth getting wrong once to be sure of.
    check("the combined board interleaves ours with theirs",
          [x["name"] for x in c["rows"]],
          ["MomOne", "KsfOne", "P1", "MomTwo", "P2"])
    check("...and counts every readable tier", c["n"], 5)
    check("the per-tier counts are all reported",
          (c["counts"]["ranked"], c["counts"]["momentum"], c["counts"]["ksf"]),
          (2, 2, 1))
    check("the leg tabs count imported rows too",
          [(x["track"], x["leg"], x["n"], x["ni"]) for x in c["boards"]],
          [(0, 0, 2, 3)])
    check("no board response ever names a player id",
          "player" in json.dumps(c), False)

    # An imported-only map is listed and marked unplayable rather than hidden.
    imported(m, "surf_gone", "76561198000000004", "MomThree", 4000, "momentum")
    mp = {x["map"]: x for x in body(get(m, "/board/api/maps"))["maps"]}
    check("a map we hold only imported times for is listed",
          ("surf_gone" in mp, mp.get("surf_gone", {}).get("have")), (True, 0))
    check("...and a zoned installed map says it is playable",
          mp["bhop_eazy"]["have"], 1)
    check("the maps list carries imported counts",
          (mp["bhop_eazy"]["imp"], mp["bhop_eazy"]["runs"]), (3, 2))

    # ---- search ------------------------------------------------------------
    s = body(get(m, "/board/api/players"))
    check("every player is searchable", s["n"], 6)
    # NOT `"player" in json.dumps(...)`: the key is spelled "players" and that
    # check passes on its own substring.  Look for the guids themselves.
    blob = json.dumps(s)
    check("...with no guid in the body",
          [g for g in ("p1", "p2", "76561198000000001") if '"' + g + '"' in blob],
          [])
    check("...and handles that round-trip",
          sorted(x["who"] for x in s["players"]) ==
          sorted(m.web_handle(p) for p in ("p1", "p2", "76561198000000001",
                                           "76561198000000002",
                                           "76561198000000003",
                                           "76561198000000004")), True)
    s = body(get(m, "/board/api/players?q=momo"))
    check("a search matches case-insensitively",
          sorted(x["name"] for x in s["players"]), ["MomOne"])
    s = body(get(m, "/board/api/players?q=nobody"))
    check("...and a miss is 200 with nothing", (s["n"], s["players"]), (0, []))

    # A colour-coded name must match the plain text the page renders.
    imported(m, "bhop_eazy", "76561198000000005", "^1Red^7Shift", 5000, "momentum")
    m.people_reset()
    s = body(get(m, "/board/api/players?q=redshift"))
    check("a search sees through Quake colour codes",
          [x["name"] for x in s["players"]], ["^1Red^7Shift"])

    # ---- one profile -------------------------------------------------------
    h1 = m.web_handle("p1")
    p = body(get(m, "/board/api/player/" + h1))
    check("a profile counts its rows and maps",
          (p["name"], p["n"], p["maps"]), ("P1", 1, 1))
    check("...names the handle and not the guid",
          (p["who"], "player" in json.dumps(p)), (h1, False))
    check("...and publishes no outbound id for one of ours", p["ext"], None)
    pm = body(get(m, "/board/api/player/" + m.web_handle("76561198000000001")))
    check("an imported profile does publish one",
          (pm["name"], pm["ext"], pm["src"]),
          ("MomOne", "76561198000000001", "momentum"))
    check("...and counts its records", pm["wr"], 1)

    # A FIRST PLACE ON A BOARD OF ONE IS NOT A RECORD.  MomThree is alone on
    # surf_gone, so its rank 1 counts in `wr` and must not count in `wrc` --
    # on a real imported profile that distinction was 35 against 0.
    p3 = body(get(m, "/board/api/player/" + m.web_handle("76561198000000004")))
    check("an uncontested first place is not a contested record",
          (p3["wr"], p3["wrc"]), (1, 0))
    check("...while a contested one is", (pm["wr"], pm["wrc"]), (1, 1))

    # "BEST FIRST" IS PEOPLE BEATEN, not placing and not board size.  Three
    # boards, because the fixture has to reject both wrong answers: ordering by
    # rank leads with the lone first, ordering by board size leads with DEAD
    # LAST on the biggest board.  Both were tried against real data and both
    # put nonsense at the top.
    ME = "76561198000000009"
    imported(m, "surf_busy", ME, "Mid", 4500, "momentum")
    for k in range(4):
        imported(m, "surf_busy", "76561198000001%03d" % k, "F%d" % k,
                 4000 + k * 10, "momentum")
        imported(m, "surf_busy", "76561198000002%03d" % k, "S%d" % k,
                 5000 + k * 10, "momentum")
    imported(m, "surf_alone", ME, "Mid", 9000, "momentum")
    imported(m, "surf_huge", ME, "Mid", 9000, "momentum")
    for k in range(19):
        imported(m, "surf_huge", "76561198000003%03d" % k, "H%d" % k,
                 3000 + k * 10, "momentum")
    m.people_reset()
    pr = body(get(m, "/board/api/player/" + m.web_handle(ME)))
    got = [(x["disp"], x["r"], x["of"]) for x in pr["rows"]]
    check("control: the fixture is the three shapes it claims to be",
          sorted(got), [("surf_alone", 1, 1), ("surf_busy", 5, 9),
                        ("surf_huge", 20, 20)])
    check("best-first leads with the row that beat the most people",
          got[0], ("surf_busy", 5, 9))
    check("...and neither of the two wrong orderings survives it",
          (got[0][0] != "surf_alone", got[0][0] != "surf_huge"), (True, True))

    # THE ARM THAT MATTERS: the profile ranks each row with rank_of (two
    # counts over the board index); the reference here is a window over
    # BOARD_ORDER, the query the profile ran until 5 Oct (52.8 s on the Pi for
    # one profile).  Two spellings of one rule, made to agree on the same rows
    # /api/board pages, imported tiers and a tie included.
    imported(m, "surf_busy", "76561198000000008", "Tie", 4500, "momentum",
             submitted=1800000000)
    conn = sqlite3.connect(m._test_db)
    conn.row_factory = sqlite3.Row
    ref = {}
    for r in conn.execute(
            "SELECT map, track, leg, tier, style, player, ROW_NUMBER() OVER"
            " (PARTITION BY map, track, leg, tier, style ORDER BY " + m.BOARD_ORDER
            + ") AS rk, COUNT(*) OVER (PARTITION BY map, track, leg, tier, style)"
            " AS of FROM runs"):
        ref[(r["map"], r["track"], r["leg"], r["tier"], r["style"], r["player"])] = (
            r["rk"], r["of"])
    conn.close()
    disagree, seen = [], 0
    for who in ("p1", "p2", "76561198000000001", "76561198000000002",
                "76561198000000003", ME, "76561198000000008"):
        pr = body(get(m, "/board/api/player/" + m.web_handle(who)))
        for row in pr["rows"]:
            seen += 1
            want = ref[(row["map"], row["track"], row["leg"], row["tr"],
                        row["style"], who)]
            if (row["r"], row["of"]) != want:
                disagree.append((who, row["map"], row["r"], row["of"], want))
    check("profile rank agrees with the window over BOARD_ORDER on every row",
          (disagree, seen > 8), ([], True))

    # MAIN TRACKS LEAD, then bonuses, then stages (Lex, 5 Oct): by people beaten
    # alone a stage board outranks its own map's main board.
    ST = "76561198000000077"
    imported(m, "surf_busy", ST, "Stager", 4990, "momentum")
    for k in range(30):
        imported(m, "surf_busy", "76561198000006%03d" % k, "S%d" % k, 6000 + k,
                 "momentum", leg=1)
    imported(m, "surf_busy", ST, "Stager", 5500, "momentum", leg=1)
    imported(m, "surf_busy", ST, "Stager", 7000, "momentum", track=1)
    ps = body(get(m, "/board/api/player/" + m.web_handle(ST)))
    got = [(x["track"], x["leg"], x["r"], x["of"]) for x in ps["rows"]]
    check("control: the stage row beat more people than the main row",
          (got[2][3] - got[2][2]) > (got[0][3] - got[0][2]), True)
    check("main first, then bonuses, then stages",
          [(t, l) for t, l, _r, _o in got], [(0, 0), (1, 0), (0, 1)])

    # Outbound ids: Steam for an imported player, KSF's STEAM_0 form only when
    # they hold KSF rows, and nothing for one of ours.
    KS = "76561197960265733"           # STEAM_0:1:2
    imported(m, "surf_busy", KS, "Kay", 4800, "ksf")
    pk = body(get(m, "/board/api/player/" + m.web_handle(KS)))
    check("a KSF player gets their KSF id", (pk["ext"], pk["ksfid"]), (KS, "STEAM_0:1:2"))
    check("...a Momentum-only player gets Steam and no KSF id",
          (ps["ext"], ps["ksfid"]), (ST, None))
    check("...and one of ours gets neither",
          (p["ext"], p["ksfid"]), (None, None))

    # THE DIRECTORY IS NEVER BUILT ON A REQUEST'S CLOCK once one exists: a build
    # is 6 s on the Pi and nginx gives the request 5.  A stale one is served
    # while a thread rebuilds it; a new process starts from the snapshot.
    builds = []
    real_build = m._people_build

    def counted(db):
        builds.append(1)
        return real_build(db)

    m._people_build = counted
    try:
        get(m, "/board/api/players")              # fresh: no build
        n0 = len(builds)
        m.time.now += m.WEB_PEOPLE_TTL + 1
        started = []
        real_kick = m._people_kick
        m._people_kick = lambda now: started.append(now)
        r = get(m, "/board/api/players")
        check("a stale directory is served at once, the rebuild started behind it",
              (r.status_code, len(builds) - n0, len(started)), (200, 0, 1))
        m._people_kick = real_kick
        check("control: the snapshot exists", os.path.exists(m.PEOPLE_SNAPSHOT), True)
        with m._people_lock:                      # a new worker: nothing in memory
            m._people["at"], m._people["by_handle"], m._people["list"] = -1e9, {}, []
        m.time.now -= m.WEB_PEOPLE_TTL + 1
        n1 = len(builds)
        r = get(m, "/board/api/player/" + h1)
        check("...a new process starts from the snapshot without a build",
              (r.status_code, len(builds) - n1), (200, 0))
        m.people_reset()
        check("people_reset removes the snapshot", os.path.exists(m.PEOPLE_SNAPSHOT), False)
        n2 = len(builds)
        get(m, "/board/api/players")
        check("...so the next request builds, as on a fresh install", len(builds) - n2, 1)
    finally:
        m._people_build = real_build

    check("an unknown handle is 404",
          get(m, "/board/api/player/" + "0" * 12).status_code, 404)
    check("a malformed handle is 400",
          get(m, "/board/api/player/nothex").status_code, 400)
    check("...and one with a slash never reaches the route",
          get(m, "/board/api/player/a/b").status_code, 404)

    # ---- completion, and the catalogue that is not there --------------------
    check("no catalogue means completion is UNKNOWN, not zero",
          body(get(m, "/board/api/player/" + h1))["completion"], None)
    check("...and the maps list says the tiers are missing",
          body(get(m, "/board/api/maps"))["tiers"], False)
    tsv = os.path.join(os.environ["SURFD_HOME"], "momtracks.tsv")
    with open(tsv, "w") as fh:
        fh.write("# map\tmapid\ttier\tgamemode\ttrackType\ttrackNum\n")
        fh.write("bhop_eazy\t1\t2\t2\t0\t1\n")
        fh.write("bhop_eazy\t1\t2\t2\t1\t1\n")        # a repeat, one map
        fh.write("surf_lux\t2\t5\t1\t0\t1\n")
        fh.write("surf_kitsune\t3\t2\t1\t0\t1\n")
        fh.write("surf_gone\t4\t0\t1\t0\t1\n")         # unrated: tier 0
    os.environ["SURFD_MOMTRACKS"] = tsv
    m.MOMTRACKS_PATH = tsv
    m.people_reset()
    p = body(get(m, "/board/api/player/" + h1))
    comp = p["completion"]
    check("with a catalogue, completion is a table",
          [(x["tier"], x["done"], x["of"]) for x in comp["tiers"]],
          [(2, 1, 2), (5, 0, 1)])
    check("...an unrated map is counted as untiered, not as tier 0",
          comp["untiered"] >= 1, True)
    check("...and the overall figure is maps, not rows",
          (comp["done"], comp["of"] >= 5), (1, True))
    m.time.now += m.WEB_MAPS_TTL + 1       # the maps body is cached for a minute
    check("the maps list now reports a difficulty",
          {x["map"]: x.get("mt") for x in body(get(m, "/board/api/maps"))["maps"]}
          .get("bhop_eazy"), 2)

    # ---- the run viewer ----------------------------------------------------
    print("\n--- 6b. the run viewer --")
    m = fresh()
    submit(m, "bhop_eazy", "p1", 3000)
    rid = body(get(m, "/board/api/map?map=bhop_eazy"))["rows"][0]["rep"]
    check("control: the ranked row names a replay", rid > 0, True)
    write_rec(m, "run", "bhop_eazy", 0, 0, leaf(3000, "p1"))
    r = body(get(m, "/board/api/run/%d" % rid))
    check("a run plots", (r["n"], len(r["x"]), len(r["spd"])), (4, 4, 4))
    check("...with the board's own identity on it",
          (r["map"], r["ms"], r["name"], r["who"]),
          ("bhop_eazy", 30000, "P1", m.web_handle("p1")))
    check("...and stats it computed, not ones we sent",
          r["stats"]["max_speed"] > 0, True)

    # THE SECURITY ARM.  The fixture .rec CONTAINS mapcrc, zonecrc, zonerule,
    # nonce and pmpin -- so a head that leaked them would leak them here, and
    # this check fails if the allowlist is ever turned into a blocklist.
    # ...intersected with what the file actually states: a ranked recording has no
    # `momdemo` and must not grow an empty one, or the run page's wording branch
    # would key on a key that is always present.
    check("the head carries only WEB_HEAD_KEYS, and only the ones the file states",
          sorted(r["head"]),
          sorted(k for k in m.WEB_HEAD_KEYS if k in ("map", "track", "leg",
                                                     "startseg", "tickrate",
                                                     "movetickrate", "clock",
                                                     "flags")))
    leaked = [k for k in ("mapcrc", "zonecrc", "zonerule", "nonce", "pmpin",
                          "zonesrc", "instart", "startjit", "owner", "runid")
              if k in json.dumps(r)]
    check("...and no integrity key reaches the browser", leaked, [])

    # `momdemo` IS in WEB_HEAD_KEYS, and these two arms are why that is safe
    # rather than an oversight: it is the only key the run page needs, it is a
    # hash of a public demo rather than a secret, and every key that must stay
    # private is named explicitly in the check above rather than inferred from
    # the allowlist being short.
    check("control: a ranked run's file carries no momdemo, so the head has none",
          "momdemo" in r["head"], False)

    m = fresh()
    DEMO = "e9a68559a40f01840828fc3dffe01c9a7a4d3fe6"
    imported(m, "bhop_eazy", "76561198000000009", "FromDemo", 4100,
             "momentum", momdemo=DEMO)
    imported(m, "bhop_eazy", "76561198000000010", "FromPos", 4200, "momentum")
    rows = {x["name"]: x for x in
            body(get(m, "/board/api/map?map=bhop_eazy&tier=imported"))["rows"]}
    check("control: both imported rows are on the board",
          sorted(rows), ["FromDemo", "FromPos"])

    # THE WORDING ARM.  The page used to call every imported path "derived",
    # which was true of the position-difference import and stopped being true
    # when tools/momreimport.py rewrote 5260 of the 5281 runs from their own
    # demos.  `momdemo` is the key that tells them apart, and 21 files really do
    # lack it -- so both branches are live, not one branch and a dead default.
    rd = body(get(m, "/board/api/run/%d" % rows["FromDemo"]["rep"]))
    rp = body(get(m, "/board/api/run/%d" % rows["FromPos"]["rep"]))
    check("an import written from its own demo publishes the demo hash",
          rd["head"].get("momdemo"), DEMO)
    check("...and one derived from positions publishes nothing",
          "momdemo" in rp["head"], False)
    check("both still plot, so the page can tell them apart",
          (rd["n"], rp["n"]), (4, 4))
    check("neither leaked an integrity key on the way",
          [k for k in ("mapcrc", "nonce", "pmpin", "zonerule", "runid")
           if k in json.dumps(rd) + json.dumps(rp)], [])

    check("an unknown run is 404", get(m, "/board/api/run/99999").status_code, 404)
    check("a run whose file is gone is 404",
          get(m, "/board/api/run/%d" % unplottable(m, "run")).status_code, 404)
    check("an EVIDENCE row is never public",
          get(m, "/board/api/run/%d" % evidence_row(m)).status_code, 404)
    check("a community run's path is never public",
          get(m, "/board/api/run/%d" % community_row(m)).status_code, 404)
    add_review(m, rid, "reject")
    check("a rejected run drops off the viewer with the board",
          get(m, "/board/api/run/%d" % rid).status_code, 404)
    add_review(m, rid, "approve")
    check("control: approving it back makes it viewable again",
          get(m, "/board/api/run/%d" % rid).status_code, 200)

    m = fresh()
    submit(m, "bhop_eazy", "p1", 3000)
    write_rec(m, "run", "bhop_eazy", 0, 0, leaf(3000, "p1"))
    rid = body(get(m, "/board/api/map?map=bhop_eazy"))["rows"][0]["rep"]
    codes = [get(m, "/board/api/run/%d" % rid, ip="198.51.100.9").status_code
             for _ in range(m.WEB_RUN_MAX + 1)]
    check("the run viewer has its own bucket",
          (codes.count(200), codes[-1]), (m.WEB_RUN_MAX, 429))
    check("...which does not close the board",
          get(m, "/board/api/maps", ip="198.51.100.9").status_code, 200)

    print("\n--- 6c. the map screenshot ---------------------------------------")
    # The name in the URL is a board key run through clean_map, and what comes
    # back is joined to one directory. These arms exist because that is the only
    # thing standing between a public GET and the filesystem: /board/<name> has
    # a filename allowlist to fall back on and this route cannot have one.
    m = fresh()
    shots = os.environ["SURFD_WEBSHOTS"]
    with open(os.path.join(shots, "surf_kitsune.jpg"), "wb") as fh:
        fh.write(b"\xff\xd8\xff\xe0JFIF-not-really")
    # A file the route must never reach, one directory up from the shot dir.
    with open(os.path.join(os.path.dirname(shots), "secret.jpg"), "wb") as fh:
        fh.write(b"NOT-FOR-THE-PUBLIC")

    r = get(m, "/board/shot/surf_kitsune")
    check("a map with a picture serves it",
          (r.status_code, r.mimetype), (200, "image/jpeg"))
    check("...and it is the file on disk",
          r.get_data(), b"\xff\xd8\xff\xe0JFIF-not-really")
    check("a map with no picture is 404, with no placeholder",
          get(m, "/board/shot/surf_lux").status_code, 404)

    # Every one of these is a path clean_map must refuse. The encoded forms
    # matter separately: Flask decodes %2f before the view ever sees it, so
    # the string clean_map is handed really can contain a separator.
    walks = ["../secret", "..%2fsecret", "....//secret",
             "%2e%2e%2fsecret", "/etc/passwd", "surf_kitsune/../../secret",
             "..\\secret", "surf_kitsune.jpg"]
    codes = sorted({get(m, "/board/shot/" + w).status_code for w in walks})
    check("no traversal reaches a file outside the shot directory",
          codes, [404])
    leaked = [w for w in walks
              if b"NOT-FOR-THE-PUBLIC" in get(m, "/board/shot/" + w).get_data()]
    check("control: none of them returned the file one level up", leaked, [])
    check("control: that file really is there and readable",
          open(os.path.join(os.path.dirname(shots), "secret.jpg"), "rb").read(),
          b"NOT-FOR-THE-PUBLIC")

    codes = [get(m, "/board/shot/surf_kitsune", ip="198.51.100.7").status_code
             for _ in range(m.WEB_SHOT_MAX + 1)]
    check("pictures have their own bucket",
          (codes.count(200), codes[-1]), (m.WEB_SHOT_MAX, 429))
    check("...which does not close the board",
          get(m, "/board/api/maps", ip="198.51.100.7").status_code, 200)

    print("\n--- 6d. the map want-queue ---------------------------------------")
    # A write hung off a public read, which is the only one in this file. What
    # matters is not that it counts, but that it counts ONLY maps the route has
    # already agreed exist -- otherwise a stranger picks what our cron asks
    # somebody else's API about, which is the whole thing the queue exists to
    # avoid.
    m = fresh()

    def wants(mod):
        c = mod.connect()
        try:
            return {r["map"]: r["asked"]
                    for r in c.execute("SELECT map, asked FROM mapwant")}
        finally:
            c.close()

    check("a fresh database has an empty queue", wants(m), {})
    get(m, "/board/api/map?map=bhop_eazy")
    check("viewing a map queues it", wants(m), {"bhop_eazy": 1})
    get(m, "/board/api/map?map=bhop_eazy")
    get(m, "/board/api/map?map=bhop_eazy")
    check("viewing it again counts rather than duplicating",
          wants(m), {"bhop_eazy": 3})

    # THE ARM THAT MATTERS. Each of these is refused by the route, so none may
    # reach the queue -- a 404 that still queued would let anyone fill it.
    for bad in ("surf_does_not_exist", "../../etc/passwd", "", "%2e%2e",
                "surf_kitsune.jpg"):
        get(m, "/board/api/map?map=" + bad)
    check("a map the route refuses is never queued", wants(m), {"bhop_eazy": 3})

    # And it must not be able to fail the page it hangs off. The table is
    # dropped from under the live connection, so the INSERT raises for real
    # rather than being skipped by a flag.
    c = m.connect()
    c.execute("DROP TABLE mapwant")
    c.commit()
    c.close()
    check("a broken queue does not break the board",
          get(m, "/board/api/map?map=bhop_eazy").status_code, 200)

    print("\n--- 6e. the player directory: writers, cold starts, clock steps, paging --")
    # TWO SAVES AT ONCE (two threads, or the old and new worker in a reload),
    # held at a barrier with their temp files open; the longer payload lands
    # first, the shorter second.  Through one shared temp name that left the
    # short one over the long one's head, and that file was installed.
    m = fresh()
    submit(m, "bhop_eazy", "p1", 3000)
    submit(m, "bhop_eazy", "p2", 3100)
    conn = m.connect()
    big = m._people_build(conn)
    conn.close()
    T = int(m.time.now)
    real_json = m.json
    opened, written = threading.Barrier(2, timeout=10), threading.Barrier(2, timeout=10)
    long_done = threading.Event()

    def dump_racing(obj, fh, **kw):
        text = real_json.dumps(obj, **kw)
        opened.wait()
        if not obj["players"]:
            long_done.wait(10)
        fh.write(text)
        fh.flush()
        long_done.set()
        written.wait()

    m.json = Shim(real_json, dump=dump_racing)
    try:
        ts = [threading.Thread(target=m._people_save, args=big + (T,)),
              threading.Thread(target=m._people_save, args=({}, [], set(), T + 1))]
        for t in ts:
            t.start()
        for t in ts:
            t.join(30)
    finally:
        m.json = real_json
    snap = m._people_load()
    check("two overlapping saves leave a people.json that loads, whole",
          "unloadable" if snap is None else
          (snap[3] - T, sorted(snap[0])) in ((0, sorted(big[0])), (1, [])), True)
    check("...and no temp file behind them", snapshot_temps(m), [])

    def dump_fails(obj, fh, **kw):
        fh.write(real_json.dumps(obj, **kw)[:40])
        fh.flush()
        raise OSError(28, "No space left on device")

    m._people_save(*(big + (T + 2,)))        # a good snapshot to fall back on
    m.json = Shim(real_json, dump=dump_fails)
    try:
        m._people_save(*(big + (T + 5,)))
    finally:
        m.json = real_json
    after = m._people_load()
    check("a failed save removes its temp file and keeps the last good snapshot",
          (snapshot_temps(m), after and after[3] - T), ([], 2))

    # ONE COLD LOAD PER PROCESS: four first requests at once each built (or
    # loaded) and saved the directory for themselves.
    m = fresh()
    for i in range(3):
        submit(m, "bhop_eazy", "c%d" % i, 3000 + i)
    m.people_reset()                          # a fresh install: no snapshot either
    real_bls = (m._people_build, m._people_load, m._people_save)
    for held in ("build", "load"):
        calls = {"build": 0, "load": 0, "save": 0}
        m._people_build = tally(real_bls[0], calls, "build", held == "build")
        m._people_load = tally(real_bls[1], calls, "load", held == "load")
        m._people_save = tally(real_bls[2], calls, "save")
        try:
            codes = together(m, "/board/api/players")
        finally:
            m._people_build, m._people_load, m._people_save = real_bls
        if held == "build":
            check("four first requests at once: one load, one build, one save",
                  (codes, calls), ([200] * 4, {"build": 1, "load": 1, "save": 1}))
            new_worker(m)                     # the snapshot is there this time
        else:
            check("...and from a snapshot, one load the other three wait for",
                  (codes, calls), ([200] * 4, {"build": 0, "load": 1, "save": 0}))

    # A SLOW SNAPSHOT LOAD MAY NOT INSTALL AN OLDER DIRECTORY OVER A NEWER BUILD.
    m = fresh()
    submit(m, "bhop_eazy", "p1", 3000)
    T0 = int(m.time.now)
    get(m, "/board/api/players")              # built and saved at T0
    m.time.now += m.WEB_PEOPLE_TTL + 1
    T1 = int(m.time.now)
    submit(m, "bhop_eazy", "p2", 3100)
    new_worker(m)
    real_load, real_kick, kicks = m._people_load, m._people_kick, []

    def slow_load():
        conn = m.connect()                    # a rebuild lands mid-read
        try:
            m._people_install(*m._people_build(conn), at=T1)
        finally:
            conn.close()
        return real_load()

    m._people_load, m._people_kick = slow_load, kicks.append
    try:
        n = body(get(m, "/board/api/players"))["n"]
    finally:
        m._people_load, m._people_kick = real_load, real_kick
    check("a slow snapshot load leaves the newer build in place (age, n, kicks)",
          (m._people["at"] - T0, n, kicks), (T1 - T0, 2, []))
    m._people_install({"b": "y"}, [], set(), T1)
    check("...an equal stamp is not older, so it installs",
          m._people["by_handle"], {"b": "y"})
    m._people_install({"c": "z"}, [], set(), T1 + 3600)
    m._people_install({"d": "w"}, [], set(), T1)
    check("...and a stamp ahead of the clock is not newer: a rebuild replaces it",
          m._people["by_handle"], {"d": "w"})
    m.people_reset()
    check("people_reset still clears it",
          (m._people["at"], m._people["by_handle"]), (-1e9, {}))

    # THE CLOCK STEPS BACK AN HOUR under a snapshot it stamped.  `now - at` is
    # then negative, which read as fresh: a player new since then was a 404 with
    # no rebuild until the clock caught up.
    m = fresh()
    T = int(m.time.now)
    m.time.now = T + 3600
    submit(m, "bhop_eazy", "p1", 3000)
    get(m, "/board/api/players")              # built and saved at T+3600
    m.time.now = T
    new_worker(m)
    submit(m, "bhop_eazy", "late", 3100)
    path = "/board/api/player/" + m.web_handle("late")
    first = get(m, path).status_code
    join_rebuilds()
    check("a snapshot from ahead of the clock is stale: 404, rebuilt, found (age 0)",
          (first, get(m, path).status_code, m._people["at"] - T), (404, 200, 0))

    # A REBUILD THREAD THAT CANNOT START left the directory marked busy, and it
    # never refreshed again.
    m = fresh()
    submit(m, "bhop_eazy", "p1", 3000)
    get(m, "/board/api/players")
    m.time.now += m.WEB_PEOPLE_TTL + 1        # stale: the next request kicks
    real_threading, fails = m.threading, [1]

    def thread_once_failing(*a, **kw):
        t = real_threading.Thread(*a, **kw)
        if fails:
            fails.pop()

            def start():
                raise RuntimeError("can't start new thread")
            t.start = start
        return t

    m.threading = Shim(real_threading, Thread=thread_once_failing)
    try:
        code = get(m, "/board/api/players").status_code
    except RuntimeError as exc:
        code = "raised %s" % exc
    finally:
        m.threading = real_threading
    check("a rebuild thread that cannot start: 200, not left busy (code, busy, fired)",
          (code, bool(m._people.get("busy")), fails), (200, False, []))
    get(m, "/board/api/players")              # still stale: this kick starts
    join_rebuilds()
    check("...so the next stale request rebuilds", m._people["at"] - int(m.time.now), 0)

    # PROFILE PAGING.  "Show more" re-asks for the whole prefix (offset 0, a
    # longer limit) and re-renders it: the order is recomputed per request, so
    # the next fixed offset could skip or repeat rows when a board changed.
    m = fresh()
    W = "76561198000000042"
    for mp in ("surf_a", "surf_b", "surf_c"):
        imported(m, mp, W, "Wide", 5000, "momentum")
    for k in range(2):
        imported(m, "surf_b", "76561198000007%03d" % k, "B%d" % k, 6000 + k, "momentum")
    for mp in ("surf_a", "surf_b"):
        imported(m, mp, W, "Wide", 7000, "momentum", track=1)
        imported(m, mp, W, "Wide", 900, "momentum", leg=1)
    url = "/board/api/player/" + m.web_handle(W)
    key = lambda p: [(x["map"], x["track"], x["leg"]) for x in p["rows"]]
    whole = body(get(m, url + "?offset=0&limit=5000"))
    order = key(whole)
    check("control: the whole order is 7 rows, main then bonuses then stages",
          ([(t, l) for _m, t, l in order], whole["total"], order[0][0]),
          ([(0, 0)] * 3 + [(1, 0)] * 2 + [(0, 1)] * 2, 7, "surf_b"))
    check("offset=0&limit=N is exactly the first N rows of the whole order",
          [key(body(get(m, url + "?offset=0&limit=%d" % n))) for n in range(1, 8)],
          [order[:n] for n in range(1, 8)])
    check("limit is clamped to 1..WEB_PROFILE_MAX, a bad one to the page size",
          [body(get(m, url + "?offset=0&limit=" + v))["limit"]
           for v in ("0", "-3", "999999", "x")],
          [1, 1, m.WEB_PROFILE_MAX, m.WEB_PROFILE_ROWS])
    check("...and limit=0 answers one row",
          len(body(get(m, url + "?offset=0&limit=0"))["rows"]), 1)
    real_rows = m.WEB_PROFILE_ROWS
    m.WEB_PROFILE_ROWS = 3
    try:
        p = body(get(m, url))
    finally:
        m.WEB_PROFILE_ROWS = real_rows
    check("with no limit a page is WEB_PROFILE_ROWS, and says so (rows, limit, total)",
          (len(p["rows"]), p["limit"], p["total"]), (3, 3, 7))
    check("an offset still pages", key(body(get(m, url + "?offset=2&limit=3"))),
          order[2:5])
    js = open(os.path.join(HERE, "web", "board.js"), encoding="utf-8").read()
    check("board.js's Show more asks for the whole prefix, not the next offset",
          ("'?offset=0&limit=' + want" in js, "'?offset=' + P.shown" in js),
          (True, False))

    print("\n%d failed" % len(FAILED))
    for f in FAILED:
        print("  " + f)
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
