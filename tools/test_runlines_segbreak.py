#!/usr/bin/env python3
"""Grade the replay's Segments rows around a teleport (Patch 613) on an authored recording.

  python tools/test_runlines_segbreak.py <rig>/ftesurf/logs/runlines_smoke.log
      --control-log <the same arm on a build before the patch>

The log is tools/runlines_smoke.py's, from ftesurf/cfg/test/runlines_segbreak.cfg. Its recording,
ftesurf/cfg/test/runlines_segbreak.rec, is authored: 155 samples a tick (0.015 s) apart, sample i at
tick 67 + i. The tables below are WRITTEN BY HAND from that body and the rule, not read off a build:

  samples 0..19    standing on ground
  sample 20        A: moved 300 u along and 200 u up, into the air (a break: no move makes that step)
  samples 21..59   a plain fall; 60..71 ground
  samples 72..91   off the ground and through the air; 92..111 a ramp ride; 112..113 off it, bit clear
  sample 114       B: moved 150 u along and 60 u down, 0.045 s after the last contact (a break)
  samples 115..129 a fall
  sample 130       C: moved 160 u up in mid-air, its speed along cut from 300 to 100 u/s (a break)
  samples 131..144 the fall goes on; 145..154 ground

The rule: where the run line breaks, the held ride ends, the launch point is forgotten and the energy
step across the break -- height and speed both -- is charged to no row. Every teleport here is under
the 512 u the segment machine notices by itself. So each of the three rows a teleport touches is a
body in free flight or on a level ride that gained nothing, and the ramp row ends on B's tick.
Before: the fall after A was a hop measured from the ground left behind (+196 at 89%), the ramp row
ran on to where the 0.08 s hold expired three ticks after B and took B's 60 u, and the fall after it
took C's step (160 u of height less 50 of speed).

The control log is required: a grader for a display rule that cannot be shown failing shows nothing.
"""
import argparse
from pathlib import Path
import re
import unittest

LAND, LEAVE, JUMP, BREAK = 1, 2, 3, 7
AIR, RAMP = 1, 2                       # a row's kind
TICK0 = 67                             # sample i is tick TICK0 + i
MARKS = ((BREAK, 0, 20), (LAND, 4, 60), (LEAVE, 1, 72), (LAND, 6, 92), (BREAK, 0, 114), (BREAK, 0, 130),
         (LAND, 4, 145))
# kind, the sample the row ends on, its length in samples, and whether a teleport touched it
ROWS = ((AIR, 60, 40, True), (AIR, 92, 20, False), (RAMP, 114, 22, True), (AIR, 145, 31, True))
NOTHING = 10                           # energy, in units of height: free flight here drifts under 4


def parse(text):
    marks = [(int(f[1]), int(f[2]), int(f[4]), float(f[3]))
             for f in (m[1].split() for m in re.finditer(r'\blnm ([^\r\n]+)', text))]
    rows = [dict(kind=int(f[1]), sub=int(f[2]), tick=int(float(f[3])), dur=float(f[4]), de=float(f[5]))
            for f in (m[1].split() for m in re.finditer(r'\blns ([^\r\n]+)', text))]
    return marks, rows


class SegBreak(unittest.TestCase):
    text = control = None

    @classmethod
    def setUpClass(cls):
        cls.marks, cls.rows = parse(cls.text)

    def test_the_fixture_was_read_as_written(self):
        self.assertIn('runlines_segbreak.rec', self.text)
        self.assertEqual([m[:3] for m in self.marks], list(MARKS))
        self.assertEqual([r['kind'] for r in self.rows], [k for k, _, _, _ in ROWS])

    def test_rows_end_where_written_and_on_a_mark(self):
        ticks = {TICK0 + i for kind, _, i, _ in self.marks if kind in (LAND, LEAVE, JUMP, BREAK)}
        for row, (_, end, length, _) in zip(self.rows, ROWS):
            self.assertEqual(row['tick'], TICK0 + end)
            self.assertAlmostEqual(row['dur'], length * 0.015, delta=0.001)
            self.assertIn(row['tick'], ticks)

    def test_no_row_is_charged_a_teleport(self):
        for row, (kind, end, _, touched) in zip(self.rows, ROWS):
            if touched:
                print('\n  the %s row ending at sample %d: %.2f of energy' %
                      ('ramp' if kind == RAMP else 'air', end, row['de']), end='')
                self.assertLess(abs(row['de']), NOTHING)
        print()

    def test_a_fall_after_a_teleport_is_not_named_a_hop(self):
        self.assertEqual(self.rows[0]['sub'], 0)

    def test_control_build_is_refused(self):
        marks, rows = parse(self.control)
        self.assertNotEqual(self.control, self.text, 'the control log is the subject log')
        self.assertEqual([m[:3] for m in marks], list(MARKS), 'the line itself is not what changed')
        self.assertEqual([r['kind'] for r in rows], [k for k, _, _, _ in ROWS])
        print('\n  control: the three touched rows read %s; the ramp row ends at sample %d'
              % (', '.join('%.2f' % rows[i]['de'] for i in (0, 2, 3)), rows[2]['tick'] - TICK0))
        for i in (0, 2, 3):
            self.assertGreater(abs(rows[i]['de']), 5 * NOTHING)
        self.assertEqual(rows[2]['tick'], TICK0 + 117)      # where the hold ran out: 0.09 s after sample 111


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('log', type=Path)
    ap.add_argument('--control-log', type=Path, required=True)
    args = ap.parse_args()
    text = args.log.read_text(errors='replace')
    if 'RUNLINES COMPLETE' not in text:
        raise SystemExit('Control did not finish')
    SegBreak.text = text
    SegBreak.control = args.control_log.read_text(errors='replace')
    unittest.main(argv=['test_runlines_segbreak.py'])
