#!/usr/bin/env python3
"""Grade the acted controls in runlines_reset.cfg; log lives in the private rig."""
import argparse
import re
import unittest


def sections(text):
    out = {}
    for part in re.split(r'==== ([A-Z0-9]+) ====', text)[1:]:
        if re.fullmatch(r'[A-Z0-9]+', part):
            name = part
        else:
            out[name] = part
    return out


def points(part):
    m = re.search(r'live slot (\d+) \((\d+) pts', part)
    if not m:
        raise AssertionError('No acted trail report')
    return tuple(map(int, m.groups()))


def head(part):
    m = re.search(r'trail: head ([\d.]+) s at ([^\r\n]+)', part)
    if not m:
        raise AssertionError('No trail head')
    return float(m[1]), tuple(map(float, m[2].split()))


class Reset(unittest.TestCase):
    data = None

    def setUp(self):
        if self.data is None:
            self.skipTest('requires a retained runtime log')

    def test_run_acted(self):
        self.assertGreater(points(self.data['GROW1'])[1], 10)
        self.assertGreater(points(self.data['GROW2'])[1], points(self.data['GROW1'])[1])
        self.assertIn('recording 1', self.data['GROW2'])

    def test_reset_retains_head_and_rewind(self):
        a, b = self.data['RESET1'], self.data['RESET2']
        self.assertEqual(points(a), points(b))
        self.assertEqual(head(a), head(b))
        self.assertIn('stopped 1', a)
        m = re.search(r'rewind: at \d+ ([^\r\n]+?)  0:', a)
        self.assertIsNotNone(m)
        self.assertEqual(tuple(map(float, m[1].split())), head(a)[1])
        self.assertIn('timer: armed', a)

    def test_start_save_does_not_erase_failed_run(self):
        self.assertEqual(points(self.data['RESET2']), points(self.data['LOADSTART']))
        self.assertEqual(head(self.data['RESET2']), head(self.data['LOADSTART']))
        self.assertIn('stopped 1', self.data['LOADSTART'])
        self.assertIn('latest command ack 3', self.data['LOADSTART'])

    def test_departure_starts_one_second_fade(self):
        a, b = self.data['NEW'], self.data['FADED']
        self.assertNotEqual(points(a)[0], points(self.data['RESET2'])[0])
        self.assertGreater(points(a)[1], 2)
        self.assertIn('(on 1,', a)
        self.assertIn('1.00 s fade', a)
        self.assertIn('(on 0,', b)
        self.assertGreater(points(b)[1], points(a)[1])

    def test_stage_control_acted(self):
        self.assertIn('stagerun 1  stage 1 asked 1', self.data['STAGERUN'])
        self.assertIn('recording 1', self.data['STAGERUN'])
        self.assertGreater(points(self.data['STAGERUN'])[1], 10)
        a, b = self.data['STAGERESET1'], self.data['STAGERESET2']
        self.assertEqual(points(a), points(b))
        self.assertEqual(head(a), head(b))
        self.assertIn('stopped 1', a)
        self.assertIn('timer: armed', a)
        self.assertIn('(on 1,', self.data['STAGENEW'])
        self.assertIn('(on 0,', self.data['STAGEFADED'])
        self.assertGreater(points(self.data['STAGEFADED'])[1], points(self.data['STAGENEW'])[1])


if __name__ == '__main__':
    from pathlib import Path
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('log', type=Path)
    args = ap.parse_args()
    text = args.log.read_text(errors='replace')
    if 'RUNLINES COMPLETE' not in text:
        raise SystemExit('Control did not finish')
    Reset.data = sections(text)
    unittest.main(argv=['test_runlines_reset.py'])
