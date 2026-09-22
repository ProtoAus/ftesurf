#!/usr/bin/env python3
"""
p434rew.py -- driver for cfg/test/p434rew.cfg (Patch 434: a save whose
recording cannot be restored ends the run).

WHY A DRIVER.  The subject is a save whose run.rec is MISSING, and the control
is a real save taken by the same run.  Nothing in a cfg can delete a file, and
a fixture committed as a directory would have to be copied into the live save
tree by hand -- so this stages cfg/test/p434state.txt as
data/saves/bhop_eazy/save901/state.txt, runs the cfg, reads the observables out
of the log, and puts the tree back.

ftesurf/data/saves/bhop_eazy IS A SHARED FIXTURE (p415reset, p428hold read it).
It is PARKED -- renamed, not copied -- for the run and restored afterwards,
including when the run throws.  Pass --keep to leave the staged tree in place.

    python tools/p434rew.py [--exe ftesurf64.exe] [--control] [--grade-only]

--control runs the same cfg against whatever exe you name, which is how the
pre-fix build is measured: copy sv_saveloc.qc aside, `git checkout --` it,
`pwsh -NoProfile -Command "./build.ps1 -Jobs 8"` from src/, run this with
--exe ftesurf64.exe --control, copy the file back, rebuild, run again.

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
SAVES = os.path.join(ROOT, "ftesurf", "data", "saves", "bhop_eazy")
PARK = SAVES + ".p434park"
FIXTURE = os.path.join(ROOT, "ftesurf", "cfg", "test", "p434state.txt")
CFG = "cfg/test/p434rew.cfg"
LOG = os.path.join(ROOT, "ftesurf", "logs", "p434rew.log")


def stage():
    """Park the shared fixture and put save901 in its place."""
    if os.path.isdir(PARK):
        raise SystemExit("refusing: %s already exists (a previous run did not restore)" % PARK)
    if os.path.isdir(SAVES):
        os.rename(SAVES, PARK)
    os.makedirs(os.path.join(SAVES, "save901"))
    shutil.copyfile(FIXTURE, os.path.join(SAVES, "save901", "state.txt"))


def restore(keep):
    if keep:
        print("--keep: staged tree left at %s" % SAVES)
        return
    if os.path.isdir(SAVES):
        shutil.rmtree(SAVES)
    if os.path.isdir(PARK):
        os.rename(PARK, SAVES)


def run(exe, timeout):
    # The basedir is the cwd, so this must not inherit a shell left in ftesurf/.
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


def blocks(path):
    """{arm: text} from the cfg's own `==== <arm> ` echoes, so a rerun's
    appended lines and an earlier arm's report cannot be read for a later one."""
    with open(path, "r", errors="replace") as fh:
        txt = fh.read()
    out, cur = {}, None
    for line in txt.splitlines():
        m = re.search(r"==== (\S+)\b", line)
        if m:
            cur = m.group(1)
            out[cur] = []
        elif cur:
            out[cur].append(line)
    return {k: "\n".join(v) for k, v in out.items()}


def field(txt, pat):
    m = re.search(pat, txt, re.M)
    return m.group(1) if m else "<absent>"


def grade(log, control):
    ok = True
    b = blocks(log)

    def show(label, got, want):
        nonlocal ok
        good = (got == want) if want is not None else (got != "<absent>")
        ok = ok and good
        print("  %-42s %-34s %s"
              % (label, got, "ok" if good else "MISMATCH, want %s" % want))

    print("observables (%s), %s predictions:"
          % (os.path.basename(log), "PRE-FIX" if control else "POST-FIX"))
    # C2 is the arm that makes S mean anything: a running save this harness can
    # load at all.  If it does not resume, S reading "idle" proves nothing.
    c2 = b.get("C2", "")
    show("C2 resumed line", field(c2, r"(save 2 -- run resumed at \S+),"), None)
    show("C2 timer state", field(c2, r"timer: (\w+) on"), "running")
    show("C2 shadow", field(c2, r"shadow (\d+)"), "1")
    show("C2 recording", field(c2, r"recording (\d)"), "1")
    show("C2 buffer", field(c2, r"recorder: buffer (-?\d+)"), None)
    s = b.get("S", "")
    show("S cancel line", field(s, r"(run cancelled \(the save's recording could not be restored\))"),
         None if not control else "<absent>")
    show("S timer state", field(s, r"timer: (\w+) on"), "running" if control else "idle")
    # The fixture's own clock is ticks 500 at the 0.01 rate = 0:05.000.  Pre-fix
    # the run kept counting after the load, so the report reads PAST it (0:06.200
    # in the control run) -- that drift, not the value, is the defect.
    clk = field(s, r"\s(\d+:\d\d\.\d+)\s+pb")
    try:
        mm, ss = clk.split(":")
        secs = float(mm) * 60 + float(ss)
    except ValueError:
        secs = -1
    if control:
        good = secs > 5.0
        print("  %-42s %-34s %s"
              % ("S clock", clk, "ok, past the restored 0:05.000"
                 if good else "MISMATCH, the clock did not advance"))
    else:
        show("S clock", clk, "0:05.000")
    ok = ok and (secs > 5.0 if control else clk == "0:05.000")
    show("S recording", field(s, r"recording (\d)"), "0")
    show("S buffer", field(s, r"recorder: buffer (-?\d+)"), "-1")
    show("S stopped", field(s, r"stopped (\d) at (\S+)"),
         "0" if control else "1")
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
