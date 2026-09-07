"""
fixstagepad.py -- one-shot repair for build 24's stage slices.

THE BUG.  SV_StageWrite rebased a stage's sample timestamps against
`run_st_tick * run_t_tick`, a time RECONSTRUCTED from the split's tick count.  The
first sample of the slice does not sit exactly there -- the split is processed
inside a tick whose sample may have been written just before or just after it --
so the first rebased timestamp landed within half a tick either side of zero and
the sign was a coin flip.  Five of the first twelve real stage files came out
positive and seven came out negative.

WHY HALF A MILLISECOND MATTERS.  A negative timestamp is the .rec grammar's one
structural marker for the pre-start padding ring, so a reader opens the span at
-0.0005 and counts one approach sample -- while the trailer, which hardcoded a
literal 0, says there are none.  reccheck.py faults on that disagreement, and it
is right to: a trailer that does not describe its own body is the one thing a
self-checking format must not tolerate.

Build 25 takes the base from the first sample's own timestamp instead, so the
first rebased value is exactly 0.0000 and the trailer's count is derived from
the lines actually written.  This does the same to the files already on disk:
subtract the first sample's t from every sample's t, leaving a file identical to
what the fixed writer would have produced.

IT IS DELIBERATELY NARROW.  It touches only a file that is REC 4, whose trailer
claims zero padding, and whose first sample is negative by less than one tick --
i.e. exactly the fingerprint of this bug.  Anything else is refused and left
alone, because a file this tool does not understand is worth more unmodified
than modified, and a run with a real padding ring is a main run rather than a
stage slice.  Build 23's migrate_runs.py made the same refusal for the same
reason.

    python tools/fixstagepad.py                 report only
    python tools/fixstagepad.py --write         rewrite, with .bak beside each
"""
import argparse
import glob
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
RUNS = os.path.join(os.path.dirname(HERE), "ftesurf", "data", "runs")


def is_sample(tok):
    return tok[0].isdigit() or (tok[0] == "-" and len(tok) > 1 and tok[1].isdigit())


def examine(path):
    """Return (verdict, detail, lines, tbase, tick) without changing anything."""
    with open(path, "r", errors="replace") as f:
        lines = f.read().split("\n")

    if not lines or lines[0].strip() != "FTESURF-REC 4":
        return "skip", "not a REC 4 file", None, 0, 0

    tick = 0.015
    body = None
    for i, ln in enumerate(lines):
        tok = ln.split()
        if not tok:
            continue
        if tok[0] == "tickrate" and len(tok) > 1:
            tick = float(tok[1]) or 0.015
        if tok[0] == "begin":
            body = i + 1
            break
    if body is None:
        return "skip", "no begin record", None, 0, 0

    first_t = None
    for ln in lines[body:]:
        tok = ln.split()
        if tok and is_sample(tok[0]):
            first_t = float(tok[0])
            break
    if first_t is None:
        return "skip", "no samples", None, 0, 0

    end = None
    for ln in lines:
        tok = ln.split()
        if tok and tok[0] == "end":
            end = tok
    if end is None or len(end) < 4:
        return "skip", "no usable end record", None, 0, 0

    claimed_pad = float(end[3])

    if first_t >= 0:
        return "ok", "first sample %+.4f, already non-negative" % first_t, None, 0, 0
    if claimed_pad != 0:
        return "refuse", ("first sample %+.4f but the trailer claims %g padding "
                          "-- this is not the stage-slice bug"
                          % (first_t, claimed_pad)), None, 0, 0
    if -first_t >= tick:
        return "refuse", ("first sample %+.4f is a whole tick or more before "
                          "zero -- too large to be the rounding this fixes"
                          % first_t), None, 0, 0

    return "fix", "first sample %+.4f -> 0.0000" % first_t, lines, first_t, tick


def rewrite(lines, tbase):
    """Subtract tbase from every sample's first field, leaving the rest byte for
    byte -- the same 'copy from the first space onward' rule SV_StageLine uses,
    so seventeen columns cannot pick up rounding drift on the way through."""
    out = []
    inbody = False
    for ln in lines:
        if not inbody:
            out.append(ln)
            if ln.strip() == "begin":
                inbody = True
            continue
        tok = ln.split()
        if tok and is_sample(tok[0]):
            sp = ln.index(" ")
            out.append("%.4f%s" % (float(ln[:sp]) - tbase, ln[sp:]))
        else:
            out.append(ln)
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("files", nargs="*")
    ap.add_argument("--write", action="store_true",
                    help="actually rewrite (a .bak is left beside each file)")
    a = ap.parse_args()

    files = a.files or sorted(glob.glob(os.path.join(RUNS, "*", "*", "*.rec")))
    if not files:
        raise SystemExit("nothing to look at in %s" % RUNS)

    fixed = refused = 0
    for p in files:
        verdict, detail, lines, tbase, _ = examine(p)
        rel = os.path.relpath(p, RUNS)
        if verdict == "skip":
            continue
        if verdict == "ok":
            continue
        if verdict == "refuse":
            print("REFUSE %s\n       %s" % (rel, detail))
            refused += 1
            continue

        print("fix    %s\n       %s" % (rel, detail))
        fixed += 1
        if a.write:
            with open(p + ".bak", "w") as b:
                b.write("\n".join(lines))
            with open(p, "w") as f:
                f.write("\n".join(rewrite(lines, tbase)))

    print("\n%d file(s) %s, %d refused"
          % (fixed, "rewritten" if a.write else "would be rewritten", refused))
    if fixed and not a.write:
        print("re-run with --write to apply")
    return 0


if __name__ == "__main__":
    sys.exit(main())
