#!/usr/bin/env python3
"""Front-edge algebra/SAT/joint units plus optional ACTED retained native controls."""
import argparse
from copy import deepcopy
import math
from pathlib import Path
import re
import unittest
from unittest.mock import patch

import offramp_triangle as triangle
import offramp_tribev as bevel
import offramp_tribev_smoke as installer
from offramp_motion import joint_overlap
from offramp_trislab import compare as old_compare
from test_offramp_triangle import prism_halfspaces

NATIVE_ARMS = None


def fixture_text():
    lines = ['OFFRAMPTRIBEV_BEGIN 1 30', 'OFFRAMPTRIBEV_SOURCE '+bevel.source_digest(),
             'OFFRAMPTRIBEV_FIXTURE '+' '.join(map(str, [0, 1, 2, *(x for v in bevel.VERTICES for x in v), *bevel.MINS, *bevel.MAXS]))]
    for i in range(1, 31):
        q, c = bevel.expected(i)
        lines += ['OFFRAMPTRIBEV_QUERY '+' '.join(map(str, q)), 'OFFRAMPTRIBEV_COPY '+' '.join(map(str, c))]
    return '\n'.join([*lines, 'OFFRAMPTRIBEV_END 30'])


def render(rows):
    return '\n'.join('OFFRAMPTRIBEV_'+tag+' '+' '.join(words) for tag, words in rows)


class Units(unittest.TestCase):
    def test_hand_derived_front_edge_planes_entries_and_bias(self):
        for c, enter, normal, bias in ((0, 5/8, [1/math.sqrt(3)]*3, math.sqrt(3)/128),
                                      (1, 1/2, [0, 1/math.sqrt(2), 1/math.sqrt(2)], math.sqrt(2)/64)):
            start, end = bevel.ENDPOINTS[c]
            g = triangle.sweep(bevel.VERTICES, start, end, bevel.MINS, bevel.MAXS)
            self.assertAlmostEqual(g['enter'], enter)
            self.assertEqual(len(g['entry_planes']), 1)
            self.assertTrue(bevel.close(g['entry_planes'][0], normal+[0], 1e-9))
            speed = abs(triangle.dot(triangle.sub(end, start), normal))
            self.assertAlmostEqual(triangle.NATIVE_BIAS/speed, bias)
        self.assertAlmostEqual(bevel.expected(7)[0][9], 1/4-math.sqrt(6)/64)

    def test_joint_feasibility_before_after_and_missing_bevel_acts(self):
        planes = prism_halfspaces(bevel.VERTICES, 4)
        for c, enter in ((0, 5/8), (1, 1/2)):
            start, end = bevel.ENDPOINTS[c]
            for t, want in ((0, False), (enter-.001, False), (enter+.001, True), (1, True)):
                origin = [s+t*(e-s) for s, e in zip(start, end)]
                sat = triangle.sweep(bevel.VERTICES, origin, origin, bevel.MINS, bevel.MAXS)
                joint = joint_overlap(planes, [x-.5 for x in origin], [x+.5 for x in origin])
                self.assertEqual(sat['intersects'], want)
                self.assertEqual(joint, want)
        ghost = bevel.ENDPOINTS[2][0]
        self.assertFalse(joint_overlap(planes, [x-.5 for x in ghost], [x+.5 for x in ghost]))
        self.assertFalse(triangle.sweep(bevel.VERTICES, ghost, ghost, bevel.MINS, bevel.MAXS)['intersects'])
        _, normal = triangle.prism(bevel.VERTICES)
        incomplete = [[1, 0, 0], [0, 1, 0], [0, 0, 1], normal]
        incomplete += [triangle.cross(triangle.sub(bevel.VERTICES[(i+1)%3], bevel.VERTICES[i]), normal) for i in range(3)]
        with patch.object(triangle, 'separating_axes', return_value=incomplete):
            self.assertTrue(triangle.sweep(bevel.VERTICES, ghost, ghost, bevel.MINS, bevel.MAXS)['intersects'])

    def test_off_ghost_and_removed_hypothetical_not_support(self):
        rows = bevel.decode(fixture_text())
        self.assertEqual(rows[1]['geometry_basis'], 'COPIED_WINNING_NATIVE_TRIANGLE')
        self.assertFalse(rows[6]['agrees_with_ideal_prism'])
        self.assertFalse(rows[7]['agrees_with_ideal_prism'])
        self.assertTrue(rows[7]['native_solid'])
        self.assertFalse(rows[7]['ideal_prism']['intersects'])
        self.assertTrue(rows[11]['ideal_prism']['intersects'])
        self.assertFalse(rows[11]['native_hit'])
        self.assertIsNone(rows[11]['agrees_with_ideal_prism'])
        self.assertTrue(all(r['copied_winner'] == [0]*16 for r in rows[10:15]))

    def test_schema_source_counts_order_nonfinite_refuse(self):
        good, rows = fixture_text(), bevel.parse(fixture_text())
        for i in range(len(rows)):
            with self.subTest(missing=i), self.assertRaises(AssertionError):
                bevel.decode(render(rows[:i]+rows[i+1:]))
        for text in (good+'\nOFFRAMPTRIBEV_UNKNOWN 1', good+'\nOFFRAMPTRIBEV_END 30',
                     good.replace('BEGIN 1 30', 'BEGIN 2 30'), good.replace(bevel.source_digest(), '0'*64),
                     good.replace('FIXTURE 0 1 2', 'FIXTURE 0 0 2'), good.replace('QUERY 1 1', 'QUERY nan 1'),
                     good.replace('QUERY 1 1', 'QUERY 1 1 0'), good.replace('END 30', 'END 29')):
            with self.assertRaises(AssertionError):
                bevel.decode(text)
        bad = deepcopy(rows)
        bad[3], bad[4] = bad[4], bad[3]
        with self.assertRaises(AssertionError):
            bevel.decode(render(bad))

    def test_copy_cannot_substitute_authored_or_stale_geometry(self):
        q, c = map(lambda r: list(map(str, r)), bevel.expected(2))
        for column, value in ((0, '1'), (1, '0'), (2, '0'), (3, '0'), (4, '.1'), (5, '2'), (8, '.125'), (16, 'nan')):
            bad = c.copy()
            bad[column] = value
            with self.assertRaises(AssertionError):
                bevel.query(q, bad, 2)
        # A copied-source geometry fault must not be masked by SAT over constants.
        with patch.object(bevel, 'sweep') as sweep:
            bad = c.copy()
            bad[8] = '.125'
            with self.assertRaises(AssertionError):
                bevel.query(q, bad, 2)
            sweep.assert_not_called()

    def test_installer_collision_and_late_anchor_refuse_without_write(self):
        engine = Path('unpopulated-readonly-test-engine')
        with patch.object(installer, 'isolated'), patch.object(Path, 'exists', return_value=True), patch.object(Path, 'write_text') as write:
            with self.assertRaisesRegex(RuntimeError, 'overwrite'):
                installer.instrument(engine)
            write.assert_not_called()
        common = engine/'engine/common'
        prepared = {common/'com_bih.c': '#include "offramp_origin_selftest.inc"',
                    common/'offramp_origin_selftest.inc': 'MISSING_REQUIRED_LATE_ANCHOR'}
        with patch.object(installer, 'isolated'), patch.object(Path, 'exists', return_value=False), patch.object(installer, 'slab_prepare', return_value=prepared), patch.object(Path, 'write_text') as write:
            with self.assertRaises((RuntimeError, AssertionError)):
                installer.instrument(engine)
            write.assert_not_called()


@unittest.skipUnless(NATIVE_ARMS, 'No retained native arms; skips are NOT runtime evidence')
class Native(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.texts, cls.provenance = bevel.load_arms(NATIVE_ARMS)
        cls.result = bevel.compare(*cls.texts)
        cls.blocks = re.findall(r'OFFRAMPMOTION_CASE [0-9]+ .*?(?=OFFRAMPMOTION_CASE_END [0-9]+ [0-9]+)', cls.texts[3], flags=re.S)

    def test_actual_bevel_winner_and_off_ghosts_and_removal(self):
        self.assertEqual(self.result['native_queries'], 600)
        self.assertEqual(self.result['copied_setup_winners'], 160)
        self.assertEqual(self.result['bevel_winners'], 40)
        self.assertEqual(self.result['general_triangle_support'], 'ABSTAIN')
        self.assertEqual(self.result['new_mover_actor'], 'NONE')
        self.assertEqual(self.result['unique_on_queries'][1]['copied_winner'][1], 5)
        self.assertEqual(self.result['unique_off_queries'][1]['copied_winner'][1], 2)
        self.assertFalse(self.result['unique_off_queries'][2]['ideal_prism']['intersects'])
        self.assertTrue(self.result['unique_off_queries'][2]['native_solid'])
        self.assertTrue(all(not r['native_hit'] and not r['native_solid'] for r in self.result['unique_removed_queries']))

    def test_every_actual_numeric_query_copy_fixture_fault_acts(self):
        acted = 0
        for block in self.blocks:
            rows = bevel.parse(block)
            words = rows[2][1]
            for j in range(len(words)):
                bad = words.copy()
                bad[j] = str(float(words[j])+.125)
                with self.subTest(fixture=j), self.assertRaises(AssertionError):
                    bevel.fixture(bad)
                acted += 1
            for ordinal in range(1, 31):
                q, c = rows[3+2*(ordinal-1)][1], rows[4+2*(ordinal-1)][1]
                for name, words in (('query', q), ('copy', c)):
                    for j in range(len(words)):
                        bad = words.copy()
                        bad[j] = str(float(words[j])+.125)
                        with self.subTest(ordinal=ordinal, kind=name, column=j), self.assertRaises(AssertionError):
                            bevel.query(bad if name == 'query' else q, bad if name == 'copy' else c, ordinal)
                        acted += 1
        self.assertEqual(acted, 24360)
        print(f'{acted} ACTED native front-edge/bevel query/copy/fixture refusal controls, 0 failed')

    def test_mirrored_wrong_fraction_and_copy_pass_old_then_refuse(self):
        good = self.texts[3]
        for tag, column in (('QUERY', 10), ('COPY', 9)):
            row = next(line[line.find('OFFRAMPTRIBEV_'+tag):] for line in good.splitlines() if 'OFFRAMPTRIBEV_'+tag+' 2 ' in line)
            words = row.split()
            words[column] = str(float(words[column])+.01)
            texts = [t.replace(row, ' '.join(words)) for t in self.texts]
            self.assertEqual(old_compare(*texts), old_compare(*self.texts))
            with self.assertRaises(AssertionError):
                bevel.compare(*texts)

    def test_quiet_envelopes_and_runtime_repeat_cannot_pass(self):
        texts = self.texts.copy()
        texts[2] += '\nOFFRAMPTRIBEV_BEGIN 1 30\n'
        with self.assertRaises(AssertionError):
            bevel.compare(*texts)
        with self.assertRaises(AssertionError):
            bevel.grade(self.texts[3]+'\nOFFRAMPTRIBEV_END 30\n')
        texts = self.texts.copy()
        texts[4] = '\n'.join(l for l in texts[4].splitlines() if 'OFFRAMPTRIBEV_' not in l)
        with self.assertRaises(AssertionError):
            bevel.compare(*texts)


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--native-arms', type=Path)
    a, rest = ap.parse_known_args()
    NATIVE_ARMS = a.native_arms
    Native.__unittest_skip__ = not bool(NATIVE_ARMS)
    unittest.main(argv=[__file__, *rest])
