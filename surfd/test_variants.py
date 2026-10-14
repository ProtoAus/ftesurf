#!/usr/bin/env python3
"""Two builds of one map on /api/board, and the map list the game fetches.

  python3 test_variants.py

A throwaway home, as test_board.py does it.  The rows are written straight
into `runs`: what is under test is which rows a board READS.
"""
import atexit
import importlib
import json
import logging
import os
import shutil
import sqlite3
import sys
import tempfile

os.environ.setdefault("SURFD_RANKED_LINKED", "0")
FAILED = []
HOME = tempfile.mkdtemp(prefix="surfd-variants-")


def check(label, got, want):
    ok = got == want
    print("%-4s %-66s %r" % ("ok" if ok else "FAIL", label, got))
    if not ok:
        FAILED.append("%s: got %r, want %r" % (label, got, want))


with open(os.path.join(HOME, "surfd.env"), "w") as _fh:
    _fh.write("SURFD_KEY=testkey\n")
os.environ.update(SURFD_HOME=HOME, SURFD_DB=os.path.join(HOME, "test.db"),
                  SURFD_ENV=os.path.join(HOME, "surfd.env"),
                  SURFD_RUNS=os.path.join(HOME, "runs"))
for _k in ("SURFD_EVIDENCE", "SURFD_KEEP", "SURFD_PUBLIC_HOST", "SURFD_TRUSTED"):
    os.environ.pop(_k, None)
S = importlib.import_module("surfd")


@atexit.register
def _cleanup():
    logging.shutdown()
    shutil.rmtree(HOME, ignore_errors=True)


WATCH = os.path.join(S.DATA_DIR, "mapwatch")
os.makedirs(WATCH, exist_ok=True)


def row(mp, tier, player, ms):
    conn = sqlite3.connect(os.environ["SURFD_DB"])
    conn.execute(
        "INSERT INTO runs (map, track, leg, tier, style, player, name, ticks, tickrate,"
        " millis, flags, node, runid, submitted, replay_id) VALUES (?, 0, 0, ?, 'clean', ?, ?,"
        " ?, 100, ?, 0, 'p1', '', 1, 0)", (mp, tier, player, player, ms // 10, ms))
    conn.commit()
    conn.close()


def catalogue(maps):
    with open(os.path.join(WATCH, "catalogue.json"), "w", encoding="utf-8") as fh:
        json.dump({"at": 1, "maps": maps, "momnames": []}, fh)
    S._variants["at"] = None            # the cache is 120 s old otherwise


def board(mp, tier, n=0, **kw):
    args = dict({"map": mp, "tier": tier}, **{k: str(v) for k, v in kw.items()})
    resp = S.app.test_client().get("/api/board", query_string=args,
                                   environ_base={"REMOTE_ADDR": "10.0.0.%d" % (n % 250 + 1)})
    return resp.get_json() if resp.status_code == 200 else "HTTP %d" % resp.status_code


def who(body):
    return [r["name"] for r in body["rows"]]


def main():
    # surf_x is Momentum's build; surf_x_css is KSF's build of it.
    row("surf_x", "ranked", "native-on-x", 50000)
    row("surf_x", "ksf", "ksf-1", 40000)
    row("surf_x", "ksf", "ksf-2", 42000)
    row("surf_x", "momentum", "mom-1", 41000)
    row("surf_x_css", "ranked", "native-on-css", 45000)
    row("surf_x_css", "ksf", "ksf-filed-under-css", 39000)
    row("surf_y_css", "ranked", "native-on-y-css", 30000)
    row("surf_y", "ksf", "ksf-on-y", 31000)
    catalogue({"surf_x": {"name": "surf_x", "mode": "surf", "src": "km"},
               "surf_x_css": {"name": "surf_x_css", "mode": "surf", "src": "k", "of": "surf_x"},
               "surf_y": {"name": "surf_y", "mode": "surf", "src": "k"}})

    check("the plain build's boards are its own rows, as ever",
          (who(board("surf_x", "ksf")), who(board("surf_x", "momentum")),
           who(board("surf_x", "ranked")), who(board("surf_x", "combined"))),
          (["ksf-1", "ksf-2"], ["mom-1"], ["native-on-x"],
           ["ksf-1", "mom-1", "ksf-2", "native-on-x"]))
    b = board("surf_x_css", "combined")
    check("KSF's build shows KSF's and Momentum's times for the map and its OWN native "
          "rows, in time order -- not rows filed under its own name by a game, nor the "
          "plain build's native rows",
          (who(board("surf_x_css", "ksf")), who(board("surf_x_css", "momentum")),
           who(board("surf_x_css", "ranked")), who(b)),
          (["ksf-1", "ksf-2"], ["mom-1"], ["native-on-css"],
           ["ksf-1", "mom-1", "ksf-2", "native-on-css"]))
    check("...its counts are those boards' sizes, and each row carries its game",
          (b["counts"]["ksf"], b["counts"]["momentum"], b["counts"]["ranked"],
           b["counts"]["imported"], [r["tr"] for r in b["rows"]], b["map"]),
          (2, 1, 1, 3, ["ksf", "momentum", "ksf", "ranked"], "surf_x_css"))
    check("...and it pages as one list",
          (who(board("surf_x_css", "combined", limit=2)),
           who(board("surf_x_css", "combined", limit=2, offset=2))),
          (["ksf-1", "mom-1"], ["ksf-2", "native-on-css"]))
    check("a map that merely ends in _css, named a build of nothing, is only itself",
          (who(board("surf_y_css", "combined")), who(board("surf_y", "combined"))),
          (["native-on-y-css"], ["ksf-on-y"]))

    conn = sqlite3.connect(os.environ["SURFD_DB"])
    conn.execute("DELETE FROM mapwant")
    conn.commit()
    conn.close()
    board("surf_x_css", "ksf", limit=50)        # a short page of an imported board
    conn = sqlite3.connect(os.environ["SURFD_DB"])
    want = [r[0] for r in conn.execute("SELECT map FROM mapwant")]
    conn.close()
    check("a player at the end of that board queues the plain name for the crawls",
          want, ["surf_x"])

    for label, maps in (
            ("a build named of itself", {"surf_x_css": {"of": "surf_x_css"}}),
            ("a build of a name that is not a map's", {"surf_x_css": {"of": "../x"}}),
            ("a row that is not a row", {"surf_x_css": "surf_x"}),
            ("a key that is not a board's", {"Surf_X_css": {"of": "surf_x"}})):
        catalogue(maps)
        check("%s is no second build" % label, who(board("surf_x_css", "ksf")),
              ["ksf-filed-under-css"])
    with open(os.path.join(WATCH, "catalogue.json"), "wb") as fh:
        fh.write(b'{"maps": [1, 2')
    S._variants["at"] = None
    check("a catalogue that does not parse is no second builds, and the board answers",
          who(board("surf_x_css", "combined")), ["ksf-filed-under-css", "native-on-css"])
    os.remove(os.path.join(WATCH, "catalogue.json"))
    S._variants["at"] = None
    check("...as is none at all", who(board("surf_x_css", "ranked")), ["native-on-css"])

    # The map list.
    c = S.app.test_client()
    r = c.get("/api/board?maps=1", environ_base={"REMOTE_ADDR": "10.9.0.1"})
    check("with no list written the game is told so", (r.status_code, r.get_json()["error"]),
          (404, "no map list"))
    body = b"FTESURF-MAPDL 1\n# written\ndl surf_x surf km 2 40 2026-10-11 0 2 1\n"
    with open(os.path.join(WATCH, "mapdl.txt"), "wb") as fh:
        fh.write(body)
    r = c.get("/api/board?maps=1", environ_base={"REMOTE_ADDR": "10.9.0.2"})
    check("the list carries per-build zone/pool flags without caching policy",
          (r.status_code, r.data.endswith(body.splitlines()[-1] + b" - 0 1\n"),
           r.mimetype, r.headers.get("Cache-Control")),
          (200, True, "text/plain", "no-store"))
    with open(os.path.join(WATCH, "mapdl.txt"), "ab") as fh:
        fh.write(b"dl surf_new surf m 1 9 2026-10-12 1 1 0\n")
    os.utime(os.path.join(WATCH, "mapdl.txt"), ns=(10 ** 18, 10 ** 18))
    r = c.get("/api/board?maps=1", environ_base={"REMOTE_ADDR": "10.9.0.3"})
    check("a list rewritten since is the one served", r.data.endswith(b"2026-10-12 1 1 0 - 0 1\n"), True)
    keep, S.MAPLIST_MAX = S.MAPLIST_MAX, 16
    r = c.get("/api/board?maps=1", environ_base={"REMOTE_ADDR": "10.9.0.4"})
    S.MAPLIST_MAX = keep
    check("a list over the cap is not served (the cap set to 16 bytes here)", r.status_code, 404)
    r = c.get("/api/board?map=surf_x&tier=ksf", environ_base={"REMOTE_ADDR": "10.9.0.5"})
    check("...and a board asked for the ordinary way is still a board",
          (r.status_code, [x["name"] for x in r.get_json()["rows"]]), (200, ["ksf-1", "ksf-2"]))

    print("\n%d failed" % len(FAILED))
    for f in FAILED:
        print("  " + f)
    return 1 if FAILED else 0


if __name__ == "__main__":
    raise SystemExit(main())
