#!/usr/bin/env python3
"""
b65stub.py -- a fake /api/run, so the GAME's half of the rank path can be
tested on its own.

WHY A STUB AND NOT THE REAL SURFD.  What is under test here is everything
between a finish and a sentence on the results card: the submission stamps a
subject, the reply is routed back to the player who finished, the JSON is
parsed, a userinfo key is rewritten, and CSQC matches the key's subject against
the run in front of it.  surfd's own half -- which run belongs on which board
and what rank it stands at -- is already pinned by test_board.py section 11,
against the real database and the real ordering.

Pointing the test at the live directory instead would have two problems and
both are disqualifying: it would put fabricated rows on the public leaderboard,
and it could only ever produce the answer the real rules produce, so the three
outcomes the card draws differently (a rank, no board, a refusal) could not all
be reached from one harness.

  usage:  b65stub.py <rank|norank|noboard|refuse> <port> [delay-seconds]

`norank` IS THE OLD SURFD, not a broken one.  Before this build /api/run
answered {"ok","stored","best"} with no position in it, so that is exactly what
a server running build 65 progs sees if it is pointed at a directory that has
not been updated -- a window an operator creates by deploying in the wrong
order.  The game must call that a success, because it is one.  It is here as an
arm because the first version of the reply handler called it a refusal, and a
game that tells a player their run was rejected while the row goes up on the
board behind them is the same lie this build exists to remove.

THE DELAY IS AN INSTRUMENT, not padding.  The card draws "asking the
leaderboard" between the submission and the answer, and that state lasts
however long the round trip takes -- on a LAN, less than one frame.  Holding
the answer for a couple of seconds is the only way a polling config can ever
observe it, and a state that cannot be observed cannot be said to work.

The key is stripped from the log line.  It is a test key and it is still not
printed, because a habit that has an exception is not a habit.
"""

import json
import sys
import time

from http.server import BaseHTTPRequestHandler, HTTPServer

MODE = sys.argv[1] if len(sys.argv) > 1 else "rank"
PORT = int(sys.argv[2]) if len(sys.argv) > 2 else 8099
DELAY = float(sys.argv[3]) if len(sys.argv) > 3 else 0.0

# Deliberately not 1: "#1 of 1" is what a board with one row on it says, and it
# is also what several plausible bugs say (a hardcoded default, a count that
# never ran).  3 of 17 is a number that can only have come from the reply.
RANK, OF = 3, 17


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(n).decode("utf-8", "replace")
        shown = "&".join(p for p in body.split("&") if not p.startswith("key="))
        print("%s  POST %-16s %s" % (time.strftime("%H:%M:%S"), self.path, shown),
              flush=True)

        # Heartbeats are answered at once whatever the mode.  Only /api/run is
        # under test, and delaying the heartbeat would just make the server's
        # own directory status noisy for no reason.
        if DELAY and self.path.endswith("/api/run"):
            time.sleep(DELAY)

        if MODE == "noboard":
            self.send_response(204)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return

        if MODE == "refuse":
            out = b'{"ok":false,"error":"forbidden"}'
            code = 403
        elif MODE == "norank":
            out = json.dumps({"ok": True, "stored": True,
                              "best": 18510}).encode()
            code = 200
        else:
            out = json.dumps({"ok": True, "stored": True, "best": 18510,
                              "rank": RANK, "of": OF}).encode()
            code = 200

        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(out)))
        self.end_headers()
        self.wfile.write(out)

    def log_message(self, *args):
        pass                    # the POST line above is the whole log


print("b65stub mode=%s port=%d delay=%.1fs -> rank %d of %d"
      % (MODE, PORT, DELAY, RANK, OF), flush=True)
HTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
