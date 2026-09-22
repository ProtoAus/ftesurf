#!/usr/bin/env python3
"""
p436hand.py -- driver for cfg/test/p436hand.cfg against cfg/test/p436sv.cfg
(Patch 436's other half: the legitimate stage handover must not move).

Two processes, so this owns both: the dedicated server on 27666 (C:\\FTEQuake's
binary, started from C:\\FTESurf so the basedir is right) and the client.  Ports
and processes are checked before starting, because a second server on a port
another one holds logs "Server spawned" and then sees no clients at all -- the
connect goes to the incumbent and the run lands in the OTHER log file.

    python tools/p436hand.py [--exe ftesurf64.exe] [--grade-only]

Exit status 0 when the handover fired.  Grade the same log on HEAD~ with
--grade-only to see that the predictions are identical on both builds, which is
the point of the arm.
"""
import argparse
import os
import re
import socket
import subprocess
import sys
import time

ROOT = r"C:\FTESurf"
GAMEDIR = os.path.join(ROOT, "ftesurf")
SVEXE = r"C:\FTEQuake\fteqwsv64.exe"
PORT = 27666
SVLOG = os.path.join(GAMEDIR, "logs", "p436sv.log")
CLLOG = os.path.join(GAMEDIR, "logs", "p436hand.log")


def port_free(port):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.bind(("127.0.0.1", port))
        return True
    except OSError:
        return False
    finally:
        s.close()


def start(cmd):
    return subprocess.Popen(cmd, cwd=ROOT, creationflags=0x08000000,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def sections(path):
    with open(path, "r", errors="replace") as fh:
        lines = fh.read().splitlines()
    out, cur = {}, None
    for line in lines:
        m = re.search(r"(?:----|====) ([A-Z][A-Z0-9]{0,3}) ", line)
        if m:
            cur = m.group(1)
            out.setdefault(cur, [])
        elif cur:
            out[cur].append(line)
    return {k: "\n".join(v) for k, v in out.items()}


PATS = {
    "state": r"timer: (\w+) on",
    "stagerun": r"stagerun (\d)",
    "pendarm": r"pending arm (-?\d+)",
    "practice": r"practice (\d)",
    "class": r"class: (\w+) \(seg",
    "clock": r"\s(\d+:\d\d\.\d+)\s+pb",
}


def get(txt, key):
    ms = list(re.finditer(PATS[key], txt, re.M))
    if not ms:
        return "<absent>"
    return ms[-1].group(1)


# Identical on both builds: this arm exists to NOT MOVE.  `pending arm` is the
# handover's own footprint -- owed at G2 (the crossing) and spent at G3 (the step
# out), which is the pair that proves the live path still runs end to end.
EXPECT = {
    "G1": {"stagerun": "1", "pendarm": "-1"},
    "G2": {"state": "finished", "pendarm": "1"},
    "G3": {"state": "running", "stagerun": "1", "pendarm": "-1"},
    "G4": {"state": "running", "stagerun": "1"},
}
REPORT = {"G2": ("clock",), "G3": ("practice", "class", "clock"),
          "G1": ("state", "practice", "class")}


def grade(log):
    ok = True
    s = sections(log)
    print("observables (%s):" % os.path.basename(log))
    for tag in sorted(set(list(EXPECT) + list(REPORT))):
        txt = s.get(tag)
        if txt is None:
            print("  %-3s SECTION ABSENT -- the cfg never reached it" % tag)
            ok = False
            continue
        pairs = list(EXPECT.get(tag, {}).items())
        pairs += [(k, None) for k in REPORT.get(tag, ()) if k not in EXPECT.get(tag, {})]
        for key, exp in pairs:
            got = get(txt, key)
            if exp is None:
                print("  %-3s %-10s %-22s reported" % (tag, key, got))
                continue
            good = (got == exp)
            ok = ok and good
            print("  %-3s %-10s %-22s %s"
                  % (tag, key, got, "ok" if good else "MISMATCH, want %s" % exp))
    return ok


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--exe", default="ftesurf64.exe")
    ap.add_argument("--timeout", type=float, default=180)
    ap.add_argument("--grade-only", action="store_true")
    a = ap.parse_args()

    if a.grade_only:
        if not os.path.exists(CLLOG):
            raise SystemExit("no log at %s" % CLLOG)
        return 0 if grade(CLLOG) else 1

    if not os.path.exists(SVEXE):
        raise SystemExit("no server binary: %s" % SVEXE)
    if not port_free(PORT):
        raise SystemExit("port %d is held -- a server on it would take the connect "
                         "and this run would read the incumbent's log" % PORT)
    for p in (SVLOG, CLLOG):
        if os.path.exists(p):
            os.remove(p)

    sv = start([SVEXE, "+set", "sv_port", str(PORT), "+set", "sv_public", "0",
                "+set", "lobby_master", "", "+map", "bhop_eazy",
                "+exec", "cfg/test/p436sv.cfg"])
    print("server started on %d, waiting 14 s for the map" % PORT)
    time.sleep(14)
    if sv.poll() is not None:
        raise SystemExit("the server exited early (%d) -- see %s" % (sv.returncode, SVLOG))
    cl = start([os.path.join(ROOT, a.exe), "-WindowStyle", "Minimized",
                "+exec", "cfg/test/p436hand.cfg"])
    t0 = time.time()
    try:
        while time.time() - t0 < a.timeout:
            if cl.poll() is not None:
                break
            time.sleep(1)
        if cl.poll() is None:
            print("the client did not exit in %.0f s -- killing" % (time.time() - t0))
            cl.kill()
    finally:
        if sv.poll() is None:
            sv.kill()
    print("client ran %.0f s" % (time.time() - t0))
    if not os.path.exists(CLLOG):
        raise SystemExit("no log at %s" % CLLOG)
    return 0 if grade(CLLOG) else 1


if __name__ == "__main__":
    sys.exit(main())
