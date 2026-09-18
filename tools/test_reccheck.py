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
# v9: a pin with an exponent-form value, as %.9g prints one.
PIN = "pmsrcver=1 gravity=800 maxspeed=320 ticrate=0.00999999978 bounce=1e-05"


def build(instart=True, inputs=True, ver=9, startjit=None, warps=(),
          rides=(), inend=True, pmpin=True, seed=True, pms=(), pes=(),
          portals=(), sessions=()):
    """-> list of lines.  A finished, well-formed recording, v9 by default.

    BUILD 87 (v9): `pmpin`/`seed` default on (off below v9); a `warp` may carry a
    fourth item, its <row>, defaulting to its pk (one `in` row per packet here);
    `pms` is (pk, row), `pes` (pk, row, crc), `portals` (pk, row, n), all
    appended after the packet loop, so every row they name is already written.

    BUILD 83: `ver` EXISTS SO THE TRAILER WIDTH IS DERIVED AND NEVER TYPED.  v6
    ends with five fields and v7 with six, and the fixtures below used to reach
    into that line by position -- `l.split()[5]` was the last field, and the
    moment a sixth was appended the same expression silently DROPPED it.  The
    test then failed on trailer WIDTH while claiming to be about the input
    count, which is a failure that reports the wrong cause: exactly the class of
    bug this suite exists to catch, one level up, in the suite itself.

    `startjit` is None (no key) or a 4-tuple; `warps` is a sequence of
    (pk, mt, kind) inserted into the body in order.

    BUILD 85: `rides` is a sequence of (pk, mt, what, bx, by, bz); `inend`
    defaults ON because v8 writes it whenever the trace exists, so a fixture
    without one would fault for a reason it is not about.

    PATCH 364 (v10): `sessions` is a sequence of (after_pk, new_mt, why): after
    that packet the builder writes `pause`, `session` and (with the pin) a
    `seed`, and the rows go on from new_mt.  A drop/rotate/server reason sets
    TF_MULTISESSION; the trailer gains <sessions>.
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
    ms = any(w in ("drop", "rotate", "server") for _p, _m, w in sessions)
    L.append("flags %d" % (16384 if ms else 0))
    v9 = ver >= 9
    if v9 and pmpin:
        L.append("pmpin " + PIN)
    L.append("begin")
    if v9 and seed:
        L.append("seed 0 0 64 0 0 0 0 ducked=0 ducktime=0 msec_carry=0.003")

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

    mt, carry, n_in, n_sess = HORIZON, 0.003, 0, 0
    for pk in range(PACKETS):
        if inputs:
            if v9:
                L.append("in %d %d %.9g 0 0 0 0.0000 90.0000 0.0000 0 0" %
                         (pk, mt, carry))
            else:
                L.append("in %d %d %.5f 0 0 0 0.0000 90.0000 0.0000 0" %
                         (pk, mt, carry))
            n_in += 1
            carry += 0.016 - TICK * (2 if carry + 0.016 >= 2 * TICK else 1)
            mt += 2 if carry < 0.003 else 1
            carry = round(carry % TICK, 5)
        L.append(sample(pk * TICK))
        for spk, smt, why in sessions:
            if spk == pk:
                L.append("pause %d %.9g %d %s" % (mt, carry, pk + 1, why))
                L.append("session %d %d %.9g %d" % (n_sess + 2, smt, carry, pk + 1))
                if v9 and seed:
                    L.append("seed 0 0 64 0 0 0 0 ducked=0 ducktime=0 msec_carry=0.003")
                mt = smt
                n_sess += 1

    # Build 83.  Appended AFTER the loop so a fixture can state them without
    # having to model the interleave; `warp` is not per-packet and the grammar
    # imposes no position on it beyond being in the body.
    for w in warps:
        if v9:
            wrow = w[3] if len(w) > 3 else w[0]
            L.append("warp %d %d %d %s 0 0 64 0 0 0 0"
                     % (w[0], w[1], wrow, w[2]))
        else:
            L.append("warp %d %d %s 0.00 0.00 64.00 0.00 0.00 0.00"
                     % tuple(w[:3]))

    # Build 85, appended after the warps for the same reason: the grammar imposes
    # no position on a `ride` beyond being in the body, and modelling the real
    # interleave would tie every fixture to the packet loop's arithmetic.
    for rd in rides:
        L.append(("ride %d %d %s %.9g %.9g %.9g" if v9 else
                  "ride %d %d %s %.2f %.2f %.2f") % tuple(rd))

    for ppk, prow in pms:
        L.append("pm %d %d %s" % (ppk, prow, PIN))
    for ppk, prow, crc in pes:
        L.append("pe %d %d %d" % (ppk, prow, crc))
    for ppk, prow, n in portals:
        L.append("portal %d %d %d 0 0 64 0 0 0" % (ppk, prow, n))

    # Build 85.  Before the trailer, where SV_RecClose writes it, and gated on
    # the trace as `instart` is -- one without the other means TRUNCATED.
    if ver >= 8 and inend and inputs:
        L.append(("inend %d %.9g" if v9 else "inend %d %.5f") % (mt, carry))

    tail = [PACKETS, PAD + PACKETS, PAD, 0]
    if ver >= 6:
        tail.append(n_in)            # <inputs>, build 82
    if ver >= 7:
        tail.append(len(warps))      # <warps>, build 83
    if ver >= 8:
        tail.append(len(rides))      # <rides>, build 85
    if v9:
        tail += [len(pms), len(pes), len(portals)]   # build 87
    if ver >= 10:
        tail.append(n_sess)                          # Patch 364
    L.append("end " + " ".join(str(x) for x in tail))
    return L


# The trailer's fields BY NAME, so a fixture never reaches into it by position.
# See build()'s docstring for what that cost the first time.
END_FIELD = {"ticks": 1, "samples": 2, "padding": 3, "cp": 4,
             "inputs": 5, "warps": 6, "rides": 7,
             "pms": 8, "pes": 9, "portals": 10, "sessions": 11}


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
           "yaw": 8, "bt": 10, "fl": 11}[k]] = str(v)
    lines[ix] = " ".join(f)
    return lines


def edit(lines, kind, pos, value, which=0):
    """Set token `pos` (keyword = 0) of the `which`-th `kind` line; kind
    "sample" picks sample lines."""
    ix = [i for i, l in enumerate(lines)
          if (l[:1].isdigit() or l[:1] == "-" if kind == "sample"
              else l.split()[0] == kind)][which]
    f = lines[ix].split()
    f[pos] = str(value)
    lines = list(lines)
    lines[ix] = " ".join(f)
    return lines


def after_row(lines, which, text):
    """Insert `text` directly after the `which`-th `in` row."""
    ix = [i for i, l in enumerate(lines) if l.startswith("in ")][which]
    return lines[:ix + 1] + [text] + lines[ix + 1:]


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
    check(not f, "a well-formed v9 recording passes with 0 faults")
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
    """Each rung DEMANDS its own width; one short is a fault.

    BUILD 85: every rung names its version explicitly now.  The v7 arm used to
    build the default and assert "in a v7 file", true only while the default was
    7 -- so the v8 bump made it fail about v8 while claiming to be about v7.
    """
    for ver, want in ((6, 5), (7, 6), (8, 7), (9, 10)):
        b = [l if not l.startswith("end ") else " ".join(l.split()[:want])
             for l in build(ver=ver)]
        faults_with(b, "'end' takes %d fields in a v%d file, has %d"
                    % (want, ver, want - 1),
                    "a v%d trailer with %d fields is a fault" % (ver, want - 1))


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
    """v9 appends <fl>, so the v8 width is a short v9 row."""
    for ver, want in ((8, 10), (9, 11)):
        b = build(ver=ver)
        ix = [i for i, l in enumerate(b) if l.startswith("in ")][10]
        b[ix] = " ".join(b[ix].split()[:want])
        faults_with(b, "'in' takes %d fields" % want,
                    "a v%d 'in' row with %d fields is a fault" % (ver, want - 1))


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
    notes_with(row(build(ver=8), yaw="12.3456789"),
               "not a multiple of the 16-bit wire quantum",
               "an off-grid angle is a note with a count (v8)")


def case_v9_offgrid_angle_is_a_fault():
    """v9 angles are input_angles, which only SHORT2ANGLE ever sets, so setpos
    no longer excuses one.  The worst legal %.4f print is 0.0091 quanta."""
    faults_with(row(build(), yaw="12.3456789"), "off the 16-bit wire quantum",
                "a v9 off-grid angle is a fault")
    ok_clean(row(build(), yaw="-21.0938"),
             "a v9 on-grid angle at the %.4f print limit (0.0091) passes")


def case_v5_trailer_still_four_fields():
    """THE COMPATIBILITY CLAIM, TESTED RATHER THAN ASSERTED.  v6's whole
    justification for being a version bump at all is that `end` grew a field --
    so a v5 file must still be read with four, and SV_StageWrite and
    cl_lobbytime.qc both still write v5 after build 82."""
    ok_clean(build(ver=5, instart=False, inputs=False),
             "a v5 file with a four-field trailer still passes")


def case_warp_shape():
    """Build 83.  `warp <pk> <mt> <kind> <ox oy oz> <vx vy vz>` -- nine fields;
    v9 adds <row> and <fl> for eleven."""
    for ver, want in ((8, 9), (9, 11)):
        b = build(ver=ver, warps=[(5, HORIZON + 5, "tele")])
        ok_clean(b, "a well-formed v%d warp record passes" % ver)
        short = [l if not l.startswith("warp ") else " ".join(l.split()[:want])
                 for l in b]
        faults_with(short, "'warp' takes %d fields" % want,
                    "a short v%d warp record is a fault" % ver)


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
    # v9 adds lift and zone; a v8 file keeps the five.
    ok_clean(build(warps=[(5, HORIZON + 5, "lift"), (9, HORIZON + 9, "zone")]),
             "v9 warp kinds lift and zone pass")
    f, n = run(build(warps=[(5, HORIZON + 5, "lift")]))
    check(not n, "and draw no note in a v9 file")
    notes_with(build(ver=8, warps=[(5, HORIZON + 5, "lift")]),
               "not one this tool knows",
               "lift in a v8 file is still an unknown-kind note")


def case_ride_shape():
    """Build 85.  `ride <pk> <mt> <what> <bx by bz>` -- six fields."""
    b = build(rides=[(5, HORIZON + 5, "arm", 0.0, 0.0, 650.0)])
    ok_clean(b, "a well-formed ride record passes")

    short = [l if not l.startswith("ride ") else " ".join(l.split()[:6])
             for l in b]
    faults_with(short, "'ride' takes 6 fields",
                "a short ride record is a fault")


def case_ride_what_vocabulary_is_closed():
    """AND `warp`'s IS NOT -- the one place the two records are checked
    differently.  A <kind> names which HANDLER imposed state (a growing set, so an
    unknown one is a newer server and gets a note); a <what> names which half of a
    mechanism that has exactly two, so a third word is a fault.
    """
    ok_clean(build(rides=[(5, HORIZON + 5, "arm", 0.0, 0.0, 650.0)]),
             "ride what 'arm' passes")
    ok_clean(build(rides=[(5, HORIZON + 5, "pay", 0.0, 0.0, 650.0)]),
             "ride what 'pay' passes")
    faults_with(build(rides=[(5, HORIZON + 5, "held", 0.0, 0.0, 650.0)]),
                "not 'arm' or 'pay'",
                "an unknown ride what is a fault, unlike an unknown warp kind")


def case_ride_count():
    """The seventh field is EXACT, and its loss costs the most: a `ride` track is
    a STATE track, so a dropped record is a WRONG carrier held for an unbounded
    span rather than one missing fact, and that error does not heal.
    """
    b = build(rides=[(5, HORIZON + 5, "arm", 0.0, 0.0, 650.0),
                     (9, HORIZON + 9, "pay", 0.0, 0.0, 650.0)])
    ok_clean(b, "two ride records counted correctly in the trailer pass")
    faults_with(bump_end(b, "rides"), "ride records, the file has",
                "a trailer that over-counts the ride records is a fault")
    dropped = [l for l in b if not l.startswith("ride ")]
    faults_with(dropped, "ride records, the file has",
                "a trailer counting rides a truncated body does not have "
                "is a fault")


def case_bare_pay_is_the_addoutput_shape():
    """A `pay` with no `arm` before it is CORRECT.

    Mid-run it is `AddOutput basevelocity` (789 outputs / 139 zoned maps), which
    writes the carrier WITHOUT the armed flag, so the mover is never handed it and
    there is no span to open.  At the horizon it is a run that began mid-ride and
    ended it on the first recorded command -- what build 85's capture arm actually
    measured, after pre-registering the opposite.
    """
    ok_clean(build(rides=[(0, HORIZON, "pay", -1700.0, 0.0, 0.0),
                          (0, HORIZON, "arm", 0.0, 0.0, 0.0)]),
             "a pay before any arm is not a fault (the inherited-ride shape)")
    ok_clean(build(rides=[(5, HORIZON + 5, "arm", 0.0, 0.0, 250.0),
                          (9, HORIZON + 9, "pay", 0.0, 0.0, 250.0),
                          (9, HORIZON + 9, "arm", 0.0, 0.0, 0.0),
                          (20, HORIZON + 20, "pay", 0.0, 0.0, 650.0)]),
             "a ride span followed by a bare AddOutput pay is not a fault")
    # Build 87 corrected the grammar: `arm 0` follows a pay only after a
    # non-zero arm (or none since open), so a lone mid-run pay has none.
    ok_clean(build(rides=[(12, HORIZON + 12, "pay", 0.0, 0.0, 650.0)]),
             "a lone mid-run pay with no arm 0 after it is not a fault")


def case_ride_below_horizon():
    """The horizon binds the carrier track too."""
    faults_with(build(rides=[(5, HORIZON - 3, "arm", 0.0, 0.0, 650.0)]),
                "below the trace's horizon",
                "a ride stamped before the horizon is a fault")


def case_ride_monotone():
    """A ride cannot go backwards in <mt>, and a warp can: several warps share a
    packet and arrive in touch order, while these are written once per command.
    """
    faults_with(build(rides=[(9, HORIZON + 9, "arm", 0.0, 0.0, 650.0),
                             (5, HORIZON + 5, "pay", 0.0, 0.0, 650.0)]),
                "cannot go backwards",
                "a ride track that steps backwards in movetick is a fault")


def case_inend_shape():
    """Build 85.  `inend <mt> <carry>`, written at close."""
    ok_clean(build(), "a well-formed inend record passes")

    b = build()
    short = [l if not l.startswith("inend ") else "inend 700" for l in b]
    faults_with(short, "'inend' takes 2 fields",
                "a one-field inend is a fault")


def case_inend_is_required_beside_a_trailer():
    """`inend` and `end` come from one function, so a trailer without a closing
    horizon is a writer that has gone wrong."""
    faults_with(build(inend=False), "a writer that has gone wrong",
                "a v8 file with a trace, a trailer and no inend is a fault")


def case_inend_not_demanded_of_a_part():
    """AND A .part LEGITIMATELY HAS NEITHER -- the arm that keeps the check honest.

    SV_RecClose writes `inend` and `end` together or not at all.  The first cut of
    this check keyed off the `in` rows alone and faulted build 85's own capture
    arm: a false note about a correct file, which this tool may not produce.
    """
    b = [l for l in build(inend=False) if not l.startswith("end ")]
    f, n = run(b, name="t.part")
    check(not any("inend" in x for x in f),
          "a .part with no trailer is not faulted for having no inend")
    check(any("interrupted .part" in x for x in n),
          "a .part is still reported as interrupted")


def case_inend_not_below_the_last_row():
    """The final move's duration is inend minus the last `in` row's <mt>; a
    negative one is not a rounding question."""
    b = build()
    bad = [l if not l.startswith("inend ") else "inend %d 0.00300" % (HORIZON - 1)
           for l in b]
    faults_with(bad, "below the trace's horizon",
                "an inend below the horizon is a fault")


def case_v7_needs_no_inend_and_keeps_six_fields():
    """A version bump must not retroactively fault every file already on disk.
    v7 files are the corpus this build inherits: no `inend`, six trailer fields,
    and still correct.  Same claim case_v6_trailer_still_five_fields makes.
    """
    ok_clean(build(ver=7), "a v7 file with no inend and six trailer fields "
                           "still passes")


def case_v7_carrier_silence_is_not_a_claim():
    """AND THE REASON v8 EXISTS: v7 silence about boosters is a limit of the
    format, not a statement.  E5 measured a v7 PB with zero warps across ten
    boosters, so a v7 file with no carrier track must not fault.
    """
    ok_clean(build(ver=7, warps=()),
             "a v7 file with no warp and no ride records is not faulted")


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


# ---------------------------------------------------------------------------
# v9 (build 87): exact state.
# ---------------------------------------------------------------------------
V9_ALL = dict(warps=[(5, HORIZON + 6, "tele", 5)],
              rides=[(3, HORIZON + 3, "arm", 0.0, 0.0, 250.0)],
              pms=[(7, 7)], pes=[(0, 0, 1948226), (9, 9, 0xFFFFFF)],
              portals=[(12, 12, 1)])


def case_v9_every_record_clean():
    f, n = run(build(**V9_ALL))
    check(not f and not n, "a v9 file with seed, pmpin, warp, ride, pm, pe and "
                           "portal passes with no faults and no notes")
    if f or n:
        print("        faults=%s notes=%s" % (f, n))


def case_v9_exponent_is_legal_in_float_columns():
    """%.9g switches to exponent form below 1e-4; those columns must not fault."""
    for kind, pos, v in (("warp", 9, "-4.37113883e-08"),
                         ("in", 3, "9.99999975e-05"),
                         ("ride", 6, "7.26431608e-08"),
                         ("seed", 4, "-1.25664083e-04"),
                         ("portal", 8, "-4.37113883e-08"),
                         ("inend", 2, "9.99999975e-05")):
        ok_clean(edit(build(**V9_ALL), kind, pos, v),
                 "v9 %s column %d in exponent form (%s) passes" % (kind, pos, v))


def case_v9_exponent_still_faults_elsewhere():
    """Integer columns, and the fixed-point sample columns, keep EXP_RE's rule."""
    for kind, pos, v in (("pe", 3, "1.9e+06"), ("warp", 3, "5e+00"),
                         ("in", 2, "6.06e+02"), ("end", 1, "4e+01"),
                         ("sample", 1, "0e+00")):
        faults_with(edit(build(**V9_ALL), kind, pos, v), "in exponent form",
                    "v9 %s column %d in exponent form is a fault" % (kind, pos))


def case_v9_trailer_counts():
    b = build(**V9_ALL)
    for field, kind in (("pms", "pm"), ("pes", "pe"), ("portals", "portal")):
        for d, how in ((1, "over"), (-1, "under")):
            faults_with(bump_end(b, field, d), "%s records, the file has" % kind,
                        "a trailer that %s-counts %s is a fault" % (how, field))


def case_v9_row_must_be_written_already():
    """Every row-bound record is written after its row's move."""
    faults_with(build(warps=[(5, HORIZON + 6, "tele", PACKETS)]),
                "names row %d" % PACKETS, "a warp naming a row past the end "
                                          "is a fault")
    ok_clean(build(warps=[(5, HORIZON + 6, "tele", -1)]),
             "a warp naming row -1 (imposed on the seed) passes")
    faults_with(build(warps=[(5, HORIZON + 6, "tele", -2)]),
                "names row -2", "a warp naming row -2 is a fault")
    faults_with(build(pes=[(1, -1, 7)]), "'pe' names row -1",
                "only a warp may name row -1")
    # Row 6 exists later in the file, but not yet.
    faults_with(after_row(build(), 5, "warp 5 %d 6 tele 0 0 64 0 0 0 0"
                          % (HORIZON + 6)),
                "names row 6 and 6", "a warp naming a row not yet written "
                                     "is a fault")
    ok_clean(bump_end(after_row(build(), 5, "warp 5 %d 5 tele 0 0 64 0 0 0 0"
                                % (HORIZON + 6)), "warps"),
             "a warp naming the row just written passes")
    for kind, kw in (("pm", dict(pms=[(1, PACKETS)])),
                     ("pe", dict(pes=[(1, PACKETS, 7)])),
                     ("portal", dict(portals=[(1, PACKETS, 1)]))):
        faults_with(build(**kw), "'%s' names row %d" % (kind, PACKETS),
                    "a %s naming a row past the end is a fault" % kind)


def case_v9_seed():
    b = build()
    ix = [i for i, l in enumerate(b) if l.startswith("seed ")][0]
    faults_with(b[:ix + 1] + [b[ix]] + b[ix + 1:], "a second 'seed'",
                "a second seed is a fault")
    faults_with(build(pmpin=False), "with no 'pmpin'",
                "a seed without pmpin is a fault")
    faults_with(b[:ix] + [b[ix + 1], b[ix]] + b[ix + 2:],
                "not the first line after 'begin'",
                "a seed that is not right after begin is a fault")
    notes_with(build(seed=False), "there is no 'seed'",
               "pmpin with no seed is a note")
    ok_clean(build(pmpin=False, seed=False),
             "no pmpin and no seed (engine before Patch 346) passes")


def case_v9_field_values():
    for lines, want, what in (
            (row(build(), fl=8), "is outside 0..7", "'in' fl 8"),
            (row(build(), fwd="450.5"), "non-integer", "'in' fwd 450.5"),
            (edit(build(**V9_ALL), "warp", 11, 2), "is not 0 or 1", "warp fl 2"),
            (edit(build(**V9_ALL), "pe", 3, 0x1000000), "24-bit", "pe crc 2^24"),
            (edit(build(**V9_ALL), "portal", 3, 0), "positive", "portal n 0"),
            (edit(build(**V9_ALL), "pm", 3, "gravity"), "name=value",
             "a pm token with no value"),
            (edit(build(**V9_ALL), "pm", 5, "gravity=1"), "appears twice",
             "a pm naming a value twice"),
            (head(build(), "pmpin", PIN + " maxspeed"), "name=value",
             "a pmpin token with no value"),
            (head(build(), "pmpin", ""), "carries no values", "an empty pmpin")):
        faults_with(lines, want, "%s is a fault" % what)
    notes_with(row(build(), fl=4), "never occur on a clean run",
               "'in' fl 4 is a note, not a fault")


def case_v8_as_before():
    """The v8 contract is untouched: blanket exponent rule, v9 records unknown."""
    f, n = run(build(ver=8))
    check(not f and not n, "a v8 file passes with no faults and no notes")
    faults_with(row(build(ver=8), carry="9.99999975e-05"), "in exponent form",
                "a v8 carry in exponent form is still a fault")
    b = build(ver=8)
    notes_with(b[:-1] + ["pe 1 1 7"] + b[-1:], "unknown record 'pe'",
               "a pe record in a v8 file is still an unknown-record note")


def case_v9_zseed():
    """build 88: the timer latches for pm_verify -- once, before the first row."""
    z = "zseed evzone=-1 azone=0 cpzone=-1 track=0 startseg=0 stagerun=0 twarp=1"
    b = build(**V9_ALL)
    k = b.index("begin") + 2          # after `begin` and `seed`
    ok_clean(b[:k] + [z] + b[k:], "a zseed after the seed and before row 0 passes")
    faults_with(b[:k] + [z, z] + b[k:], "a second 'zseed'", "two zseeds is a fault")
    faults_with(after_row(build(**V9_ALL), 3, z), "'zseed' after",
                "a zseed after a row is a fault")
    faults_with(b[:k] + [z.replace(" twarp=1", "")] + b[k:], "'zseed' lacks twarp",
                "a zseed missing a latch is a fault")


# ---------------------------------------------------------------------------
# Patch 360: stagepost / abandon (additive, no version bump).
# ---------------------------------------------------------------------------
# A main run crossing 4 stages; the trailer's ticks are PACKETS (40).  Stage 0
# posts from the run's start (base 0); stage 2 is flown through (no stagestart,
# so never primed); stage 3 posts at the finish.
STAGED = ["stagepost 0 10 280", "stage 1 10",
          "stagestart 1 14", "stagepost 1 8 250", "stage 2 22",
          "stage 3 30",
          "stagestart 3 31", "stagepost 3 9 270"]


def staged(recs=STAGED, pre=(), **kw):
    """build() with stage records (and `pre`) spliced in before the trailer."""
    b = build(**kw)
    ix = [i for i, l in enumerate(b) if l.split()[0] in ("inend", "end")][0]
    return b[:ix] + list(recs) + list(pre) + b[ix:]


def swap(recs, old, new):
    return [new if r == old else r for r in recs]


def case_stagepost():
    f, n = run(staged())
    check(not f and not n, "a main run posting stages 0, 1 and 3 passes clean")
    if f or n:
        print("        faults=%s notes=%s" % (f, n))
    # The print tuple has no other falsifier (see emit()).
    d = tempfile.mkdtemp(prefix="reccheck_t")
    try:
        p = os.path.join(d, "t.rec")
        with open(p, "w", encoding="utf-8") as fh:
            fh.write("\n".join(staged()) + "\n")
        out = subprocess.run([sys.executable, RECCHECK, "-v", p],
                             capture_output=True, text=True).stdout
    finally:
        shutil.rmtree(d, ignore_errors=True)
    check("stageposts     3" in out, "-v prints stageposts 3")
    for recs, want, what in (
            (swap(STAGED, "stagepost 1 8 250", "stagepost 1 9 250"),
             "says 9 ticks, but its stage ran 8", "a post off by one tick"),
            (swap(STAGED, "stagepost 3 9 270", "stagepost 3 10 270"),
             "ran 9 to the finish", "a finish post off by one tick"),
            (STAGED[:5] + ["stagepost 2 8 0"] + STAGED[5:],
             "never left its box", "a post for a flown-through stage"),
            (STAGED[:4] + ["stagepost 1 8 250"] + STAGED[4:],
             "a second 'stagepost' for stage 1", "two posts for one stage"),
            (swap(STAGED, "stagepost 1 8 250", "stagepost 2 8 250"),
             "not the open one (1)", "a post naming the wrong stage"),
            (STAGED[:4] + ["restart 1 20"] + STAGED[4:],
             "'restart' after stage 1 was posted", "a restart after a post"),
            (swap(STAGED, "stagepost 1 8 250", "stagepost 1 8"),
             "takes 3 fields", "a two-field post")):
        faults_with(staged(recs), want, "%s is a fault" % what)
    b = head(staged(), "leg", 2)
    faults_with(b, "only a main run posts", "a post in a stage run (leg 2) is a fault")


def case_abandon():
    ok_clean(staged(pre=["abandon %d" % PACKETS]),
             "an abandoned run with posts, abandon at the trailer's ticks, passes")
    faults_with(staged(pre=["abandon %d" % (PACKETS - 1)]),
                "but the trailer says", "an abandon off the trailer's ticks is a fault")
    faults_with(staged(pre=["abandon %d" % PACKETS] * 2), "a second 'abandon'",
                "two abandons is a fault")
    # A save-load rewinds the clock before the keep: abandon/end below the stages.
    b = bump_end(staged(pre=["abandon 25"]), "ticks", 25 - PACKETS)
    faults_with(b, "before the stage record at 31",
                "an abandon earlier than its own stage records is a fault")
    notes_with(staged(recs=(), pre=["abandon %d" % PACKETS]), "with no 'stagepost'",
               "an abandon with nothing posted is a note")


# ---------------------------------------------------------------------------
# Patch 364: v10 -- `pause` / `session`, a run across a counter restart.
# ---------------------------------------------------------------------------
V10 = dict(ver=10, sessions=[(15, 3, "drop")])


def drop_kinds(lines, kinds):
    return [l for l in lines if l.split()[0] not in kinds]


def insert_before(lines, kind, text):
    ix = [i for i, l in enumerate(lines) if l.split()[0] == kind][0]
    return lines[:ix] + [text] + lines[ix:]


def case_v10_session():
    f, n = run(build(**V10))
    check(not f and not n, "a v10 run with a drop pause and session 2 passes clean")
    if f or n:
        print("        faults=%s notes=%s" % (f, n))
    d = tempfile.mkdtemp(prefix="reccheck_t")
    try:
        p = os.path.join(d, "t.rec")
        with open(p, "w", encoding="utf-8") as fh:
            fh.write("\n".join(build(**V10)) + "\n")
        out = subprocess.run([sys.executable, RECCHECK, "-v", p],
                             capture_output=True, text=True).stdout
    finally:
        shutil.rmtree(d, ignore_errors=True)
    check("sessions       1" in out and "pauses         drop" in out,
          "-v prints sessions 1 and the pause reason")

    # THE CONTROL: the same body without the two records must fault.
    b = bump_end(drop_kinds(build(**V10), ("pause", "session")), "sessions", -1)
    faults_with(b, "movetick goes backwards",
                "the same body minus pause/session faults (control)")

    b = build(**V10)
    faults_with(bump_end(b, "sessions", 1), "'end' says 2 sessions",
                "a trailer over-counting sessions is a fault")
    faults_with(edit(b, "session", 4, 99), "the clock does not run while parked",
                "session ticks off the pause's is a fault")
    faults_with(drop_kinds(b, ("pause",)), "with no 'pause' before it",
                "a session with no pause is a fault")
    faults_with(edit(b, "session", 1, 3), "where session 2 comes next",
                "a session numbered out of order is a fault")
    faults_with(insert_before(b, "session", "in 15 3 0.003 0 0 0 0.0000 90.0000 0.0000 0 0"),
                "an 'in' row inside the pause", "an in row inside a pause is a fault")
    faults_with(edit(b, "inend", 1, 2), "below the trace's horizon 3",
                "an inend below the last session's horizon is a fault")
    faults_with([l for l in b if not l.startswith("end ")]
                + ["pause 50 0.003 41 drop", [l for l in b if l.startswith("end ")][0]],
                "a run does not finish while parked", "a trailer while paused is a fault")
    faults_with(bump_end(b, "sessions", 0)[:-1] + [" ".join(b[-1].split()[:-1])],
                "'end' takes 11 fields in a v10 file", "a v10 trailer of 10 fields is a fault")
    # <carry> is %.9g: a tiny one prints in exponent form (p364rewind arm C).
    ok_clean(edit(edit(b, "pause", 2, "2.81259418e-07"), "session", 3, "2.81259418e-07"),
             "a %.9g carry in exponent form on pause/session is legal")
    faults_with(edit(b, "pause", 3, "1.6e+01"), "in exponent form",
                "an exponent in a pause's <ticks> is a fault")


def case_v10_horizons_restart():
    # A warp below the new horizon faults; a ride and a board may restart.
    b = build(**V10)
    ix = [i for i, l in enumerate(b) if l.startswith("session ")][0]
    w = b[:ix + 2] + ["warp 16 1 16 tele 0 0 64 0 0 0 0"] + b[ix + 2:]
    faults_with(bump_end(w, "warps"), "warp at movetick 1 is below the trace's horizon 3",
                "a warp below the session's horizon is a fault")
    rides = b[:ix - 1] + ["ride 14 %d arm 0 0 250" % (HORIZON + 20)] + b[ix - 1:ix + 2] \
        + ["ride 16 5 pay 0 0 250"] + b[ix + 2:]
    ok_clean(bump_end(rides, "rides", 2),
             "a ride track restarts with the session (mt 5 after %d)" % (HORIZON + 20))
    boards = b[:ix - 1] + ["board 0.1 7 0 0 1 0 0 0"] + b[ix - 1:ix + 2] \
        + ["board 0.2 1 0 0 1 0 0 0"] + b[ix + 2:]
    f, _ = run(boards)
    check(not any("board counter" in x for x in f),
          "the board counter restarts with the session")
    if any("board counter" in x for x in f):
        print("        %s" % f)


def case_v10_flag():
    faults_with(head(build(**V10), "flags", 0), "does not say multi-session",
                "a drop pause without TF_MULTISESSION is a fault")
    ok_clean(build(ver=10, sessions=[(15, 3, "retry")]),
             "a retry session sets no bit and passes")
    faults_with(head(build(ver=10, sessions=[(15, 3, "retry")]), "flags", 16384),
                "says multi-session, but there is no",
                "TF_MULTISESSION with only a retry pause is a fault")


def case_v9_session_is_unknown():
    b = build()
    notes_with(insert_before(b, "inend", "session 2 3 0.003 20"),
               "unknown record 'session'", "a session in a v9 file is an unknown-record note")


def main():
    for fn in (case_control,
               case_no_horizon, case_horizon_without_rows,
               case_trailer_width, case_trailer_count,
               case_row_width,
               case_movetick_backwards, case_packet_backwards,
               case_below_horizon, case_carry_bound, case_button_width,
               case_instart_ordering, case_resume_is_not_a_fault,
               case_offgrid_angle_is_a_note, case_v9_offgrid_angle_is_a_fault,
               case_v5_trailer_still_four_fields,
               case_v6_trailer_still_five_fields,
               case_warp_shape, case_warp_count, case_warp_below_horizon,
               case_warp_unknown_kind_is_a_note,
               case_ride_shape, case_ride_what_vocabulary_is_closed,
               case_ride_count, case_bare_pay_is_the_addoutput_shape,
               case_ride_below_horizon, case_ride_monotone,
               case_inend_shape, case_inend_is_required_beside_a_trailer,
               case_inend_not_demanded_of_a_part,
               case_inend_not_below_the_last_row,
               case_v7_needs_no_inend_and_keeps_six_fields,
               case_v7_carrier_silence_is_not_a_claim,
               case_startjit_shape, case_startjit_outside_its_own_rule,
               case_startjit_vertical_is_a_fault,
               case_startjit_blocked_is_a_note_not_a_fault,
               case_v9_every_record_clean,
               case_v9_exponent_is_legal_in_float_columns,
               case_v9_exponent_still_faults_elsewhere,
               case_v9_trailer_counts, case_v9_row_must_be_written_already, case_v9_zseed,
               case_v9_seed, case_v9_field_values, case_v8_as_before,
               case_stagepost, case_abandon,
               case_v10_session, case_v10_horizons_restart, case_v10_flag,
               case_v9_session_is_unknown):
        print("%s:" % fn.__name__)
        fn()
        print("")
    print("%d checks, %d failed" % (CHECKS, len(FAILED)))
    for f in FAILED:
        print("  FAILED: %s" % f)
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
