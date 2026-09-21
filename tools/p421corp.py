#!/usr/bin/env python3
"""Drive Patch 421's v9 angle corpus: one dedicated server, N client runs.

    cd C:\\FTESurf && python tools/p421corp.py --out <dir>

Each variant is one client process with a different cl_maxfps / cl_yawspeed /
cl_pitchspeed, running cfg/test/p421corp.cfg against cfg/test/p421sv.cfg's
server.  The pair it produces is collected under <dir>/<variant>/ and measured
by tools/reccheck.py.

WHY ONE PROCESS PER VARIANT.  A finished run's recording lands at
data/runs/<map>/main/cheat.rec under a FIXED name (SV_RecFinalPath; only an
archived tag gets a stamp, and a setpos route is always RT_CHEAT), so a second
run in the same session overwrites the first.  The sidecars do not collide --
they upload to data/evidence/<map>/<runid>.view -- so it is only the recording
that forces the batch apart.  Collect between processes and the pairing is by
construction rather than by guess.

THE TREE'S OWN data/runs/bhop_eazy IS PARKED FOR THE DURATION and restored at
the end, including on Ctrl-C: cheat.rec there is one of the 339 corpus pairs
and the first variant would overwrite it.  See the harness-hygiene rule in
AGENTS.md.
"""
import argparse
import os
import shutil
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GAME = os.path.join(ROOT, "ftesurf")
MAP = "bhop_eazy"
PORT = 27696
SVEXE = r"C:\FTEQuake\fteqwsv64.exe"
CLEXE = os.path.join(ROOT, "ftesurf64.exe")

RUNS = os.path.join(GAME, "data", "runs", MAP)
PARK = RUNS + ".p421park"
EVID = os.path.join(GAME, "data", "evidence", MAP)

# maxfps against a 100 Hz mover is the axis the join lives on: 0.3 frames per
# tick up to 5.  yawspeed/pitchspeed set how far the camera moves INSIDE one
# tick, which is the denominator of the normalised residual.
#
# THE WORST HONEST CASE IS NOT THE HIGHEST FRAMERATE, which is why f110 is here.
# Below the mover rate the client builds one usercmd per rendered frame and the
# two angles are the same number, so the residual is the wire quantum.  Above
# it, the packet goes out between frames and carries angles CL_AdjustAngles has
# moved on since the last one -- by at most one frame interval.  Normalised by
# the tick's own sweep that is mover_rate/fps, so it is WORST just above the
# mover rate and falls away as the framerate climbs: ~0.9 at 110 fps, ~0.4 at
# 250, ~0.2 at 500.  Measured at w=1 and w=2 join windows as well: widening the
# tick group does not reduce it, so it is the usercmd's sampling instant and
# not the join.
VARIANTS = [
    ("base",  100, 140, 150),   # p420live's own settings -- the replication
    ("f030",   30, 140, 150),   # far under the mover: most ticks have no frame
    ("f050",   50, 140, 150),
    ("f110",  110, 140, 150),   # THE PREDICTED WORST CASE -- see below
    ("f150",  150, 140, 150),
    ("f250",  250, 140, 150),   # over the mover: the join must pick a frame
    ("f500",  500, 140, 150),
    ("flick", 100, 900, 600),   # ~9 deg of yaw inside a single tick
    ("crawl",  73,  25,  30),   # a framerate that divides nothing, a slow pan
    # THE TWO THAT DECIDE THE CUT.  Every variant above holds the sweep rate
    # fixed while the framerate moves, so none of them says whether the
    # residual is a fixed number of degrees or a fixed fraction of the tick's
    # own sweep -- and the normalised statistic is only meaningful if it is the
    # second.  These cross the two axes at the framerate that showed the
    # residual at all.
    ("xfast", 250, 900, 600),
    ("xslow", 250,  25,  30),
    # AND THE EXTREME, because xfast put ONE move of 1738 at 1.49 normalised --
    # above the whole pre-v9 corpus's worst of 1.24 -- and a single boundary
    # event that scales with turn rate is the shape that eventually crosses a
    # cut.  2000 deg/s is faster than +left can be driven usefully and stands
    # in for a mouse flick.  PREDICTED: the outlier scales to ~3.3, so one or
    # two moves land past ANG_CUT and the verdict stays ok anyway, because 2 of
    # 1738 is 0.1% against a 5% rule and is not consecutive.
    ("xmad",  250, 2000, 1200),
]


def minimized():
    if os.name != "nt":
        return None
    si = subprocess.STARTUPINFO()
    si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    si.wShowWindow = 7          # SW_SHOWMINNOACTIVE
    return si


def evidence():
    if not os.path.isdir(EVID):
        return set()
    return set(os.listdir(EVID))


def park():
    if os.path.isdir(PARK):
        sys.exit("%s already exists -- an earlier run did not restore. Move it "
                 "back by hand before starting another." % PARK)
    if os.path.isdir(RUNS):
        os.rename(RUNS, PARK)
        print("parked %s" % RUNS)


def restore():
    if not os.path.isdir(PARK):
        return
    if os.path.isdir(RUNS):
        shutil.rmtree(RUNS)
    os.rename(PARK, RUNS)
    print("restored %s" % RUNS)


def collect(name, out, before, settle=6.0):
    """The run's three files, joined by the runid the receipt names."""
    dst = os.path.join(out, name)
    os.makedirs(dst, exist_ok=True)
    rid = None
    for _ in range(int(settle * 2)):
        new = sorted(f for f in evidence() - before if f.endswith(".rcpt"))
        if new:
            rid = new[-1][:-5]
            break
        time.sleep(0.5)
    if rid is None:
        print("  %-5s NO RECEIPT -- the run did not end on the server" % name)
        return None
    got = {}
    for ext in ("rcpt", "view"):
        src = os.path.join(EVID, "%s.%s" % (rid, ext))
        if os.path.exists(src):
            shutil.copy2(src, os.path.join(dst, "%s.%s" % (rid, ext)))
            got[ext] = src
    rec = os.path.join(RUNS, "main", "cheat.rec")
    if os.path.exists(rec):
        shutil.copy2(rec, os.path.join(dst, "%s.rec" % rid))
        got["rec"] = rec
    log = os.path.join(GAME, "logs", "p421corp.log")
    if os.path.exists(log):
        shutil.copy2(log, os.path.join(dst, "client.log"))
    print("  %-5s %s  %s" % (name, rid, " ".join(sorted(got))))
    return rid if {"rec", "view"} <= set(got) else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(ROOT, "report", "p421corp"))
    ap.add_argument("--only", help="comma-separated variant names")
    ap.add_argument("--wait", type=float, default=150.0,
                    help="seconds to allow one client run")
    args = ap.parse_args()

    want = VARIANTS
    if args.only:
        keep = set(args.only.split(","))
        want = [v for v in VARIANTS if v[0] in keep]
    os.makedirs(args.out, exist_ok=True)

    park()
    sv = None
    made = []
    try:
        sv = subprocess.Popen(
            [SVEXE, "+set", "sv_port", str(PORT), "+set", "sv_public", "0",
             "+set", "log_enable", "1", "+set", "log_dir", "logs",
             "+set", "log_name", "p421sv", "+map", MAP,
             "+exec", "cfg/test/p421sv.cfg"],
            cwd=ROOT, startupinfo=minimized())
        print("server %d starting on %d" % (sv.pid, PORT))
        time.sleep(18.0)            # prop lighting, then the map
        if sv.poll() is not None:
            sys.exit("the server exited during map load -- read "
                     "ftesurf/logs/p421sv.log")

        for name, fps, yaw, pitch in want:
            print("%s: cl_maxfps %g cl_yawspeed %g cl_pitchspeed %g"
                  % (name, fps, yaw, pitch))
            before = evidence()
            cl = subprocess.Popen(
                [CLEXE, "+set", "cl_maxfps", str(fps),
                 "+set", "cl_yawspeed", str(yaw),
                 "+set", "cl_pitchspeed", str(pitch),
                 "+exec", "cfg/test/p421corp.cfg"],
                cwd=ROOT, startupinfo=minimized())
            try:
                cl.wait(timeout=args.wait)
            except subprocess.TimeoutExpired:
                print("  %-5s TIMED OUT -- killing" % name)
                cl.kill()
                cl.wait(timeout=20)
            rid = collect(name, args.out, before)
            if rid:
                made.append((name, rid))
    finally:
        if sv is not None and sv.poll() is None:
            sv.terminate()
            try:
                sv.wait(timeout=20)
            except subprocess.TimeoutExpired:
                sv.kill()
        restore()

    print("\n%d of %d variants produced a .rec/.view pair" % (len(made), len(want)))
    for name, rid in made:
        print("  %-5s %s" % (name, rid))
    return 0 if len(made) == len(want) else 1


if __name__ == "__main__":
    sys.exit(main())
