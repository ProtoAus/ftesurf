#!/usr/bin/env python3
"""Grade where the run line stamps a ramp leave (Patch 608), against the recording itself.

  python tools/test_runlines_rampleave.py <rig>/ftesurf/logs/runlines_smoke.log
      [--control-log <the same arm on a build before the patch>]

The log is tools/runlines_smoke.py's, from ftesurf/cfg/test/runlines_rampleave.cfg. Input stays in
the private rig; only counts, times and distances are printed, never positions or the player.

What this fixture can and cannot fail on is printed by the first test: a recording whose rides
are all one shape grades the stamp and nothing else of the rule.
"""
import argparse
import bisect
import math
from pathlib import Path
import re
import statistics
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import p449mark                                     # noqa: E402  (the shared rule)

RAMP_TO_AIR = p449mark.RAMP * 4 + p449mark.AIR
AIR_RGB, RAMP_RGB = (0.85, 0.88, 0.95), (0.35, 0.85, 1.00)


def samples(path):
    """[(t, (x, y, z), flags, (vx, vy, vz))] for every sample of the body, in file order."""
    out, body = [], False
    with open(path, 'r', errors='replace') as fh:
        for line in fh:
            if not body:
                body = line.startswith('begin')
                continue
            if p449mark.is_sample(line):
                f = line.split()
                out.append((p449mark.f32(float(f[0])), tuple(float(x) for x in f[1:4]), int(float(f[9])),
                            tuple(float(x) for x in f[4:7])))
    return out


def marks(text):
    """The client's mark table: dicts in table order."""
    out = []
    for m in re.finditer(r'\blnm ([^\r\n]+)', text):
        f = m[1].split()
        out.append(dict(kind=int(f[1]), sub=int(f[2]), t=float(f[3]), i=int(f[4]),
                        pos=tuple(float(x) for x in f[5:8]), speed=float(f[8]), vz=float(f[10]),
                        edge=float(f[11]) if len(f) > 11 else None))
    return out


def ramp_leaves(table, rows):
    """Each ramp-to-air leave with the sample it is stamped on and the sample its edge fell on."""
    times = [r[0] for r in rows]
    out = []
    for n, m in enumerate(table):
        if m['kind'] != p449mark.E_LEAVE or m['sub'] != RAMP_TO_AIR:
            continue
        # A build before the patch prints no edge clock: its edge IS the stamped sample.
        edge = m['i'] if m['edge'] is None else max(m['i'], bisect.bisect_left(times, m['edge'] - 1e-4))
        out.append(dict(m, n=n, edge_i=edge))
    return out


def dist(a, b):
    return sum((x - y) ** 2 for x, y in zip(a, b)) ** 0.5


LAND, LEAVE, STITCH = p449mark.E_LAND, p449mark.E_LEAVE, p449mark.E_STITCH
# ftesurf/cfg/test/runlines_rampshapes.rec, WRITTEN BY HAND from its 74 samples and the rule, not derived by
# p449mark: (kind, sub-code, the sample stamped, the sample the edge fell on). Sub-code is from * 4 + to,
# ground 0, air 1, ramp 2. The hold is 0.08 s and a sample 0.015 s, so an edge is six samples past a contact.
SHAPES = (
    (LAND, 6, 6, 6), (LEAVE, 9, 6, 12),                      # one sample touches: land and leave share it
    (LAND, 6, 15, 15), (LEAVE, 9, 23, 29),                   # contact 15..18, a 2-sample gap bridged, 21..23
    (LAND, 4, 32, 32), (LAND, 2, 36, 36), (LEAVE, 9, 36, 41),    # ground with the ramp bit at 35, then air: the
                                                             # hold opens a ride at 36 with no contact of its own
    (LAND, 6, 44, 44), (STITCH, 0, 50, 50), (LEAVE, 9, 50, 54),  # contact 44..47, a stitch on a repeated clock
                                                             # at 50: the leave may not go back behind it
    (LAND, 6, 59, 59), (LAND, 8, 63, 63), (LEAVE, 1, 70, 70),    # a ride that ends on ground; a walk-off later
)
SHAPE_CLOCK = lambda i: 1.02 + 0.015 * (i if i < 50 else i - 1)    # sample 50 repeats sample 49's clock


class RampLeave(unittest.TestCase):
    text = control = recording = shapes = None

    @classmethod
    def setUpClass(cls):
        if cls.text is None:
            raise unittest.SkipTest('requires a retained runtime log')
        cls.rows = samples(cls.recording)
        cls.table = marks(cls.text)
        cls.leaves = ramp_leaves(cls.table, cls.rows)

    def test_authored_ride_shapes_are_stamped_as_written(self):
        self.assertIsNotNone(self.shapes, 'the arm did not replay cfg/test/runlines_rampshapes.rec')
        got = marks(self.shapes)
        self.assertEqual([(m['kind'], m['sub'], m['i']) for m in got], [s[:3] for s in SHAPES])
        for m, (_, _, stamp, edge) in zip(got, SHAPES):
            self.assertAlmostEqual(m['t'], SHAPE_CLOCK(stamp), delta=0.001)
            self.assertAlmostEqual(m['edge'], SHAPE_CLOCK(edge), delta=0.001)
        clocks = [m['t'] for m in got]
        self.assertEqual(clocks, sorted(clocks), 'the mark table is not in clock order')

    def test_0_what_this_recording_can_fail_on(self):
        """Not a gate: the shapes of ride the fixture holds, so a pass is read for what it covers."""
        ramp, ground = p449mark.F_RAMP, p449mark.F_ONGROUND
        stamped_without_bit = sum(not self.rows[m['i']][2] & ramp for m in self.leaves)
        one_sample = sum(self.table[m['n'] - 1]['i'] == m['i'] for m in self.leaves)
        both_bits = sum(bool(r[2] & ramp and r[2] & ground) for r in self.rows)
        repeated = sum(a[0] == b[0] for a, b in zip(self.rows, self.rows[1:]))
        gaps, run, seen = 0, 0, False
        for r in self.rows:
            if r[2] & ramp:
                gaps += seen and 0 < run and r[0] - last <= p449mark.RAMP_GAP
                run, seen, last = 0, True, r[0]
            else:
                run += 1
        kinds = [m['kind'] for m in self.table]
        print('shapes here: %d ramp leaves; %d stamped by the no-contact fallback, %d one-sample rides, '
              '%d bridged gaps, %d samples with ground and ramp bits, %d repeated clocks, %d stitches, %d breaks'
              % (len(self.leaves), stamped_without_bit, one_sample, gaps, both_bits, repeated,
                 kinds.count(p449mark.E_STITCH), kinds.count(p449mark.E_BREAK)))

    def test_every_mark_carries_the_clock_of_its_edge(self):
        self.assertTrue(all(m['edge'] is not None for m in self.table), 'no edge clock: a build before the patch')
        for m in self.table:
            if m['kind'] == p449mark.E_LEAVE and m['sub'] == RAMP_TO_AIR:
                self.assertGreaterEqual(m['edge'], m['t'] - 1e-4)
            else:
                self.assertAlmostEqual(m['edge'], m['t'], delta=1e-4)

    def test_marks_match_the_recording_under_the_new_rule(self):
        breaks = {m['i'] for m in self.table if m['kind'] == p449mark.E_BREAK}
        want, count = p449mark.derive(str(self.recording), breaks)
        self.assertEqual((count, len(self.table)), (len(self.rows), len(want)))
        for got, w in zip(self.table, want):
            self.assertEqual((got['kind'], got['sub'], got['i']), (w[0], w[1], w[3]))
            self.assertAlmostEqual(got['t'], w[2], delta=0.0002)
            self.assertAlmostEqual(got['t'] if got['edge'] is None else got['edge'], w[7], delta=0.0002)

    def test_a_ramp_leave_sits_on_the_rides_last_real_contact(self):
        self.assertGreaterEqual(len(self.leaves), 10, 'too few ramp exits to say anything')
        moved, late = [], []
        for m in self.leaves:
            t, pos, fl, vel = self.rows[m['i']]
            opened = self.table[m['n'] - 1]
            touched = bool(fl & p449mark.F_RAMP)
            with self.subTest(t=round(m['t'], 3)):
                # The stamped sample touched the ramp, or the ride has no contact of its own and it is
                # the sample that opened it.
                self.assertTrue(touched or opened['i'] == m['i'])
                # The mark IS that sample: clock, position and velocity.
                self.assertAlmostEqual(m['t'], t, delta=0.0002)
                self.assertLess(dist(m['pos'], pos), 0.02)
                self.assertAlmostEqual(m['speed'], math.hypot(vel[0], vel[1]), delta=0.01)
                self.assertAlmostEqual(m['vz'], vel[2], delta=0.01)
                # No later sample of the ride touched it.
                self.assertGreater(m['edge_i'], m['i'])
                self.assertFalse(any(r[2] & p449mark.F_RAMP for r in self.rows[m['i'] + 1:m['edge_i'] + 1]))
                if touched:
                    # The hold runs from that contact: out at the edge sample, and not one sample sooner.
                    self.assertGreater(self.rows[m['edge_i']][0] - t, p449mark.RAMP_GAP - 1e-4)
                    self.assertLessEqual(self.rows[m['edge_i'] - 1][0] - t, p449mark.RAMP_GAP + 1e-4)
            moved.append(dist(self.rows[m['edge_i']][1], pos))
            late.append(self.rows[m['edge_i']][0] - t)
        print('%d ramp leaves, each on its ride\'s last real contact; the hold ran out %.3f s later (%.3f..%.3f), '
              '%.0f units further on (median; %.0f..%.0f)'
              % (len(moved), statistics.median(late), min(late), max(late),
                 statistics.median(moved), min(moved), max(moved)))

    def test_the_contact_colour_ends_where_the_leave_is(self):
        block = self.text.split('p452col C1 contact')[-1]
        head = re.search(r'lncb 0 2 (\d+) 1\b', block)
        self.assertIsNotNone(head, 'no every-point contact colour dump')
        self.assertEqual(int(head[1]), len(self.rows), 'points are not the samples: the line decimated')
        colour = {int(m[1]): tuple(float(x) for x in m.group(2, 3, 4))
                  for m in re.finditer(r'lnc (\d+) [\d.-]+ ([\d.]+) ([\d.]+) ([\d.]+)', block)}
        near = lambda a, b: all(abs(x - y) <= 0.02 for x, y in zip(a, b))
        tail = ride = 0
        for m in self.leaves:
            for i in range(m['i'], m['edge_i'] + 1):
                tail += 1
                self.assertTrue(near(colour[i], AIR_RGB), 'point %d after a leave is not drawn as air' % i)
            opened = self.table[m['n'] - 1]
            for i in range(opened['i'], m['i']):
                ride += 1
                self.assertTrue(near(colour[i], RAMP_RGB), 'point %d inside a ride is not drawn as ramp' % i)
        self.assertGreater(tail, 5 * len(self.leaves) // 2)
        self.assertGreater(ride, tail)
        print('%d points between a leave and its hold running out are drawn as air; %d ride points as ramp'
              % (tail, ride))

    def test_a_segment_row_starts_on_a_marks_edge_and_not_on_its_stamp(self):
        rate = re.search(r'lnsb \d+ ([\d.]+)', self.text)
        rows = [(int(m[1]), int(m[2])) for m in re.finditer(r'\blns \d+ (\d+) \S+ (\d+) ', self.text)]
        self.assertIsNotNone(rate)
        self.assertGreater(len(rows), 10)
        tick = lambda clock: int(clock / float(rate[1]))
        # True of a build before the patch as well: there the edge and the stamp are one sample.
        edges = {tick(m['t'] if m['edge'] is None else m['edge']) for m in self.table
                 if m['kind'] in (p449mark.E_LAND, p449mark.E_LEAVE, p449mark.E_JUMP)}
        self.assertEqual([t for _, t in rows if t > 0 and t not in edges], [])
        # The patch's own half: a row starts where the hold ran out, which is no longer where the leave is.
        starts = {t for _, t in rows}
        on_a_start = sum(tick(m['t']) in starts for m in self.leaves)
        self.assertLess(on_a_start * 2, len(self.leaves), 'the leaves are still stamped where their rows start')
        print('%d of %d ramp leaves are stamped on a tick a segment row starts on' % (on_a_start, len(self.leaves)))

    def test_a_build_before_the_patch_is_refused(self):
        if self.control is None:
            self.skipTest('no --control-log')
        table = marks(self.control)
        old = ramp_leaves(table, self.rows)
        self.assertEqual(len(old), len(self.leaves))
        self.assertTrue(all(m['edge'] is None for m in table))
        on_contact = [m for m in old if self.rows[m['i']][2] & p449mark.F_RAMP]
        self.assertEqual(on_contact, [], 'the control build already stamps a leave on a contact sample')
        # The same ride in both builds: the old stamp is the sample the new build names as its edge.
        self.assertEqual([m['i'] for m in old], [m['edge_i'] for m in self.leaves])
        moved = [dist(self.rows[a['i']][1], self.rows[b['i']][1]) for a, b in zip(old, self.leaves)]
        print('control: %d of %d ramp leaves on a contact sample; the patch moves each back %.0f units '
              '(median; %.0f..%.0f)' % (len(on_contact), len(old), statistics.median(moved), min(moved), max(moved)))


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('log', type=Path)
    ap.add_argument('--control-log', type=Path)
    args = ap.parse_args()
    def fixtures(path):
        """{recording path: the log from its FIXTURE line to the next}; the arm must have finished."""
        text = path.read_text(errors='replace')
        if 'RUNLINES COMPLETE' not in text:
            raise SystemExit('The arm did not finish: %s' % path)
        parts = re.split(r'=== p449mark FIXTURE (\S+) ===', text)
        return dict(zip(parts[1::2], parts[2::2]))

    blocks = fixtures(args.log)
    RampLeave.text = blocks.get('cfg/test/runlines_sample.rec')
    RampLeave.shapes = blocks.get('cfg/test/runlines_rampshapes.rec')
    if args.control_log:
        RampLeave.control = fixtures(args.control_log).get('cfg/test/runlines_sample.rec')
    RampLeave.recording = args.log.parent.parent / 'cfg/test/runlines_sample.rec'
    unittest.main(argv=['test_runlines_rampleave.py'], verbosity=2)
