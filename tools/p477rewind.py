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
            "R10", "R11", "R12", "R13", "R13B", "R22A", "R22C", "R14", "R15", "R16", "R17", "R17B", "R18", "R18C",
            "R18D", "R18J", "R18K", "R18L", "R18M", "R18E", "R22D", "R22E", "R23A", "R23B", "R23C", "R24A", "R24B", "R18F", "R18G", "R18H", "R18I", "R18B",
            "R19")


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
            elif rel.endswith("run.view"):
                made.setdefault("_views", []).append(rel)
            elif rel.endswith("seq.txt"):
                made.setdefault("_seqs", []).append(rel)
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
    print("saves the run made: %s" % (", ".join(sorted(k for k in made if not k.startswith("_"))) or "none"))
    print("view prefixes: %s" % (", ".join(made.get("_views", [])) or "none"))
    print("segment columns: %s" % (", ".join(made.get("_seqs", [])) or "none"))
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
    cannot = []                 # round 22: a premise that did not hold is not a verdict

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

    # R13B: a warp that started no run kept the ring, so the kept line's head
    # resumes (counting), and the countdown then ends.
    st13b = status("R13B")
    t13b = txt("R13B")
    # The countdown is a save-lock hold, so either of Watch_Open's refusals may
    # be the one that speaks; the go's round trip (no hold yet) is code-read only.
    rr13b = ("wait for the rewind's resume first" in t13b
             or "let go of the save-lock key first" in t13b)
    ok13b = (len(st13b) >= 2 and st13b[0].group(1) == "1" and st13b[0].group(2) == "1"
             and "rewind: resumed" in t13b and "nothing kept at that time" not in t13b
             and st13b[-1].group(1) == "0" and rr13b)
    check("R13B", ok13b, "after the go: %s; resumed %s, refused %s, after the count on %s, "
          "replay refused in the count %s" % (
              st13b[0].group(0) if st13b else None, "rewind: resumed" in t13b,
              "nothing kept at that time" in t13b, st13b[-1].group(1) if st13b else None, rr13b))

    # R13C (round 18): ENTER pressed in the countdown is the rewind's, not
    # `bind enter say`'s -- a draft opened there swallows the releases of the
    # keys held for the release.  Premise: R13B's countdown was on (its status).
    k13c = [re.search(r"vote key: scan 13 down 1 took (\d)", s) for s in sec["R13B"]]
    k13c = [m.group(1) for m in k13c if m]
    check("R13C", bool(st13b) and st13b[0].group(2) == "1" and k13c == ["1"],
          "counting %s, ENTER took %s" % (st13b[0].group(2) if st13b else None, k13c))

    # R13D (rounds 19-20): `4` in the countdown deletes nothing -- the count
    # `vote key` prints before it and 600 ms after.  (`1` could not tell: a save
    # under the countdown's hold is the server's to refuse.)
    sc13d = [m for m in (re.search(r"vote key: scan (52|1) down (\d) took (\d) .* saves (\d+)", s)
                         for s in sec["R13B"]) if m]
    first = [m for m in sc13d if m.group(1) == "52" and m.group(2) == "1"]
    after = [m for m in sc13d if m.group(1) == "1"]
    check("R13D", bool(st13b) and st13b[0].group(2) == "1" and bool(first) and bool(after)
          and first[0].group(4) == after[-1].group(4),
          "counting %s, saves %s then %s" % (st13b[0].group(2) if st13b else None,
                                             first[0].group(4) if first else None,
                                             after[-1].group(4) if after else None))

    # R13E (round 20): in the countdown S bound to `sl_del` is the mode's, not its
    # bind's (`took 1`).  Premise: the countdown was on (R13B's status).
    k13e = [m.group(1) for m in (re.search(r"vote key: scan 115 down 1 took (\d)", s)
                                 for s in sec["R13B"]) if m]
    check("R13E", bool(st13b) and st13b[0].group(2) == "1" and k13e == ["1"],
          "counting %s, S took %s" % (st13b[0].group(2) if st13b else None, k13e))

    # R22A (round 22): a key reporting scancode 0 tapped in the countdown ends
    # nothing -- 0 is the countdown hold's "no key".  Premise: counting before the
    # tap, and both halves of the tap went through the whole chain.  Verdict:
    # still counting after it, and the count then ends in a resume as ever.
    st22a = status("R22A")
    t22a = txt("R22A")
    k22a = [m.group(1) for m in (re.search(r"vote key: scan 0 down (\d) took \d", s)
                                 for s in sec["R22A"]) if m]
    ok22a = (len(st22a) >= 3 and st22a[0].group(1) == "1" and st22a[0].group(2) == "1"
             and k22a == ["1", "0"] and st22a[1].group(1) == "1" and st22a[1].group(2) == "1"
             and st22a[2].group(1) == "0" and "rewind: resumed" in t22a)
    check("R22A", ok22a, "counting %s, key 0 %s, then on %s counting %s; after the count on %s, "
          "resumed %s" % (st22a[0].group(2) if st22a else None, k22a,
                          st22a[1].group(1) if len(st22a) > 1 else None,
                          st22a[1].group(2) if len(st22a) > 1 else None,
                          st22a[2].group(1) if len(st22a) > 2 else None, "rewind: resumed" in t22a))

    # R22B (round 22): `4` held in that countdown stays swallowed once it ends,
    # the key-0 release between notwithstanding.  Premise: `4` was pressed in the
    # count, the mode had closed (on 0) before its repeat.  Verdict: the count of
    # saves `vote key` prints before and after is the same.
    sc22 = [m for m in (re.search(r"vote key: scan (52|1) down (\d) took (\d) .* saves (\d+)", s)
                        for s in sec["R22A"]) if m]
    rd22 = [m.group(4) for m in sc22 if m.group(1) == "1"]
    fk22 = [m for m in sc22 if m.group(1) == "52" and m.group(2) == "1"]
    check("R22B", len(st22a) >= 3 and st22a[2].group(1) == "0" and len(fk22) == 2
          and len(rd22) == 2 and rd22[0] == rd22[1],
          "4 pressed %d time(s), closed before the repeat %s, saves %s" % (
              len(fk22), st22a[2].group(1) == "0" if len(st22a) > 2 else None, rd22))

    # R22C (round 22): `1` pressed while browsing, its release taken by a chat
    # draft; after the close the next `1` saves.  Premises: the mode was open,
    # took the first `1`, the draft took its release, and the mode then read
    # closed.  Verdict: one more save, said by the server.
    st22c = status("R22C")
    t22c = txt("R22C")
    k22c = [m.group(1) for m in (re.search(r"vote key: scan 49 (down \d took \d)", s)
                                 for s in sec["R22C"]) if m]
    rd22c = [m.group(1) for m in (re.search(r"vote key: scan 1 down 0 took \d .* saves (\d+)", s)
                                  for s in sec["R22C"]) if m]
    # Round 24: the draft passes that release now (it did not take the press), so
    # R22C guards the outcome both round 22's table clear and round 24's draft
    # rule give, and the release's `took` is no longer a premise.
    pre22c = (len(st22c) >= 2 and st22c[0].group(1) == "1" and st22c[1].group(1) == "0"
              and k22c[:1] == ["down 1 took 1"])
    sv22c = re.search(r"\bsave (\d+) \(slot \d+\)", t22c)
    if not pre22c:
        print("CANNOT GRADE R22C: status %s, `1` %s" % ([m.group(1) for m in st22c], k22c))
        cannot.append("R22C")
    else:
        check("R22C", len(rd22c) == 2 and int(rd22c[1]) == int(rd22c[0]) + 1 and sv22c is not None,
              "saves %s, the server's save %s" % (rd22c, sv22c.group(0) if sv22c else None))

    # R15: a refused warp ends nothing.  Premise: it WAS refused (out of range).
    st15 = status("R15")
    t15 = txt("R15")
    # Round 14: the pinned run's record counts include the pin's `warp`.
    wp15 = last(r"rec rows: in \d+ warp (\d+)", "R15")
    ok15 = ("out of range" in t15 and "moved while the rewind held it" not in t15
            and bool(st15) and st15[-1].group(1) == "1" and "timer: running on" in t15
            and wp15 is not None and int(wp15.group(1)) >= 1)
    check("R15", ok15, "refused %s, voided %s, on %s, still running %s, warps %s" % (
        "out of range" in t15, "moved while the rewind held it" in t15,
        st15[-1].group(1) if st15 else None, "timer: running on" in t15,
        wp15.group(1) if wp15 else None))

    # R16: a load under the pin is the server's to refuse.
    st16 = status("R16")
    t16 = txt("R16")
    ok16 = ("close the replay or rewind first" in t16 and bool(st16) and st16[-1].group(1) == "1")
    check("R16", ok16, "refused %s, on %s" % ("close the replay or rewind first" in t16,
                                              st16[-1].group(1) if st16 else None))

    # R17: the S save's slot has no .view prefix and no segment column; R12's
    # plain running save has both (the premise: this client writes them here).
    views = set(made.get("_views", []))
    seqs = set(made.get("_seqs", []))
    sv17, _ = answered("R17", 0)
    v17 = ("save%s/run.view" % sv17.group(2)) in views if sv17 else None
    v12 = ("save%s/run.view" % sv12.group(2)) in views if sv12 else None
    q17 = ("save%s/seq.txt" % sv17.group(2)) in seqs if sv17 else None
    q12 = ("save%s/seq.txt" % sv12.group(2)) in seqs if sv12 else None
    check("R17", sv17 is not None and v17 is False and v12 is True and q17 is False and q12 is True,
          "S save %s, its run.view %s seq.txt %s; R12's save %s, its run.view %s seq.txt %s" % (
              sv17.group(2) if sv17 else None, v17, q17, sv12.group(2) if sv12 else None, v12, q12))

    # R17B: a replay opened while browsing takes the pin in the same frame, so a
    # go on the same line never leaves.  Premise: the rewind was open on a timed
    # run, and the replay really opened.
    st17b = status("R17B")
    t17b = txt("R17B")
    ok17b = (len(st17b) >= 2 and st17b[0].group(1) == "1" and "replay: opened in" in t17b
             and "rewind: resumed" not in t17b and st17b[-1].group(1) == "0"
             and "a rewind left without a resume" in t17b)
    check("R17B", ok17b, "open %s, replay opened %s, resumed %s, on after %s, run ended %s" % (
        st17b[0].group(1) if st17b else None, "replay: opened in" in t17b,
        "rewind: resumed" in t17b, st17b[-1].group(1) if st17b else None,
        "a rewind left without a resume" in t17b))

    # R18: a replay's pin keeps its run through a warp.  Premise: the setpos landed.
    t18 = txt("R18")
    ok18 = ("setpos: " in t18 and "moved while the rewind held it" not in t18
            and "timer: running on" in t18)
    check("R18", ok18, "warped %s, voided %s, still running %s" % (
        "setpos: " in t18, "moved while the rewind held it" in t18, "timer: running on" in t18))

    # R18W (round 16): the pin's warp is written when it zeroes something.  The
    # first pin lands on a sliding body; let go and taken again in one packet,
    # the body the release zeroed writes none (a pin blind to it writes two).
    wp18 = last(r"rec rows: in \d+ warp (\d+)", "R18")
    check("R18W", wp18 is not None and int(wp18.group(1)) == 1,
          "pin warps %s (one sliding, one re-pinned still)" % (wp18.group(1) if wp18 else None))

    # R18C: a typed `rec_watch 0` under the rewind's pin voids the frozen run.
    st18c = status("R18C")
    t18c = txt("R18C")
    tm18c = last(r"timer: (\w+) on ", "R18C")
    ok18c = (len(st18c) >= 2 and st18c[0].group(1) == "1" and st18c[-1].group(1) == "0"
             and "a rewind left without a resume" in t18c
             and tm18c is not None and tm18c.group(1) != "running")
    check("R18C", ok18c, "on %s then %s, voided %s, timer %s" % (
        st18c[0].group(1) if st18c else None, st18c[-1].group(1) if st18c else None,
        "a rewind left without a resume" in t18c, tm18c.group(1) if tm18c else None))

    # R18D: the same release of an idle rewind frees the body; the client closes.
    # Round 16: after it STAT_FS_PIN reads -serial, a release the client sees
    # even inside one snapshot.
    st18d = status("R18D")
    t18d = txt("R18D")
    pn18d = last(r"rewind: pin (\S+) serial (\S+)", "R18D")
    neg18d = (pn18d is not None and float(pn18d.group(2)) > 0
              and float(pn18d.group(1)) == -float(pn18d.group(2)))
    ok18d = (len(st18d) >= 2 and st18d[0].group(1) == "1" and st18d[-1].group(1) == "0"
             and "a rewind left without a resume" not in t18d and neg18d)
    check("R18D", ok18d, "on %s then %s, voided %s, after it pin %s serial %s" % (
        st18d[0].group(1) if st18d else None, st18d[-1].group(1) if st18d else None,
        "a rewind left without a resume" in t18d,
        pn18d.group(1) if pn18d else None, pn18d.group(2) if pn18d else None))

    # R18J (rounds 17-18): through the whole input chain, a press the chat draft
    # took repeats into the open rewind without a go, and a scrub whose release
    # the draft swallowed stops.  Premise: the rewind opened; the draft took the
    # first ENTER and the arrow's release, and the rewind's repeat guard the
    # second ENTER (`took 1` each -- a go on either would show as sent or
    # counting, not as a pass).
    st18j = status("R18J")
    t18j = txt("R18J")
    tk18j = [m.group(1) for m in (re.search(r"vote key: scan (13 down 1|130 down 0) took 1", s)
                                  for s in sec["R18J"]) if m]
    ok18j = (len(st18j) >= 5 and st18j[0].group(1) == "1"
             and tk18j.count("13 down 1") == 2 and "130 down 0" in tk18j
             and st18j[1].group(1) == "1" and st18j[1].group(2) == "0" and st18j[1].group(3) == "0"
             and "rewind: resumed" not in t18j and int(st18j[2].group(4)) >= 30
             and int(st18j[3].group(4)) >= int(st18j[2].group(4)) - 15
             and st18j[3].group(4) == st18j[4].group(4))
    check("R18J", ok18j, "open %s; after the repeat counting %s sent %s; seek at %s, then cursor %s, %s" % (
        st18j[0].group(1) if st18j else None,
        st18j[1].group(2) if len(st18j) > 1 else None, st18j[1].group(3) if len(st18j) > 1 else None,
        st18j[2].group(4) if len(st18j) > 2 else None, st18j[3].group(4) if len(st18j) > 3 else None,
        st18j[4].group(4) if len(st18j) > 4 else None))

    # R18K (round 19): ESC's repeat after the rewind it closed is still taken.
    # Premise: the rewind opened and the first ESC closed it (taken, then on 0).
    st18k = status("R18K")
    e18k = [m.group(1) for m in (re.search(r"vote key: scan 27 down 1 took (\d)", s)
                                 for s in sec["R18K"]) if m]
    check("R18K", len(st18k) >= 2 and st18k[0].group(1) == "1" and st18k[-1].group(1) == "0"
          and e18k == ["1", "1"],
          "open %s then %s, ESC took %s" % (st18k[0].group(1) if st18k else None,
                                            st18k[-1].group(1) if st18k else None, e18k))

    # R18L (round 19): S bound to a saveloc alias is still the rewind's save.
    st18l = status("R18L")
    sv18l, _ = answered("R18L")
    check("R18L", len(st18l) >= 1 and st18l[0].group(1) == "1" and sv18l is not None,
          "open %s, the rewind's save %s" % (st18l[0].group(1) if st18l else None,
                                             sv18l.group(0) if sv18l else None))

    # R18M (round 21): a typed `sl_del` with the rewind up deletes nothing, and
    # the client says why; `4` held across the close stays swallowed.  The save
    # count is read three times (before, after the typed delete, after the
    # held key's repeat) and must not move.  Premise: the rewind was open.
    st18m = status("R18M")
    t18m = txt("R18M")
    c18m = [m.group(1) for m in (re.search(r"vote key: scan 1 down 0 took \d .* saves (\d+)", s)
                                 for s in sec["R18M"]) if m]
    # Round 22: and the mode had closed before the held key's repeat (on 0) --
    # inside the mode the repeat is swallowed whatever the fix does.
    check("R18M", len(st18m) >= 2 and st18m[0].group(1) == "1" and st18m[1].group(1) == "0"
          and len(c18m) == 3
          and c18m[0] == c18m[1] == c18m[2] and "the save-lock waits for the rewind" in t18m,
          "open %s then %s, saves %s, said %s" % (
              st18m[0].group(1) if st18m else None, st18m[1].group(1) if len(st18m) > 1 else None,
              c18m, "the save-lock waits for the rewind" in t18m))

    # R18E: a hop chain's tag survives a fast load and rest in the box.  Premise:
    # the chain tagged (its own dprint-free line and the first read) and the load
    # raised -- row 1 is R3's rewind row, which says so as "practice from here".
    hops18e = [m.group(1) for m in (re.search(r"hopped (\d)", s) for s in sec["R18E"]) if m]
    t18e = txt("R18E")
    up18e = "it carries speed" in t18e or "rewind: resumed -- practice from here" in t18e
    ok18e = (len(hops18e) >= 2 and hops18e[0] == "1" and hops18e[-1] == "1"
             and "tagged a hopped start" in t18e and up18e)
    check("R18E", ok18e, "chain tagged %s, hopped %s, the load raised %s, after rest %s" % (
        "tagged a hopped start" in t18e, hops18e[0] if hops18e else None, up18e,
        hops18e[-1] if hops18e else None))

    # R22D (round 22): a hop chain's tag raised by a load drops a forgiveness
    # already pending.  Premises: the chain tagged the run (hopped 1), `!r`
    # cleared it (hopped 0), the idle load raised a forgivable tag (R3's rewind
    # row, "practice from here"), the running row's load raised again ("it
    # carries speed"), and the rest was in the box (armed).  Verdict: hopped 1.
    # Round 23: the running row's own file is the premise (RUNNING, hopped 1,
    # faster than a walk or a jump), so its raise ("it carries speed") is a
    # verdict -- the rule under test prints it -- and the rest's conditions are
    # read (start ok 0, grounded).  R22E shows that rest forgives without it.
    hp22d = [m.group(1) for m in (re.search(r"\bhopped (\d) rearmhop", s) for s in sec["R22D"]) if m]
    tm22d = [m.group(1) for m in (re.search(r"timer: (\w+) on ", s) for s in sec["R22D"]) if m]
    ok22d = [m.group(1) for m in (re.search(r"start: ok (\d) ", s) for s in sec["R22D"]) if m]
    gr22d = [float(m.group(1)) for m in (re.search(r"phase: ground ([0-9.]+) ", s) for s in sec["R22D"]) if m]
    t22d = txt("R22D")
    sl22d = re.search(r"\bsave \d+ \(slot (\d+)\)", t22d)
    row22d = made.get("save%s/state.txt" % sl22d.group(1), "") if sl22d else ""
    v22d = vec(row22d, "velocity")
    fast22d = bool(v22d) and (math.hypot(v22d[0], v22d[1]) > 270 or abs(v22d[2]) > 310)
    pre22d = (re.search(r"^state 2$", row22d, re.M) is not None
              and re.search(r"^hopped 1$", row22d, re.M) is not None and fast22d
              and len(hp22d) == 3 and hp22d[0] == "1" and hp22d[1] == "0" and len(tm22d) == 3
              and tm22d[0] == "running" and tm22d[2] == "armed"
              and "rewind: resumed -- practice from here" in t22d)
    if not pre22d:
        print("CANNOT GRADE R22D: row %s velocity %s, hopped %s, states %s, idle load raised %s" % (
            sl22d.group(1) if sl22d else None, v22d, hp22d, tm22d,
            "rewind: resumed -- practice from here" in t22d))
        cannot.append("R22D")
    else:
        check("R22D", "it carries speed" in t22d and hp22d[2] == "1" and ok22d[-1:] == ["0"]
              and bool(gr22d) and gr22d[-1] > 0,
              "row %s at %.0f u/s raised %s; chain hopped %s, after !r %s, after rest %s "
              "(start ok %s, ground %s)" % (
                  sl22d.group(1), math.hypot(v22d[0], v22d[1]), "it carries speed" in t22d,
                  hp22d[0], hp22d[1], hp22d[2], ok22d[-1:], gr22d[-1:]))

    # R22E (round 23): R22D's control -- only the idle load, then the same rest:
    # forgiven, in the server's words.  Premise: the load raised.
    hp22e = [m.group(1) for m in (re.search(r"\bhopped (\d) rearmhop", s) for s in sec["R22E"]) if m]
    t22e = txt("R22E")
    check("R22E", "rewind: resumed -- practice from here" in t22e and hp22e[-1:] == ["0"]
          and "the hopped start died with that run" in t22e,
          "the load raised %s, after rest hopped %s, forgiven %s" % (
              "rewind: resumed -- practice from here" in t22e, hp22e[-1:],
              "the hopped start died with that run" in t22e))

    # R23A (rounds 23-24): with a draft open the release of a key held into it
    # passes (took 0); a key pressed while typing is the draft's, press and
    # release (took 1 each).  Premise: the draft was open -- its ESC.
    k23a = dict((m.group(1), m.group(2)) for m in (
        re.search(r"vote key: scan (107 down 0|106 down 1|106 down 0|27 down 1) took (\d)", s)
        for s in sec["R23A"]) if m)
    check("R23A", k23a.get("27 down 1") == "1" and k23a.get("107 down 0") == "0"
          and k23a.get("106 down 1") == "1" and k23a.get("106 down 0") == "1",
          "ESC took %s; a held key's release took %s; a typed key took %s, its release %s" % (
              k23a.get("27 down 1"), k23a.get("107 down 0"), k23a.get("106 down 1"), k23a.get("106 down 0")))

    # R23B (round 23): rec_savelock 0 lets go only of a key's hold.  Premise: the
    # `+sl_hold` held (holding 1, the server's hold 1).  Verdict: still holding
    # after another key's press and release, and `-sl_hold` lets go.
    hd23b = [(m.group(1), m.group(2)) for m in (re.search(r"saveloc: locked \S+ refkey \S+ hold (\S+) holding (\S+)", s)
                                               for s in sec["R23B"]) if m]
    # Round 24: the other key's press reached SaveLoc_Key's branch (took 0: it
    # falls through to its bind), and -sl_hold let go on both sides.
    k23b = [m.group(1) for m in (re.search(r"vote key: scan 107 down 1 took (\d)", s) for s in sec["R23B"]) if m]
    if not (len(hd23b) == 3 and hd23b[0] == ("1", "1") and k23b == ["0"]):
        print("CANNOT GRADE R23B: saveloc reads %s, the other key took %s" % (hd23b, k23b))
        cannot.append("R23B")
    else:
        check("R23B", hd23b[1] == ("1", "1") and hd23b[2] == ("0", "0"),
              "held %s, after another key %s, after -sl_hold %s" % tuple(hd23b))

    # R24A (round 24): `2` held into a chat draft is let go by its own release.
    # Premises: the load key held (holding 1, the server's hold 1), the draft
    # open (its ESC taken).  Verdict: the hold is gone on both sides after the
    # release -- `took` cannot tell, the save-lock key takes it either way.
    hd24a = [(m.group(1), m.group(2)) for m in (re.search(r"saveloc: locked \S+ refkey \S+ hold (\S+) holding (\S+)", s)
                                               for s in sec["R24A"]) if m]
    k24a = [m.group(1) for m in (re.search(r"vote key: scan 27 down 1 took (\d)", s) for s in sec["R24A"]) if m]
    if not (len(hd24a) == 2 and hd24a[0] == ("1", "1") and k24a == ["1"]):
        print("CANNOT GRADE R24A: saveloc reads %s, the draft's ESC took %s" % (hd24a, k24a))
        cannot.append("R24A")
    else:
        check("R24A", hd24a[1] == ("0", "0"),
              "held %s; after its release under the draft %s" % (hd24a[0], hd24a[1]))

    # R24B (round 24): a save-lock key the rewind swallows says why -- once for
    # a press and its repeat.  Premise: the rewind was open, and took the press.
    st24b = status("R24B")
    t24b = txt("R24B")
    k24b = [m.group(1) for m in (re.search(r"vote key: scan 49 down 1 took (\d)", s) for s in sec["R24B"]) if m]
    if not (st24b[:1] and st24b[0].group(1) == "1" and k24b[:1] == ["1"]):
        print("CANNOT GRADE R24B: open %s, `1` took %s" % ([m.group(1) for m in st24b], k24b))
        cannot.append("R24B")
    else:
        n24b = t24b.count("rewind: the save-lock waits for the rewind")
        check("R24B", n24b == 1, "said %d time(s) for a press and its repeat" % n24b)

    # R23C (round 23): sl_save under the replay pin is refused and makes nothing.
    t23c = txt("R23C")
    check("R23C", "save: close the replay or rewind first" in t23c
          and not re.search(r"\bsave \d+ \(slot", t23c),
          "refused %s, a save made %s" % ("save: close the replay or rewind first" in t23c,
                                          bool(re.search(r"\bsave \d+ \(slot", t23c))))

    # R18F: a rewind pin asked from a non-running state on a running run is
    # refused, and the run stays clean.  Premise: the run was on the clock.
    t18f = txt("R18F")
    tm18f = last(r"timer: (\w+) on ", "R18F")
    pr18f = last(r"\bpractice (\d)\b", "R18F")
    ok18f = ("the run changed since you asked" in t18f
             and "practice run -- this run will not be saved" not in t18f
             and tm18f is not None and tm18f.group(1) == "running"
             and pr18f is not None and pr18f.group(1) == "0")
    check("R18F", ok18f, "refused %s, made practice %s, timer %s, practice %s" % (
        "the run changed since you asked" in t18f,
        "practice run -- this run will not be saved" in t18f,
        tm18f.group(1) if tm18f else None, pr18f.group(1) if pr18f else None))

    # R18G: asked from RUNNING at more ticks than the run has -- another run --
    # refused, and the run stays clean.  Premise: still R18F's run, on the clock.
    t18g = txt("R18G")
    tm18g = last(r"timer: (\w+) on ", "R18G")
    pr18g = last(r"\bpractice (\d)\b", "R18G")
    ok18g = ("the run changed since you asked" in t18g
             and "practice run -- this run will not be saved" not in t18g
             and tm18g is not None and tm18g.group(1) == "running"
             and pr18g is not None and pr18g.group(1) == "0")
    check("R18G", ok18g, "refused %s, made practice %s, timer %s, practice %s" % (
        "the run changed since you asked" in t18g,
        "practice run -- this run will not be saved" in t18g,
        tm18g.group(1) if tm18g else None, pr18g.group(1) if pr18g else None))

    # R18H: a save/load count other than the run's -- refused, the run clean.
    t18h = txt("R18H")
    tm18h = last(r"timer: (\w+) on ", "R18H")
    pr18h = last(r"\bpractice (\d)\b", "R18H")
    ok18h = ("the run changed since you asked" in t18h
             and "practice run -- this run will not be saved" not in t18h
             and tm18h is not None and tm18h.group(1) == "running"
             and pr18h is not None and pr18h.group(1) == "0")
    check("R18H", ok18h, "refused %s, made practice %s, timer %s, practice %s" % (
        "the run changed since you asked" in t18h,
        "practice run -- this run will not be saved" in t18h,
        tm18h.group(1) if tm18h else None, pr18h.group(1) if pr18h else None))

    # R18I: a go with no rewind pin is refused; the run stays on the clock.
    t18i = txt("R18I")
    tm18i = last(r"timer: (\w+) on ", "R18I")
    ok18i = ("not rewinding -- open the rewind again" in t18i
             and "rewind: resumed" not in t18i
             and tm18i is not None and tm18i.group(1) == "running")
    check("R18I", ok18i, "refused %s, resumed %s, timer %s" % (
        "not rewinding -- open the rewind again" in t18i, "rewind: resumed" in t18i,
        tm18i.group(1) if tm18i else None))

    # R18B: retry under the rewind ends the run first, and the restart's own line
    # says it restored no run; an idle save after it writes no .view prefix.
    # Premise: the rewind was open on a running run before the retry.
    st18b = status("R18B")
    t18b = txt("R18B")
    rr18b = last(r"retry -- (.*)$", "R18B")
    sv18b = last(r"^save (\d+) \(slot (\d+)\)", "R18B")
    v18b = ("save%s/run.view" % sv18b.group(2)) in views if sv18b else None
    ok18b = (bool(st18b) and st18b[0].group(1) == "1" and st18b[0].group(7) == "0"
             and "retry during a rewind" in t18b
             and rr18b is not None and "back where you were" in rr18b.group(1)
             and sv18b is not None and v18b is False)
    check("R18B", ok18b, "open before %s at the last resume %s, ended %s, restart said %r, "
          "idle save %s run.view %s" % (
              st18b[0].group(1) if st18b else None, st18b[0].group(7) if st18b else None,
              "retry during a rewind" in t18b, rr18b.group(1) if rr18b else None,
              sv18b.group(2) if sv18b else None, v18b))

    # R19: the trigger fires on the pinned body, and the body keeps no speed.
    sets19 = len(re.findall(r"basevel: SET ", txt("R19")))
    h19 = [float(m.group(1)) for m in (re.search(r"velocity \S+ \S+ \S+\s+horizontal ([0-9.]+)", s)
                                       for s in sec["R19"]) if m]
    ok19 = sets19 >= 5 and len(h19) >= 2 and max(h19) < 1
    check("R19", ok19, "trigger fired %d time(s) on the pinned body, horizontal pinned/released %s"
          % (sets19, h19))

    bad = len(re.findall(r"Unknown command", text))
    frames = len(re.findall(r"\w+\.qc:\d+:", text))
    check("Q", bad == 0 and frames == 0, "Unknown command %d, QC frames %d" % (bad, frames))
    print("%d check(s) failed" % len(fails))
    if cannot:
        print("CANNOT GRADE %s" % ", ".join(cannot))
    # Round 23: a FAIL is the verdict even beside a check that could not grade.
    return 1 if fails else (2 if cannot else 0)


if __name__ == "__main__":
    raise SystemExit(main())
