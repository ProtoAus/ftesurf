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
             "pms": 8, "pes": 9, "portals": 10, "sessions": 11, "clocks": 12}


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


def view_for(lines, rot=0.0, lo=0.0, hi=1.0, dense=1, dense_lo=0.0,
             dense_hi=1.0, nan_at=None, shift=0):
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

    `shift` moves the whole tick column, which is what a PING does to a real
    sidecar: the column is a server stat the client reads out of the last
    snapshot it got, so on a connection it LAGS the recording by the round trip
    and reads LOWER -- a negative shift.  CLAMPED AT ZERO, because that is the
    honest shape: `SV_TimerTicks` never returns a negative, so a lagging client
    pins its clock at 0 until the first post-gate snapshot arrives rather than
    counting backwards.  A sidecar that does count backwards is a forgery and
    reccheck faults it as one.  `dense_lo`/`dense_hi` put the extra frames over a WINDOW rather than the
    whole file, which is the shape a forger wants: leave the honest stretch at
    one frame a tick so the rule arms on it, and pad the stretch you are lying
    about so it is never examined.  `nan_at` puts a NaN in one row's tick
    column -- the same file, one token different.
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
        d = dense if dense_lo * n <= i < dense_hi * n else 1
        for k in range(d):
            col = "nan" if (nan_at is not None and i == nan_at and k == 0) \
                else "%d" % max(0, tk + shift)
            out.append("%.4f %d %s %.2f %.2f 0"
                       % (10.0 + (tk + k / float(d)) * TICK,
                          1000 + tk, col, float(f[7]), yaw))
    return out


def run(lines, name="t.rec", view=None, report=False):
    """-> (faults, notes), optionally with the complete reader report."""
    d = tempfile.mkdtemp(prefix="reccheck_t")
    try:
        p = os.path.join(d, name)
        with open(p, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
        if view is not None:
            with open(os.path.splitext(p)[0] + ".view", "w", encoding="utf-8") as f:
                f.write("\n".join(view) + "\n")
        proc = subprocess.run([sys.executable, "-X", "utf8", RECCHECK, "-v", p],
                              capture_output=True, text=True, encoding="utf-8")
        if (proc.returncode not in (0, 1) or "Traceback" in proc.stderr
                or "file(s) checked" not in proc.stdout):
            raise AssertionError("reader did not complete: %s\n%s" % (proc.stdout, proc.stderr))
        out = proc.stdout
        faults = [l.strip()[2:] for l in out.splitlines()
                  if l.strip().startswith("! ")]
        notes = [l.strip()[2:] for l in out.splitlines()
                 if l.strip().startswith("- ")]
        return (faults, notes, out) if report else (faults, notes)
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
            (row(build(), fl=16), "is outside 0..15", "'in' fl 16"),
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
    ok_clean(row(build(), fl=8), "'in' fl 8 (a later part of a split usercmd, Patch 893) passes")


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


def over_bound(lines, val=5000):
    """-> the same lines with the first `in` row's move triple over any bound.

    THE ROW IS EDITED AND NOT APPENDED because the check is about the rows the
    file already carries: `in <pk> <mt> <carry> <fwd side up> ...`, so columns 4
    to 6 are the move triple.  A fixture that appended a row of its own would
    also have to model the packet ordinal and the movetick, and would then be
    testing the builder's arithmetic rather than the cross-check."""
    out, done = [], False
    for l in lines:
        t = l.split()
        if not done and t and t[0] == "in":
            t[4] = t[5] = t[6] = str(val)
            l = " ".join(t)
            done = True
        out.append(l)
    return out


def case_movebnd():
    """THE BOUND, THE ROWS AND THE BIT HAVE TO AGREE.  Patch 493.

    Three properties, and the arms below are in that order because each one is
    what makes the next safe:

    ABSENCE ABSTAINS.  No `movebnd` key means no bound was applied -- the server
    runs `run_movebound 0`, or its progs predate the check -- and then NEITHER
    direction may run.  That is not a hole: this tree's own Patch 358 fixtures
    carry `side=2325 / fwd=-1067` and no TF_MOVEOOR, because a harness drove
    them, and a reader that could not tell "no rule" from "no such rule yet"
    would fault honest files for predating the rule.

    THE STRONG DIRECTION IS A FAULT.  The rows and the marker are written by the
    same command, so a file holding rows over its own stated bound with the bit
    clear was either written by a recorder that stopped checking or edited by
    somebody who did not know the values are in the trace beside the bit.

    THE WEAK DIRECTION IS A NOTE.  Two honest writers produce a bit with no row
    over it -- SV_TimerInFrame stops writing rows at its line cap while
    SV_MoveBoundFrame keeps counting commands, and a `pause` epoch can hold the
    rows a marker was set beside -- and this tool can see neither.  A forger also
    has no reason to set a marker that demotes nothing."""
    # THE CONTROL, and it is every recording written before Patch 493.
    f, n = run(build())
    check(not f and not n, "no movebnd key at all is neither a fault nor a note")

    ok_clean(insert_before(build(), "begin", "movebnd 2000"),
             "a v9 file stating movebnd, with no row over it, passes clean")

    b = over_bound(insert_before(build(), "begin", "movebnd 2000"))
    faults_with(b, "does not say TF_MOVEOOR",
                "a row over the stated bound with the bit clear is a fault")
    ok_clean(head(b, "flags", str(262144)),
             "...and the same file with TF_MOVEOOR set passes clean")

    # The row over the bound is not judged at all when the file states no bound.
    f, n = run(over_bound(build()))
    check(not f, "an over-bound row in a file with no movebnd key is not judged")

    notes_with(head(insert_before(build(), "begin", "movebnd 2000"),
                    "flags", str(262144)),
               "line cap",
               "the bit with no row over the bound is a note that names the cap")

    # THE GATE THAT COST A RUN TO FIND.  A Multi-Session park and a save-state
    # prefix are CLOSED files whose header flags word is still the 0 written at
    # open: SV_RecFlagLine reserves a fixed width and only SV_RecClose /
    # SV_RecKeepEvidence seek back to it.  So a marker set mid-run is not in them,
    # and this arm's own first file was exactly that -- 284 rows over the stated
    # bound beside `flags 0`, which the ungated check read as tampering.
    # `run.rec` is what is_prefix() recognises, and the file has no `end`, which is
    # the same gate every other header-bit cross-check in reccheck sits behind.
    b = over_bound(insert_before(build(), "begin", "movebnd 2000"))
    b = [l for l in b if not l.startswith("end ")]
    f, n = run(b, name="run.rec")
    check(not any("TF_MOVEOOR" in x for x in f),
          "an unclosed file (a park, a save-state prefix) is not judged against "
          "its flags word at all -- it still holds the 0 written at open")
    f, n = run(b, name="t.rec")
    check(any("no 'end' record" in x for x in f),
          "...and the same rows in a file that is not a prefix FAULT on the "
          "missing trailer, so the gate is about the flags word and not a blanket "
          "exemption (%d fault(s))" % len(f))

    # SHAPE.  A non-number, and a 0 -- the writer states a bound only when it
    # applied one, so a stated 0 is a writer that drifted from its own grammar.
    faults_with(insert_before(build(), "begin", "movebnd x"),
                "not a number", "a non-numeric movebnd is a fault")
    faults_with(insert_before(build(), "begin", "movebnd 0"),
                "should be absent", "movebnd 0 is a fault: 0 means none applied")
    notes_with(insert_before(build(ver=8), "begin", "movebnd 2000"),
               "is not part of v8",
               "the key in a v8 file is a note: v9 is where it was added")


def case_profile_verdict():
    """Patch 840: the header's `inprof` and the body's `prof` name the profile
    verdict that SV_TimerProfile acts on in the same packet, so a known verdict
    that is not ok beside a clear TF_NOPROFILE is a fault (after `end`); the
    converse is a note (a loaded save carries the bit), and so is anything this
    tool does not know -- a later writer's word, a NaN the player typed."""
    ok_clean(insert_before(build(), "begin", "inprof ok 15 1 0 0 1"),
             "an ok start verdict with the bit clear passes clean")
    b = insert_before(build(), "begin", "inprof m_accel 15 1 0 1 1")
    faults_with(b, "does not say TF_NOPROFILE",
                "a bad start verdict with the bit clear is a fault")
    ok_clean(head(b, "flags", str(2048)),
             "...and the same file with TF_NOPROFILE passes clean")
    b = insert_before(insert_before(build(), "begin", "inprof ok 15 1 0 0 1"),
                      "inend", "prof changed")
    faults_with(b, "does not say TF_NOPROFILE",
                "a bad finish verdict with the bit clear is a fault")
    ok_clean(head(b, "flags", str(2048)),
             "...and with the bit set passes clean")
    notes_with(head(insert_before(build(), "begin", "inprof ok 15 1 0 0 1"),
                    "flags", str(2048)),
               "loaded save",
               "the bit with every verdict ok is a note, not a fault")
    notes_with(insert_before(build(), "begin", "inprof bogus 15 1 0 0 1"),
               "not one this tool knows", "an unknown start verdict is a note")
    notes_with(insert_before(build(), "inend", "prof bogus"),
               "not one this tool knows", "an unknown finish verdict is a note")
    ok_clean(head(insert_before(build(), "begin", "inprof m_accel 15 1 0 nan 1"),
                  "flags", str(2048)),
             "a NaN in the report is not a fault of its own")
    notes_with(insert_before(build(), "begin", "inprof ok 15 1 0"),
               "fields after its verdict", "a short inprof is a note")
    faults_with(insert_before(build(), "inend", "prof"),
                "'prof' takes one verdict word", "a bare prof is a fault")
    b = insert_before(build(), "begin", "inprof m_accel 15 1 0 1 1")
    b = [l for l in b if not l.startswith("end ")]
    f, n = run(b, name="run.rec")
    check(not any("TF_NOPROFILE" in x for x in f),
          "an unclosed file is not judged against its flags word")


def clk(behind, wall=60.0, stalls=0, cred=0.0, debt=None, bound=1):
    """A `clk` line.  `debt` defaults to `behind`."""
    if debt is None:
        debt = behind
    return "clk %g 0.2 0.5 %.3f %d %.3f %.3f %.3f" % (bound, wall, stalls, cred, debt, behind)


def case_slow_clock():
    """Patch 840: the finish's `clk` states its bound and the measure (summed
    debt rises), so the bit is judged from the file alone: clearly behind with
    TF_SLOWCLOCK clear is a fault, clearly not with it set is a note, bound 0
    judges nothing.  What the measure means is the writer's (SV_ClockFrame)."""
    slow = clk(48.8, 99.0)
    honest = clk(0.0, 9.6, 1, 0.5, -0.32)
    ok_clean(insert_before(build(), "inend", honest),
             "an honest clk (one stall, surplus after it) with the bit clear passes clean")
    b = insert_before(build(), "inend", slow)
    faults_with(b, "does not say TF_SLOWCLOCK", "48.8 s behind with the bit clear is a fault")
    ok_clean(head(b, "flags", str(524288)), "...and with TF_SLOWCLOCK set passes clean")
    notes_with(head(insert_before(build(), "inend", honest), "flags", str(524288)),
               "under its own bound", "the bit over an honest clk is a note")
    ok_clean(insert_before(build(), "inend", clk(48.8, 99.0, bound=0)),
             "bound 0 (off) judges nothing")
    faults_with(insert_before(build(), "inend", clk(1.3, 300.0, debt=0.0)),
                "does not say TF_SLOWCLOCK",
                "1.3 s behind after the debt was repaid (debt 0) is still slow")
    ok_clean(insert_before(build(), "inend", clk(1.0)),
             "exactly at the bound is not judged slow with the bit clear")
    ok_clean(head(insert_before(build(), "inend", clk(1.0)), "flags", str(524288)),
             "...nor judged honest with the bit set")
    ok_clean(insert_before(build(), "inend", "clk 1 0.2 0.5 9 1 0.5 -0.4 0"),
             "a negative debt (surplus) is legal")
    faults_with(insert_before(build(), "inend", "clk 1 0.2 0.5 99 0 0"),
                "'clk' takes 8", "a short clk is a fault")
    faults_with(insert_before(build(), "inend", "clk 1 0.2 0.5 -9 0 0 0 0"),
                "'clk' takes 8", "a negative wall is a fault")
    faults_with(insert_before(build(), "inend", "clk 1 0.2 0.5 9 0 0 nan 0"),
                "'clk' takes 8", "a NaN clk field is a fault")
    f, n, out = run(insert_before(build(), "inend", slow), report=True)
    check("clk" in out and "behind 48.800" in out, "-v prints the clk line with how far behind")
    b = [l for l in insert_before(build(), "inend", slow) if not l.startswith("end ")]
    f, n = run(b, name="run.rec")
    check(not any("TF_SLOWCLOCK" in x for x in f),
          "an unclosed file is not judged against its flags word")


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
    check(any("down to a flat" in x for x in n),
          "...and the checker says what the sweep rule is reduced to (a flat "
          "3 deg cut), not that it passed")
    if not any("down to a flat" in x for x in n):
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


def case_split_part_rows_are_not_joined():
    """Patch 893: the server runs a usercmd of several ticks one tick per part, and a later part's
    row (fl 8) carries the COMMAND's angles at a tick where the client drew a later frame.  The
    one-frame rule must skip those rows -- and the same rows without the bit must fault, or the bit
    is not what passes them."""
    L = build(sweep=128, packets=400)
    view = view_for(L)

    def split(bit, repeat=True):
        # A later part repeats its usercmd: packet, moves, angles and buttons; mt and carry move on.
        out, prev, k = [], None, 0
        for l in L:
            if l.startswith("in "):
                f = l.split()
                if prev is not None:
                    k += 1
                    if k % 2 == 0:
                        if repeat:
                            f[1] = prev[1]
                            f[4:11] = prev[4:11]
                        else:
                            f[7], f[8] = prev[7], prev[8]
                        f[11] = str(int(f[11]) | bit)
                        l = " ".join(f)
                prev = f
            out.append(l)
        return out

    f, n = run(split(8), view=view)
    check(not any("not this recording" in x or "does not describe" in x for x in f),
          "a later part's row (fl 8) with the command's angles is not joined to its tick's frame")
    if f:
        print("        %s" % f)
    check(not any("do not repeat" in x for x in n), "...and a row that repeats its command draws no note")
    f, n = run(split(8, repeat=False), view=view)
    check(any("do not repeat" in x for x in n),
          "an fl 8 row whose packet, moves or buttons differ from the row before is noted")
    f, _ = run(split(0), view=view)
    check(any("not this recording" in x or "does not describe" in x for x in f),
          "...and the same rows without fl 8 are a fault (the control)")
    f, _ = run(insert_before(build(), "inend", "in 0 0 0 0 0 0 0 0 0 0 16"))
    check(any("fl 16 is outside 0..15" in x for x in f), "fl 16 is still outside the grammar")


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
    check(any("one-frame rule is what discriminated" in x for x in n),
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
    check(any("what is left is the sweep rule" in x for x in n),
          "...and it says the pair is being judged by the loose rule only")
    if not any("what is left is the sweep rule" in x for x in n):
        print("        notes=%s" % n)


def case_angle_one_frame_rule_cannot_be_armed_on_a_slice():
    """THE DISARM A REVIEWER FOUND, AND IT IS THE INTERESTING ONE.

    `len(solo)` counts ticks that held one frame IN THE .view, and the .view is
    the attacker's file.  So a count alone is a number they set: keep enough
    honest one-frame ticks to satisfy it, put two frames on every tick you lie
    about, and the rule arms, looks only at the honest ones, and prints the
    cleanest line it can produce while most of the sidecar is never examined.
    Measured before the fix: 150 solo of 334 joined, the other 184 two degrees
    out, verdict `ok`, no fault, NO NOTE.  The fix is that coverage is a
    fraction and the fraction arms the rule.
    """
    L = build(sweep=128, packets=400)
    f, n = run(L, view=view_for(L, rot=2.0, lo=0.3, dense=2, dense_lo=0.3))
    check(not any("the sidecar is not this recording's" in x for x in f),
          "the padded ticks are still not examined -- that part is physics")
    check(any("held one rendered frame" in x and "under the" in x
              and "it needs" in x for x in n),
          "...but the pair no longer passes quietly: the coverage is said, and "
          "the note names the gate that bit")
    if not any("it needs" in x for x in n):
        print("        notes=%s" % n)
    # CONTROL: the same lie WITHOUT the padding is caught, so the arm is about
    # the padding and not about 2 degrees being too small to see.
    f2, _ = run(L, view=view_for(L, rot=2.0, lo=0.45))
    check(any("the sidecar is not this recording's" in x for x in f2),
          "CONTROL: the same 2 deg lie with one frame a tick is caught")


def case_angle_nan_is_a_fault_not_a_skip():
    """NOT COMPARABLE IS NOT A PASS.  `nan` parses as a float, survives the
    numeric check, and then raises inside the tick join -- which rcptcheck
    catches as "the cross-check did not run", leaving the receipt VALID and the
    review page with no angle verdict at all.  One token, in a file the client
    writes and signs, suppressing the whole comparison."""
    L = build(sweep=128, packets=400)
    f, _ = run(L, view=view_for(L, rot=5.0, nan_at=3))
    check(any("not a finite number" in x for x in f),
          "a NaN in the tick column is a fault of its own")
    check(any("does not describe this recording" in x
              or "the sidecar is not this recording's" in x for x in f),
          "...and the rest of the sidecar is still compared, not abandoned")
    if not f:
        print("        NO FAULT")


def with_ghost(lines, a, b):
    """Declare a ghost window over run ticks [a, b] in an existing fixture.

    A HELPER RATHER THAN A build() ARGUMENT because the two records and the
    flag bit are all it takes, and threading a parameter through the builder
    for one arm is how build() got fifteen of them.
    """
    out = []
    for l in lines:
        if l.startswith("flags "):
            out.append("flags %d" % (int(l.split()[1]) | 64))      # TF_GHOST
            continue
        if l.startswith("end "):
            out.append("ghost 1 %d" % a)
            out.append("ghost 0 %d" % b)
        out.append(l)
    return out


def view_for_samples(lines, rot=0.0):
    """A sidecar built from the SAMPLE rows, for a file with no `in` records.

    check_rec falls back to that stream whenever a recording carries no inputs,
    and the fallback's angles are .v_angle at every version -- which is the
    thing the tight rule must not be pointed at.
    """
    out = ["FTESURF-VIEW 2", "map bhop_eazy", "hid 1", "begin"]
    for l in lines:
        tok = l.split()
        if len(tok) < 9:
            continue
        try:
            st = float(tok[0])
        except ValueError:
            continue        # a record line, not a sample
        if st < 0:
            continue
        tk = int(round(st / TICK))
        yaw = ((float(tok[8]) + rot) + 180.0) % 360.0 - 180.0
        out.append("%.4f %d %d %.2f %.2f 0"
                   % (10.0 + st, 1000 + tk, tk, float(tok[7]), yaw))
    return out


def case_angle_omission_does_not_read_as_cover():
    """THE CHEAPER DISARM, AND THE ONE A COUNT OR A RATIO OVER `joined` MISSES.

    Coverage was `len(solo) / joined` and `joined` only counts moves the
    sidecar put a frame on -- so DELETING frames shrank both sides and the
    ratio stayed at 100%.  Measured by a reviewer on p417/s with the middle 40%
    of the sidecar removed: `399 of 399 joined ticks held one frame (100%)`,
    verdict ok, no note, for a file describing 60% of the run.  The denominator
    is now the RECORDING's move count, which the client does not write.
    """
    L = build(sweep=128, packets=400)
    full = view_for(L)
    head, body = full[:4], full[4:]
    thin = head + body[:int(0.45 * len(body))]      # the rest simply not there
    f, n = run(L, view=thin)
    check(not any("the sidecar is not this recording's" in x for x in f),
          "the missing stretch is not examined -- that part is physics")
    check(any("it needs" in x for x in n),
          "...but dropping frames no longer reads as full cover")
    if not any("it needs" in x for x in n):
        print("        notes=%s" % n)


def case_angle_tight_rule_abstains_where_the_epoch_moves():
    """A RESUME, A RETRY, A PAUSE OR A SESSION MOVES THE TICK EPOCH.

    The join is `view.ticks == in.mt - instart`, but the sidecar's column is
    STAT_FS_TIMERTICKS, which subtracts frozen ticks and carries restored ones
    (SV_TickCounted).  After one of those records the header's `instart` no
    longer describes the epoch, and a mis-joined row is an arbitrary angle
    difference -- which the loose rule survives and a 0.05 deg rule does not.
    NOT MEASURED ON A REAL PAIR: no v9 file in the corpus has one, so this
    abstains on a mechanism read out of the recorder rather than on data.
    """
    L = build(sweep=128, packets=400)
    good, _ = run(L, view=view_for(L, rot=0.5))
    check(any("the sidecar is not this recording's" in x for x in good),
          "CONTROL: without a resume the 0.5 deg lie is caught")
    R = [l for l in L]
    R.insert(next(i for i, l in enumerate(R) if l.startswith("in ")),
             "resume 20260101-000000-0")
    f, n = run(R, view=view_for(R, rot=0.5))
    check(not any("the sidecar is not this recording's" in x for x in f),
          "a recording carrying a resume is not judged by the tight rule")
    check(any("resume" in x and "tight" in x for x in n),
          "...and the note says that is why")
    if not any("resume" in x and "tight" in x for x in n):
        print("        notes=%s" % n)


def case_angle_tight_rule_is_keyed_on_the_source_not_the_version():
    """THE EXEMPTION HAS TO FOLLOW THE ANGLES, NOT THE VERSION NUMBER.

    check_rec falls back to the `samples` stream whenever a file carries no
    `in` rows, and SV_RecOpen allows that at ANY version -- so a v9 file of
    that shape would have armed a 0.05 deg cut against .v_angle, which
    SV_RunCmd leaves stale under fixangle.  Measured by a reviewer with only
    the version gate lifted: 11 honest pre-v9 pairs fault, worst 176.19 deg.
    """
    L = build(sweep=128, packets=400, inputs=False)
    clean, _ = run(L, view=view_for_samples(L))
    check(not clean, "CONTROL: the samples-built sidecar pairs cleanly")
    if clean:
        print("        got: %s" % clean)
    f, n = run(L, view=view_for_samples(L, rot=0.5))
    check(not any("the sidecar is not this recording's" in x for x in f),
          "a v9 file with no `in` rows is not judged by the tight rule")
    check(any("samples" in x for x in n),
          "...and the note names the stream it fell back to")
    if not any("samples" in x for x in n):
        print("        notes=%s  faults=%s" % (n, f))


def run_inproc(lines, view):
    """The same pair, checked IN THIS PROCESS, so a case can reach into
    reccheck's constants.  run() shells out, which is right for everything else
    -- it tests the tool a user invokes -- but it means a monkeypatch here does
    nothing, and the first cut of the control below `passed` while measuring
    the ordinary behaviour it was supposed to be the control for.
    """
    import reccheck as rc
    d = tempfile.mkdtemp(prefix="reccheck_i")
    try:
        p = os.path.join(d, "t.rec")
        with open(p, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
        v = os.path.splitext(p)[0] + ".view"
        with open(v, "w", encoding="utf-8") as f:
            f.write("\n".join(view) + "\n")
        return rc.check_view(v, rc.check_rec(p)).faults
    finally:
        shutil.rmtree(d, ignore_errors=True)


def case_angle_lag_is_recovered():
    """THE CHECK DID NOT WORK OVER A NETWORK, AND EVERY LOBBY CLIENT IS REMOTE.

    The sidecar's join column is STAT_FS_TIMERTICKS -- a server stat read out
    of the last snapshot -- while the recording stamps `in.mt` when the server
    ran the move, so the two are separated by the round trip.  Measured with
    `cl_delay_packets 30` against a control run minutes apart on the same
    route: an HONEST pair read 30.2 deg max, 49.6% of one-frame ticks past cut
    and 19.9% of joined moves past the sweep cut, BOTH RULES FAULTING A CLEAN
    RUN.  The control read 0.008 deg.
    """
    L = build(sweep=128, packets=400)
    f, _ = run(L, view=view_for(L, shift=-3))
    check(not f, "a sidecar three ticks behind the recording is not a fault")
    if f:
        print("        got: %s" % f)
    # CONTROL: the shift has to be REAL, or the arm is about nothing.  Without
    # the search this same pair faults.
    L2 = build(sweep=128, packets=400)
    import reccheck as _rc
    keep = _rc.ANG_LAG_FLOOR
    _rc.ANG_LAG_FLOOR = -1.0            # no offset can ever be accepted
    try:
        f2 = run_inproc(L2, view_for(L2, shift=-3))
    finally:
        _rc.ANG_LAG_FLOOR = keep
    check(any("the sidecar is not this recording's" in x for x in f2),
          "CONTROL: with the search switched off the same pair faults")
    check(not run_inproc(L2, view_for(L2, shift=-3)),
          "...and with it back on, in the same process, it does not")


def case_angle_lag_has_no_window():
    """THE CLIFF A REVIEWER MEASURED, REMOVED RATHER THAN MOVED.

    The offset used to be searched over a fixed window, so at 12 ticks of lag
    an honest pair was clean and at 13 it drew both faults -- and widening the
    window only moved the edge.  Worse, the score is a delta function (0.00% at
    the true offset, ~50% one tick away), so a coarse scan over a wider range
    steps straight over it.  The offset is read off the files now: every frame
    is indexed by its printed angles and the moves vote.  There is no range.
    """
    L = build(sweep=128, packets=1200)
    for shift in (13, 40, 120):
        f, _ = run(L, view=view_for(L, shift=-shift))
        check(not f, "a sidecar %d ticks behind the recording is not a fault"
                     % shift)
        if f:
            print("        got: %s" % f[:1])


def case_angle_lag_does_not_rescue_a_lie():
    """AND THE SEARCH MUST NOT BE A SECOND CHANCE.  Fifteen offsets is fifteen
    opportunities to fit, so the arm that matters is the one where none of them
    helps: a rotated sidecar is wrong at every offset and has to stay wrong."""
    L = build(sweep=128, packets=400)
    f, _ = run(L, view=view_for(L, rot=0.5, shift=-3))
    check(any("the sidecar is not this recording's" in x for x in f),
          "a rotated sidecar is not rescued by the offset search")
    if not f:
        print("        NO FAULT")


def case_angle_lag_is_not_invented_on_a_still_camera():
    """A TIE IS NOT A MEASUREMENT.  A camera that never turned agrees equally
    well at every offset -- the same degeneracy that made a corpus of
    nailed-down fixtures agree with each other's sidecars -- so the search has
    to come back with zero rather than pick one and call it a ping."""
    L = build(packets=400)                  # sweep 0
    f, n = run(L, view=view_for(L))
    check(not f, "a still pair is still not a fault")
    check(not any("ticks (" in x and "next best offset" in x for x in n),
          "...and no lag is claimed for it")


def case_angle_ghost_is_not_a_fault():
    """THE FALSE FAULT A REVIEWER FOUND BEFORE THIS SHIPPED ANYWHERE.

    Across a ghost the two files disagree BY DESIGN and the sidecar's own
    writer says so (cl_replay.qc:1730): Ghost_InputFrame pins input_angles to
    the body's frozen aim while Rec_ViewSample keeps writing the flying camera.
    TF_GHOST is not a taint -- reccheck.py:336, "a ghosted run is still a run"
    -- so without an exemption a 0.6 s detach in a 60 s run is a FAULT on an
    honest recording, which is the patch being worse than no patch.

    The window comes from the .rec and never from the .view: a forger who could
    declare his own would exempt the whole run with two lines.
    """
    L = with_ghost(build(packets=400), 120, 260)
    f, _ = run(L, view=view_for(L, rot=90.0, lo=0.30, hi=0.65))
    check(not f, "a sidecar that disagrees only inside a declared ghost window "
                 "draws no fault")
    if f:
        print("        got: %s" % f)
    # CONTROL: the same disagreement one window over IS a fault, so the arm is
    # about the ghost and not about the rotation being invisible.
    f2, _ = run(L, view=view_for(L, rot=90.0, lo=0.70, hi=0.95))
    check(any("the sidecar is not this recording's" in x for x in f2),
          "CONTROL: the same 90 deg lie outside the window is still caught")
    # AND THE .view CANNOT DECLARE ONE.  Same lie, no ghost in the recording.
    L2 = build(packets=400)
    f3, _ = run(L2, view=["FTESURF-VIEW 2", "map bhop_eazy", "hid 1", "begin",
                          "ghost 1 0.0 120", "ghost 0 0.0 260"]
                + view_for(L2, rot=90.0, lo=0.30, hi=0.65)[4:])
    check(any("the sidecar is not this recording's" in x for x in f3),
          "a ghost the SIDECAR declares exempts nothing")


def case_angle_negative_run_clock_is_a_fault():
    """`SV_TimerTicks` RETURNS A COUNT OR ZERO, NEVER A NEGATIVE, so a sidecar
    whose run clock counts backwards did not get it from the server.  It is the
    cheapest form of the head amnesty: put the rows you lied about at a tick
    below the start and they fall out of range, taking the lie with them."""
    L = build(sweep=128, packets=400)
    f, _ = run(L, view=view_for(L, rot=90.0, lo=0.0, hi=0.05, shift=-12))
    check(not any("never negative" in x for x in f),
          "CONTROL: a sidecar clamped at zero, as a real one is, draws no "
          "negative-clock fault")
    v = view_for(L, rot=90.0, lo=0.0, hi=0.05)
    head, body = v[:4], v[4:]
    body = [" ".join([t[0], t[1], "-3"] + t[3:]) for t in (l.split() for l in body)]
    f2, _ = run(L, view=head + body)
    check(any("never negative" in x for x in f2),
          "a negative run clock in the sidecar is a fault")
    if not any("never negative" in x for x in f2):
        print("        got: %s" % f2)


def case_angle_head_amnesty_costs_coverage():
    """THE AMNESTY A REVIEWER FOUND, REDUCED TO WHAT IS INTRINSIC.

    Deciding `tk < 0` on the SHIFTED tick dropped the moves a forger had buried
    from the comparison AND from the coverage denominator, so a 90 degree lie
    over the first 2% of a run went from a fault at 2.10% past cut to `ok,
    0.00%, worst 0.0050` -- no numeric trace anywhere.  The range is decided on
    the recording's own tick now.  The moves still cannot be CHECKED, because
    the sidecar does not describe them, but they are counted.
    """
    L = build(sweep=128, packets=400)
    clean, n = run(L, view=view_for(L, shift=-12))
    check(not clean, "an honest sidecar 12 ticks behind is still not a fault")
    # The moves the shift hides are UNCOVERED, not absent: they stay in the
    # count the coverage figure divides by.
    import reccheck as _rc
    d = tempfile.mkdtemp(prefix="reccheck_a")
    try:
        p = os.path.join(d, "t.rec")
        open(p, "w", encoding="utf-8").write("\n".join(L) + "\n")
        vp = os.path.splitext(p)[0] + ".view"
        open(vp, "w", encoding="utf-8").write(
            "\n".join(view_for(L, shift=-12)) + "\n")
        info = _rc.check_view(vp, _rc.check_rec(p)).info
    finally:
        shutil.rmtree(d, ignore_errors=True)
    check("did not" in info.get("angle_joined", ""),
          "the buried moves are reported as uncovered rather than vanishing")
    check("no frame under it" in info.get("angle_lag", ""),
          "...and the offset, and what it hides, is on the report")
    if "no frame under it" not in info.get("angle_lag", ""):
        print("        angle_lag=%r" % info.get("angle_lag"))


def case_angle_lag_is_not_claimed_when_the_winner_is_bad():
    """A RATIO HAS NO OPINION ABOUT THE WINNER BEING BAD.  At a wrong offset
    the runner-up is naturally 70-85%, so a 4x margin is nearly free, and the
    corpus accepted offsets whose own score was 15-20% past cut.  The winner has
    to align, not merely align least badly."""
    L = build(sweep=128, packets=400)
    f, n = run(L, view=view_for(L, rot=90.0, lo=0.25, hi=0.9, shift=-3))
    check(not any("-3 ticks" in x or "+3 ticks" in x for x in n),
          "no offset is claimed for a sidecar that is wrong at all of them")
    check(any("lines these two files up" in x for x in n),
          "...and the checker says the search found nothing, not nothing at all")
    if not any("lines these two files up" in x for x in n):
        print("        notes=%s" % n)


def retry_clock_pair(retries=2, resets=2):
    """Server retry markers; client-local clocks reset while run ticks increase."""
    base = head(build(sweep=128), "flags", 1)
    out, pending = [], [2 + 2 * n for n in range(retries)]
    for line in base:
        if line.startswith("in "):
            tick = int(line.split()[2]) - HORIZON
            while pending and tick >= pending[0]:
                out.append("retry %d" % pending.pop(0))
        out.append(line)
    assert not pending
    view = ["FTESURF-VIEW 2", "map bhop_eazy", "hid 1", "begin",
            "10.0 100 0 0 0 0", "11.0 101 1 0 0 0"]
    for n in range(resets):
        view += ["1.0 1 %d 0 0 0" % (2 + 2 * n),
                 "2.0 2 %d 0 0 0" % (3 + 2 * n)]
    return out, view


def cold_clock_pair(why="load", resets=2, restore=True):
    lines = build(ver=10, sessions=((10, 3, why), (20, 3, why)))
    out = []
    for line in lines:
        out.append(line)
        if restore and line.startswith("pause "):
            ticks = line.split()[3]
            out.append("retry %s" % ticks if why == "retry" else "resume 1 %s" % ticks)
    boundaries = [int(float(l.split()[4])) for l in lines if l.startswith("session ")]
    _unused, view = retry_clock_pair(0, resets)
    ticks = [0, boundaries[0] - 1]
    for n in range(resets):
        t = boundaries[n] if n < len(boundaries) else boundaries[-1] + 2 * (n - 1)
        ticks += [t, t + 1]
    for i, tick in enumerate(ticks):
        f = view[i + 4].split(); f[2] = str(tick); view[i + 4] = " ".join(f)
    return out, view


def case_view_resume_slot_history():
    base, view = retry_clock_pair()
    for slot, valid in (("1", True), ("0", True), ("999", True),
                        ("bad", False), ("1000", False), ("-1", False),
                        ("1.0", False), ("\u0662", False), ("1" * 129, False)):
        lines = ["resume %s %s" % (slot, l.split()[1]) if l.startswith("retry ") else l
                 for l in base]
        f, _notes, report = run(lines, view=view, report=True)
        acted = (not f and "angle_rule     unavailable" in report) if valid else any(
            "goes backwards" in x for x in f)
        check(acted, "resume slot %s: valid history only grants reset allowance" % ascii(slot[:20]))


def case_view_restore_history():
    for why, restore in (("load", True), ("retry", True), ("drop", False)):
        L, view = cold_clock_pair(why, restore=restore)
        f, _ = run(L)
        check(not f, "CONTROL: %s session history parses without faults" % why)
        f, _notes, report = run(L, view=view, report=True)
        check(not f and "angle_rule     unavailable" in report,
              "%s client restarts stay unavailable, not a clock conviction" % why)
        L, view = cold_clock_pair(why, resets=3, restore=restore)
        f, _ = run(L, view=view)
        check(any("goes backwards" in x for x in f),
              "%s restore + session is one boundary, not two reset permissions" % why)


def case_view_retry_history():
    L, view = retry_clock_pair()
    f, _ = run(L)
    check(not f, "CONTROL: two authoritative retry markers parse without faults")
    f, _notes, report = run(L, view=view, report=True)
    check(not f and "angle_rule     unavailable" in report,
          "two declared retries permit two client-local resets, never an angle OK")
    for retries, resets in ((0, 2), (1, 2), (2, 3)):
        L, view = retry_clock_pair(retries, resets)
        f, _ = run(L, view=view)
        check(any("goes backwards" in x for x in f),
              "%d retries cannot authorize %d client-local resets" % (retries, resets))
    L, view = retry_clock_pair()
    f, _ = run(view, name="t.view")
    check(any("goes backwards" in x for x in f),
          "a standalone sidecar has no authority for a second reset")
    for token in ("--1", "\u0662", "2.5", "nan", "1" * 129):
        bad = ["retry %s" % token if l.startswith("retry ") else l for l in L]
        f, _ = run(bad, view=view)
        check(any("goes backwards" in x for x in f),
              "invalid server marker %s cannot grant additional resets" % ascii(token[:20]))


def held_clock_pair(holds=((150, 73), (350, 137)), sessions=()):
    """Independent run-clock view; only raw server counters acquire held time."""
    base = head(build(sweep=128, packets=600, ver=10 if sessions else 9,
                      sessions=sessions), "flags", 1)
    view = view_for(base)
    out, n, frozen = [], 0, 0
    for line in base:
        f = line.split()
        if f[0] == "session":
            frozen = 0
        if f[0] == "begin":
            out.append("holdclock 1")
        if f[0] == "in":
            for at, gap in holds:
                if n == at:
                    frozen += gap
                    out.append("hold %d %d" % (int(f[2]) + frozen, frozen))
            f[2] = str(int(f[2]) + frozen)
            line = " ".join(f)
            n += 1
        elif f[0] in ("inend", "pause"):
            f[1] = str(int(f[1]) + frozen)
            line = " ".join(f)
        out.append(line)
    return out, view


def view_validation_cases():
    """Independent sidecar faults while the unchanged angle join still ACTS."""
    lines, good = held_clock_pair(holds=((0, 73),))
    yield "valid", lines, good, ""
    base = head(build(sweep=128, packets=600), "flags", 1)
    rotated = view_for(base, rot=5)
    yield "rotation", lines, rotated, "angular"
    yield "rotation-ghost", lines, rotated + ["ghost 2 10 0"] * 30, "ghost' state"
    end = int(next(line.split()[1] for line in lines if line.startswith("end ")))
    for label, reason in (("nonfinite", "finite number"), ("width", "columns"),
                          ("negative-tick", "never negative"), ("past-end", "recording ends"),
                          ("run-clock", "run clock goes backwards"),
                          ("local-resets", "cltime goes backwards"),
                          ("ghost", "ghost' state")):
        view = good[:]
        if label == "ghost":
            view.append("ghost 2 10 0")
        elif label == "local-resets":
            for i in range(4, len(view)):
                fields = view[i].split()
                fields[0] = "%.5f" % (float(fields[0]) - (100 if i >= 150 else 0)
                                      - (100 if i >= 350 else 0))
                view[i] = " ".join(fields)
        else:
            i = len(view) - 1 if label in ("past-end", "run-clock") else 4
            fields = view[i].split()
            if label == "nonfinite":
                fields[3] = "nan"
            elif label == "width":
                fields = fields[:-1]
            elif label == "negative-tick":
                fields[2] = "-1"
            elif label == "past-end":
                fields[2] = str(end + 1)
            elif label == "run-clock":
                fields[2] = "0"
            view[i] = " ".join(fields)
        yield label, lines, view, reason


def case_angle_hold_clock():
    L, view = held_clock_pair()
    f, n, report = run(L, view=view, report=True)
    check(not f, "two held intervals join the independent run-clock sidecar")
    check("angle_rule     tight" in report,
          "held-clock correction retains an acting one-frame comparison")
    if f:
        print("        %s" % f)
    missing = [l for l in L if not l.startswith("hold ")]
    f, _ = run(missing, view=view)
    check(any("sidecar" in x for x in f),
          "removing clock edges reproduces the mismatch, not a blanket exemption")
    base = head(build(sweep=128, packets=600), "flags", 1)
    for lo, what in ((0.0, "whole"), (0.65, "post-hold")):
        f, _ = run(L, view=view_for(base, rot=5, lo=lo))
        check(any("sidecar" in x or "does not describe" in x for x in f),
              "%s sidecar rotation still faults with honest server clock edges" % what)
    injected = view[:4] + ["hold 999999 999999"] + view[4:]
    f, _, report = run(L, view=injected, report=True)
    check(any("3 columns, expected 6" in x for x in f),
          "a sidecar hold is a format fault even with an otherwise matching clock")
    check("angle_rule     tight" in report,
          "rejecting a sidecar hold does not suppress the remaining angle comparison")
    f, _ = run(missing, view=injected)
    check(any("sidecar" in x for x in f),
          "a sidecar-supplied edge cannot repair the authoritative clock")


def case_angle_hold_legacy():
    L, view = held_clock_pair()
    legacy = [l for l in L if not l.startswith(("hold ", "holdclock "))]
    for unclosed in (False, True):
        part = [l for l in legacy if not l.startswith(("end ", "inend "))] if unclosed else legacy
        if unclosed:
            part = head(part, "flags", 0)  # a prefix's placeholder, NOT a clean verdict
        f, n = run(part, name="run.rec" if unclosed else "t.rec", view=view)
        check(not f and any("legacy hold clock not stated" in x for x in n),
              "legacy %s clock is explicitly unavailable, never an angle conviction"
              % ("prefix" if unclosed else "practice"))
    ranked = build(sweep=128, packets=600)
    f, _ = run(ranked, view=view_for(ranked, rot=5))
    check(any("sidecar" in x or "does not describe" in x for x in f),
          "legacy closed ranked no-hold records retain their existing comparison")
    future = head(L[:], "holdclock", 2)
    f, n = run(future, view=view)
    check(not f and any("unsupported hold clock" in x for x in n),
          "an unknown future clock cannot claim an angle OK or a conviction")


def case_angle_hold_origins():
    L, _ = held_clock_pair(holds=((150, 73), (161, 37)),
                           sessions=((160, 10, "retry"),))
    f, _ = run(L)
    check(not f, "a session resets cumulative exclusion and its prior-origin floor")
    if f:
        print("        %s" % f)
    L = build(sweep=128, packets=600)
    R = L[:]
    R.insert(next(i for i, l in enumerate(R) if l.startswith("in ")),
             "resume 001 0")
    f, n, report = run(R, view=view_for(L, rot=90), report=True)
    check(not f and "angle_rule     unavailable" in report,
          "an unknown restored origin cannot produce even a loose-rule conviction")
    bad = view_for(L)
    bad[4] = "10.01 1 nan 0 0 0"
    f, _ = run(R, view=bad)
    check(any("not a number" in x or "NaN" in x or "finite" in x for x in f),
          "clock abstention does not suppress independent sidecar format faults")


def case_angle_initial_origin():
    L, view = held_clock_pair(holds=((0, 73),))
    faults, _, report = run(L, view=view, report=True)
    check(not faults and "angle_rule     tight" in report,
          "a first hold projecting exactly to the initial origin still ACTS")
    ix = next(i for i, line in enumerate(L) if line.startswith("hold "))
    fields = L[ix].split()
    fields[2] = str(int(fields[2]) + 1)
    bad = L[:]
    bad[ix] = " ".join(fields)
    faults, _, report = run(bad, view=view, report=True)
    check(any("initial timer origin" in x for x in faults),
          "a first exclusion cannot consume ticks before the initial origin")
    check("angle_rule     unavailable" in report,
          "an impossible first exclusion cannot judge either angular rule")
    bad = L[:]
    bad[ix] = "hold %d 0" % (HORIZON - 1)
    faults, _, report = run(bad, view=view, report=True)
    check(any("trace's own horizon" in x for x in faults),
          "a hold cannot precede the recording's raw trace horizon")
    check("angle_rule     unavailable" in report,
          "an impossible raw hold horizon also withholds both angle rules")
    base = head(build(sweep=128, packets=600), "flags", 1)
    faults, _ = run(L, view=view_for(base, rot=5))
    check(any("sidecar" in x for x in faults),
          "trusted initial clock accounting still detects a rotated sidecar")


def case_closing_carry_exact_sign():
    """Underflow is not signed zero; exponent magnitude cannot erase sign."""
    for ver in (9, 10):
        base = build(ver=ver, sweep=128, packets=600)
        for value, negative in (("-1e-999", True), ("-0e-999", False),
                                ("-1e-323", True), ("1e-999", False),
                                ("-1e-999999999999999999999999999", True),
                                ("-0e-999999999999999999999999999", False)):
            faults, _ = run(edit(base, "inend", 2, value))
            check((len(faults) == 1 and "inend carry" in faults[0]) if negative
                  else not faults,
                  "v%d closing carry %s keeps exact sign and genuine zero" % (ver, value))
    base = build(ver=8, sweep=128, packets=600)
    for value, negative in (("-0." + "0" * 400 + "1", True),
                            ("-0." + "0" * 400, False),
                            ("0." + "0" * 400 + "1", False)):
        faults, _ = run(edit(base, "inend", 2, value))
        check((len(faults) == 1 and "inend carry" in faults[0]) if negative
              else not faults,
              "v8 decimal closing carry preserves exact nonzero sign=%s" % negative)


def case_closing_carry_nonnegative():
    """The native mover clamps its remainder; this is not a timer equality."""
    for ver in (8, 9, 10):
        base = build(ver=ver, sweep=128, packets=600)
        for value in ("0", "-0", "0.003", "0.000000001"):
            faults, _ = run(edit(base, "inend", 2, value))
            check(not faults, "v%d closing carry %s remains legal" % (ver, value))
        for value in ("-0.001", "-1", "-0.000000001"):
            faults, _ = run(edit(base, "inend", 2, value))
            check(len(faults) == 1 and "inend carry" in faults[0]
                  and "negative" in faults[0],
                  "v%d rejects only the negative closing carry %s" % (ver, value))
    old = build(ver=7, sweep=128, packets=600)
    end = int(next(l.split()[2] for l in reversed(old) if l.startswith("in "))) + 1
    faults, _ = run(insert_before(old, "end", "inend %d -0.001" % end))
    check(not faults, "pre-v8 closing record has no new carry assertion")
    for label, pair in (("warm retries", retry_clock_pair()),
                        ("cold loads", cold_clock_pair("load"))):
        lines, view = pair
        lower = edit(lines, "inend", 2, "-0.001")
        faults, _notes, report = run(lower, view=view, report=True)
        check(len(faults) == 1 and "inend carry" in faults[0],
              "negative carry with two %s preserves source resets" % label)
        check("angle_rule     unavailable" in report,
              "negative carry with %s does not invent an angle judgement" % label)
        bad = view[:]
        f = bad[-1].split(); f[2] = "-1"; bad[-1] = " ".join(f)
        faults, _ = run(lower, view=bad)
        check(len(faults) == 2 and any("never negative" in x for x in faults)
              and any("inend carry" in x for x in faults),
              "negative carry with %s preserves only the independent view fault" % label)
        end = int(next(l.split()[1] for l in lines if l.startswith("inend ")))
        for kind in ("warp", "ride"):
            marker = ("warp %d %d %d tele 0 0 64 0 0 0 0"
                      % (PACKETS - 1, end + 1, PACKETS - 1) if kind == "warp"
                      else "ride %d %d arm 0 0 0" % (PACKETS - 1, end + 1))
            live = lines
            for row in STAGED + [marker]:
                live = insert_before(live, "inend", row)
            live = bump_end(live, "warps" if kind == "warp" else "rides")
            faults, _ = run(live, view=view)
            check(len(faults) == 1 and "'%s' observation" % kind in faults[0],
                  "existing %s closer fault with %s is an acting control" % (kind, label))
            lower = edit(live, "inend", 2, "-0.001")
            faults, _ = run(lower, view=view)
            check(len(faults) == 2 and any("inend carry" in x for x in faults)
                  and any("'%s' observation" % kind in x for x in faults),
                  "both independent closer faults with %s/%s preserve resets" % (kind, label))
            faults, _ = run(lower, view=bad)
            check(len(faults) == 3 and any("inend carry" in x for x in faults)
                  and any("'%s' observation" % kind in x for x in faults)
                  and any("never negative" in x for x in faults),
                  "both closer faults with %s/%s retain independent view fault" % (kind, label))


def case_imposition_closing_horizon():
    """A post-move warp / frozen carrier can outlive the final input row."""
    def with_marker(kind, mt, ver=9, **kw):
        if kind == "warp":
            kw["warps"] = ((PACKETS - 1, mt, "tele"),)
        else:
            kw["rides"] = ((PACKETS - 1, mt, "arm", 0, 0, 0),)
        return build(ver=ver, **kw)

    for ver in (8, 9, 10):
        end = int(next(l.split()[1] for l in build(ver=ver) if l.startswith("inend ")))
        for kind in ("warp", "ride"):
            tail = with_marker(kind, end, ver)
            ok_clean(tail, "v%d closing exactly on the final %s passes" % (ver, kind))
            ok_clean(edit(tail, "inend", 1, end + 1),
                     "v%d closing after the final %s passes" % (ver, kind))
            faults_with(edit(tail, "inend", 1, end - 1), "'%s' observation" % kind,
                        "v%d closing before the final %s faults specifically" % (ver, kind))

    end = int(next(l.split()[1] for l in build() if l.startswith("inend ")))
    # Warp touch order is not a sorted track. A later lower stamp cannot erase
    # the earlier observation, whether or not this writer emits that ordering.
    many = build(warps=((PACKETS - 1, end + 2, "tele"),
                       (PACKETS - 1, end + 1, "tele")))
    ok_clean(edit(many, "inend", 1, end + 2), "closing reaches the maximum warp, not just the last")
    faults_with(edit(many, "inend", 1, end + 1), "'warp' observation",
                "an earlier larger warp still bounds closing")

    for kind in ("warp", "ride"):
        tail = with_marker(kind, end + 1)
        part = [l for l in tail if not l.startswith(("inend ", "end "))]
        faults, _ = run(part, name="t.part")
        check(not faults, "a final %s in a live prefix needs no invented closer" % kind)
        late = with_marker(kind, end)
        marker = next(l for l in late if l.startswith(kind + " "))
        late.remove(marker)
        close = next(i for i, l in enumerate(late) if l.startswith("inend "))
        late.insert(close + 1, marker)
        ok_clean(late, "a %s row after the closer still permits equal raw counters" % kind)
        faults_with(edit(late, "inend", 1, end - 1), "'%s' observation" % kind,
                    "moving a %s row after the closer cannot erase its observation" % kind)
        for boundary in ("resume 3 40", "retry 40"):
            reset = insert_before(tail, "inend", boundary)
            ok_clean(reset, "a prior %s does not constrain closing across %s"
                     % (kind, boundary.split()[0]))

        reset = with_marker(kind, end, ver=10, sessions=((PACKETS - 2, 10, "retry"),))
        marker = next(l for l in reset if l.startswith(kind + " "))
        reset.remove(marker)
        pause_mt = int(next(l.split()[1] for l in reset if l.startswith("pause ")))
        f = marker.split()
        f[1:3] = [str(PACKETS - 2), str(pause_mt)]
        if kind == "warp":
            f[3] = str(PACKETS - 2)
        reset = insert_before(reset, "pause", " ".join(f))
        current = int(next(l.split()[1] for l in reset if l.startswith("inend ")))
        check(pause_mt > current, "the %s session control actually resets to a smaller counter" % kind)
        ok_clean(reset, "an old-session %s cannot bound the new session's closer" % kind)
        f[1:3] = [str(PACKETS - 1), str(current)]
        if kind == "warp":
            f[3] = str(PACKETS - 1)
        new = insert_before(reset, "inend", " ".join(f))
        new = bump_end(new, "warps" if kind == "warp" else "rides")
        ok_clean(new, "a current-session %s can equal its closer" % kind)
        faults_with(edit(new, "inend", 1, current - 1), "'%s' observation" % kind,
                    "the new session's own %s still bounds closing" % kind)

        # `inend` itself is not declared before v8. Do not invent a new
        # counter contract from records under a version that cannot state it.
        old = with_marker(kind, end + 1, ver=7)
        old = insert_before(old, "end", "inend %d 0.003" % end)
        ok_clean(old, "a v7 %s with an undeclared closer keeps legacy handling" % kind)
        malformed = edit(tail, kind, 2, "bad")
        faults, _ = run(malformed)
        check(any("pk/mt are not integers" in x for x in faults)
              and not any("observation" in x for x in faults),
              "a malformed %s is not promoted to a closing observation" % kind)

    unknown = build(warps=((PACKETS - 1, end, "newhandler"),))
    faults, notes = run(unknown)
    check(not faults and any("newhandler" in x for x in notes),
          "an unknown warp kind retains open vocabulary at a valid raw boundary")
    faults_with(edit(unknown, "inend", 1, end - 1), "'warp' observation",
                "an unknown warp handler still carries the known raw counter field")
    ok_clean(build(pms=((end + 1000, PACKETS - 1),)),
             "a pm packet ordinal is not a raw closing-horizon observation")


def case_imposition_abandon_horizon():
    """Kept frozen evidence closes at the freeze latch, not its later state."""
    for ver in (8, 9, 10):
        end = int(next(l.split()[1] for l in build(ver=ver) if l.startswith("inend ")))
        for kind in ("warp", "ride"):
            kw = ({"warps": ((PACKETS - 1, end + 1, "tele"),)} if kind == "warp"
                  else {"rides": ((PACKETS - 1, end + 1, "arm", 0, 0, 0),)})
            kept = head(staged(ver=ver, pre=["abandon %d" % PACKETS], **kw), "flags", 1)
            ok_clean(kept, "v%d frozen kept %s may exceed the latched closer" % (ver, kind))
            faults_with(drop_kinds(kept, ("abandon",)), "'%s' observation" % kind,
                        "v%d the same %s still faults at an ordinary live closer" % (ver, kind))
            if ver == 9:
                faults_with(edit(kept, kind, 2, "bad"), "pk/mt are not integers",
                            "kept evidence still validates %s fields" % kind)
                if kind == "warp":
                    faults_with(edit(kept, "abandon", 1, PACKETS - 1), "trailer says",
                                "the frozen exception does not hide an invalid abandon")

    for label, pair in (("warm retries", retry_clock_pair()),
                        ("cold loads", cold_clock_pair("load"))):
        lines, view = pair
        end = int(next(l.split()[1] for l in lines if l.startswith("inend ")))
        for kind in ("warp", "ride"):
            marker = ("warp %d %d %d tele 0 0 64 0 0 0 0"
                      % (PACKETS - 1, end + 1, PACKETS - 1) if kind == "warp"
                      else "ride %d %d arm 0 0 0" % (PACKETS - 1, end + 1))
            kept = lines[:]
            for rec in STAGED + [marker, "abandon %d" % PACKETS]:
                kept = insert_before(kept, "inend", rec)
            kept = bump_end(kept, "warps" if kind == "warp" else "rides")
            faults, _notes, report = run(kept, view=view, report=True)
            check(not faults and "angle_rule     unavailable" in report,
                  "frozen kept %s with two %s stays unavailable, not a false fault" % (kind, label))
            bad = view[:]
            f = bad[-1].split(); f[2] = "-1"; bad[-1] = " ".join(f)
            faults, _ = run(kept, view=bad)
            check(any("never negative" in x for x in faults),
                  "a frozen %s with %s preserves an independent sidecar fault" % (kind, label))


def case_imposition_restore_allowance():
    """An independent closer fault cannot revoke valid client clock resets."""
    for label, pair in (("warm retries", retry_clock_pair()),
                        ("cold loads", cold_clock_pair("load"))):
        lines, view = pair
        end = int(next(l.split()[1] for l in lines if l.startswith("inend ")))
        for kind in ("warp", "ride"):
            marker = ("warp %d %d %d tele 0 0 64 0 0 0 0"
                      % (PACKETS - 1, end + 1, PACKETS - 1) if kind == "warp"
                      else "ride %d %d arm 0 0 0" % (PACKETS - 1, end + 1))
            live = edit(lines, "inend", 1, end + 1)
            for rec in STAGED + [marker]:
                live = insert_before(live, "inend", rec)
            live = bump_end(live, "warps" if kind == "warp" else "rides")
            faults, _notes, report = run(live, view=view, report=True)
            check(not faults and "angle_rule     unavailable" in report,
                  "ordinary %s with two %s has a clean unavailable control" % (kind, label))
            lower = edit(live, "inend", 1, end)
            faults, _notes, report = run(lower, view=view, report=True)
            check(len(faults) == 1 and "'%s' observation" % kind in faults[0],
                  "ordinary %s closer fault preserves two %s without sidecar faults" % (kind, label))
            check("angle_rule     unavailable" in report,
                  "faulting %s closer with %s does not invent an angular judgement" % (kind, label))
            bad = view[:]
            f = bad[-1].split(); f[2] = "-1"; bad[-1] = " ".join(f)
            faults, _ = run(lower, view=bad)
            check(len(faults) == 2 and any("never negative" in x for x in faults)
                  and any("'%s' observation" % kind in x for x in faults),
                  "faulting %s closer with %s preserves only the independent view fault" % (kind, label))


def case_imposition_boundary_authority():
    end = int(next(l.split()[1] for l in build() if l.startswith("inend ")))
    for kind in ("warp", "ride"):
        kw = ({"warps": ((PACKETS - 1, end + 1, "tele"),)} if kind == "warp"
              else {"rides": ((PACKETS - 1, end + 1, "arm", 0, 0, 0),)})
        for ver in (8, 9):
            tail = build(ver=ver, **kw)
            for rec in ("session", "session 2 10 0.003 40"):
                faults_with(insert_before(tail, "inend", rec), "'%s' observation" % kind,
                            "v%d unknown %s cannot erase the %s bound" % (ver, rec, kind))
        for rec in ("resume bad 40", "resume 1000 40", "retry nan"):
            faults_with(insert_before(build(**kw), "inend", rec), "'%s' observation" % kind,
                        "invalid %s cannot erase the %s bound" % (rec, kind))
        for rec in ("session", "session 2 10 0.003 40"):
            faults_with(insert_before(build(ver=10, **kw), "inend", rec), "'%s' observation" % kind,
                        "a malformed/unpaired v10 %s cannot erase the %s bound" % (rec, kind))


def case_hold_closing_horizon():
    """A final thaw is a raw observation even without another input row."""
    base = insert_before(head(build(), "flags", 1), "begin", "holdclock 1")
    end = int(next(l.split()[1] for l in base if l.startswith("inend ")))
    for frozen in (0, 1):
        tail = insert_before(base, "inend", "hold %d %d" % (end, frozen))
        ok_clean(tail, "closing exactly on the final hold (%d frozen) passes" % frozen)
        ok_clean(edit(tail, "inend", 1, end + 1),
                 "closing after the final hold (%d frozen) passes" % frozen)
        bad = edit(tail, "inend", 1, end - 1)
        faults_with(bad, "last 'hold' horizon",
                    "closing before the final hold (%d frozen) faults specifically" % frozen)
        future = head(bad, "holdclock", 2)
        faults, _ = run(future)
        check(not faults, "an unsupported hold clock does not acquire v1 horizon semantics")
        part = [l for l in tail if not l.startswith(("inend ", "end "))]
        faults, _ = run(part, name="t.part")
        check(not faults, "a final hold in a live prefix needs no invented closing horizon")

    # The old raw counter is larger than the new session's closing horizon.
    reset, _ = held_clock_pair(holds=((150, 73),), sessions=((299, 10, "drop"),))
    reset = head(reset, "flags", 16385)
    end = int(next(l.split()[1] for l in reset if l.startswith("inend ")))
    old = int(next(l.split()[1] for l in reset if l.startswith("hold ")))
    check(old > end, "the reset control actually has an earlier-origin hold beyond this footer")
    ok_clean(reset, "an earlier-origin hold cannot bound the new session's footer")
    current = insert_before(reset, "inend", "hold %d 1" % end)
    ok_clean(current, "a final hold in the new session can equal its closing horizon")
    faults_with(edit(current, "inend", 1, end - 1), "last 'hold' horizon",
                "the current-origin final hold still bounds a reset session")


def case_angle_initial_restore():
    base = build(sweep=128, packets=600)
    for declared in (False, True):
        L = insert_before(base[:], "begin", "holdclock 1") if declared else base[:]
        L = head(L, "instart", "%d %d" % (HORIZON, HORIZON - 50))
        faults, _, report = run(L, view=view_for(base, rot=5), report=True)
        check(not faults and "angle_rule     unavailable" in report
              and "initial timer origin unavailable" in report,
              "%s initial restored origin cannot silently convict"
              % ("declared" if declared else "legacy"))
        bad = view_for(base)
        bad[4] = "10.01 1 nan 0 0 0"
        faults, _ = run(L, view=bad)
        check(any("not a number" in x or "NaN" in x or "finite" in x for x in faults),
              "initial-origin abstention preserves independent sidecar faults")


def case_integer_tokens():
    cases = []
    S = build(ver=10, sessions=((5, 10, "retry"),))
    for kind, positions in (("pause", (1, 3)), ("session", (1, 2, 4))):
        for pos in positions:
            cases.append((S, kind, pos))
    cases += [(build(), "instart", 1), (build(), "zonerule", 1),
              (build(), "inend", 1),
              (build(warps=((0, HORIZON, "tele"),)), "warp", 1),
              (build(rides=((0, HORIZON, "arm", 0, 0, 0),)), "ride", 1)]
    for L, kind, pos in cases:
        for token in ("--1", "\u00b2", "1" * 5000):
            bad = edit(L, kind, pos, token)
            faults, _ = run(bad)
            check(any(kind in x for x in faults),
                  "%s field %d rejects malformed integer %s without a reader crash"
                  % (kind, pos, ascii(token[:16])))


def case_angle_hold_restore_boundaries():
    # Frozen ticks belong to a timer origin, not to the whole file. Keep the
    # raw mover counter continuous but start a smaller total after each restore.
    for kind in ("resume", "retry"):
        lines, _ = held_clock_pair(holds=((150, 73), (350, 13)))
        out, n = [], 0
        for line in lines:
            fields = line.split()
            if fields[0] == "in":
                if n == 300:
                    out.append("resume slot 300" if kind == "resume" else "retry 300")
                n += 1
            elif fields[0] == "hold" and n > 300:
                fields[2] = "13"
                line = " ".join(fields)
            out.append(line)
        faults, _ = run(out)
        check(not faults, "%s resets frozen totals before the next hold" % kind)
        if faults:
            print("        got: %s" % faults)

    # No preceding input/hold in this session can lend its floor to this check.
    lines, _ = held_clock_pair(holds=(), sessions=((299, 2000, "drop"),))
    lines = head(lines, "flags", 16385)       # TF_CHEAT | TF_MULTISESSION
    session = next(i for i, line in enumerate(lines) if line.startswith("session "))
    first = next(i for i in range(session + 1, len(lines))
                 if lines[i].startswith("in "))
    lines.insert(first, "hold 2000 0")
    faults, _ = run(lines)
    check(not faults, "a first hold at the new session horizon is clean")
    if faults:
        print("        got: %s" % faults)
    lines[first] = "hold 1999 0"
    faults, _ = run(lines)
    check(any("'hold' is below the trace's own horizon" in f for f in faults),
          "a hold before the first session input still obeys that session's horizon")


def case_angle_hold_conversion():
    for token in ("--1", "\u00b2", "1" * 5000):
        L = build()
        ix = next(i for i, l in enumerate(L) if l.startswith("inend "))
        L.insert(ix, "hold %s 0" % token)
        f, _ = run(L)
        check(any("'hold'" in x for x in f),
              "noncanonical hold counter %r completes with a format fault" % token[:20])
    for mt in (-2147483648, 2147483648):
        L = insert_before(build(), "begin", "holdclock 1")
        ix = next(i for i, l in enumerate(L) if l.startswith("in "))
        f = L[ix].split()
        f[2] = str(mt)
        L[ix] = " ".join(f)
        if mt < 0:
            L.insert(ix, "hold 2147483647 %d" % (2147483647 - HORIZON))
        faults, _notes, report = run(L, view=view_for(build()), report=True)
        check(any("projected angle tick" in x for x in faults),
              "projected counter %s reports instead of overflowing the angle array" % mt)
        check("angle_rule     unavailable" in report,
              "an unrepresentable projection cannot produce an angle judgment")


def case_angle_hold_shape():
    L, view = held_clock_pair()
    for bad in ("hold x 3", "hold 1", "hold 100 -1", "hold 20 21",
                "hold 99999999999999999 3", "hold 10 0"):
        mutant = L[:]
        ix = next(i for i, l in enumerate(mutant) if l.startswith("hold "))
        mutant[ix] = bad
        f, _ = run(mutant, view=view)
        check(any("'hold'" in x for x in f), "invalid clock edge %r cannot remap angles" % bad)
    mutant = L[:]
    ix = [i for i, l in enumerate(mutant) if l.startswith("hold ")][1]
    f = mutant[ix].split()
    mutant[ix] = "hold %s 1" % f[1]
    faults_with(mutant, "counters go backwards", "cumulative exclusions cannot decrease")
    mutant = L[:]
    ix = next(i for i, l in enumerate(mutant) if l.startswith("hold "))
    f = mutant[ix].split()
    mutant[ix] = "hold %d %s" % (int(f[1]) + 50, f[2])
    faults_with(mutant, "below the preceding hold horizon", "a clock edge cannot cover earlier input")


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


def v11_fixture(*, frozen=0, **kw):
    """Synthetic grammar-only declaration, not a native replay/hardware pass."""
    lines = build(**kw)
    lines[0] = "FTESURF-REC 11"
    close = next(i for i, l in enumerate(lines) if l.startswith("inend "))
    mt = int(lines[close].split()[1])
    lines.insert(close, "clockend counted %d 0 %d" % (HORIZON, frozen))
    ix = next(i for i, l in enumerate(lines) if l.startswith("end "))
    tail = lines[ix].split()
    tail[1] = str(mt - HORIZON - frozen)
    if len(tail) == 11:
        tail.append("0")                  # v9 builder had no session column
    tail.append("1")                      # exactly one closing declaration
    lines[ix] = " ".join(tail)
    return lines


def case_v11_clock():
    base = v11_fixture()
    ok_clean(base, "v11 counted declaration acts on a matched footer")
    faults_with(bump_end(base, "ticks"), "clockend predicts",
                "one changed rank tick contradicts declared clock state")
    faults_with(bump_end(base, "clocks"), "clockend count",
                "closing declaration count is independently bound")
    faults_with(drop_kinds(base, ("clockend",)), "exactly one",
                "dropping the required witness is not absence-as-zero")
    doubled = insert_before(base[:], "inend", "clockend counted %d 0 0" % HORIZON)
    faults_with(doubled, "exactly one", "duplicate clock witnesses have no authority")
    ok_clean(v11_fixture(frozen=10),
             "unthawed final exclusion needs no invented thaw hold (grammar only)")
    for value in ("-1e-99999", "1e-99999", "nan", "inf", "1e100"):
        faults_with(edit(base, "clockend", 3, value), "invalid clockend",
                    "impossible source tickcarry %s is rejected" % value)
    for value in ("0", "-0", "0.0", "-0e-99999"):
        ok_clean(edit(base, "clockend", 3, value),
                 "mathematical zero tickcarry %s stays valid" % value)
    # Large integer additions really round in QC float32, unlike Python ints.
    rounded = edit(base, "inend", 1, 16777216)
    rounded = edit(rounded, "clockend", 2, 0)
    rounded = edit(rounded, "clockend", 3, 1)
    rounded = edit(rounded, "end", 1, 16777216)
    ok_clean(rounded, "declared clock emulates float32 addition, not integer algebra")
    faults_with(bump_end(rounded, "ticks"), "clockend predicts",
                "integer-algebra neighbor does not pass the float32 model")
    faults_with(edit(base, "clockend", 2, 16777217), "invalid clockend",
                "an impossible float32 origin is not rounded into acceptance")
    faults_with(edit(base, "clockend", 1, "other"), "invalid clockend",
                "unknown closing-clock modes are not guessed")
    bad = base[:]
    ix = next(i for i, l in enumerate(bad) if l.startswith("clockend "))
    bad[ix] = "clockend counted"
    faults_with(bad, "invalid clockend", "missing native components report, not crash")
    for suffix in ("0", "1e0"):
        extra = base[:]
        ix = next(i for i, l in enumerate(extra) if l.startswith("end "))
        extra[ix] += " " + suffix
        faults, _ = run(extra)
        check(len(faults) == 1 and "clockend" in faults[0],
              "counted footer extra %s adds no false equation fault" % suffix)
        faults, _ = run(bump_end(extra, "inputs"))
        check(any("input records" in f for f in faults),
              "counted footer extra %s still validates old input count" % suffix)


def case_v11_closing_restore_authority():
    """Every closing-only failure stays separate from validated clock resets."""
    bad = "clockend counted bad 0 0"
    variants = (("word origin", bad, None, 1),
                ("exponent origin", "clockend counted 1e0 0 0", None, 1),
                ("exponent frozen", "clockend counted 0 0 0e0", None, 1),
                ("exponent kind", "clockend 1e0", None, 1),
                ("exponent extra", "clockend counted 0 0 0 1e0", None, 1),
                ("missing count", bad, "missing", 2),
                ("word count", bad, "bad", 2),
                ("exponent count", bad, "1e0", 2),
                ("wrong count", bad, "0", 2),
                ("extra token", bad, "1 0", 2),
                ("extra exponent token", bad, "1 1e0", 2))
    for label, pair in (("warm retries", retry_clock_pair()),
                        ("cold loads", cold_clock_pair("load"))):
        base, view = pair
        faults, _notes, report = run(base, view=view, report=True)
        check(not faults and "angle_rule     unavailable" in report,
              "%s control actually consumes both validated resets" % label)
        for name, closer, count, expected in variants:
            lines = base[:]
            lines[0] = "FTESURF-REC 11"
            lines = insert_before(lines, "inend", closer)
            ix = next(i for i, l in enumerate(lines) if l.startswith("end "))
            tail = lines[ix].split()
            if len(tail) == 11:
                tail.append("0")
            if count != "missing":
                tail.append("1" if count is None else count)
            lines[ix] = " ".join(tail)
            faults, _notes, report = run(lines, view=view, report=True)
            check(len(faults) == expected and all("clockend" in f for f in faults),
                  "%s preserves both %s without sidecar blame" % (name, label))
            check("angle_rule     unavailable" in report,
                  "%s grants no angular judgement for %s" % (name, label))
            badview = view[:]
            fields = badview[-1].split(); fields[2] = "-1"; badview[-1] = " ".join(fields)
            faults, _ = run(lines, view=badview)
            check(len(faults) == expected + 1 and any("never negative" in f for f in faults),
                  "%s preserves an independent VIEW fault for %s" % (name, label))
            if name in ("missing count", "extra token", "extra exponent token"):
                faults, _ = run(bump_end(lines, "inputs"), view=view)
                check(any("input records" in f for f in faults)
                      and any("goes backwards" in f for f in faults),
                      "%s does not hide old input-count damage for %s" % (name, label))
                tail = lines[ix].split(); tail[11] = str(int(tail[11]) + 1)
                wrong = lines[:]; wrong[ix] = " ".join(tail)
                faults, _ = run(wrong, view=view)
                check(any("sessions" in f for f in faults)
                      and any("goes backwards" in f for f in faults),
                      "%s does not hide old session-count damage for %s" % (name, label))


def case_v11_closing_spectate_authority():
    """A closing declaration cannot become an authoritative spectate boundary."""
    for label, pair in (("warm retries", retry_clock_pair()),
                        ("cold loads", cold_clock_pair("load"))):
        base, view = pair
        base = spectated(base)
        faults, _notes, report = run(base, view=view, report=True)
        check(not faults and "angle_rule     unavailable" in report,
              "%s spectate control consumes both validated resets" % label)
        for closer, expected in (("clockend sampled", 0),
                                 ("clockend counted bad 0 0", 1)):
            lines = base[:]
            lines[0] = "FTESURF-REC 11"
            lines = insert_before(lines, "spec", closer)
            ix = next(i for i, l in enumerate(lines) if l.startswith("end "))
            tail = lines[ix].split()
            if len(tail) == 11:
                tail.append("0")
            tail.append("1")
            lines[ix] = " ".join(tail)
            faults, _notes, report = run(lines, view=view, report=True)
            check(len(faults) == expected and all("clockend" in f for f in faults),
                  "%s before spectate does not reclassify %s history" % (closer, label))
            check("angle_rule     unavailable" in report,
                  "closing-only placement keeps %s angular judgement unavailable" % label)
            faults, _ = run(bump_end(lines, "inputs"), view=view)
            check(any("input records" in f for f in faults)
                  and any("goes backwards" in f for f in faults),
                  "closing placement still exposes independent count damage for %s" % label)


def case_v11_closing_session_seed_authority():
    """Closing declarations are transparent at initial and restored seed boundaries."""
    from reccheck import check_rec, check_view

    base, view = cold_clock_pair("load")
    base[0] = "FTESURF-REC 11"
    base = insert_before(base, "inend", "clockend sampled")
    ix = next(i for i, l in enumerate(base) if l.startswith("end "))
    tail = base[ix].split()
    if len(tail) == 11:
        tail.append("0")
    tail.append("1")
    base[ix] = " ".join(tail)
    control = check_rec("session.rec", data=("\n".join(base) + "\n").encode())
    check(not control.faults and control.view_reset_budget == 2,
          "session boundary control validates exactly two reset allowances")
    variants = (("relocated", ["clockend sampled"], False, 0),
                ("duplicate", ["clockend sampled"], True, 1),
                ("malformed relocated", ["clockend counted bad 0 0"], False, 1),
                ("malformed duplicate", ["clockend counted bad 0 0"], True, 1),
                ("consecutive", ["clockend sampled", "clockend counted bad 0 0"], True, 1))
    # -1 is the initial begin/seed boundary; the rest are restored sessions.
    for session in range(-1, sum(l.startswith("session ") for l in base)):
        for name, closers, keep_terminal, expected in variants:
            lines = [l for l in base if keep_terminal or not l.startswith("clockend ")]
            sl = (lines.index("begin") if session < 0 else
                  [i for i, l in enumerate(lines) if l.startswith("session ")][session])
            lines[sl + 1:sl + 1] = closers
            ix = next(i for i, l in enumerate(lines) if l.startswith("end "))
            tail = lines[ix].split()
            tail[-1] = str(len(closers) + int(keep_terminal))
            lines[ix] = " ".join(tail)
            rec = check_rec("session.rec", data=("\n".join(lines) + "\n").encode())
            check(rec.view_reset_budget == control.view_reset_budget,
                  "%s at session %d preserves exact reset budget" % (name, session))
            faults, _notes, report = run(lines, view=view, report=True)
            check(len(faults) == expected and all("clockend" in f for f in faults)
                  and "angle_rule     unavailable" in report,
                  "%s at session %d adds no VIEW blame or angular grant" % (name, session))
            badview = view[:]
            fields = badview[-1].split(); fields[2] = "-1"; badview[-1] = " ".join(fields)
            faults, _ = run(lines, view=badview)
            check(len(faults) == expected + 1 and any("never negative" in f for f in faults),
                  "%s at session %d preserves independent VIEW damage" % (name, session))
            faults, _ = run(bump_end(lines, "inputs"), view=view)
            check(any("input records" in f for f in faults)
                  and any("goes backwards" in f for f in faults),
                  "%s at session %d cannot hide legacy damage" % (name, session))
        intervening = base[:]
        sl = (intervening.index("begin") if session < 0 else
              [i for i, l in enumerate(intervening) if l.startswith("session ")][session])
        sample = next(l for l in base if l and l[0] in "-0123456789")
        intervening.insert(sl + 1, sample)
        faults, _ = run(intervening, view=view)
        placement = "not the first line" if session < 0 else "second 'seed'"
        check(any(placement in f for f in faults),
              "a real intervening sample still breaks session %d seed adjacency" % session)

    # Check every body boundary, not just the two adjacency sites already found.
    view_bytes = ("\n".join(view) + "\n").encode()
    for label, source in (("restores", base), ("spectate/restores", spectated(base))):
        baseline = check_rec("positions.rec", data=("\n".join(source) + "\n").encode())
        bv = check_view("positions.view", baseline, data=view_bytes)
        check(not baseline.faults and not bv.faults and baseline.view_reset_budget == 2,
              "%s all-position control actually validates two resets" % label)
        bare = [l for l in source if not l.startswith("clockend ")]
        for kind, original, closer, count, expected in (
                ("relocated", bare, "clockend sampled", 1, 0),
                ("malformed", bare, "clockend counted bad 0 0", 1, 1),
                ("duplicate", source, "clockend counted bad 0 0", 2, 1)):
            failures, acted = [], 0
            for pos in range(original.index("begin") + 1, len(original) + 1):
                lines = original[:]
                lines.insert(pos, closer)
                ix = next(i for i, l in enumerate(lines) if l.startswith("end "))
                tail = lines[ix].split(); tail[-1] = str(count); lines[ix] = " ".join(tail)
                rec = check_rec("positions.rec", data=("\n".join(lines) + "\n").encode())
                vr = check_view("positions.view", rec, data=view_bytes)
                acted += 1
                if (len(rec.faults) != expected or any("clockend" not in f for f in rec.faults)
                        or rec.view_reset_budget != baseline.view_reset_budget or vr.faults
                        or vr.info.get("angle_rule") != bv.info.get("angle_rule")):
                    failures.append((pos, rec.faults, vr.faults, rec.view_reset_budget))
            check(not failures and acted > 0,
                  "%s %s stays outside lifecycle authority at all %d body positions"
                  % (label, kind, acted))
            if failures:
                print("        first boundary failures=%s" % failures[:3])


def case_v11_fzin():
    base = v11_fixture(sweep=128, packets=300)
    excluded = edit(base, "in", 0, "fzin", which=10)
    faults, _notes, out = run(excluded, view=view_for(base), report=True)
    check(not faults, "excluded-clock input counts as a real input without a fake angle tick")
    check("angle_rule     unavailable" in out,
          "release-phase clock joins abstain explicitly pending a sound model")
    badview = view_for(base, nan_at=20)
    faults, _ = run(excluded, view=badview)
    check(bool(faults), "excluded phase does not hide independently malformed VIEW metadata")
    faults_with(bump_end(excluded, "inputs"), "'end' says",
                "fzin participates in the existing exact input count")
    old = edit(build(), "in", 0, "fzin", which=10)
    faults_with(old, "requires format 11", "old prefixes cannot silently claim new input semantics")


def main():
    for fn in (case_control,
               case_no_horizon, case_horizon_without_rows,
               case_trailer_width, case_trailer_count,
               case_row_width,
               case_movetick_backwards, case_packet_backwards,
               case_below_horizon, case_carry_bound, case_button_width,
               case_instart_ordering, case_resume_is_not_a_fault,
               case_offgrid_angle_is_a_note, case_v9_offgrid_angle_is_a_fault,
               case_split_part_rows_are_not_joined,
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
               case_movebnd, case_profile_verdict, case_slow_clock,
               case_angle_control, case_angle_blind_is_said_out_loud,
               case_angle_rotated, case_angle_one_frame_rule,
               case_angle_one_frame_rule_reaches_a_still_camera,
               case_angle_one_frame_rule_needs_v9,
               case_angle_one_frame_rule_says_when_it_is_thin,
               case_angle_one_frame_rule_cannot_be_armed_on_a_slice,
               case_angle_nan_is_a_fault_not_a_skip,
               case_angle_ghost_is_not_a_fault,
               case_angle_lag_is_recovered,
               case_angle_lag_has_no_window,
               case_angle_lag_does_not_rescue_a_lie,
               case_angle_lag_is_not_invented_on_a_still_camera,
               case_angle_negative_run_clock_is_a_fault,
               case_angle_head_amnesty_costs_coverage,
               case_angle_lag_is_not_claimed_when_the_winner_is_bad,
               case_angle_omission_does_not_read_as_cover,
               case_angle_tight_rule_abstains_where_the_epoch_moves,
               case_angle_tight_rule_is_keyed_on_the_source_not_the_version,
               case_angle_hold_clock, case_angle_hold_legacy, case_angle_hold_origins,
               case_angle_hold_shape, case_angle_hold_restore_boundaries,
               case_angle_hold_conversion,
               case_angle_initial_origin, case_angle_initial_restore, case_integer_tokens,
               case_hold_closing_horizon, case_closing_carry_nonnegative,
               case_closing_carry_exact_sign,
               case_v11_clock, case_v11_closing_restore_authority,
               case_v11_closing_spectate_authority,
               case_v11_closing_session_seed_authority, case_v11_fzin,
               case_imposition_closing_horizon,
               case_imposition_abandon_horizon, case_imposition_restore_allowance,
               case_imposition_boundary_authority,
               case_view_retry_history,
               case_view_restore_history, case_view_resume_slot_history,
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
