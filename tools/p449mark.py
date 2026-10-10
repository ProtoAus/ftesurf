"""p449mark.py -- grade Patch 449's run-line marks against the .rec itself.

Written from the recorder's grammar block (src/server/sv_timer.qc, the .rec
sample record and the resume/retry records) and NOT from cl_lines.qc, for the
reason tools/reccheck.py exists: a reader written from the writer agrees with
the writer's bugs.  It reimplements the three-state contact rule from the
documented flag bits and compares, mark for mark, with what the client printed.

ONE DEPENDENCE IS DELIBERATE AND PARTIAL.  The break set (a teleport: no segment
from the previous sample) is consumed from the client's own `break` marks rather
than re-derived, because it is Interp_Fit's verdict over a kinematic model and
re-implementing that here would test Patch 378, not this patch.  It is already
falsified independently: Patch 432's A2/A3 graded the same set against the snap
table on four fixtures.  Everything else below is derived from the file.

It reads the breaks from the MARK stream and not from the `lnk` list beside it:
past LN_CAP the point array halves and carries a dropped sample's break onto the
next kept point, so `lnk` is up to one sample late and grading against it
reported eight marks out of phase on a 127437-sample file that were not.

Marks are keyed by SAMPLE ORDINAL, never by time.  Both bhop fixtures repeat a
timestamp (a file records one sample per packet and a held clock repeats it), so
`t` does not identify a sample, and keying on it mis-assigned a break in each.

A RAMP LEAVE IS STAMPED AT THE RIDE'S LAST REAL CONTACT (Patch 608).  The
classifier still sees the edge when the 0.08 s hold runs out, so a bridged gap
marks nothing; but the mark's time, ordinal, position and velocity are those of
the last sample carrying the ramp bit.  A ride with no such sample of its own
since the last break or stitch (or opened by the hold as the body left ground)
takes its first such sample.  Each mark
also carries the clock of the sample its edge fell on, which is what the
containment check uses: a segment row still starts where the hold ran out.
THIS PART OF THE MODEL IS NOT INDEPENDENT: it was written beside the client
change, so agreement on a stamp shows the two say the same thing, not that
either is right.  tools/test_runlines_rampleave.py checks the stamp against the
file's own flag bits and positions instead.

  python tools/p449mark.py ftesurf/logs/p449mark.log [--verbose]

Reads FIXTURE/lnmb/lnk/lnm lines from the log, the .rec paths from the FIXTURE
lines (relative to ftesurf/), and prints one PASS/FAIL line per fixture.
"""
import os
import re
import struct
import sys

GROUND, AIR, RAMP = 0, 1, 2          # SEG_NONE, SEG_AIR, SEG_RAMP
E_LAND, E_LEAVE, E_JUMP, E_APEX, E_TROUGH, E_STITCH, E_BREAK = 1, 2, 3, 4, 5, 6, 7
KIND_NAME = {1: "land", 2: "leave", 3: "jump", 4: "apex", 5: "trough",
             6: "stitch", 7: "break"}

F_ONGROUND, F_JUMP, F_RAMP = 1, 4, 16
RAMP_GAP = 0.08                      # cl_board.qc:248, PMSRC_BOARD_AIRGATE
EVZMIN = 40                          # cl_lines.qc LN_EVZMIN
EVCAP = 4096                         # cl_lines.qc LN_EVCAP

C_T, C_ORG, C_VEL, C_FLAGS = 0, 1, 4, 9


def f32(x):
    """QC arithmetic is single precision, and one mark in 1304 turns on it.

    bhop_monster_jam at t=594.2242 leaves a ramp with a contact gap of EXACTLY
    RAMP_GAP: 0.08000000000004547 in double, which expires the hold, and
    0.07995605 in single, which does not.  The client held one sample longer
    and was right to -- it runs the same float32 subtraction the live board
    does.  Modelling this in double would report a defect that is the model's.
    """
    return struct.unpack("f", struct.pack("f", x))[0]


def is_sample(line):
    """The .rec's one structural rule: a sample starts with a digit or a minus."""
    return line[:1].isdigit() or line[:1] == "-"


def derive(path, breaks):
    """Every mark the file implies, in order.  breaks: a set of sample times."""
    out = []
    pkind = -1
    ron, rlast, gjmp, pvz, vzmax = False, 0.0, False, 0.0, 0.0
    ride = None                     # the open ride's last real contact, as a mark's fields
    stitch = False
    body = False
    n = 0
    with open(path, "r", errors="replace") as fh:
        for line in fh:
            line = line.rstrip("\n")
            if not body:
                if line.startswith("begin"):
                    body = True
                continue
            if not is_sample(line):
                k = line.split(" ", 1)[0]
                if k == "resume" or k == "retry":
                    stitch = True          # ...for the sample that follows it
                continue
            f = line.split()
            t = f32(float(f[C_T]))
            o = (float(f[C_ORG]), float(f[C_ORG + 1]), float(f[C_ORG + 2]))
            v = tuple(f32(float(f[C_VEL + i])) for i in range(3))
            fl = int(float(f[C_FLAGS]))
            n += 1

            # A hold cannot bridge a teleport (Patch 530).  This model lacked the
            # reset until Patch 608 and made a leave the client rightly does not.
            brk = (n - 1) in breaks
            if brk:
                ron, rlast = False, f32(t - 999)
            raw = fl & F_RAMP
            held = bool(raw) or (ron and rlast > 0 and t >= rlast
                                 and f32(t - rlast) <= f32(RAMP_GAP))
            if raw:
                rlast = t
            ron = held
            k = GROUND if (fl & F_ONGROUND) else (RAMP if held else AIR)

            here = (t, n - 1, (v[0] ** 2 + v[1] ** 2) ** 0.5,
                    v[0] ** 2 + v[1] ** 2 + v[2] ** 2, v[2])
            # (kind, sub, t, ordinal, speed, v.v, vz, the clock the edge fell on)
            rec = lambda kind, sub, at=here: out.append((kind, sub) + at + (t,))

            if brk:
                rec(E_BREAK, 0)
            if stitch:
                rec(E_STITCH, 0)
            if brk or stitch:
                ride = None             # a leave stamped behind either would be out of order
            if brk or pkind < 0:
                vzmax = 0.0
            elif k != pkind:
                if k in (GROUND, RAMP):
                    rec(E_LAND, pkind * 4 + k)
                elif pkind == RAMP:
                    rec(E_LEAVE, pkind * 4 + k, ride if ride is not None else here)
                else:
                    rec(E_JUMP if gjmp else E_LEAVE, pkind * 4 + k)
                vzmax = 0.0
            elif k == AIR:
                vzmax = max(vzmax, abs(v[2]))
                if vzmax >= EVZMIN:
                    if pvz > 0 and v[2] <= 0:
                        rec(E_APEX, 0)
                        vzmax = 0.0
                    elif pvz <= 0 and v[2] > 0:
                        rec(E_TROUGH, 0)
                        vzmax = 0.0
            if k != RAMP:
                ride = None
            elif raw or ride is None:
                ride = here
            pkind, pvz = k, v[2]
            gjmp = (gjmp or bool(fl & F_JUMP)) if k == GROUND else False
            stitch = False
    return out, n


def parse_log(path):
    """[(recpath, header, {break sample ordinals}, [marks]) ...], in run order."""
    runs, cur = [], None
    fixture = re.compile(r"=== p449mark FIXTURE (\S+) ===")
    for line in open(path, "r", errors="replace"):
        line = re.sub(r"^\d{4}-\d\d-\d\d \d\d:\d\d:\d\d ", "", line.rstrip("\n"))
        m = fixture.search(line)
        if m:
            cur = {"path": m.group(1), "brk": set(), "marks": [], "hdr": None,
                   "rows": [], "tickrate": 0}
            runs.append(cur)
            continue
        if cur is None:
            continue
        if line.startswith("lnsb "):
            cur["tickrate"] = float(line.split()[2])
        elif line.startswith("lns "):
            f = line.split()
            cur["rows"].append((int(float(f[2])), int(float(f[4]))))   # kind, tick
        elif line.startswith("lnmb "):
            f = line.split()
            cur["hdr"] = {"n": int(float(f[2])), "cut": int(float(f[3])),
                          "drop": int(float(f[4]))}
        elif line.startswith("lnm "):
            f = line.split()
            if int(float(f[2])) == E_BREAK:
                cur["brk"].add(int(float(f[5])))
            cur["marks"].append((int(float(f[2])), int(float(f[3])),
                                 float(f[4]), int(float(f[5])),
                                 float(f[9]), float(f[10]), float(f[11]),
                                 # a build before Patch 608 prints no edge clock
                                 float(f[12]) if len(f) > 12 else None))
    return runs


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    verbose = "--verbose" in sys.argv
    log = args[0] if args else "ftesurf/logs/p449mark.log"
    root = os.path.join(os.path.dirname(os.path.abspath(log)), "..")

    runs = parse_log(log)
    if not runs:
        print("FAIL no FIXTURE blocks in %s -- the arm measured nothing" % log)
        return 1
    bad = 0
    for r in runs:
        want, nsamp = derive(os.path.join(root, r["path"]), r["brk"])
        got = r["marks"]
        name = os.path.basename(r["path"])
        capped = r["hdr"] and (r["hdr"]["cut"] or r["hdr"]["drop"])
        if capped:
            # Past the cap the peaks were dropped as a class: compare what the
            # policy promises to keep, which is every structural mark.
            want = [w for w in want if w[0] not in (E_APEX, E_TROUGH)]
            got = [g for g in got if g[0] not in (E_APEX, E_TROUGH)]
        fails = []
        if len(want) != len(got):
            fails.append("count file %d client %d" % (len(want), len(got)))
        for i in range(min(len(want), len(got))):
            w, g = want[i], got[i]
            if w[0] != g[0] or w[1] != g[1]:
                fails.append("[%d] kind/sub file %s/%d client %s/%d at t=%.4f"
                             % (i, KIND_NAME.get(w[0]), w[1],
                                KIND_NAME.get(g[0]), g[1], w[2]))
            elif abs(w[2] - g[2]) > 1e-4:
                fails.append("[%d] t file %.4f client %.4f" % (i, w[2], g[2]))
            elif w[3] != g[3]:
                fails.append("[%d] sample file %d client %d at t=%.4f"
                             % (i, w[3], g[3], w[2]))
            elif abs(w[4] - g[4]) > 0.01 or abs(w[6] - g[6]) > 0.01:
                fails.append("[%d] speed/vz file %.2f/%.2f client %.2f/%.2f"
                             % (i, w[4], w[6], g[4], g[6]))
            elif g[7] is None or abs(w[7] - g[7]) > 1e-4:
                fails.append("[%d] edge clock file %.4f client %s at t=%.4f"
                             % (i, w[7], g[7], w[2]))
            if len(fails) > 4:
                break
        # CONTAINMENT.  Every segment row starts at a contact edge, or at the
        # break that cut a held ride short, so every row
        # boundary must have a mark whose EDGE fell on its tick (a ramp leave is
        # stamped earlier than its edge).  Not the reverse: a contact
        # under SEG_MINTIME is a mark with no row, and that count is printed
        # rather than asserted -- it is what "no debounce" means.
        loose = 0
        if r["rows"] and r["tickrate"] > 0 and not capped:
            ticks = set()
            for g in r["marks"]:
                if g[0] in (E_LAND, E_LEAVE, E_JUMP, E_BREAK):
                    ticks.add(int((g[2] if g[7] is None else g[7]) / r["tickrate"]))
            miss = [t for (_, t) in r["rows"] if t > 0 and t not in ticks]
            row_ticks = set(t for (_, t) in r["rows"] if t > 0)
            loose = sum(1 for g in r["marks"] if g[0] in (E_LAND, E_LEAVE, E_JUMP)
                        and int((g[2] if g[7] is None else g[7]) / r["tickrate"]) not in row_ticks)
            if miss:
                fails.append("containment: %d row boundary/ies with no mark, "
                             "first at tick %d" % (len(miss), miss[0]))

        census = {}
        for g in r["marks"]:
            census[g[0]] = census.get(g[0], 0) + 1
        line = "  ".join("%s %d" % (KIND_NAME[k], census[k])
                         for k in sorted(census))
        if fails:
            bad += 1
            print("FAIL %-28s %s" % (name, fails[0]))
            for f in fails[1:4]:
                print("     %s" % f)
        else:
            print("PASS %-28s %4d marks  (%s)%s%s"
                  % (name, len(r["marks"]), line,
                     "  CAP: peaks cut, %d dropped" % r["hdr"]["drop"]
                     if capped else "",
                     "  [%d rows contained, %d marks with no row]"
                     % (len(r["rows"]), loose) if r["rows"] else ""))
        if verbose:
            print("     %d samples parsed, %d breaks from the client"
                  % (nsamp, len(r["brk"])))
    print("%d fixture(s), %d failed" % (len(runs), bad))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
