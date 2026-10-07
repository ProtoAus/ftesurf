#!/usr/bin/env python3
"""Grade actual drawn label strings/counts against the same-frame mark table.

Input stays in the private rig. No raw recording or player details are emitted.
"""
import argparse
from pathlib import Path
import re
import unittest


def sections(text):
    parts = re.split(r'==== ([A-Z]+) ====', text)
    return dict(zip(parts[1::2], parts[2::2]))


def count(part, prefix):
    return [int(m[1]) for m in re.finditer(rf'{prefix} 0 (\d+)', part)]


class Labels(unittest.TestCase):
    data = None
    text = None
    recording = None

    def setUp(self):
        if self.data is None:
            self.skipTest('requires a retained runtime log')

    def test_marks_match_recording(self):
        from p449mark import derive
        rows = [m[1].split() for m in re.finditer(r'\blnm ([^\r\n]+)', self.text)]
        breaks = {int(f[4]) for f in rows if int(f[1]) == 7}
        want, samples = derive(str(self.recording), breaks)
        self.assertGreater(samples, 100)
        self.assertEqual(len(rows), len(want))
        for f, w in zip(rows, want):
            self.assertEqual((int(f[1]), int(f[2]), int(f[4])), (w[0], w[1], w[3]))
            self.assertAlmostEqual(float(f[3]), w[2], delta=0.0002)
            self.assertAlmostEqual(float(f[8]), w[4], delta=0.02)
            self.assertAlmostEqual(float(f[10]), w[6], delta=0.02)

    def test_complete_and_sparse_both_acted(self):
        sparse = count(self.data['SPARSE'], 'lnd3')
        full = count(self.data['COMPLETE'], 'lnd3')
        marks = [int(m[1]) for m in re.finditer(r'lnd2 0 [\d ]+ (\d+)\s*$',
                                              self.data['COMPLETE'], re.M)]
        self.assertEqual(len(full), 2)
        self.assertEqual(full, marks)
        self.assertGreater(full[0], sparse[0])
        self.assertGreater(sparse[0], 0)
        self.assertNotRegex(self.data['COMPLETE'], r'lndm 0 .* -\s*$')
        self.assertIn('lnde 8 0', self.data['COMPLETE'])

    def test_switches_acted(self):
        self.assertGreater(len(count(self.data['NUMSOFF'], 'lnd3')), 0)
        self.assertEqual(set(count(self.data['NUMSOFF'], 'lnd3')), {0})
        self.assertIn('lndm 0', self.data['NUMSOFF'])
        self.assertGreater(len(count(self.data['MARKSOFF'], 'lnd3')), 0)
        self.assertEqual(set(count(self.data['MARKSOFF'], 'lnd3')), {0})
        self.assertNotIn('lndm 0', self.data['MARKSOFF'])

    def test_every_numeric_field_matches_its_contact(self):
        marks = []
        for m in re.finditer(r'lnm (\d+) ([^\r\n]+)', self.text):
            f = ['lnm', m[1], *m[2].split()]
            if len(f) >= 12:
                marks.append(dict(t=float(f[4]), z=float(f[8]), speed=float(f[9]),
                                  v2=float(f[10]), vz=float(f[11])))
        self.assertGreater(len(marks), 8)
        zero = re.search(r'lnmz 0 ([\d.-]+) ([\d.-]+)', self.text)
        self.assertIsNotNone(zero)
        ref = float(zero[1]) + float(zero[2]) / 1600
        bytime = {round(m['t'], 4): (i, m) for i, m in enumerate(marks)}
        rows = list(re.finditer(r'lndm 0 \d+ ([\d.]+) [\d.-]+ [\d.-]+ "([^"]+)"',
                                self.data['COMPLETE']))
        self.assertGreater(len(rows), 0)
        for row in rows:
            i, src = bytime[round(float(row[1]), 4)]
            nums = re.fullmatch(r'([\d.-]+) u/s  E ([\d+-]+)  vz ([\d+-]+)  dE ([\d+-]+)  ([\d.]+) s', row[2])
            self.assertIsNotNone(nums)
            speed, energy, vz, delta, t = map(float, nums.groups())
            self.assertAlmostEqual(speed, src['speed'], delta=0.51)
            en = src['z'] + src['v2'] / 1600
            self.assertAlmostEqual(energy, en - ref, delta=0.51)
            self.assertAlmostEqual(vz, src['vz'], delta=0.51)
            prev = marks[i - 1]
            self.assertAlmostEqual(delta, en - prev['z'] - prev['v2'] / 1600, delta=0.51)
            self.assertAlmostEqual(t, src['t'], delta=0.006)


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('log', type=Path)
    args = ap.parse_args()
    Labels.text = args.log.read_text(errors='replace')
    if 'RUNLINES COMPLETE' not in Labels.text:
        raise SystemExit('Control did not finish')
    Labels.data = sections(Labels.text)
    Labels.recording = args.log.parent.parent / 'cfg/test/runlines_sample.rec'
    unittest.main(argv=['test_runlines_labels.py'])
