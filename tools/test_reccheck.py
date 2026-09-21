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
# $RECCHECK runs the suite against another copy (the pre-patch control).
RECCHECK = os.environ.get("RECCHECK") or os.path.join(HERE, "reccheck.py")

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
# One 16-bit wire quantum, the unit `sweep` counts in (protocol.h:1496).
QUANTUM = 360.0 / 65536.0
# v9: a pin with an exponent-form value, as %.9g prints one.
PIN = "pmsrcver=1 gravity=800 maxspeed=320 ticrate=0.00999999978 bounce=1e-05"


def build(instart=True, inputs=True, ver=9, startjit=None, warps=(),
          rides=(), inend=True, pmpin=True, seed=True, pms=(), pes=(),
          portals=(), sessions=(), sweep=0.0, packets=None):
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
    np_ = PACKETS if packets is None else packets
    for pk in range(np_):
        if inputs:
            # `sweep` turns the camera, in whole 16-bit quanta so the
            # off-grid arm above stays clean: the angle cross-check divides by
            # the tick's own sweep, so a fixture that never turns is BLIND and
            # cannot tell a matching sidecar from any other.
            yaw = 90.0 + n_in * sweep * QUANTUM
            if v9:
                L.append("in %d %d %.9g 0 0 0 0.0000 %.4f 0.0000 0 0" %
                         (pk, mt, carry, yaw))
            else:
                L.append("in %d %d %.5f 0 0 0 0.0000 %.4f 0.0000 0" %
                         (pk, mt, carry, yaw))
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

    tail = [np_, PAD + np_, PAD, 0]
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


def view_for(lines, rot=0.0, lo=0.0, hi=1.0, dense=1):
    """A sidecar that agrees with `lines`, optionally rotated over a window.

    BUILT FROM THE RECORDING'S OWN ROWS, which is the only way an arm for this
    check can be honest: the thing under test is whether the two files describe
    one run, so the control has to be a sidecar that genuinely does.  Frames are
    written at %.2f exactly as Rec_ViewSample does, so the residual the checker
    sees here is the same print rounding it sees on a real pair.

    ONE FRAME PER MOVE by default, which is the WORST case for the sweep rule
    -- a real client renders several per tick and the checker takes the best of
    them -- and the BEST case for the one-frame rule, which only has something
    to say about a tick that held exactly one.  `dense` writes that many frames
    per tick instead, which is what a client above the mover rate produces and
    what takes the one-frame rule's coverage to nothing.
    """
    rows = [l.split() for l in lines if l.startswith("in ")]
    ticks = [int(f[2]) - HORIZON for f in rows]
    # The trailer's tick count is the sidecar's ceiling: check_view faults a
    # .view that runs past the recording, and that is a different finding.
    end = [l.split() for l in lines if l.startswith("end ")]
    top = int(end[0][1]) if end else max(ticks)
    keep = [(tk, f) for tk, f in zip(ticks, rows) if 0 <= tk <= top]
    out = ["FTESURF-VIEW 2", "map bhop_eazy", "hid 1", "begin"]
    n = len(keep)
    for i, (tk, f) in enumerate(keep):
        yaw = float(f[8])
        if lo * n <= i < hi * n:
            yaw = ((yaw + rot) + 180.0) % 360.0 - 180.0
        for k in range(dense):
            out.append("%.4f %d %d %.2f %.2f 0"
                       % (10.0 + (tk + k / float(dense)) * TICK,
                          1000 + tk, tk, float(f[7]), yaw))
    return out


def run(lines, name="t.rec", view=None):
    """-> (faults, notes) as reccheck.py reports them."""
    d = tempfile.mkdtemp(prefix="reccheck_t")
    try:
        p = os.path.join(d, name)
        with open(p, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
        if view is not None:
            with open(os.path.splitext(p)[0] + ".view", "w", encoding="utf-8") as f:
                f.write("\n".join(view) + "\n")
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


def case_mc():
    """Patch 376: the client's mouse counts, additive in v9."""
    b = build()
    ok_clean(insert_before(b, "inend", "mc 3 3 234 0 234 0 0"),
             "an mc whose ring equals its read passes clean")
    notes_with(insert_before(b, "inend", "mc 3 3 234 0 235 0 0"),
               "the view used counts the device did not send",
               "an mc whose read differs from its ring is a note")
    faults_with(insert_before(b, "inend", "mc 3 3 234 0 234 0"),
                "'mc' takes 7 fields", "a short mc is a fault")


def case_v9_session_is_unknown():
    b = build()
    notes_with(insert_before(b, "inend", "session 2 3 0.003 20"),
               "unknown record 'session'", "a session in a v9 file is an unknown-record note")


# ---------------------------------------------------------------------------
# Patch 382: `spec` -- a spectate hold (additive, no bump).
# ---------------------------------------------------------------------------
TF_SPEC = 32768
SPEC_WHY = ("leave", "drop", "rotate", "server", "retry", "load", "zone",
            "setpos", "respawn", "move", "notarget")
# <ox oy oz> <vx vy vz> <fl>, %.9g.  Plain by default, so the pre-patch control
# faults nothing for an unrelated reason; EXP_BODY is what %.9g prints near 0.
SPEC_BODY = "-123.456001 4.5 64.03125 250.5 -1 0 0"
EXP_BODY = "-123.456001 4.5e-05 64.03125 250.5 -7.26431608e-08 0 0"


def spec_edges(ticks, mt, carry, why="leave", wall=(812.5, 815.25), body=SPEC_BODY):
    return ["spec 1 %s %s %s %s %.3f" % (ticks, mt, carry, body, wall[0]),
            "spec 0 %s %s %s %s %.3f %s" % (ticks, mt, carry, body, wall[1], why)]


def set_spec_flag(lines):
    fx = [i for i, l in enumerate(lines) if l.startswith("flags ")][0]
    lines = list(lines)
    lines[fx] = "flags %d" % (int(lines[fx].split()[1]) | TF_SPEC)
    return lines


def spectated(lines=None, which=12, flag=True, **kw):
    """A window between packets, before the `which`-th `in` row: its edges state
    that row's <mt> <carry>, the counter after the last move."""
    b = build() if lines is None else list(lines)
    ix = [i for i, l in enumerate(b) if l.startswith("in ")][which]
    f = b[ix].split()
    b = b[:ix] + spec_edges(which, f[2], f[3], **kw) + b[ix:]
    return set_spec_flag(b) if flag else b


def spec_line(lines, on, which=0):
    return [i for i, l in enumerate(lines) if l.startswith("spec %d " % on)][which]


def spec_edit(lines, on, pos, value, which=0):
    """Set token `pos` (keyword = 0, state = 1) of a `spec <on>` line."""
    lines = list(lines)
    ix = spec_line(lines, on, which)
    f = lines[ix].split()
    f[pos] = str(value)
    lines[ix] = " ".join(f)
    return lines


def verbose_out(lines, name="t.rec"):
    d = tempfile.mkdtemp(prefix="reccheck_t")
    try:
        p = os.path.join(d, name)
        with open(p, "w", encoding="utf-8") as fh:
            fh.write("\n".join(lines) + "\n")
        return subprocess.run([sys.executable, RECCHECK, "-v", p],
                              capture_output=True, text=True).stdout
    finally:
        shutil.rmtree(d, ignore_errors=True)


def case_spec_clean():
    f, n = run(spectated())
    check(not f and not n, "a spectated v9 file passes with no faults and no notes")
    if f or n:
        print("        faults=%s notes=%s" % (f, n))
    out = verbose_out(spectated())
    for want in ("spectated      yes", "spec_windows   1", "spec_held      2.750",
                 "spec_why       leave"):
        check(want in out, "-v prints %r (the r.info tuple)" % want)
    check("spectated      no" in verbose_out(build()),
          "-v prints 'spectated no' for a file without the bit")
    ok_clean(spectated(body=EXP_BODY),
             "a %.9g origin and velocity in exponent form pass")
    ok_clean(spectated(lines=row(build(), which=12, carry="9.99999975e-05")),
             "a %.9g <carry> in exponent form on both edges and the row passes")
    two = spectated()
    ix = spec_line(two, 1)
    e = two[ix].split()
    two = two[:ix] + spec_edges(e[2], e[3], e[4], why="zone") + two[ix:]
    ok_clean(spectated(two, which=30, flag=False, why="notarget"),
             "three windows, two back to back before one row, pass")
    for why in SPEC_WHY:
        f, n = run(spectated(why=why))
        check(not f and not n, "reason %r passes with no note" % why)
    ok_clean(spectated(lines=build(ver=10, sessions=[(15, 3, "drop")]), which=25),
             "a window in the second session of a v10 Multi-Session file passes")


def case_spec_malformed():
    b = spectated()
    ix = spec_line(b, 1)
    for lines, want, what in (
            (spec_edit(b, 1, 1, 2), "state '2' is not 0 or 1", "a spec state 2"),
            (b[:ix] + [" ".join(b[ix].split()[:-1])] + b[ix + 1:],
             "'spec 1' takes 11 fields", "a spec 1 with 10 fields"),
            (b[:ix] + [b[ix] + " leave"] + b[ix + 1:],
             "'spec 1' takes 11 fields", "a spec 1 with a <why>"),
            (b[:ix + 1] + [" ".join(b[ix + 1].split()[:-1])] + b[ix + 2:],
             "'spec 0' takes 12 fields", "a spec 0 with no <why>"),
            (spec_edit(b, 0, 6, "x"), "has a non-numeric field", "a non-numeric origin"),
            (spec_edit(b, 0, 7, "nan"), "has a non-numeric field", "a nan origin"),
            (spec_edit(spec_edit(b, 0, 3, "618.5"), 1, 3, "618.5"),
             "a non-integer <mt>", "a non-integer <mt>"),
            (spec_edit(spec_edit(b, 0, 11, 2), 1, 11, 2), "an <fl> other than 0 or 1",
             "an <fl> of 2"),
            (spec_edit(b, 1, 3, "6.18e+02"), "in exponent form",
             "an <mt> in exponent form")):
        faults_with(lines, want, "%s is a fault" % what)


def case_spec_alternation():
    b = spectated()
    faults_with([l for l in b if not l.startswith("spec 1 ")],
                "'spec 0' with no window open", "a spec 0 with no 1 open is a fault")
    ix = spec_line(b, 1)
    faults_with(b[:ix] + [b[ix]] + b[ix:], "while the window opened at line",
                "a spec 1 inside an open window is a fault")


def case_spec_nothing_inside():
    b = spectated()
    ix = spec_line(b, 0)
    row = [l for l in b if l.startswith("in ")][12]
    smp = [l for l in b if l[:1].isdigit()][12]
    for text, what in ((row, "an 'in' row"), (smp, "a sample"),
                       ("ghost 1 12", "a 'ghost' line"), ("foo 1 2", "a 'foo' line")):
        faults_with(b[:ix] + [text] + b[ix:], "%s inside the spec window" % what,
                    "%s between a 1 and its 0 is a fault" % what)


def case_spec_edges_agree():
    b = spectated()
    for pos, name, value in ((2, "ticks", 13), (3, "mt", 999), (4, "carry", 0.00499),
                             (6, "oy", 16), (9, "vy", 5), (11, "fl", 1)):
        faults_with(spec_edit(b, 0, pos, value), "disagree on %s" % name,
                    "a spec 0 whose <%s> differs from its 1 is a fault" % name)
    ok_clean(spec_edit(spec_edit(spectated(body=EXP_BODY), 0, 7, "64.031250"),
                       0, 6, "0.000045"),
             "the same numbers in other text (64.031250, 0.000045) pass")
    ok_clean(spec_edit(b, 0, 12, "9999.000"),
             "a different <wall> is not part of the edge identity")
    notes_with(spec_edit(b, 0, 12, "800.000"), "<wall> runs backwards",
               "a window whose <wall> runs backwards is a note")


def case_spec_next_row_restates():
    base = build()
    ix = [i for i, l in enumerate(base) if l.startswith("in ")][12]
    mt, carry = base[ix].split()[2:4]
    for emt, ecarry, what in ((int(mt) - 1, carry, "mt"), (mt, "0.00123", "carry")):
        b = set_spec_flag(base[:ix] + spec_edges(12, emt, ecarry) + base[ix:])
        faults_with(b, "the 'in' row after the 'spec 0' at line",
                    "a next 'in' row not restating the edge's <%s> is a fault" % what)
    b = set_spec_flag(base[:ix] + spec_edges(12, int(mt) - 1, carry)
                      + spec_edges(12, mt, carry) + base[ix:])
    faults_with(b, "the 'in' row after the 'spec 0' at line",
                "a row restating only the second of two windows before it is a fault")
    # A Multi-Session pause is counter-bearing; a retry/load pause ends the check.
    for why in ("drop", "retry"):
        v = build(ver=10, sessions=[(15, 3, why)])
        px = [i for i, l in enumerate(v) if l.startswith("pause ")][0]
        p = v[px].split()
        good = v[:px] + spec_edges(16, p[1], p[2]) + v[px:]
        bad = v[:px] + spec_edges(16, int(p[1]) + 5, p[2]) + v[px:]
        ok_clean(set_spec_flag(good), "a window before a '%s' pause stating its "
                                      "counter passes" % why)
        if why == "drop":
            faults_with(set_spec_flag(bad), "the 'drop' pause after the 'spec 0'",
                        "a 'drop' pause not restating the edge's <mt> is a fault")
            faults_with(set_spec_flag(v[:px] + spec_edges(16, p[1], "0.00777") + v[px:]),
                        "the 'drop' pause after the 'spec 0'",
                        "a 'drop' pause not restating the edge's <carry> is a fault")
            f, _ = run(set_spec_flag(v[:px] + spec_edges(16, int(p[1]) + 5, p[2])
                                     + ["resume 1 16"] + v[px:]))
            check(any("'drop' pause" in x and "the rewind at line" in x for x in f),
                  "a 'drop' pause past a rewind, below the edge's <mt>, is a fault")
            if not f:
                print("        got: NO FAULT")
        else:
            ok_clean(set_spec_flag(bad), "a 'retry' pause after a window is not "
                                         "read as restating it")
    # A warm rewind whose mark sat right after the 0: the rows run on from the
    # live counter, so only >= holds.  (The control is the mt-1 arm above.)
    for rec in ("resume 1 12", "retry 12"):
        kw = rec.split()[0]
        ok_clean(set_spec_flag(base[:ix] + spec_edges(12, int(mt) - 1, carry) + [rec]
                               + base[ix:]),
                 "a '%s' between the 0 and the next row: a counter that ran on passes" % kw)
        faults_with(set_spec_flag(base[:ix] + spec_edges(12, int(mt) + 5, carry) + [rec]
                                  + base[ix:]), "and the rewind at line",
                    "...and a row below the edge's <mt> after a '%s' is a fault" % kw)


def case_spec_where():
    """Positions SV_SpecStart never writes a window in.  The clean twins pass on
    the pre-381 reccheck too: they show the fault is the position, not the edges."""
    base = build()
    ii = [i for i, l in enumerate(base) if l.startswith("inend ")][0]
    ie = [i for i, l in enumerate(base) if l.startswith("end ")][0]
    s1, s0 = spec_edges(PACKETS, *base[ii].split()[1:3])
    ok_clean(set_spec_flag(base[:ii] + [s1, s0] + base[ii:]),
             "its clean twin: a window just before the trailer passes")
    for lines, what in (
            (base[:ii] + [s1, base[ii], s0] + base[ii + 1:], "a window spanning 'inend'"),
            (base[:ii] + [s1] + base[ii:ie + 1] + [s0] + base[ie + 1:],
             "a window spanning 'inend' and 'end'"),
            (base[:ii + 1] + [s1, s0] + base[ii + 1:], "a window between 'inend' and 'end'"),
            (base + [s1, s0], "a window after 'end'")):
        faults_with(set_spec_flag(lines), "after the trailer", "%s is a fault" % what)
    f, _ = run(set_spec_flag(base[:ii] + [s1] + base[ii:]))
    check(len(f) == 1 and "never closed" in f[0],
          "a window open across the trailer is one fault, 'never closed'")
    if len(f) != 1:
        print("        got: %s" % (f or "NO FAULT"))

    # pm_verify refuses this one too (sv_ccmds.c "a spec edge inside a ghost window").
    def ghosted(lines):
        fx = [i for i, l in enumerate(lines) if l.startswith("flags ")][0]
        lines[fx] = "flags %d" % (int(lines[fx].split()[1]) | 64)     # TF_GHOST
        return lines
    b = spectated()
    i1, i0 = spec_line(b, 1), spec_line(b, 0)
    faults_with(ghosted(b[:i1] + ["ghost 1 12"] + b[i1:i0 + 1] + ["ghost 0 12"] + b[i0 + 1:]),
                "inside the ghost window opened at line",
                "a spec window inside a ghost window is a fault")
    ok_clean(ghosted(b[:i1] + ["ghost 1 12", "ghost 0 12"] + b[i1:]),
             "its clean twin: a ghost window just before the spec window passes")

    # Clean twins: case_spec_next_row_restates' windows just before the pause.
    for why in ("drop", "retry"):
        v = build(ver=10, sessions=[(15, 3, why)])
        sx = [i for i, l in enumerate(v) if l.startswith("session ")][0]
        s = v[sx].split()
        faults_with(set_spec_flag(v[:sx] + spec_edges(16, s[2], s[3]) + v[sx:]),
                    "between the 'pause' at line",
                    "a window between a '%s' pause and its session is a fault" % why)


def case_spec_flag_and_finish():
    faults_with(set_spec_flag(build()), "says spectated, but there is no 'spec' window",
                "TF_SPEC with no window is a fault")
    faults_with(spectated(flag=False), "does not say spectated",
                "a window with TF_SPEC clear is a fault")
    faults_with([l for l in spectated() if not l.startswith("spec 0 ")],
                "'spec 1' is never closed", "a window left open at the finish is a fault")
    # A live part file copied during a hold ends at its `spec 1`; its flags line
    # is still the `flags 0` reserved at open.
    b = spectated(flag=False)
    f, n = run(b[:spec_line(b, 1) + 1], name="t.part")
    check(not f, "a part file (no end) with an open window: no fault")
    if f:
        print("        %s" % f)
    check(any("still open" in x for x in n), "...and the open window is a note")
    f, _ = run([l for l in b if l.split()[0] not in ("inend", "end")], name="t.part")
    check(not f, "a part file with a closed window and flags 0: no fault")
    if f:
        print("        %s" % f)


def case_spec_unknown_why_is_a_note():
    notes_with(spectated(why="max"), "spec reason 'max' is not one this tool knows",
               "an unknown <why> is a note, not a fault")


def case_spec_below_v9_is_unknown():
    b = build(ver=8)
    ix = [i for i, l in enumerate(b) if l.startswith("in ")][12]
    notes_with(b[:ix] + spec_edges(12, 1, 0) + b[ix:],
               "unknown record 'spec'",
               "a spec record in a v8 file stays an unknown-record note")


# Patch 416.  32 lowercase hex, and deliberately not a round number or a
# repeating pattern: a fixture whose value would still parse after a truncation
# tests the truncation less than it looks like it does.
NONCE = "1bf8d0a2e3c94f6712ab34cd56ef7890"


def case_nonce_header():
    """THE KEY IS ADDITIVE AND ITS SHAPE IS EXACT.  Patch 416.

    The shape arm is the one that matters: the failure this will actually have
    is a half-applied patch writing an empty or truncated key, which reads to
    every later consumer as a run that simply had no nonce."""
    b = insert_before(build(), "begin", "nonce " + NONCE)
    ok_clean(b, "a v9 file with a nonce header key passes with 0 faults")
    _, n = run(b)
    check(not n, "...and emits no notes")
    if n:
        print("        %s" % n)

    # THE CONTROL, and it is the whole reason absence may not be a finding:
    # every recording written before Patch 416 is this file.
    f, n = run(build())
    check(not f and not n, "no nonce key at all is neither a fault nor a note")

    faults_with(insert_before(build(), "begin", "nonce " + NONCE[:31]),
                "not 32 lowercase hex", "a 31-digit nonce is a fault")
    faults_with(insert_before(build(), "begin", "nonce " + NONCE.upper()),
                "not 32 lowercase hex", "an uppercase nonce is a fault")
    faults_with(insert_before(build(), "begin", "nonce"),
                "not 32 lowercase hex", "an empty nonce key is a fault")
    notes_with(insert_before(build(ver=8), "begin", "nonce " + NONCE),
               "is not part of v8",
               "the key in a v8 file is a note: v9 is where it was added")


def case_nonce_record():
    """The resumed session's own nonce, in the body.

    IT SITS INSIDE THE OPEN PAUSE, which for a sample or an `in` row is a fault
    -- those say something moved.  This says a client attached, which is exactly
    what happens between the park and the first move of the new session."""
    b = insert_before(build(**V10), "session", "nonce 3 " + NONCE)
    ok_clean(b, "a body nonce between the pause and its session passes clean")
    _, n = run(b)
    check(not n, "...and emits no notes: a resume re-issues by design")
    if n:
        print("        %s" % n)

    faults_with(insert_before(build(**V10), "session", "nonce 3 " + NONCE[:31]),
                "not 32 lowercase hex", "a short nonce record is a fault")
    faults_with(insert_before(build(**V10), "session", "nonce " + NONCE),
                "takes <mt> <hex32>", "a nonce record without <mt> is a fault")
    faults_with(insert_before(build(**V10), "session", "nonce x " + NONCE),
                "takes <mt> <hex32>", "a non-integer <mt> is a fault")

    # A NOTE AND NOT A FAULT.  The writer only reaches the body form from a
    # resume, so a `nonce` written where no pause is open -- here, after the
    # `session` that closed it -- is a writer that has drifted from its grammar.
    # It is still a file a reader can use, which is what keeps it a note.
    #
    # THE FIRST CUT OF THIS ARM TESTED THE WRONG THING: it put the record in a
    # file with no pause at all, which the v10 gate now makes an unknown record
    # -- so it passed while saying nothing about position.  Review caught the
    # predicate; this catches it staying fixed.
    notes_with(insert_before(build(**V10), "end", "nonce 3 " + NONCE),
               "outside an open 'pause'",
               "a body nonce after its session closed the pause is a note")

    notes_with(insert_before(build(), "end", "nonce 3 " + NONCE),
               "unknown record 'nonce'",
               "a nonce record in a v9 file stays an unknown-record note: the "
               "record can only come from a resume, and a resume makes it v10")


def case_nonce_flag():
    """The answer bit against the number it answers.  ONE WAY ONLY.

    Patch 416.  A file carrying TF_NONCE must state a nonce; a file stating one
    need not carry the bit, and that asymmetry is the whole design -- every
    recording written before 416 states nothing and answers nothing, and a
    client that simply did not answer is not a finding."""
    b = head(build(), "flags", str(131072))
    faults_with(b, "states no nonce",
                "TF_NONCE with no nonce anywhere is a fault")

    ok_clean(insert_before(head(build(), "flags", str(131072)), "begin",
                           "nonce " + NONCE),
             "TF_NONCE with a header nonce passes clean")

    # The bit answered by a BODY record, which is what a resumed session writes.
    ok_clean(insert_before(head(build(**V10), "flags", str(131072 + 16384)),
                           "session", "nonce 3 " + NONCE),
             "TF_NONCE answered by a body nonce alone passes clean")

    # THE CONVERSE, and it may never become a fault.
    ok_clean(insert_before(build(), "begin", "nonce " + NONCE),
             "a nonce with the bit clear is not a finding")

    # The version gate: a v5 file takes its flags from a stat and has no header
    # key to state (a lifted stage, or cl_lobbytime.qc's client-side writer), so
    # the pair cannot be checked there.
    ok_clean(head(build(ver=5), "flags", str(131072)),
             "TF_NONCE in a v5 file is not checked against a key it cannot have")


def case_angle_control():
    """THE PAIR THAT MUST PASS.  Everything below is a mutation of this one, so
    a fault here would make every arm under it unreadable."""
    L = build(sweep=128)                # 0.70 deg a move, 28 deg over the run
    f, n = run(L, view=view_for(L))
    check(not f, "a sidecar built from the recording's own rows passes clean")
    if f:
        print("        %s" % f)
    check(any("0.00% of joined moves" in x for x in n)
          or not any("BLIND" in x for x in n),
          "...and the check says it actually compared something")


def case_angle_blind_is_said_out_loud():
    """A FIXTURE THAT CANNOT FAIL MUST SAY SO.  build()'s default camera never
    turns, and a still run agrees with every other still run to 0.003 deg --
    three files in data/ are in exactly that state.  Reporting that as a pass
    is how a check that discriminates nothing gets believed."""
    L = build()                         # sweep 0: the camera is nailed down
    f, n = run(L, view=view_for(L))
    check(not f, "a still run with a matching sidecar is not a fault")
    check(any("could not discriminate" in x for x in n),
          "...and the checker says the comparison was blind, not that it passed")
    if not any("could not discriminate" in x for x in n):
        print("        notes=%s" % n)


def case_angle_rotated():
    """The whole sidecar turned. 5 deg against a 0.70 deg/move sweep is 7x the
    tick's own travel; 2 deg would be under the cut and is not claimed."""
    L = build(sweep=128)
    f, _ = run(L, view=view_for(L, rot=5.0))
    check(any("does not describe this recording" in x for x in f),
          "a sidecar rotated 5 deg is caught")
    if not any("does not describe this recording" in x for x in f):
        print("        got: %s" % (f or "NO FAULT"))


def case_angle_one_frame_rule():
    """THE HOLE THE SWEEP RULE LEAVES, AND WHAT CLOSES IT.

    Normalising by the tick's own sweep makes a lie smaller than that sweep
    invisible -- 0.5 deg against 0.70 deg a move is 0.71x, and the cut is 3.
    A tick that held exactly one rendered frame does not need the normalisation
    at all: the usercmd was built from that frame, so the two files carry the
    same number and the difference is the print rounding plus the wire quantum.

    THIS ARM USED TO ASSERT THE OPPOSITE and passed after the rule existed,
    because it matched one fault STRING rather than the verdict -- the new rule
    words its finding differently.  Assert the verdict.
    """
    L = build(sweep=128, packets=400)
    clean, _ = run(L, view=view_for(L))
    check(not clean, "400 moves and a matching sidecar is still clean")
    f, _ = run(L, view=view_for(L, rot=0.5))
    check(any("the sidecar is not this recording's" in x for x in f),
          "a 0.5 deg rotation is caught on the ticks that held one frame")
    if not f:
        print("        NO FAULT")


def case_angle_one_frame_rule_reaches_a_still_camera():
    """AND IT WORKS WHERE THE SWEEP RULE CANNOT WORK AT ALL.

    build()'s default camera never turns, which is every 416-419 fixture and
    nearly every run the fleet records.  The sweep rule has nothing to divide
    by and says BLIND; the one-frame rule does not care whether anything moved.
    Before this existed the checker returned early on BLIND and a sidecar from
    another still run at another heading drew no finding of any kind.
    """
    L = build(packets=400)              # sweep 0: the camera is nailed down
    clean, n = run(L, view=view_for(L))
    check(not clean, "a still run with its own sidecar is still not a fault")
    check(any("one-frame rule did" in x for x in n),
          "...and the checker names which rule did the discriminating")
    f, _ = run(L, view=view_for(L, rot=0.5))
    check(any("the sidecar is not this recording's" in x for x in f),
          "a 0.5 deg rotation IS caught on a camera that never turned")
    if not f:
        print("        NO FAULT")


def case_angle_one_frame_rule_needs_v9():
    """AND THE EXEMPTION IS LOAD-BEARING.  Below v9 the `in` row carries
    .v_angle, which SV_RunCmd leaves stale while fixangle is set: ahop_coast's
    saves put honest one-frame ticks 176 deg out.  Applying a 0.05 deg cut to
    those files would fault the corpus, not a cheat."""
    L = build(sweep=128, packets=400, ver=7)
    f, _ = run(L, view=view_for(L, rot=0.5))
    check(not f, "the same rotation is NOT claimed on a pre-v9 recording")
    if f:
        print("        got: %s" % f)


def case_angle_one_frame_rule_says_when_it_is_thin():
    """A FAST CLIENT TAKES THE RULE'S COVERAGE AWAY, and the checker has to say
    that rather than report a quiet pass.  Three frames a tick is what 250 fps
    against a 100 Hz mover looks like; on the real pair it left 5 one-frame
    ticks of 1740, and 5 samples is not a verdict."""
    L = build(sweep=128, packets=400)
    f, n = run(L, view=view_for(L, rot=0.5, dense=3))
    check(not f, "three frames a tick leaves nothing for the one-frame rule "
                 "and it does not guess")
    check(any("the sweep rule alone" in x for x in n),
          "...and it says the pair is being judged by the loose rule only")
    if not any("the sweep rule alone" in x for x in n):
        print("        notes=%s" % n)


def case_angle_splice():
    """A CONTIGUOUS BLOCK FROM SOMEWHERE ELSE, which the fraction rule alone
    misses: --tamper-view put a tenth of surf_kitsune 90 deg out and scored
    9.98%, under a 10% cut.  The run-length rule is what catches it."""
    L = build(sweep=128, packets=900)
    f, _ = run(L, view=view_for(L, rot=90.0, lo=0.3, hi=0.75))
    check(any("does not match its sidecar" in x or
              "does not describe this recording" in x for x in f),
          "a spliced stretch is caught")
    if not f:
        print("        NO FAULT")


def case_angle_no_sidecar_is_silent():
    """A .rec with no .view beside it must say nothing about angles at all."""
    L = build(sweep=128)
    f, n = run(L)
    check(not f and not any("angle" in x for x in n),
          "a recording with no sidecar draws no angle finding")


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
               case_v9_session_is_unknown, case_mc,
               case_spec_clean, case_spec_malformed, case_spec_alternation,
               case_spec_nothing_inside, case_spec_edges_agree,
               case_spec_next_row_restates, case_spec_where, case_spec_flag_and_finish,
               case_spec_unknown_why_is_a_note, case_spec_below_v9_is_unknown,
               case_nonce_header, case_nonce_record, case_nonce_flag,
               case_angle_control, case_angle_blind_is_said_out_loud,
               case_angle_rotated, case_angle_one_frame_rule,
               case_angle_one_frame_rule_reaches_a_still_camera,
               case_angle_one_frame_rule_needs_v9,
               case_angle_one_frame_rule_says_when_it_is_thin,
               case_angle_splice, case_angle_no_sidecar_is_silent):
        # argv: case-name prefixes to run (default all).
        if sys.argv[1:] and not fn.__name__.startswith(tuple(sys.argv[1:])):
            continue
        print("%s:" % fn.__name__)
        fn()
        print("")
    print("%d checks, %d failed" % (CHECKS, len(FAILED)))
    for f in FAILED:
        print("  FAILED: %s" % f)
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
