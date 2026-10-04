#!/usr/bin/env python3
"""One-off: prove tools/p486injrn.py can FAIL.  Not shipped as a tool -- the
mutations are recorded in the cfg header and re-runnable by hand.

A grader that passes on a mutated log is a grader that measures nothing, which is
the exact shape of the two arms Patch 403 shipped with an inherited RESULT block.
Each mutant below is a defect the patch could really have, and the grader must
name it.

THE VALUES ARE READ OUT OF THE LOG, NOT HARD-CODED, and that was not tidiness.
The first cut of this script substituted the literal `frames 183` and the run it
was pointed at had produced 181 -- so three mutants mutated NOTHING, the grader
passed them, and the script reported "3 not caught" while looking like a grader
bug.  A mutant that does not mutate is the same false green as a grader that does
not grade, and it is silent in exactly the same way.
"""
import io
import os
import re
import subprocess
import sys

LOG = os.path.join("ftesurf", "logs", "p486injrn.log")
MUT = os.path.join("ftesurf", "logs", "p486mut.log")

JRN = re.compile(r"jrnident:\s+said\s+(-?[\d.]+)\s+have\s+(-?[\d.]+)\s+"
                 r"frames\s+(-?[\d.]+)\s+ghosts\s+(-?[\d.]+)\s+viol\s+(-?[\d.]+)"
                 r"\s+bad\s+(-?[\d.]+)\s+skip\s+(-?[\d.]+)")
ARM = re.compile(r"P486 ARM (\d)")
KEYS = ("said", "have", "frames", "ghosts", "viol", "bad", "skip")


def read_arm(path, arm):
    """The last jrnident reading inside one arm, as a dict of ints."""
    cur, got = 0, None
    for ln in io.open(path, errors="replace"):
        m = ARM.search(ln)
        if m:
            cur = int(m.group(1))
        m = JRN.search(ln)
        if m and cur == arm:
            got = {k: int(float(v)) for k, v in zip(KEYS, m.groups())}
    return got


def arm_lines(s, arm, fn):
    """Rewrite the jrnident lines inside one arm."""
    out, cur = [], 0
    for ln in s.split("\n"):
        m = ARM.search(ln)
        if m:
            cur = int(m.group(1))
        if cur == arm and "jrnident" in ln:
            ln = fn(ln)
        out.append(ln)
    return "\n".join(out)


def setfield(ln, key, val):
    return re.sub(key + r" -?[\d.]+", "%s %d" % (key, val), ln)


def run(s, label, expect_fail=True):
    io.open(MUT, "w", errors="replace").write(s)
    p = subprocess.run([sys.executable, "tools/p486injrn.py", "--log", MUT],
                       capture_output=True, text=True)
    fails = [l for l in p.stdout.split("\n") if l.startswith("FAIL")]
    print("%-58s exit=%d  FAILs=%d" % (label, p.returncode, len(fails)))
    for f in fails[:3]:
        print("       " + f)
    if expect_fail:
        return 0 if (p.returncode != 0 and fails) else 1
    return 0 if (p.returncode == 0 and not fails) else 1


src = io.open(LOG, errors="replace").read()

# Read the real numbers out of the log this script is pointed at.
A1 = read_arm(LOG, 1)
A2 = read_arm(LOG, 2)
A4 = read_arm(LOG, 4)
if not (A1 and A2 and A4):
    print("FAIL cannot read arms 1/2/4 out of %s -- run the harness first" % LOG)
    sys.exit(1)
F2 = A2["frames"]
print("read from the log: ARM1 frames=%d  ARM2 frames=%d  ARM4 frames=%d"
      % (A1["frames"], F2, A4["frames"]))
if F2 <= 0:
    print("FAIL ARM2 frames is %d, so there is nothing to mutate against" % F2)
    sys.exit(1)
print()

bad = 0

# 1 -- the console forged the fact (ARM 3 reads the typed 999999).
s = arm_lines(src, 3, lambda l: setfield(l, "frames", 999999))
bad += run(s, "M1 ARM3 frames=999999 (console wrote the fact)")

# 2 -- ARM 1 reads 0 instead of -1: the Patch 484 arm-A defect, one layer up.
def zero(ln):
    for k in KEYS[2:]:
        ln = setfield(ln, k, 0)
    return ln
s = arm_lines(src, 1, zero)
bad += run(s, "M2 ARM1 reads 0 not -1 (unmeasured wearing clean)")

# 3 -- dead channel: ARM 2 never differs from ARM 1.
s = arm_lines(src, 2, lambda l: setfield(l, "frames", -1))
bad += run(s, "M3 ARM2 frames=-1 (dead channel / silence)")

# 4 -- the reset never propagates: ARM 4 still holds ARM 2's number.
s = arm_lines(src, 4, lambda l: setfield(l, "frames", F2))
bad += run(s, "M4 ARM4 frames=%d (cache never re-sent)" % F2)

# 5 -- the two ends drift by one: the server was told something other than what
#      the engine's own cvar printed in the same arm.
s = arm_lines(src, 2, lambda l: setfield(l, "frames", F2 - 1))
bad += run(s, "M5 ARM2 server frames=%d vs engine %d (drift)" % (F2 - 1, F2))

# 6 -- honest input accused.
s = arm_lines(src, 2, lambda l: setfield(l, "viol", 7))
bad += run(s, "M6 ARM2 viol=7 (an honest run accused)")

# 7 -- CONTROL: the unmutated log must still pass.
bad += run(src, "CONTROL unmutated (must be exit 0, 0 FAILs)", expect_fail=False)

os.path.exists(MUT) and os.remove(MUT)
print()
print("mutants not caught / control failed:", bad)
sys.exit(1 if bad else 0)
