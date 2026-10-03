#!/usr/bin/env python3
"""p478ghost.py -- driver and grader for cfg/test/p478ghost.cfg (Patch 478: a
ghost begun in an armed start box starts no run where it ends).

    python tools/p478ghost.py [--exe ftesurf64.exe] [--grade-only] [--timeout 300]

G3 parks a run and retries, so data/saves/surf_dune and data/resume/surf_dune
are PARKED (renamed) for the run and put back, each listing checked.  The rest
of data/ is listed (files AND dirs) before; what the run made there is printed
and removed, each removal checked, and D passes only if the whole tree then
lists as it did.  Exit 0 pass, 1 fail, 2 cannot grade.
"""
import argparse
import hashlib
import os
import re
import shutil
import subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GAME = os.path.join(ROOT, "ftesurf")
LOG = os.path.join(GAME, "logs", "p478ghost.log")
DATA = os.path.join(GAME, "data")
STAMP = re.compile(r"^\d{4}-\d\d-\d\d \d\d:\d\d:\d\d ")
SECTIONS = ("G1", "G2", "G3", "G3P", "G3A")
EDGE_Y = 769 + 16       # surf_dune's start box +y face, plus the hull's half-width
PARKS = [os.path.join(DATA, "saves", "surf_dune"), os.path.join(DATA, "resume", "surf_dune")]


def tree(d):
    """Every file AND directory under d, as (kind, relative path)."""
    out = set()
    for r, ds, fs in os.walk(d):
        out |= {("d", os.path.relpath(os.path.join(r, x), d)) for x in ds}
        out |= {("f", os.path.relpath(os.path.join(r, x), d)) for x in fs}
    return out


def run(exe, timeout):
    for p in PARKS:
        if os.path.exists(p + ".p478park"):
            raise SystemExit("a previous park is still there: %s -- restore it first" % p)
    orig = tree(DATA)
    had = {p: os.path.exists(p) for p in PARKS}
    kept = {p: tree(p) if had[p] else set() for p in PARKS}
    for p in PARKS:
        if had[p]:
            os.rename(p, p + ".p478park")
    before = tree(DATA)
    try:
        if os.path.exists(LOG):
            os.replace(LOG, LOG + ".prev")
        subprocess.run([os.path.join(ROOT, exe), "-WindowStyle", "Minimized",
                        "+exec", "cfg/test/p478ghost.cfg"], cwd=ROOT, timeout=timeout)
    finally:
        made = sorted(tree(DATA) - before)
        for p in PARKS:
            if os.path.exists(p):
                shutil.rmtree(p)
            if had[p]:
                os.rename(p + ".p478park", p)
            back = tree(p) if os.path.exists(p) else set()
            print("%s restored: %s (%d entries, before %d)" % (
                os.path.relpath(p, DATA), "yes" if back == kept[p] else "NO -- LISTINGS DIFFER",
                len(back), len(kept[p])))
            if back != kept[p]:
                raise SystemExit("%s did not come back as it was" % p)
        parked = [os.path.relpath(p, DATA) for p in PARKS]
        rest = [(k, r) for k, r in made if not any(r == q or r.startswith(q + os.sep) for q in parked)]
        print("data/ the run made outside the parks: %s" % (
            ", ".join("%s%s" % (r, "/" if k == "d" else "") for k, r in rest) or "none"))
        for k, r in sorted(rest, key=lambda e: (e[0] == "d", -len(e[1]))):
            p = os.path.join(DATA, r)
            if k == "f":
                os.remove(p)
            else:
                os.rmdir(p)
            if os.path.exists(p):
                raise SystemExit("could not remove %s" % p)
    return sorted(r for k, r in tree(DATA) ^ orig)


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
    said1 = "no run -- your body is out of its start box as a ghost" in t1
    check("G1", st1[1] == "idle" and st1[2] != "running" and said1,
          "armed at y %.0f, ghosted out to y %.0f (state %s), unghosted at y %.0f: %s%s, said %s" % (
              y1[0], y1[1], st1[1], y1[2], st1[2],
              (" class %s at %s" % (cl1[-1], el1[-1])) if st1[2] == "running" and cl1 and el1 else "",
              said1))

    # G2.  A ghost in the box with the body still keeps the arm; a clean start
    # after, primed for its stage-1 post (the ghost's flag no longer stands into
    # the start: `stage fill: prime 1`).
    st2, cl2 = states("G2"), classes("G2")
    t2 = "\n".join(sec["G2"])
    pr2 = [m.group(1) for m in (re.search(r"stage fill: prime (\d)", s) for s in sec["G2"]) if m]
    check("G2", len(st2) == 2 and st2[0] == "armed" and st2[1] == "running"
          and bool(cl2) and cl2[-1] == "clean" and "as a ghost" not in t2
          and bool(pr2) and pr2[-1] == "1",
          "after the unghost %s, after +forward %s class %s prime %s" % (
              st2[0] if st2 else None, st2[1] if len(st2) > 1 else None, cl2[-1] if cl2 else None,
              pr2[-1] if pr2 else None))

    # G3.  Premises: the reload parked G3's own run (a few seconds -- the
    # parks hold nothing older), and the resume phase began.  Verdict: in the
    # phase `!r` and `retry` are refused, and the resume applies.  Before 478:
    # "!r -- start of the map", "retry -- back where you were", then a CLEAN run.
    t3 = "\n".join(sec["G3P"] + sec["G3A"])
    pk3 = re.search(r"resume: your run here is paused at (\d+):(\d+)\.(\d+)", t3)
    if not (pk3 and int(pk3.group(1)) == 0 and int(pk3.group(2)) < 30):
        print("CANNOT GRADE G3: no park of G3's own run (%s)" % (pk3.group(0) if pk3 else None))
        return 2
    st3, cl3 = states("G3A"), classes("G3A")
    ok3 = ("resume: wait for the resume to finish" in t3
           and "retry: wait for the resume to finish" in t3
           and "start of the map" not in t3 and "retry -- back where you were" not in t3
           and "resume: run resumed at" in t3)
    check("G3", ok3, "park %s; !r refused %s, retry refused %s, warped %s, retried %s, "
          "resumed %s; after: %s class %s" % (
              pk3.group(0).split(" at ")[-1], "resume: wait for the resume to finish" in t3,
              "retry: wait for the resume to finish" in t3, "start of the map" in t3,
              "retry -- back where you were" in t3, "resume: run resumed at" in t3,
              st3[-1] if st3 else None, cl3[-1] if cl3 else None))

    check("D", not new, "data/ lists as it did" if not new else "data/ differs: %s" % ", ".join(new))
    print("%d check(s) failed" % len(fails))
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
