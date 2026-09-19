#!/usr/bin/env python3
"""
p371stub.py -- a scripted /api/run for the Patch 371 announcement harness.

  usage:  p371stub.py <port> "<stored rank of prevms delay>;<...>;..."

Each full-run post (body carries leg=0) takes the next script entry in turn,
so one walk after another can get a first time, a new best, a world record, a
standing best and a slow reply.  Stage posts and heartbeats are answered at
once (stored, #3 of 17).  Threaded, unlike b65stub.py: a delayed full-run
reply must not queue behind the stage posts of the same walk.  The key is
stripped from the log line.
"""

import json
import sys
import threading
import time

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8141
SCRIPT = [e.split() for e in (sys.argv[2] if len(sys.argv) > 2 else "").split(";") if e.strip()]
LOCK = threading.Lock()
NEXT = [0]


def reply(stored, rank, of, prevms):
    return {"ok": True, "stored": bool(int(stored)), "best": 18510, "rank": int(rank),
            "of": int(of), "rep": 0, "tier": "ranked", "prevms": int(prevms)}


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(n).decode("utf-8", "replace")
        form = dict(p.split("=", 1) for p in body.split("&") if "=" in p)
        out = reply(1, 3, 17, 20000)
        delay = 0.0
        tag = ""
        if self.path.endswith("/api/run") and form.get("leg") == "0":
            with LOCK:
                i = NEXT[0]
                NEXT[0] += 1
            if i < len(SCRIPT):
                s = SCRIPT[i]
                out = reply(s[0], s[1], s[2], s[3])
                delay = float(s[4]) if len(s) > 4 else 0.0
                tag = "script %d" % (i + 1)
            else:
                tag = "script past end"
        shown = "&".join(p for p in body.split("&") if not p.startswith("key="))
        print("%s  POST %-16s %s %s" % (time.strftime("%H:%M:%S"), self.path, tag, shown),
              flush=True)
        if delay:
            time.sleep(delay)
        data = json.dumps(out).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *args):
        pass


print("p371stub port=%d script=%s" % (PORT, SCRIPT), flush=True)
ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
