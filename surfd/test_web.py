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

FAILED = []
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)


def check(label, got, want):
    ok = got == want
    print("%-4s %-62s %r" % ("ok" if ok else "FAIL", label, got))
    if not ok:
        FAILED.append("%s: got %r, want %r" % (label, got, want))


LIBRARY = ["surf_kitsune", "surf_lux", "Bhop_Mukiology", "bhop_eazy", "surf_nozone"]
ZONED = ["surf_kitsune", "surf_lux", "Bhop_Mukiology", "bhop_eazy", "surf_nobsp"]


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
    os.environ.update(SURFD_HOME=home, SURFD_DB=os.path.join(home, "test.db"),
                      SURFD_ENV=os.path.join(home, "surfd.env"),
                      SURFD_MAPS=maps, SURFD_ZONES=zones,
                      SURFD_RUNS=os.path.join(home, "runs"))
    for k in ("SURFD_PUBLIC_HOST", "SURFD_TRUSTED", "SURFD_ADMIN_HASH",
              "SURFD_ADMIN_SECRET", "SURFD_ADMIN_INSECURE_COOKIE",
              "SURFD_RCON_PASSWORD", "SURFD_ADMIN_LOBBIES"):
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


def add_verdict(m, rid, verdict, at):
    conn = sqlite3.connect(m._test_db)
    conn.execute("INSERT INTO verdicts (replay_id, verdict, reason, ticks,"
                 " engine, progs, at) VALUES (?,?,'r',-1,'e','p',?)",
                 (rid, verdict, at))
    conn.commit()
    conn.close()


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
                  "surf_nobsp", "surf_ghost"]))
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
    check("...and names no tier", ["tier" in x for x in b["boards"]] + ["tier" in b],
          [False, False, False, False])
    check("no parameters open main clean",
          (b["track"], b["leg"], b["style"]), (0, 0, "clean"))
    want = [dict((k, v) for k, v in x.items() if k != "player")
            for x in api_board(m, "bhop_eazy")["rows"]]
    check("rows are /api/board's rows minus player", b["rows"], want)
    check("...and name no player", any("player" in x for x in b["rows"]), False)
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

    print("\n%d failed" % len(FAILED))
    for f in FAILED:
        print("  " + f)
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
