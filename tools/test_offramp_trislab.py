#!/usr/bin/env python3
"""Back-slab analytic/SAT units plus optional ACTED full native query refusals."""
import argparse
from copy import deepcopy
from pathlib import Path
import re
import unittest
from unittest.mock import patch

import offramp_trislab as slab
import offramp_trislab_smoke as installer
from offramp_motion import joint_overlap
from offramp_tricopy import compare as old_compare
from test_offramp_triangle import prism_halfspaces

NATIVE_ARMS = None


def fixture_text():
    lines = ['OFFRAMPTRISLAB_BEGIN 1 24', 'OFFRAMPTRISLAB_SOURCE '+slab.source_digest(),
             'OFFRAMPTRISLAB_FIXTURE '+' '.join(map(str, [0, 1, 2, *(x for v in slab.VERTICES for x in v), *slab.MINS, *slab.MAXS]))]
    for i in range(1, 25):
        c, active = (i-1) % 6, (i-1) % 12 < 6
        x = 150 if c == 5 else 0
        result = [1, 1, 0, 0, 0, 0, 0, 0, 0, 0, -1, 0, 0]
        if active and c in (0, 1):
            speed, enter, normal, tag = (12, 5.5/12, 1, 0) if c == 0 else (8, 5.5/8, -1, 105)
            result = [enter-(1/32)/speed, enter, 0, 0, 1, 0, 0, normal, 0, 2, 1, 1, tag]
        elif active and c == 4:
            result = [1, 1, 1, 1, 1, 0, 0, 0, 0, 0, -1, 0, 0]
        row = [i, int(active), x, 0, slab.Z[c][0], x, 0, slab.Z[c][1], *result]
        lines.append('OFFRAMPTRISLAB_QUERY '+' '.join(map(str, row)))
    return '\n'.join([*lines, 'OFFRAMPTRISLAB_END 24'])


def render(rows):
    return '\n'.join('OFFRAMPTRISLAB_'+tag+' '+' '.join(words) for tag, words in rows)


class Units(unittest.TestCase):
    def test_hand_derived_front_and_back_prism_intervals(self):
        front = slab.sweep(slab.VERTICES, [0, 0, 6], [0, 0, -6], slab.MINS, slab.MAXS)
        self.assertAlmostEqual(front['enter'], 5.5/12)
        self.assertAlmostEqual(front['leave'], 10.5/12)
        self.assertIn([0, 0, 1, 0], front['entry_planes'])
        back = slab.sweep(slab.VERTICES, [0, 0, -6], [0, 0, 2], slab.MINS, slab.MAXS)
        self.assertAlmostEqual(back['enter'], 1.5/8)
        self.assertIn([0, 0, -1, 4], back['entry_planes'])
        self.assertEqual((5.5/8-back['enter'])*8, 4)

    def test_stationary_joint_feasibility_independently_agrees(self):
        planes = prism_halfspaces(slab.VERTICES, 4)
        for origin, expect in (([0, 0, -2], True), ([0, 0, 0], True), ([150, 0, 0], False)):
            with self.subTest(origin=origin):
                sat = slab.sweep(slab.VERTICES, origin, origin, slab.MINS, slab.MAXS)
                self.assertEqual(sat['starts_penetrating'], expect)
                self.assertEqual(joint_overlap(planes, [x+lo for x, lo in zip(origin, slab.MINS)],
                                              [x+hi for x, hi in zip(origin, slab.MAXS)]), expect)

    def test_native_miss_does_not_promote_ideal_clear_or_support(self):
        rows = slab.decode(fixture_text())
        self.assertEqual([r['label'] for r in rows[:6] if r['differs_from_ideal_prism']],
                         ['back-axial', 'short-back', 'stationary-back-slab'])
        self.assertFalse(rows[2]['native_intersects'])
        self.assertTrue(rows[2]['ideal_prism']['intersects'])
        self.assertTrue(rows[3]['ideal_prism']['starts_penetrating'])
        self.assertTrue(all(not r['native_intersects'] for r in rows[6:12]))
        self.assertTrue(rows[6]['ideal_prism']['intersects'])

    def test_winding_hull_and_geometry_changes_refuse(self):
        row = slab.parse(fixture_text())[3][1]
        for vertices, mins, maxs in ((slab.VERTICES[::-1], slab.MINS, slab.MAXS),
                                    (slab.VERTICES, [-1]*3, slab.MAXS),
                                    (slab.VERTICES, slab.MINS, [1]*3)):
            with self.assertRaises(AssertionError):
                slab.query(row, 1, vertices, mins, maxs)

    def test_schema_source_counts_order_and_nonfinite_refuse(self):
        good = fixture_text()
        rows = slab.parse(good)
        for i in range(len(rows)):
            with self.subTest(missing=i), self.assertRaises(AssertionError):
                slab.decode(render(rows[:i]+rows[i+1:]))
        mutations = [good+'\nOFFRAMPTRISLAB_UNKNOWN 1', good+'\nOFFRAMPTRISLAB_END 24',
                     good.replace('BEGIN 1 24', 'BEGIN 2 24'), good.replace(slab.source_digest(), '0'*64),
                     good.replace('FIXTURE 0 1 2', 'FIXTURE 0 0 2'), good.replace('QUERY 1 1', 'QUERY nan 1'),
                     good.replace('QUERY 1 1', 'QUERY 1 1 0'), good.replace('END 24', 'END 23')]
        for text in mutations:
            with self.assertRaises(AssertionError):
                slab.decode(text)

    def test_installer_prepares_before_any_write(self):
        # New layer existing include and missing composition anchor both refuse.
        engine = Path('unpopulated-readonly-test-engine')
        with patch.object(Path, 'exists', return_value=True), patch.object(Path, 'write_text') as write:
            with self.assertRaisesRegex(RuntimeError, 'overwrite'):
                installer.prepare(engine)
            write.assert_not_called()
        with patch.object(Path, 'exists', return_value=False), patch.object(installer, 'copy_prepare',
             return_value={engine/'engine/common/com_bih.c': 'MISSING_REQUIRED_COMPOSITION_ANCHOR'}), patch.object(Path, 'write_text') as write:
            with self.assertRaises((RuntimeError, AssertionError)):
                installer.prepare(engine)
            write.assert_not_called()


@unittest.skipUnless(NATIVE_ARMS, 'No retained native arms; skips are NOT runtime evidence')
class Native(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.texts, cls.provenance = slab.load_arms(NATIVE_ARMS)
        cls.result = slab.compare(*cls.texts)
        cls.blocks = re.findall(r'OFFRAMPMOTION_CASE [0-9]+ .*?(?=OFFRAMPMOTION_CASE_END [0-9]+ [0-9]+)', cls.texts[3], flags=re.S)

    def test_actual_native_queries_control_removal_and_repeat(self):
        self.assertEqual(self.result['native_queries'], 480)
        self.assertEqual(self.result['native_setup_calls'], 20)
        self.assertEqual(self.result['measured_native_vs_ideal'], 'NON_EQUIVALENT_BACK_SLAB')
        self.assertEqual(self.result['general_triangle_support'], 'ABSTAIN')
        self.assertTrue(self.result['unique_present_queries'][0]['native_intersects'])
        self.assertTrue(self.result['unique_present_queries'][1]['native_intersects'])
        self.assertTrue(self.result['unique_present_queries'][4]['native_intersects'])
        self.assertTrue(all(not r['native_intersects'] for r in self.result['unique_removed_queries']))

    def test_every_actual_query_numeric_and_fixture_fault_acts(self):
        acted = 0
        for block in self.blocks:
            rows = slab.parse(block)
            for i, (tag, words) in enumerate(rows):
                if tag not in ('QUERY', 'FIXTURE'):
                    continue
                for j in range(len(words)):
                    bad = deepcopy(rows)
                    bad[i][1][j] = str(float(words[j])+.125)
                    with self.subTest(row=i, column=j), self.assertRaises(AssertionError):
                        slab.decode(render(bad))
                    acted += 1
        self.assertEqual(acted, 10440)
        print(f'{acted} ACTED native back-slab query/fixture refusal controls, 0 failed')

    def test_mirrored_wrong_fraction_passes_old_parity_then_refuses(self):
        good = self.texts[3]
        row = next(l[l.find('OFFRAMPTRISLAB_QUERY'):] for l in good.splitlines() if 'OFFRAMPTRISLAB_QUERY 2 ' in l)
        words = row.split()
        words[9] = str(float(words[9])+.01)
        bad = [' '.join(words)]
        texts = [t.replace(row, bad[0]) for t in self.texts]
        self.assertEqual(old_compare(*texts), old_compare(*self.texts))
        with self.assertRaises(AssertionError):
            slab.compare(*texts)
        # Quiet and envelope controls must fail even if old layers are intact.
        texts = self.texts.copy()
        texts[2] += '\nOFFRAMPTRISLAB_BEGIN 1 24\n'
        with self.assertRaises(AssertionError):
            slab.compare(*texts)
        with self.assertRaises(AssertionError):
            slab.grade(good+'\nOFFRAMPTRISLAB_END 24\n')


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--native-arms', type=Path)
    a, rest = ap.parse_known_args()
    NATIVE_ARMS = a.native_arms
    Native.__unittest_skip__ = not bool(NATIVE_ARMS)
    unittest.main(argv=[__file__, *rest])
