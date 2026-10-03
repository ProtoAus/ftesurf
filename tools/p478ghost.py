#!/usr/bin/env python3
"""p478ghost.py -- driver and grader for cfg/test/p478ghost.cfg (Patch 478: a
ghost, or a Multi-Session resume phase, that leaves a start box starts no run
where it ends).

    python tools/p478ghost.py [--exe ftesurf64.exe] [--grade-only] [--timeout 420]

G3-G8 save, park, retry and resume on surf_dune and bhop_eazy, so those maps'
data/saves and data/resume folders are PARKED (renamed) for the run and put
back, each listing checked.  The game's folders for those two maps, and
data/parts (SCOPE), are listed (files AND dirs) before; what the run made there
is printed and removed, each removal checked, and D passes only if they then
list as they did.  Anything new elsewhere in data/ is another tool's or
another run's (another session works there) and is reported, not touched.
The progs hashes, what the run left in the parks (each save row's state,
latch and origin too) and D's answer are kept in logs/p478ghost.made.json,
which --grade-only reads (--made and --log name kept copies).  Exit 0 pass,
1 fail, 2 cannot grade.
"""
import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GAME = os.path.join(ROOT, "ftesurf")
LOG = os.path.join(GAME, "logs", "p478ghost.log")
MADE = os.path.join(GAME, "logs", "p478ghost.made.json")
DATA = os.path.join(GAME, "data")
STAMP = re.compile(r"^\d{4}-\d\d-\d\d \d\d:\d\d:\d\d ")
SECTIONS = ("G1", "G8", "G2", "G6", "G7", "G7A", "G3", "G3P", "G3A", "G4", "G4A", "G5", "G5P", "G5A")
EDGE_Y = 769 + 16       # surf_dune's start box +y face, plus the hull's half-width
PROGS = {}              # the progs the run was graded on, kept in MADE
MAPS = ("surf_dune", "bhop_eazy")
PARKS = [os.path.join(DATA, d, m) for m in MAPS for d in ("saves", "resume")]
# Round 6: only what this arm's maps can write.  Another run of the game, on
# another map, writes the same folders.
SCOPE = [os.path.join(d, m) for m in MAPS for d in ("runs", "evidence", "resume", "saves")] + ["parts"]


def scoped(rel):
    return any(rel == q or rel.startswith(q + os.sep) for q in SCOPE)


def row(path):
    """A save row's state, latch and origin, as its own file says them."""
    out = {}
    for s in open(path, errors="replace"):
        k, _, v = s.strip().partition(" ")
        if k in ("state", "azone", "armzone", "origin", "velocity"):
            out[k] = v
    return out


def tree(d):
    """Every file AND directory under d, as (kind, relative path)."""
    out = set()
    for r, ds, fs in os.walk(d):
        out |= {("d", os.path.relpath(os.path.join(r, x), d)) for x in ds}
        out |= {("f", os.path.relpath(os.path.join(r, x), d)) for x in fs}
    return out


def run(exe, timeout):
    for p in PARKS:
        # Ours, or another harness's (p477rewind parks the saves as .p477park):
        # two drivers restoring one path would delete each other's restores.
        for q in os.listdir(os.path.dirname(p)) if os.path.isdir(os.path.dirname(p)) else []:
            if q.startswith(os.path.basename(p) + ".") and q.endswith("park"):
                raise SystemExit("a park is already there: %s -- another harness, or restore it first"
                                 % os.path.join(os.path.dirname(p), q))
    orig = tree(DATA)
    kept = {p: tree(p) if os.path.exists(p) else set() for p in PARKS}
    parked, runcopy, rows = [], {}, {}
    try:
        for p in PARKS:
            if os.path.exists(p):
                os.rename(p, p + ".p478park")
                parked.append(p)
        before = tree(DATA)
        if os.path.exists(LOG):
            os.replace(LOG, LOG + ".prev")
        subprocess.run([os.path.join(ROOT, exe), "-WindowStyle", "Minimized",
                        "+exec", "cfg/test/p478ghost.cfg"], cwd=ROOT, timeout=timeout)
    finally:
        made = sorted(tree(DATA) - before) if "before" in locals() else []
        other = [r for k, r in made if not scoped(r)]
        if other:
            print("data/ new outside this arm's maps, left alone: %s" % ", ".join(other))
        made = [(k, r) for k, r in made if scoped(r)]
        for p in PARKS:
            rel = os.path.relpath(p, DATA)
            if os.path.exists(p):
                # The run's copy, listed before it goes: G4 grades its slot.
                runcopy[rel] = sorted(r for k, r in tree(p) if k == "f")
                print("%s as the run left it: %s" % (rel, ", ".join(runcopy[rel]) or "no files"))
                for r in runcopy[rel]:
                    if r.endswith("state.txt"):
                        rows[os.path.join(rel, r)] = row(os.path.join(p, r))
                shutil.rmtree(p)
            if p in parked:
                os.rename(p + ".p478park", p)
            back = tree(p) if os.path.exists(p) else set()
            print("%s restored: %s (%d entries, before %d)" % (
                rel, "yes" if back == kept[p] else "NO -- LISTINGS DIFFER", len(back), len(kept[p])))
            if back != kept[p]:
                raise SystemExit("%s did not come back as it was" % p)
        rels = [os.path.relpath(p, DATA) for p in PARKS]
        rest = [(k, r) for k, r in made if not any(r == q or r.startswith(q + os.sep) for q in rels)]
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
    differs = sorted(r for k, r in tree(DATA) ^ orig if scoped(r))
    with open(MADE, "w") as fh:
        json.dump({"runcopy": runcopy, "rows": rows, "differs": differs, "progs": PROGS}, fh)
    return runcopy, rows, differs


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
    ap.add_argument("--timeout", type=int, default=420)
    ap.add_argument("--made", default=MADE)
    ap.add_argument("--log", default=LOG)
    a = ap.parse_args()
    for f in ("csprogs.dat", "qwprogs.dat"):
        PROGS[f] = hashlib.sha256(open(os.path.join(GAME, f), "rb").read()).hexdigest()[:16].upper()
    if a.grade_only:
        if not os.path.exists(a.made):
            print("CANNOT GRADE: %s is missing -- the slot listing and D need a run" % a.made)
            return 2
        m = json.load(open(a.made))
        runcopy, rows, differs = m["runcopy"], m.get("rows"), m["differs"]
        if rows is None:
            print("CANNOT GRADE: %s predates the rows record G8 reads" % a.made)
            return 2
        PROGS.clear()
        PROGS.update(m.get("progs", {}))
    else:
        runcopy, rows, differs = run(a.exe, a.timeout)
    for f in ("csprogs.dat", "qwprogs.dat"):
        print("%s %s" % (f, PROGS.get(f, "not recorded")))
    lines = [STAMP.sub("", l.rstrip("\n")) for l in open(a.log, errors="replace")]
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

    def field(name, pat):
        return [m.group(1) for m in (re.search(pat, s) for s in sec[name]) if m]

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
    # the start: `stage fill: prime 1`).  Premise: its own ghost on and off.
    st2, cl2 = states("G2"), classes("G2")
    t2 = "\n".join(sec["G2"])
    if not ("ghost -- `ghost` again to go back" in t2 and "ghost off" in t2):
        print("CANNOT GRADE G2: its ghost on/off lines are missing")
        return 2
    pr2 = [m.group(1) for m in (re.search(r"stage fill: prime (\d)", s) for s in sec["G2"]) if m]
    check("G2", len(st2) == 2 and st2[0] == "armed" and st2[1] == "running"
          and bool(cl2) and cl2[-1] == "clean" and "as a ghost" not in t2
          and bool(pr2) and pr2[-1] == "1",
          "after the unghost %s, after +forward %s class %s prime %s" % (
              st2[0] if st2 else None, st2[1] if len(st2) > 1 else None, cl2[-1] if cl2 else None,
              pr2[-1] if pr2 else None))

    # G8.  Round 5.  Premises: the save row is IDLE, latched -1, mid-air in the
    # box (its own file, z above the standing 15052), and the live scan armed
    # the body that fell into the box after it.  Verdict: the load of that row
    # arms nothing -- idle, where the stale -1 armed it before round 5.
    t8 = "\n".join(sec["G8"])
    st8 = states("G8")
    mid = [r for r, v in rows.items()
           if v.get("state") == "0" and v.get("azone") == "-1"
           and len(v.get("origin", "").split()) == 3 and float(v["origin"].split()[2]) > 15100]
    if not (mid and "setpos:" in t8 and len(st8) == 2 and st8[0] == "armed"):
        print("CANNOT GRADE G8: rows %s, setpos said %s, states %s" % (rows, "setpos:" in t8, st8))
        return 2
    check("G8", st8[1] == "idle", "row %s %s; after the box armed live, the load: %s" % (
        mid[0], rows[mid[0]], st8[1]))

    # G6.  Round 6.  Premises, from the timer under the ghost: ghosted, the
    # load's practice, and the gate's arm pending (arm zone -1).  Verdict: after
    # the unghost the practice stands (the unghost armed no box).  Before round
    # 6 the unghost's scan armed it: practice 0, start ok 0.
    def ghostload(name):
        g, pr, az = field(name, r"^\s*ghost (\d)  ghosted"), field(name, r"\bpractice (\d)\b"), \
            field(name, r"arm zone (-?\d+) ")
        return g, pr, az

    g6, pr6, az6 = ghostload("G6")
    ok6 = field("G6", r"start: ok (\d) ")
    t6 = "\n".join(sec["G6"])
    if not (len(g6) == 2 and g6[0] == "1" and len(pr6) == 2 and pr6[0] == "1"
            and len(az6) == 2 and az6[0] == "-1" and "ghost off" in t6):
        print("CANNOT GRADE G6: ghost %s, practice %s, arm zone %s, ghost off %s" % (
            g6, pr6, az6, "ghost off" in t6))
        return 2
    check("G6", states("G6")[-1:] == ["armed"] and pr6[1] == "1" and g6[1] == "0",
          "under the ghost practice %s arm zone %s; after the unghost %s practice %s arm zone %s "
          "start ok %s" % (pr6[0], az6[0], states("G6")[-1:], pr6[1], az6[1], ok6[-1:]))

    # G7.  Round 6.  The same premise under the ghost, then `retry`: its own
    # line, and after it the practice stands.  Before round 6's retry line the
    # point held the gate's -1 and the restore armed the box (practice 0).
    g7, pr7, az7 = ghostload("G7")
    t7 = "\n".join(sec["G7"] + sec["G7A"])
    pr7a = field("G7A", r"\bpractice (\d)\b")
    if not (g7[:1] == ["1"] and pr7[:1] == ["1"] and az7[:1] == ["-1"]
            and "retry -- back where you were" in t7):
        print("CANNOT GRADE G7: ghost %s, practice %s, arm zone %s, retried %s" % (
            g7, pr7, az7, "retry -- back where you were" in t7))
        return 2
    check("G7", states("G7A")[-1:] == ["armed"] and pr7a[-1:] == ["1"],
          "under the ghost practice %s arm zone %s; after the retry %s practice %s" % (
              pr7[0], az7[0], states("G7A")[-1:], pr7a[-1:]))

    # G3.  Premises: the reload parked G3's own run (a few seconds -- the parks
    # hold nothing older), and the phase began.  Verdict, on the door's own
    # consequences: `!r` and `retry` refused, no warp and no retry taken, and
    # the resume applied.  Before 478: "start of the map", "retry -- back where
    # you were", no resume, and a CLEAN run from the park point.
    t3 = "\n".join(sec["G3P"] + sec["G3A"])
    pk3 = re.search(r"resume: your run here is paused at (\d+):(\d+)\.(\d+)", t3)
    if not (pk3 and int(pk3.group(1)) == 0 and int(pk3.group(2)) < 30):
        print("CANNOT GRADE G3: no park of G3's own run (%s)" % (pk3.group(0) if pk3 else None))
        return 2
    st3, cl3, y3 = states("G3A"), classes("G3A"), ys("G3A")
    ok3 = ("resume: wait for the resume to finish" in t3
           and "retry: wait for the resume to finish" in t3
           and "start of the map" not in t3 and "retry -- back where you were" not in t3
           and "resume: run resumed at" in t3)
    check("G3", ok3, "park %s; !r refused %s, retry refused %s, warped %s, retried %s, "
          "resumed %s; after: %s class %s at y %s" % (
              pk3.group(0).split(" at ")[-1], "resume: wait for the resume to finish" in t3,
              "retry: wait for the resume to finish" in t3, "start of the map" in t3,
              "retry -- back where you were" in t3, "resume: run resumed at" in t3,
              st3[-1] if st3 else None, cl3[-1] if cl3 else None,
              "%.0f" % y3[-1] if y3 else None))

    # G4.  The reverse order: `retry` then `!resume` in one packet.  Premise: a
    # park was offered first.  Verdict: the accept is refused while the restart
    # is pending, the slot is offered again after it, and the run leaves it
    # whole (ms.txt, no claim).  Before 478's round 3 the accept claimed it, the
    # restart skipped the abort, and the claim stood alone -- never offered.
    t4 = "\n".join(sec["G4"] + sec["G4A"])
    offers4 = re.findall(r"resume: your run here is paused at", t4)
    slot = runcopy.get(os.path.join("resume", "surf_dune"))
    if not offers4 or slot is None:
        print("CANNOT GRADE G4: offers %d, slot listed %s" % (len(offers4), slot is not None))
        return 2
    claim4 = any(f.endswith("ms.claim.txt") for f in slot)
    ms4 = any(f.endswith("ms.txt") for f in slot)
    check("G4", "the map is restarting for a retry" in t4 and len(offers4) >= 2 and ms4 and not claim4,
          "refused %s, offered %d time(s), slot ms.txt %s claim %s" % (
              "the map is restarting for a retry" in t4, len(offers4), ms4, claim4))

    # G5.  A `kill` in a resume countdown on bhop_eazy, whose spawns are all in
    # the start box: the respawn arms that box as any respawn does.  Premises:
    # G5's own park was offered, and the phase began (its `!r` refused -- only a
    # resume phase says "wait for the resume to finish").  Round 3 scanned the
    # latches at the spawn in SV_MsAbort, and the box never armed (idle).
    t5 = "\n".join(sec["G5P"])
    st5 = states("G5A")
    if not ("resume: your run here is paused at" in t5
            and "resume: wait for the resume to finish" in t5):
        print("CANNOT GRADE G5: offered %s, phase began %s" % (
            "resume: your run here is paused at" in t5, "resume: wait for the resume to finish" in t5))
        return 2
    check("G5", bool(st5) and st5[-1] == "armed", "after the kill: %s" % (st5[-1] if st5 else None))

    check("D", not differs, "data/ lists as it did" if not differs
          else "data/ differs: %s" % ", ".join(differs))
    print("%d check(s) failed" % len(fails))
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
