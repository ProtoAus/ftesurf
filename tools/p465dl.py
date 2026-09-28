#!/usr/bin/env python3
"""p465dl.py -- does the Download button actually download a map?

  python tools/p465dl.py             subject: a local mirror that serves the bsp
  python tools/p465dl.py --control   control:  the same mirror answering 404

Drives cfg/test/p465dl.cfg, which calls `ui_dlmap` -- the headless twin of the
button, the way `ui_join` is the start button's.

THE CONTROL IS NOT OPTIONAL.  The subject arm can pass for reasons that have
nothing to do with the patch: a stale maps/p465test.bsp from a previous run, or
a log line printed for a transfer the engine later threw away.  --control serves
404 from the same port with the same config, and must end `failed` with no file.
If both arms pass, this measures nothing and says so.

It also settles by MEASUREMENT which url layout the engine takes.  Both
sv_dlURL and cl_download_mapsrc are set in the arm and the mirror serves both
shapes, so the request log names the winner rather than this file asserting one.
"""

import argparse
import http.server
import os
import re
import shutil
import socket
import subprocess
import sys
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
GAME = os.path.join(ROOT, "ftesurf")
CFG = "cfg/test/p465dl.cfg"
SRCCFG = os.path.join(GAME, "cfg", "test", "p465src.cfg")
LOG = os.path.join(GAME, "logs", "p465dl.log")
DEST = os.path.join(GAME, "maps", "p465test.bsp")
TMP = os.path.join(GAME, "maps", "p465test.tmp")

# Small enough that the run does not have to wait on it, big enough that the
# engine reports a rate at all rather than finishing inside one frame.
PREFER = ["surf_dread", "surf_1998", "surf_ezclap"]

REQUESTS = []           # (path, status) -- what the engine actually asked for


class Handler(http.server.BaseHTTPRequestHandler):
    serve_file = None   # set per run; None means the control arm
    throttle = 0        # bytes/sec, 0 = as fast as the socket takes it
    protocol_version = "HTTP/1.1"

    def log_message(self, *a):
        pass            # the REQUESTS list is the record; stderr noise is not

    def _serve(self, body):
        # Both layouts resolve to the same file. Which one the engine asks for
        # is the measurement, so neither is privileged here.
        want = re.fullmatch(r"/(?:ftesurf/)?(?:maps/)?p465test\.bsp", self.path)
        if not want or not self.serve_file:
            REQUESTS.append((self.path, 404))
            self.send_response(404)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        n = os.path.getsize(self.serve_file)
        REQUESTS.append((self.path, 200))
        self.send_response(200)
        self.send_header("Content-Type", "application/octet-stream")
        self.send_header("Content-Length", str(n))
        self.end_headers()
        if not body:
            return
        if not self.throttle:
            with open(self.serve_file, "rb") as fh:
                shutil.copyfileobj(fh, self.wfile)
            return
        # THROTTLED, because an unthrottled localhost transfer finishes inside a
        # single Dl_Tick and every rate sample reads 0 -- which looks exactly
        # like a broken KB/s readout. Pacing the mirror is what makes the rate
        # and the percentage observable at all, so the display is tested rather
        # than assumed.
        chunk = max(4096, self.throttle // 8)
        with open(self.serve_file, "rb") as fh:
            while True:
                b = fh.read(chunk)
                if not b:
                    break
                self.wfile.write(b)
                time.sleep(len(b) / float(self.throttle))

    def do_GET(self):
        self._serve(True)

    def do_HEAD(self):
        self._serve(False)


def free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


def pick_source():
    """A real bsp to serve, chosen from maps this install has."""
    for name in PREFER:
        for d in (os.path.join(GAME, "maps"),
                  r"C:\Program Files (x86)\Steam\steamapps\common"
                  r"\Momentum Mod Playtest\momentum\maps"):
            p = os.path.join(d, name + ".bsp")
            if os.path.exists(p) and os.path.getsize(p) < 40 * 1024 * 1024:
                return p
    return None


def run_client(exe, timeout):
    # DELETE THE LOG FIRST. FTE appends, so without this the grader reads the
    # PREVIOUS run's lines too -- and the previous run is usually the other arm.
    # The control's first pass showed 12 state samples for 6 calls, opening with
    # the subject's `ok`, which is exactly the shape that makes a control look
    # like it measured something it did not.
    if os.path.exists(LOG):
        os.remove(LOG)
    flags = 0x08000000 if os.name == "nt" else 0
    p = subprocess.Popen([os.path.join(ROOT, exe), "-WindowStyle", "Minimized",
                          "+exec", CFG], cwd=ROOT, creationflags=flags,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    t0 = time.time()
    while p.poll() is None and time.time() - t0 < timeout:
        time.sleep(1)
    if p.poll() is None:
        p.kill()
        raise SystemExit("the run did not exit in %g s -- killed" % timeout)
    return time.time() - t0


src_used = [None]


def grade(control):
    if not os.path.exists(LOG):
        return False, ["no log at %s -- the run never got that far" % LOG]

    with open(LOG, "r", encoding="utf-8", errors="replace") as fh:
        log = fh.read()

    notes = []
    ok = True

    if 'Unknown command "ui_dlmap"' in log:
        return False, ["the menu VM never started -- `Unknown command \"ui_dlmap\"`. "
                       "menu_restart did not take; see b67join.cfg's header."]

    m = re.search(r"ui_dlmap: builtin (\w+)", log)
    if not m:
        return False, ["ui_dlmap printed nothing -- the arm did not run"]
    notes.append("builtin: %s" % m.group(1))
    if m.group(1) != "present":
        return False, notes + ["the downloadmap builtin did not bind. A #0 with "
                               "no :name compiles clean and resolves to nothing."]

    states = re.findall(r"ui_dlmap: builtin \w+, state (\d) \((\w+)\)", log)
    seq = [s[1] for s in states]
    notes.append("state sequence: %s" % " -> ".join(seq))

    rates = [float(r) for r in re.findall(r"ui_dlmap: [\d.]+% at ([\d.]+) B/s", log)]
    nonzero = [r for r in rates if r > 0]
    notes.append("rate samples: %d, non-zero: %d, max %.0f B/s"
                 % (len(rates), len(nonzero), max(rates) if rates else 0))

    have = os.path.exists(DEST)
    notes.append("maps/p465test.bsp on disk afterwards: %s%s"
                 % (have, " (%d bytes)" % os.path.getsize(DEST) if have else ""))

    # Patch 465 writes to .tmp and renames only when the file is whole. A .tmp
    # surviving the run means the rename did not happen, which is the bug this
    # arm exists to catch -- a truncated bsp under the real name.
    leftover = os.path.exists(TMP)
    notes.append("maps/p465test.tmp left behind: %s%s"
                 % (leftover,
                    " (%d bytes)" % os.path.getsize(TMP) if leftover else ""))

    served = [r for r in REQUESTS if r[1] == 200]
    missed = [r for r in REQUESTS if r[1] == 404]
    notes.append("http requests: %d served, %d refused" % (len(served), len(missed)))
    for path, st in REQUESTS[:6]:
        notes.append("    %s -> %d" % (path, st))
    if REQUESTS:
        notes.append("URL LAYOUT THE ENGINE CHOSE: %s" % REQUESTS[0][0])

    if control:
        # The control must FAIL, and must fail for the right reason: the engine
        # asked and was refused, rather than never asking.
        if not REQUESTS:
            ok = False
            notes.append("CONTROL DID NOT DISCRIMINATE: the engine never made a "
                         "request, so 'no file' proves nothing about the mirror.")
        if have:
            ok = False
            notes.append("CONTROL FAILED: a file exists after a 404-only mirror.")
        if leftover:
            ok = False
            notes.append("CONTROL FAILED: a .tmp survived a refused download.")
        if "failed" not in seq:
            ok = False
            notes.append("CONTROL FAILED: never reached the failed state.")
    else:
        if not have:
            ok = False
            notes.append("SUBJECT FAILED: no bsp on disk.")
        if "ok" not in seq:
            ok = False
            notes.append("SUBJECT FAILED: never reached the ok state.")
        if not served:
            ok = False
            notes.append("SUBJECT FAILED: the mirror served nothing, so whatever "
                         "landed did not come from here.")
        if leftover:
            ok = False
            notes.append("SUBJECT FAILED: a .tmp survived a completed download "
                         "-- the rename did not happen.")
        if have and os.path.getsize(DEST) != os.path.getsize(src_used[0]):
            ok = False
            notes.append("SUBJECT FAILED: the landed file is %d bytes, the served "
                         "file is %d -- TRUNCATED."
                         % (os.path.getsize(DEST), os.path.getsize(src_used[0])))
        if not nonzero:
            notes.append("NOTE: every rate sample was zero. The transfer may have "
                         "finished inside one poll -- not a failure, but the KB/s "
                         "readout is unproven by this run.")
    return ok, notes


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--control", action="store_true",
                    help="serve 404 for everything: the arm must FAIL")
    ap.add_argument("--throttle", type=int, default=400000,
                    help="mirror speed in bytes/sec; 0 = unthrottled. The "
                         "default paces the transfer so the rate and the "
                         "percentage are observable at all.")
    ap.add_argument("--exe", default="ftesurf64.exe")
    ap.add_argument("--timeout", type=float, default=150)
    args = ap.parse_args()

    src = None if args.control else pick_source()
    if not args.control and not src:
        sys.exit("no suitable bsp to serve -- edit PREFER")

    # A leftover from an earlier run would let the subject arm pass without
    # downloading anything, and would make the control look like a failure.
    for stale in (DEST, TMP):
        if os.path.exists(stale):
            os.remove(stale)
            print("removed a stale %s" % stale)

    port = free_port()
    Handler.serve_file = src
    Handler.throttle = args.throttle
    src_used[0] = src
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", port), Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()

    with open(SRCCFG, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("// written by tools/p465dl.py -- the per-run mirror address.\n")
        fh.write('set sv_dlURL "http://127.0.0.1:%d"\n' % port)
        fh.write('set cl_download_mapsrc "http://127.0.0.1:%d/"\n' % port)

    print("arm    : %s" % ("CONTROL (404 only)" if args.control else "SUBJECT"))
    print("mirror : http://127.0.0.1:%d  serving %s%s"
          % (port, os.path.basename(src) if src else "nothing",
             "  throttled to %d B/s" % args.throttle if args.throttle else ""))
    took = run_client(args.exe, args.timeout)
    srv.shutdown()
    print("client ran %.1f s" % took)

    ok, notes = grade(args.control)
    print()
    for n in notes:
        print("  " + n)
    print()
    print("%s: %s" % ("CONTROL" if args.control else "SUBJECT",
                      "as expected" if ok else "NOT as expected"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
