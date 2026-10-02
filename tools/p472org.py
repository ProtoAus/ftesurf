#!/usr/bin/env python3
"""p472org.py -- driver and grader for cfg/test/p472org.cfg (Patch 472: a load
refuses a save whose origin is not a place).

Stages three saves (save981-983) under ftesurf/data/saves/<map> from
cfg/test/p441rest.txt -- origin x 1e999 (stof gives inf), x 1e9, and a real one --
runs the cfg,
grades where each `sl_goto` left the body, and puts the save root back as it found
it (parked and restored if it existed, removed if not), listing it first.

    python tools/p472org.py [--exe ftesurf64.exe] [--grade-only] [--timeout 240]

Exit 0 pass, 1 fail, 2 cannot grade.

RESULT (2026-10-03, the N100 laptop, surf_colin_blaster_69000):
  fixed   qwprogs 34ECFDC6A1F6E80A: O1 and O2 pass -- rows 1 (inf) and 2 (x 1e9)
          both "that save's position is not a place on any map", body unmoved.
  control 271B367694668A3E (Patch 471): row 1 refused as "that save changed on
          disk" (SV_SaveRowIs: inf - inf is NaN), row 2 PLACED at x 1e9.
  First cut used `nan`: this laptop's msvcrt atof reads it as 0, so the row
  listed as 0 0 0 and loaded there -- on ucrt and glibc it is a real NaN.
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
LOG = os.path.join(GAMEDIR, "logs", "p472org.log")
TEMPLATE = os.path.join(GAMEDIR, "cfg", "test", "p441rest.txt")
# slot -> origin, as state.txt spells it.  Row order is the seq order.
ROWS = (("981", "1e999 0.0000 64.0000"), ("982", "1000000000.0000 0.0000 64.0000"),
        ("983", "-13968.0000 -80.0000 12800.0000"))
GOOD = (-13968.0, -80.0, 12800.0)


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
    for n, (slot, org) in enumerate(ROWS):
        out = []
        for line in tmpl:
            k = line.split(" ", 1)[0]
            if k == "map":
                line = "map " + MAP
            elif k == "seq":
                line = "seq %d" % (n + 1)
            elif k == "origin":
                line = "origin " + org
            elif k == "velocity":
                line = "velocity 0.0000 0.0000 0.0000"
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
                          "+exec", "test/p472org.cfg"], cwd=ROOT,
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
    if "=== p472org done ===" not in txt:
        print("CANNOT GRADE: the run did not reach its end")
        return 2
    sec = {}
    for name in ("row 3", "row 1", "row 2"):
        s = txt.split("=== p472org %s ===" % name, 1)[1].split("=== p472org", 1)[0]
        m = re.search(r"setpos (\S+) (\S+) (\S+)", s)
        say = [ln.split("save: ", 1)[1].strip() for ln in s.splitlines()
               if "save: " in ln]
        sec[name] = (tuple(float(x) for x in m.groups()) if m else None, say)
        print("     %s: body %s, said %s" % (name, sec[name][0], say or "nothing"))
    fails = 0
    at = sec["row 3"][0]
    # x and y only: the save's z is the spawn's, above the floor, and the body falls
    # before viewpos answers.
    ok1 = at is not None and all(abs(a - b) < 1.0 for a, b in zip(at[:2], GOOD[:2]))
    print("%s O1  row 3 loads: the body at its x, y" % ("PASS" if ok1 else "FAIL"))
    if not ok1:
        print("CANNOT GRADE O2: the arm could not load a real save")
        return 2
    bad = []
    for name in ("row 1", "row 2"):
        pos, say = sec[name]
        if pos is None or any(abs(a - b) >= 1.0 for a, b in zip(pos[:2], GOOD[:2])):
            bad.append("%s moved the body to %s" % (name, pos))
        if not any("position" in s for s in say):
            bad.append("%s said %s" % (name, say or "nothing"))
    print("%s O2  rows 1 and 2 refused with the position message, body unmoved%s"
          % ("FAIL" if bad else "PASS", "  (" + "; ".join(bad) + ")" if bad else ""))
    fails += (0 if ok1 else 1) + (1 if bad else 0)
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
