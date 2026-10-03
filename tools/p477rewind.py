#!/usr/bin/env python3
"""p477rewind.py -- driver and grader for cfg/test/p477rewind.cfg (Patch 477:
rewind along your own run, resume or save there).

    python tools/p477rewind.py [--exe ftesurf64.exe] [--grade-only] [--timeout 480]

The arm makes real save states on surf_dune, so ftesurf/data/saves/surf_dune is
PARKED (renamed) for the run, the saves the run made are read and then removed,
and the park is put back -- each step listed, and a restore that did not happen
is an error, not a warning.  Exit 0 pass, 1 fail, 2 cannot grade.
"""
import argparse
import hashlib
import json
import math
import os
import re
import shutil
import subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GAME = os.path.join(ROOT, "ftesurf")
LOG = os.path.join(GAME, "logs", "p477rewind.log")
MADE = os.path.join(GAME, "logs", "p477rewind.saves.json")   # what --grade-only reads
SAVES = os.path.join(GAME, "data", "saves", "surf_dune")
PARK = SAVES + ".p477park"
STAMP = re.compile(r"^\d{4}-\d\d-\d\d \d\d:\d\d:\d\d ")
SECTIONS = ("R1", "R2", "R3", "R4", "R4C", "R4B", "R5", "R5B", "R5C", "R6", "R7", "R8", "R9",
            "R10", "R11", "R12", "R13", "R14")


def listing(d):
    out = []
    for r, _, fs in os.walk(d):
        out += [os.path.relpath(os.path.join(r, f), d).replace(os.sep, "/") for f in fs]
    return sorted(out)


def run(exe, timeout):
    if os.path.exists(PARK):
        raise SystemExit("a previous park is still there: %s -- restore it first" % PARK)
    had = os.path.exists(SAVES)
    before = listing(SAVES) if had else []
    if had:
        os.rename(SAVES, PARK)
    made = {}
    try:
        if os.path.exists(LOG):
            os.replace(LOG, LOG + ".prev")
        subprocess.run([os.path.join(ROOT, exe), "-WindowStyle", "Minimized",
                        "+exec", "cfg/test/p477rewind.cfg"], cwd=ROOT, timeout=timeout)
        for rel in listing(SAVES) if os.path.exists(SAVES) else []:
            if rel.endswith("state.txt"):
                made[rel] = open(os.path.join(SAVES, rel), errors="replace").read()
    finally:
        if os.path.exists(SAVES):
            shutil.rmtree(SAVES)
        if had:
            os.rename(PARK, SAVES)
        after = listing(SAVES) if os.path.exists(SAVES) else []
        print("saves restored: %s (%d files, before %d)"
              % ("yes" if after == before else "NO -- LISTINGS DIFFER", len(after), len(before)))
        if after != before:
            raise SystemExit("the saves tree did not come back as it was")
    print("saves the run made: %s" % (", ".join(sorted(made)) or "none"))
    with open(MADE, "w") as fh:
        json.dump(made, fh)
    return made


def sections(lines):
    out, cur = {}, None
    for s in lines:
        m = re.search(r"==== P477 (\w+) ====", s)
        if m:
            cur = m.group(1)
            out[cur] = []
        elif cur:
            out[cur].append(s)
    return out


def clock(s):
    """`m:ss.fff` or `s.fff` -> seconds, as Time_TickString and SV_TimerString print."""
    m = re.fullmatch(r"(?:(\d+):)?(\d+)\.(\d+)", s)
    return int(m.group(1) or 0) * 60 + int(m.group(2)) + float("0." + m.group(3)) if m else None


def vec(f, key):
    m = re.search(r"^%s (\S+) (\S+) (\S+)$" % key, f, re.M)
    return [float(x) for x in m.groups()] if m else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--exe", default="ftesurf64.exe")
    ap.add_argument("--grade-only", action="store_true")
    ap.add_argument("--timeout", type=int, default=480)
    a = ap.parse_args()
    for f in ("csprogs.dat", "qwprogs.dat"):
        print("%s %s" % (f, hashlib.sha256(open(os.path.join(GAME, f), "rb").read())
                         .hexdigest()[:16].upper()))
    made = json.load(open(MADE)) if a.grade_only else run(a.exe, a.timeout)
    lines = [STAMP.sub("", l.rstrip("\n")) for l in open(LOG, errors="replace")]
    text = "\n".join(lines)
    if "FTESurf CSQC loaded" not in text:
        print("CANNOT GRADE: CSQC never loaded")
        return 2
    sec = sections(lines)
    if any(k not in sec for k in SECTIONS):
        print("CANNOT GRADE: sections missing: %s" % [k for k in SECTIONS if k not in sec])
        return 2
    t1 = "\n".join(sec["R1"])
    if not (re.search(r"timer: running on ", t1) and re.search(r"\brecording 1\b", t1)):
        print("CANNOT GRADE: R1 never had a run on the clock")
        return 2

    fails = []

    def check(name, ok, said):
        print("%s %-3s %s" % ("PASS" if ok else "FAIL", name, said))
        if not ok:
            fails.append(name)

    def txt(name):
        return "\n".join(sec[name])

    def status(name):
        out = [re.search(r"rewind: on (\d) counting (\d) sent (\d)\s+cursor (\d+) of (\d+)"
                         r"\s+kept (\d)\s+resume (\d)", s) for s in sec[name]]
        return [m for m in out if m]

    def cursor(name):
        out = [re.search(r"rewind: at (\S+) (\S+) (\S+) (\S+)\s+(\S+)", s) for s in sec[name]]
        return [m for m in out if m]

    def answered(name, which=-1):
        """A server rewind save in a section (the last by default), and its state.txt."""
        sv = [re.search(r"rewind: save (\d+) \(slot (\d+)\) at (\S+), (\d+) u/s", s) for s in sec[name]]
        sv = [m for m in sv if m]
        if not sv:
            return None, None
        return sv[which], made.get("save%s/state.txt" % sv[which].group(2))

    def last(pattern, name):
        ms = [re.search(pattern, s) for s in sec[name]]
        ms = [m for m in ms if m]
        return ms[-1] if ms else None

    def xyz(m):
        return [float(m.group(i)) for i in (2, 3, 4)]

    # R2: the clean run's first press asks and stays closed; the second opens.
    st = status("R2")
    ok2 = (len(st) >= 2 and st[0].group(1) == "0" and "again to rewind" in txt("R2")
           and st[-1].group(1) == "1" and int(st[-1].group(4)) == int(st[-1].group(5)) - 1)
    check("R2", ok2, "asked %s, first on %s, then: %s" % (
        "again to rewind" in txt("R2"), st[0].group(1) if st else None,
        st[-1].group(0) if st else "none"))

    # R3: the file an older build reads is at rest; the speed is in rwvel.
    at = cursor("R3")
    sv, f = answered("R3")
    ok3, said3 = False, "no server answer"
    if at and sv:
        said3 = "server: %s; state.txt %s" % (sv.group(0), "found" if f else "MISSING")
        if f:
            o, v, rv = vec(f, "origin"), vec(f, "velocity"), vec(f, "rwvel")
            d = math.dist(xyz(at[-1]), o) if o else 1e9
            hv = math.hypot(rv[0], rv[1]) if rv else 0
            ok3 = ("demoted 1" in f and "rewound 1" in f and v == [0, 0, 0]
                   and int(sv.group(4)) > 50 and hv > 50 and d < 64)
            said3 += ", velocity %s, rwvel %.0f u/s, origin %.1f u from the cursor" % (v, hv, d)
    check("R3", ok3, said3)

    vel = [re.search(r"velocity \S+ \S+ \S+\s+horizontal ([0-9.]+)", s) for s in sec["R4"]]
    vel = [float(m.group(1)) for m in vel if m]
    moving = [v for v in vel if v > 0.5]
    hop4 = last(r"hopped (\d)", "R4")
    walk4 = "no faster than a walk" in txt("R4")
    check("R4", bool(moving) and moving[0] > 50 and hop4 is not None and hop4.group(1) == "0"
          and walk4,
          "readings %s, hopped %s, said walking speed %s" % ([round(v) for v in vel],
                                                             hop4.group(1) if hop4 else None, walk4))

    # R4C: reopened at that resume, then a resume faster than a walk is practice.
    st4c = status("R4C")
    hop4c = last(r"hopped (\d)", "R4C")
    ok4c = (bool(st4c) and st4c[0].group(7) == "1" and "practice from here" in txt("R4C")
            and hop4c is not None and hop4c.group(1) == "1")
    check("R4C", ok4c, "reopened: %s; practice from here %s; hopped %s" % (
        st4c[0].group(0) if st4c else None, "practice from here" in txt("R4C"),
        hop4c.group(1) if hop4c else None))

    # R4B: a plain save taken off the go, forgiven, loaded -- the tag comes back.
    t4b = txt("R4B")
    ps = last(r"^save (\d+) \(slot (\d+)\)", "R4B")
    pf = made.get("save%s/state.txt" % ps.group(2)) if ps else None
    pv = vec(pf, "velocity") if pf else None
    hop4b = last(r"hopped (\d)", "R4B")
    ok4b = (ps is not None and pf is not None and pv is not None
            and math.hypot(pv[0], pv[1]) > 50 and "hopped 1" in pf
            and "hopped start is forgiven" in t4b
            and hop4b is not None and hop4b.group(1) == "1" and "it carries speed" in t4b)
    check("R4B", ok4b, "plain save %s, its speed %s, its hopped %s, forgiven %s, after the load hopped %s"
          % (ps.group(2) if ps else None, round(math.hypot(pv[0], pv[1])) if pv else None,
             ("hopped 1" in pf) if pf else None, "hopped start is forgiven" in t4b,
             hop4b.group(1) if hop4b else None))

    t5 = txt("R5")
    hop5 = last(r"hopped (\d)", "R5")
    check("R5", "hopped start is forgiven" in t5 and hop5 is not None and hop5.group(1) == "0",
          "forgiven %s, hopped %s" % ("hopped start is forgiven" in t5,
                                      hop5.group(1) if hop5 else None))

    # R5B: armed -- no ask, opens at the last resume, and the pin left no taint.
    st5b = status("R5B")
    pr5b = last(r"\bpractice (\d)\b", "R5B")
    ok5b = (len(st5b) >= 2 and st5b[0].group(1) == "1" and st5b[0].group(7) == "1"
            and int(st5b[0].group(4)) < int(st5b[0].group(5)) - 1
            and "again to rewind" not in txt("R5B") and st5b[-1].group(1) == "0"
            and pr5b is not None and pr5b.group(1) == "0")
    check("R5B", ok5b, "opened: %s; closed on %s; practice %s; asked %s" % (
        st5b[0].group(0) if st5b else None, st5b[-1].group(1) if st5b else None,
        pr5b.group(1) if pr5b else None, "again to rewind" in txt("R5B")))

    # R5C: a fast load tags, a load at rest forgives.  Its premise is that the
    # at-rest save is row 4 -- the save's own line says so, or the arm is unsound.
    t5c = txt("R5C")
    sv5c = last(r"^save (\d+) \(slot", "R5C")
    hops5c = [m.group(1) for m in (re.search(r"hopped (\d)", s) for s in sec["R5C"]) if m]
    ok5c = (sv5c is not None and sv5c.group(1) == "4" and len(hops5c) >= 2
            and hops5c[0] == "1" and hops5c[-1] == "0" and "hopped start is forgiven" in t5c)
    check("R5C", ok5c, "at-rest save %s, hopped after the fast load %s, after the rest load %s, "
          "forgiven %s" % (sv5c.group(1) if sv5c else None, hops5c[0] if hops5c else None,
                           hops5c[-1] if hops5c else None, "hopped start is forgiven" in t5c))

    check("R6", "nothing kept at that time" in txt("R6"), "out-of-range ask refused")

    # R7: a clean run (it asked), the old cursor reads kept 0, its go is refused,
    # and nothing moved.
    t7 = txt("R7")
    st7 = status("R7")
    at7 = cursor("R7")
    cls7 = last(r"^\s*class: (\w+)", "R7")
    pos7 = [re.search(r"setpos (\S+) (\S+) (\S+)", s) for s in sec["R7"]]
    pos7 = [[float(x) for x in m.groups()] for m in pos7 if m]
    head7 = clock(at7[0].group(5)) if at7 else None
    moved = math.dist(pos7[0], pos7[-1]) if len(pos7) >= 2 else None
    ok7 = (cls7 is not None and cls7.group(1) == "clean" and "again to rewind" in t7
           and head7 is not None and head7 > 125 and len(st7) >= 3
           and st7[1].group(6) == "0"
           and "nothing kept at that time" in t7 and "practice from here" not in t7
           and st7[-1].group(1) == "1" and st7[-1].group(2) == "0" and st7[-1].group(3) == "0"
           and moved is not None and moved < 1)
    check("R7", ok7, "class %s, asked %s, head at %s s, old cursor kept %s, refused %s, loaded %s, "
          "after: %s, body moved %s u"
          % (cls7.group(1) if cls7 else None, "again to rewind" in t7, head7,
             st7[1].group(6) if len(st7) > 1 else None, "nothing kept at that time" in t7,
             "practice from here" in t7, st7[-1].group(0) if st7 else None,
             "%.2f" % moved if moved is not None else None))

    # R8: past the wrap, a save near the cursor's own time; then leaving resumes
    # at the head and replaces R4B's resume row.
    st8 = status("R8")
    at8 = cursor("R8")
    sv8, f8 = answered("R8", 0)      # the S save; the last is the leave's resume
    lst8 = last(r"saves: (\d+)/(\d+)", "R8")
    ok8, said8 = False, "no server answer"
    if at8 and sv8 and st8:
        want, got = clock(at8[0].group(5)), clock(sv8.group(3))
        said8 = "cursor %s s kept %s, server %s s; state.txt %s" % (
            want, st8[0].group(6), got, "found" if f8 else "MISSING")
        if f8 and want is not None and got is not None:
            d = math.dist(xyz(at8[0]), vec(f8, "origin") or [1e9] * 3)
            ok8 = (st8[0].group(6) == "1" and abs(want - got) < 1 and "rewound 1" in f8
                   and d < 64 and "rewind: resumed" in txt("R8")
                   and st8[-1].group(1) == "0"
                   and lst8 is not None and lst8.group(2) == "5")
            said8 += (", origin %.1f u from the cursor; left: resumed %s, closed %s, list %s"
                      % (d, "rewind: resumed" in txt("R8"), st8[-1].group(1) == "0",
                         lst8.group(0) if lst8 else None))
    check("R8", ok8, said8)

    # R9: the line starts over when a load winds the clock back, so its first
    # point is one the ring holds -- the save made there is AT the cursor.  "It
    # was answered" alone cannot tell: a load to under 0.5 s puts the ring's first
    # sample inside the window of a stale line's t=0 (the no-restart mutant did).
    tr9 = [int(m.group(1)) for m in (re.search(r"trail: run (\d+) samples", s) for s in sec["R9"]) if m]
    at9 = cursor("R9")
    sv9, f9 = answered("R9")
    d9 = (math.dist(xyz(at9[-1]), vec(f9, "origin") or [1e9] * 3)
          if (at9 and f9) else None)
    ok9 = (len(tr9) >= 2 and tr9[1] < tr9[0] and sv9 is not None
           and "nothing kept at that time" not in txt("R9") and d9 is not None and d9 < 64)
    check("R9", ok9, "trail samples %s, save at the line's first point: %s, %s u from the cursor"
          % (tr9, sv9.group(0) if sv9 else "refused or none",
             "%.1f" % d9 if d9 is not None else None))

    # R10: a restart while browsing closes the mode and leaves the body at the start.
    st10 = status("R10")
    pos10 = [re.search(r"setpos (\S+) (\S+) (\S+)", s) for s in sec["R10"]]
    pos10 = [[float(x) for x in m.groups()] for m in pos10 if m]
    ok10 = (len(st10) >= 2 and st10[0].group(1) == "0" and st10[-1].group(1) == "0"
            and len(pos10) >= 2 and pos10[-1][1] < 900
            and math.dist(pos10[0], pos10[-1]) < 64 and "rewind: resumed" not in txt("R10"))
    check("R10", ok10, "on after %s, positions %s, resumed %s" % (
        [m.group(1) for m in st10], [[round(c) for c in p] for p in pos10],
        "rewind: resumed" in txt("R10")))

    # R11: after `kill`, the pin's freeze request is gone and the next run is
    # clean with a moving clock.
    t11 = txt("R11")
    cls11 = last(r"^\s*class: (\w+)", "R11")
    want11 = last(r"want freeze (\d)", "R11")
    clk11 = last(r"^\s*(\d+:\d\d\.\d+)\s+pb ", "R11")
    sec11 = clock(clk11.group(1)) if clk11 else None
    ok11 = ("timer: running on" in t11 and cls11 is not None and cls11.group(1) == "clean"
            and want11 is not None and want11.group(1) == "0"
            and sec11 is not None and sec11 > 1.0)
    check("R11", ok11, "running %s, class %s, want freeze %s, clock %s s" % (
        "timer: running on" in t11, cls11.group(1) if cls11 else None,
        want11.group(1) if want11 else None, sec11))

    # R12: a running save with speed does NOT tag on load.  Premise: the save WAS of a
    # running run ("save N (slot ...)  m:ss.fff", not "no run") and fast.
    t12 = txt("R12")
    sv12 = last(r"^save (\d+) \(slot (\d+)\)\s+(\S+)", "R12")
    f12 = made.get("save%s/state.txt" % sv12.group(2)) if sv12 else None
    v12 = vec(f12, "velocity") if f12 else None
    hop12 = last(r"hopped (\d)", "R12")
    ok12 = (sv12 is not None and sv12.group(3) != "no" and v12 is not None
            and math.hypot(v12[0], v12[1]) > 300 and "run resumed" in t12
            and "it carries speed" not in t12 and hop12 is not None and hop12.group(1) == "0")
    check("R12", ok12, "running save %s at %s, its speed %s, resumed %s, said %s, hopped %s" % (
        sv12.group(1) if sv12 else None, sv12.group(3) if sv12 else None,
        round(math.hypot(v12[0], v12[1])) if v12 else None, "run resumed" in t12,
        "it carries speed" in t12, hop12.group(1) if hop12 else None))

    # R13: a server-served warp under the rewind ends the frozen run, and the
    # mode closes.  Premise: open on a running run before; the setpos landed
    # outside the start box (no "back in the start" cancel instead).
    st13 = status("R13")
    t13 = txt("R13")
    ok13 = (len(st13) >= 2 and st13[0].group(1) == "1" and st13[-1].group(1) == "0"
            and "moved while the rewind held it" in t13 and "back in the start" not in t13)
    check("R13", ok13, "on before %s, on after %s, ended at the warp %s, start-box cancel %s" % (
        st13[0].group(1) if st13 else None, st13[-1].group(1) if st13 else None,
        "moved while the rewind held it" in t13, "back in the start" in t13))

    # R14: a held S saves once.  Premise: the press and the repeat both reached
    # the handler (two "key 115 down" lines), and the first made a save.
    t14 = txt("R14")
    saves14 = len(re.findall(r"rewind: save \d+ \(slot", t14))
    downs14 = len(re.findall(r"rewind: key 115 down -> taken", t14))
    check("R14", downs14 == 2 and saves14 == 1,
          "presses taken %d, saves %d" % (downs14, saves14))

    bad = len(re.findall(r"Unknown command", text))
    frames = len(re.findall(r"\w+\.qc:\d+:", text))
    check("Q", bad == 0 and frames == 0, "Unknown command %d, QC frames %d" % (bad, frames))
    print("%d check(s) failed" % len(fails))
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
