#!/usr/bin/env python3
"""p497tick.py -- driver and grader for cfg/test/p497tick.cfg (Patch 497: a
replay turns ticks into seconds at the MOVER's rate).

WHY A DRIVER.  The subject is a file whose two tick keys disagree, and no
recording in this tree has that: the writer emits one value for both (measured
over 6056 .rec files in ftesurf/data -- 5569 equal, 487 with no `movetickrate`,
0 differ).  So this stages two synthetic headers over one real recording,
ftesurf/data/p497{diff,same}.rec, runs the cfg, grades the log, and REMOVES both.
The source is opened read-only.

    python tools/p497tick.py [--rec <path>] [--exe ftesurf64.exe] [--grade-only]
                             [--timeout 300]

--rec must be a v4+ recording of the cfg's map (bhop_eazy); the default is the
one this was written against.

THREE RATES, so every verdict names one cause: this map's server runs 0.01, the
diff file says `tickrate 0.025` / `movetickrate 0.008`, the same file says 0.02
for both.  A reader that fell back to the server's rate, one that took the
file's `tickrate` and one that took its `movetickrate` therefore print three
different numbers, and T5 (the same file, 0.02 on both builds) is what stops the
arm passing by printing a constant.

THE CONTROL is this patch compiled out -- `git worktree add <tmp> HEAD~1`, copy
src/fteqcc64.exe in, build the three .src there with -NoDeploy, copy its
csprogs.dat over the install's, run this driver, put the subject's back.  The
hash below is printed by the driver so the two sides cannot be confused.
Predicted on the control: T1-T4 read 0.02500 and T5 still reads 0.02000.
Exit 0 pass, 1 fail, 2 cannot grade.
"""
import argparse
import hashlib
import os
import re
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GAMEDIR = os.path.join(ROOT, "ftesurf")
LOG = os.path.join(GAMEDIR, "logs", "p497tick.log")
SRC = os.path.join(GAMEDIR, "data", "runs", "bhop_eazy", "main", "0000013_run.rec")
CFGMAP = "bhop_eazy"

# (staged name, tickrate, movetickrate)
FILES = (("p497diff.rec", 0.025, 0.008), ("p497same.rec", 0.02, 0.02))
LIVE = 0.01           # what this map's server runs; nothing graded may read it


def staged(name):
    return os.path.join(GAMEDIR, "data", name)


def stage(src):
    """The source's bytes with the header's two tick keys rewritten.  Refuses to
    overwrite: a leftover from a previous run is a result someone should read."""
    for name, _, _ in FILES:
        if os.path.exists(staged(name)):
            raise SystemExit("%s exists -- a previous run did not clean up; look "
                             "at it before removing it" % staged(name))
    with open(src, "r", newline="", errors="surrogateescape") as f:
        lines = f.readlines()
    for name, tr, mtr in FILES:
        seen, body, out = set(), False, []
        for line in lines:
            if not body:
                key = line.split(" ", 1)[0].strip()
                if key == "map" and line.split()[1] != CFGMAP:
                    raise SystemExit("%s is a recording of %s; the cfg loads %s"
                                     % (src, line.split()[1], CFGMAP))
                if key in ("tickrate", "movetickrate"):
                    eol = line[len(line.rstrip("\r\n")):]
                    line = "%s %g%s" % (key, tr if key == "tickrate" else mtr, eol)
                    seen.add(key)
                if key == "begin":
                    body = True
            out.append(line)
        if seen != {"tickrate", "movetickrate"}:
            raise SystemExit("%s states %s; this arm needs both keys to disagree"
                             % (src, sorted(seen) or "neither"))
        with open(staged(name), "w", newline="", errors="surrogateescape") as f:
            f.writelines(out)
        print("staged %s: tickrate %g movetickrate %g" % (name, tr, mtr))


def unstage():
    for name, _, _ in FILES:
        p = staged(name)
        if os.path.exists(p):
            os.remove(p)                       # an error here is the result
    left = [n for n in os.listdir(os.path.dirname(staged("x"))) if "p497" in n]
    print("cleanup: staged files removed; p497 names left in data/: %s"
          % (left or "none"))
    return not left


def run(exe, timeout):
    if os.path.exists(LOG):
        os.remove(LOG)
    flags = 0x08000000 if os.name == "nt" else 0
    p = subprocess.Popen([os.path.join(ROOT, exe), "-WindowStyle", "Minimized",
                          "+exec", "test/p497tick.cfg"], cwd=ROOT,
                         creationflags=flags, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL)
    t0 = time.time()
    while p.poll() is None and time.time() - t0 < timeout:
        time.sleep(1)
    if p.poll() is None:
        p.kill()
        print("the run did not exit in %g s -- killed" % timeout)


def parse(log):
    """{file section: {path, tick, bar, lnmv[slot], lnsb}} plus done/live/focus."""
    lines = [re.sub(r"^\d{4}-\d\d-\d\d \d\d:\d\d:\d\d ", "", r.rstrip("\n"))
             for r in open(log, "r", errors="replace")]
    out = {"done": False, "live": None, "focus": 0, "diff": None, "same": None}
    cur, lastmv = None, None
    for line in lines:
        f = line.split()
        if "[focus] window is foreground" in line:
            out["focus"] += 1
        m = re.search(r"=== p497tick (\w+)(?: \d)? ===", line)
        if m:
            sect = m.group(1)
            if sect == "done":
                out["done"] = True
                cur = None
            elif sect in ("diff", "same"):
                cur = out[sect] = {"path": None, "bar": None, "lnmv": {},
                                   "lnsb": None}
            # any other echo (live/colours/seq/line) is a marker inside the
            # section it sits in and must not drop it
            continue
        m = re.match(r'"pm_ticrate" is "([^"]+)"', line)
        if m and out["live"] is None:
            out["live"] = float(m.group(1))
        if cur is None:
            continue
        m = re.match(r"replay: \S*(p497\w+\.rec)", line)
        if m and cur["path"] is None:
            cur["path"] = m.group(1)
        m = re.match(r"\s+bar tick (\S+)\s+ideal", line)
        if m and cur["bar"] is None:
            cur["bar"] = float(m.group(1))
        if line.startswith("lnmv ") and len(f) >= 2:
            lastmv = float(f[1])              # lncb below names its slot
        elif line.startswith("lncb ") and len(f) >= 2 and lastmv is not None:
            cur["lnmv"][int(float(f[1]))] = lastmv
            lastmv = None
        elif line.startswith("lnsb ") and len(f) >= 3 and cur["lnsb"] is None:
            cur["lnsb"] = float(f[2])
    return out


def grade():
    if not os.path.exists(LOG):
        print("CANNOT GRADE: no log at %s" % LOG)
        return 2
    d = parse(LOG)
    if not d["done"]:
        print("CANNOT GRADE: the cfg did not reach its done marker")
        return 2
    if d["live"] is None or abs(d["live"] - LIVE) > 1e-6:
        print("CANNOT GRADE: the server's pm_ticrate read %s, want %g -- the three "
              "rates are not three" % (d["live"], LIVE))
        return 2
    if d["focus"]:
        print("NOTE: %d `[focus] window is foreground` line(s) -- someone was at "
              "the machine during this run" % d["focus"])
    for k in ("diff", "same"):
        c = d[k]
        if not c or c["path"] != "p497%s.rec" % k:
            print("CANNOT GRADE: the %s section loaded %s"
                  % (k, c and c["path"]))
            return 2
        missing = [n for n in ("bar", "lnsb") if c[n] is None] + \
                  [n for n in (0, 1) if n not in c["lnmv"]]
        if missing:
            print("CANNOT GRADE: the %s section printed no %s"
                  % (k, ", ".join(str(m) for m in missing)))
            return 2
    rates = [FILES[0][1], FILES[0][2], FILES[1][2]]
    if any(abs(d["live"] - r) < 1e-6 for r in rates):
        print("CANNOT GRADE: the server's rate %g is one of the file's (%s) -- "
              "a fallback would be indistinguishable"
              % (d["live"], ", ".join("%g" % r for r in rates)))
        return 2

    fails = 0

    def verdict(ok, text):
        nonlocal fails
        fails += 0 if ok else 1
        print("%s %s" % ("PASS" if ok else "FAIL", text))

    def close(v, want):
        return v is not None and abs(v - want) < 1e-6

    c = d["diff"]
    want = FILES[0][2]                       # the diff file's movetickrate
    other = FILES[0][1]                      # its tickrate, what a control reads
    verdict(close(c["bar"], want),
            "T1  the strafe bar's rate: `bar tick` %.5f, want %.5f -- the file's "
            "movetickrate (its tickrate is %g, the server's %g)"
            % (c["bar"], want, other, d["live"]))
    verdict(close(c["lnmv"][0], want),
            "T2  Line_Tick slot 0 (the replay): lnmv %.5f, want %.5f"
            % (c["lnmv"][0], want))
    verdict(close(c["lnmv"][1], want),
            "T3  Line_Tick slot 1 (the board-line job): lnmv %.5f, want %.5f"
            % (c["lnmv"][1], want))
    verdict(close(c["lnsb"], want),
            "T4  replay seq: lnsb %s, want %g" % (c["lnsb"], want))

    s = d["same"]
    want2 = FILES[1][2]                      # both keys of the same file
    ok = all((close(s["bar"], want2), close(s["lnmv"][0], want2),
              close(s["lnmv"][1], want2), close(s["lnsb"], want2)))
    verdict(ok,
            "T5  self-control, both keys %g: bar %.5f lnmv %.5f/%.5f lnsb %s"
            % (want2, s["bar"], s["lnmv"][0], s["lnmv"][1], s["lnsb"]))
    obs = [c["bar"], c["lnmv"][0], c["lnmv"][1], c["lnsb"],
           s["bar"], s["lnmv"][0], s["lnmv"][1], s["lnsb"]]
    fb = ["%g" % v for v in obs if v is not None and abs(v - d["live"]) < 1e-6]
    verdict(not fb,
            "T6  nothing fell back to the server's %g: %d observables, %s"
            % (d["live"], len(obs), ", ".join(fb) if fb else "none of them it"))
    print("6 check(s), %d failed" % fails)
    return 0 if fails == 0 else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rec", default=SRC)
    ap.add_argument("--exe", default="ftesurf64.exe")
    ap.add_argument("--grade-only", action="store_true")
    ap.add_argument("--timeout", type=float, default=300)
    a = ap.parse_args()
    if not a.grade_only:
        with open(os.path.join(GAMEDIR, "csprogs.dat"), "rb") as f:
            print("csprogs %s" % hashlib.sha256(f.read()).hexdigest()[:16].upper())
        stage(a.rec)
        try:
            run(a.exe, a.timeout)
        finally:
            clean = unstage()
        if not clean:
            return 1
    return grade()


if __name__ == "__main__":
    sys.exit(main())
