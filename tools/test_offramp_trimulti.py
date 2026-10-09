#!/usr/bin/env python3
"""Multi-patch actors: fixture/installer units + ACTED native falsifiers on retained arms."""
import argparse
from contextlib import redirect_stderr
from copy import deepcopy
from fractions import Fraction as F
import io
import json
from pathlib import Path
import re
import sys
import unittest
from unittest.mock import patch

import offramp_bevpm as pm
import offramp_trimulti as multi
import offramp_trimulti_smoke as installer
import offramp_trireach as walk
import offramp_trisupport as reach

ARMS = None
CASES = re.compile(r'OFFRAMPTRIMULTI_CASE [0-9]+ .*?(?=OFFRAMPTRIMULTI_CASE_END)', re.S)
SINGLE, SECOND = 'NATIVE_SINGLE_PLANE_BRANCH_VERIFIED', 'SECOND_PLANE_NOT_VERIFIED'


def bumped(line, column, step=None):
    """The same row with one field changed.

    An integer moves by one, so the MEANING behind it has to refuse and not
    merely the integer parser; another number moves by 1/8 (or `step`); a word
    becomes a foreign word.
    """
    words = line.split()
    try:
        words[column] = str(int(words[column])+1) if step is None else repr(float(words[column])+step)
    except ValueError:
        try:
            words[column] = repr(float(words[column])+(.125 if step is None else step))
        except ValueError:
            words[column] = 'x'
    return ' '.join(words)


def row(text, start):
    return next(l[l.find(start):] for l in text.splitlines() if start in l)


def forged(block, edits):
    """Several rows moved TOGETHER: {row start: {word: delta}}. A consistent lie only one gate can see."""
    for start, changes in edits.items():
        old = row(block, start)
        new = old
        for column, delta in changes.items():
            new = bumped(new, column, delta)
        block = block.replace(old, new, 1)
    return block


class Units(unittest.TestCase):
    def test_authored_patches_are_coplanar_upward_exact_and_removed_twin_matches(self):
        self.assertEqual([len(multi.authored(i)) for i in range(5)], [4, 4, 4, 4, 2])
        self.assertEqual(multi.authored(2), multi.authored(3))
        for actor in range(5):
            for triangle in multi.authored(actor):
                a, b, c = (reach.vector(v) for v in triangle)
                normal = reach.cross(reach.sub(a, b), reach.sub(c, b))
                # One plane family 0.8x+0.6z=const, wound so the front faces up.
                self.assertEqual((normal[0]*3, normal[1]), (normal[2]*4, 0))
                self.assertGreater(normal[2], 0)
        low = multi.authored(2)[2]
        self.assertEqual(low, [[0, 114, -2], [0, 256, -2], [192, 256, -258]])
        self.assertEqual({F(4, 5)*x+F(3, 5)*z for x, _, z in low}, {F(-6, 5)})

    def test_unknown_malformed_duplicate_and_outside_rows_refuse(self):
        envelope = 'OFFRAMPTRIMULTI_BEGIN 2 0 0 5 32\nOFFRAMPTRIMULTI_END 5\n'
        self.assertEqual(multi.split('a\n'+envelope+'b\n'), ('a\nb\n', envelope))
        # Unknown and malformed rows sit INSIDE an envelope, so only the row gate can refuse them.
        for text, message in ((envelope.replace('OFFRAMPTRIMULTI_END 5', 'OFFRAMPTRIMULTI_UNKNOWN 1\nOFFRAMPTRIMULTI_END 5'), 'unknown/malformed'),
                              (envelope.replace(' 5 32\n', ' 5\n'), 'unknown/malformed'), (envelope+envelope, 'missing/duplicate'),
                              ('no envelope', 'missing/duplicate'), (envelope+'OFFRAMPTRIMULTI_LEAVES 0 4 0\n', 'outside envelope')):
            with self.subTest(text=text[-40:]), self.assertRaisesRegex(AssertionError, message): multi.split(text)
        self.assertEqual(multi.foreign('x OFFRAMPGEOM_BEGIN 2\nOFFRAMPTRIMULTI_TICK 0\nOFFRAMPTRIMULTIX_ROW 1'),
                         ['OFFRAMPGEOM_', 'OFFRAMPTRIMULTIX_'])

    def test_coplanar_bevel_ties_the_face_and_coplanar_neighbours_tie_each_other(self):
        first, second = multi.authored(0)[:2]
        start, end = [46, 24, -39.5], [46, 24, -41.5]
        found = multi.candidates(first, start, end)
        tags = [c['clipped']['entry_plane']['tag'] for c in found]
        # Tag 8 is the slope-direction edge crossed with y: the face plane again. A second such bevel (11)
        # is oriented by rounding alone, here and natively, because its off-vertex lies IN the plane.
        self.assertEqual((tags[:2], set(tags) <= {0, 8, 11}), ([0, 8], True))
        self.assertEqual(len({c['clipped']['enter'] for c in found}), 1)
        self.assertTrue(all(pm.close(c['clipped']['entry_plane']['normal'], [.8, 0, .6], 1e-12) and
                            abs(c['clipped']['entry_plane']['dist']) < 1e-12 for c in found))
        both = multi.native_prediction([first, second], start, end)
        self.assertEqual(len(both), len(found)+len(multi.candidates(second, start, end)))
        self.assertEqual({c['triangle'] for c in both}, {0, 1})
        self.assertEqual(multi.native_prediction([first, second], [46, 24, 50], [46, 24, 48]), [dict(expected=multi.MISS)])
        self.assertEqual(multi.native_prediction([], start, end), [dict(expected=multi.MISS)])
        with self.assertRaisesRegex(AssertionError, 'embedded'):
            multi.native_prediction([first], [46, 24, -41], [46, 24, -43])
        hit = [*both[0]['expected'], *[s+both[0]['expected'][0]*(e-s) for s, e in zip(start, end)]]
        self.assertEqual(multi.check_trace(hit, start, end, [first, second]), dict(triangles=2, candidates=len(both)))
        self.assertEqual(multi.check_trace(hit, start, end, [first]), dict(triangles=1, candidates=len(found)))
        self.assertEqual(multi.check_trace([*multi.MISS, 46, 24, 48], [46, 24, 50], [46, 24, 48], [first]), dict(triangles=0, candidates=0))

    def test_plane_list_clears_on_any_move_and_only_a_second_standing_hit_is_unverified(self):
        self.assertEqual(multi.clip_branch(0, .3), (1, SINGLE))
        self.assertEqual(multi.clip_branch(0, 0), (1, SINGLE))
        self.assertEqual(multi.clip_branch(1, 0), (2, SECOND))
        self.assertEqual(multi.clip_branch(2, 0), (3, SECOND))
        # A hit after a positive move is the single-plane branch again, whatever came before.
        self.assertEqual(multi.clip_branch(2, 1e-9), (1, SINGLE))

    def test_sat_only_sensitivity_equals_certified_coverage_and_nests(self):
        triangles = multi.authored(4)
        points = [[46, 24, -39.5], [47, 30, -36], [48, 36, -39]]
        shares = [F(1, 2), F(1, 2)]
        certified = walk.path_reach(triangles, points, shares, multi.MINS, multi.MAXS, 2)
        rational = [reach.vector(p) for p in points]
        found = [multi.sensitivity(triangles, rational, shares, h) for h in (2, 4, 8)]
        self.assertEqual(found[0]['coverage'], certified['coverage'])
        self.assertTrue(0 < len(found[0]['coverage']) and found[0]['coverage'] != found[2]['coverage'])
        for inner, outer in zip(found, found[1:]):
            self.assertTrue(all(any(a <= lo and hi <= b for a, b in outer['coverage']) for lo, hi in inner['coverage']))
        here, deep = (walk.path_reach(triangles, points, shares, multi.MINS, multi.MAXS, h)['segments'] for h in (0, 2))
        self.assertEqual(multi.edge_checks(here, deep, 2), dict(segments=2, domain_pairs=4, nonempty_segments=0, nonempty_domains=0))
        sunk = [[46, 24, -41], [46, 30, -41]]  # through the plane: both triangles under the hull edge
        here, deep = (walk.path_reach(triangles, sunk, [F(1)], multi.MINS, multi.MAXS, h)['segments'] for h in (0, 2))
        self.assertEqual(multi.edge_checks(here, deep, 2), dict(segments=1, domain_pairs=2, nonempty_segments=1, nonempty_domains=2))

    def test_removed_twin_must_share_a_prefix_then_part_and_have_fewer_leaves(self):
        tick = lambda x: [0]*10+[x, 0, 0, 0, 0, 0]
        kept = dict(ticks=[tick(1), tick(2), tick(3)], native_leaves=[0, 1, 2, 3])
        parted = dict(ticks=[tick(1), tick(2), tick(9)], native_leaves=[0, 1])
        self.assertEqual(multi.removal_acts(kept, parted), 2)
        for twin in (dict(parted, ticks=kept['ticks']), dict(parted, ticks=[tick(9), tick(2), tick(3)]),
                     dict(parted, native_leaves=kept['native_leaves'])):
            with self.assertRaisesRegex(AssertionError, 'did not ACT'): multi.removal_acts(kept, twin)

    def test_predecessor_report_must_equal_a_retained_one_when_one_is_given(self):
        prior = dict(count=3, coverage=[[F(0), F(1, 2)]], nested=dict(flag='PASS'))
        retained = dict(count=3, coverage=[['0', '1/2']], nested=dict(flag='PASS'), arms='theirs')
        self.assertEqual(multi.same_prior(prior, retained), 'EQUAL_TO_RETAINED_REPORT')
        for bad in (dict(retained, count=4), dict(retained, coverage=[['0', '1/3']]), {k: v for k, v in retained.items() if k != 'nested'}):
            with self.assertRaisesRegex(AssertionError, 'differs from the retained one'): multi.same_prior(prior, bad)

    def test_installer_collision_and_missing_seam_write_nothing(self):
        root = Path('unpopulated-readonly-engine')
        prior = {root/'engine/common/pm_source.c': 'no forward declaration here', root/'engine/common/com_bih.c': ''}
        # Only THIS layer's includes exist, and the earlier layers are stubbed, so only this layer's check can refuse.
        mine = lambda self: self.name in installer.TARGETS
        with patch.object(installer, 'isolated'), patch.object(Path, 'exists', mine), \
                patch.object(installer, 'path_prepare', return_value=dict(prior)) as earlier, patch.object(Path, 'write_text') as write:
            with self.assertRaisesRegex(RuntimeError, 'multi-patch include'): installer.instrument(root)
            earlier.assert_not_called(); write.assert_not_called()
        with patch.object(installer, 'isolated'), patch.object(Path, 'exists', return_value=False), \
                patch.object(installer, 'path_prepare', return_value=dict(prior)), patch.object(Path, 'write_text') as write:
            with self.assertRaisesRegex(RuntimeError, 'seam mismatch'): installer.instrument(root)
            write.assert_not_called()

    def test_existing_report_refuses_before_read_or_write(self):
        with patch.object(sys, 'argv', ['multi', '--arms', 'absent', '--output', 'existing']), \
                patch.object(Path, 'exists', return_value=True), patch.object(multi, 'load_arms') as load, \
                patch.object(Path, 'open') as opened, redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as error: multi.main()
            self.assertEqual(error.exception.code, 2); load.assert_not_called(); opened.assert_not_called()


@unittest.skipUnless(ARMS, 'Retained native arms not supplied; NOT runtime evidence')
class Native(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.texts, _ = multi.load_arms(ARMS)
        cls.result = multi.compare(*cls.texts)
        cls.cases, cls.native = cls.result['cases'], cls.result['native_cases']
        cls.blocks = {name: CASES.findall(multi.split(text)[1]) for name, text in zip(multi.NAMES, cls.texts)}
        real, cache = multi.candidates, {}
        def cached(triangle, start, end):
            key = (repr(triangle), repr(start), repr(end))
            if key not in cache:
                cache[key] = real(triangle, start, end)
            return cache[key]
        cls.cached = staticmethod(cached)  # one row changes per mutant; every other prediction is the same

    def refusals(self, arm, capture, oracle, prefix, cases=range(5), keep=lambda words, column: True):
        acted = 0
        with patch.object(multi, 'candidates', side_effect=self.cached):
            for case in cases:
                block = self.blocks[arm][case]
                multi.grade_case(block, case, capture, oracle)
                for line in [l[l.find(prefix):] for l in block.splitlines() if prefix in l]:
                    words = line.split()
                    for column in range(1, len(words)):
                        if not keep(words, column):
                            continue
                        mutated = block.replace(line, bumped(line, column), 1)
                        self.assertNotEqual(mutated, block)
                        with self.subTest(case=case, row=' '.join(words[:3]), column=column), self.assertRaises(AssertionError):
                            multi.grade_case(mutated, case, capture, oracle)
                        acted += 1
        return acted

    def test_registered_structure_and_measured_counts(self):
        r, each = self.result, lambda key: [c[key] for c in self.cases]
        path_counts = lambda key: [n['path'][key] for n in self.native]
        self.assertEqual(path_counts('attempt_count'), [62, 62, 58, 40, 50])
        self.assertEqual(path_counts('hit_count'), [30, 30, 26, 8, 18])
        self.assertEqual((r['native_attempt_count'], r['accepted_copied_hit_count'], r['committed_segment_count']), (272, 112, 272))
        ramp = [[c['command_index'] for c in case['commands'] if c['native_ramp_return']] for case in self.cases]
        self.assertEqual(ramp, [list(range(2, 32)), list(range(2, 32)), [*range(2, 10), *range(14, 32)],
                                list(range(2, 10)), list(range(14, 32))])
        self.assertEqual([case['native_hits'][0]['command_index'] for case in self.cases], [2, 2, 2, 2, 14])
        self.assertTrue(all(case['native_hits'][0]['committed_fraction'] > .1 for case in self.cases))
        self.assertEqual((r['second_plane_command_count'], r['second_plane_clip_semantics'], r['down2_disagreement_count']),
                         (0, 'NOT_EXERCISED', 0))
        self.assertEqual(each('second_plane_commands'), [[]]*5)
        rules = [s['clip_rule'] for case in self.cases for c in case['commands'] for s in c['segments']]
        self.assertEqual((rules.count(SINGLE), rules.count(None), len(rules)), (112, 160, 272))
        # No command has more than two attempts and every hit is its command's first: more bumps are unexercised.
        self.assertEqual({len(c['segments']) for case in self.cases for c in case['commands']}, {1, 2})
        self.assertFalse(any(h['bump'] for case in self.cases for h in case['native_hits']))
        self.assertEqual(r['live_horizon2_reach_regained'], ['NOT_ACTED_IN_THESE_ACTORS', 'NOT_ACTED_IN_THESE_ACTORS', 'OBSERVED',
                                                            'NOT_ACTED_IN_THESE_ACTORS', 'OBSERVED'])
        # Measured, not predicted: how much the gates had to compare, and how much of it is distinct.
        self.assertEqual(path_counts('validation_count'), [2, 2, 6, 24, 14])
        self.assertEqual(r['distinct'], dict(attempts=209, hits=88, tick_end_bodies=119, zero_length_segments=91))
        self.assertEqual((each('triangle_tie_trace_count'), each('plane_only_tie_trace_count')),
                         ([12, 10, 7, 0, 0], [18, 18, 15, 8, 18]))
        self.assertEqual((r['triangle_tie_trace_count'], r['plane_only_tie_trace_count']), (29, 77))
        self.assertEqual(r['common_point_probes'], dict(parameters=2207, inside_coverage=885))
        self.assertEqual(r['in_place_edge'], dict(
            live=dict(segments=272, domain_pairs=908, nonempty_segments=0, nonempty_domains=0),
            full_authored_set_counterfactual=dict(segments=40, domain_pairs=160, nonempty_segments=18, nonempty_domains=27)))
        self.assertEqual(r['predecessor_report'], 'NOT_COMPARED_WITH_A_RETAINED_REPORT')
        for key, want in (('general_triangle_support', 'ABSTAIN'), ('native_front_reach_equivalence', 'NOT_CLAIMED'),
                          ('discovered_neighborhood_topology', 'NOT_IMPLEMENTED'),
                          ('physical_exit_acceptance', 'NOT_TESTED'), ('standability_load_bearing_acceptance', 'NOT_TESTED'),
                          ('classifier_render_hold_clock', 'NOT_TESTED')):
            self.assertEqual(r[key], want)

    def test_supplied_set_is_the_native_dump_and_winners_are_its_nodes(self):
        self.assertEqual([[(x['node'], x['indexes']) for x in n['native_leaves']] for n in self.native],
                         [[(j+1, list(i)) for j, i in enumerate(multi.INDEXES)]]*3+[[(j+1, list(i)) for j, i in enumerate(multi.INDEXES[:2])]]*2)
        for index, (case, native) in enumerate(zip(self.cases, self.native)):
            dumped = [x['vertices'] for x in native['native_leaves']]
            self.assertEqual((case['supplied_patch_set']['triangles'], native['supplied']), (dumped, dumped))
            self.assertTrue(all(type(x) is float for t in dumped for v in t for x in v))
            self.assertEqual(dumped, multi.authored(index)[:len(dumped)])
        order = [list(dict.fromkeys(c['winner_triangles_in_order'])) for c in self.cases]
        self.assertEqual(order, [[0, 3, 2], [0, 3, 2], [0, 3, 2], [0], [0]])
        # P1 before the gap, P2 after it, never interleaved.
        wide = self.cases[2]['native_hits']
        self.assertEqual({h['winner_triangle'] for h in wide if h['command_index'] < 10}, {0})
        self.assertEqual({h['winner_triangle'] for h in wide if h['command_index'] > 13}, {2, 3})
        hits = [h for c in self.cases for h in c['native_hits']]
        self.assertTrue(all(h['winner_horizon2_reachable_at_hit_body'] and h['winner_native_leaf_node'] == h['winner_triangle']+1
                            for h in hits))
        ties = [(i, h['command_index'], h['winner_plane_tag'], h['winner_plane_tag_tied_with_model_tag'])
                for i, c in enumerate(self.cases) for h in c['native_hits'] if h['winner_plane_tag'] != 0]
        self.assertEqual(ties, [(1, 27, 8, 0)])

    def test_seam_and_narrow_gap_never_lose_reach(self):
        for case in self.cases[:2]:
            t = case['track']['hypothetical_down']
            self.assertEqual((t['coverage'], t['regained'], case['live_horizon2_reach_regained']),
                             ([[F(0), F(1)]], [], 'NOT_ACTED_IN_THESE_ACTORS'))
            self.assertEqual({tr['kind'] for tr in t['transitions']}, {'track-bound'})
            self.assertEqual(case['track']['in_place']['coverage'], [])
            self.assertEqual((case['live_native_ramp_without_reach_commands'], case['live_reach_without_native_ramp_commands']), ([], [0, 1]))
            self.assertEqual([w['coverage'] for w in case['horizon_sensitivity']], [[[F(0), F(1)]]]*2)

    def test_wide_gap_loses_and_regains_reach_at_footprint_edges(self):
        case = self.cases[2]
        t = case['track']['hypothetical_down']
        self.assertEqual(t['coverage'], [[F(0), F(7, 24)], [F(37, 96), F(1)]])
        self.assertEqual(t['regained'], [dict(lost_at=F(7, 24), regained_at=F(37, 96), regained_measure=F(59, 96))])
        _, leave, enter, _ = t['transitions']
        for transition, kind, command, y, triangles in ((leave, 'exit', 9, 80, [0]), (enter, 'enter', 12, 98, [3])):
            (site,) = transition['sites']
            self.assertEqual((transition['kind'], transition['strictly_inside_command'], transition['reachable_only_at_full_horizon']),
                             (kind, True, False))
            self.assertEqual((site['command_index'], site['local_t'], site['command_parameter'], site['origin'][1],
                              site['bounding_triangles'], site['down_range_at_boundary'][1]), (command, F(1, 3), F(1, 3), y, triangles, 2))
        self.assertAlmostEqual(float(leave['sites'][0]['down_range_at_boundary'][0]), 1/32/.6, delta=2e-5)
        self.assertAlmostEqual(float(enter['sites'][0]['down_range_at_boundary'][0]), 1.33209, delta=5e-6)
        gap = next(g for g in t['gaps'] if g['length'] == F(3, 32))
        self.assertEqual((gap['start_included'], gap['end_included'], gap['nominal_seconds_not_exit_clock']), (False, False, F(9, 200)))
        self.assertEqual((case['live_partially_reached_commands'], case['live_reach_without_native_ramp_commands'],
                          case['live_native_ramp_without_reach_commands']), ([9, 12], [0, 1, 12, 13], []))
        self.assertEqual([c['command_index'] for c in case['commands'] if not c['hypothetical_down']['coverage']], [10, 11])
        self.assertEqual([w['coverage'] for w in case['horizon_sensitivity']], [t['coverage']]*2)
        landing = next(h for h in case['native_hits'] if h['command_index'] == 14)
        self.assertEqual((landing['winner_triangle'], landing['committed_fraction'] > .2), (3, True))

    def test_a_footprint_edge_holds_only_down_to_the_low_end_of_its_own_down_range(self):
        case = self.cases[2]
        owners = [s for c in case['commands'] for s in c['segments']]
        points = [reach.vector(multi.ORIGIN)]+[reach.vector(s['end']) for s in owners]
        shares = [s['track_share'] for s in owners]
        at = lambda horizon: multi.sensitivity(case['supplied_patch_set']['triangles'], points, shares, horizon)['coverage']
        # The regain is reachable from 1.332 down; a probe shorter than that turns it into a horizon cut.
        self.assertEqual((at(F(134, 100)), at(F(13, 10))[0]), (at(2), at(2)[0]))
        self.assertGreater(at(F(13, 10))[1][0], at(2)[1][0])
        self.assertEqual(at(F(52, 1000)), [])

    def test_removed_neighbour_is_counterfactual_only_and_changes_the_body_at_the_landing(self):
        gone, kept = self.cases[3], self.cases[2]
        self.assertEqual(self.result['removed_neighbour_first_differing_tick'], 14)
        self.assertEqual([t[10:16] for t in self.native[3]['ticks'][:14]], [t[10:16] for t in self.native[2]['ticks'][:14]])
        self.assertEqual((len(gone['supplied_patch_set']['triangles']), gone['authored_triangles_never_built']), (2, multi.authored(3)[2:]))
        live = gone['track']['hypothetical_down']
        self.assertEqual((live['coverage'], live['regained'], gone['live_horizon2_reach_regained']),
                         ([[F(0), F(7, 24)]], [], 'NOT_ACTED_IN_THESE_ACTORS'))
        against = gone['full_authored_set_counterfactual']
        self.assertEqual(against['hypothetical_down']['coverage'], kept['track']['hypothetical_down']['coverage'])
        self.assertEqual(against['in_place_edge'], dict(segments=40, domain_pairs=160, nonempty_segments=18, nonempty_domains=27))
        # The removed body falls through where the live one landed: one landing, one comparison.
        (site,) = against['in_place']['transitions'][0]['sites']
        landing = next(h for h in kept['native_hits'] if h['command_index'] == 14)
        self.assertEqual(site['command_index'], 14)
        # 3.2e-6 of a sweep that closes about half a unit along the normal: under 2e-6 units.
        self.assertAlmostEqual(float(site['command_parameter']), landing['truefraction'], delta=5e-6)
        self.assertEqual([c for c in self.cases if c['full_authored_set_counterfactual']], [gone])

    def test_vertical_lift_boundaries_are_horizon_cuts_and_move_with_the_horizon(self):
        case = self.cases[4]
        t = case['track']['hypothetical_down']
        self.assertEqual((len(t['coverage']), len(t['regained']), case['live_horizon2_reach_regained']), (2, 1, 'OBSERVED'))
        _, leave, enter, _ = t['transitions']
        for transition, kind, command, local in ((leave, 'exit', 1, .346941), (enter, 'enter', 12, .539974)):
            (site,) = transition['sites']
            self.assertEqual((transition['kind'], transition['reachable_only_at_full_horizon'], site['command_index'],
                              site['down_range_at_boundary']), (kind, True, command, [2, 2]))
            self.assertAlmostEqual(float(site['local_t']), local, delta=1e-6)
        four, eight = case['horizon_sensitivity']
        self.assertEqual((len(four['regained']), eight['coverage'], eight['regained']), (1, [[F(0), F(1)]], []))
        self.assertTrue(t['coverage'][0][1] < four['coverage'][0][1] < four['coverage'][1][0] < t['coverage'][1][0])
        self.assertEqual((case['live_partially_reached_commands'], case['live_reach_without_native_ramp_commands']), ([1, 12], [0, 1, 12, 13]))

    def test_live_in_place_is_empty_and_down2_agrees_at_every_tick_end(self):
        for case in self.cases:
            self.assertEqual((case['track']['in_place']['coverage'], case['in_place_edge']['nonempty_domains'], case['down2_disagreement_ticks']),
                             ([], 0, []))
            self.assertEqual(len(case['tick_ends']), 32)
        hits = [sum(e['native_down2_hit'] for e in c['tick_ends']) for c in self.cases]
        self.assertEqual(hits, [32, 32, 29, 9, 21])

    def test_supplied_patch_set_decides_the_verdict(self):
        case = self.cases[2]
        owners = [s for c in case['commands'] for s in c['segments']]
        points = [multi.ORIGIN]+[s['end'] for s in owners]
        supplied = case['supplied_patch_set']['triangles']
        _, alone = multi.track(supplied[:2], [0, 1], points, owners, case['commands'], 2, None)
        self.assertEqual((alone['coverage'], alone['regained']), ([[F(0), F(7, 24)]], []))
        # The neighbour moved 13 units along y: the regain follows it, half-way through the landing command.
        moved = [[[x, 127 if y == 114 else y, z] for x, y, z in t] for t in supplied[2:]]
        _, later = multi.track(supplied[:2]+moved, [0, 1, 2, 3], points, owners, case['commands'], 2, None)
        self.assertEqual(later['coverage'][0], [F(0), F(7, 24)])
        self.assertAlmostEqual(float(later['coverage'][1][0])*32, 14.5, delta=1e-5)
        # A removed triangle offered as live makes the native trace gate refuse a clear sweep it would have blocked.
        attempt = self.native[3]['path']['calls'][14]['attempts'][0]
        self.assertEqual(multi.check_trace(attempt[24:], attempt[5:8], attempt[14:17], self.native[3]['supplied']),
                         dict(triangles=0, candidates=0))
        with self.assertRaisesRegex(AssertionError, 'every plane-set candidate'):
            multi.check_trace(attempt[24:], attempt[5:8], attempt[14:17], multi.authored(3))

    def test_every_fixture_leaf_seed_and_tick_field_fault_refuses(self):
        # A quiet arm binds neither a tick's body nor a leaf's node index: those are mutated where something does
        # (capture here and in the leaf test), and the rest of them only five-arm parity can see.
        quiet = lambda w, column: 'TICK' not in w[0] and not ('LEAF' in w[0] and 'LEAVES' not in w[0] and column == 3)
        acted = self.refusals('nooracle', 0, 0, 'OFFRAMPTRIMULTI_', keep=quiet)
        acted += self.refusals('on', 1, 1, 'OFFRAMPTRIMULTI_TICK')
        self.assertEqual(acted, 5*5+18*15+16*15+5*3+5*13+160*28)
        print(f'{acted} ACTED multi-patch fixture/leaf/seed/tick field refusals, 0 failed')

    def test_every_native_query_field_fault_refuses(self):
        acted = self.refusals('control', 0, 1, 'OFFRAMPTRIMULTI_QUERY')
        self.assertEqual(acted, 480*19)
        print(f'{acted} ACTED multi-patch native query field refusals, 0 failed')

    def test_every_path_and_capture_field_fault_refuses_on_the_two_recontact_actors(self):
        acted = sum(self.refusals('on', 1, 1, prefix, cases=(2, 4)) for prefix in
                    ('OFFRAMPTRIPATH_', 'OFFRAMPBUF_TICK', 'OFFRAMPBUF_CONTACT', 'OFFRAMPORIGIN_CONTACT', 'OFFRAMPTRICOPY_CONTACT'))
        fields = lambda case: (6+32*28+self.native[case]['path']['attempt_count']*(37+10) +
                               self.native[case]['path']['validation_count']*18+32*11+1+32*16 +
                               self.native[case]['path']['hit_count']*(24+10+18))
        self.assertEqual(acted, fields(2)+fields(4))
        print(f'{acted} ACTED path/buffer/origin/copy field refusals on the wide-gap and vertical-lift actors, 0 failed')

    def test_each_row_missing_duplicated_or_swapped_with_its_neighbour_refuses(self):
        acted = 0
        with patch.object(multi, 'candidates', side_effect=self.cached):
            for case in (2, 4):
                block = self.blocks['on'][case]
                lines = block.splitlines()
                for prefix in (multi.OWN, 'OFFRAMPTRIPATH_', 'OFFRAMPBUF_'):
                    owned = [i for i, l in enumerate(lines) if prefix in l]
                    for at, i in enumerate(owned):
                        variants = [lines[:i]+lines[i+1:], lines[:i]+[lines[i]]+lines[i:]]
                        if at+1 < len(owned):
                            j = owned[at+1]
                            variants.append(lines[:i]+[lines[j]]+lines[i+1:j]+[lines[i]]+lines[j+1:])
                        for bad in variants:
                            with self.subTest(case=case, row=lines[i][lines[i].find(prefix):][:40]), self.assertRaises(AssertionError):
                                multi.grade_case('\n'.join(bad), case, 1, 1)
                            acted += 1
        rows = lambda case: sum(3*len([l for l in self.blocks['on'][case].splitlines() if p in l])-1
                                for p in (multi.OWN, 'OFFRAMPTRIPATH_', 'OFFRAMPBUF_'))
        self.assertEqual(acted, rows(2)+rows(4))
        print(f'{acted} ACTED row deletion/duplication/adjacent-swap refusals, 0 failed')

    def test_attempts_that_belong_to_no_command_and_truncated_envelopes_refuse(self):
        block = self.blocks['on'][2]
        begin, attempt, outcome = (row(block, s) for s in ('OFFRAMPTRIPATH_BEGIN ', 'OFFRAMPTRIPATH_ATTEMPT 57 ', 'OFFRAMPTRIPATH_OUTCOME 57 '))
        self.assertEqual(begin.split()[4], '58')
        extra = []
        for ordinal, call in ((58, 32), (59, -7)):
            a, o = attempt.split(), outcome.split()
            a[1:3], o[1] = [str(ordinal), str(call)], str(ordinal)
            extra += [' '.join(a), ' '.join(o)]
        first_return = row(block, 'OFFRAMPTRIPATH_RETURN 0 ')
        orphaned = block.replace(begin, begin.replace(' 58 0 ', ' 60 0 ', 1), 1).replace(first_return, '\n'.join(extra+[first_return]), 1)
        with self.assertRaisesRegex(AssertionError, 'belongs to no command'): multi.grade_case(orphaned, 2, 1, 1)
        lines = block.splitlines()
        cut = lambda keep: '\n'.join(l for l in lines if keep(l))
        for name, bad in (('no returns or end', cut(lambda l: 'OFFRAMPTRIPATH_RETURN' not in l and 'OFFRAMPTRIPATH_END' not in l)),
                          ('calls only', cut(lambda l: 'OFFRAMPTRIPATH_' not in l or 'OFFRAMPTRIPATH_BEGIN' in l or 'OFFRAMPTRIPATH_CALL' in l)),
                          ('begin only', cut(lambda l: 'OFFRAMPTRIPATH_' not in l or 'OFFRAMPTRIPATH_BEGIN' in l)),
                          ('nothing', cut(lambda l: 'OFFRAMPTRIPATH_' not in l))):
            with self.subTest(truncated=name), self.assertRaises(AssertionError): multi.grade_case(bad, 2, 1, 1)

    def test_rows_no_reader_owns_refuse_in_a_capture_case_too(self):
        block = self.blocks['on'][0]
        seed = row(block, 'OFFRAMPTRIMULTI_SEED ')
        for stray in ('OFFRAMPBEVPM_TICK 0 0', 'OFFRAMPMOTION_CASE 0 x', 'OFFRAMPZZZ_UNSUPPORTED recovery portal', 'OFFRAMPTRIMULTIX_ROW 1'):
            with self.subTest(stray=stray), self.assertRaisesRegex(AssertionError, 'rows no reader owns'):
                multi.grade_case(block.replace(seed, seed+'\n'+stray, 1), 0, 1, 1)

    def test_consistent_forgeries_refuse_at_the_one_gate_that_can_see_them(self):
        block = self.blocks['on'][0]
        self.assertEqual((self.native[0]['path']['calls'][31]['attempts'][1][0], row(block, 'OFFRAMPTRIPATH_ATTEMPT 61 ').split()[25]), (61, '1'))
        queries = [f'OFFRAMPTRIMULTI_QUERY 0 31 {name} ' for name in pm.QUERIES]
        # y runs along the plane, so a body or a velocity moved in y keeps every distance to it.
        body = {'OFFRAMPTRIPATH_ATTEMPT 61 ': {36: 1}, 'OFFRAMPTRIPATH_OUTCOME 61 ': {5: 1}, 'OFFRAMPTRIPATH_RETURN 31 ': {6: 1},
                'OFFRAMPTRIMULTI_TICK 0 31 ': {12: 1}, 'OFFRAMPBUF_TICK 31 ': {9: 1}, **{q: {5: 1, 8: 1} for q in queries}}
        with self.assertRaisesRegex(AssertionError, 'trace endpoint/fraction differs'):
            multi.grade_case(forged(block, body), 0, 1, 1)
        speed = {'OFFRAMPTRIPATH_OUTCOME 60 ': {8: 1}, 'OFFRAMPTRIPATH_ATTEMPT 61 ': {13: 1, 16: .015, 36: .015},
                 'OFFRAMPTRIPATH_OUTCOME 61 ': {5: .015, 8: 1}, 'OFFRAMPTRIPATH_RETURN 31 ': {6: .015, 9: 1},
                 'OFFRAMPTRIMULTI_TICK 0 31 ': {12: .015, 15: 1}, 'OFFRAMPBUF_TICK 31 ': {9: .015, 12: 1},
                 **{q: {5: .015, 8: .015} for q in queries}}
        with self.assertRaisesRegex(AssertionError, 'single-plane clip velocity differs'):
            multi.grade_case(forged(block, speed), 0, 1, 1)

    def test_native_leaf_must_be_the_dumped_node_and_the_winner_must_have_bevels_on(self):
        block = self.blocks['on'][0]
        origin, shape = row(block, 'OFFRAMPORIGIN_CONTACT 0 '), row(block, 'OFFRAMPGEOM_CONTACT 0 ')
        self.assertEqual((origin.split()[5:7], shape.split()[4:6]), (['1', '1'], ['1', '1']))
        # The shape layer already binds the origin's leaf to its own row, so the two move together here.
        with self.assertRaisesRegex(AssertionError, 'shape not bound to winning origin'):
            multi.grade_case(block.replace(origin, origin.replace(' 2 1 1 0 ', ' 2 3 3 0 ', 1), 1), 0, 1, 1)
        relabelled, renamed = block, 0
        for line in block.splitlines():
            for prefix, at in (('OFFRAMPORIGIN_CONTACT', 5), ('OFFRAMPGEOM_CONTACT', 4)):
                if prefix in line:
                    words = line[line.find(prefix):].split()
                    if words[at:at+2] == ['1', '1']:
                        words[at:at+2] = ['9', '9']
                        relabelled = relabelled.replace(line[line.find(prefix):], ' '.join(words), 1)
                        renamed += 1
        self.assertEqual(renamed, 16)
        # Every contact of triangle 0 renamed alike: consistent, and still not the node the walker dumped.
        with self.assertRaisesRegex(AssertionError, 'not the dumped node'): multi.grade_case(relabelled, 0, 1, 1)
        # And from the other side: the dumped node of any triangle that ever wins cannot move either.
        acted = 0
        for case, native in enumerate(self.native):
            for leaf in native['native_leaves']:
                if multi.INDEXES.index(leaf['indexes']) in {h['winner_triangle'] for h in self.cases[case]['native_hits']}:
                    line = row(self.blocks['on'][case], f"OFFRAMPTRIMULTI_LEAF {case} {native['native_leaves'].index(leaf)} ")
                    with self.subTest(case=case, node=leaf['node']), self.assertRaises(AssertionError):
                        multi.grade_case(self.blocks['on'][case].replace(line, bumped(line, 3), 1), case, 1, 1)
                    acted += 1
        self.assertEqual(acted, 11)
        copy = row(block, 'OFFRAMPTRICOPY_CONTACT 0 ')
        self.assertEqual(copy.split()[5], '1')
        with self.assertRaisesRegex(AssertionError, 'bevels on'):
            multi.grade_case(block.replace(copy, bumped(copy, 5, -1), 1), 0, 1, 1)

    def test_quiet_capture_rows_outside_rows_and_arm_faults_refuse(self):
        on, quiet = self.blocks['on'][0], self.blocks['nooracle'][0]
        for prefix in ('OFFRAMPGEOM_', 'OFFRAMPBUF_', 'OFFRAMPTRIPATH_', 'OFFRAMPHULL_'):
            line = row(on, prefix)
            with self.subTest(prefix=prefix), self.assertRaisesRegex(AssertionError, 'quiet multi-patch arm has capture rows'):
                multi.grade_case(quiet+'\n'+line, 0, 0, 0)
        stray = row(on, 'OFFRAMPTRIPATH_CALL 0 ')
        envelope = multi.split(self.texts[3])[1]
        with self.assertRaisesRegex(AssertionError, 'capture outside cases'):
            multi.grade(envelope.replace('OFFRAMPTRIMULTI_END 5', stray+'\nOFFRAMPTRIMULTI_END 5'))
        for arm, change in ((3, lambda t: t+'\nOFFRAMPTRIMULTI_LEAVES 0 4 0'), (2, lambda t: t+'\n'+stray)):
            texts = list(self.texts); texts[arm] = change(texts[arm])
            with self.subTest(arm=arm), self.assertRaises(AssertionError): multi.compare(*texts)

    def test_faults_only_five_arm_parity_can_see_refuse_there(self):
        # Each fault passes its own arm's gates: a quiet body, a hit fraction and a truefraction inside tolerance.
        tick = row(self.texts[0], 'OFFRAMPTRIMULTI_TICK 2 9 ')
        down = row(self.texts[2], 'OFFRAMPTRIMULTI_QUERY 0 5 down2 ')
        hit = next(l[l.find('OFFRAMPTRIPATH_ATTEMPT'):] for l in self.blocks['repeat'][2].splitlines()
                   if 'OFFRAMPTRIPATH_ATTEMPT' in l and 0 < float(l[l.find('OFFRAMPTRIPATH_ATTEMPT'):].split()[25]) < 1)
        self.assertLess(float(down.split()[10]), 1)
        leaf = row(self.texts[0], 'OFFRAMPTRIMULTI_LEAF 4 1 ')  # a triangle that never wins: nothing else binds its node
        for arm, old, new, message in ((0, tick, bumped(tick, 11), 'body/leaf parity'), (0, leaf, bumped(leaf, 3), 'body/leaf parity'),
                                       (2, down, bumped(down, 10, 1e-9), 'query parity'),
                                       (4, hit, bumped(hit, 26, 1e-9), 'repeat capture differs')):
            texts = list(self.texts); texts[arm] = texts[arm].replace(old, new, 1)
            self.assertNotEqual(texts[arm], self.texts[arm])
            multi.grade(multi.split(texts[arm])[1])
            with self.subTest(arm=arm), self.assertRaisesRegex(AssertionError, message): multi.compare(*texts)
        texts = list(self.texts); texts[2] = texts[3]
        with self.assertRaisesRegex(AssertionError, 'arm modes differ'): multi.compare(*texts)

    def test_envelope_header_and_footer_faults_refuse(self):
        envelope = multi.split(self.texts[0])[1]
        multi.grade(envelope)
        acted = 0
        for start in ('OFFRAMPTRIMULTI_BEGIN ', 'OFFRAMPTRIMULTI_SOURCE ', 'OFFRAMPTRIMULTI_CASE_END 3 ', 'OFFRAMPTRIMULTI_END '):
            line = row(envelope, start)
            for column in range(1, len(line.split())):
                with self.subTest(row=start, column=column), self.assertRaises(AssertionError):
                    multi.grade(envelope.replace(line, bumped(line, column), 1))
                acted += 1
        self.assertEqual(acted, 5+3+2+1)

    def test_share_rule_horizon_nesting_containment_and_merged_horizons_refuse(self):
        equal = lambda rows, duration: [F(1, len(rows))]*len(rows)
        with patch.object(walk, 'shares', side_effect=equal), self.assertRaisesRegex(AssertionError, 'velocity x nominal share'):
            multi.assess_actor(4, self.native[4])
        shrunk = lambda triangles, points, shares, horizon: dict(horizon=horizon, coverage=[], regained=[], basis='mutant')
        with patch.object(multi, 'sensitivity', side_effect=shrunk), self.assertRaisesRegex(AssertionError, 'does not nest'):
            multi.assess_actor(4, self.native[4])
        real = multi.track
        def blind(triangles, names, points, owners, commands, horizon, key):
            result, summary = real(triangles, names, points, owners, commands, horizon, key)
            return result, summary if key else dict(summary, coverage=[])
        with patch.object(multi, 'track', side_effect=blind), self.assertRaisesRegex(AssertionError, 'does not contain live reach'):
            multi.assess_actor(3, self.native[3])
        with patch.object(multi, 'HORIZONS', (('in_place', 2), ('hypothetical_down', 2))), \
                self.assertRaisesRegex(AssertionError, 'zero-distance edge'):
            multi.assess_actor(3, self.native[3])

    def test_this_capture_reproduces_its_own_predecessor_report_and_a_changed_one_refuses(self):
        prior = self.result['prior_committed_reach_report']
        retained = json.loads(json.dumps(reach.encoded(prior), allow_nan=False))
        self.assertEqual(multi.same_prior(prior, dict(retained, arms='theirs')), 'EQUAL_TO_RETAINED_REPORT')
        with self.assertRaisesRegex(AssertionError, 'differs from the retained one'):
            multi.same_prior(prior, dict(retained, committed_segment_count=retained['committed_segment_count']+1))

    def test_the_old_quiet_check_now_sees_the_shape_layer(self):
        text = multi.split(self.texts[0])[0]
        rest, block = pm.split(text)
        pm.grade(block)
        end = 'OFFRAMPBEVPM_CASE_END 0 32'
        with self.assertRaisesRegex(AssertionError, 'quiet bevel PM arm has capture rows'):
            pm.grade(block.replace(end, 'OFFRAMPGEOM_BEGIN 2 16 64\n'+end, 1))

    def test_manifest_source_and_mode_faults_refuse(self):
        arms = json.loads(ARMS.read_text())
        for field, value in (('trimulti_source_sha256', '0'*64), ('tripath_source_sha256', '0'*64), ('capture', True), ('oracle', 0)):
            bad = deepcopy(arms); bad['on'][field] = value
            with self.subTest(field=field), patch.object(Path, 'read_text', return_value=json.dumps(bad)), \
                    patch.object(multi.path.pm, 'load_arms', return_value=(self.texts, [])), self.assertRaises(AssertionError):
                multi.load_arms(ARMS)


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__); ap.add_argument('--native-arms', type=Path)
    a, rest = ap.parse_known_args(); ARMS = a.native_arms
    Native.__unittest_skip__ = not bool(ARMS)
    unittest.main(argv=[__file__, *rest])
