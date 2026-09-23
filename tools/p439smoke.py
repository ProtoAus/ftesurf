#!/usr/bin/env python3
"""
p439smoke.py -- driver for cfg/test/p439smoke.cfg: the smoke test that Patches
434, 435 and 436 compose on one save.

Each patch has its own arm (p434rew, p435pre, p436pend); this one stages a single
fixture that has all three of their properties at once -- TS_RUNNING, carrying
320 u/s, inside a STAGE box, with `pendarm 2` owed and no recording prefix -- and
grades the one read that says whether they interact correctly.

ftesurf/data/saves/bhop_eazy IS A SHARED FIXTURE (p415reset, p428hold, p434rew,
p435pre read it).  It is PARKED -- renamed, not copied -- and restored afterwards,
including when the run throws.  --keep leaves the staged tree.

    python tools/p439smoke.py [--exe ftesurf64.exe] [--control] [--grade-only]

Exit status 0 when every pre-registered prediction in the cfg header held.
"""
import argparse
import os
import re
import shutil
import subprocess
import sys
import time

ROOT = r"C:\FTESurf"
GAMEDIR = os.path.join(ROOT, "ftesurf")
SAVES = os.path.join(GAMEDIR, "data", "saves", "bhop_eazy")
PARK = SAVES + ".p439park"
FIXTURE = os.path.join(GAMEDIR, "cfg", "test", "p439smoke.txt")
SLOT = "save901"
CFG = "cfg/test/p439smoke.cfg"
LOG = os.path.join(GAMEDIR, "logs", "p439smoke.log")

PATS = {
    "state": r"timer: (\w+) on",
    "clock": r"\s(\d+:\d\d\.\d+)\s+pb",
    "practice": r"practice (\d)",
    "class": r"class: (\w+) \(seg",
    # `stopped %g at %s`: the FIRST number is TF_STOPPED, the second is run_t_stopat
    # -- the time SV_TimerVoid parked.  SV_TimerIdle zeroes the flags and not the
    # stopat, so an IDLE report reads `stopped 0 at 0:05.000` and the parked time
    # is the observable (p434rew reads `stopped 1` because it never went idle).
    "stopped": r"stopped \d at (\S+)",
    "recording": r"recording (\d)",
    "buffer": r"recorder: buffer (-?\d+)",
    "stagerun": r"stagerun (\d)",
    "cancelled": r"(run cancelled \(the save's recording could not be restored\))",
    "velocity": r"velocity (-?[\d.]+) (-?[\d.]+) (-?[\d.]+)\s+horizontal (-?[\d.]+)",
    "origin": r"setpos (-?[\d.]+) (-?[\d.]+) (-?[\d.]+)",
}

# Both builds, measured.  The fixture carries no velocity: a body at rest inside a
# stage box stays there, which is what makes S3 a stable read rather than a race
# against gravity and friction (a 320 u/s row bled to 0 in ~0.4 s and the body slid
# 80 u before the first viewpos answered).
FIXED = {
    "S1": {"cancelled": "run cancelled (the save's recording could not be restored)",
           "state": "idle", "clock": "0:00.000", "stopped": "0:05.000",
           "recording": "0", "buffer": "-1"},
    "S2": {"state": "armed", "stagerun": "1", "clock": "0:05.000"},
    "S3": {"origin": "2624.0 512.0 64.0"},
}
CONTROL = {
    "S1": {"cancelled": None, "state": "running", "practice": "1",
           "class": "segmented", "stagerun": "1", "recording": "0"},
    "S2": {"state": "finished", "practice": "1", "class": "segmented"},
    "S3": {"origin": "2624.0 512.0 64.0"},
}
# S2 is where the two builds part, and the line that grades the composition:
# the control build sits in FINISHED with the pendarm still owed and spends it into
# a CLEAN stage run (practice 0) at the next scan; the fixed build drops the
# pendarm, so the re-arm is a fresh ARMED one from the stage box the body stands in
# and the stopped clock it inherits reads practice 0 too -- but it never passed
# through FINISHED-with-a-pendarm, and S1's void is what proves the recorder side.
DISCRIMINATOR = {
    "control": ("S2", "state", "finished"),
    "fixed": ("S2", "state", "armed"),
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


def sections(path):
    with open(path, "r", errors="replace") as fh:
        lines = fh.read().splitlines()
    out, cur = {}, None
    for line in lines:
        m = re.search(r"(?:----|====) ([A-Za-z][A-Za-z0-9]{0,3}) ", line)
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
    m = ms[-1]
    if key == "velocity":
        return m.group(4)                      # the horizontal figure
    if key == "origin":
        return "%s %s %s" % m.groups()
    return m.group(1)


def grade(log, control):
    ok = True
    s = sections(log)
    want = CONTROL if control else FIXED
    print("observables (%s), %s predictions:"
          % (os.path.basename(log), "PRE-FIX" if control else "POST-FIX"))
    for tag in sorted(want):
        txt = s.get(tag)
        if txt is None:
            print("  %-3s SECTION ABSENT -- the cfg never reached it" % tag)
            ok = False
            continue
        for key, exp in want[tag].items():
            got = get(txt, key)
            if exp is None:                    # must NOT be present
                good = (got == "<absent>")
                exp = "<absent>"
            elif key == "velocity":
                try:
                    good = abs(float(got) - float(exp)) < 1.0
                except ValueError:
                    good = False
                exp = "~%s" % exp
            else:
                good = (got == exp)
            ok = ok and good
            print("  %-3s %-11s %-46s %s"
                  % (tag, key, got, "ok" if good else "MISMATCH, want %s" % exp))
    return ok


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--exe", default="ftesurf64.exe")
    ap.add_argument("--control", action="store_true",
                    help="grade against the PRE-fix predictions (434/435/436 absent)")
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
