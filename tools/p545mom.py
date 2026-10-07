#!/usr/bin/env python3
"""Offline game falsifier for the Momentum download UI (stdlib HTTP stub).

python tools/p545mom.py --prepare
python tools/p545mom.py --serve > <fresh stub log>
Run only in a private content overlay via tools/runlines_smoke.py (p545mom.cfg).
python tools/p545mom.py --check <client log> --http-log <stub log>

The stub serves TWO indexed handles: a held demo and a permanently missing one.
It cannot contact Momentum or a live DB. It proves QC parses the board handle,
POSTs both line requests before polling, receives ready, transfers/loads the
replay, preserves it across board close, and reports unavailable honestly.
Backend worker/codec controls belong to test_momrequest/test_momgrab separately.
"""
import argparse
import http.server
import json
import re
import time
from pathlib import Path
from urllib.parse import urlparse, parse_qs

ROOT = Path(__file__).resolve().parents[1]
PORT = 8545
REP = 995451
TOKENS = ["54501/" + "a" * 40, "54502/" + "b" * 40]


def prepare():
    base = ROOT / "ftesurf/cfg/test"
    base.mkdir(parents=True, exist_ok=True)
    (base / "p545mom.cfg").write_text('''cfg_save_auto 0
log_enable 1
log_dir logs
log_name runlines_smoke
developer 0
cl_idlefps 0
cl_maxfps 100
vid_fullscreen 0
set fs_missingwarn 0
sv_public 0
sv_port 27640
set run_resume 0
// Synthetic client consents only inside this private test overlay.
set rec_terms 4
set lobby_dir "http://127.0.0.1:8545"
set hud_lines_board 1
set hud_scale 1
set hud_linegraph 1
set hud_linegraph_labels 1
set hud_watch_path 1
set hud_watch_skipidle 0
waitms 2000
map surf_dune
waitmap 60
waitms 2500
menu_restart
waitms 500
ui_close
waitms 500
// menu_restart reloads consent, so set only the synthetic test cvar afterward.
set rec_terms 4
scores tab imported
scores leg 0
scores open
waitms 1500
board_status
screenshot screenshots/p545mom_get.png
// Revoking the synthetic cvar permission cannot spend a cached handle.
set rec_terms 0
scores line 0
waitms 500
scores lines clear
set rec_terms 4
scores line 0
scores line 1
waitms 12500
scores lines
board_status
screenshot screenshots/p545mom_ready.png
scores close
waitms 500
linegraph
waitms 500
screenshot screenshots/p545mom_graph.png
linegraph close
scores tab imported
scores open
// A cached row must replace an older queued watch without waiting.
scores olpick 1
waitms 300
scores olpick 0
waitms 1500
replay status
screenshot screenshots/p545mom_cancel.png
replay stop
scores open
scores olpick 1
waitms 11500
scores olpick 0
waitms 1500
replay status
screenshot screenshots/p545mom_watch.png
replay stop
scores lines clear
waitms 500
echo p545mom DONE
echo RUNLINES COMPLETE
quit
''')
    print("Prepared cfg/test/p545mom.cfg; HTTP stub listens only on 127.0.0.1:%d" % PORT)


def serve():
    posted = set()
    class Handler(http.server.BaseHTTPRequestHandler):
        def respond(self, code, obj):
            data = obj if isinstance(obj, bytes) else json.dumps(obj).encode()
            self.send_response(code)
            self.send_header("Content-Type", "text/plain" if isinstance(obj, bytes) else "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            print(self.command, self.path, code, flush=True)

        def do_POST(self):
            self.rfile.read(int(self.headers.get("Content-Length", 0)))
            token = self.path.removeprefix("/api/momentum/")
            if token not in TOKENS:
                return self.respond(409, {"state": "failed", "why": "unknown handle"})
            posted.add(token)
            return self.respond(200, {"state": "queued"})

        def do_GET(self):
            url = urlparse(self.path)
            if url.path == "/api/board":
                q = {k:v[0] for k,v in parse_qs(url.query).items()}
                rows = [{"r":i+1, "name":name, "ticks":10, "ms":100,
                         "rate":100, "flags":0, "when":1, "rep":0, "get":TOKENS[i], "tr":"momentum"}
                        for i,name in enumerate(("TestMomentum", "TestGone"))]
                return self.respond(200, {"map":q["map"], "track":int(q["track"]), "leg":int(q["leg"]),
                    "tier":q["tier"], "style":q["style"], "t":int(time.time()),
                    "counts":{"ranked":0,"community":0,"momentum":2,"ksf":0}, "rows":rows})
            token = url.path.removeprefix("/api/momentum/")
            if token in TOKENS:
                if token not in posted:
                    return self.respond(404, {"state":"failed", "why":"not requested"})
                if token == TOKENS[0]:
                    return self.respond(200, {"state":"ready", "rep":REP})
                return self.respond(200, {"state":"failed", "why":"gone"})
            if url.path == "/api/replay/%d" % REP:
                data = (ROOT / "ftesurf/cfg/test/p545graphA.rec").read_text()
                data = data.replace("pmpin gravity=800\n", "")
                data = data.replace("begin\n", "foreign momentum %s 0 0 1 76561198000000001\nbegin\n" % ("a" * 40))
                return self.respond(200, data.encode())
            self.respond(404, {"error":"not found"})

        def log_message(self, *args):
            pass

    with http.server.ThreadingHTTPServer(("127.0.0.1", PORT), Handler) as server:
        server.timeout = 1
        deadline = time.monotonic() + 100
        print("stub ready", flush=True)
        while time.monotonic() < deadline:
            server.handle_request()


def check(path, http_log):
    text = Path(path).read_text(errors="replace")
    http = Path(http_log).read_text(errors="replace")
    missing = []
    for token in TOKENS:
        if "POST /api/momentum/%s 200" % token not in http:
            missing.append("no POST for parsed handle " + token[:5])
        if "GET /api/momentum/%s 200" % token not in http:
            missing.append("no poll for " + token[:5])
    firstpoll = http.find("GET /api/momentum/")
    if any(http.find("POST /api/momentum/" + t) > firstpoll for t in TOKENS):
        missing.append("comparisons were not enqueued together before first poll")
    if "GET /api/replay/%d 200" % REP not in http:
        missing.append("no replay body transfer (use a cold disposable cache)")
    for word in ("accept the online terms before requesting a demo", "line 1 drawn", "line 2 demo unavailable: gone", "scores: demo unavailable: gone", "p545mom DONE"):
        if word not in text:
            missing.append("missing acted control: " + word)
    if "QC ERROR" in text or "runaway" in text:
        missing.append("QC runtime error")
    if "replay:" not in text or "TestA" not in text:
        missing.append("watch did not report the delivered file")
    print("\n".join("FAIL " + x for x in missing) if missing else "PASS board handles -> two POSTs -> polls -> replay transfer, line, watch and explicit unavailable")
    return bool(missing)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--prepare", action="store_true")
    p.add_argument("--serve", action="store_true")
    p.add_argument("--check")
    p.add_argument("--http-log")
    a = p.parse_args()
    if a.prepare: prepare()
    if a.serve: serve()
    if a.check: raise SystemExit(check(a.check, a.http_log))
