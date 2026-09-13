#!/usr/bin/env python3
"""
b66stub.py -- a fake /lobbies.json, so the map list's live headcount can be
tested on the cases the real directory cannot currently produce.

WHY A STUB AND NOT THE LIVE DIRECTORY.  The join itself -- lobby row to map row
to drawn count -- is already pinned against the real play.proto.bar by
cfg/testrun/b66pop.cfg, and that arm is the one worth having because it proves
the feature works against the thing it ships against.  What it cannot prove is
anything about a NON-ZERO count, because the five lobbies are idle: every row it
saw drew "0 playing", so the green branch, the summation and the case fix were
all untested by it.  Waiting for somebody to be playing is not a test.

  usage:  b66stub.py [port]          (default 8099)

THE FIVE ROWS ARE EACH AN ARM, and every one of them is a case the live
directory cannot be made to produce on demand:

  27511 surf_lux         3  | two lobbies on ONE map, so the row must draw
  27512 surf_lux         4  | their SUM (7) and not either half, and not twice
  27513 bhop_mukiology   2  | lowercase, while the FILE is Bhop_Mukiology.bsp --
                            | the only capitalised BSP in the 1312-map library.
                            | Before build 66 ui_map_index compared exactly and
                            | answered -1 here, which the lobby cell draws as a
                            | red "not installed" for a map that IS installed.
  27514 surf_flow        0  | a lobby with nobody on it.  Must draw a dim
                            | "0 playing" and NOT nothing -- 0 and "no lobby"
                            | are different facts and this is the arm that says
                            | so.  If this row goes silent the two have been
                            | folded together.
  27515 zz_b66_absent    9  | a lobby on a map this install does not have.  Its
                            | nine players must land on NO row at all.  Without
                            | the mapidx < 0 guard in ui_map_players they would
                            | land on every uninstalled lobby's row, because -1
                            | is also Lob_Row's "not installed" marker.

PORTS ARE ASCENDING AND DISTINCT ON PURPOSE.  Lob_Parse keeps the five lobbies
with the LOWEST ports (m_lobby.qc:359-375) and LB_MAX is 5, so five distinct
ports is the only arrangement in which every arm above survives the parse.  A
sixth row here would be dropped silently and its arm would read as a pass.

EXPECTED: 5 lobbies, 3 rows drawing a count -- surf_lux "7 playing",
Bhop_Mukiology "2 playing", surf_flow "0 playing".  Any other total is a
failure, and "4 of 1337" specifically means the absent map found a row.
"""

import json
import sys
import time

from http.server import BaseHTTPRequestHandler, HTTPServer

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8099

LOBBIES = [
    # map,              players, port,  name
    ("surf_lux",        3, 27511, "FTESurf -- stub a"),
    ("surf_lux",        4, 27512, "FTESurf -- stub b"),
    ("bhop_mukiology",  2, 27513, "FTESurf -- stub case"),
    ("surf_flow",       0, 27514, "FTESurf -- stub empty"),
    ("zz_b66_absent",   9, 27515, "FTESurf -- stub absent"),
]


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        print("%s  GET %s" % (time.strftime("%H:%M:%S"), self.path), flush=True)
        if not self.path.startswith("/lobbies.json"):
            self.send_response(404)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return

        body = json.dumps({
            "v": 1,
            "t": int(time.time()),
            "lobbies": [
                {"map": m, "players": p, "max": 32,
                 "addr": "127.0.0.1:%d" % port, "name": nm, "age": 1}
                for (m, p, port, nm) in LOBBIES
            ],
        }).encode()

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass                        # the GET line above is the whole log


print("b66stub on %d -- %d lobbies, expect 3 rows to draw a count"
      % (PORT, len(LOBBIES)), flush=True)
HTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
