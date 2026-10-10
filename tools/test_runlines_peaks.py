#!/usr/bin/env python3
"""The line's turnaround marks -- the top of an arc, the bottom of a ride (ROADMAP 12.6).

  python tools/test_runlines_peaks.py                       the model, no game
  python tools/test_runlines_peaks.py --write               regenerate the two fixtures
  python tools/test_runlines_peaks.py --log <rig log> --control-log <log of the build before>

THE FIXTURE is built here, tick by tick, so every expected mark is known by
construction and not from the classifier under test: ftesurf/cfg/test/
runlines_peaks.rec (a native file, contact in flags bit 16) and
runlines_peaks_mom.rec, THE SAME MOTION as an import (`foreign`, `momdemo`, no
bit 16), whose contact the viewer has to infer (tools/rampinfer.py).  One body:

  apex 1      the top of an arc in the air, 8.1 u above the file's first sample and
              6.5 u above the last one before the clock starts.  A REPLAY marks it;
              a BOARD LINE, whose count starts at that one seed sample, does not.
              That disagreement is the code's (BACKLOG, "Tops and bottoms on a
              line") and is pinned here so that changing it is seen
  bottom 1    vz turns up ON a ramp, where nothing was marked before -- twice,
              three ticks and a fifth of a unit apart: ONE mark, at the lower
  apex 2      in the air after the ride
  (none)      a landing on an upslope that itself turns vz up: the landing's mark
              is the bottom, and there is no second one
  apex 3      SLOW, on a ramp: |vz| never reaches 40, the body has risen 12 u
  (none)      six ticks of vz flipping between +3 and -3 on the ramp: noise
  bottom 2    on the ramp
  apex 4      in the 0.08 s the ramp hold bridges after the last contact; the
              leave is stamped back at that contact and comes BEFORE it
  (none)      a jump off ground (vz from 0 to +258 is a takeoff, not a bottom)
  (none)      that jump's top, 3 u above the ledge it lands on -- and not marked by
              the 40 u fall off the ledge afterwards: ground starts the count again
  (none)      after a teleport the body rises 0.8 u more and falls: not a top
  (none)      vz changing sign across a loaded save
  apex 5      25 u above where the load put the body, and 1 u above a ramp the
              body lands on next: it stands clear only some way down that ramp, so
              it is marked after the landing and has to go in the table BEFORE it
  bottom 3    on a sample whose vz is exactly 0 (the turn is AT that sample)
  apex 6      in the air after that ride
  (none)      after a teleport the body rises 7.4 u and falls: under the 8
  apex 7      after another it rises 8.6 u: over it
  (none)      a landing whose own sample still falls (vz -47) and whose next one
              turns up: the bottom between them is the landing's, as half the
              upslope landings in real files are (the review counted 13 of 24)
  apex 8      on that ramp: the alternation went through the landing's bottom
  apex 9      on a sample whose vz is exactly 0, off a jump onto a ledge 8.1 u
              under it.  The last air sample is 7.3 u under: the landing itself
              is where the body gets 8 u clear, and it marks the top

THE RULE (ROADMAP 12.6: height extrema, debounced, slow ones kept).  A turn is
where vz crossed zero between two samples: its time, height and sideways speed
read off the straight line vz draws between them (exact in the air, where the
mover's gravity is two half steps).  It is marked when it stands 8 u of height
clear on both sides -- of the turn before it, or of where the body left ground
or was moved; and of where the body goes next.  The expectations below are
computed from the file's own printed numbers with that reading, and which
turns stand clear is by the construction above.

The log is tools/runlines_smoke.py's, from ftesurf/cfg/test/runlines_peaks.cfg:
the client must mark each file exactly as above -- time, sample, place, speed --
mark the two identically (`~` aside), mark a board line of each the same from
its window's start (apex 1 aside), read `hud_lines_nums` as 2 with nothing set,
and queue some tops and bottoms for drawing with their numbers (the `lndm`
trace: it says a label was issued, not that it reached the screen).

EXIT STATUSES.  0 right.  1 wrong -- which includes a control that is not one
(it must mark no bottom and fewer tops).  2 CANNOT MEASURE: a log or a section
is missing.  64 the command line.
"""
import argparse
import os
from pathlib import Path
import re
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import p449mark  # noqa: E402
import rampinfer  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = {False: ROOT / "ftesurf/cfg/test/runlines_peaks.rec",
            True: ROOT / "ftesurf/cfg/test/runlines_peaks_mom.rec"}
TICK, STEP = 0.015, 12.0
SEED = 1                            # the last sample before the clock starts: a board line's seed
GROUND, AIR, RAMP = 0, 1, 2
E_LAND, E_LEAVE, E_JUMP, E_APEX, E_TROUGH, E_STITCH, E_BREAK = 1, 2, 3, 4, 5, 6, 7
CANNOT = "CANNOT MEASURE: "


class Motion:
    """The body, one sample a tick.  Positions follow the two velocities either
    side of a tick, as the mover's do, so nothing here reads as a teleport
    unless it is made one."""

    def __init__(self):
        self.t = -2 * TICK
        self.o = [0.0, 0.0, 2000.0]
        self.v = [600.0, 0.0, 114.0]
        self.samples = []           # (t, o, v, ground, jump, ramp, record before)
        self.want = []              # (what, kind, sub, sample ordinal, stamped at ordinal, on a board line too)
        self._put(False, False, False, None)

    def _put(self, ground, jump, ramp, record):
        self.samples.append((self.t, tuple(self.o), tuple(self.v), ground, jump, ramp, record))
        return len(self.samples) - 1

    def tick(self, dvz, dvx=0.0, ramp=False, ground=False, jump=False, move=None, record=None, n=1):
        i = -1
        for _ in range(n):
            pv = list(self.v)
            self.v[2] = 0.0 if ground else self.v[2] + dvz
            self.v[0] += dvx
            self.o = [self.o[k] + (pv[k] + self.v[k]) * 0.5 * TICK for k in range(3)]
            if move:
                self.o = [self.o[k] + move[k] for k in range(3)]
            self.t += TICK
            i = self._put(ground, jump, ramp, record)
        return i

    def fall(self, n):
        return self.tick(-STEP, n=n)

    def mark(self, what, kind, sub, i, at=None, board=True):
        self.want.append((what, kind, sub, i, i if at is None else at, board))

    def turn_z(self, i):
        """The height where vz crossed zero between samples i-1 and i."""
        (t0, o0, v0), (t1, _, v1) = self.samples[i - 1][:3], self.samples[i][:3]
        f = v0[2] / (v0[2] - v1[2]) if v0[2] != v1[2] else 1.0
        return o0[2] + 0.5 * v0[2] * f * (t1 - t0)


def build():
    m = Motion()
    m.fall(2)                                   # the clock starts: vz +90
    m.fall(7)                                   # ... +6
    # 8.1 u above the file's first sample, 6.5 u above the one before the clock starts
    m.mark("apex 1, in the air", E_APEX, 0, m.fall(1), board=False)
    m.fall(24)                                  # -294
    m.mark("on ramp 1", E_LAND, AIR * 4 + RAMP, m.tick(25, dvx=-20, ramp=True))
    m.tick(25, dvx=-20, ramp=True, n=10)        # -19
    m.tick(25, dvx=-20, ramp=True)              # +6: a first bottom...
    m.tick(-11, dvx=-1, ramp=True, n=2)         # -5, -16: a wobble a fifth of a unit deep
    m.mark("bottom 1, the lower of two a wobble apart", E_TROUGH, 0, m.tick(25, dvx=-20, ramp=True))    # +9
    last = m.tick(25, dvx=-20, ramp=True, n=8)  # +209
    m.fall(5)                                   # the hold's five ticks
    m.mark("off ramp 1, stamped at its last contact", E_LEAVE, RAMP * 4 + AIR, m.fall(1), at=last)
    m.fall(11)                                  # +5
    m.mark("apex 2, in the air", E_APEX, 0, m.fall(1))
    m.fall(14)                                  # -175
    # landing on an upslope: this one tick turns vz up.  The landing's mark only.
    m.mark("on ramp 2 (the turn up is this mark's)", E_LAND, AIR * 4 + RAMP, m.tick(211, dvx=-150, ramp=True))
    m.tick(0, dvx=-1, ramp=True, n=20)          # +36 held: 10.8 u of climb
    m.tick(-8, dvx=-1, ramp=True, n=4)          # +4
    m.mark("apex 3, slow, on the ramp", E_APEX, 0, m.tick(-8, dvx=-1, ramp=True))
    for k in range(6):                          # -4, then +3 -3 +3 -3 +3 -3: noise
        m.tick(7 if k == 0 else (-6 if k % 2 else 6), dvx=-1, ramp=True)
    m.tick(-10, dvx=-1, ramp=True, n=10)        # -103
    m.tick(20, dvx=-5, ramp=True, n=5)          # -3
    m.mark("bottom 2, on the ramp", E_TROUGH, 0, m.tick(20, dvx=-5, ramp=True))
    m.tick(20, dvx=-5, ramp=True, n=4)          # +97
    last = m.tick(-10, dvx=-1, ramp=True, n=8)  # +17
    m.fall(1)                                   # +5, in the hold
    gap = m.fall(1)                             # -7: the turn, still in the hold
    m.fall(3)
    edge = m.fall(1)                            # the hold ran out
    m.mark("off ramp 2, stamped at its last contact", E_LEAVE, RAMP * 4 + AIR, edge, at=last)
    m.mark("apex 4, in the hold after that contact", E_APEX, 0, gap)
    m.fall(10)                                  # -175
    m.mark("on the ground", E_LAND, AIR * 4 + GROUND, m.tick(0, ground=True))
    m.tick(0, ground=True, n=3)
    m.tick(0, ground=True, jump=True)
    m.v[2] = 270.0
    m.mark("a jump (not a bottom)", E_JUMP, GROUND * 4 + AIR, m.fall(1))    # +258
    m.fall(21)                                  # +6
    m.fall(6)                                   # over the top and 2.7 u down: -66
    # ...onto a ledge 3 u under that top.  It is not 8 u clear of where the body
    # went next, and standing there starts the count again: the fall off the ledge
    # afterwards must not mark it either.
    m.mark("onto a ledge 3 u under the top (no top)", E_LAND, AIR * 4 + GROUND, m.tick(0, ground=True))
    m.tick(0, ground=True, n=3)
    m.mark("off the ledge", E_LEAVE, GROUND * 4 + AIR, m.fall(1))           # -12
    m.fall(20)                                  # 40 u down: -252
    m.v[2] = 48.0                               # a teleport, arriving still rising a little:
    m.mark("a teleport", E_BREAK, 0, m.tick(-STEP, move=(3000.0, 0.0, 0.0)))    # +36
    m.fall(13)                                  # ...0.8 u more, then down to -120: no top
    m.v[2] = 212.0                              # a save loaded: elsewhere, and rising
    i = m.tick(-STEP, move=(-3000.0, 500.0, 0.0), record="resume 1 400")    # +200
    m.mark("a loaded save: the break", E_BREAK, 0, i)
    m.mark("a loaded save: the stitch (not a bottom)", E_STITCH, 0, i)
    m.fall(16)                                  # +8
    m.mark("apex 5, in the air, 25 u above the load", E_APEX, 0, m.fall(1))
    m.fall(3)                                   # -40, 1 u under that top...
    # ...and onto a ramp there.  The top stands 8 u clear only some way down the ramp,
    # so it is marked AFTER this landing and has to go in front of it.
    m.mark("on ramp 3, 1 u under apex 5", E_LAND, AIR * 4 + RAMP, m.tick(-2, dvx=-5, ramp=True))
    m.tick(-5, dvx=-2, ramp=True, n=14)         # -112
    m.tick(28, dvx=-10, ramp=True, n=4)         # -84 -56 -28, and exactly 0 on a sample
    m.mark("bottom 3, on a sample whose vz is exactly 0", E_TROUGH, 0, m.tick(28, dvx=-10, ramp=True))    # +28
    last = m.tick(28, dvx=-10, ramp=True, n=3)  # +112
    m.fall(5)
    m.mark("off ramp 3, stamped at its last contact", E_LEAVE, RAMP * 4 + AIR, m.fall(1), at=last)    # +40
    m.fall(3)                                   # +4
    m.mark("apex 6, in the air", E_APEX, 0, m.fall(1))
    m.fall(10)                                  # 10 u down: -128
    # LN_EVDZ from both sides.  A teleport starts the count at its arrival: from
    # there the body rises 7.4 u and falls (no top), then 8.6 u and falls (a top).
    m.v[2] = 121.0
    m.mark("a second teleport", E_BREAK, 0, m.tick(-STEP, move=(3000.0, 0.0, 0.0)))     # +109
    m.fall(10)                                  # over a top 7.4 u up: -11
    m.fall(12)                                  # 13 u down: -155
    m.v[2] = 129.0
    m.mark("a third teleport", E_BREAK, 0, m.tick(-STEP, move=(-3000.0, 0.0, 0.0)))     # +117
    m.fall(9)                                   # +9
    m.mark("apex 7, 8.6 u above a teleport's arrival", E_APEX, 0, m.fall(1))            # -3
    m.fall(12)                                  # 13 u down: -147
    # A landing whose own sample still falls; the next one turns up.  The bottom
    # between the two is the landing's: no second mark, and it still alternates.
    m.mark("on ramp 4, still falling", E_LAND, AIR * 4 + RAMP, m.tick(100, dvx=-60, ramp=True))   # -47
    m.tick(100, dvx=-60, ramp=True)             # +53
    m.tick(0, dvx=-1, ramp=True, n=14)          # +53 held: 11 u of climb
    m.tick(-9, dvx=-1, ramp=True, n=5)          # +8
    m.mark("apex 8, on ramp 4, after the landing's bottom", E_APEX, 0, m.tick(-9, dvx=-1, ramp=True))   # -1
    m.tick(-9, dvx=-1, ramp=True, n=13)         # 11 u down: -118
    m.mark("on the ground, off ramp 4", E_LAND, RAMP * 4 + GROUND, m.tick(0, ground=True))
    m.tick(0, ground=True, n=3)
    m.tick(0, ground=True, jump=True)
    m.v[2] = 276.0
    m.mark("a second jump", E_JUMP, GROUND * 4 + AIR, m.fall(1))                        # +264
    # Its top is on a sample (vz exactly 0), and the ledge it lands on is 8.1 u
    # under it while the last air sample is 7.3 u under: the landing marks the top.
    m.mark("apex 9, 8.1 u above the ledge it lands on", E_APEX, 0, m.fall(22))
    m.fall(9)                                   # -108
    m.mark("onto the ledge", E_LAND, AIR * 4 + GROUND, m.tick(0, ground=True))
    m.tick(0, ground=True, n=2)
    return m


def text(m, foreign):
    head = ["FTESURF-REC 5" if foreign else "FTESURF-REC 9", "tickrate %g" % TICK,
            "movetickrate %g" % TICK, "clock counted"]
    if foreign:
        head += ["foreign momentum fixture", "momdemo 0", "flags 0"]
    out = head + ["begin"]
    for t, o, v, ground, jump, ramp, record in m.samples:
        if record:
            out.append(record)
        fl = (1 if ground else 0) | (4 if jump else 0) | (16 if ramp and not foreign else 0)
        plane = "0.8000 0.0000 0.6000" if ramp and not foreign else "0.0000 0.0000 0.0000"
        out.append("%.4f %.2f %.2f %.2f %.2f %.2f %.2f 0.0 0.0 %d 0 0 0 0 %s"
                   % ((t,) + o + v + (fl, plane)))
    return "\n".join(out) + "\n"


def expected(path, board=False):
    """The marks, each (what, kind, sub, t, ordinal, z, sideways speed, vz, edge clock, x, y),
    from the FILE's own numbers: a turnaround where vz crossed zero between its two samples.
    board: as a board line of the whole file marks it (see apex 1)."""
    rows = [l.split() for l in Path(path).read_text().split("begin\n", 1)[1].splitlines()
            if l[:1].isdigit() or l[:1] == "-"]
    num = lambda i, c: float(rows[i][c])
    out = []
    for what, kind, sub, i, at, on_board in build().want:
        if board and not on_board:
            continue
        if kind in (E_APEX, E_TROUGH):
            pvz, vz = num(i - 1, 6), num(i, 6)
            f = pvz / (pvz - vz)
            dt = num(i, 0) - num(i - 1, 0)
            vx = num(i - 1, 4) + (num(i, 4) - num(i - 1, 4)) * f
            vy = num(i - 1, 5) + (num(i, 5) - num(i - 1, 5)) * f
            out.append((what, kind, sub, num(i - 1, 0) + f * dt, i,
                        num(i - 1, 3) + 0.5 * pvz * f * dt, (vx * vx + vy * vy) ** 0.5, 0.0, num(i, 0),
                        num(i - 1, 1) + (num(i, 1) - num(i - 1, 1)) * f,
                        num(i - 1, 2) + (num(i, 2) - num(i - 1, 2)) * f))
        else:
            out.append((what, kind, sub, num(at, 0), at, num(at, 3),
                        (num(at, 4) ** 2 + num(at, 5) ** 2) ** 0.5, num(at, 6), num(i, 0),
                        num(at, 1), num(at, 2)))
    out.sort(key=lambda w: w[3])        # the table is in time order; a tie keeps the order made
    return out


def breaks_of(want):
    return {w[4] for w in want if w[1] == E_BREAK}


class Model(unittest.TestCase):
    """No game: the fixtures are the generator's, and tools/p449mark.py agrees with the construction."""

    def test_tracked_fixtures_are_the_generators(self):
        m = build()
        for foreign, path in FIXTURES.items():
            self.assertTrue(path.is_file(), "%s is missing: run --write" % path.name)
            self.assertEqual(path.read_text(), text(m, foreign), "%s is not what build() writes" % path.name)

    def test_the_construction_has_every_case(self):
        m = build()
        kinds = [w[1] for w in m.want]
        self.assertEqual(kinds.count(E_APEX), 9)
        self.assertEqual(kinds.count(E_TROUGH), 3)
        self.assertEqual((kinds.count(E_LAND), kinds.count(E_LEAVE), kinds.count(E_JUMP),
                          kinds.count(E_BREAK), kinds.count(E_STITCH)), (8, 4, 2, 4, 1))

    def test_the_construction_stands_where_it_says(self):
        """The clearances the cases are named for, from the generator's own numbers."""
        m = build()
        z = lambda i: m.samples[i][1][2]
        at = {w[0].split(",")[0]: w[3] for w in m.want}
        # apex 1: over 8 u above the first sample (a replay marks it), under 8 above the seed
        top = m.turn_z(at["apex 1"])
        self.assertGreater(top - z(0), 8.05)
        self.assertLess(top - z(1), 7.0)
        # the two teleports: the top after each, above its arrival sample
        a, b = at["a second teleport"], at["a third teleport"]
        low = m.turn_z(a + 10)
        self.assertTrue(7.3 < low - z(a) < 7.6, low - z(a))
        self.assertGreater(z(a + 10) - z(a + 22), 10)       # and it fell far enough to be marked, if it counted
        high = m.turn_z(at["apex 7"])
        self.assertTrue(8.4 < high - z(b) < 8.7, high - z(b))
        # the landing whose own sample still falls, and whose next one turns up
        land = at["on ramp 4"]
        self.assertLess(m.samples[land][2][2], 0)
        self.assertGreater(m.samples[land + 1][2][2], 0)
        # apex 9: on a sample, the last air sample under 8 u below it, the ledge over 8
        top, ledge = at["apex 9"], at["onto the ledge"]
        self.assertEqual(m.samples[top][2][2], 0.0)
        self.assertTrue(7.0 < z(top) - z(ledge - 1) < 7.9, z(top) - z(ledge - 1))
        self.assertTrue(8.05 < z(top) - z(ledge) < 8.5, z(top) - z(ledge))
        # bottom 3: the sample before its mark's has vz exactly 0
        self.assertEqual(m.samples[at["bottom 3"] - 1][2][2], 0.0)

    def check_model(self, foreign, board=False):
        path = FIXTURES[foreign]
        want = expected(path, board=board)
        bits = None
        if foreign:
            keys, rows = rampinfer.read(path)
            bits, step, _, _, why = rampinfer.verdict(keys, rows)
            self.assertEqual((why, step), ("", STEP))
            self.assertEqual(bits, [s[5] for s in build().samples], "the inferred contact is not the constructed one")
        # A board line of the whole file: the last sample before the clock starts seeds it.
        seed = SEED if board else None
        brk = {b - SEED - 1 for b in breaks_of(want)} if board else breaks_of(want)
        got, n = p449mark.derive(str(path), brk, bits=bits, seed=seed)
        self.assertEqual(n, len(build().samples) - (SEED + 1 if board else 0))
        compare(self, [g + (None,) * 3 for g in got], want, "model", model=True, shift=SEED + 1 if board else 0)

    def test_model_marks_the_native_file(self):
        self.check_model(False)

    def test_model_marks_the_import(self):
        self.check_model(True)

    def test_model_marks_a_board_line_without_apex_1(self):
        self.check_model(False, board=True)
        self.check_model(True, board=True)
        self.assertEqual(len(expected(FIXTURES[False])) - len(expected(FIXTURES[False], board=True)), 1)


def compare(test, got, want, who, model=False, shift=0):
    """got: (kind, sub, t, ordinal, speed, v.v, vz, edge clock, z, x, y), the last three None for the model."""
    names = [w[0] for w in want]
    test.assertEqual([(g[0], g[1]) for g in got], [(w[1], w[2]) for w in want],
                     "%s: the marks, in order, are not %s" % (who, names))
    for g, w in zip(got, want):
        what = "%s: %s" % (who, w[0])
        test.assertEqual(g[3], w[4] - shift, what + ": the sample")
        test.assertAlmostEqual(g[2], w[3], delta=0.0002, msg=what + ": the time")
        test.assertAlmostEqual(g[4], w[6], delta=0.02, msg=what + ": the sideways speed")
        test.assertAlmostEqual(g[6], w[7], delta=0.02, msg=what + ": vz")
        test.assertAlmostEqual(g[7], w[8], delta=0.0002, msg=what + ": the edge's clock")
        if not model:
            test.assertAlmostEqual(g[8], w[5], delta=0.02, msg=what + ": the height")
            test.assertAlmostEqual(g[9], w[9], delta=0.02, msg=what + ": x")
            test.assertAlmostEqual(g[10], w[10], delta=0.02, msg=what + ": y")


class Section:
    def __init__(self, body):
        self.slots, slot = {}, None
        for line in body.splitlines():
            line = re.sub(r"^\d{4}-\d\d-\d\d \d\d:\d\d:\d\d ", "", line.strip())
            f = line.split()
            if line.startswith("lnmb "):
                slot = int(float(f[1]))
                self.slots[slot] = {"marks": [], "text": [], "inf": None}
            elif line.startswith("lnm ") and slot is not None:
                self.slots[slot]["marks"].append((int(float(f[2])), int(float(f[3])), float(f[4]), int(float(f[5])),
                                                  float(f[9]), float(f[10]), float(f[11]), float(f[12]), float(f[8]),
                                                  float(f[6]), float(f[7])))
            elif line.startswith("lnml ") and slot is not None:
                self.slots[slot]["text"].append(line.split(" ", 2)[2].strip('"'))
            elif line.startswith("lnmi ") and slot is not None:
                self.slots[slot]["inf"] = int(float(f[2]))
        m = re.search(r'"hud_lines_nums" is "([^"]*)"', body)
        self.nums = m.group(1) if m else None
        self.drawn = [(int(m[1]), m[2]) for m in re.finditer(r'lndm 0 (\d+) [-\d.]+ [-\d.]+ [-\d.]+ (".*?"|-)\s*$', body, re.M)]


class Run:
    def __init__(self, log):
        text_ = log.read_text(errors="replace")
        self.complete = "RUNLINES COMPLETE" in text_
        parts = re.split(r"==== ([A-Z]+) ====", text_)
        self.s = {name: Section(body) for name, body in zip(parts[1::2], parts[2::2])}

    def why_not(self, need):
        if not self.complete:
            return "the run did not finish"
        for name, slots in need:
            if name not in self.s:
                return "no %s section" % name
            for slot in slots:
                if slot not in self.s[name].slots:
                    return "the %s section printed no marks for slot %d" % (name, slot)
        return None


class Game(unittest.TestCase):
    subject = control = None

    def setUp(self):
        if self.subject is None:
            self.skipTest("no --log")

    def test_native_marks(self):
        got = self.subject.s["NATIVE"].slots[0]
        compare(self, got["marks"], expected(FIXTURES[False]), "native")
        self.assertEqual(got["inf"], 0)
        self.assertFalse([t for t in got["text"] if t.startswith("~")])

    def test_import_marks_are_the_same(self):
        nat, imp = self.subject.s["NATIVE"].slots[0], self.subject.s["IMPORT"].slots[0]
        compare(self, imp["marks"], expected(FIXTURES[True]), "import")
        self.assertEqual(imp["inf"], 1, "the import's contact was not inferred")
        self.assertEqual(len(nat["marks"]), len(imp["marks"]))
        for a, b in zip(nat["marks"], imp["marks"]):
            self.assertEqual(a[:2] + (a[3],), b[:2] + (b[3],))
            for x, y in zip(a[2:], b[2:]):
                self.assertAlmostEqual(x, y, delta=0.0002, msg="a native and an import mark differ")
        edges = [t for m, t in zip(imp["marks"], imp["text"]) if m[0] in (E_LAND, E_LEAVE) and RAMP in (m[1] // 4, m[1] % 4)]
        made = [w for w in build().want if w[1] in (E_LAND, E_LEAVE) and RAMP in (w[2] // 4, w[2] % 4)]
        self.assertEqual(len(edges), len(made))
        self.assertGreater(len(made), 3)
        self.assertTrue(all(t.startswith("~") for t in edges))

    def test_board_lines_mark_the_same(self):
        for name, slot, foreign in (("NATIVE", 1, False), ("IMPORT", 2, True)):
            got = self.subject.s[name].slots[slot]["marks"]
            compare(self, got, expected(FIXTURES[foreign], board=True), "%s board line" % name.lower(),
                    shift=SEED + 1)

    def test_labels_are_on_by_default_and_drawn(self):
        sec = self.subject.s["NATIVE"]
        self.assertEqual(sec.nums, "2", "hud_lines_nums does not read 2 by default")
        peaks = [lab for k, lab in sec.drawn if k in (E_APEX, E_TROUGH)]
        print("\n  drawn in the frames traced: %d marks, %d of them tops and bottoms (%d with a number)"
              % (len(sec.drawn), len(peaks), sum(1 for p in peaks if p != "-")))
        self.assertGreater(sum(1 for p in peaks if p != "-"), 0, "no top or bottom drew its number")
        text_ = sec.slots[0]["text"]
        self.assertTrue(all(t for t in text_), "a mark has no label text")

    def test_control_lacks_the_new_marks(self):
        got = self.control.s["NATIVE"].slots[0]["marks"]
        kinds = [g[0] for g in got]
        print("\n  control: %d apexes, %d bottoms (the patch: 9 and 3)" % (kinds.count(E_APEX), kinds.count(E_TROUGH)))
        self.assertEqual(kinds.count(E_TROUGH), 0, "the control already marks a bottom on a ramp")
        self.assertLess(kinds.count(E_APEX), 9)


def usage(parser):
    def error(message):
        parser.print_usage(sys.stderr)
        sys.stderr.write("%s: error: %s\n" % (parser.prog, message))
        sys.exit(64)
    return error


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.error = usage(ap)
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--log", type=Path)
    ap.add_argument("--control-log", type=Path)
    args = ap.parse_args()
    if args.write:
        m = build()
        for foreign, path in FIXTURES.items():
            with open(path, "w", encoding="utf-8", newline="\n") as fh:
                fh.write(text(m, foreign))
            print("wrote %s: %d samples, %d bytes" % (path.name, len(m.samples), os.path.getsize(path)))
        sys.exit(0)
    if args.log or args.control_log:
        if not (args.log and args.control_log):
            ap.error("--log and --control-log go together: a grader that cannot be shown failing shows nothing")
        for name, path, need in (("subject", args.log, (("NATIVE", (0, 1)), ("IMPORT", (0, 2)))),
                                 ("control", args.control_log, (("NATIVE", (0,)),))):
            try:
                run = Run(path)
            except OSError as e:
                print(CANNOT + "the %s log cannot be read (%s)" % (name, e))
                sys.exit(2)
            why = run.why_not(need)
            if why:
                print(CANNOT + "the %s log: %s" % (name, why))
                sys.exit(2)
            setattr(Game, name, run)
    unittest.main(argv=["test_runlines_peaks.py"])
