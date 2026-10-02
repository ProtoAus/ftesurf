#!/usr/bin/env python3
"""p473seq.py -- driver and grader for cfg/test/p473seq.cfg (Patch 473: a replay's
Segments column is built at the recording's tick, not the server's).

Stages ftesurf/data/p473seq.rec -- tools/p470tick.py's re-ticked copy of the
fixture, under its own name -- runs the cfg, removes the file, and compares the
two `replay seq` dumps the cfg takes under server ticks 0.015 and 0.01.

    python tools/p473seq.py [--rec <path>] [--exe ftesurf64.exe] [--grade-only]

Exit 0 pass, 1 fail, 2 cannot grade.

RESULT (2026-10-03, the N100 laptop; surf_colin_blaster_69000 runid
20260930-085843-0 re-ticked to 0.01):
  fixed   csprogs EF78D1D34178CB53: S1 19 rows each, 0 differ; S2 9 air rows.
          Row 0's ceiling reads 99.281 under BOTH server ticks.
  control 567E80F25E1DA377 (Watch_BuildSeq's one line removed): 14 of 19 rows
          differ -- row 0's ceiling 85.500 under the 0.015 server, 99.281 under
          the 0.01 one, so the fixed column is the file's.
  The movement lock reverts a typed pm_ticrate (`... restored to "0.015"`); the
  cfg's sv_cheats 1 is the lock's own way off, set for both halves.
"""
import argparse
import hashlib
import os
import re
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import p470tick                                     # noqa: E402  (the staging)

ROOT, GAMEDIR = p470tick.ROOT, p470tick.GAMEDIR
LOG = os.path.join(GAMEDIR, "logs", "p473seq.log")
p470tick.STAGED = os.path.join(GAMEDIR, "data", "p473seq.rec")


def run(exe, timeout):
    if os.path.exists(LOG):
        os.remove(LOG)
    p = subprocess.Popen([os.path.join(ROOT, exe), "-WindowStyle", "Minimized",
                          "+exec", "test/p473seq.cfg"], cwd=ROOT,
                         creationflags=0x08000000 if os.name == "nt" else 0,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
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
    if "=== p473seq done ===" not in txt:
        print("CANNOT GRADE: the run did not reach its end")
        return 2
    dumps = {}
    for tag in ("0.015", "0.01"):
        sec = txt.split("=== p473seq server %s ===" % tag, 1)[1].split("=== p473seq", 1)[0]
        live = re.search(r'"pm_ticrate" is "([^"]+)"', sec)
        rows = [ln.split()[1:] for ln in
                (re.sub(r"^\S+ \S+ ", "", r) for r in sec.splitlines())
                if ln.startswith("lns ")]
        dumps[tag] = rows
        print("     server %s (cvar reads %s): %d rows"
              % (tag, live.group(1) if live else "?", len(rows)))
        if not live or abs(float(live.group(1)) - float(tag)) > 1e-6:
            print("CANNOT GRADE: the server's tick was not %s for this dump" % tag)
            return 2
    a, b = dumps["0.015"], dumps["0.01"]
    if not a or any(len(r) < 8 for r in a + b):
        print("CANNOT GRADE: a dump is empty or has no ceiling column")
        return 2
    diff = [i for i, (x, y) in enumerate(zip(a, b)) if x != y]
    ok1 = len(a) == len(b) and not diff
    first = ""
    if diff:
        first = "  (first: row %d %s against %s)" % (diff[0], " ".join(a[diff[0]]),
                                                    " ".join(b[diff[0]]))
    print("%s S1  the two columns are identical: %d and %d rows, %d differ%s"
          % ("PASS" if ok1 else "FAIL", len(a), len(b), len(diff), first))
    air = [r for r in a if float(r[6]) > 0]
    ok2 = len(air) >= 3
    print("%s S2  %d row(s) carry an air ceiling" % ("PASS" if ok2 else "FAIL", len(air)))
    fails = (0 if ok1 else 1) + (0 if ok2 else 1)
    print("2 check(s), %d failed" % fails)
    return 1 if fails else 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rec", default=p470tick.SRC)
    ap.add_argument("--exe", default="ftesurf64.exe")
    ap.add_argument("--grade-only", action="store_true")
    ap.add_argument("--timeout", type=float, default=240)
    a = ap.parse_args()
    if not a.grade_only:
        with open(os.path.join(GAMEDIR, "csprogs.dat"), "rb") as f:
            print("csprogs %s" % hashlib.sha256(f.read()).hexdigest()[:16].upper())
        p470tick.stage(a.rec, 0.01)
        try:
            run(a.exe, a.timeout)
        finally:
            os.remove(p470tick.STAGED)
            print("cleanup: staged file removed; p473 names left in data/: %s"
                  % ([n for n in os.listdir(os.path.join(GAMEDIR, "data"))
                      if "p473" in n] or "none"))
    return grade()


if __name__ == "__main__":
    sys.exit(main())
