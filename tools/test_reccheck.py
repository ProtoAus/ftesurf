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


def build(instart=True, inputs=True, ver=7, startjit=None, warps=()):
    """-> list of lines.  A finished, well-formed recording, v7 by default.

    BUILD 83: `ver` EXISTS SO THE TRAILER WIDTH IS DERIVED AND NEVER TYPED.  v6
    ends with five fields and v7 with six, and the fixtures below used to reach
    into that line by position -- `l.split()[5]` was the last field, and the
    moment a sixth was appended the same expression silently DROPPED it.  The
    test then failed on trailer WIDTH while claiming to be about the input
    count, which is a failure that reports the wrong cause: exactly the class of
    bug this suite exists to catch, one level up, in the suite itself.

    `startjit` is None (no key) or a 4-tuple; `warps` is a sequence of
    (pk, mt, kind) inserted into the body in order.
    """
    L = ["FTESURF-REC %d" % ver,
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
    if startjit is not None:
        L.append("startjit %g %g %g %g" % tuple(startjit))
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

    # Build 83.  Appended AFTER the loop so a fixture can state them without
    # having to model the interleave; `warp` is not per-packet and the grammar
    # imposes no position on it beyond being in the body.
    for wpk, wmt, wkind in warps:
        L.append("warp %d %d %s 0.00 0.00 64.00 0.00 0.00 0.00"
                 % (wpk, wmt, wkind))

    tail = [PACKETS, PAD + PACKETS, PAD, 0]
    if ver >= 6:
        tail.append(n_in)            # <inputs>, build 82
    if ver >= 7:
        tail.append(len(warps))      # <warps>, build 83
    L.append("end " + " ".join(str(x) for x in tail))
    return L


# The trailer's fields BY NAME, so a fixture never reaches into it by position.
# See build()'s docstring for what that cost the first time.
END_FIELD = {"ticks": 1, "samples": 2, "padding": 3, "cp": 4,
             "inputs": 5, "warps": 6}


def bump_end(lines, field, delta=1):
    """Add `delta` to one named field of the `end` record."""
    ix = [i for i, l in enumerate(lines) if l.startswith("end ")][0]
    f = lines[ix].split()
    n = END_FIELD[field]
    if n >= len(f):
        raise AssertionError(
            "the trailer in this fixture has no %r field (%d tokens): %r"
            % (field, len(f), lines[ix]))
    f[n] = str(int(f[n]) + delta)
    lines = list(lines)
    lines[ix] = " ".join(f)
    return lines


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


def ok_clean(lines, what):
    """Assert a fixture produces NO faults, and print them when it does.

    Build 83.  The pattern was already written inline twice; a version bump adds
    a third and a fourth, and a compatibility claim that is only ever asserted in
    prose is the thing this file exists to replace.
    """
    f, _ = run(lines)
    check(not f, what)
    if f:
        print("        %s" % f)


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
         for l in build(ver=6)]
    faults_with(b, "'end' takes 5 fields in a v6 file, has 4",
                "a v6 trailer with four fields is a fault")
    b = [l if not l.startswith("end ") else " ".join(l.split()[:6])
         for l in build()]
    faults_with(b, "'end' takes 6 fields in a v7 file, has 5",
                "a v7 trailer with five fields is a fault")


def case_trailer_count():
    faults_with(bump_end(build(), "inputs"),
                "input records, the file has",
                "a trailer that over-counts the input rows is a fault")


def case_v6_trailer_still_five_fields():
    # The sibling of case_v5_trailer_still_four_fields, and it exists for the
    # same reason: a version bump must not retroactively fault every file
    # written before it.  A v6 file has five trailer fields and no `warp`
    # records, and that is a complete and correct recording.
    ok_clean(build(ver=6), "a v6 file with a five-field trailer still passes")


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
    ok_clean(build(ver=5, instart=False, inputs=False),
             "a v5 file with a four-field trailer still passes")


def case_warp_shape():
    """Build 83.  `warp <pk> <mt> <kind> <ox oy oz> <vx vy vz>` -- nine fields."""
    b = build(warps=[(5, HORIZON + 5, "tele")])
    ok_clean(b, "a well-formed warp record passes")

    short = [l if not l.startswith("warp ") else " ".join(l.split()[:9])
             for l in b]
    faults_with(short, "'warp' takes 9 fields",
                "a short warp record is a fault")


def case_warp_count():
    """The trailer's sixth field is EXACT and a disagreement is unambiguous.

    It matters more than <inputs> does: a missing input row is one move of a
    thousand, but a missing warp is a discontinuity with nothing in the file to
    explain it -- which is what a verifier would otherwise read as tampering.
    """
    b = build(warps=[(5, HORIZON + 5, "tele"), (9, HORIZON + 9, "push")])
    ok_clean(b, "two warp records counted correctly in the trailer pass")
    faults_with(bump_end(b, "warps"), "warp records, the file has",
                "a trailer that over-counts the warp records is a fault")
    # And the direction that matters: the records are there, the count is not.
    dropped = [l for l in b if not l.startswith("warp ")]
    faults_with(dropped, "warp records, the file has",
                "a trailer counting warps a truncated body does not have "
                "is a fault")


def case_warp_below_horizon():
    """The horizon binds the warps as well as the `in` rows, and for the same
    reason: nothing in the body can predate the tick the recording opened on."""
    faults_with(build(warps=[(5, HORIZON - 3, "tele")]),
                "below the trace's horizon",
                "a warp stamped before the horizon is a fault")


def case_warp_unknown_kind_is_a_note():
    """A word this tool has not heard of is a NEWER SERVER, not a broken file.

    The writers are five today and the set is expected to grow -- the
    basevelocity family is named in sv_timer.qc's grammar as the next one.  A
    checker written from the grammar that faulted an unknown word would fault
    every file a newer build wrote, which is the failure this tool exists on the
    other side of.
    """
    b = build(warps=[(5, HORIZON + 5, "basevel")])
    f, n = run(b)
    check(not f, "an unknown warp kind is not a fault")
    check(any("not one this tool knows" in x for x in n),
          "an unknown warp kind is reported as a note")


def case_startjit_shape():
    """Build 83.  `startjit <units> <dx> <dy> <dz>`."""
    ok_clean(build(startjit=(2, 1.37, -0.82, 0)),
             "a well-formed startjit key passes")
    faults_with(head(build(startjit=(2, 1.37, -0.82, 0)), "startjit", "2 1 2"),
                "startjit takes 4 fields",
                "a three-field startjit is a fault")


def case_startjit_outside_its_own_rule():
    """The rule is written beside the outcome precisely so this is checkable
    without the tool knowing what run_startjitter was set to."""
    faults_with(build(startjit=(2, 3.5, 0, 0)),
                "outside the rule of 2 it states",
                "an offset larger than the rule it states is a fault")


def case_startjit_vertical_is_a_fault():
    """dz is structurally 0 -- the rule is horizontal, because a vertical nudge
    changes GROUND CONTACT and that is a much larger felt change than the
    anti-replay property needs.  A non-zero one means the writer grew a
    component this block does not know about."""
    faults_with(build(startjit=(2, 0.5, 0.5, 0.5)),
                "the rule is horizontal",
                "a vertical startjit component is a fault")


def case_startjit_blocked_is_a_note_not_a_fault():
    """ALL ZEROES IS A LEGAL AND EXPECTED FILE, and this is the check that says
    so.  Every candidate can be blocked -- a start box flush against a wall, a
    player in a corner -- and the server then applies nothing and says so.  A
    checker that faulted that would fault a correct recording of a correct
    refusal, which is the same shape as build 82's `carry printed at exactly one
    tick` fixture two cases up."""
    b = build(startjit=(2, 0, 0, 0))
    f, n = run(b)
    check(not f, "a startjit that applied nothing is not a fault")
    check(any("applied nothing" in x for x in n),
          "a startjit that applied nothing is reported as a note")


def main():
    for fn in (case_control,
               case_no_horizon, case_horizon_without_rows,
               case_trailer_width, case_trailer_count,
               case_row_width,
               case_movetick_backwards, case_packet_backwards,
               case_below_horizon, case_carry_bound, case_button_width,
               case_instart_ordering, case_resume_is_not_a_fault,
               case_offgrid_angle_is_a_note,
               case_v5_trailer_still_four_fields,
               case_v6_trailer_still_five_fields,
               case_warp_shape, case_warp_count, case_warp_below_horizon,
               case_warp_unknown_kind_is_a_note,
               case_startjit_shape, case_startjit_outside_its_own_rule,
               case_startjit_vertical_is_a_fault,
               case_startjit_blocked_is_a_note_not_a_fault):
        print("%s:" % fn.__name__)
        fn()
        print("")
    print("%d checks, %d failed" % (CHECKS, len(FAILED)))
    for f in FAILED:
        print("  FAILED: %s" % f)
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
