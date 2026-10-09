#!/usr/bin/env python3
"""Committed-path front reach: hand-derived kinked paths + retained-native falsifiers."""
import argparse
from contextlib import redirect_stderr
from copy import deepcopy
from fractions import Fraction as F
import io
from pathlib import Path
import unittest
from unittest.mock import patch

import offramp_bevpm as pm
import offramp_tripath as path
import offramp_trireach as walk
import offramp_trisupport as reach

NATIVE_ARMS = None
TRI = [[0, 0, 0], [0, 10, 0], [10, 0, 0]]
MINS, MAXS = [-1, -1, 0], [1, 1, 2]
# Over TRI's interior the box reaches the flat front within D iff -2 <= z <= D.
BEND = [[2, 2, 3], [2, 2, 0], [2, 2, 0], [6, 2, 0]], [F(1, 2), F(0), F(1, 2)]


def owner(command, segment, offset, share):
    return dict(command_index=command, segment=segment, attempt_ordinal=segment, command_offset=offset, command_share=share)


class Units(unittest.TestCase):
    def test_kink_hides_gap_and_recontact_the_chord_covers(self):
        points = [[2, 2, 1], [2, 2, 5], [4, 2, 1]]
        r = walk.path_reach([TRI], points, [F(1, 2), F(1, 2)], MINS, MAXS, 2)
        self.assertEqual(r['coverage'], [[F(0), F(1, 8)], [F(7, 8), F(1)]])
        self.assertEqual(r['gaps'], [dict(start=F(1, 8), end=F(7, 8), start_included=False,
                                        end_included=False, length=F(3, 4))])
        self.assertEqual(reach.patch_coverage([TRI], points[0], points[2], MINS, MAXS, 2)['coverage'], [[F(0), F(1)]])
        probes = walk.probe([TRI], r, MINS, MAXS, 2)
        self.assertTrue(0 < probes['inside_coverage'] < probes['parameters'])
        self.assertEqual(walk.regained(r['coverage']), [dict(lost_at=F(1, 8), regained_at=F(7, 8), regained_measure=F(1, 8))])

    def test_kink_reveals_reach_the_chord_misses_and_in_place_stays_apart(self):
        points, shares = [[2, 2, 5], [3, 2, 1], [4, 2, 5]], [F(1, 4), F(3, 4)]
        r = walk.path_reach([TRI], points, shares, MINS, MAXS, 2)
        self.assertEqual(r['coverage'], [[F(3, 16), F(7, 16)]])
        self.assertEqual([(g['start'], g['end'], g['start_included'], g['end_included']) for g in r['gaps']],
                         [(F(0), F(3, 16), True, False), (F(7, 16), F(1), False, True)])
        self.assertEqual(reach.patch_coverage([TRI], points[0], points[2], MINS, MAXS, 2)['coverage'], [])
        self.assertEqual(walk.path_reach([TRI], points, shares, MINS, MAXS, 0)['coverage'], [])
        self.assertEqual(walk.regained(r['coverage']), [])

    def test_recontact_counts_intervals_not_track_ends_and_names_a_bare_touch(self):
        touch = walk.regained([[F(0), F(1, 4)], [F(3, 4), F(3, 4)]])
        end = walk.regained([[F(0), F(1, 4)], [F(1), F(1)]])
        self.assertEqual(touch, [dict(lost_at=F(1, 4), regained_at=F(3, 4), regained_measure=F(0))])
        self.assertEqual(end, [dict(lost_at=F(1, 4), regained_at=F(1), regained_measure=F(0))])
        self.assertEqual([walk.recontact_verdict(x) for x in ([], touch, end, walk.regained([[0, F(1, 8)], [F(7, 8), 1]]))],
                         ['NOT_ACTED_IN_THESE_ACTORS', 'ZERO_MEASURE_TOUCH_ONLY', 'ZERO_MEASURE_TOUCH_ONLY', 'OBSERVED'])

    def test_ramp_versus_reach_decides_by_emptiness_and_lists_a_bare_touch(self):
        reached = [(0, True, dict(coverage=[], covered_share=F(0))), (1, True, dict(coverage=[[F(0), F(0)]], covered_share=F(0))),
                   (2, False, dict(coverage=[[F(0), F(1, 2)]], covered_share=F(1, 2))),
                   (3, True, dict(coverage=[[F(0), F(1)]], covered_share=F(1))), (4, False, dict(coverage=[], covered_share=F(0)))]
        self.assertEqual(walk.ramp_versus_reach(reached), dict(
            live_native_ramp_without_reach_commands=[0], live_reach_without_native_ramp_commands=[2],
            live_partially_reached_commands=[1, 2], live_zero_measure_reach_commands=[1]))

    def test_zero_share_point_adds_no_measure_and_must_not_move(self):
        points, shares = BEND
        deep = walk.path_reach([TRI], points, shares, MINS, MAXS, 2)
        here = walk.path_reach([TRI], points, shares, MINS, MAXS, 0)
        self.assertEqual(deep['coverage'], [[F(1, 6), F(1)]])
        self.assertEqual(here['coverage'], [[F(1, 2), F(1)]])
        self.assertEqual([walk.separate(a, b) for a, b in zip(here['segments'], deep['segments'])], [1, 1, 1])
        with self.assertRaisesRegex(AssertionError, 'no path share'):
            walk.path_reach([TRI], [points[0], points[1], [3, 2, 0], points[3]], shares, MINS, MAXS, 2)

    def test_separate_refuses_on_bounds_and_separately_on_the_polygon(self):
        points, shares = BEND
        deep = walk.path_reach([TRI], points, shares, MINS, MAXS, 2)['segments']
        here = walk.path_reach([TRI], points, shares, MINS, MAXS, 0)['segments']
        for a, b in ((deep[0], deep[0]), (deep[0], here[0])):
            with self.assertRaisesRegex(AssertionError, 'zero-distance edge'): walk.separate(a, b)
        # Bounds are right here, so only the polygon clause can refuse a neighbour's edge.
        self.assertEqual((here[0]['domains'][0]['downward_bounds'], deep[2]['domains'][0]['downward_bounds']),
                         ([0, 0], [0, 2]))
        self.assertNotEqual(here[0]['domains'][0]['polygon'], here[2]['domains'][0]['polygon'])
        with self.assertRaisesRegex(AssertionError, 'zero-distance edge'): walk.separate(here[0], deep[2])
        hover = [[2, 2, 1], [4, 2, 1]]
        self.assertEqual(walk.separate(*(walk.path_reach([TRI], hover, [F(1)], MINS, MAXS, d)['segments'][0] for d in (0, 2))), 0)
        # Out of reach at both horizons the polygons are equal and empty: only the bounds can tell a merged label.
        far = [walk.path_reach([TRI], [[2, 2, 9], [4, 2, 9]], [F(1)], MINS, MAXS, d)['segments'][0] for d in (0, 2)]
        self.assertEqual((far[0]['domains'][0]['polygon'], far[1]['domains'][0]['polygon'], walk.separate(*far)), ([], [], 0))
        for a, b in ((far[1], far[1]), (far[0], far[0])):
            with self.assertRaisesRegex(AssertionError, 'zero-distance edge'): walk.separate(a, b)

    def test_shares_from_native_bookkeeping_and_refusals(self):
        rows = [dict(native_left_before=.015, committed_fraction=.5), dict(native_left_before=.0075, committed_fraction=1.0)]
        point = dict(native_left_before=.015, committed_fraction=0.0)
        self.assertEqual(walk.shares(rows, .015), [F(1, 2), F(1, 2)])
        self.assertEqual(walk.shares([point, dict(native_left_before=.015, committed_fraction=1.0)], .015), [F(0), F(1)])
        for bad, duration in (([], .015), (rows[:1], .015), (rows, .016), ([point], .015),
                              ([dict(native_left_before=.015, committed_fraction=1.5)], .015),
                              ([dict(native_left_before=0.0, committed_fraction=1.0)], .015)):
            with self.assertRaises(AssertionError): walk.shares(bad, duration)

    def test_glue_and_path_refuse_bad_shares_coverage_and_shape(self):
        for pieces in ([], [(F(1, 2), [])], [(F(-1, 2), []), (F(3, 2), [])], [(F(1), [[0, 2]])], [(F(1), [[True, 1]])]):
            with self.assertRaises(AssertionError): walk.glue(pieces)
        self.assertEqual(walk.glue([(F(1, 3), [[0, 1]]), (F(2, 3), [[0, F(1, 2)]])])[0], [[F(0), F(2, 3)]])
        for points, shares in (([[0, 0, 0]], []), ([[0, 0, 0], [1, 0, 0]], [F(1), F(0)])):
            with self.assertRaises(AssertionError): walk.path_reach([TRI], points, shares, MINS, MAXS, 2)

    def test_probe_is_exhaustive_for_gluing_and_tight_at_boundaries(self):
        # One segment whose reach, local [13/50, 49/100], holds no quarter point and no midpoint.
        r = walk.path_reach([TRI], [[2, 2, F(150, 23)], [2, 2, F(-250, 23)]], [F(1)], MINS, MAXS, 2)
        self.assertEqual(r['coverage'], [[F(13, 50), F(49, 100)]])
        walk.probe([TRI], r, MINS, MAXS, 2)
        for bad in ([], [[F(13, 50), F(49, 100)-F(1, 4000)]], [[F(13, 50), F(49, 100)+F(1, 10**9)]], [[F(0), F(1)]]):
            with self.subTest(glued=bad), self.assertRaisesRegex(AssertionError, 'local segment coverage'):
                walk.probe([TRI], dict(r, coverage=bad), MINS, MAXS, 2)
        # Local and glued wrong TOGETHER: only witnesses can refuse, and they sit hard against each claimed end.
        for bad in ([[F(13, 50), F(49, 100)-F(1, 4000)]], [[F(13, 50), F(49, 100)+F(1, 10**9)]], [[F(13, 50)+F(1, 10**9), F(49, 100)]]):
            both = dict(r, coverage=bad, segments=[dict(r['segments'][0], coverage=bad)])
            with self.subTest(both=bad), self.assertRaisesRegex(AssertionError, 'common-point witness'):
                walk.probe([TRI], both, MINS, MAXS, 2)
        # Known limit, kept visible: an interval lost from BOTH is between every sample here.
        walk.probe([TRI], dict(r, coverage=[], segments=[dict(r['segments'][0], coverage=[])]), MINS, MAXS, 2)

    def test_probe_refuses_reordered_shares(self):
        r = walk.path_reach([TRI], [[2, 2, 1], [2, 2, 5], [4, 2, 1]], [F(1, 4), F(3, 4)], MINS, MAXS, 2)
        self.assertEqual(r['coverage'], [[F(0), F(1, 16)], [F(13, 16), F(1)]])
        with self.assertRaisesRegex(AssertionError, 'local segment coverage'):
            walk.probe([TRI], dict(r, shares=[F(3, 4), F(1, 4)]), MINS, MAXS, 2)

    def test_transitions_sites_bounds_horizon_limit_and_consistency(self):
        points, shares = BEND
        owners = [owner(0, 0, F(0), F(1)), owner(1, 0, F(0), F(0)), owner(1, 1, F(0), F(1))]
        deep = walk.path_reach([TRI], points, shares, MINS, MAXS, 2)
        here = walk.path_reach([TRI], points, shares, MINS, MAXS, 0)
        enter, leave = walk.transitions(deep, owners, 2)
        self.assertEqual((enter['kind'], enter['track_parameter'], enter['strictly_inside_command'],
                          enter['reachable_only_at_full_horizon']), ('enter', F(1, 6), True, True))
        self.assertEqual([(s['command_index'], s['local_t'], s['command_parameter'], s['down_range_at_boundary'])
                          for s in enter['sites']], [(0, F(1, 3), F(1, 3), [2, 2])])
        self.assertEqual((leave['kind'], leave['track_parameter']), ('track-bound', F(1)))
        # In place the entry is the joint of two commands: three sites, none strictly inside.
        joint = walk.transitions(here, owners, 0)[0]
        self.assertEqual((joint['kind'], joint['strictly_inside_command'], joint['reachable_only_at_full_horizon']),
                         ('enter', False, None))
        self.assertEqual([(s['command_index'], s['segment'], s['command_parameter']) for s in joint['sites']],
                         [(0, 0, F(1)), (1, 0, F(0)), (1, 1, F(0))])
        commands = [dict(command_index=0, x=dict(coverage=[[F(1, 3), F(1)]])), dict(command_index=1, x=dict(coverage=[[F(0), F(1)]]))]
        walk.consistent(deep['coverage'], [enter, leave], commands, 'x', 2)
        wrong = deepcopy(commands); wrong[0]['x']['coverage'] = [[F(1, 2), F(1)]]
        with self.assertRaisesRegex(AssertionError, 'command glue'): walk.consistent(deep['coverage'], [enter, leave], wrong, 'x', 2)
        moved = deepcopy(enter); moved['sites'][0]['command_parameter'] = F(1, 4)
        with self.assertRaisesRegex(AssertionError, 'boundary site'): walk.consistent(deep['coverage'], [moved, leave], commands, 'x', 2)

    def test_existing_cli_output_refused_before_input_read_or_write(self):
        argv = ['offramp_trireach.py', '--arms', 'unused.json', '--output', 'retained.json']
        with patch('sys.argv', argv), patch.object(Path, 'exists', return_value=True), \
                patch.object(path, 'load_arms') as load, patch.object(Path, 'open') as output, redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as error: walk.main()
            self.assertEqual(error.exception.code, 2)
            load.assert_not_called(); output.assert_not_called()


@unittest.skipUnless(NATIVE_ARMS, 'No retained native arms; skips are NOT runtime evidence')
class Native(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.texts, _ = path.load_arms(NATIVE_ARMS)
        cls.native = path.compare(*cls.texts)
        cls.derived = reach.compare(*cls.texts)
        cls.pristine = deepcopy((cls.native, cls.derived))
        cls.previous = cls.native['prior_plane_set_report']['prior_pm_report']['cases']
        cls.result = walk.assess(cls.native, cls.derived)
        cls.on, cls.removed, cls.off = cls.result['cases']

    def case(self, index, change=None):
        native, derived = deepcopy(self.native['cases'][index]), deepcopy(self.derived['cases'][index])
        if change:
            change(native, derived)
        return walk.assess_case(native, self.previous[index], derived, index)

    def test_registered_structure_measured_counts_flags_and_inputs_untouched(self):
        r = self.result
        each = lambda key: [c[key] for c in r['cases']]
        self.assertEqual(each('segment_count'), [44, 32, 38])
        self.assertEqual(each('point_segment_count'), [10, 0, 4])
        self.assertEqual(each('kinked_commands'), [[10, 16], [], [6, 11]])
        # A kink is resolved only beyond one float32 step of the command's coordinates.
        self.assertEqual(each('resolved_kink_commands'), [[10], [], [6]])
        self.assertEqual(each('coverage_differs_from_chord_commands'), [[10], [], []])
        self.assertEqual(each('coverage_differs_below_float32_commands'), [[], [], [11]])
        self.assertEqual((r['committed_path_vs_chord'], r['kinked_command_count'], r['resolved_kink_command_count']), ('ACTED', 4, 2))
        unkinked = [c for case in r['cases'] for c in case['commands'] if c['path_is_endpoint_chord']]
        self.assertEqual((len(unkinked), {c['chord_comparison'] for c in unkinked}), (92, {'EQUAL'}))
        rows = [s for case in r['cases'] for c in case['commands'] for s in c['segments']]
        # A clear pass prints truefraction 0; the report must not carry that as an entry.
        self.assertEqual(sum(s['native_hit'] for s in rows), 18)
        self.assertTrue(all((s['truefraction'] is None) == (s['native_plane'] is None) == (not s['native_hit']) for s in rows))
        self.assertEqual(each('live_native_ramp_without_reach_commands'), [[], [], [6, 7, 8, 9, 10]])
        self.assertEqual(each('live_partially_reached_commands'), [[10, 21], [], [11]])
        self.assertEqual(each('live_reach_without_native_ramp_commands'), [[], [], []])
        self.assertEqual(each('live_zero_measure_reach_commands'), [[], [], []])
        # Measured on the retained arms; what the gates had to chew on, not a prediction.
        self.assertEqual(r['common_point_probes'], dict(parameters=1245, inside_coverage=233, live_inside_coverage=91))
        self.assertEqual(each('in_place_edge_nonempty_count'), [0, 12, 0])
        self.assertEqual(r['in_place_edge_checks'], dict(segments=114, nonempty=12))
        for key, want in (('general_triangle_support', 'ABSTAIN'), ('native_front_reach_equivalence', 'NOT_CLAIMED'),
                          ('physical_exit_acceptance', 'NOT_TESTED'), ('standability_load_bearing_acceptance', 'NOT_TESTED'),
                          ('discovered_neighborhood_topology', 'NOT_IMPLEMENTED'), ('classifier_render_hold_clock', 'NOT_TESTED')):
            self.assertEqual(r[key], want)
        self.assertEqual((self.native, self.derived), self.pristine)

    def test_on_enters_before_the_chord_and_exits_exactly_inside_a_ramp_command(self):
        t = self.on['track']['hypothetical_down']
        self.assertEqual((len(t['live_coverage']), t['live_regained']), (1, []))
        lo, hi = t['live_coverage'][0]
        self.assertEqual(hi, F(2, 3))
        enter, leave = t['front_transitions']
        self.assertEqual((enter['kind'], leave['kind']), ('enter', 'exit'))
        self.assertTrue(enter['strictly_inside_command'] and leave['strictly_inside_command'])
        # The entry is the horizon cut and would move with it; the exit is the footprint edge.
        self.assertEqual((enter['reachable_only_at_full_horizon'], leave['reachable_only_at_full_horizon']), (True, False))
        (site,) = enter['sites']
        self.assertEqual((site['command_index'], site['segment'], site['down_range_at_boundary']), (10, 0, [2, 2]))
        self.assertAlmostEqual(float(site['local_t']), .339225215, delta=5e-9)
        self.assertAlmostEqual(float(site['command_parameter']), .257072427, delta=5e-9)
        self.assertEqual(lo, (10+site['command_parameter'])/32)
        command = self.on['commands'][10]
        self.assertEqual((command['chord_comparison'], command['kink_resolved']), ('DIFFERS', True))
        self.assertAlmostEqual(float(command['chord_boundary_shift']), .082152210, delta=5e-9)
        self.assertEqual(command['hypothetical_down']['coverage'], [[site['command_parameter'], F(1)]])
        (site,) = leave['sites']
        self.assertEqual((site['command_index'], site['segment'], site['local_t'], site['command_parameter']),
                         (21, 1, F(1, 3), F(1, 3)))
        self.assertEqual((site['origin'][0]+pm.MAXS[0], site['down_range_at_boundary'][1]), (0, 2))
        self.assertTrue(self.on['commands'][21]['native_ramp_return'])
        self.assertEqual([c['command_index'] for c in self.on['commands'] if c['hypothetical_down']['coverage']],
                         [c['command_index'] for c in self.on['commands'] if c['native_ramp_return']])
        self.assertEqual([(g['length'], g['nominal_seconds_not_exit_clock']) for g in t['live_gaps']],
                         [(lo, lo*F(12, 25)), (F(1, 3), F(4, 25))])

    def test_off_interior_reach_at_horizon_two_only_and_its_chord_difference_is_unresolved(self):
        t = self.off['track']['hypothetical_down']
        self.assertEqual((len(t['live_coverage']), t['live_regained']), (1, []))
        enter, leave = t['front_transitions']
        self.assertEqual((enter['reachable_only_at_full_horizon'], leave['reachable_only_at_full_horizon']), (True, False))
        for transition, local, parameter in ((enter, .067784460, .067816457), (leave, .648758114, .648770170)):
            (site,) = transition['sites']
            self.assertEqual((site['command_index'], site['segment']), (11, 1))
            self.assertAlmostEqual(float(site['local_t']), local, delta=5e-9)
            self.assertAlmostEqual(float(site['command_parameter']), parameter, delta=5e-9)
            self.assertEqual(transition['track_parameter'], (11+site['command_parameter'])/32)
        points = [pm.SEED[:3]]+[s['end'] for c in self.off['commands'] for s in c['segments']]
        seen = [sum(reach.spatial_witness(pm.VERTICES, p, pm.MINS, pm.MAXS, d) is not None for p in points) for d in (2, 4, 8)]
        self.assertEqual((len(points), seen), (39, [0, 2, 4]))
        self.assertEqual([c['command_index'] for c in self.off['commands'] if c['native_ramp_return']], list(range(6, 12)))
        self.assertEqual([c['command_index'] for c in self.off['commands'] if c['hypothetical_down']['coverage']], [11])
        command = self.off['commands'][11]
        self.assertEqual((command['chord_comparison'], command['kink_resolved']), ('DIFFERS_BELOW_FLOAT32_KINK', False))
        self.assertLess(command['kink_offset_units'], command['float32_step_units'])
        self.assertLess(command['chord_boundary_shift'], F(1, 10**6))
        self.assertEqual((self.off['commands'][6]['chord_comparison'], self.off['commands'][6]['kink_resolved']), ('EQUAL', True))

    def test_removed_is_counterfactual_only_and_enters_in_place_at_live_truefraction(self):
        for name, _ in walk.HORIZONS:
            t = self.removed['track'][name]
            self.assertEqual((t['front_is_live'], t['live_coverage'], t['live_gaps'][0]['length'], len(t['front_coverage'])),
                             (False, [], 1, 1))
        self.assertFalse(any(c[n]['front_is_live'] for c in self.removed['commands'] for n, _ in walk.HORIZONS))
        # Same free fall as the live actor until its first hit: one hit, one comparison.
        (site,) = self.removed['track']['in_place']['front_transitions'][0]['sites']
        hit = self.on['native_hits'][0]
        self.assertEqual((site['command_index'], hit['command_index']), (10, 10))
        self.assertAlmostEqual(float(site['command_parameter']), hit['truefraction'], delta=2e-7)

    def test_live_in_place_is_empty_and_each_actor_rides_its_own_plane_bias(self):
        for case, count in ((self.on, 24), (self.off, 1)):
            self.assertEqual(case['track']['in_place']['live_coverage'], [])
            self.assertFalse(any(s['in_place']['coverage'] for c in case['commands'] for s in c['segments']))
            lows = [s['hypothetical_down']['domains'][0]['reach_distance_range'][0] for c in case['commands']
                    for s in c['segments'] if s['hypothetical_down']['coverage']]
            (normal_z,) = {s['native_plane'][2] for c in case['commands'] for s in c['segments'] if s['native_hit']}
            self.assertEqual(len(lows), count)
            # 1/32 off the plane the body actually hit, read off vertically: 0.0521 bevel, 0.1012 side.
            self.assertTrue(all(abs(float(x)-1/32/normal_z) < 2e-5 for x in lows))
        self.assertEqual(sum(bool(s['in_place']['coverage']) for c in self.removed['commands'] for s in c['segments']), 12)

    def test_hits_one_fresh_entry_eleven_bias_recontacts_and_ghosts_miss_the_front(self):
        on, off = self.on['native_hits'], self.off['native_hits']
        self.assertEqual((len(on+off), sum(h['hypothetical_down_reachable'] for h in on+off)), (18, 12))
        self.assertFalse(any(h['hypothetical_down_reachable'] for h in off))
        self.assertEqual([h['command_index'] for h in on+off if not h['previous_command_native_ramp']], [10, 6])
        # The one fresh entry: exact front entry on the REQUESTED sweep against native truefraction.
        self.assertAlmostEqual(float(on[0]['front_entry_after_native_along_contact_normal']), -2.8934e-7, delta=1e-10)
        again = [abs(float(h['front_entry_after_native_along_contact_normal'])) for h in on[1:]]
        self.assertEqual(len(again), 11)
        self.assertLess(max(again), 7e-6)
        self.assertTrue(all(abs(h['truefraction']-.28933) < 6e-5 for h in on[1:]))
        self.assertEqual([h['requested_sweep_front_entry'] is None for h in off], [True]*5+[False])
        self.assertAlmostEqual(float(off[5]['front_entry_minus_truefraction']), .107573247, delta=5e-9)

    def test_no_recontact_acted_and_that_is_reported_not_passed(self):
        self.assertEqual(self.result['live_interior_gap_recontact'], 'NOT_ACTED_IN_THESE_ACTORS')
        self.assertEqual([c['track'][n]['live_regained'] for c in self.result['cases'] for n, _ in walk.HORIZONS], [[]]*6)

    def test_chord_substituted_for_captured_segments_refuses(self):
        real = walk.committed
        def chord(call, tick, body, ordinal):
            return [dict(real(call, tick, body, ordinal)[-1], segment=0, start=body, committed_fraction=1.0,
                         native_left_before=call['call'][2], native_hit=False, native_plane=None)]
        with patch.object(walk, 'committed', side_effect=chord), self.assertRaisesRegex(AssertionError, 'captured kink'):
            walk.assess(self.native, self.derived)
        self.assertEqual(path.clip.compare(*self.texts), self.native['prior_plane_set_report'])

    def test_wrong_nominal_shares_refuse_at_captured_kinematics(self):
        def equal(rows, duration):
            return [F(1, len(rows))]*len(rows)
        def left_after(rows, duration):
            w = [reach.rational(r['native_left_after'])*reach.rational(r['committed_fraction']) for r in rows]
            return [x/sum(w) for x in w]
        def geometric(rows, duration):  # truefraction instead of the committed biased fraction
            w = [reach.rational(r['native_left_before'])*reach.rational(r['truefraction'] if r['native_hit'] else 1) for r in rows]
            return [x/sum(w) for x in w]
        for mutant in (equal, left_after, geometric):
            with self.subTest(mutant=mutant.__name__), patch.object(walk, 'shares', side_effect=mutant), \
                    self.assertRaisesRegex(AssertionError, 'velocity x nominal share'):
                walk.assess(self.native, self.derived)

    def test_horizon_merge_or_label_exchange_refuses(self):
        for mutant in ((('in_place', 2), ('hypothetical_down', 2)), (('in_place', 2), ('hypothetical_down', 0))):
            with self.subTest(mutant=mutant), patch.object(walk, 'HORIZONS', mutant), \
                    self.assertRaisesRegex(AssertionError, 'zero-distance edge'):
                self.case(0)

    def test_shifted_track_glue_refuses_against_local_coverage(self):
        real = walk.glue
        def shifted(pieces):
            return real(pieces[1:]+pieces[:1]) if len(pieces) > 2 else real(pieces)
        for index in (0, 2):
            with self.subTest(case=index), patch.object(walk, 'glue', side_effect=shifted), \
                    self.assertRaisesRegex(AssertionError, 'local segment coverage'):
                self.case(index)

    def test_track_or_command_shares_exchanged_refuse_against_each_other(self):
        real_reach, real_glue = walk.path_reach, walk.glue
        for index, first in ((0, 10), (2, 16)):  # global segment of the resolved/unresolved kink that carries reach
            def track(triangles, points, shares, *rest):
                shares = list(shares); shares[first], shares[first+1] = shares[first+1], shares[first]
                return real_reach(triangles, points, shares, *rest)
            def command(pieces):
                return real_glue([(pieces[1][0], pieces[0][1]), (pieces[0][0], pieces[1][1])] if len(pieces) == 2 else pieces)
            for name, target, mutant in (('track', 'path_reach', track), ('command', 'glue', command)):
                with self.subTest(case=index, shares=name), patch.object(walk, target, side_effect=mutant), \
                        self.assertRaisesRegex(AssertionError, 'command glue'):
                    self.case(index)

    def test_stuck_command_offset_refuses_at_boundary_site(self):
        real = walk.transitions
        def stuck(result, owners, horizon):
            found = real(result, owners, horizon)
            for t in found:
                for s in t['sites']:
                    s['command_parameter'] = s['local_t']*owners[s['attempt_ordinal']]['command_share']
            return found
        with patch.object(walk, 'transitions', side_effect=stuck), self.assertRaisesRegex(AssertionError, 'boundary site'):
            self.case(2)

    def test_forged_derived_chord_refuses_kinked_and_unkinked_alike(self):
        for index, command in ((0, 10), (0, 12), (2, 11)):
            def forge(native, derived):
                domain = derived['segments'][command]['front_domain']
                domain['coverage'] = [domain['coverage'][0], domain['coverage'][1]-F(1, 1000)]
            with self.subTest(case=index, command=command), self.assertRaisesRegex(AssertionError, 'recomputation'):
                self.case(index, forge)
        own = self.on['commands'][10]['hypothetical_down']['coverage'][0]
        def agree(native, derived):
            derived['segments'][10]['front_domain']['coverage'] = list(own)
        with self.assertRaisesRegex(AssertionError, 'recomputation'): self.case(0, agree)

    def test_identity_duration_ramp_hull_and_actor_order_gates_fire(self):
        def ordinal(native, derived):  # shifted alike in all three rows of one segment
            call = native['calls'][5]
            call['committed_segments'][0]['attempt_ordinal'] += 1; call['attempts'][0][0] += 1; call['outcomes'][0][0] += 1
        def ramp(native, derived):
            native['calls'][12]['returned'][-1] = 0.0
        def hull(native, derived):
            native['calls'][3]['attempts'][0][17] -= 1
        for change, message in ((ordinal, 'identity'), (ramp, 'ramp flag'), (hull, 'fixed AABB')):
            with self.subTest(change=change.__name__), self.assertRaisesRegex(AssertionError, message):
                self.case(0, change)
        ticks = deepcopy(self.previous[0]); ticks['ticks'][7][2] = 30
        with self.assertRaisesRegex(AssertionError, 'duration'):
            walk.assess_case(self.native['cases'][0], ticks, self.derived['cases'][0], 0)
        with self.assertRaisesRegex(AssertionError, 'actor order'):
            walk.assess_case(self.native['cases'][0], self.previous[0], self.derived['cases'][0], 1)

    def test_every_mirrored_committed_field_fault_refuses_chain_binding(self):
        # s/attempt/outcome mirrors move together, so only the chain can refuse.
        mirrors = dict(start=('attempts', 5), end=('attempts', 34), native_left_before=('attempts', 4),
                       native_left_after=('outcomes', 2), committed_fraction=('attempts', 24))
        acted = 0
        for index, case in enumerate(self.native['cases']):
            ticks = self.previous[index]['ticks']
            for i, call in enumerate(case['calls']):
                body, first = pm.SEED[:3] if i == 0 else ticks[i-1][10:13], call['attempts'][0][0]
                self.assertTrue(walk.committed(call, ticks[i], body, first))
                for k in range(len(call['committed_segments'])):
                    for key, (rows, where) in mirrors.items():
                        for axis in range(3 if key in ('start', 'end') else 1):
                            bad = deepcopy(call)
                            s, row = bad['committed_segments'][k], bad[rows][k]
                            if key in ('start', 'end'):
                                s[key][axis] += .125; row[where+axis] += .125
                                if key == 'end': bad['outcomes'][k][3+axis] += .125
                            else:
                                s[key] += .125; row[where] += .125
                            with self.subTest(case=index, call=i, segment=k, key=key, axis=axis), self.assertRaises(AssertionError):
                                walk.committed(bad, ticks[i], body, first)
                            acted += 1
        self.assertEqual(acted, 114*9)
        print(f'{acted} ACTED mirrored committed-field chain refusals (binding, not independent native semantics)')

    def test_committed_segment_coverage_nests_where_there_is_something_to_nest(self):
        filled = [0, 0, 0]
        for case in self.result['cases']:
            for c in case['commands']:
                for s in c['segments']:
                    deep = reach.patch_coverage([pm.VERTICES], s['start'], s['end'], pm.MINS, pm.MAXS, 8)['coverage']
                    chain = (s['in_place']['coverage'], s['hypothetical_down']['coverage'], deep)
                    for inner, outer in zip(chain, chain[1:]):
                        self.assertTrue(all(any(a <= lo and hi <= b for a, b in outer) for lo, hi in inner))
                    filled = [n+bool(x) for n, x in zip(filled, chain)]
        # Empty nests in anything: only these many segments had coverage at horizons 0/2/8 (measured).
        self.assertEqual(filled, [12, 37, 45])
        print(f'114 committed segments nest across horizons 0/2/8; non-empty at each: {filled}')


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__); ap.add_argument('--native-arms', type=Path)
    args, rest = ap.parse_known_args(); NATIVE_ARMS = args.native_arms
    Native.__unittest_skip__ = not bool(NATIVE_ARMS)
    unittest.main(argv=[__file__, *rest])
