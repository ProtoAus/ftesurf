#!/usr/bin/env python3
"""Exact front-domain algebra, independent common-point witnesses and retained arms."""
import argparse
from contextlib import redirect_stderr
from copy import deepcopy
from fractions import Fraction as F
import io
import json
from pathlib import Path
import random
import unittest
from unittest.mock import patch

import offramp_bevclip as clip
import offramp_bevpm as pm
import offramp_trisupport as reach
from offramp_triangle import sweep

NATIVE_ARMS = None
TRI = [[0, 0, 0], [0, 10, 0], [10, 0, 0]]
MINS, MAXS = [-1, -1, 0], [1, 1, 2]


def rectangle(lo, hi):
    a, b, c, d = [lo, -10, 0], [lo, 10, 0], [hi, 10, 0], [hi, -10, 0]
    return [[a, b, c], [a, c, d]]


class Units(unittest.TestCase):
    def test_hand_derived_domain_and_distance(self):
        r = reach.certified_domain(TRI, [-2, 5, 1], [12, 5, 1], MINS, MAXS, 2)
        self.assertEqual(r['coverage'], [F(1, 14), F(9, 14)])
        self.assertEqual(r['reach_distance_range'], [F(1), F(2)])
        self.assertEqual(r['polygon'], [(F(1, 14), F(1)), (F(1, 14), F(2)),
                                        (F(9, 14), F(1)), (F(9, 14), F(2))])
        self.assertTrue(all(type(x) is F for p in r['polygon']+r['constraints'] for x in p))
        self.assertEqual(len(r['vertex_witnesses']), 4)

    def test_center_exit_not_full_footprint_exit(self):
        r = reach.certified_domain(TRI, [-F(1, 2), 5, 1], [-F(1, 2), 5, 1], MINS, MAXS, 2)
        self.assertEqual(r['coverage'], [F(0), F(1)])
        w = reach.spatial_witness(TRI, [-F(1, 2), 5, 1], MINS, MAXS, 2)
        self.assertIsNotNone(w)
        self.assertGreaterEqual(w['point'][0], 0)
        self.assertEqual(sum(w['barycentric']), 1)

    def test_diagonal_corner_needs_joint_geometry_not_axial_extents(self):
        origin = [7, 7, 1]
        self.assertFalse(reach.certified_domain(TRI, origin, origin, MINS, MAXS, 2)['polygon'])
        self.assertIsNone(reach.spatial_witness(TRI, origin, MINS, MAXS, 2))
        # Removing edge-cross axes invents support despite each xyz extent overlapping.
        with patch.object(reach, 'axes', return_value=[(F(1), F(0), F(0)),
                                                       (F(0), F(1), F(0)), (F(0), F(0), F(1))]):
            self.assertTrue(reach.domain(TRI, origin, origin, MINS, MAXS, 2)['polygon'])
            with self.assertRaisesRegex(AssertionError, 'SAT/joint-barycentric'):
                reach.certified_domain(TRI, origin, origin, MINS, MAXS, 2)

    def test_closed_touch_point_and_zero_horizon(self):
        for start, end, horizon, want in (([-2, 5, 0], [-1, 5, 0], 0, [F(1), F(1)]),
                                         ([-1, 5, 0], [-1, 5, 0], 0, [F(0), F(1)])):
            r = reach.certified_domain(TRI, start, end, MINS, MAXS, horizon)
            self.assertEqual(r['coverage'], want)
            self.assertTrue(all(p[1] == 0 for p in r['polygon']))
        r = reach.certified_domain(TRI, [-2, 5, 0], [-1, 5, 0], MINS, MAXS, 0)
        self.assertEqual(r['polygon'], [(F(1), F(0))])
        self.assertEqual(reach.gaps([[1, 1]]), [dict(start=F(0), end=F(1), start_included=True,
                                                  end_included=False, length=F(1))])

    def test_vertical_reach_loss_with_interior_footprint(self):
        r = reach.certified_domain(TRI, [2, 2, 1], [2, 2, 5], MINS, MAXS, 2)
        self.assertEqual(r['coverage'], [F(0), F(1, 4)])
        self.assertEqual(r['reach_distance_range'], [F(1), F(2)])
        self.assertIsNone(reach.spatial_witness(TRI, [2, 2, 5], MINS, MAXS, 2))
        self.assertIsNotNone(reach.spatial_witness(TRI, [2, 2, 5], MINS, MAXS, 8))

    def test_two_patch_seam_union_not_previous_triangle_only(self):
        patches = rectangle(-10, 0)+rectangle(0, 20)
        r = reach.patch_coverage(patches, [-2, 0, 1], [10, 0, 1], MINS, MAXS, 2)
        self.assertEqual(r['coverage'], [[F(0), F(1)]])
        self.assertEqual(r['gaps'], [])
        old_only = reach.patch_coverage(patches[:2], [-2, 0, 1], [10, 0, 1], MINS, MAXS, 2)
        self.assertTrue(old_only['gaps'])
        self.assertEqual(old_only['coverage'], [[F(0), F(1, 4)]])

    def test_short_gap_recontact_endpoint_alias_and_removal_suffix(self):
        r = reach.patch_coverage(rectangle(-10, 0)+rectangle(4, 20), [0, 0, 1], [10, 0, 1], MINS, MAXS, 2)
        self.assertEqual(r['coverage'], [[F(0), F(1, 10)], [F(3, 10), F(1)]])
        self.assertEqual(r['gaps'], [dict(start=F(1, 10), end=F(3, 10), start_included=False,
                                        end_included=False, length=F(1, 5))])
        # Both endpoint samples pass, yet three milliseconds of a derived 15ms segment do not.
        for pos in ([0, 0, 1], [10, 0, 1]):
            self.assertTrue(any(reach.spatial_witness(t, pos, MINS, MAXS, 2) for t in rectangle(-10, 0)+rectangle(4, 20)))
        self.assertEqual(r['gaps'][0]['length']*F(15, 1000), F(3, 1000))
        removed = reach.patch_coverage(rectangle(-10, 0), [0, 0, 1], [10, 0, 1], MINS, MAXS, 2)
        self.assertEqual(removed['gaps'][0]['length'], F(9, 10))
        self.assertTrue(removed['gaps'][0]['end_included'])
        self.assertEqual(reach.patch_coverage([], [0, 0, 1], [10, 0, 1], MINS, MAXS, 2)['gaps'][0]['length'], 1)

    def test_arbitrarily_short_positive_gap_is_not_rounded_or_dwelled_away(self):
        width = F(1, 10**12)
        r = reach.patch_coverage(rectangle(-10, 0)+rectangle(2+width, 20), [0, 0, 1], [10, 0, 1], MINS, MAXS, 2)
        self.assertEqual(r['gaps'][0]['length'], width/10)
        self.assertGreater(r['gaps'][0]['length'], 0)

    def test_gap_boundary_inclusion_and_closed_seams(self):
        self.assertEqual(reach.gaps([[0, F(1, 2)], [F(1, 2), 1]]), [])
        self.assertEqual(reach.union_coverage([[F(1, 2), 1], [0, F(1, 2)], [F(1, 4), F(3, 4)]]), [[F(0), F(1)]])
        r = reach.gaps([[F(1, 2), F(1, 2)]])
        self.assertEqual([(g['start_included'], g['end_included']) for g in r], [(True, False), (False, True)])
        self.assertEqual(sum(g['length'] for g in r), 1)
        self.assertEqual(reach.gaps([])[0], dict(start=F(0), end=F(1), start_included=True, end_included=True, length=F(1)))

    def test_front_triangle_is_not_back_slab_or_load_bearing_acceptance(self):
        front = [[0, 0, 0], [0, 10, -10], [10, 0, -10]]
        origin = [-F(3, 2), 5, -8]
        # A back-slab witness is (0,5.75,-5.75)-(.75,.75,.75).
        # Its slab depth .75*sqrt(3)<4; its negative x is outside the FRONT.
        self.assertFalse(reach.certified_domain(front, origin, origin, MINS, MAXS, 2)['polygon'])
        self.assertTrue(sweep(front, [float(x) for x in origin], [float(x) for x in origin], MINS, MAXS)['intersects'])
        # An embedded box may reach the front mathematically; that proves no standability.
        self.assertTrue(reach.certified_domain(TRI, [2, 2, -1], [2, 2, -1], MINS, MAXS, 2)['polygon'])

    def test_independent_domain_mutants_act(self):
        builder = reach.domain
        def lose_horizon(vertices, start, end, mins, maxs, horizon):
            result = builder(vertices, start, end, mins, maxs, horizon+4)
            result['downward_bounds'] = [F(0), reach.rational(horizon)]
            return result  # Conceal metadata change: geometric equality must refuse.
        def back_surface(vertices, start, end, mins, maxs, horizon):
            return builder([[x, y, z-4] for x, y, z in vertices], start, end, mins, maxs, horizon)
        def center_only(vertices, start, end, mins, maxs, horizon):
            return builder(vertices, start, end, [-F(1, 1000), -F(1, 1000), mins[2]],
                           [F(1, 1000), F(1, 1000), maxs[2]], horizon)
        for mutant in (lose_horizon, back_surface, center_only):
            with self.subTest(mutant=mutant.__name__), patch.object(reach, 'domain', side_effect=mutant), \
                    self.assertRaisesRegex(AssertionError, 'SAT/joint-barycentric'):
                reach.certified_domain(TRI, [-F(1, 2), 5, 1], [-F(1, 2), 5, 1], MINS, MAXS, 2)

    def test_wrong_projection_or_bounds_certificate_refuses(self):
        builder = reach.domain
        for field, bad in (('coverage', [F(0), F(1, 2)]), ('reach_distance_range', [F(0), F(2)]),
                           ('parameter_bounds', [F(-1), F(1)]), ('downward_bounds', [F(0), F(3)])):
            def mutant(*args):
                result = builder(*args); result[field] = bad
                return result
            with self.subTest(field=field), patch.object(reach, 'domain', side_effect=mutant), self.assertRaises(AssertionError):
                reach.certified_domain(TRI, [2, 2, 1], [2, 2, 1], MINS, MAXS, 2)

    def test_translation_and_cyclic_winding_invariance(self):
        start, end = [-2, 5, 1], [12, 5, 1]
        shift = [123, -456, 789]
        vs = [[a+b for a, b in zip(v, shift)] for v in TRI]
        r = reach.certified_domain(TRI, start, end, MINS, MAXS, 2)
        shifted = reach.certified_domain(vs[1:]+vs[:1], [a+b for a, b in zip(start, shift)],
                                         [a+b for a, b in zip(end, shift)], MINS, MAXS, 2)
        self.assertEqual(r['polygon'], shifted['polygon'])

    def test_deterministic_random_domains_and_spatial_grid(self):
        rng = random.Random(9012)
        checked = 0
        for i in range(40):
            vs = [[0, 0, 0], [0, 10, -rng.randint(0, 10)], [10, 0, -rng.randint(0, 10)]]
            start, end = [[rng.randint(-3, 12), rng.randint(-3, 12), rng.randint(-12, 8)] for _ in range(2)]
            horizon = rng.randint(0, 4)
            r = reach.certified_domain(vs, start, end, MINS, MAXS, horizon)
            for t in (F(0), F(1, 3), F(2, 3), F(1)):
                for down in (F(0), F(horizon, 2), F(horizon)):
                    within = all(a*t+b*down <= c for a, b, c in r['constraints'])
                    origin = [F(a)+t*(b-a)-(down if axis == 2 else 0) for axis, (a, b) in enumerate(zip(start, end))]
                    self.assertEqual(within, reach.spatial_witness(vs, origin, MINS, MAXS, 0) is not None)
                    checked += 1
        self.assertEqual(checked, 480)

    def test_rational_serialization_and_extreme_type_refusals(self):
        self.assertEqual(reach.rational(.1), F(1, 10))
        self.assertEqual(reach.encoded(dict(x=F(1, 3), polygon=[(F(0), F(1))])), {'x': '1/3', 'polygon': [['0', '1']]})
        for x in (True, '0.1', None, float('nan'), float('inf'), -float('inf'), 10**400):
            with self.subTest(value=str(x)), self.assertRaises(AssertionError): reach.rational(x)

    def test_invalid_geometry_hull_horizon_and_coverage_refuse(self):
        for vertices in (TRI[::-1], [[0, 0, 0]]*3, [[0, 0, 0], [0, 0, 10], [0, 10, 0]], TRI[:2]):
            with self.assertRaises(AssertionError): reach.domain(vertices, [0, 0, 0], [0, 0, 0], MINS, MAXS, 2)
        for mins, maxs, horizon in ((MAXS, MINS, 2), (MINS, MINS, 2), (MINS, MAXS, -1)):
            with self.assertRaises(AssertionError): reach.domain(TRI, [0, 0, 0], [0, 0, 0], mins, maxs, horizon)
        with self.assertRaises(AssertionError): reach.patch_coverage([], [0, 0, 0], [0, 0, 0], MAXS, MINS, 2)
        with self.assertRaises(AssertionError): reach.patch_coverage([], [0, 0, 0], [0, 0, 0], MINS, MAXS, -1)
        for intervals in ([[0, 2]], [[1, 0]], [[-1, 0]], [[0]], [[True, 1]]):
            with self.assertRaises(AssertionError): reach.union_coverage(intervals)

    def test_existing_cli_output_refused_before_input_read_or_write(self):
        argv = ['offramp_trisupport.py', '--arms', 'unused.json', '--output', 'retained.json']
        with patch('sys.argv', argv), patch.object(Path, 'exists', return_value=True), \
                patch.object(pm, 'load_arms') as load, patch.object(Path, 'open') as output, redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as error: reach.main()
            self.assertEqual(error.exception.code, 2)
            load.assert_not_called(); output.assert_not_called()


@unittest.skipUnless(NATIVE_ARMS, 'No retained native arms; skips are NOT runtime evidence')
class Native(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.texts, _ = reach.load_arms(NATIVE_ARMS)
        cls.prior = clip.compare(*cls.texts)
        cls.result = reach.compare(*cls.texts)

    def test_all_domains_witnesses_and_previous_report_exact(self):
        r = self.result
        self.assertEqual((r['sample_count'], r['derived_segment_count'], r['accepted_request_count']), (96, 96, 18))
        self.assertEqual(r['prior_plane_set_report'], self.prior)
        self.assertEqual(r['general_triangle_support'], 'ABSTAIN')
        self.assertEqual(r['physical_exit_acceptance'], 'NOT_TESTED')
        self.assertEqual(r['standability_load_bearing_acceptance'], 'NOT_TESTED')
        self.assertEqual(r['native_front_reach_equivalence'], 'NOT_CLAIMED')
        self.assertEqual(json.loads(json.dumps(reach.encoded(r), allow_nan=False))['prior_plane_set_report'], self.prior)
        self.assertTrue(all(d['front_domain']['joint_barycentric_equality'] == 'PASS' for c in r['cases'] for d in c['segments']))
        self.assertTrue(all(a['geometry_basis'] == 'COPIED_WINNING_NATIVE_TRIANGLE_FRONT_ONLY' for a in r['accepted']))

    def test_late_raw_loss_and_back_slab_do_not_establish_front_support(self):
        on = self.result['cases'][0]
        self.assertEqual([s['tick'] for s in on['samples'] if s['counterfactual_front_reachable']], list(range(10, 21)))
        for i in (21, 22):
            self.assertFalse(on['samples'][i]['counterfactual_front_reachable'])
            self.assertTrue(self.prior['cases'][0]['queries'][i][1]['ideal_prism']['intersects'])
        self.assertEqual(on['segments'][21]['front_domain']['coverage'], [F(0), F(1, 3)])
        self.assertEqual(on['live_derived_track_coverage'][0][1], F(2, 3))
        self.assertEqual(on['live_derived_track_gaps'][-1]['derived_seconds'], F(4, 25))
        self.assertEqual(self.prior['prior_pm_report']['raw_loss_ticks'], [22])

    def test_removed_geometry_is_counterfactual_not_live_support(self):
        removed = self.result['cases'][1]
        self.assertTrue(any(s['counterfactual_front_reachable'] for s in removed['samples']))
        self.assertFalse(any(s['live_front_reachable'] for s in removed['samples']))
        self.assertEqual(removed['live_derived_track_coverage'], [])
        self.assertEqual(removed['live_derived_track_gaps'][0]['length'], 1)

    def test_bevel_off_interpolation_alias_is_not_native_recontact_claim(self):
        off = self.result['cases'][2]
        self.assertFalse(any(s['counterfactual_front_reachable'] for s in off['samples']))
        self.assertTrue(off['live_derived_track_coverage'])
        self.assertTrue(any(s['front_domain']['polygon'] for s in off['segments']))
        self.assertEqual(off['trajectory_basis'], 'LINEAR_INTERPOLATION_OF_CAPTURED_COMMAND_ENDPOINTS_NOT_CAPTURED_SUBCOMMAND_PATH')

    def test_every_copy_coordinate_and_hull_fault_refuses_new_binding_gate(self):
        contacts = [r for c in self.prior['prior_pm_report']['cases'] for r in c['accepted']]
        acted = 0
        for contact in contacts:
            for i in range(9):
                bad = deepcopy(contact); bad['copied_winner']['vertices'][i//3][i % 3] += .125
                with self.assertRaisesRegex(AssertionError, 'copied front geometry/hull'): reach.assess_contact(bad)
                acted += 1
            for i in range(15, 21):
                bad = deepcopy(contact); bad['contact'][i] += .125
                with self.assertRaisesRegex(AssertionError, 'copied front geometry/hull'): reach.assess_contact(bad)
                acted += 1
        self.assertEqual(acted, 270)
        print(f'{acted} ACTED NEW copy-coordinate/hull binding refusals (not independent native semantics)')

    def test_runtime_bound_new_geometry_mutants_preserve_prior(self):
        builder = reach.domain
        def expanded_horizon(vertices, start, end, mins, maxs, horizon):
            result = builder(vertices, start, end, mins, maxs, horizon+4)
            result['downward_bounds'] = [F(0), reach.rational(horizon)]
            return result  # Refusal must ACT on geometry, not only the bounds header.
        def back_surface(vertices, start, end, mins, maxs, horizon):
            return builder([[x, y, z-4] for x, y, z in vertices], start, end, mins, maxs, horizon)
        for mutant in (expanded_horizon, back_surface):
            self.assertEqual(clip.compare(*self.texts), self.prior)
            with patch.object(reach, 'domain', side_effect=mutant), self.assertRaisesRegex(AssertionError, 'SAT/joint-barycentric'):
                reach.compare(*self.texts)
        print('2 ACTED retained-trajectory new domain mutants; prior report unchanged')

    def test_manifest_fixture_and_modes_refuse_with_prior_loader_held_constant(self):
        arms = json.loads(NATIVE_ARMS.read_text())
        prior_load = pm.load_arms(NATIVE_ARMS)
        acted = 0
        for n in pm.NAMES:
            for key in ('bevpm_source_sha256', 'capture', 'oracle'):
                bad = deepcopy(arms)
                bad[n][key] = '0'*64 if key.endswith('sha256') else 1-bad[n][key]
                with patch.object(pm, 'load_arms', return_value=prior_load), \
                        patch.object(Path, 'read_text', return_value=json.dumps(bad)), \
                        self.assertRaisesRegex(AssertionError, 'fixture/mode manifest'):
                    reach.load_arms(NATIVE_ARMS)
                acted += 1
        self.assertEqual(acted, 15)
        print('15 ACTED NEW fixture/mode manifest refusals; prior loader held constant')

    def test_direct_sample_common_points_at_registered_horizons(self):
        # Horizons are diagnostic inputs, not fitted classifier constants.
        for case in self.prior['prior_pm_report']['cases']:
            for tick in case['ticks']:
                for horizon in (0, 2, 8):
                    origin = tick[10:13]
                    r = reach.certified_domain(pm.VERTICES, origin, origin, pm.MINS, pm.MAXS, horizon)
                    self.assertEqual(bool(r['polygon']), reach.spatial_witness(pm.VERTICES, origin, pm.MINS, pm.MAXS, horizon) is not None)
        print('288 ACTED exact sample horizon domains / independent point witnesses')


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__); ap.add_argument('--native-arms', type=Path)
    args, rest = ap.parse_known_args(); NATIVE_ARMS = args.native_arms
    Native.__unittest_skip__ = not bool(NATIVE_ARMS)
    unittest.main(argv=[__file__, *rest])
