#!/usr/bin/env python3
"""Independent triangle SAT units; optional ACTED retained native query controls."""
import argparse
from copy import deepcopy
import itertools
import json
from pathlib import Path
import unittest
from unittest.mock import patch

import offramp_triangle as triangle
from offramp_motion import TRIANGLE_VERTICES, compare, joint_overlap
from test_offramp_motion import change

NATIVE_ARMS = None
FLAT = [[0, 0, 0], [0, 10, 0], [10, 0, 0]]
OBLIQUE = [[0, 0, 0], [0, 4, 2], [4, 0, -4]]


def stationary(vertices, origin, mins=(-1, -1, 0), maxs=(1, 1, 2), thickness=4):
    return triangle.sweep(vertices, origin, origin, mins, maxs, thickness)


def prism_halfspaces(vertices, thickness):
    """Five original solid faces for the independent JOINT feasibility solver."""
    _, normal = triangle.prism(vertices, thickness)
    distance = triangle.dot(vertices[0], normal)
    planes = [normal+[distance], [-x for x in normal]+[-distance+thickness]]
    for i in range(3):
        a, b, off = vertices[i], vertices[(i+1)%3], vertices[(i+2)%3]
        axis = triangle.cross(triangle.sub(b, a), normal)
        if triangle.dot(triangle.sub(off, a), axis) > 0:
            axis = [-x for x in axis]
        planes.append(axis+[triangle.dot(a, axis)])
    return planes


class Units(unittest.TestCase):
    def test_front_touch_penetration_and_full_back_slab(self):
        self.assertFalse(stationary(FLAT, [2, 2, .01])['intersects'])
        touching = stationary(FLAT, [2, 2, 0])
        self.assertTrue(touching['intersects'])
        self.assertTrue(touching['starts_overlap'])
        self.assertFalse(touching['starts_penetrating'])
        self.assertTrue(stationary(FLAT, [2, 2, -3])['starts_penetrating'])
        self.assertTrue(stationary(FLAT, [2, 2, -5])['intersects'])
        self.assertFalse(stationary(FLAT, [2, 2, -5], thickness=.1)['intersects'])
        self.assertFalse(stationary(FLAT, [2, 2, -6.01])['intersects'])

    def test_winding_reverses_solid_not_both_sides(self):
        reversed_triangle = FLAT[::-1]
        self.assertEqual(triangle.prism(FLAT)[1], [0, 0, 1])
        self.assertEqual(triangle.prism(reversed_triangle)[1], [0, 0, -1])
        self.assertFalse(stationary(FLAT, [2, 2, 2])['intersects'])
        self.assertTrue(stationary(reversed_triangle, [2, 2, 2])['intersects'])
        self.assertFalse(stationary(reversed_triangle, [2, 2, -3])['intersects'])

    def test_exact_front_back_sweep_intervals(self):
        down = triangle.sweep(FLAT, [2, 2, 2], [2, 2, -8], [-1, -1, 0], [1, 1, 2])
        self.assertTrue(down['intersects'])
        self.assertFalse(down['starts_overlap'])
        self.assertAlmostEqual(down['enter'], .2)
        self.assertAlmostEqual(down['leave'], .8)
        self.assertIn([0, 0, 1, 0], down['entry_planes'])
        up = triangle.sweep(FLAT, [2, 2, -8], [2, 2, 2], [-1, -1, 0], [1, 1, 2])
        self.assertAlmostEqual(up['enter'], .2)
        self.assertAlmostEqual(up['leave'], .8)
        self.assertIn([0, 0, -1, 4], up['entry_planes'])

    def test_partial_vertex_edge_and_full_exits(self):
        self.assertTrue(stationary(FLAT, [10.9, 0, -1])['intersects'])
        self.assertFalse(stationary(FLAT, [11.1, 0, -1])['intersects'])
        self.assertTrue(stationary(FLAT, [6, 6, -1])['intersects'])
        self.assertFalse(stationary(FLAT, [6.01, 6.01, -1])['intersects'])
        along = triangle.sweep(FLAT, [-2, 2, -1], [14, 2, -1], [-1, -1, 0], [1, 1, 2])
        self.assertAlmostEqual(along['enter'], 1/16)
        self.assertAlmostEqual(along['leave'], 12/16)

    def test_inside_moving_out_and_parallel_clear(self):
        leave = triangle.sweep(FLAT, [2, 2, -1], [2, 2, 3], [-1, -1, 0], [1, 1, 2])
        self.assertTrue(leave['starts_penetrating'])
        self.assertEqual(leave['enter'], 0)
        self.assertEqual(leave['leave'], .25)
        self.assertFalse(triangle.sweep(FLAT, [2, 2, 1], [8, 2, 1], [-1, -1, 0], [1, 1, 2])['intersects'])

    def test_missing_edge_cross_axes_false_positive_acts(self):
        # Exact binary fractions. The box at the back corner is excluded by
        # edge x Y axes even though all prism-face + axial intervals overlap.
        origin, mins, maxs = [-2.75, 1.25, -3.25], [-.25]*3, [.25]*3
        points, normal = triangle.prism(OBLIQUE)
        incomplete = [[1, 0, 0], [0, 1, 0], [0, 0, 1], normal]
        incomplete += [triangle.cross(triangle.sub(OBLIQUE[(i+1)%3], OBLIQUE[i]), normal) for i in range(3)]
        self.assertFalse(stationary(OBLIQUE, origin, mins, maxs)['intersects'])
        with patch.object(triangle, 'separating_axes', return_value=incomplete):
            self.assertTrue(stationary(OBLIQUE, origin, mins, maxs)['intersects'])
        self.assertFalse(joint_overlap(prism_halfspaces(OBLIQUE, 4),
                                       [x-.25 for x in origin], [x+.25 for x in origin]))
        self.assertEqual(len(points), 6)

    def test_stationary_sat_matches_independent_joint_feasibility(self):
        # Two independently solved formulations; include actual overlap and
        # actual separation, not a corpus of quiet negatives.
        hits = misses = 0
        for vertices in (FLAT, OBLIQUE):
            planes = prism_halfspaces(vertices, 4)
            for origin in itertools.product((-3, 0, 3), repeat=3):
                mins, maxs = [-.25]*3, [.25]*3
                actual = stationary(vertices, origin, mins, maxs)['intersects']
                joint = joint_overlap(planes, [x-.25 for x in origin], [x+.25 for x in origin])
                self.assertEqual(actual, joint, (vertices, origin))
                hits += actual
                misses += not actual
        self.assertGreater(hits, 0)
        self.assertGreater(misses, 0)

    def test_translation_does_not_change_geometry(self):
        before = triangle.sweep(OBLIQUE, [2, 2, 4], [2, 2, -8], [-1, -1, 0], [1, 1, 2])
        shift = [30, -40, 50]
        shifted = [[x+y for x, y in zip(v, shift)] for v in OBLIQUE]
        after = triangle.sweep(shifted, [32, -38, 54], [32, -38, 42], [-1, -1, 0], [1, 1, 2])
        self.assertEqual(before['intersects'], after['intersects'])
        self.assertAlmostEqual(before['enter'], after['enter'])
        self.assertAlmostEqual(before['leave'], after['leave'])

    def test_invalid_geometry_and_hulls_refuse(self):
        for vertices in (FLAT[:2], [[0, 0, 0]]*3, [[0, 0, 0], [1, 1, 1], [2, 2, 2]],
                         [[float('nan'), 0, 0], *FLAT[1:]]):
            with self.subTest(vertices=vertices), self.assertRaises(AssertionError):
                stationary(vertices, [0, 0, 0])
        for thickness in (0, -4, float('inf')):
            with self.assertRaises(AssertionError): stationary(FLAT, [0, 0, 0], thickness=thickness)
        for mins, maxs in (([0]*3, [0]*3), ([1]*3, [-1]*3), ([0]*2, [1]*3)):
            with self.assertRaises(AssertionError): stationary(FLAT, [0, 0, 0], mins, maxs)
        with self.assertRaises(AssertionError): stationary(FLAT, [0, float('inf'), 0])


@unittest.skipUnless(NATIVE_ARMS, 'needs --native-arms retained five-arm manifest')
class Native(unittest.TestCase):
    acted = 0

    @classmethod
    def setUpClass(cls):
        arms = json.loads(NATIVE_ARMS.read_text())
        cls.texts = [Path(arms[n]['log']).read_text(errors='replace') for n in ('nooracle', 'control', 'off', 'on', 'repeat')]
        cls.motion = compare(*cls.texts)
        cls.cases = cls.motion['cases'][14:16]
        cls.vertices = [TRIANGLE_VERTICES[i:i+3] for i in range(0, 9, 3)]
        cls.result = triangle.assess(*cls.cases)

    def test_native_queries_and_removed_counterfactual_act(self):
        self.assertEqual(self.result['native_down2_hit_ticks'], list(range(14)))
        self.assertEqual(self.result['native_down2_miss_ticks'], list(range(14, 32)))
        self.assertTrue(self.result['removed_inactive_triangle_intersection_ticks'])
        self.assertEqual(self.result['triangle_support_geometry_acceptance'], 'ABSTAIN')
        self.assertTrue(all(w['geometry_status'] == 'world-triangle-unresolved' for w in self.cases[0]['accepted']))
        self.assertFalse(self.cases[1]['accepted'])

    def test_native_query_mutations_all_refuse_independently(self):
        hit_count = miss_count = 0
        for index, case in enumerate(self.cases):
            for tick, queries in zip(case['ticks'], case['oracles']):
                for query in queries:
                    active = index == 0 and query[2] != 'untriangled'
                    triangle.native_query(query, tick, self.vertices, active)
                    # Every actual query is first proved acceptable. Mutations
                    # then ACT the separate SAT/row binding check, not parity.
                    faults = [(4, query[4]+.001), (10, float('nan')), (11, 1), (12, 1), (13, 1), (18, 2)]
                    if query[10] < 1:
                        faults += [(10, query[10]+.01), (14, query[14]+.1), (17, query[17]+.1)]
                        hit_count += 1
                    else:
                        faults += [(10, .5), (14, .8)]
                        miss_count += 1
                    for field, value in faults:
                        changed = query[:]
                        changed[field] = value
                        with self.subTest(case=index, tick=tick[1], query=query[2], field=field), self.assertRaises(AssertionError):
                            triangle.native_query(changed, tick, self.vertices, active)
                        Native.acted += 1
        self.assertGreater(hit_count, 0)
        self.assertGreater(miss_count, 0)

    def test_body_hull_vertices_and_active_binding_refuse(self):
        tick = self.cases[0]['ticks'][0]
        query = self.cases[0]['oracles'][0][1]
        for field, value in ((10, tick[10]+1), (21, 45), (22, 1), (25, 1), (26, 1)):
            changed = tick[:]
            changed[field] = value
            with self.assertRaises(AssertionError): triangle.native_query(query, changed, self.vertices, True)
            Native.acted += 1
        changed = deepcopy(self.vertices)
        changed[0][0] += 1
        with self.assertRaises(AssertionError): triangle.native_query(query, tick, changed, True)
        with self.assertRaises(AssertionError): triangle.native_query(query, tick, self.vertices, False)
        Native.acted += 2

    def test_mirrored_native_fraction_mutation_cannot_self_certify(self):
        # Existing triangle reader abstains on geometry. Alter EVERY arm's
        # corresponding down2 hit identically: parity alone still passes, but
        # the independent query geometry must refuse.
        pred = lambda r: r[:4] == ['14', '0', 'down2', '-1']
        texts = [change(t, 'ORACLE', 10, '.5', pred) if i else t for i, t in enumerate(self.texts)]
        altered = compare(*texts)
        self.assertEqual(altered['capture_body_oracle_parity'], 'PASS')
        with self.assertRaisesRegex(AssertionError, 'independent SAT/bias'):
            triangle.assess(*altered['cases'][14:16])
        Native.acted += 1


if __name__ == '__main__':
    ap = argparse.ArgumentParser(add_help=False)
    ap.add_argument('--native-arms', type=Path)
    args, remaining = ap.parse_known_args()
    NATIVE_ARMS = args.native_arms
    # Decorator ran before CLI parsing; update the native class's skip marker.
    Native.__unittest_skip__ = not bool(NATIVE_ARMS)
    program = unittest.main(argv=[__file__]+remaining, exit=False)
    if NATIVE_ARMS:
        print(f'{Native.acted} ACTED retained native triangle controls, {len(program.result.failures)+len(program.result.errors)} failed')
    raise SystemExit(not program.result.wasSuccessful())
