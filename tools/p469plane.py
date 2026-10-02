"""p469plane.py -- grade Patch 469: a board line is graded against its own plane.

The same file sits in slot 0 (the replay) and slot 1 (`scores lineat`, the board
job).  Both dump ln_q at stride 1; this grades each against the .rec with
p453q's model and against each other.  The model is run twice -- with the file's
planes and with them zeroed -- so the arm can count the points at which the
plane decides the grade, which is the only place the fix can show.

  python tools/p469plane.py [ftesurf/logs/p469plane.log]

Exit 0 pass, 1 fail, 2 cannot grade (an incomplete dump is not a wrong one).
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import p453q                                        # noqa: E402  (the model)

MARK = "=== p469plane slot 0 ==="


def last_run(log):
    """The lines of the LAST run in the log, and how many runs it holds.

    Logs append, so an earlier run's dump is still in the file."""
    lines = [re.sub(r"^\d{4}-\d\d-\d\d \d\d:\d\d:\d\d ", "", r.rstrip("\n"))
             for r in open(log, "r", errors="replace")]
    starts = [i for i, s in enumerate(lines) if MARK in s]
    if not starts:
        return [], 0, lines
    return lines[starts[-1]:], len(starts), lines[:starts[-1]]


def parse(lines):
    mv, slots, cur = {}, {}, None
    for line in lines:
        f = line.split()
        if line.startswith("lnmv ") and len(f) >= 7:
            mv.update(tick=float(f[1]), airaccel=float(f[2]), accel=float(f[3]),
                      maxspeed=float(f[4]), aircap=float(f[5]), gravity=float(f[6]))
        elif line.startswith("lnmv2 ") and len(f) >= 5:
            mv.update(gfric=float(f[1]), stopspeed=float(f[2]), duck=float(f[3]),
                      ghold=float(f[4]))
        elif line.startswith("lncb ") and len(f) >= 5:
            cur = {"n": int(float(f[3])), "stride": int(float(f[4])), "pts": [],
                   "closed": False}
            slots[int(float(f[1]))] = cur
        elif line.startswith("lnc ") and len(f) >= 7 and cur is not None:
            cur["pts"].append((int(float(f[1])), float(f[2]), float(f[6]),
                               (float(f[3]), float(f[4]), float(f[5]))))
        elif line.startswith("lnce") and cur is not None:
            cur["closed"] = True
            cur = None
    return mv, slots


def differs(a, b, tol):
    if a < 0 or b < 0:
        return (a < 0) != (b < 0)
    return abs(a - b) > tol


def main():
    log = sys.argv[1] if len(sys.argv) > 1 else "ftesurf/logs/p469plane.log"
    run, nruns, before = last_run(log)
    mv, slots = parse(run)
    recs = [m.group(1) for m in (re.search(r"scores: line 1 queued: (\S+)", s)
                                 for s in before + run) if m]
    for k in (0, 1):
        s = slots.get(k)
        if not s or not s["closed"] or s["stride"] != 1 or len(s["pts"]) != s["n"]:
            print("CANNOT GRADE: slot %d's dump is missing or incomplete (%s)"
                  % (k, "absent" if not s else "%d of %d points, closed %s"
                     % (len(s["pts"]), s["n"], s["closed"])))
            return 2
    if len(mv) < 10 or not recs:
        print("CANNOT GRADE: %d settings, rec %s" % (len(mv), recs[-1:] or None))
        return 2
    recpath = "ftesurf/" + recs[-1]
    rows = p453q.samples(recpath)
    want = p453q.grades(rows, mv)
    flat = p453q.grades([dict(r, n=(0.0, 0.0, 0.0)) for r in rows], mv)

    s0, s1 = slots[0]["pts"], slots[1]["pts"]
    if len(s0) != len(rows):
        print("CANNOT GRADE: slot 0 holds %d points, the file %d samples"
              % (len(s0), len(rows)))
        return 2
    # The board job keeps the samples from the clock's start on (t >= 0).
    off = next((i for i, r in enumerate(rows) if r["t"] >= 0), len(rows))

    fails = 0

    def verdict(ok, text):
        nonlocal fails
        fails += 0 if ok else 1
        print("%s %s" % ("PASS" if ok else "FAIL", text))

    late = [j for j, (_, t, _, _) in enumerate(s1)
            if off + j >= len(rows) or abs(t - rows[off + j]["t"]) > 0.00051]
    verdict(len(s1) == len(rows) - off and not late,
            "P1  slot 1 holds %d points, the file's %d samples from t >= 0 "
            "(%d before it); %d out of place"
            % (len(s1), len(rows) - off, off, len(late)))
    if late:
        print("CANNOT GRADE further: slot 1's points are not the file's samples")
        return 1

    # Point 0 of a slot has nothing to have turned from: no answer, by rule.
    w1 = [-1.0] + [want[off + j] for j in range(1, len(s1))]
    f1 = [-1.0] + [flat[off + j] for j in range(1, len(s1))]
    bad2 = [j for j, (_, _, q, _) in enumerate(s1) if differs(q, w1[j], 0.01)]
    verdict(not bad2, "P2  slot 1 against the file: %d points, %d wrong%s"
            % (len(s1), len(bad2),
               "" if not bad2 else "  (first: point %d t %.4f client %.4f file %.4f)"
               % (bad2[0], s1[bad2[0]][1], s1[bad2[0]][2], w1[bad2[0]])))
    # The grade AND the colour the emitter was handed (ln_col), mode 4.
    bad3 = [j for j in range(1, len(s1))
            if differs(s1[j][2], s0[off + j][2], 0.0001)
            or max(abs(a - b) for a, b in zip(s1[j][3], s0[off + j][3])) > 0.0011]
    verdict(not bad3, "P3  slot 1 against slot 0, grade and colour: %d points, "
            "%d differ%s" % (len(s1) - 1, len(bad3),
               "" if not bad3 else "  (first: point %d slot1 %.4f slot0 %.4f)"
               % (bad3[0], s1[bad3[0]][2], s0[off + bad3[0]][2])))
    moved = [j for j in range(len(s1)) if differs(w1[j], f1[j], 0.01)]
    verdict(len(moved) >= 20,
            "P4  the plane moves the grade at %d of %d points (a zero plane "
            "would be wrong there)" % (len(moved), len(s1)))
    # What the unfixed build prints, said so a control run can be read off.
    asflat = sum(1 for j in moved if not differs(s1[j][2], f1[j], 0.01))
    print("     of those %d, slot 1 matches the ZERO-PLANE model at %d"
          % (len(moved), asflat))
    bad0 = [i for i, (_, _, q, _) in enumerate(s0) if differs(q, want[i], 0.01)]
    print("     slot 0 against the file: %d points, %d wrong" % (len(s0), len(bad0)))
    print("     %d run(s) in the log, the last graded; %s"
          % (nruns, recpath))
    print("4 check(s), %d failed" % fails)
    return 0 if fails == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
