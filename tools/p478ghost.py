#!/usr/bin/env python3
"""p478ghost.py -- driver and grader for cfg/test/p478ghost.cfg (Patch 478: a
ghost begun in an armed start box starts no run where it ends).

    python tools/p478ghost.py [--exe ftesurf64.exe] [--grade-only] [--timeout 300]

The arm saves nothing; data/ is listed before and after, and anything the run
left there is printed and fails the run.  Exit 0 pass, 1 fail, 2 cannot grade.
"""
import argparse
import hashlib
import os
import re
import subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GAME = os.path.join(ROOT, "ftesurf")
LOG = os.path.join(GAME, "logs", "p478ghost.log")
DATA = os.path.join(GAME, "data")
STAMP = re.compile(r"^\d{4}-\d\d-\d\d \d\d:\d\d:\d\d ")
SECTIONS = ("G1", "G2")
EDGE_Y = 769 + 16       # surf_dune's start box +y face, plus the hull's half-width


def listing(d):
    out = []
    for r, _, fs in os.walk(d):
        out += [os.path.relpath(os.path.join(r, f), d).replace(os.sep, "/") for f in fs]
    return set(out)


def run(exe, timeout):
    before = listing(DATA)
    if os.path.exists(LOG):
        os.replace(LOG, LOG + ".prev")
    subprocess.run([os.path.join(ROOT, exe), "-WindowStyle", "Minimized",
                    "+exec", "cfg/test/p478ghost.cfg"], cwd=ROOT, timeout=timeout)
    new = sorted(listing(DATA) - before)
    print("data/ files the run made: %s" % (", ".join(new) or "none"))
    return new


def sections(lines):
    out, cur = {}, None
    for s in lines:
        m = re.search(r"==== P478 (\w+) ====", s)
        if m:
            cur = m.group(1)
            out[cur] = []
        elif cur:
            out[cur].append(s)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--exe", default="ftesurf64.exe")
    ap.add_argument("--grade-only", action="store_true")
    ap.add_argument("--timeout", type=int, default=300)
    a = ap.parse_args()
    for f in ("csprogs.dat", "qwprogs.dat"):
        print("%s %s" % (f, hashlib.sha256(open(os.path.join(GAME, f), "rb").read())
                         .hexdigest()[:16].upper()))
    new = [] if a.grade_only else run(a.exe, a.timeout)
    lines = [STAMP.sub("", l.rstrip("\n")) for l in open(LOG, errors="replace")]
    if "FTESurf CSQC loaded" not in "\n".join(lines):
        print("CANNOT GRADE: CSQC never loaded")
        return 2
    sec = sections(lines)
    if any(k not in sec for k in SECTIONS):
        print("CANNOT GRADE: sections missing: %s" % [k for k in SECTIONS if k not in sec])
        return 2

    fails = []

    def check(name, ok, said):
        print("%s %-3s %s" % ("PASS" if ok else "FAIL", name, said))
        if not ok:
            fails.append(name)

    def states(name):
        return [m.group(1) for m in (re.search(r"timer: (\w+) on ", s) for s in sec[name]) if m]

    def classes(name):
        return [m.group(1) for m in (re.search(r"^\s*class: (\w+)", s) for s in sec[name]) if m]

    def elapsed(name):
        return [m.group(1) for m in (re.search(r"^\s+(\d+:\d\d\.\d+)\s+pb ", s) for s in sec[name]) if m]

    def ys(name):
        return [float(m.group(1)) for m in (re.search(r"^setpos \S+ (\S+) \S+ ", s) for s in sec[name]) if m]

    # G1.  Premises: armed in the box; the ghost began there (the not-running
    # line); the body was inside the box at the ghost and outside it later,
    # still ghosted.  Verdict: no run on the clock after the unghost, and the
    # disarm said why.  Before 478: `running`, class clean, its clock started at
    # the unghost (about a second on it) with the body far down the ramp.
    t1 = "\n".join(sec["G1"])
    st1, cl1, el1, y1 = states("G1"), classes("G1"), elapsed("G1"), ys("G1")
    premise = (len(st1) == 3 and st1[0] == "armed"
               and "ghost -- `ghost` again to go back" in t1 and "ghost off" in t1
               and len(y1) == 3 and y1[0] < EDGE_Y and y1[1] > EDGE_Y)
    if not premise:
        print("CANNOT GRADE G1: states %s, ghost on/off %s/%s, y %s (box edge %d)" % (
            st1, "ghost -- `ghost` again to go back" in t1, "ghost off" in t1, y1, EDGE_Y))
        return 2
    check("G1", st1[2] != "running" and "left the start box as a ghost" in t1,
          "armed at y %.0f, ghosted out to y %.0f (state %s), unghosted at y %.0f: %s%s, said %s" % (
              y1[0], y1[1], st1[1], y1[2], st1[2],
              (" class %s at %s" % (cl1[-1], el1[-1])) if st1[2] == "running" and cl1 and el1 else "",
              "left the start box as a ghost" in t1))

    # G2.  A ghost in the box with the body still keeps the arm; a clean start after.
    st2, cl2 = states("G2"), classes("G2")
    t2 = "\n".join(sec["G2"])
    check("G2", len(st2) == 2 and st2[0] == "armed" and st2[1] == "running"
          and bool(cl2) and cl2[-1] == "clean" and "left the start box as a ghost" not in t2,
          "after the unghost %s, after +forward %s class %s" % (
              st2[0] if st2 else None, st2[1] if len(st2) > 1 else None, cl2[-1] if cl2 else None))

    check("D", not new, "data/ left as it was" if not new else "the run left: %s" % ", ".join(new))
    print("%d check(s) failed" % len(fails))
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
