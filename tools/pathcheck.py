#!/usr/bin/env python3
"""
pathcheck.py -- does the replay's drawn path reach the end of the run?

WHY THIS EXISTS, AND WHY IT IS A SEPARATE TOOL FROM reccheck.py.

reccheck.py validates a recording as a FILE: its grammar, its column counts, its
monotone clock.  This validates what cl_watch.qc will MAKE of that file, which is
a different question and one no amount of file-level checking can answer.  Build
43's bug was exactly there: every .rec on disk was and is perfectly valid, and
twelve of them still drew a path that stopped short of the run's own end.

The report was "Demo lines in demos do not draw the entire demo, it stops at the
last 10% for some reason", and the reason is arithmetic.  Watch_BuildCurve set
its subdivision step from the path's total length divided by the point budget,
then spent ceil(len/step) points per span.  Ceil costs up to one extra point per
span, so the real spend was budget + spans against a table of budget + 2, and the
overrun was silently dropped off the END of the run -- the guard inside the
subdivision loop broke only that loop, so every later span ran and emitted
nothing.

This file re-implements BOTH halves of that pipeline -- the control-point
selection in Watch_Scan and the Catmull-Rom budget in Watch_BuildCurve -- closely
enough to reproduce the saturation, and reports which files truncate and by how
much.  It is a MODEL, not the code: it does not evaluate the spline, because
where the points land does not change how many of them there are.

    python tools/pathcheck.py ftesurf/data/runs

Exit status is 1 if any file truncates, so it can be a gate.  Pass --old to model
build 42's arithmetic instead, which is how the 12-of-57 baseline was taken.

KEEP THIS IN STEP WITH cl_watch.qc.  The constants below are the ones that
matter; if WT_CTLMAX, WT_PATHMAX, WT_CTL_ANG, WT_CTL_MAXD or the step derivation
change, change them here in the same commit or this tool starts lying in the
reassuring direction.
"""

import math
import os
import sys

WT_CTLMAX   = 1024      # cl_watch.qc: control points
WT_PATHMAX  = 2048      # cl_watch.qc: drawn curve points
WT_CTL_ANG  = 0.997     # cos(4.4 degrees)
WT_CTL_MAXD = 192.0
STEP_FLOOR  = 12.0
SUB_MAX     = 16

WT_C_T   = 0
WT_C_ORG = 1


def is_sample(line):
    """FS_IsSample (sh_defs.qc): a sample begins with a digit or a minus."""
    if not line:
        return False
    c = line[0]
    return c == '-' or c.isdigit()


def read_samples(path):
    """Every sample's (t, x, y, z), in file order, after `begin`."""
    out = []
    with open(path, 'r', errors='replace') as f:
        for line in f:
            line = line.strip()
            if not is_sample(line):
                continue
            tok = line.split()
            if len(tok) < 4:
                continue
            try:
                out.append((float(tok[WT_C_T]),
                            float(tok[WT_C_ORG + 0]),
                            float(tok[WT_C_ORG + 1]),
                            float(tok[WT_C_ORG + 2])))
            except ValueError:
                continue
    return out


def vlen(a):
    return math.sqrt(a[0] * a[0] + a[1] * a[1] + a[2] * a[2])


def sub3(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def controls(samples):
    """Watch_Scan's control-point selection, cl_watch.qc:605-655."""
    nsamp = len(samples)
    if nsamp == 0:
        return []

    cstride = math.ceil(nsamp / (WT_CTLMAX - 2))
    if cstride < 1:
        cstride = 1

    cpos = []
    lastdir = None
    nextp = 0

    for c, s in enumerate(samples):
        o = (s[1], s[2], s[3])

        want = False
        if c == 0:
            want = True
        elif c == nsamp - 1:
            want = True
        elif c >= nextp and cpos:
            step = sub3(o, cpos[-1])
            d = vlen(step)
            if d >= WT_CTL_MAXD:
                want = True
            elif d > 1 and lastdir is not None:
                n = (step[0] / d, step[1] / d, step[2] / d)
                turn = n[0] * lastdir[0] + n[1] * lastdir[1] + n[2] * lastdir[2]
                if turn < WT_CTL_ANG:
                    want = True

        if want and len(cpos) < WT_CTLMAX:
            if cpos and o != cpos[-1]:
                d3 = sub3(o, cpos[-1])
                dl = vlen(d3)
                if dl > 0:
                    lastdir = (d3[0] / dl, d3[1] / dl, d3[2] / dl)
            cpos.append(o)
            nextp = c + cstride

    return cpos


def curve(cpos, old):
    """
    Watch_BuildCurve's point budget.

    Returns (pn, saturated, drawn_fraction, step).  drawn_fraction is the share
    of the control polygon's LENGTH that got points before the table filled --
    which is the number the user sees as "it stops at the last 10%".
    """
    cn = len(cpos)
    if cn < 2:
        return cn, False, 1.0, 0.0

    seg = [vlen(sub3(cpos[i + 1], cpos[i])) for i in range(cn - 1)]
    total = sum(seg)

    spans = cn - 1
    budget = WT_PATHMAX - 2

    def cost(st):
        """Watch_CurveCost: what a step spends, ceil and both clamps included."""
        n = 0
        for length in seg:
            s = math.ceil(length / st) if st > 0 else 1
            n += max(1, min(SUB_MAX, s))
        return n + 1

    if old:
        step = total / budget                       # build 42: the bug
    elif spans >= budget:
        step = total
    else:
        step = total / (budget - spans)             # build 43: reserve the ceil

    if step < STEP_FLOOR:
        step = STEP_FLOOR

    if not old:
        # ...then spend the slack.  Bisected, not scaled: cost is a sum of ceils
        # and falls in cliffs, so one proportional guess lands past the edge.
        hi = step
        used = cost(hi)
        for _ in range(5):
            if used >= budget:
                break
            lo = max(STEP_FLOOR, hi * used / budget)
            if lo >= hi:
                break
            cst = cost(lo)
            if cst <= budget:
                hi, used = lo, cst          # fits; go finer again
                continue
            for _ in range(5):              # a cliff between lo and hi
                trial = (lo + hi) * 0.5
                if trial >= hi:
                    break
                if cost(trial) <= budget:
                    hi = trial
                else:
                    lo = trial
            break
        step = hi

    pn = 0
    covered = 0.0
    full = False

    for i in range(spans):
        if full:
            break                                   # build 43's outer break
        length = seg[i]
        sub = math.ceil(length / step) if step > 0 else 1
        sub = max(1, min(SUB_MAX, sub))
        for _ in range(sub):
            if pn >= WT_PATHMAX:
                full = True
                break
            pn += 1
        if not full:
            covered += length

    if pn < WT_PATHMAX:
        pn += 1
    else:
        full = True

    frac = 1.0 if not full else (covered / total if total > 0 else 1.0)
    return pn, full, frac, step


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('-')]
    old = '--old' in sys.argv
    root = args[0] if args else 'ftesurf/data/runs'

    if not os.path.isdir(root):
        print("pathcheck: no such directory: %s" % root)
        return 2

    files = []
    for dirpath, _, names in os.walk(root):
        for n in sorted(names):
            if n.endswith('.rec'):
                files.append(os.path.join(dirpath, n))
    files.sort()

    if not files:
        print("pathcheck: no .rec files under %s" % root)
        return 2

    bad = []
    print("%-52s %6s %5s %8s %7s %5s" %
          ("file", "nsamp", "ctl", "step", "curve", "drawn"))
    for path in files:
        samples = read_samples(path)
        cpos = controls(samples)
        pn, full, frac, step = curve(cpos, old)
        rel = os.path.relpath(path, root).replace('\\', '/')
        if len(rel) > 52:
            rel = '...' + rel[-49:]
        mark = '  <-- TRUNCATES' if full else ''
        print("%-52s %6d %5d %8.1f %7d %4.0f%%%s" %
              (rel, len(samples), len(cpos), step, pn, frac * 100, mark))
        if full:
            bad.append((rel, frac))

    print()
    print("%d file(s) of %d truncate%s" %
          (len(bad), len(files), "" if len(bad) == 1 else ""))
    if bad:
        worst = min(bad, key=lambda b: b[1])
        print("worst: %s draws %.1f%% of its path" % (worst[0], worst[1] * 100))
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
