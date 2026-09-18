#!/usr/bin/env python3
"""
p357board.py -- a fake surfd for the "board refreshes after a finish" fixtures
(cfg/test/p357ref*.cfg).  POST /api/run stores the run (any flags: the fixture's
finishes are setpos-tainted) and answers like surfd 353+; GET /api/board serves
the rows back, lowercasing `map` in the echo exactly as surfd does.  Every GET is
logged, because "no request until the board opens" is one of the predictions.

  usage:  p357board.py <port> [seed N] [getdelay S]

`seed N` pre-fills N rows faster than any scripted run (1000.. ticks) on every
board asked for, so the finisher lands at rank N+1 (the pinned-row arm).
"""

import json
import sys
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8131
ARGS = sys.argv[2:]
SEED = int(ARGS[ARGS.index("seed") + 1]) if "seed" in ARGS else 0
GETDELAY = float(ARGS[ARGS.index("getdelay") + 1]) if "getdelay" in ARGS else 0.0

ROWS = {}   # (map, track, leg, style) -> {player: row}


def board(key):
    b = ROWS.setdefault(key, {})
    if SEED and not any(p.startswith("seed") for p in b):
        for i in range(SEED):
            b["seed%02d" % i] = {"player": "seed%02d" % i, "name": "Seed%02d" % i,
                                 "ticks": 1000 + i, "rate": 100.0,
                                 "ms": (1000 + i) * 10, "flags": 0, "when": 0}
    return b


def ranked(b):
    return sorted(b.values(), key=lambda r: r["ms"])


class Handler(BaseHTTPRequestHandler):
    def _send(self, obj, code=200):
        out = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(out)))
        self.end_headers()
        self.wfile.write(out)

    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        form = dict(urllib.parse.parse_qsl(self.rfile.read(n).decode("utf-8", "replace")))
        if not self.path.endswith("/api/run"):
            return self._send({})
        flags = int(float(form.get("flags", "0")))
        style = "segmented" if flags & (128 | 8) else "clean"
        key = (form.get("map", "").lower(), int(form.get("track", 0)),
               int(form.get("leg", 0)), style)
        b = board(key)
        ticks = int(float(form.get("ticks", "0")))
        rate = float(form.get("tickrate", "100"))
        ms = int(round(ticks * 1000.0 / rate))
        player = form.get("player", "?")
        prev = b.get(player)
        stored = prev is None or ms < prev["ms"]
        if stored:
            b[player] = {"player": player, "name": form.get("name", player),
                         "ticks": ticks, "rate": rate, "ms": ms, "flags": flags,
                         "when": int(time.time())}
        order = ranked(b)
        rank = [r["player"] for r in order].index(player) + 1
        print("%s  POST run %s -> stored %s rank %d of %d" %
              (time.strftime("%H:%M:%S"), key, stored, rank, len(order)), flush=True)
        self._send({"ok": True, "stored": stored, "best": b[player]["ms"],
                    "rank": rank, "of": len(order), "rep": 0,
                    "tier": "community" if flags & 0x3E00 else "ranked",
                    "prevms": prev["ms"] if prev else 0})

    def do_GET(self):
        u = urllib.parse.urlparse(self.path)
        q = dict(urllib.parse.parse_qsl(u.query))
        if u.path != "/api/board":
            return self._send({}, 404)
        key = (q.get("map", "").lower(), int(q.get("track", 0)), int(q.get("leg", 0)),
               q.get("style", "clean"))
        print("%s  GET board %s" % (time.strftime("%H:%M:%S"), key), flush=True)
        if GETDELAY:
            time.sleep(GETDELAY)
        order = ranked(board(key))
        limit = int(q.get("limit", 50))
        rows = [dict(r, r=i + 1, rep=0) for i, r in enumerate(order[:limit])]
        self._send({"v": 1, "t": int(time.time()), "map": key[0], "track": key[1],
                    "leg": key[2], "tier": q.get("tier", "ranked"), "style": key[3],
                    "counts": {"ranked": len(order), "community": 0},
                    "offset": 0, "rows": rows})

    def log_message(self, *args):
        pass


print("p357board port=%d seed=%d getdelay=%.1f" % (PORT, SEED, GETDELAY), flush=True)
HTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
