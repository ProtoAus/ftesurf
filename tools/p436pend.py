#!/usr/bin/env python3
"""
p436pend.py -- driver for cfg/test/p436pend.cfg (Patch 436: a restored `pendarm`
does not hand back a clean stage run).

WHY A DRIVER.  The subject is a save whose `pendarm` names a stage box on the
other side of the map, so the handover's own condition (`!SV_ZoneIn(pendarm, p,
hull)`) is true on the first scan after the load.  Nothing in a cfg can write
that file, so this stages cfg/test/p436state.txt as
data/saves/bhop_eazy/save901/state.txt, runs the cfg, reads the observables out
of the log, and puts the tree back.

ftesurf/data/saves/bhop_eazy IS A SHARED FIXTURE (p415reset, p428hold, p434rew,
p435pre read it).  It is PARKED -- renamed, not copied -- and restored
afterwards, including when the run throws.  --keep leaves the staged tree.

    python tools/p436pend.py [--exe ftesurf64.exe] [--control] [--grade-only]

--control grades the PRE-fix predictions: copy sv_saveloc.qc aside, `git checkout
--` it, build, run this with --control, copy back, rebuild, run again.

Exit status 0 when every pre-registered prediction in the cfg header held.
"""
import argparse
import os
import re
import shutil
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GAMEDIR = os.path.join(ROOT, "ftesurf")
SAVES = os.path.join(GAMEDIR, "data", "saves", "bhop_eazy")
PARK = SAVES + ".p436park"
FIXTURE = os.path.join(GAMEDIR, "cfg", "test", "p436state.txt")
SLOT = "save901"
CFG = "cfg/test/p436pend.cfg"
LOG = os.path.join(GAMEDIR, "logs", "p436pend.log")

PATS = {
    "state": r"timer: (\w+) on",
    "pendarm": r"pending arm (-?\d+)",
    "practice": r"practice (\d)",
    "class": r"class: (\w+) \(seg",
    "stagerun": r"stagerun (\d)",
    "clock": r"\s(\d+:\d\d\.\d+)\s+pb",
}


def stage():
    if os.path.isdir(PARK):
        raise SystemExit("refusing: %s already exists (a previous run did not restore)" % PARK)
    if os.path.isdir(SAVES):
        os.rename(SAVES, PARK)
    os.makedirs(os.path.join(SAVES, SLOT))
    shutil.copyfile(FIXTURE, os.path.join(SAVES, SLOT, "state.txt"))


def restore(keep):
    if keep:
        print("--keep: staged tree left at %s" % SAVES)
        return
    if os.path.isdir(SAVES):
        shutil.rmtree(SAVES)
    if os.path.isdir(PARK):
        os.rename(PARK, SAVES)


def run(exe, timeout):
    if os.path.exists(LOG):
        os.remove(LOG)
    flags = 0x08000000 if os.name == "nt" else 0     # CREATE_NO_WINDOW
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


def sections(path):
    """{tag: text} keyed by the cfg's own `---- <tag> ` / `==== <arm> ` echoes."""
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


def get(txt, key):
    ms = list(re.finditer(PATS[key], txt, re.M))
    if not ms:
        return "<absent>"
    return ms[-1].group(1)


# The fixture's own numbers: state 3 = TS_FINISHED, ticks 300 at the 0.01 rate.
# `pendarm` is NOT a discriminator and is reported rather than expected: the
# fixed build drops it at the load (-1) and the control build spends it on the
# arm (-1), so both read -1 and only the state, the class and the clock differ.
FIXED = {
    "P1": {"state": "finished", "practice": "1",
           "class": "segmented", "clock": "0:03.000"},
    "P2": {"state": "finished", "practice": "1", "class": "segmented"},
}
# The control build needs TWO packets: the load's own packet restores FINISHED
# with the pendarm still standing (P1 reads `pending arm 2`), and the next scan
# spends it.  So the pre-fix predictions are graded on P2, and P1's pre-fix
# readings are reported as the handover's own footprint.
CONTROL = {
    "P2": {"state": "running", "practice": "0", "class": "clean", "stagerun": "1"},
}
CONTROL_REPORT = {"P1": ("state", "pendarm", "practice", "class")}


def grade(log, control):
    ok = True
    s = sections(log)
    want = CONTROL if control else FIXED
    report = CONTROL_REPORT if control else {}
    print("observables (%s), %s predictions:"
          % (os.path.basename(log), "PRE-FIX" if control else "POST-FIX"))
    for tag in sorted(set(list(want) + list(report))):
        txt = s.get(tag)
        if txt is None:
            print("  %-4s SECTION ABSENT -- the cfg never reached it" % tag)
            ok = False
            continue
        pairs = list(want.get(tag, {}).items())
        pairs += [(k, None) for k in report.get(tag, ())
                  if k not in want.get(tag, {})]
        for key, exp in pairs:
            got = get(txt, key)
            if exp is None:
                print("  %-4s %-11s %-24s reported" % (tag, key, got))
                continue
            good = (got == exp)
            ok = ok and good
            print("  %-4s %-11s %-24s %s"
                  % (tag, key, got, "ok" if good else "MISMATCH, want %s" % exp))
        if not control and tag in ("P1", "P2"):
            print("  %-4s %-11s %-24s reported"
                  % (tag, "pendarm", get(txt, "pendarm")))
    # P3 is the control for the gesture and is graded the same on both builds: a
    # real save taken by this run must come back, and must not be wearing the
    # fixture's pending arm.
    txt = s.get("P3")
    if txt is None:
        print("  P3   SECTION ABSENT -- the cfg never reached it")
        return False
    got = get(txt, "state")
    resumed = "resumed" in txt or got in ("armed", "running")
    print("  %-4s %-11s %-24s %s" % ("P3", "pendarm", get(txt, "pendarm"), "reported"))
    print("  %-4s %-11s %-24s %s" % ("P3", "restored", got,
                                      "ok" if resumed else "MISMATCH, a real save did not restore"))
    ok = ok and resumed
    return ok


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--exe", default="ftesurf64.exe")
    ap.add_argument("--control", action="store_true",
                    help="grade against the PRE-fix predictions")
    ap.add_argument("--timeout", type=float, default=180)
    ap.add_argument("--keep", action="store_true")
    ap.add_argument("--grade-only", action="store_true",
                    help="grade the log already on disk; stage and run nothing")
    a = ap.parse_args()

    if a.grade_only:
        if not os.path.exists(LOG):
            raise SystemExit("no log at %s" % LOG)
        return 0 if grade(LOG, a.control) else 1

    if not os.path.exists(FIXTURE):
        raise SystemExit("no fixture: %s" % FIXTURE)
    stage()
    try:
        secs = run(a.exe, a.timeout)
    finally:
        restore(a.keep)
    print("ran %s for %.0f s" % (a.exe, secs))
    if not os.path.exists(LOG):
        raise SystemExit("no log at %s -- was the cwd C:\\FTESurf?" % LOG)
    return 0 if grade(LOG, a.control) else 1


if __name__ == "__main__":
    sys.exit(main())
