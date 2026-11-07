#!/usr/bin/env python3
"""Frozen owner-sheet and exact-course coverage falsifiers; no network/player data."""
from pathlib import Path
import unittest
import rampwear_priorities as p


class PrioritiesTests(unittest.TestCase):
    def setUp(self):
        self.raw = Path(__file__).with_name('rampwear-priorities.csv').read_bytes()
        self.doc = p.parse(self.raw)

    def test_all_sheet_cells_and_split_course_mentions_are_kept(self):
        self.assertEqual(len(self.doc['bonuses']), 278)
        self.assertEqual(sum(len(b['mentions']) for b in self.doc['bonuses']), 280)
        self.assertEqual(len({b['map'] for b in self.doc['bonuses']}), 173)
        split = next(b for b in self.doc['bonuses'] if b['map'] == 'surf_shibboleth' and b['bonus'] == 4)
        self.assertEqual({v['category'] for v in split['mentions']}, {'unit', 'strafe'})
        self.assertEqual({b['map'] for b in self.doc['bonuses']} & set(p.ALIASES), set())

    def test_unknown_course_cell_and_changed_layout_refuse(self):
        for raw in [self.raw.replace(b'gigapede b4', b'not-a-course', 1),
                    self.raw.replace(b'Unit Bonuses', b'changed-layout', 1)]:
            with self.assertRaises(ValueError):
                p.parse(raw)

    def test_course_input_is_not_surface_or_bake_coverage(self):
        doc = dict(self.doc, bonuses=[{'map': 'surf_case', 'bonus': 2, 'mentions': []}])
        inventory = {'maps': {'surf_case': {'courses': [[0, 0], [1, 0]]}}}
        ready = {'surf_case': {'map': 'surf_case', 'status': 'ready'}}
        self.assertFalse(p.coverage(doc, inventory, ready)['bonuses'][0]['cosmetic_course_input_and_map_ready'])
        inventory['maps']['surf_case']['courses'].append([2, 0])
        self.assertTrue(p.coverage(doc, inventory, ready)['bonuses'][0]['cosmetic_course_input_and_map_ready'])
        self.assertFalse(p.coverage(doc, inventory, {})['bonuses'][0]['cosmetic_course_input_and_map_ready'])


if __name__ == '__main__':
    unittest.main()
