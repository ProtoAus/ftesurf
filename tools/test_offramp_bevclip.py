#!/usr/bin/env python3
"""Native-semantic algebra and optional retained-native ACTED falsifiers."""
import argparse
from contextlib import redirect_stderr
from copy import deepcopy
import io
import json
from pathlib import Path
import unittest
from unittest.mock import patch

import offramp_bevclip as clip
import offramp_bevpm as pm
from offramp_motion import joint_overlap
from offramp_triangle import dot, prism, sweep
from test_offramp_triangle import prism_halfspaces

NATIVE_ARMS = None


class Units(unittest.TestCase):
    def test_plane_order_winding_and_full_slab_bevel_support(self):
        planes = clip.triangle_planes(pm.VERTICES, True)
        self.assertEqual([p['tag'] for p in planes], [*range(14), *range(100, 106)])
        self.assertTrue(pm.close(planes[5]['normal'], [0, .8, .6], 1e-6))
        points, _ = prism(pm.VERTICES)
        shifted = 0
        for p in planes:
            if p['kind'] in ('front', 'back', 'side', 'bevel'):
                self.assertAlmostEqual(p['dist'], max(dot(v, p['normal']) for v in points), places=7)
            if p['kind'] == 'bevel' and p['dist'] > max(dot(v, p['normal']) for v in pm.VERTICES)+1e-6:
                shifted += 1
        self.assertGreater(shifted, 0)
        self.assertEqual([p['tag'] for p in clip.triangle_planes(pm.VERTICES, False)], [*range(5), *range(100, 106)])

    def test_hand_derived_enter_bias_and_tie_keeps_first(self):
        r = clip.prediction(pm.VERTICES, [-8, 64, -60], [-8, 64, -68], pm.MINS, pm.MAXS, True)
        self.assertAlmostEqual(r['expected'][0], .5-1/32/4.8, places=6)
        self.assertAlmostEqual(r['expected'][1], .5, places=6)
        self.assertEqual(r['clipped']['entry_plane']['tag'], 5)
        p = [dict(tag=t, normal=[1, 0, 0], dist=0, kind='unit') for t in (9, 8)]
        g = clip.interval(p, [2, 0, 0], [-2, 0, 0], [-1]*3, [1]*3)
        self.assertEqual(g['enter'], .25)
        self.assertEqual(g['entry_plane']['tag'], 9)
        self.assertEqual(clip.interval(p[::-1], [2, 0, 0], [-2, 0, 0], [-1]*3, [1]*3)['entry_plane']['tag'], 8)

    def test_hand_derived_raw_axial_exclusion_not_physical_prism(self):
        p = [-16.25, 64, -65]
        g = clip.interval(clip.triangle_planes(pm.VERTICES, True), p, p, pm.MINS, pm.MAXS)
        self.assertFalse(g['intersects'])
        self.assertEqual(g['parallel_outside_tags'], [103])
        self.assertEqual(next(x for x in g['planes'] if x['tag'] == 103)['start_distance'], .25)
        self.assertTrue(sweep(pm.VERTICES, p, p, pm.MINS, pm.MAXS)['intersects'])
        self.assertTrue(joint_overlap(prism_halfspaces(pm.VERTICES, 4),
                                      [x+y for x, y in zip(p, pm.MINS)], [x+y for x, y in zip(p, pm.MAXS)]))
        planes = [p for p in clip.triangle_planes(pm.VERTICES, True) if p['tag'] != 103]
        self.assertTrue(clip.interval(planes, p, p, pm.MINS, pm.MAXS)['intersects'])

    def test_full_slab_axes_are_a_different_contract(self):
        points, _ = prism(pm.VERTICES)
        axes = [p for p in clip.triangle_planes(pm.VERTICES, True) if p['kind'] == 'raw-triangle-axial']
        negative_x = next(p for p in axes if p['tag'] == 103)
        self.assertEqual(negative_x['dist'], 0)
        self.assertGreater(max(dot(v, negative_x['normal']) for v in points), 2)

    def test_miss_and_every_hit_output_fault_refuse(self):
        prediction = clip.prediction(pm.VERTICES, [-8, 64, -60], [-8, 64, -68], pm.MINS, pm.MAXS, True)
        clip.check_observation(prediction['expected'], prediction)
        uncaptured = prediction['expected'].copy(); uncaptured[1] = None
        clip.check_observation(uncaptured, prediction, truefraction_observed=False)
        with self.assertRaises(AssertionError):
            clip.check_observation(prediction['expected'], prediction, truefraction_observed=False)
        for i in range(10):
            bad = prediction['expected'].copy(); bad[i] += .125
            with self.subTest(column=i), self.assertRaises(AssertionError): clip.check_observation(bad, prediction)
        miss = clip.prediction(pm.VERTICES, [-32, 64, -60], [-32, 64, -68], pm.MINS, pm.MAXS, True)
        self.assertEqual(miss['expected'], [1, 0, 0, 0, -1, 0, 0, 0, 0, 0])
        with self.assertRaises(AssertionError): clip.check_observation(prediction['expected'], miss)

    def test_wrong_hull_and_winding_cannot_explain_hand_entry(self):
        start, end = [-8, 64, -60], [-8, 64, -68]
        good = clip.prediction(pm.VERTICES, start, end, pm.MINS, pm.MAXS, True)
        for vertices, mins in ((pm.VERTICES, [-16, -16, -1]), (pm.VERTICES[::-1], pm.MINS)):
            bad = clip.prediction(vertices, start, end, mins, pm.MAXS, True)
            with self.assertRaises(AssertionError): clip.check_observation(good['expected'], bad)

    def test_nonfinite_invalid_hull_and_degenerate_refuse(self):
        for value in (float('nan'), float('inf'), -float('inf')):
            with self.assertRaises(AssertionError):
                clip.prediction(pm.VERTICES, [value, 64, -60], [-8, 64, -68], pm.MINS, pm.MAXS, True)
        with self.assertRaises(AssertionError): clip.triangle_planes([[0, 0, 0]]*3, True)
        with self.assertRaises(AssertionError): clip.triangle_planes(pm.VERTICES, 1)
        with self.assertRaises(AssertionError):
            clip.prediction(pm.VERTICES, [-8, 64, -60], [-8, 64, -68], pm.MAXS, pm.MINS, True)

    def test_cli_refuses_existing_report_before_read_or_write(self):
        argv = ['offramp_bevclip.py', '--arms', 'unused-arms.json', '--output', 'retained-report.json']
        with patch('sys.argv', argv), patch.object(Path, 'exists', return_value=True), \
                patch.object(pm, 'load_arms') as load, patch.object(Path, 'open') as output, redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as error: clip.main()
            self.assertEqual(error.exception.code, 2)
            load.assert_not_called(); output.assert_not_called()

    def test_embedded_counterfactual_has_no_modeled_wrapper_output(self):
        r = clip.prediction(pm.VERTICES, [-8, 64, -66], [-8, 64, -66], pm.MINS, pm.MAXS, True)
        self.assertTrue(r['clipped']['starts_overlap'])
        self.assertIsNone(r['expected'])
        self.assertEqual(r['wrapper_semantics'], 'EMBEDDED_NOT_MODELED')
        with self.assertRaises(AssertionError): clip.check_observation([0]*10, r)


@unittest.skipUnless(NATIVE_ARMS, 'No retained native arms; skips are NOT runtime evidence')
class Native(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.texts, _ = pm.load_arms(NATIVE_ARMS)
        cls.prior = pm.compare(*cls.texts)
        cls.result = clip.compare(*cls.texts)

    def test_all_native_queries_and_contacts_and_prior_exact(self):
        r = self.result
        self.assertEqual((r['actual_query_checks'], r['accepted_contact_checks']), (288, 18))
        self.assertEqual(r['prior_pm_report'], self.prior)
        self.assertEqual(r['on_down2_axial_exclusion_ticks'], [21, 22])
        self.assertEqual(r['on_stationary_ideal_overlap_ticks'], [])
        self.assertEqual(r['general_triangle_support'], 'ABSTAIN')
        self.assertEqual(r['physical_exit_acceptance'], 'NOT_TESTED')
        self.assertEqual(r['accepted_entry_plane_tags'], [2, 5])
        self.assertEqual(r['all_plane_runtime_coverage'], 'NOT_CLAIMED')
        self.assertEqual(r['quiet_arm_queries'], 'NOT_CAPTURED')
        self.assertEqual(json.loads(json.dumps(r, allow_nan=False)), r)
        self.assertTrue(all(x['observed_truefraction'] == 'NOT_CAPTURED' for c in r['cases'] for x in c['accepted']))

    def test_every_native_query_output_numeric_fault_new_gate_acts(self):
        acted = 0
        for c, case in enumerate(self.prior['cases']):
            for i, (t, qs) in enumerate(zip(case['ticks'], case['queries'])):
                for q in qs:
                    for col in range(9, 19):
                        bad = q.copy(); bad[col] += .125
                        # Deliberately call NEW gate directly, not prior parsing.
                        with self.subTest(case=c, tick=i, query=q[2], column=col), self.assertRaises(AssertionError):
                            clip.assess_query(bad, t, c)
                        acted += 1
        self.assertEqual(acted, 2880)
        print(f'{acted} ACTED retained-native query-output refusals in NEW independent gate, 0 failed')

    def test_every_copied_contact_output_and_tag_fault_new_gate_acts(self):
        acted = 0
        for c, case in enumerate(self.prior['cases']):
            for r in case['accepted']:
                for col in range(4, 9):
                    bad = deepcopy(r); bad['contact'][col] += .125
                    with self.subTest(case=c, tick=r['contact'][1], column=col), self.assertRaises(AssertionError):
                        clip.assess_contact(bad, c)
                    acted += 1
                bad = deepcopy(r); bad['copied_winner']['native_plane_tag'] += 1
                with self.assertRaises(AssertionError): clip.assess_contact(bad, c)
                acted += 1
        self.assertEqual(acted, 108)
        print(f'{acted} ACTED copied accepted-contact output/tag refusals in NEW gate, 0 failed')

    def test_each_axial_exclusion_relaxed_interval_matches_sat_and_joint(self):
        for i, want in ((21, .25), (22, .625)):
            q = self.result['cases'][0]['queries'][i][1]
            x = q['axial_exclusion']; p = x['separating_planes'][0]
            self.assertEqual(x['tags'], [103])
            self.assertEqual((p['start_distance'], p['end_distance']), (want, want))
            self.assertAlmostEqual(x['without_exclusions']['enter'], q['ideal_prism']['enter'], places=10)
            row = self.prior['cases'][0]['queries'][i][1]
            t = (q['ideal_prism']['enter']+q['ideal_prism']['leave'])/2
            pos = [a+t*(b-a) for a, b in zip(row[3:6], row[6:9])]
            self.assertTrue(joint_overlap(prism_halfspaces(pm.VERTICES, 4),
                                          [x+y for x, y in zip(pos, pm.MINS)], [x+y for x, y in zip(pos, pm.MAXS)]))

    def test_raw_loss_sweep_is_native_and_ideal_clear_not_axial_only_cause(self):
        loss = self.result['raw_loss_first_move']
        self.assertFalse(loss['predicted_native']['clipped']['intersects'])
        self.assertFalse(loss['ideal_prism']['intersects'])
        self.assertEqual(loss['predicted_native']['clipped']['whole_segment_outside_tags'], [2, 103])
        self.assertEqual([p['tag'] for p in loss['full_prism_separating_planes']], [2])
        self.assertGreater(loss['full_prism_separating_planes'][0]['start_distance'], .23)
        self.assertGreater(loss['full_prism_separating_planes'][0]['end_distance'], .49)
        self.assertEqual(loss['basis'], 'DERIVED_ATTEMPT_NOT_CAPTURED_ACCEPTED_TRACE')
        planes = [p for p in clip.triangle_planes(pm.VERTICES, True) if p['tag'] != 103]
        self.assertFalse(clip.interval(planes, loss['start'], loss['end'], pm.MINS, pm.MAXS)['intersects'])
        # A down2 counterfactual still intersects ideal geometry after that move.
        self.assertTrue(self.result['cases'][0]['queries'][22][1]['ideal_prism']['intersects'])

    def test_wrong_native_contract_refuses_without_touching_prior_or_arm_parity(self):
        builder = clip.triangle_planes
        points, _ = prism(pm.VERTICES)
        def slab_axes(vertices, bevels):
            planes = builder(vertices, bevels)
            for p in planes:
                if p['kind'] == 'raw-triangle-axial':
                    p['dist'] = max(dot(v, p['normal']) for v in points)
            return planes
        def no_bevels(vertices, bevels):
            return builder(vertices, False)
        def bad_side(vertices, bevels):
            planes = builder(vertices, bevels); planes[2]['dist'] += .125
            return planes
        acted = 0
        for mutant in (slab_axes, no_bevels, bad_side):
            self.assertEqual(pm.compare(*self.texts), self.prior)
            with patch.object(clip, 'triangle_planes', side_effect=mutant), self.assertRaises(AssertionError):
                clip.compare(*self.texts)
            acted += 1
        self.assertEqual(acted, 3)
        print(f'{acted} ACTED independent plane-construction mutants; prior report unchanged')

    def test_unacted_front_mutant_does_not_prove_all_plane_coverage(self):
        builder = clip.triangle_planes
        def bad_front(vertices, bevels):
            planes = builder(vertices, bevels); planes[0]['dist'] += .125
            return planes
        with patch.object(clip, 'triangle_planes', side_effect=bad_front):
            result = clip.compare(*self.texts)
        self.assertEqual(result['bounded_native_plane_set_gates'], 'PASS')
        self.assertEqual(result['prior_pm_report'], self.prior)
        # This plane is constructed/tested algebraically, NOT runtime-accepted.
        self.assertEqual({x['predicted_native']['clipped']['entry_plane']['tag'] for c in result['cases'] for x in c['accepted']}, {2, 5})

    def test_counterfactual_embedded_is_not_false_wrapper_verification(self):
        removed = self.result['cases'][1]['queries']
        rows = [q for qs in removed for q in qs if q['counterfactual_native']['clipped']['starts_overlap']]
        self.assertTrue(rows)
        self.assertTrue(all(q['counterfactual_native']['expected'] is None and not q['native_hit'] for q in rows))


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__); ap.add_argument('--native-arms', type=Path)
    args, rest = ap.parse_known_args(); NATIVE_ARMS = args.native_arms
    Native.__unittest_skip__ = not bool(NATIVE_ARMS)
    unittest.main(argv=[__file__, *rest])
