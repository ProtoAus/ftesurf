#!/usr/bin/env python3
"""p466reget.py -- does the browser notice a WRONG BUILD, and can it replace one?

  python tools/p466reget.py            subject: plant a truncated shadow
  python tools/p466reget.py --control  control:  plant nothing

Patch 465 asked "is there a file of that name". Having a FILE and having the
RIGHT BUILD are different facts, and only the first was checked -- so the one
case the Download button could not help with was a wrong build, which is exactly
what a server kicks you for.

THE CONTROL IS THE POINT. A check that flags a correct install is worse than no
check: its action is a re-download, so a false positive spends the player's
bandwidth on a lie. The control plants nothing and the count must not move off
the pre-existing baseline; the subject plants ONE truncated shadow in
ftesurf/maps/ (which wins the mount) and the count must become baseline + 1.

THE BASELINE IS NOT ZERO ON THIS BOX and assuming it was would have made the
control meaningless. Two maps already differ -- surf_dune and surf_fantasy, the
CS:S builds lextest 2i flags -- so baseline() computes it and prints it. The
feature finding exactly those two, from file size, having been found originally
from hash attestation, is two independent methods agreeing.

AND A READING TAKEN BEFORE THE LIST LOADS IS NOT A READING. ui_load_maps is
lazy, so a bare ui_dlmap at startup reports `list 0` and a wrongbuild of 0 that
says nothing about the install. The first cut of this graded that reading and
the control "passed" while measuring nothing; the cfg now calls ui_maplist
first, and the grader discards any row whose list is 0.
"""

import argparse
import hashlib
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
CFG = "cfg/test/p466reget.cfg"
SRCCFG = os.path.join(GAME, "cfg", "test", "p466src.cfg")
LOG = os.path.join(GAME, "logs", "p466reget.log")

MAP = "surf_exxak"
MOMMAPS = (r"C:\Program Files (x86)\Steam\steamapps\common"
           r"\Momentum Mod Playtest\momentum\maps")
REAL = os.path.join(MOMMAPS, MAP + ".bsp")
SHADOW = os.path.join(GAME, "maps", MAP + ".bsp")
SHADOWTMP = os.path.join(GAME, "maps", MAP + ".tmp")

REQUESTS = []


def sha1(p):
    h = hashlib.sha1()
    with open(p, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


class Handler(http.server.BaseHTTPRequestHandler):
    throttle = 200000
    protocol_version = "HTTP/1.1"

    def log_message(self, *a):
        pass

    def _serve(self, body):
        want = re.fullmatch(r"/(?:ftesurf/)?maps/%s\.bsp" % re.escape(MAP), self.path)
        if not want:
            REQUESTS.append((self.path, 404))
            self.send_response(404)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        n = os.path.getsize(REAL)
        REQUESTS.append((self.path, 200))
        self.send_response(200)
        self.send_header("Content-Type", "application/octet-stream")
        self.send_header("Content-Length", str(n))
        self.end_headers()
        if not body:
            return
        chunk = max(4096, self.throttle // 8)
        with open(REAL, "rb") as fh:
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


def run_client(exe, timeout):
    # DELETE THE LOG FIRST -- FTE appends, so otherwise the grader reads the
    # other arm's lines too. p465dl's control failed this way once.
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


def grade(control, planted_kb, real_kb, base):
    if not os.path.exists(LOG):
        return False, ["no log at %s" % LOG]
    with open(LOG, "r", encoding="utf-8", errors="replace") as fh:
        log = fh.read()

    notes, ok = [], True

    if 'Unknown command "ui_dlmap"' in log:
        return False, ["the menu VM never started -- menu_restart did not take"]

    m = re.search(r"ui_dlmap: builtin (\w+)", log)
    if not m:
        return False, ["ui_dlmap printed nothing -- the arm did not run"]
    notes.append("builtin: %s" % m.group(1))
    if m.group(1) != "present":
        return False, notes + ["downloadmap did not bind"]

    # ONLY READINGS TAKEN AGAINST A LOADED LIST COUNT. ui_load_maps is lazy, so
    # a bare ui_dlmap before the browser has ever opened reports `list 0` -- and
    # a wrongbuild of 0 from an empty list says nothing about the install. The
    # first cut of this grader took wb[0], which was always that reading, so the
    # control "passed" by measuring nothing.
    rows = [(int(a), int(b), int(c)) for a, b, c in
            re.findall(r"offerable (\d+), wrongbuild (\d+), list (\d+)", log)]
    notes.append("readings (offerable, wrongbuild, list): %s" % (rows or "NONE"))
    if not rows:
        return False, notes + ["no wrongbuild figure -- menu.dat predates Patch 466"]
    loaded = [r for r in rows if r[2] > 0]
    if not loaded:
        return False, notes + ["every reading was taken against an EMPTY list "
                               "(list 0) -- ui_maplist did not load it, so this "
                               "measured nothing."]
    notes.append("graded on %d reading(s) with a loaded list" % len(loaded))
    first = loaded[0][1]

    lk = re.findall(r"localkb=(-?\d+)", log)
    notes.append("localkb reported: %s   (planted %s, real %s)"
                 % (lk or "NONE", planted_kb, real_kb))
    if lk and lk[0] == "-1":
        return False, notes + ["mapfilekb did not bind -- the engine predates Patch 466"]

    states = re.findall(r"ui_dlmap: builtin \w+, state (\d) \((\w+)\)", log)
    seq = [s[1] for s in states]
    notes.append("state sequence: %s" % " -> ".join(seq))

    have = os.path.exists(SHADOW)
    sz = os.path.getsize(SHADOW) if have else 0
    notes.append("ftesurf/maps/%s.bsp afterwards: %s%s"
                 % (MAP, have, " (%d bytes)" % sz if have else ""))
    notes.append("leftover .tmp: %s" % os.path.exists(SHADOWTMP))
    served = [r for r in REQUESTS if r[1] == 200]
    notes.append("http: %d served, %d refused" % (len(served), len(REQUESTS) - len(served)))

    if control:
        if first != base:
            ok = False
            notes.append("CONTROL FAILED: wrongbuild is %d, expected the "
                         "pre-existing %d. Planting nothing must not change the "
                         "count -- a check whose action is a re-download must "
                         "never accuse a correct install." % (first, base))
        if have:
            ok = False
            notes.append("CONTROL FAILED: a shadow exists in ftesurf/maps/; the "
                         "control plants none, so something wrote one.")
        if served:
            ok = False
            notes.append("CONTROL FAILED: the mirror served %d time(s). Nothing "
                         "should have been downloaded." % len(served))
    else:
        if first != base + 1:
            ok = False
            notes.append("SUBJECT FAILED: wrongbuild is %d, expected %d -- the "
                         "pre-existing %d plus the one planted shadow."
                         % (first, base + 1, base))
        if lk and int(lk[0]) != planted_kb:
            ok = False
            notes.append("SUBJECT FAILED: localkb reads %s but the planted "
                         "shadow is %d KB -- mapfilekb is not resolving through "
                         "the mount order." % (lk[0], planted_kb))
        if "ok" not in seq:
            ok = False
            notes.append("SUBJECT FAILED: never reached the ok state.")
        if not served:
            ok = False
            notes.append("SUBJECT FAILED: the mirror served nothing.")
        if os.path.exists(SHADOWTMP):
            ok = False
            notes.append("SUBJECT FAILED: a .tmp survived.")
        if not have:
            ok = False
            notes.append("SUBJECT FAILED: no file afterwards.")
        elif sz != os.path.getsize(REAL):
            ok = False
            notes.append("SUBJECT FAILED: %d bytes, real map is %d -- the "
                         "re-get did not replace the truncated shadow."
                         % (sz, os.path.getsize(REAL)))
        elif sha1(SHADOW) != sha1(REAL):
            ok = False
            notes.append("SUBJECT FAILED: same size, different sha1.")
        else:
            notes.append("sha1 matches the served file exactly")
    return ok, notes


def baseline():
    """How many installed maps ALREADY differ from the Pi, before we plant one.

    ftesurf/maps/ is the top mount (see AGENTS.md), so anything there whose
    rounded size differs from data/mapdl.txt is what the menu will flag. Maps in
    lower mounts cannot contribute here because mapdl.txt was generated from the
    Momentum install on this box, so those match by construction.

    On this box it is 2 -- surf_dune and surf_fantasy, the CS:S builds lextest
    2i flags. Computed rather than hardcoded so a changed tree is not a mystery.
    """
    dl = {}
    with open(os.path.join(GAME, "data", "mapdl.txt"), encoding="utf-8",
              errors="replace") as fh:
        for ln in fh:
            f = ln.split()
            if len(f) >= 8 and f[0] == "dl":
                dl[f[1].lower()] = int(f[5])
    n, who = 0, []
    d = os.path.join(GAME, "maps")
    for fn in sorted(os.listdir(d)):
        if not fn.lower().endswith(".bsp"):
            continue
        nm = fn[:-4]
        pkb = dl.get(nm.lower())
        if pkb is None:
            continue
        lkb = (os.path.getsize(os.path.join(d, fn)) + 1023) // 1024
        if lkb != pkb:
            n += 1
            who.append("%s (%d vs %d KB)" % (nm, lkb, pkb))
    return n, who


def cleanup(where):
    """Listed, not assumed -- a driver's cleanup is part of the arm."""
    left = []
    for p in (SHADOW, SHADOWTMP):
        if os.path.exists(p):
            os.remove(p)          # no except: a removal that fails must be loud
            left.append(os.path.basename(p))
    rest = sorted(os.path.basename(f) for f in
                  __import__("glob").glob(os.path.join(GAME, "maps", "*"))
                  if MAP in os.path.basename(f))
    print("cleanup (%s): removed %s; %s still matching %r: %s"
          % (where, left or "nothing", "files", MAP, rest or "none"))
    return rest


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--control", action="store_true")
    ap.add_argument("--exe", default="ftesurf64.exe")
    ap.add_argument("--timeout", type=float, default=150)
    args = ap.parse_args()

    if not os.path.exists(REAL):
        sys.exit("no %s to work from" % REAL)
    real_kb = (os.path.getsize(REAL) + 1023) // 1024

    cleanup("before")
    base, who = baseline()
    print("pre-existing wrong-build maps: %d%s"
          % (base, (" -- " + ", ".join(who)) if who else ""))

    planted_kb = 0
    if not args.control:
        # A truncated copy: a real bsp header so nothing rejects it out of hand,
        # but a size that cannot be the published build.
        n = os.path.getsize(REAL) // 2
        with open(REAL, "rb") as src, open(SHADOW, "wb") as dst:
            dst.write(src.read(n))
        planted_kb = (os.path.getsize(SHADOW) + 1023) // 1024
        print("planted a %d KB shadow (real map is %d KB)" % (planted_kb, real_kb))

    port = free_port()
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", port), Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    with open(SRCCFG, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("// written by tools/p466reget.py\n")
        fh.write('set sv_dlURL "http://127.0.0.1:%d"\n' % port)
        # The ONLY difference between the arms. The control must not force,
        # or it downloads a map it already has correctly and both arms look
        # the same -- which is how the first cut of this ran.
        fh.write('alias p466_act "ui_dlmap %s%s"\n'
                 % (MAP, "" if args.control else " force"))

    print("arm    : %s" % ("CONTROL (nothing planted)" if args.control else "SUBJECT"))
    took = run_client(args.exe, args.timeout)
    srv.shutdown()
    print("client ran %.1f s" % took)

    ok, notes = grade(args.control, planted_kb, real_kb, base)
    print()
    for n in notes:
        print("  " + n)
    print()
    leftover = cleanup("after")
    if leftover:
        ok = False
        print("  CLEANUP FAILED: %s" % leftover)
    print("%s: %s" % ("CONTROL" if args.control else "SUBJECT",
                      "as expected" if ok else "NOT as expected"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
