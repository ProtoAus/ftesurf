#!/usr/bin/env python3
"""p856stub.py -- a scripted /api/run for the Patch 856 medal-toast rig.

  usage:  p856stub.py <port> <log file>

Each full-run post (leg=0) takes the next entry of STORY below as the reply's
`story` (past the end: none), and its Story facts (sfails, smask, stop) are
logged one line per post, key stripped.  Heartbeats and stage posts get a plain
stored answer.  cfg/test/p856sv.cfg points a lobby at it.
"""
import json
import sys
import threading
import time
import urllib.parse

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 18856
LOG = sys.argv[2] if len(sys.argv) > 2 else "p856stub.log"
STORY = [
    [{"l": "Story", "n": 3, "map": "surf_666", "m": "b", "t": "Complete the map",
      "tot": 1, "ch": ""}],
    [{"l": "Story", "n": 3, "map": "surf_666", "m": "s", "t": "First try every stage",
      "tot": 2, "ch": ""},
     {"l": "Events", "n": 7, "map": "surf_666", "m": "g", "t": "W only", "tot": 9,
      "ch": "Tier 2"}],
]
LOCK = threading.Lock()
NEXT = [0]


def note(line):
    with open(LOG, "a", encoding="utf-8") as fh:
        fh.write("%s %s\n" % (time.strftime("%H:%M:%S"), line))


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        form = dict(urllib.parse.parse_qsl(self.rfile.read(n).decode("utf-8", "replace")))
        out = {"ok": True, "stored": True, "best": 18510, "rank": 3, "of": 17, "rep": 0,
               "tier": "ranked", "prevms": 20000}
        if self.path.endswith("/api/run") and form.get("leg") == "0":
            with LOCK:
                i = NEXT[0]
                NEXT[0] += 1
            if i < len(STORY):
                out["story"] = STORY[i]
            note("run %d map=%s ticks=%s flags=%s sfails=%s smask=%s stop=%s story=%d" % (
                i + 1, form.get("map"), form.get("ticks"), form.get("flags"),
                form.get("sfails", "-"), form.get("smask", "-"), form.get("stop", "-"),
                len(out.get("story", []))))
        elif self.path.endswith("/api/run"):
            note("stage leg=%s sfails=%s" % (form.get("leg"), form.get("sfails", "-")))
        data = json.dumps(out).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *args):
        pass


note("p856stub port=%d" % PORT)
ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
