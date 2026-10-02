#!/usr/bin/env python3
"""p471list.py -- driver and grader for cfg/test/p471list.cfg (Patch 471:
`sl_list` shows the speed the start-box gate reads).

Stages four saves (save971-974) under ftesurf/data/saves/<map>, built from
cfg/test/p441rest.txt with the map, origin and velocity rewritten, runs the cfg,
grades `cmd sl_list`, and puts the directory back as it found it: a save root
that already existed is PARKED (renamed) for the run and restored; one that did
not is removed, along with any parent this created.  The tree is listed after.

    python tools/p471list.py [--exe ftesurf64.exe] [--grade-only] [--timeout 240]

Exit 0 pass, 1 fail, 2 cannot grade.

RESULT (2026-10-03, the N100 laptop, surf_colin_blaster_69000):
  fixed   qwprogs 271B367694668A3E: L1 and L2 pass --
            0.6 u/s at rest / 1.0 u/s at rest / 1.1 u/s / 1.4 u/s
  control F53EBB0795E4E7F5 (game 80ba8c2): both fail -- every row `1 u/s`.
  The 0.99 row prints `1.0 u/s at rest`: one decimal alone still hides the side
  of the line a row is on, which is why the gate's answer is printed too.
"""
import argparse
import hashlib
import os
import re
import shutil
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GAMEDIR = os.path.join(ROOT, "ftesurf")
MAP = "surf_colin_blaster_69000"
SAVES = os.path.join(GAMEDIR, "data", "saves", MAP)
PARK = SAVES + ".savepark"
LOG = os.path.join(GAMEDIR, "logs", "p471list.log")
TEMPLATE = os.path.join(GAMEDIR, "cfg", "test", "p441rest.txt")
# slot -> velocity.  |v| 0.6, 0.99, 1.06, 1.4: the gate arms below 1.
ROWS = (("971", (0.6, 0.0, 0.0)), ("972", (0.7, 0.7, 0.0)),
        ("973", (0.75, 0.75, 0.0)), ("974", (0.0, 1.0, 0.98)))
ARM = 1.0                                   # SL_ARM_SPEED, sv_saveloc.qc


def speed(v):
    return (v[0] ** 2 + v[1] ** 2 + v[2] ** 2) ** 0.5


def stage():
    if os.path.exists(PARK):
        raise SystemExit("refusing: %s exists (a previous run did not restore)" % PARK)
    made = []
    for d in (os.path.dirname(os.path.dirname(SAVES)), os.path.dirname(SAVES)):
        if not os.path.isdir(d):
            os.mkdir(d)
            made.append(d)
    if os.path.isdir(SAVES):
        os.rename(SAVES, PARK)
    os.mkdir(SAVES)
    tmpl = open(TEMPLATE, "r").read().splitlines()
    for n, (slot, v) in enumerate(ROWS):
        out = []
        for line in tmpl:
            k = line.split(" ", 1)[0]
            if k == "map":
                line = "map " + MAP
            elif k == "seq":
                line = "seq %d" % (n + 1)
            elif k == "origin":
                line = "origin 0.0000 0.0000 %.4f" % (64 * (n + 1))
            elif k == "velocity":
                line = "velocity %.4f %.4f %.4f" % v
            elif k == "state":
                line = "state 0"
            out.append(line)
        os.mkdir(os.path.join(SAVES, "save" + slot))
        with open(os.path.join(SAVES, "save" + slot, "state.txt"), "w", newline="\n") as f:
            f.write("\n".join(out) + "\n")
    return made


def restore(made):
    left = sorted(os.path.relpath(os.path.join(dp, f), GAMEDIR)
                  for dp, _, fs in os.walk(SAVES) for f in fs)
    print("save root after the run: %s" % ", ".join(left))
    shutil.rmtree(SAVES)
    if os.path.isdir(PARK):
        os.rename(PARK, SAVES)
    for d in reversed(made):
        os.rmdir(d)                          # empty, or the error is the result
    print("restored: %s %s" % (os.path.relpath(SAVES, GAMEDIR),
                               "back from its park" if os.path.isdir(SAVES)
                               else "absent, as it was"))


def run(exe, timeout):
    if os.path.exists(LOG):
        os.remove(LOG)
    flags = 0x08000000 if os.name == "nt" else 0
    p = subprocess.Popen([os.path.join(ROOT, exe), "-WindowStyle", "Minimized",
                          "+exec", "test/p471list.cfg"], cwd=ROOT,
                         creationflags=flags, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL)
    t0 = time.time()
    while p.poll() is None and time.time() - t0 < timeout:
        time.sleep(1)
    if p.poll() is None:
        p.kill()
        print("the run did not exit in %g s -- killed" % timeout)


def grade():
    if not os.path.exists(LOG):
        print("CANNOT GRADE: no log")
        return 2
    txt = open(LOG, "r", errors="replace").read()
    if "=== p471list done ===" not in txt:
        print("CANNOT GRADE: the run did not reach its end")
        return 2
    sect = txt.split("=== p471list list ===", 1)[-1]
    fails = 0
    l1, l2 = [], []
    for slot, v in ROWS:
        m = re.search(r"slot %s(?:\s+-?\d+){3}\s+([\d.]+) u/s( at rest)?" % slot, sect)
        if not m:
            print("CANNOT GRADE: no row for slot %s in the list" % slot)
            return 2
        want = speed(v)
        if abs(float(m.group(1)) - want) > 0.051:
            l1.append("slot %s printed %s, carries %.3f" % (slot, m.group(1), want))
        if bool(m.group(2)) != (want < ARM):
            l2.append("slot %s (%.3f u/s) %s" % (slot, want,
                      "says at rest" if m.group(2) else "does not say at rest"))
    for name, bad, text in (("L1", l1, "each row's own speed, to one decimal"),
                            ("L2", l2, "`at rest` on exactly the rows under 1 u/s")):
        fails += 1 if bad else 0
        print("%s %s  %s%s" % ("FAIL" if bad else "PASS", name, text,
                               "  (" + "; ".join(bad) + ")" if bad else ""))
    print("2 check(s), %d failed" % fails)
    return 1 if fails else 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--exe", default="ftesurf64.exe")
    ap.add_argument("--grade-only", action="store_true")
    ap.add_argument("--timeout", type=float, default=240)
    a = ap.parse_args()
    if not a.grade_only:
        with open(os.path.join(GAMEDIR, "qwprogs.dat"), "rb") as f:
            print("qwprogs %s" % hashlib.sha256(f.read()).hexdigest()[:16].upper())
        made = stage()
        try:
            run(a.exe, a.timeout)
        finally:
            restore(made)
    return grade()


if __name__ == "__main__":
    sys.exit(main())
