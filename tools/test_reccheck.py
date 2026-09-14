#!/usr/bin/env python3
"""
test_reccheck.py -- the falsifier for reccheck.py's build-82 input trace (v6).

    python3 test_reccheck.py

WHY THIS EXISTS.  reccheck.py passing every file in data/runs proves nothing on
its own: a checker that always says "ok" also passes every clean file.  What has
to be shown is that each new check FAILS on the thing it claims to catch, and
that it stays QUIET on the legitimate shapes that look similar -- of which v6 has
two that a careless check would fault, and both are here.

BUILT FROM THE GRAMMAR, NOT FROM THE WRITER, which is the rule reccheck.py itself
is written under and the reason it has caught anything.  The recording below is
assembled from the block comment over SV_RecOpen in src/server/sv_timer.qc and
from nothing else; it never reads a real .rec, so this file runs on a fresh clone
with an empty data/ and keeps working when the recorder is rewritten.  If the two
ever disagree, that disagreement is the finding.

NOTHING HERE IS WRITTEN UNDER data/.  Everything lands in a temporary directory
and is removed, so no synthetic file can be mistaken for a run somebody made.
"""
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
RECCHECK = os.path.join(HERE, "reccheck.py")

CHECKS = 0
FAILED = []


def check(cond, what):
    global CHECKS
    CHECKS += 1
    if not cond:
        FAILED.append(what)
        print("  FAIL  %s" % what)
    else:
        print("  ok    %s" % what)


# ---------------------------------------------------------------------------
# A v6 recording, assembled from the grammar.
#
# THE NUMBERS ARE CHOSEN TO BE UNREMARKABLE, deliberately: the point of the
# control is that a mutation is the only thing that can fault it, so the base
# must not be sitting on any boundary.  One tick is 0.01 s; the mover advances
# one or two ticks per command, which is what a ~62 Hz client against a 100 Hz
# mover actually produces; the carry oscillates inside [0, 0.01) as it must.
# ---------------------------------------------------------------------------
TICK = 0.01
HORIZON = 606           # run_movetick when the recording opened
PAD = 4                 # pre-start padding samples, t < 0
PACKETS = 40


def build(instart=True, inputs=True):
    """-> list of lines.  A finished, well-formed v6 recording."""
    L = ["FTESURF-REC 6",
         "map bhop_eazy",
         "track 0",
         "startseg 0",
         "leg 0",
         "tickrate %g" % TICK,
         "movetickrate %g" % TICK,
         "clock counted",
         "owner Nobody",
         "runid 20260914-000000-0",
         "mapcrc 676de275",
         "zonesrc online",
         "zonecrc c50cfd70",
         "zonerule 1 1 0"]
    if instart:
        L.append("instart %d %d" % (HORIZON, HORIZON))
    L += ["flags 0", "begin"]

    def sample(t):
        # t ox oy oz  vx vy vz  pit yaw  fl keys  fwd side up  nx ny nz
        #
        # fl 0 -- AIRBORNE, and that is not laziness.  fl bit 1 (onground) with
        # an all-zero normal draws reccheck's "grounded with no plane recorded"
        # note, and a control that emits notes makes the note arms below
        # ambiguous.  keys 0 with an all-zero movement triple is the only pair
        # that satisfies the mask/movement agreement check for a still player.
        return ("%.4f 0.00 0.00 64.00 0.00 0.00 0.00 0.0 90.0 "
                "0 0 0 0 0 0.0000 0.0000 0.0000" % t)

    for i in range(PAD):
        L.append(sample(-(PAD - i) * TICK))

    mt, carry, n_in = HORIZON, 0.003, 0
    for pk in range(PACKETS):
        if inputs:
            L.append("in %d %d %.5f 0 0 0 0.0000 90.0000 0.0000 0" %
                     (pk, mt, carry))
            n_in += 1
            carry += 0.016 - TICK * (2 if carry + 0.016 >= 2 * TICK else 1)
            mt += 2 if carry < 0.003 else 1
            carry = round(carry % TICK, 5)
        L.append(sample(pk * TICK))

    L.append("end %d %d %d %d %d" % (PACKETS, PAD + PACKETS, PAD, 0, n_in))
    return L


def run(lines, name="t.rec"):
    """-> (faults, notes) as reccheck.py reports them."""
    d = tempfile.mkdtemp(prefix="reccheck_t")
    try:
        p = os.path.join(d, name)
        with open(p, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
        out = subprocess.run([sys.executable, RECCHECK, "-v", p],
                             capture_output=True, text=True).stdout
        faults = [l.strip()[2:] for l in out.splitlines()
                  if l.strip().startswith("! ")]
        notes = [l.strip()[2:] for l in out.splitlines()
                 if l.strip().startswith("- ")]
        return faults, notes
    finally:
        shutil.rmtree(d, ignore_errors=True)


def row(lines, which=10, **kw):
    """Mutate the `which`-th `in` row in place.  Field names per the grammar."""
    ix = [i for i, l in enumerate(lines) if l.startswith("in ")][which]
    f = lines[ix].split()
    for k, v in kw.items():
        f[{"pk": 1, "mt": 2, "carry": 3, "fwd": 4, "pit": 7,
           "yaw": 8, "bt": 10}[k]] = str(v)
    lines[ix] = " ".join(f)
    return lines


def head(lines, key, value):
    """Replace a header key, or remove it when value is None."""
    ix = [i for i, l in enumerate(lines) if l.split()[0] == key][0]
    if value is None:
        lines.pop(ix)
    else:
        lines[ix] = "%s %s" % (key, value)
    return lines


def faults_with(lines, want, what):
    f, _ = run(lines)
    check(any(want in x for x in f), what)
    if not any(want in x for x in f):
        print("        got: %s" % (f or "NO FAULT"))


def notes_with(lines, want, what):
    f, n = run(lines)
    check(not f and any(want in x for x in n), what)
    if f or not any(want in x for x in n):
        print("        faults=%s notes=%s" % (f, n))


# ---------------------------------------------------------------------------


def case_control():
    """THE ARM EVERY OTHER ARM RESTS ON.  Without it, "the checker faulted"
    says nothing about whether the mutation is what it faulted on."""
    f, n = run(build())
    check(not f, "a well-formed v6 recording passes with 0 faults")
    if f:
        print("        %s" % f)
    check(not n, "and emits no notes, so the note arms below are unambiguous")
    if n:
        print("        %s" % n)


def case_no_horizon():
    """Rows without a key.  A FAULT: the rows are meaningless without a
    horizon, because a reader cannot tell whether the trace starts at the run's
    start or somewhere after it."""
    faults_with(head(build(), "instart", None),
                "no 'instart' key",
                "'in' rows with no instart key are a fault")


def case_horizon_without_rows():
    """The other direction, and it is NOT a fault.  A key with no rows is what a
    recording that opened and closed inside one packet would look like; faulting
    it would assert something about the engine's packet scheduling that this
    tool has no business asserting."""
    f, n = run(build(inputs=False))
    check(not f, "instart with no rows is not a fault")
    check(any("no 'in' records" in x for x in n),
          "instart with no rows is a note")
    if f:
        print("        %s" % f)


def case_trailer_width():
    b = [l if not l.startswith("end ") else " ".join(l.split()[:5])
         for l in build()]
    faults_with(b, "'end' takes 5 fields in a v6 file, has 4",
                "a v6 trailer with four fields is a fault")


def case_trailer_count():
    b = build()
    b = [l if not l.startswith("end ")
         else " ".join(l.split()[:5] + [str(int(l.split()[5]) + 1)]) for l in b]
    faults_with(b, "input records, the file has",
                "a trailer that over-counts the input rows is a fault")


def case_row_width():
    b = build()
    ix = [i for i, l in enumerate(b) if l.startswith("in ")][10]
    b[ix] = " ".join(b[ix].split()[:10])
    faults_with(b, "'in' takes 10 fields", "a short 'in' row is a fault")


def case_movetick_backwards():
    faults_with(row(build(), mt=1), "movetick goes backwards",
                "a movetick that goes backwards is a fault")


def case_packet_backwards():
    faults_with(row(build(), pk=0), "packet ordinal goes backwards",
                "a packet ordinal that goes backwards is a fault")


def case_below_horizon():
    faults_with(row(build(), which=0, mt=HORIZON - 5),
                "below the trace's own horizon",
                "a row before the stated horizon is a fault")


def case_carry_bound():
    """THE BOUNDARY, PINNED FROM BOTH SIDES, because the sensitivity of this
    check is set by the file's %.5f rendering and not by the mover.  A legal
    remainder of 0.0099996 prints as 0.01000, so the bound itself is undecidable
    from the file and must not fault; one printed step higher cannot be a
    rounding of anything legal and must."""
    f, _ = run(row(build(), carry="0.01000"))
    check(not f, "a carry printed at exactly one tick does NOT fault "
                 "(it is a legal rounding)")
    if f:
        print("        %s" % f)
    faults_with(row(build(), carry="0.01001"), "is at or above one tick",
                "a carry one printed step above a tick is a fault")


def case_button_width():
    """<bt> carries exactly the three bits pm_source.c reads.  A fourth would
    mean the writer and this reader disagree about what the column IS, which is
    worse than a wrong value."""
    faults_with(row(build(), bt=8), "is outside 0..7",
                "a fourth button bit is a fault")


def case_instart_ordering():
    """A run cannot start after its own recording.  The two numbers are equal on
    a fresh start and the run tick only ever moves DOWN, on a resume."""
    faults_with(head(build(), "instart", "%d %d" % (HORIZON, HORIZON + 3)),
                "a run cannot start after its own recording",
                "a start tick above the horizon is a fault")
    faults_with(head(build(), "instart", str(HORIZON)),
                "instart takes 2 fields",
                "a one-field instart is a fault")


def case_resume_is_not_a_fault():
    """THE SECOND LEGITIMATE SHAPE, and no config in this tree can produce it: a
    save-state resume rebases run_t_starttick while the mover's counter keeps
    running, so the run's start tick sits BELOW the horizon.  A checker that
    treated "start != horizon" as the fault would refuse every resumed run."""
    notes_with(head(build(), "instart", "%d %d" % (HORIZON, HORIZON - 40)),
               "was resumed from a save state",
               "a start tick below the horizon is a note, not a fault")


def case_offgrid_angle_is_a_note():
    """Usercmd angles are 16-bit, so every one the protocol can deliver is a
    multiple of 360/65536.  An angle off that grid was written by something
    else -- ordinarily setpos, which writes .v_angle straight from atof and is
    exactly what a test harness does.  A NOTE with a count, because a checker
    that faulted every scripted run is one nobody could test this feature with."""
    notes_with(row(build(), yaw="12.3456789"),
               "not a multiple of the 16-bit wire quantum",
               "an off-grid angle is a note with a count")


def case_v5_trailer_still_four_fields():
    """THE COMPATIBILITY CLAIM, TESTED RATHER THAN ASSERTED.  v6's whole
    justification for being a version bump at all is that `end` grew a field --
    so a v5 file must still be read with four, and SV_StageWrite and
    cl_lobbytime.qc both still write v5 after build 82."""
    b = [l.replace("FTESURF-REC 6", "FTESURF-REC 5") for l in build(
        instart=False, inputs=False)]
    b = [l if not l.startswith("end ") else " ".join(l.split()[:5]) for l in b]
    f, _ = run(b)
    check(not f, "a v5 file with a four-field trailer still passes")
    if f:
        print("        %s" % f)


def main():
    for fn in (case_control,
               case_no_horizon, case_horizon_without_rows,
               case_trailer_width, case_trailer_count,
               case_row_width,
               case_movetick_backwards, case_packet_backwards,
               case_below_horizon, case_carry_bound, case_button_width,
               case_instart_ordering, case_resume_is_not_a_fault,
               case_offgrid_angle_is_a_note,
               case_v5_trailer_still_four_fields):
        print("%s:" % fn.__name__)
        fn()
        print("")
    print("%d checks, %d failed" % (CHECKS, len(FAILED)))
    for f in FAILED:
        print("  FAILED: %s" % f)
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
