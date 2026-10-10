#!/usr/bin/env python3
"""Unit tests for tools/rampinfer.py, on recordings built here to the tick.

  python tools/test_rampinfer.py

Each case is a few dozen samples whose contact is known by construction.  What
the rule does on real files is --score's and --twin's to say, not this file's.
"""
import os
import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import p449mark  # noqa: E402
import rampinfer  # noqa: E402

TICK = 0.015
STEP = 12.0


class Body:
    """A recording, one sample a tick.  Velocity is post-move, as the importer's."""

    def __init__(self, tick=TICK, t0=0.0):
        self.tick, self.t = tick, t0
        self.o = [0.0, 0.0, 4096.0]
        self.v = [300.0, 0.0, 0.0]
        self.rows = []
        self.put(0)

    def put(self, fl, plane=(0, 0, 0)):
        self.rows.append("%.4f %.2f %.2f %.2f %.2f %.2f %.2f 0.0 0.0 %d 0 0 0 0 %.4f %.4f %.4f"
                         % ((self.t,) + tuple(self.o) + tuple(self.v) + (fl,) + tuple(plane)))

    def tick_(self, dvz, dvx=0.0, fl=0, plane=(0, 0, 0), ticks=1, jump=None):
        """One sample `ticks` mover ticks on: vz moves by dvz, vx by dvx."""
        self.v[2] += dvz
        self.v[0] += dvx
        dt = self.tick * ticks
        for k in range(3):
            self.o[k] += self.v[k] * dt
        if jump:
            self.o = [self.o[k] + jump[k] for k in range(3)]
        self.t += dt
        self.put(fl, plane)
        return len(self.rows) - 1

    def air(self, n, step=STEP):
        return [self.tick_(-step) for _ in range(n)]

    def write(self, folder, name="a.rec", foreign=True, demo=True, extra=()):
        head = ["FTESURF-REC 5", "map unit", "track 0", "startseg 0", "leg 0",
                "tickrate %g" % self.tick, "movetickrate %g" % self.tick, "clock counted"]
        if foreign:
            head.append("foreign momentum unit")
        if demo:
            head.append("momdemo 0000")
        path = os.path.join(folder, name)
        with open(path, "w", encoding="utf-8", newline="\n") as fh:
            fh.write("\n".join(head + list(extra) + ["flags 0", "begin"] + self.rows) + "\n")
        return pathlib.Path(path)


class Rule(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)

    def verdict(self, body, **kw):
        keys, rows = rampinfer.read(body.write(self.dir.name, **kw))
        return rampinfer.verdict(keys, rows) + (rows,)

    def test_free_fall_is_no_contact_and_gives_the_step(self):
        b = Body()
        b.air(60)
        bits, step, nair, share, why, _ = self.verdict(b)
        self.assertEqual((why, step, nair, share, sum(bits)), ("", 12.0, 60, 1.0, 0))

    def test_a_ramp_is_found_to_the_tick(self):
        b = Body()
        b.air(40)
        ride = [b.tick_(-STEP + 3.76, dvx=4.1) for _ in range(30)]
        b.air(40)
        bits, step, _, _, why, rows = self.verdict(b)
        self.assertEqual(why, "")
        self.assertEqual([i for i, x in enumerate(bits) if x], ride)
        self.assertEqual(rampinfer.rides(bits, rows), [(ride[0], ride[-1])])

    def test_a_steep_face_is_above_the_threshold_and_rounding_is_below_it(self):
        b = Body()
        b.air(40)
        steep = b.tick_(-STEP + 0.12, dvx=1.0)          # nz 0.1: step * nz^2
        for _ in range(20):                             # a %.2f column's worst case
            b.tick_(-STEP + 0.01)
            b.tick_(-STEP - 0.01)
        b.tick_(-STEP + 0.04, dvx=1.0)                  # the two values either side of EPS
        over = b.tick_(-STEP + 0.05, dvx=1.0)
        bits = self.verdict(b)[0]
        self.assertEqual([i for i, x in enumerate(bits) if x], [steep, over])

    def test_a_fall_is_counted_to_the_nearest_hundredth(self):
        b = Body()
        b.air(80, step=11.96)                           # no multiple of it is exact in a float
        bits, step, nair, share, why, _ = self.verdict(b)
        self.assertEqual((why, step, nair, share, sum(bits)), ("", 11.96, 80, 1.0, 0))

    def test_the_lowest_fall_wins_a_tie(self):
        b = Body()
        for step in (12.0, 11.25, 12.5):                # neither the first read nor the last
            b.air(40, step=step)
        self.assertEqual(self.verdict(b)[1], 11.25)

    def test_the_movers_tick_is_preferred(self):
        b = Body()
        b.air(60)
        ride = [b.tick_(-STEP + 4.0, dvx=4.0) for _ in range(5)]
        # the header's last word on a key stands: tickrate is now four of these ticks
        bits, step, _, _, why, _ = self.verdict(b, extra=("tickrate %g" % (TICK * 4),))
        self.assertEqual((why, step), ("", 12.0))
        self.assertEqual([i for i, x in enumerate(bits) if x], ride)

    def test_a_wedged_body_is_contact(self):
        b = Body()
        b.air(40)
        b.v = [0.0, 0.0, -6.0]
        still = [b.tick_(0.0) for _ in range(25)]
        bits = self.verdict(b)[0]
        self.assertTrue(all(bits[i] for i in still))

    def test_a_floor_touched_for_a_tick_is_not_a_ramp(self):
        b = Body()
        b.air(60)
        flat = b.tick_(700.0)                           # vz zeroed, nothing sideways
        b.air(30)
        sideways = b.tick_(400.0, dvx=2.0)              # the same shove with a sideways part
        soft = b.tick_(-STEP + 29.76)                   # 2.48 steps, under FLAT: kept
        b.air(10)
        hard = b.tick_(-STEP + 31.2)                    # 2.6 steps, nothing sideways
        b.air(10)
        nearly = b.tick_(-STEP + 31.2, dvx=0.49)        # either side of FLATH
        b.air(10)
        turned = b.tick_(-STEP + 31.2, dvx=0.51)
        b.air(10)
        bits = self.verdict(b)[0]
        self.assertFalse(bits[flat])
        self.assertTrue(bits[sideways])
        self.assertTrue(bits[soft])
        self.assertEqual((bits[hard], bits[nearly], bits[turned]), (False, False, True))

    def test_a_push_down_is_not_looked_for(self):
        b = Body()
        b.air(40)
        down = [b.tick_(-STEP - 40.0, dvx=30.0) for _ in range(5)]
        b.air(10)
        bits = self.verdict(b)[0]
        self.assertFalse(any(bits[i] for i in down))

    def test_ground_is_never_a_ramp(self):
        b = Body()
        b.air(40)
        # The pushes a ramp would give (under FLAT steps, with a sideways part), so
        # that only the flag refuses them: on the sample itself, then the one before.
        land = b.tick_(-STEP + 20.0, dvx=6.0, fl=1)
        walk = [b.tick_(0.0, fl=1) for _ in range(10)]
        hop = b.tick_(-STEP + 20.0, dvx=6.0)            # the tick that leaves it
        b.air(10)
        free = b.tick_(-STEP + 20.0, dvx=6.0)           # the same push with no ground beside it
        bits = self.verdict(b)[0]
        self.assertFalse(any(bits[i] for i in [land] + walk + [hop]))
        self.assertTrue(bits[free])

    def test_the_step_is_read_and_not_assumed(self):
        b = Body()
        b.air(60, step=11.25)                           # gravity 750
        ride = [b.tick_(-11.25 + 5.0, dvx=6.0) for _ in range(10)]
        bits, step, _, _, why, _ = self.verdict(b)
        self.assertEqual((why, step), ("", 11.25))
        self.assertEqual([i for i, x in enumerate(bits) if x], ride)

    def test_a_teleport_and_a_gap_are_not_judged(self):
        b = Body()
        b.air(40)
        tele = b.tick_(300.0, dvx=5.0, jump=(0, 0, 5000.0))
        b.air(10)
        gap = b.tick_(-5.0, dvx=5.0, ticks=2)           # read as one tick it would be a push of 7
        b.air(10)
        nudge = b.tick_(-STEP + 4.0, dvx=4.0, jump=(0, 0, 30.0))    # inside the fit's 64 u: judged
        b.air(10)
        bits = self.verdict(b)[0]
        self.assertFalse(bits[tele])
        self.assertFalse(bits[gap])
        self.assertTrue(bits[nudge])

    def test_one_tick_is_from_half_to_one_and_a_half(self):
        b = Body()
        b.air(40)
        got = []
        for ticks in (0.49, 0.51, 1.49, 1.51):          # the same push, four clocks
            got.append(b.tick_(-5.0, dvx=5.0, ticks=ticks))
            b.air(10)
        bits = self.verdict(b)[0]
        self.assertEqual([bits[i] for i in got], [False, True, True, False])

    def test_too_long_a_run_is_unavailable(self):
        b = Body()
        b.air(40)
        [b.tick_(-STEP + 4.0, dvx=4.0) for _ in range(20)]
        self.addCleanup(setattr, rampinfer, "SCANMAX", rampinfer.SCANMAX)
        rampinfer.SCANMAX = len(b.rows)                 # at the cap: inferred
        self.assertEqual(self.verdict(b)[4], "")
        rampinfer.SCANMAX = len(b.rows) - 1             # one sample over it: no bit, and why
        bits, step, _, _, why, _ = self.verdict(b, name="b.rec")
        self.assertEqual((why, step, sum(bits)), ("over %d samples" % (len(b.rows) - 1), 0.0, 0))

    def test_an_import_without_its_demo_is_unavailable(self):
        b = Body()
        b.air(40)
        [b.tick_(-STEP + 4.0, dvx=4.0) for _ in range(20)]
        bits, step, _, _, why, _ = self.verdict(b, demo=False)
        self.assertEqual((why, step, sum(bits)), ("no per-tick velocity", 0.0, 0))

    def test_too_little_air_is_unavailable(self):
        b = Body()
        b.air(29)                                       # the numbers themselves, not the module's
        self.assertEqual(self.verdict(b)[4], "under 30 airborne pairs")
        b.air(1)
        self.assertEqual(self.verdict(b, name="b.rec")[4], "")

    def test_a_fall_shared_by_a_seventh_of_the_pairs_is_a_step(self):
        b = Body()
        b.air(30)                                       # 30 of 200: 0.15, over the 0.10
        for i in range(170):                            # and 170 that agree on nothing
            b.tick_(-20.0 - 0.07 * i)
        bits, step, nair, share, why, _ = self.verdict(b)
        self.assertEqual((why, step, nair), ("", 12.0, 200))
        self.assertAlmostEqual(share, 0.15)

    def test_no_steady_fall_is_unavailable(self):
        b = Body()
        for i in range(200):                            # two hundred different falls
            b.tick_(-5.0 - 0.07 * i)
        bits, step, nair, share, why, _ = self.verdict(b)
        self.assertEqual((why, step, sum(bits)), ("no fall common enough", 0.0, 0))
        self.assertLess(share, rampinfer.MINSHARE)

    def test_a_native_file_keeps_its_own_bit(self):
        b = Body()
        b.air(40)
        ride = [b.tick_(-STEP + 4.0, dvx=4.0, fl=16, plane=(0.8, 0, 0.6)) for _ in range(5)]
        b.tick_(-STEP + 4.0, dvx=4.0)                   # the rule would call this one too
        bits, step, _, _, why, _ = self.verdict(b, foreign=False)
        self.assertEqual((why, step), ("measured", 0.0))
        self.assertEqual([i for i, x in enumerate(bits) if x], ride)

    def test_rides_join_across_the_hold_and_no_further(self):
        b = Body()
        b.air(40)
        for gap in (5, 6):                              # 0.075 s joins, 0.09 s does not
            b.tick_(-STEP + 4.0, dvx=4.0)
            b.air(gap - 1)
        b.tick_(-STEP + 4.0, dvx=4.0)
        bits, _, _, _, _, rows = self.verdict(b)
        on = [i for i, x in enumerate(bits) if x]
        self.assertEqual(rampinfer.rides(bits, rows), [(on[0], on[1]), (on[2], on[2])])


class Marks(unittest.TestCase):
    """tools/p449mark.py's two additions: inferred bits, and a board line's seed."""

    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        b = Body(t0=-0.15)
        b.air(9)                                        # the approach: samples 0..9, t < 0
        b.air(30)
        self.ride = [b.tick_(-STEP + 4.0, dvx=4.0) for _ in range(20)]
        b.air(40)
        self.path = b.write(self.dir.name)
        keys, rows = rampinfer.read(self.path)
        self.bits = rampinfer.verdict(keys, rows)[0]
        self.rows = rows

    def test_inferred_bits_make_the_ramp_marks(self):
        none, n = p449mark.derive(str(self.path), set())
        self.assertEqual([m for m in none if m[0] in (p449mark.E_LAND, p449mark.E_LEAVE)], [])
        marks, _ = p449mark.derive(str(self.path), set(), bits=self.bits)
        edges = [(m[0], m[1], m[3]) for m in marks if m[0] in (p449mark.E_LAND, p449mark.E_LEAVE)]
        # on at the ride's first tick; off stamped back at its last, the edge seen when the hold ran out
        self.assertEqual(edges, [(p449mark.E_LAND, p449mark.AIR * 4 + p449mark.RAMP, self.ride[0]),
                                 (p449mark.E_LEAVE, p449mark.RAMP * 4 + p449mark.AIR, self.ride[-1])])
        self.assertEqual(n, len(self.rows))

    def test_a_seed_shifts_the_ordinals_and_marks_nothing_itself(self):
        seed = max(i for i, r in enumerate(self.rows) if r[0] < 0)
        marks, n = p449mark.derive(str(self.path), set(), bits=self.bits, seed=seed)
        self.assertEqual(n, len(self.rows) - seed - 1)
        edges = [(m[0], m[3]) for m in marks if m[0] in (p449mark.E_LAND, p449mark.E_LEAVE)]
        self.assertEqual(edges, [(p449mark.E_LAND, self.ride[0] - seed - 1),
                                 (p449mark.E_LEAVE, self.ride[-1] - seed - 1)])

    def test_a_seed_in_the_air_before_a_ride_gives_its_first_tick_the_edge(self):
        # the window opens ON the ride's first tick: the seed's state is what makes it an edge
        seed = self.ride[0] - 1
        marks, _ = p449mark.derive(str(self.path), set(), bits=self.bits, seed=seed)
        edges = [(m[0], m[3]) for m in marks if m[0] in (p449mark.E_LAND, p449mark.E_LEAVE)]
        self.assertEqual(edges, [(p449mark.E_LAND, 0), (p449mark.E_LEAVE, self.ride[-1] - seed - 1)])

    def test_a_seed_on_the_last_contact_tick_arms_the_hold(self):
        # the ride ends ON the seed: its leave is seen when the hold runs out, six ticks on,
        # and stamped at the window's first sample (the ride has no contact inside it)
        seed = self.ride[-1]
        marks, _ = p449mark.derive(str(self.path), set(), bits=self.bits, seed=seed)
        edges = [(m[0], m[3], round(m[7] - self.rows[seed][0], 4)) for m in marks
                 if m[0] in (p449mark.E_LAND, p449mark.E_LEAVE)]
        self.assertEqual(edges, [(p449mark.E_LEAVE, 0, 0.09)])

    def test_a_seed_in_contact_is_not_an_edge(self):
        # the window opens one sample into the ride: the seed is its first tick
        seed = self.ride[0]
        marks, _ = p449mark.derive(str(self.path), set(), bits=self.bits, seed=seed)
        edges = [(m[0], m[3]) for m in marks if m[0] in (p449mark.E_LAND, p449mark.E_LEAVE)]
        self.assertEqual(edges, [(p449mark.E_LEAVE, self.ride[-1] - seed - 1)])


if __name__ == "__main__":
    unittest.main()
