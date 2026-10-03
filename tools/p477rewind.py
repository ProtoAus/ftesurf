#!/usr/bin/env python3
"""p477rewind.py -- driver and grader for cfg/test/p477rewind.cfg (Patch 477:
rewind along your own run, resume or save there).

    python tools/p477rewind.py [--exe ftesurf64.exe] [--grade-only] [--timeout 420]

The arm makes real save states on surf_dune, so ftesurf/data/saves/surf_dune is
PARKED (renamed) for the run, the saves the run made are read and then removed,
and the park is put back -- each step listed, and a restore that did not happen
is an error, not a warning.  Exit 0 pass, 1 fail, 2 cannot grade.
"""
import argparse
import hashlib
import math
import os
import re
import shutil
import subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GAME = os.path.join(ROOT, "ftesurf")
LOG = os.path.join(GAME, "logs", "p477rewind.log")
SAVES = os.path.join(GAME, "data", "saves", "surf_dune")
PARK = SAVES + ".p477park"
STAMP = re.compile(r"^\d{4}-\d\d-\d\d \d\d:\d\d:\d\d ")
SECTIONS = ("R1", "R2", "R3", "R4", "R5", "R6", "R7", "R8")


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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--exe", default="ftesurf64.exe")
    ap.add_argument("--grade-only", action="store_true")
    ap.add_argument("--timeout", type=int, default=420)
    a = ap.parse_args()
    for f in ("csprogs.dat", "qwprogs.dat"):
        print("%s %s" % (f, hashlib.sha256(open(os.path.join(GAME, f), "rb").read())
                         .hexdigest()[:16].upper()))
    made = {} if a.grade_only else run(a.exe, a.timeout)
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

    def status(name):
        out = [re.search(r"rewind: on (\d) counting (\d) sent (\d)\s+cursor (\d+) of (\d+)\s+kept (\d)", s)
               for s in sec[name]]
        return [m for m in out if m]

    def cursor(name):
        out = [re.search(r"rewind: at (\S+) (\S+) (\S+) (\S+)\s+(\S+)", s) for s in sec[name]]
        return [m for m in out if m]

    def saved(name):
        """The server's answer in a section, and the state.txt of the slot it names."""
        sv = [re.search(r"rewind: save (\d+) \(slot (\d+)\) at (\S+), (\d+) u/s", s) for s in sec[name]]
        sv = [m for m in sv if m]
        if not sv:
            return None, None
        return sv[-1], made.get("save%s/state.txt" % sv[-1].group(2))

    def near(f, cur):
        o = re.search(r"^origin (\S+) (\S+) (\S+)$", f, re.M)
        v = re.search(r"^velocity (\S+) (\S+) (\S+)$", f, re.M)
        d = math.dist(cur, [float(x) for x in o.groups()]) if o else 1e9
        hv = math.hypot(float(v.group(1)), float(v.group(2))) if v else 0
        return d, hv

    def xyz(m):
        return [float(m.group(i)) for i in (2, 3, 4)]

    # R2: the clean run's first press asks and stays closed; the second opens.
    t2 = "\n".join(sec["R2"])
    st = status("R2")
    ok2 = (len(st) >= 2 and st[0].group(1) == "0" and "again to rewind" in t2
           and st[-1].group(1) == "1" and int(st[-1].group(4)) == int(st[-1].group(5)) - 1)
    check("R2", ok2, "asked %s, first on %s, then: %s" % (
        "again to rewind" in t2, st[0].group(1) if st else None, st[-1].group(0) if st else "none"))

    at = cursor("R3")
    sv, f = saved("R3")
    ok3, said3 = False, "no server answer"
    if at and sv:
        said3 = "server: %s; state.txt %s" % (sv.group(0), "found" if f else "MISSING")
        if f and int(sv.group(4)) > 50:
            d, hv = near(f, xyz(at[-1]))
            ok3 = "demoted 1" in f and "rewound 1" in f and d < 64 and hv > 50
            said3 += ", origin %.1f u from the cursor, velocity %.0f u/s" % (d, hv)
    check("R3", ok3, said3)

    vel = [re.search(r"velocity \S+ \S+ \S+\s+horizontal ([0-9.]+)", s) for s in sec["R4"]]
    vel = [float(m.group(1)) for m in vel if m]
    moving = [v for v in vel if v > 0.5]
    t4 = "\n".join(sec["R4"])
    hop4 = re.search(r"hopped (\d)", t4)
    check("R4", bool(moving) and moving[0] > 50 and hop4 is not None and hop4.group(1) == "1"
          and "practice from here" in t4,
          "readings %s, hopped %s, loaded %s" % ([round(v) for v in vel],
                                                hop4.group(1) if hop4 else None,
                                                "practice from here" in t4))

    t5 = "\n".join(sec["R5"])
    hop5 = re.search(r"hopped (\d)", t5)
    check("R5", "hopped start is forgiven" in t5 and hop5 is not None and hop5.group(1) == "0",
          "forgiven %s, hopped %s" % ("hopped start is forgiven" in t5,
                                      hop5.group(1) if hop5 else None))
    check("R6", "nothing kept at that time" in "\n".join(sec["R6"]),
          "out-of-range ask refused")

    # R7: the old cursor reads kept 0, its go is refused, and nothing moved.
    t7 = "\n".join(sec["R7"])
    st7 = status("R7")
    at7 = cursor("R7")
    pos7 = [re.search(r"setpos (\S+) (\S+) (\S+)", s) for s in sec["R7"]]
    pos7 = [[float(x) for x in m.groups()] for m in pos7 if m]
    head7 = clock(at7[0].group(5)) if at7 else None
    moved = math.dist(pos7[0], pos7[-1]) if len(pos7) >= 2 else None
    ok7 = (head7 is not None and head7 > 125 and len(st7) >= 3
           and st7[1].group(6) == "0"
           and "nothing kept at that time" in t7 and "practice from here" not in t7
           and st7[-1].group(1) == "1" and st7[-1].group(2) == "0" and st7[-1].group(3) == "0"
           and moved is not None and moved < 1)
    check("R7", ok7, "head at %s s, old cursor kept %s, refused %s, loaded %s, after: %s, body moved %s u"
          % (head7, st7[1].group(6) if len(st7) > 1 else None, "nothing kept at that time" in t7,
             "practice from here" in t7, st7[-1].group(0) if st7 else None,
             "%.2f" % moved if moved is not None else None))

    # R8: past the wrap, a save near the cursor's own time, then the mode closes.
    st8 = status("R8")
    at8 = cursor("R8")
    sv8, f8 = saved("R8")
    ok8, said8 = False, "no server answer"
    if at8 and sv8 and st8:
        want, got = clock(at8[0].group(5)), clock(sv8.group(3))
        said8 = "cursor %s s kept %s, server %s s; state.txt %s" % (
            want, st8[0].group(6), got, "found" if f8 else "MISSING")
        if f8 and want is not None and got is not None:
            d, _ = near(f8, xyz(at8[0]))
            ok8 = (st8[0].group(6) == "1" and abs(want - got) < 1 and "rewound 1" in f8
                   and d < 64 and st8[-1].group(1) == "0")
            said8 += ", origin %.1f u from the cursor, closed %s" % (d, st8[-1].group(1) == "0")
    check("R8", ok8, said8)

    bad = len(re.findall(r"Unknown command", text))
    frames = len(re.findall(r"\w+\.qc:\d+:", text))
    check("Q", bad == 0 and frames == 0, "Unknown command %d, QC frames %d" % (bad, frames))
    print("%d check(s) failed" % len(fails))
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
