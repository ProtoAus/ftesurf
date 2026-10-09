#!/usr/bin/env python3
"""Joint convex/schema units and ACTED retained native-trajectory controls."""
import argparse
import hashlib
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from offramp_motion import EMBEDDED_MODEL, ENTITY_MODEL, INSTANCE, LABELS, MAX_STEPS, PARAMS, assess_airposture, assess_cached_capture, authored, compare, grade, joint_overlap, oracle_validate, parse, shape_category, step_count
from offramp_motion_smoke import TARGET, instrument, prepare
import test_offramp_hull as hull_tests

BASE_SNAPSHOT = hull_tests.snapshot


def change(text, tag, index, value, pred=lambda r: True, namespace='OFFRAMPMOTION'):
    lines = text.splitlines(); token = f'{namespace}_{tag} '
    for i, line in enumerate(lines):
        if token not in line: continue
        prefix, tail = line.split(token, 1); row = tail.split()
        if not pred(row): continue
        row[index] = str(value); lines[i] = prefix+token+' '.join(row)
        return '\n'.join(lines)+'\n'
    raise AssertionError('Motion counterfactual did not ACT')


def change_all(text, tag, updates, pred):
    lines = text.splitlines(); token = f'OFFRAMPMOTION_{tag} '; count = 0
    for i, line in enumerate(lines):
        if token not in line: continue
        prefix, tail = line.split(token, 1); row = tail.split()
        if not pred(row): continue
        for index, value in updates.items(): row[index] = str(value)
        lines[i] = prefix+token+' '.join(row); count += 1
    assert count, 'Bulk counterfactual did not ACT'
    return '\n'.join(lines)+'\n'


def change_case(text, case, tag, index, value, pred=lambda r: True, namespace='OFFRAMPMOTION'):
    start = text.index(f'OFFRAMPMOTION_CASE {case} ')
    end = text.index(f'OFFRAMPMOTION_CASE_END {case} ', start)
    return text[:start]+change(text[start:end], tag, index, value, pred, namespace)+text[end:]


def entity_query(case=10):
    brushes, seed = authored(case)
    tick = [case, 0, 15, 0, 0, 0, 1, .015, 1, 0]+seed[:6]+seed[6:]+[0]*6
    row = [str(case), '0', 'down2', '-1']+list(map(str, seed[:3]+[seed[0], seed[1], seed[2]-2]+[.015625, 0, 0, 1, .8, 0, .6, 0, 1]))
    return brushes, tick, row


def capsule_query():
    brushes, seed = authored(8)
    tick = [8, 0, 15, 0, 0, 0, 1, .015, 1, 0]+seed[:6]+seed[6:]+[0, 0, 0, 1, 0, 0]
    row = ['8', '0', 'stationary', '-1']+list(map(str, seed[:3]*2+[1, 0, 0, 0, 0, 0, 0, 0, 0]))
    return brushes, tick, row


def transformed_query():
    brushes, seed = authored(9)
    tick = [9, 0, 15, 0, 0, 0, 1, .015, 1, 0]+seed[:6]+seed[6:]+[0]*6
    row = ['9', '0', 'stationary', '-1']+list(map(str, seed[:3]*2+[1, 0, 0, 0, 0, 0, 0, 0, 0]))
    return brushes, tick, row


def airposture_cases():
    """Synthetic gate units only; ACTED controls below use actual native logs."""
    cases = []
    for case in (16, 17):
        brushes, seed = authored(case); ticks, queries = [], []
        for i in range(64):
            duck, ground = case == 16 and 3 <= i <= 10, i >= 37
            t = [case, i, 15, 0, 0, 8 if duck else 0, 1, .015, 0, int(ground),
                 -100+i*.9, 0, (0 if ground else 128-.09*(i+1)**2)+(8.5 if duck else 0),
                 60, 0, 0 if ground else -12*(i+1), -16, -16, 0, 16, 16,
                 45 if duck else 62, int(duck), 0, 1000-15*(i-3) if duck else 0, 0, 0, 8 if duck else 0]
            q = [[0]*19 for _ in range(5)]
            for row, fraction in zip(q, (1, .5 if ground else 1, .5, .5, 1)): row[10] = fraction
            ticks.append(t); queries.append(q)
        cases.append(dict(label=LABELS[case], brushes=brushes, seed=seed, ticks=ticks, oracles=queries))
    return cases


def flat_query():
    brushes, _ = authored(4)
    tick = [4, 0, 15, 0, 0, 0, 1, .015, 0, 1, 0, 0, .05, 0, 0, 0, -16, -16, 0, 16, 16, 62, 0, 0, 0, 0, 0, 0]
    row = '4 0 down2 -1 0 0 .05 0 0 -1.95 .009375 0 0 0 0 0 1 0 1'.split()
    return brushes, tick, row


class Tests(unittest.TestCase):
    def test_joint_full_box_positive_negative_and_touch(self):
        box = [[1, 0, 0, 1], [-1, 0, 0, 1], [0, 1, 0, 1], [0, -1, 0, 1], [0, 0, 1, 1], [0, 0, -1, 1]]
        self.assertTrue(joint_overlap(box, [0, 0, 0], [.5, .5, .5]))
        self.assertTrue(joint_overlap(box, [1, 1, 1], [2, 2, 2]))
        self.assertFalse(joint_overlap(box, [1.1, 1.1, 1.1], [2, 2, 2]))

    def test_independent_expanded_planes_are_not_joint_collision(self):
        # VALID wedge outside a unit box. Both oblique inequalities individually
        # intersect the box, but no SAME point satisfies both within x<=1.
        planes = [[1, 0, 0, 3], [-1, 0, 0, 3], [0, 1, 0, 3], [0, -1, 0, 3],
                  [0, 0, 1, 3], [0, 0, -1, 3], [-1, -1, 0, -1.5], [-1, 1, 0, -.75]]
        lo, hi = [0, 0, 0], [1, 1, 1]
        self.assertTrue(all(sum(n*(h if n < 0 else l) for n, l, h in zip(p[:3], lo, hi)) <= p[3] for p in planes))
        self.assertFalse(joint_overlap(planes, lo, hi))
        self.assertTrue(joint_overlap(planes, [1.2, .4, 0], [2, .6, 1]))

    def test_real_query_coordinates_and_full_hull_binding(self):
        brushes, tick, row = flat_query()
        self.assertEqual(oracle_validate(row, tick, brushes)[10], .009375)
        moved = row[:]; moved[4] = '1'
        with self.assertRaisesRegex(AssertionError, 'endpoints'):
            oracle_validate(moved, tick, brushes)
        # No guessed default hull: raising the actual bottom removes collision.
        tick[18] = 5
        with self.assertRaisesRegex(AssertionError, 'JOINT'):
            oracle_validate(row, tick, brushes)

    def test_query_faults(self):
        brushes, tick, row = flat_query()
        for index, value in ((10, -1), (10, 1), (11, 1), (12, 1), (13, 2), (14, 1), (18, 2), (4, 'nan')):
            bad = row[:]; bad[index] = str(value)
            with self.subTest(index=index), self.assertRaises(AssertionError):
                oracle_validate(bad, tick, brushes)

    def test_protocol_unknown_width_and_failed_actor(self):
        for text in ('OFFRAMPMOTION_WHAT 1', 'OFFRAMPMOTION_TICK 1', 'OFFRAMPMOTION_COMPLETE 1'):
            with self.assertRaises(AssertionError): parse(text)
        for text in ('', 'OFFRAMPMOTION_BEGIN 1 0 1 6 32', 'all checks passed\nOFFRAMPMOTION_BEGIN 1 0 1 6 32'):
            with self.assertRaises(AssertionError): grade(text)

    def test_standing_counterfactual_is_not_actual_crouch_collision(self):
        brushes, _ = authored(7)
        tick = [0]*28
        tick[10:13], tick[16:22] = [0, 0, .05], [-16, -16, 0, 16, 16, 45]
        row = ['7', '0', 'standing', '-1']+list(map(str, [0, 0, .05, 0, 0, .05, 1, 1, 1, 0, 0, 0, 0, 0, 1]))
        oracle_validate(row, tick, brushes)
        actual = row[:]; actual[2] = 'stationary'
        with self.assertRaisesRegex(AssertionError, 'embedded'):
            oracle_validate(actual, tick, brushes)
        miss = row[:]; miss[11:13], miss[18] = ['0', '0'], '0'
        actual = miss[:]; actual[2] = 'stationary'
        oracle_validate(actual, tick, brushes)
        with self.assertRaisesRegex(AssertionError, 'JOINT'):
            oracle_validate(miss, tick, brushes)
        tick[10] = 48.05
        miss[4], miss[7] = '48.05', '48.05'
        oracle_validate(miss, tick, brushes)

    def test_capsule_explicit_abstention_never_uses_joint_aabb(self):
        brushes, tick, row = capsule_query()
        with patch('offramp_motion.joint_overlap', side_effect=AssertionError('AABB oracle ACTED')):
            oracle_validate(row, tick, brushes)
            down = row[:]; down[2], down[9] = 'down2', str(tick[12]-2)
            down[10], down[14:19] = '.015625', ['.8', '0', '.6', '0', '1']
            oracle_validate(down, tick, brushes)
            box = row[:]; box[2], box[11:13], box[18] = 'box', ['1', '1'], '1'
            with self.assertRaisesRegex(AssertionError, 'AABB oracle ACTED'):
                oracle_validate(box, tick, brushes)
        oracle_validate(box, tick, brushes)
        tick[25] = 0
        with self.assertRaisesRegex(AssertionError, 'JOINT'):
            oracle_validate(row, tick, brushes)

    def test_capsule_query_binding_and_actual_body_solids_refuse(self):
        brushes, tick, row = capsule_query()
        for index, value in ((0, '7'), (3, '0'), (4, '999'), (11, '1'), (18, '1')):
            bad = row[:]; bad[index] = value
            with self.subTest(index=index), self.assertRaises(AssertionError):
                oracle_validate(bad, tick, brushes)

    def test_transformed_actual_abstains_identity_acts_local_joint_oracle(self):
        brushes, tick, row = transformed_query()
        with patch('offramp_motion.joint_overlap', side_effect=AssertionError('AABB oracle ACTED')):
            oracle_validate(row, tick, brushes)
            down = row[:]; down[2], down[9] = 'down2', str(tick[12]-2)
            down[10], down[14:19] = '.015625', [str(.8*2**-.5), str(.8*2**-.5), '.6', '0', '1']
            oracle_validate(down, tick, brushes)
            identity = row[:]; identity[2], identity[9] = 'identity', str(tick[12]-2)
            with self.assertRaisesRegex(AssertionError, 'AABB oracle ACTED'):
                oracle_validate(identity, tick, brushes)
        oracle_validate(identity, tick, brushes)
        bad = down[:]; bad[2] = 'identity'
        with self.assertRaisesRegex(AssertionError, 'JOINT'):
            oracle_validate(bad, tick, brushes)

    def test_identity_solid_is_only_a_counterfactual_without_winning_plane(self):
        brushes, tick, row = transformed_query()
        tick[10:13] = [1000, -300, 90]
        row[2], row[4:10], row[11:13] = 'identity', ['1000', '-300', '90', '1000', '-300', '88'], ['1', '1']
        oracle_validate(row, tick, brushes)
        for index, value in ((2, 'down2'), (10, '.5'), (12, '0'), (14, '.8'), (18, '1')):
            bad = row[:]; bad[index] = value
            with self.subTest(index=index), self.assertRaises(AssertionError):
                oracle_validate(bad, tick, brushes)
        # A quiet false-negative cannot erase the identity's true box overlap.
        bad = row[:]; bad[11:13] = ['0', '0']
        with self.assertRaisesRegex(AssertionError, 'JOINT'):
            oracle_validate(bad, tick, brushes)

    def test_transformed_native_plane_is_not_world_affine_plane(self):
        brushes, tick, row = transformed_query()
        down = row[:]; down[2], down[9] = 'down2', str(tick[12]-2)
        down[10], down[14:19] = '.015625', [str(.8*2**-.5), str(.8*2**-.5), '.6', '0', '1']
        oracle_validate(down, tick, brushes)
        for index, value in ((0, '8'), (3, '0'), (4, '999'), (11, '1'), (14, '.8'), (17, '600'), (18, '0')):
            bad = down[:]; bad[index] = value
            with self.subTest(index=index), self.assertRaises(AssertionError):
                oracle_validate(bad, tick, brushes)
        actual = row[:]; actual[2] = 'box'
        with self.assertRaises(AssertionError): oracle_validate(actual, tick, brushes)
        self.assertEqual(INSTANCE, [9, 0, 1000, -300, 100, 0, 45, 0, 1, 0])

    def test_entity_native_query_joint_binding_and_world_removal(self):
        brushes, tick, row = entity_query()
        oracle_validate(row, tick, brushes)
        world = row[:]; world[2:4], world[10:19] = ['worldonly', '0'], ['1', '0', '0', '-1', '0', '0', '0', '0', '0']
        oracle_validate(world, tick, brushes)
        with patch('offramp_motion.joint_overlap', side_effect=AssertionError('JOINT ACTED')):
            with self.assertRaisesRegex(AssertionError, 'JOINT ACTED'): oracle_validate(row, tick, brushes)
            with self.assertRaisesRegex(AssertionError, 'JOINT ACTED'): oracle_validate(world, tick, brushes)
        fake = world[:]; fake[2:4] = ['down2', '-1']
        with self.assertRaisesRegex(AssertionError, 'JOINT'): oracle_validate(fake, tick, brushes)
        fake = row[:]; fake[2:4] = ['worldonly', '0']
        with self.assertRaisesRegex(AssertionError, 'JOINT'): oracle_validate(fake, tick, brushes)
        # Same body pose with the entity removed: no actual contact, even though
        # the inactive authored entity overlaps the swept box.
        _, removed_tick, _ = entity_query(11)
        fake = world[:]; fake[0], fake[2:4] = '11', ['down2', '-1']
        oracle_validate(fake, removed_tick, brushes)
        fake = row[:]; fake[0] = '11'
        with self.assertRaisesRegex(AssertionError, 'JOINT'): oracle_validate(fake, removed_tick, brushes)

    def test_entity_query_schema_winner_and_stale_miss_refuse(self):
        brushes, tick, row = entity_query()
        for index, value in ((0, '9'), (3, '0'), (4, '999'), (11, '1'), (13, '0'), (14, '0'), (18, '0')):
            bad = row[:]; bad[index] = value
            with self.subTest(index=index), self.assertRaises(AssertionError): oracle_validate(bad, tick, brushes)
        miss = row[:]; miss[2:4], miss[10:19] = ['worldonly', '0'], ['1', '0', '0', '-1', '0', '0', '0', '0', '0']
        for index, value in ((13, '1'), (14, '.8'), (18, '1')):
            bad = miss[:]; bad[index] = value
            with self.subTest(index=index), self.assertRaises(AssertionError): oracle_validate(bad, tick, brushes)

    def test_identity_embedded_query_active_child_and_removal(self):
        brushes, tick, row = entity_query(12); row[13] = '0'
        oracle_validate(row, tick, brushes)
        removed = row[:]; removed[2:4], removed[10:19] = ['unembedded', '0'], ['1', '0', '0', '-1', '0', '0', '0', '0', '0']
        oracle_validate(removed, tick, brushes)
        with patch('offramp_motion.joint_overlap', side_effect=AssertionError('JOINT ACTED')):
            with self.assertRaisesRegex(AssertionError, 'JOINT ACTED'): oracle_validate(row, tick, brushes)
            with self.assertRaisesRegex(AssertionError, 'JOINT ACTED'): oracle_validate(removed, tick, brushes)
        fake = removed[:]; fake[2:4] = ['down2', '-1']
        with self.assertRaisesRegex(AssertionError, 'JOINT'): oracle_validate(fake, tick, brushes)
        fake = row[:]; fake[2:4] = ['unembedded', '0']
        with self.assertRaisesRegex(AssertionError, 'JOINT'): oracle_validate(fake, tick, brushes)
        _, removed_tick, _ = entity_query(13)
        fake = removed[:]; fake[0], fake[2:4] = '13', ['down2', '-1']
        oracle_validate(fake, removed_tick, brushes)
        fake = row[:]; fake[0] = '13'
        with self.assertRaisesRegex(AssertionError, 'JOINT'): oracle_validate(fake, removed_tick, brushes)

    def test_embedded_query_wrong_family_parent_winner_pose_or_embed_refuses(self):
        brushes, tick, row = entity_query(12); row[13] = '0'
        for index, value in ((0, '11'), (2, 'worldonly'), (3, '0'), (4, '999'), (11, '1'), (12, '1'), (13, '1'), (14, '0'), (18, '0')):
            bad = row[:]; bad[index] = value
            with self.subTest(index=index), self.assertRaises(AssertionError): oracle_validate(bad, tick, brushes)
        miss = row[:]; miss[2:4], miss[10:19] = ['unembedded', '0'], ['1', '0', '0', '-1', '0', '0', '0', '0', '0']
        for index, value in ((13, '0'), (14, '.8'), (18, '1')):
            bad = miss[:]; bad[index] = value
            with self.subTest(index=index), self.assertRaises(AssertionError): oracle_validate(bad, tick, brushes)

    def test_triangle_native_query_never_substitutes_joint_aabb(self):
        brushes, tick, row = entity_query(14); row[13] = '0'
        with patch('offramp_motion.joint_overlap', side_effect=AssertionError('NO_TRIANGLE_ORACLE')):
            self.assertEqual(oracle_validate(row, tick, brushes)[10], .015625)
        row[2:4], row[10:19] = ['untriangled', '0'], ['1', '0', '0', '-1', '0', '0', '0', '0', '0']
        self.assertEqual(oracle_validate(row, tick, brushes)[10:14], [1, 0, 0, -1])
        with patch('offramp_motion.joint_overlap', side_effect=AssertionError('REMOTE_QUERY_ACTED')):
            with self.assertRaisesRegex(AssertionError, 'REMOTE_QUERY_ACTED'): oracle_validate(row, tick, brushes)

    def test_triangle_query_family_winner_hull_plane_and_body_solids_refuse(self):
        brushes, tick, row = entity_query(14); row[13] = '0'
        for index, value in ((0, '12'), (2, 'unembedded'), (3, '0'), (4, '999'), (11, '1'), (12, '1'), (13, '1'), (14, '0'), (18, '0')):
            bad = row[:]; bad[index] = value
            with self.subTest(index=index), self.assertRaises(AssertionError): oracle_validate(bad, tick, brushes)
        row[2] = 'stationary'; row[7:10] = row[4:7]
        with self.assertRaisesRegex(AssertionError, 'ended embedded'): oracle_validate(row, tick, brushes)

    def test_removed_triangle_queries_act_joint_remote_only(self):
        brushes, tick, row = entity_query(15)
        row[10:19] = ['1', '0', '0', '-1', '0', '0', '0', '0', '0']
        self.assertEqual(oracle_validate(row, tick, brushes)[10:14], [1, 0, 0, -1])
        for index, value in ((13, '0'), (14, '.8'), (18, '1')):
            bad = row[:]; bad[index] = value
            with self.subTest(index=index), self.assertRaises(AssertionError): oracle_validate(bad, tick, brushes)
        with patch('offramp_motion.joint_overlap', side_effect=AssertionError('REMOVED_ACTED')):
            with self.assertRaisesRegex(AssertionError, 'REMOVED_ACTED'): oracle_validate(row, tick, brushes)

    def test_airborne_instant_duck_unduck_control_and_landing(self):
        cases = airposture_cases(); assess_airposture(*cases)
        self.assertEqual(cases[0]['airborne_duck_ticks'], list(range(3, 11)))
        self.assertEqual(cases[0]['native_landing_tick'], 37)
        for case, tick, index, value in ((0, 3, 12, 120), (0, 3, 21, 62), (0, 3, 22, 0),
                (0, 3, 23, 1), (0, 3, 24, 985), (0, 11, 24, 1000), (0, 3, 27, 0),
                (1, 3, 22, 1), (0, 37, 9, 0), (1, 0, 15, 0), (1, 63, 12, 5)):
            bad = airposture_cases(); bad[case]['ticks'][tick][index] = value
            with self.subTest(case=case, tick=tick, index=index), self.assertRaises(AssertionError):
                assess_airposture(*bad)

    def test_airborne_full_current_hull_native_queries_use_joint_floor_oracle(self):
        brushes, _ = authored(16)
        tick = airposture_cases()[0]['ticks'][3]
        row = ['16', '3', 'stationary', '-1']+list(map(str, tick[10:13]*2+[1, 0, 0, 0, 0, 0, 0, 0, 0]))
        oracle_validate(row, tick, brushes)
        with patch('offramp_motion.joint_overlap', side_effect=AssertionError('AIR_AABB_ACTED')):
            with self.assertRaisesRegex(AssertionError, 'AIR_AABB_ACTED'): oracle_validate(row, tick, brushes)
        for index, value in ((2, 'untriangled'), (3, '1'), (4, '999'), (11, '1'), (13, '-1'), (14, '1')):
            bad = row[:]; bad[index] = value
            with self.subTest(index=index), self.assertRaises(AssertionError): oracle_validate(bad, tick, brushes)

    def test_cached_firsttrace_requires_actual_prior_ground_and_sweep(self):
        ticks = [[0]*28 for _ in range(64)]
        ticks[21][8:10], ticks[21][10:13] = [0, 1], [-17.5, 0, .03125]
        ticks[21][13] = 250
        good = dict(originroute=1, tick=22, bump=0, brush=1, fraction=.4,
                    native_plane=[-.8, 0, .6, 0], sweep_start=[-17.5, 0, .03125], sweep_end=[-13.75, 0, .03125])
        assess_cached_capture(ticks, [good])
        for key, value in (('originroute', 0), ('tick', 0), ('tick', 64), ('tick', 65), ('bump', 1), ('brush', 0),
                ('fraction', 1), ('native_plane', [.8, 0, .6, 0]), ('sweep_start', [-17.5, 0, 18]),
                ('sweep_end', [-13.75, 0, 18]), ('sweep_end', [-13.7, 0, .03125])):
            with self.subTest(key=key), self.assertRaises(AssertionError): assess_cached_capture(ticks, [dict(good, **{key:value})])
        ticks[22][8:10], ticks[22][10:16] = [1, 1], [-15.2, 0, 1.11875, 90, 0, 0]
        later = dict(good, tick=23, fraction=0, sweep_start=[-15.2, 0, 1.11875], sweep_end=[-13.64975, 0, 1.11875])
        assess_cached_capture(ticks, [good, later])
        with self.assertRaises(AssertionError):
            assess_cached_capture(ticks, [good, dict(later, sweep_end=[-11.45, 0, 1.11875])])
        ticks[21][9] = 0
        with self.assertRaises(AssertionError): assess_cached_capture(ticks, [good])

    def test_cached_removed_world_and_inactive_ramp_query_are_distinct(self):
        brushes, seed = authored(19)
        tick = [19, 0, 15, 250, 0, 0, 1, .015, 0, 1]+seed[:6]+seed[6:]+[0]*6
        tick[10:13] = [80, 0, .03125]
        row = ['19', '0', 'down2', '-1']+list(map(str, tick[10:13]+[80, 0, -1.96875]+[.01, 0, 0, 0, 0, 0, 1, 0, 1]))
        oracle_validate(row, tick, brushes)
        unramped = row[:]; unramped[2:4] = ['unramped', '0']
        oracle_validate(unramped, tick, brushes)
        local = row[:]; local[2:4] = ['rampdown2', '1']; local[10:19] = ['1', '1', '1', '0', '0', '0', '0', '0', '0']
        oracle_validate(local, tick, brushes)
        with patch('offramp_motion.joint_overlap', side_effect=AssertionError('CACHE_JOINT_ACTED')):
            for q in (row, unramped, local):
                with self.assertRaisesRegex(AssertionError, 'CACHE_JOINT_ACTED'): oracle_validate(q, tick, brushes)
        # Actual world stationary/actual down2 NEVER inherit the removed-shape solid allowance.
        for kind in ('stationary', 'down2'):
            fake = local[:]; fake[2:4] = [kind, '-1']
            with self.subTest(kind=kind), self.assertRaises(AssertionError): oracle_validate(fake, tick, brushes)
        for index, value in ((2, 'worldonly'), (3, '-1'), (4, '999'), (13, '-1'), (18, '1')):
            fake = local[:]; fake[index] = value
            with self.subTest(index=index), self.assertRaises(AssertionError): oracle_validate(fake, tick, brushes)

    def test_explicit_fixture_profile_and_case_schema(self):
        self.assertEqual(len(PARAMS), 43)
        self.assertEqual(PARAMS['fixrampbugs'], 2)
        for c in range(len(LABELS)):
            brushes, seed = authored(c)
            self.assertEqual(len(seed), 12)
            self.assertEqual(len(brushes), 2 if c in (5, 7) or 10 <= c < 16 or c >= 18 else 1)
            self.assertEqual(len(brushes[0]['planes']), 7 if c == 2 else 6)
            self.assertEqual(step_count(c), 64 if c >= 16 else (32 if c < 6 or c >= 8 else (96 if c == 6 else MAX_STEPS)))
        self.assertEqual(authored(7)[0][1]['mins'], [-32, -128, 50])
        self.assertEqual(authored(7)[0][1]['maxs'], [32, 128, 128])
        self.assertEqual(authored(18), authored(19))
        self.assertEqual(authored(18)[0][1]['planes'][5], [-.8, 0, .6, 0])
        self.assertEqual(authored(10), authored(11))
        self.assertEqual(authored(12), authored(13))
        self.assertEqual(authored(10), authored(12))
        self.assertEqual([b['mins'][1] for b in authored(10)[0]], [-1024, -64])
        self.assertEqual([b['maxs'][1] for b in authored(10)[0]], [-896, 64])


def controls(text):
    lines = text.splitlines()
    def first(tag): return next(l for l in lines if f'OFFRAMPMOTION_{tag}' in l)
    tags = ('BEGIN', 'SOURCE', 'PARAM', 'CASE', 'BRUSH', 'PLANE', 'INSTANCE', 'SEED', 'TICK', 'ORACLE', 'CASE_END', 'END', 'COMPLETE')
    bad = [(f'missing-{tag}', '\n'.join(l for l in lines if l != first(tag))) for tag in tags]
    bad += [(f'duplicate-{tag}', text+first(tag)+'\n') for tag in tags]
    bad += [('unknown', text+'OFFRAMPMOTION_WHAT 1\n'), ('capture-outside-case', text+'OFFRAMPHULL_TICK 0\n'),
            ('failed-native-setup', text.replace('all checks passed', 'native checks did NOT pass')),
            ('unknown-command', text+'Unknown command deliberate\n')]
    for label, tag, index, value in (
        ('version', 'BEGIN', 0, 1), ('invalid-capture', 'BEGIN', 1, 2), ('invalid-oracle', 'BEGIN', 2, 2),
        ('case-count', 'BEGIN', 3, 7), ('step-cap', 'BEGIN', 4, 33), ('source-digest', 'SOURCE', 0, 'bad'),
        ('source-base', 'SOURCE', 1, 'bad'), ('wrong-profile', 'PARAM', 1, 999), ('wrong-case', 'CASE', 0, 1),
        ('wrong-label', 'CASE', 1, 'unregistered'), ('wrong-case-count', 'CASE', 2, 31), ('wrong-brush-count', 'CASE', 3, 3),
        ('wrong-brush-index', 'BRUSH', 1, 3), ('wrong-plane-count', 'BRUSH', 2, 7), ('brush-bounds', 'BRUSH', 3, -257),
        ('wrong-plane-side', 'PLANE', 2, 1), ('wrong-plane', 'PLANE', 3, -1), ('wrong-seed', 'SEED', 1, -99),
        ('seed-nan', 'SEED', 3, 'nan'), ('wrong-tick-case', 'TICK', 0, 1), ('wrong-tick-ordinal', 'TICK', 1, 1),
        ('wrong-msec', 'TICK', 2, 14), ('wrong-command', 'TICK', 3, 1), ('zero-native-ticks', 'TICK', 6, 0),
        ('wrong-native-rate', 'TICK', 7, .02), ('invalid-ramp-flag', 'TICK', 8, 2), ('invalid-ground-flag', 'TICK', 9, 2),
        ('body-nan', 'TICK', 10, 'nan'), ('body-position', 'TICK', 10, -50), ('wrong-hull', 'TICK', 16, -17),
        ('unexpected-posture', 'TICK', 22, 1), ('capsule-promotion', 'TICK', 25, 1), ('wrong-movetype', 'TICK', 26, 3),
        ('fractional-buttons', 'TICK', 27, .5), ('wrong-query-tick', 'ORACLE', 1, 1), ('wrong-query-kind', 'ORACLE', 2, 'fake'),
        ('wrong-query-brush', 'ORACLE', 3, 2), ('query-not-body-bound', 'ORACLE', 4, 42), ('bad-native-fraction', 'ORACLE', 10, -1),
        ('bad-query-solid', 'ORACLE', 11, 1), ('bad-query-entity', 'ORACLE', 13, 1), ('stale-miss-plane', 'ORACLE', 14, 1),
        ('bad-query-contents', 'ORACLE', 18, 0xffffffff+1), ('wrong-case-footer', 'CASE_END', 1, 31), ('wrong-footer', 'END', 0, 5)):
        bad.append((label, change(text, tag, index, value)))
    # ACTED plausible false negative from a real projected hit: joint collision
    # still exists; returning fraction=1 is not allowed to close support gates.
    bad.append(('native-oracle-false-negative', change(text, 'ORACLE', 10, 1, lambda r: r[2:4] == ['projected', '-1'])))
    bad.append(('native-capture-silent', '\n'.join(l for l in lines if not any(p in l for p in ('OFFRAMPBUF_', 'OFFRAMPORIGIN_', 'OFFRAMPGEOM_', 'OFFRAMPHULL_')))))
    for label, tag, index, value, pred in (
        ('posture-button-silent', 'TICK', 5, 0, lambda r: r[0] == '6' and r[1] == '3'),
        ('posture-transition-silent', 'TICK', 23, 0, lambda r: r[0] == '6' and r[1] == '3'),
        ('posture-fake-crouch-hull', 'TICK', 21, 62, lambda r: r[0] == '6' and r[22] == '1'),
        ('posture-fake-duck-timer', 'TICK', 24, -1, lambda r: r[0] == '6' and r[1] == '3'),
        ('posture-fake-oldbuttons', 'TICK', 27, 0, lambda r: r[0] == '6' and r[1] == '3'),
        ('ceiling-no-standing-hit', 'ORACLE', 11, 0, lambda r: r[0] == '7' and r[2] == 'standing' and r[11] == '1'),
        ('ceiling-standing-endpoint', 'ORACLE', 4, 999, lambda r: r[0] == '7' and r[2] == 'standing'),
        ('ceiling-actual-body-embedded', 'ORACLE', 11, 1, lambda r: r[0] == '7' and r[2] == 'stationary'),
        ('ceiling-wrong-clear-hull', 'TICK', 21, 45, lambda r: r[0] == '7' and r[1] == '191'),
        ('capsule-metadata-silent', 'TICK', 25, 0, lambda r: r[0] == '8'),
        ('capsule-fake-duck', 'TICK', 22, 1, lambda r: r[0] == '8'),
        ('capsule-wrong-command', 'TICK', 3, 250, lambda r: r[0] == '8'),
        ('capsule-seed-box-height', 'SEED', 3, 154.75, lambda r: r[0] == '8'),
        ('capsule-body-embedded', 'ORACLE', 11, 1, lambda r: r[0] == '8' and r[2] == 'stationary'),
        ('capsule-query-endpoint', 'ORACLE', 4, 999, lambda r: r[0] == '8'),
        ('capsule-query-kind-promotion', 'ORACLE', 2, 'projected', lambda r: r[0] == '8' and r[2] == 'down2'),
        ('capsule-query-box-label', 'ORACLE', 2, 'standing', lambda r: r[0] == '8' and r[2] == 'box')):
        bad.append((label, change(text, tag, index, value, pred)))
    for label, pred in (
        ('capsule-native-hit-silent', lambda r: r[0] == '8' and r[2] == 'down2'),
        ('capsule-box-difference-silent', lambda r: r[0] == '8' and r[2] == 'box')):
        bad.append((label, change_all(text, 'ORACLE', {10: 1, 11: 0, 12: 0, 14: 0, 15: 0, 16: 0, 17: 0, 18: 0}, pred)))
    bad.append(('capsule-native-miss-silent', change_all(text, 'ORACLE',
                {10: .5, 11: 0, 12: 0, 14: .8, 15: 0, 16: .6, 17: 0, 18: 1},
                lambda r: r[0] == '8' and r[2] == 'down2')))
    for label, namespace, tag, index in (
        ('capsule-winning-shape-metadata', 'OFFRAMPGEOM', 'CONTACT', 14),
        ('capsule-accepted-hull-metadata', 'OFFRAMPHULL', 'CONTACT', 8),
        ('capsule-tick-hull-metadata', 'OFFRAMPHULL', 'TICK', 7)):
        bad.append((label, change(text, tag, index, 0, lambda r: r[index] == '1', namespace)))
    for label, tag, index, value, pred in (
        ('transform-unpinned-box-hulls', 'PARAM', 1, 0, lambda r: r[0] == 'rotatedboxhulls'),
        ('transform-wrong-instance-case', 'INSTANCE', 0, 8, lambda r: True),
        ('transform-wrong-physent', 'INSTANCE', 1, 1, lambda r: True),
        ('transform-instance-origin-silent', 'INSTANCE', 2, 0, lambda r: True),
        ('transform-instance-angles-silent', 'INSTANCE', 6, 0, lambda r: True),
        ('transform-instance-scaled', 'INSTANCE', 8, 2, lambda r: True),
        ('transform-instance-capsule', 'INSTANCE', 9, 1, lambda r: True),
        ('transform-instance-nonfinite', 'INSTANCE', 2, 'nan', lambda r: True),
        ('transform-seed-local-substitution', 'SEED', 1, -100, lambda r: r[0] == '9'),
        ('transform-wrong-command', 'TICK', 3, 250, lambda r: r[0] == '9'),
        ('transform-capsule-promotion', 'TICK', 25, 1, lambda r: r[0] == '9'),
        ('transform-body-solid', 'ORACLE', 11, 1, lambda r: r[0] == '9' and r[2] == 'stationary'),
        ('transform-query-local-endpoints', 'ORACLE', 4, -100, lambda r: r[0] == '9'),
        ('transform-query-kind-promotion', 'ORACLE', 2, 'projected', lambda r: r[0] == '9'),
        ('transform-native-world-dist-promotion', 'ORACLE', 17, 600, lambda r: r[0] == '9' and float(r[10]) < 1),
        ('transform-native-normal-unrotated', 'ORACLE', 14, .8, lambda r: r[0] == '9' and float(r[10]) < 1)):
        bad.append((label, change(text, tag, index, value, pred)))
    bad.append(('transform-native-hit-silent', change_all(text, 'ORACLE',
                {10: 1, 11: 0, 12: 0, 14: 0, 15: 0, 16: 0, 17: 0, 18: 0},
                lambda r: r[0] == '9' and r[2] == 'down2')))
    bad.append(('transform-native-miss-silent', change_all(text, 'ORACLE',
                {10: .5, 11: 0, 12: 0, 14: .8*2**-.5, 15: .8*2**-.5, 16: .6, 17: 0, 18: 1},
                lambda r: r[0] == '9' and r[2] == 'down2')))
    for label, index, value in (
        ('transform-identity-solid-silent', 12, 0), ('transform-identity-solid-stale-plane', 14, 1),
        ('transform-identity-solid-stale-contents', 18, 1)):
        bad.append((label, change(text, 'ORACLE', index, value,
                    lambda r: r[0] == '9' and r[2] == 'identity' and r[11] == '1')))
    for label, index, value in (
        ('transform-copied-origin', 7, 999), ('transform-copied-angle', 11, 0),
        ('transform-copied-scale', 13, 0), ('transform-copied-native-bih', 15, 0)):
        bad.append((label, change(text, 'CONTACT', index, value, lambda r: r[11] == '45', 'OFFRAMPGEOM')))
    for tag in ('SET', 'PHYSENT'):
        line = first(tag)
        bad += [(f'entity-missing-{tag}', text.replace(line+'\n', '', 1)),
                (f'entity-duplicate-{tag}', text+line+'\n')]
    for label, tag, index, value, pred in (
        ('entity-active-count', 'SET', 1, 1, lambda r: r[0] == '10'),
        ('entity-skip-filter', 'SET', 2, 42, lambda r: r[0] == '10'),
        ('removed-active-count', 'SET', 1, 2, lambda r: r[0] == '11'),
        ('entity-wrong-slot', 'PHYSENT', 1, 0, lambda r: r[:2] == ['10', '1']),
        ('entity-wrong-info', 'PHYSENT', 2, 0, lambda r: r[:2] == ['10', '1']),
        ('entity-world-model', 'PHYSENT', 3, 'maps/authored_offramp_motion.bsp', lambda r: r[:2] == ['10', '1']),
        ('entity-wrong-brush', 'PHYSENT', 4, 0, lambda r: r[:2] == ['10', '1']),
        ('entity-slot-inactive', 'PHYSENT', 5, 0, lambda r: r[:2] == ['10', '1']),
        ('removed-slot-active', 'PHYSENT', 5, 1, lambda r: r[:2] == ['11', '1']),
        ('entity-origin', 'INSTANCE', 2, 1000, lambda r: r[:2] == ['10', '1']),
        ('entity-rotation', 'INSTANCE', 6, 45, lambda r: r[:2] == ['10', '1']),
        ('entity-scale', 'INSTANCE', 8, 0, lambda r: r[:2] == ['10', '1']),
        ('entity-capsule', 'INSTANCE', 9, 1, lambda r: r[:2] == ['10', '1']),
        ('entity-metadata-nonfinite', 'INSTANCE', 2, 'nan', lambda r: r[:2] == ['10', '1']),
        ('entity-ramp-silent', 'TICK', 8, 0, lambda r: r[:2] == ['10', '0']),
        ('removed-fake-ramp', 'TICK', 8, 1, lambda r: r[:2] == ['11', '0']),
        ('entity-command', 'TICK', 3, 250, lambda r: r[0] == '10'),
        ('removed-seed', 'SEED', 1, -99, lambda r: r[0] == '11'),
        ('entity-query-winner-world', 'ORACLE', 13, 0, lambda r: r[0] == '10' and float(r[10]) < 1),
        ('entity-query-miss-stale-winner', 'ORACLE', 13, 1, lambda r: r[0] == '10' and r[2] == 'worldonly'),
        ('entity-query-endpoint', 'ORACLE', 4, 999, lambda r: r[0] == '10'),
        ('entity-query-solid', 'ORACLE', 11, 1, lambda r: r[0] == '10'),
        ('entity-query-removal-label', 'ORACLE', 2, 'down2', lambda r: r[0] == '10' and r[2] == 'worldonly')):
        bad.append((label, change(text, tag, index, value, pred)))
    bad.append(('entity-native-hits-silent', change_all(text, 'ORACLE',
                {10: 1, 13: -1, 14: 0, 15: 0, 16: 0, 17: 0, 18: 0}, lambda r: r[0] == '10' and r[2] == 'down2')))
    bad.append(('entity-removal-silent', change_all(text, 'ORACLE',
                {10: .5, 13: 1, 14: .8, 15: 0, 16: .6, 17: 0, 18: 1}, lambda r: r[0] == '10' and r[2] == 'worldonly')))
    for label, namespace, tag, index, value in (
        ('entity-contact-world-winner', 'OFFRAMPBUF', 'CONTACT', 3, 0),
        ('entity-origin-world-winner', 'OFFRAMPORIGIN', 'CONTACT', 8, 0),
        ('entity-origin-world-model', 'OFFRAMPORIGIN', 'CONTACT', 9, 'maps/authored_offramp_motion.bsp'),
        ('entity-origin-embedded-promotion', 'OFFRAMPORIGIN', 'CONTACT', 6, 1),
        ('entity-origin-cached-route', 'OFFRAMPORIGIN', 'CONTACT', 2, 1),
        ('entity-origin-wrong-leaf', 'OFFRAMPORIGIN', 'CONTACT', 4, 1),
        ('entity-copied-world-brush', 'OFFRAMPGEOM', 'SHAPE', 4, -1024),
        ('entity-copied-origin', 'OFFRAMPGEOM', 'CONTACT', 7, 1000),
        ('entity-copied-scale', 'OFFRAMPGEOM', 'CONTACT', 13, 0),
        ('entity-copied-callback', 'OFFRAMPGEOM', 'CONTACT', 15, 0),
        ('entity-accepted-hull', 'OFFRAMPHULL', 'CONTACT', 7, 45)):
        bad.append((label, change_case(text, 10, tag, index, value, namespace=namespace)))
    embed_line = first('EMBED')
    removed_embed = next(l for l in text.splitlines() if 'OFFRAMPMOTION_EMBED 13 ' in l)
    seed_line = next(l for l in text.splitlines() if 'OFFRAMPMOTION_SEED 12 ' in l)
    bad += [('embedded-missing-EMBED', text.replace(embed_line+'\n', '', 1)),
            ('embedded-missing-removed-EMBED', text.replace(removed_embed+'\n', '', 1)),
            ('embedded-duplicate-EMBED', text+embed_line+'\n'),
            ('embedded-width', text.replace(embed_line, embed_line.rsplit(' ', 1)[0], 1)),
            ('embedded-reordered-EMBED', text.replace(embed_line+'\n'+seed_line, seed_line+'\n'+embed_line, 1))]
    for label, tag, index, value, pred in (
        ('embedded-active-physents', 'SET', 1, 2, lambda r: r[0] == '12'),
        ('embedded-skip-filter', 'SET', 2, 0, lambda r: r[0] == '12'),
        ('embedded-world-slot', 'PHYSENT', 1, 1, lambda r: r[0] == '12'),
        ('embedded-parent-model', 'PHYSENT', 3, EMBEDDED_MODEL, lambda r: r[0] == '12'),
        ('embedded-parent-direct-brush', 'PHYSENT', 4, 1, lambda r: r[0] == '12'),
        ('embedded-parent-pose', 'INSTANCE', 2, 1000, lambda r: r[0] == '12'),
        ('embedded-root-leaf', 'EMBED', 1, 1, lambda r: r[0] == '12'),
        ('embedded-child-leaf', 'EMBED', 2, 1, lambda r: r[0] == '12'),
        ('embedded-node-count', 'EMBED', 3, 3, lambda r: r[0] == '12'),
        ('embedded-inactive-child', 'EMBED', 4, 0, lambda r: r[0] == '12'),
        ('embedded-removed-child-active', 'EMBED', 4, 1, lambda r: r[0] == '13'),
        ('embedded-root-kind', 'EMBED', 5, 'brush', lambda r: r[0] == '12'),
        ('embedded-child-name', 'EMBED', 6, ENTITY_MODEL, lambda r: r[0] == '12'),
        ('embedded-child-origin', 'EMBED', 7, 1000, lambda r: r[0] == '12'),
        ('embedded-child-axis', 'EMBED', 10, .5, lambda r: r[0] == '12'),
        ('embedded-child-axis-nonfinite', 'EMBED', 11, 'nan', lambda r: r[0] == '12'),
        ('embedded-ramp-silent', 'TICK', 8, 0, lambda r: r[:2] == ['12', '0']),
        ('embedded-removed-fake-ramp', 'TICK', 8, 1, lambda r: r[:2] == ['13', '0']),
        ('embedded-query-child-physent', 'ORACLE', 13, 1, lambda r: r[0] == '12' and float(r[10]) < 1),
        ('embedded-query-endpoint', 'ORACLE', 4, 999, lambda r: r[0] == '12'),
        ('embedded-query-body-startsolid', 'ORACLE', 11, 1, lambda r: r[0] == '12'),
        ('embedded-query-removal-label', 'ORACLE', 2, 'worldonly', lambda r: r[0] == '12' and r[2] == 'unembedded')):
        bad.append((label, change(text, tag, index, value, pred)))
    bad.append(('embedded-native-hits-silent', change_all(text, 'ORACLE',
                {10: 1, 13: -1, 14: 0, 15: 0, 16: 0, 17: 0, 18: 0}, lambda r: r[0] == '12' and r[2] == 'down2')))
    bad.append(('embedded-removal-silent', change_all(text, 'ORACLE',
                {10: .5, 13: 0, 14: .8, 15: 0, 16: .6, 17: 0, 18: 1}, lambda r: r[0] == '12' and r[2] == 'unembedded')))
    for label, namespace, tag, index, value in (
        ('embedded-contact-child-physent', 'OFFRAMPBUF', 'CONTACT', 3, 1),
        ('embedded-origin-child-physent', 'OFFRAMPORIGIN', 'CONTACT', 8, 1),
        ('embedded-origin-parent-model', 'OFFRAMPORIGIN', 'CONTACT', 9, 'maps/authored_offramp_motion.bsp'),
        ('embedded-origin-wrong-child', 'OFFRAMPORIGIN', 'CONTACT', 9, ENTITY_MODEL),
        ('embedded-origin-cached-route', 'OFFRAMPORIGIN', 'CONTACT', 2, 1),
        ('embedded-origin-triangle', 'OFFRAMPORIGIN', 'CONTACT', 3, 2),
        ('embedded-origin-leaf', 'OFFRAMPORIGIN', 'CONTACT', 4, 1),
        ('embedded-origin-root', 'OFFRAMPORIGIN', 'CONTACT', 5, 1),
        ('embedded-origin-depth-flattened', 'OFFRAMPORIGIN', 'CONTACT', 6, 0),
        ('embedded-origin-wrong-depth', 'OFFRAMPORIGIN', 'CONTACT', 6, 2),
        ('embedded-copied-world-brush', 'OFFRAMPGEOM', 'SHAPE', 4, -1024),
        ('embedded-copied-root-pose', 'OFFRAMPGEOM', 'CONTACT', 7, 1000),
        ('embedded-copied-root-callback', 'OFFRAMPGEOM', 'CONTACT', 15, 0),
        ('embedded-accepted-hull', 'OFFRAMPHULL', 'CONTACT', 7, 45)):
        bad.append((label, change_case(text, 12, tag, index, value, namespace=namespace)))
    triangle_line = first('TRIANGLE')
    removed_triangle = next(l for l in lines if 'OFFRAMPMOTION_TRIANGLE 15 ' in l)
    bad += [('triangle-missing-wiring', text.replace(triangle_line+'\n', '', 1)),
            ('triangle-missing-removed-wiring', text.replace(removed_triangle+'\n', '', 1)),
            ('triangle-duplicate-wiring', text+triangle_line+'\n'),
            ('triangle-width', text.replace(triangle_line, triangle_line.rsplit(' ', 1)[0], 1))]
    for label, tag, index, value, pred in (
        ('triangle-unpinned-bevels', 'PARAM', 1, 0, lambda r: r[0] == 'trisoup_bevels'),
        ('triangle-active-count', 'SET', 1, 2, lambda r: r[0] == '14'),
        ('triangle-skip-filter', 'SET', 2, 0, lambda r: r[0] == '14'),
        ('triangle-world-model', 'PHYSENT', 3, EMBEDDED_MODEL, lambda r: r[0] == '14'),
        ('triangle-brush-promotion', 'PHYSENT', 4, 0, lambda r: r[0] == '14'),
        ('triangle-instance-origin', 'INSTANCE', 2, 1000, lambda r: r[0] == '14'),
        ('triangle-instance-scale', 'INSTANCE', 8, 0, lambda r: r[0] == '14'),
        ('triangle-instance-capsule', 'INSTANCE', 9, 1, lambda r: r[0] == '14'),
        ('triangle-wiring-inactive', 'TRIANGLE', 1, 0, lambda r: r[0] == '14'),
        ('triangle-wiring-leaf', 'TRIANGLE', 2, 1, lambda r: r[0] == '14'),
        ('triangle-wiring-index', 'TRIANGLE', 3, 2, lambda r: r[0] == '14'),
        ('triangle-wiring-vertex', 'TRIANGLE', 6, -255, lambda r: r[0] == '14'),
        ('triangle-wiring-nonfinite', 'TRIANGLE', 8, 'nan', lambda r: r[0] == '14'),
        ('triangle-removed-wiring-active', 'TRIANGLE', 1, 1, lambda r: r[0] == '15'),
        ('triangle-removed-wiring-leaf', 'TRIANGLE', 2, 0, lambda r: r[0] == '15'),
        ('triangle-ramp-silent', 'TICK', 8, 0, lambda r: r[:2] == ['14', '0']),
        ('triangle-removed-fake-ramp', 'TICK', 8, 1, lambda r: r[:2] == ['15', '0']),
        ('triangle-command', 'TICK', 3, 250, lambda r: r[0] == '14'),
        ('triangle-removed-seed', 'SEED', 1, -99, lambda r: r[0] == '15'),
        ('triangle-query-winner-entity', 'ORACLE', 13, 1, lambda r: r[0] == '14' and float(r[10]) < 1),
        ('triangle-query-endpoint', 'ORACLE', 4, 999, lambda r: r[0] == '14'),
        ('triangle-query-body-solid', 'ORACLE', 11, 1, lambda r: r[0] == '14'),
        ('triangle-query-removal-label', 'ORACLE', 2, 'unembedded', lambda r: r[0] == '14' and r[2] == 'untriangled'),
        ('triangle-query-plane-nonunit', 'ORACLE', 14, 0, lambda r: r[0] == '14' and float(r[10]) < 1),
        ('triangle-query-hit-contents', 'ORACLE', 18, 0, lambda r: r[0] == '14' and float(r[10]) < 1)):
        bad.append((label, change(text, tag, index, value, pred)))
    bad.append(('triangle-native-hits-silent', change_all(text, 'ORACLE',
                {10: 1, 13: -1, 14: 0, 15: 0, 16: 0, 17: 0, 18: 0}, lambda r: r[0] == '14' and r[2] == 'down2')))
    bad.append(('triangle-native-misses-silent', change_all(text, 'ORACLE',
                {10: .5, 13: 0, 14: .8, 15: 0, 16: .6, 17: 0, 18: 1}, lambda r: r[0] == '14' and r[2] == 'down2')))
    bad.append(('triangle-removal-silent', change_all(text, 'ORACLE',
                {10: .5, 13: 0, 14: .8, 15: 0, 16: .6, 17: 0, 18: 1}, lambda r: r[0] == '14' and r[2] == 'untriangled')))
    for label, namespace, tag, index, value in (
        ('triangle-contact-entity', 'OFFRAMPBUF', 'CONTACT', 3, 1),
        ('triangle-contact-solid', 'OFFRAMPBUF', 'CONTACT', 22, 1),
        ('triangle-origin-cached', 'OFFRAMPORIGIN', 'CONTACT', 2, 1),
        ('triangle-origin-brush-promotion', 'OFFRAMPORIGIN', 'CONTACT', 3, 1),
        ('triangle-origin-leaf', 'OFFRAMPORIGIN', 'CONTACT', 4, 1),
        ('triangle-origin-root', 'OFFRAMPORIGIN', 'CONTACT', 5, 1),
        ('triangle-origin-nested-promotion', 'OFFRAMPORIGIN', 'CONTACT', 6, 1),
        ('triangle-origin-contents', 'OFFRAMPORIGIN', 'CONTACT', 7, 0),
        ('triangle-origin-entity', 'OFFRAMPORIGIN', 'CONTACT', 8, 1),
        ('triangle-origin-model', 'OFFRAMPORIGIN', 'CONTACT', 9, EMBEDDED_MODEL),
        ('triangle-shape-stale-bounds', 'OFFRAMPGEOM', 'SHAPE', 3, -256),
        ('triangle-shape-stale-sides', 'OFFRAMPGEOM', 'SHAPE', 2, 6),
        ('triangle-shape-origin', 'OFFRAMPGEOM', 'CONTACT', 7, 1000),
        ('triangle-shape-scale', 'OFFRAMPGEOM', 'CONTACT', 13, 0),
        ('triangle-shape-capsule', 'OFFRAMPGEOM', 'CONTACT', 14, 1),
        ('triangle-shape-callback', 'OFFRAMPGEOM', 'CONTACT', 15, 0),
        ('triangle-accepted-hull', 'OFFRAMPHULL', 'CONTACT', 7, 45),
        ('triangle-accepted-capsule', 'OFFRAMPHULL', 'CONTACT', 8, 1)):
        bad.append((label, change_case(text, 14, tag, index, value, namespace=namespace)))
    for label, case, tag, index, value, pred, namespace in (
        ('air-button-silent', 16, 'TICK', 5, 0, lambda r: r[1] == '3', 'OFFRAMPMOTION'),
        ('air-no-instant-duck', 16, 'TICK', 23, 1, lambda r: r[1] == '3', 'OFFRAMPMOTION'),
        ('air-wrong-crouch-hull', 16, 'TICK', 21, 62, lambda r: r[1] == '3', 'OFFRAMPMOTION'),
        ('air-timer-silent', 16, 'TICK', 24, 0, lambda r: r[1] == '3', 'OFFRAMPMOTION'),
        ('air-oldbuttons-silent', 16, 'TICK', 27, 0, lambda r: r[1] == '3', 'OFFRAMPMOTION'),
        ('air-no-instant-unduck', 16, 'TICK', 22, 1, lambda r: r[1] == '11', 'OFFRAMPMOTION'),
        ('air-origin-shift-silent', 16, 'TICK', 12, 128, lambda r: r[1] == '3', 'OFFRAMPMOTION'),
        ('air-fake-gravity', 17, 'TICK', 15, 0, lambda r: r[1] == '0', 'OFFRAMPMOTION'),
        ('air-fake-control-duck', 17, 'TICK', 22, 1, lambda r: r[1] == '3', 'OFFRAMPMOTION'),
        ('air-no-landing', 16, 'TICK', 9, 0, lambda r: r[1] == '63', 'OFFRAMPMOTION'),
        ('air-query-endpoints', 16, 'ORACLE', 4, 999, lambda r: True, 'OFFRAMPMOTION'),
        ('air-query-body-solid', 16, 'ORACLE', 11, 1, lambda r: r[2] == 'stationary', 'OFFRAMPMOTION'),
        ('air-query-triangle-family', 16, 'ORACLE', 2, 'untriangled', lambda r: r[2] == 'down2', 'OFFRAMPMOTION'),
        ('air-query-projected-silent', 16, 'ORACLE', 10, 1, lambda r: r[2] == 'projected', 'OFFRAMPMOTION'),
        ('air-query-standing-fake-hit', 16, 'ORACLE', 10, .5, lambda r: r[2] == 'standing', 'OFFRAMPMOTION'),
        ('air-captured-hull', 16, 'TICK', 6, 62, lambda r: r[0] == '3', 'OFFRAMPHULL'),
        ('air-captured-duck', 16, 'TICK', 9, 0, lambda r: r[0] == '3', 'OFFRAMPHULL'),
        ('air-captured-timer', 16, 'TICK', 11, 0, lambda r: r[0] == '3', 'OFFRAMPHULL')):
        bad.append((label, change_case(text, case, tag, index, value, pred, namespace)))
    # Plausible multi-tick posture edits must not erase duck/release actuation.
    for case, start, end, updates in ((16, 3, 10, {21: 62, 22: 0, 24: 0, 27: 0}),
                                    (16, 11, 63, {21: 45, 22: 1, 24: 1000})):
        bad.append(('air-coherent-silent-posture-'+str(start), change_all(text, 'TICK', updates,
                    lambda r, case=case, start=start, end=end: int(r[0]) == case and start <= int(r[1]) <= end)))
    for label, case, tag, index, value, pred, namespace in (
        ('cached-set-count', 18, 'BRUSHSET', 1, 1, lambda r: True, 'OFFRAMPMOTION'),
        ('cached-set-silent', 18, 'BRUSHSET', 3, 0, lambda r: True, 'OFFRAMPMOTION'),
        ('cached-removed-set-promotion', 19, 'BRUSHSET', 3, 1, lambda r: True, 'OFFRAMPMOTION'),
        ('cached-wrong-forward', 18, 'TICK', 3, 0, lambda r: r[1] == '22', 'OFFRAMPMOTION'),
        ('cached-silent-raw-impact', 18, 'TICK', 8, 0, lambda r: r[8] == '1', 'OFFRAMPMOTION'),
        ('cached-fake-control-ramp', 19, 'TICK', 8, 1, lambda r: True, 'OFFRAMPMOTION'),
        ('cached-fake-control-air', 19, 'TICK', 9, 0, lambda r: True, 'OFFRAMPMOTION'),
        ('cached-world-local-family', 18, 'ORACLE', 2, 'rampdown2', lambda r: r[2] == 'down2', 'OFFRAMPMOTION'),
        ('cached-query-local-brush', 18, 'ORACLE', 3, 0, lambda r: r[2] == 'rampdown2', 'OFFRAMPMOTION'),
        ('cached-query-unramped-endpoint', 18, 'ORACLE', 9, 999, lambda r: r[2] == 'unramped', 'OFFRAMPMOTION'),
        ('cached-query-erased-ramp-hit', 18, 'ORACLE', 10, 1, lambda r: r[2] == 'rampdown2' and float(r[10]) < 1, 'OFFRAMPMOTION'),
        ('cached-control-hidden-local-solid', 19, 'ORACLE', 11, 0, lambda r: r[2] == 'rampdown2' and r[11] == '1', 'OFFRAMPMOTION'),
        ('cached-control-solid-fake-contents', 19, 'ORACLE', 18, 1, lambda r: r[2] == 'rampdown2' and r[11] == '1', 'OFFRAMPMOTION'),
        ('cached-origin-fake-fresh-promotion', 18, 'CONTACT', 2, 1, lambda r: r[2] == '0', 'OFFRAMPORIGIN'),
        ('cached-origin-route-recovery', 18, 'CONTACT', 2, 2, lambda r: r[2] == '1', 'OFFRAMPORIGIN'),
        ('cached-origin-route-portal', 18, 'CONTACT', 2, 3, lambda r: r[2] == '1', 'OFFRAMPORIGIN'),
        ('cached-origin-wrong-brush-kind', 18, 'CONTACT', 3, 2, lambda r: r[2] == '1', 'OFFRAMPORIGIN'),
        ('cached-origin-wrong-model', 18, 'CONTACT', 9, ENTITY_MODEL, lambda r: r[2] == '1', 'OFFRAMPORIGIN'),
        ('cached-contact-wrong-bump', 18, 'CONTACT', 2, 1, lambda r: True, 'OFFRAMPBUF'),
        ('cached-contact-wrong-start', 18, 'CONTACT', 9, 999, lambda r: True, 'OFFRAMPBUF'),
        ('cached-contact-wrong-end', 18, 'CONTACT', 12, 999, lambda r: True, 'OFFRAMPBUF'),
        ('cached-contact-wrong-plane', 18, 'CONTACT', 6, .8, lambda r: True, 'OFFRAMPBUF'),
        ('cached-contact-wrong-fraction', 18, 'CONTACT', 4, 1, lambda r: True, 'OFFRAMPBUF'),
        ('cached-contact-recovered', 18, 'CONTACT', 21, 1, lambda r: True, 'OFFRAMPBUF'),
        ('cached-shape-wrong-bounds', 18, 'SHAPE', 4, -257, lambda r: True, 'OFFRAMPGEOM'),
        ('cached-hull-wrong-top', 18, 'CONTACT', 7, 45, lambda r: True, 'OFFRAMPHULL')):
        bad.append((label, change_case(text, case, tag, index, value, pred, namespace)))
    for case in (18, 19):
        token = next(l for l in text.splitlines() if f'OFFRAMPMOTION_BRUSHSET {case} ' in l)
        bad.append(('missing-cached-set-'+str(case), text.replace(token, '')))
        bad.append(('duplicate-cached-set-'+str(case), text.replace(token, token+'\n'+token)))
    # Erasing ALL cached labels must refuse, not merely alter a report count.
    start = text.index('OFFRAMPMOTION_CASE 18 '); end = text.index('OFFRAMPMOTION_CASE_END 18 ', start)
    lines = text[start:end].splitlines(); count = 0
    for i, line in enumerate(lines):
        token = 'OFFRAMPORIGIN_CONTACT '
        if token not in line: continue
        prefix, tail = line.split(token, 1); row = tail.split()
        if row[2] == '1': row[2] = '0'; lines[i] = prefix+token+' '.join(row); count += 1
    assert count, 'Native cached labels did not ACT for erase control'
    bad.append(('all-cached-routes-erased', text[:start]+'\n'.join(lines)+'\n'+text[end:]))
    return bad


def acted_controls(arms):
    a = json.loads(arms.read_text()); names = ('nooracle', 'control', 'off', 'on', 'repeat')
    texts = {n: Path(a[n]['log']).read_text(errors='replace') for n in names}
    r = compare(*(texts[n] for n in names)); assert r['native_static_fixture_gates'] == 'PASS'
    bad = controls(texts['on'])
    for label, text in bad:
        assert text != texts['on'], f'Counterfactual did not ACT: {label}'
        try: grade(text)
        except AssertionError: continue
        raise AssertionError(f'Native motion counterfactual accepted: {label}')
    # Legal provenance/numeric changes must still fail cross-arm equality.
    for text in (change(texts['on'], 'SOURCE', 0, '0'*64),
                 change(texts['on'], 'ORACLE', 10, .5, lambda r: r[2:4] == ['projected', '-1'])):
        try: compare(texts['nooracle'], texts['control'], texts['off'], text, texts['repeat'])
        except AssertionError: continue
        raise AssertionError('Native cross-arm counterfactual accepted')
    # A legal single changed capsule result need not fail the standalone
    # abstaining reader; it MUST still fail exact native cross-arm parity.
    altered = change(texts['on'], 'ORACLE', 10, .5, lambda r: r[0] == '8' and r[2] == 'down2' and float(r[10]) < 1)
    with unittest.TestCase().assertRaises(AssertionError):
        compare(texts['nooracle'], texts['control'], texts['off'], altered, texts['repeat'])
    def promote(o, contact, shape, payload, mapname):
        if shape['capsule']: return 'copied-world-brush-plane-bound', [5]
        return shape_category(o, contact, shape, payload, mapname)
    with patch('offramp_motion.shape_category', side_effect=promote), unittest.TestCase().assertRaisesRegex(AssertionError, 'promoted'):
        grade(texts['on'])
    assert r['capsule_support_geometry_acceptance'] == 'ABSTAIN'
    assert r['cases'][8]['independent_capsule_oracle'] == 'NOT_IMPLEMENTED'
    altered = change(texts['on'], 'ORACLE', 10, .5, lambda r: r[0] == '9' and r[2] == 'down2' and float(r[10]) < 1)
    with unittest.TestCase().assertRaises(AssertionError):
        compare(texts['nooracle'], texts['control'], texts['off'], altered, texts['repeat'])
    def promote_transform(o, contact, shape, payload, mapname):
        if shape['instance_angles'] == [0, 45, 0]: return 'copied-world-brush-plane-bound', [5]
        return shape_category(o, contact, shape, payload, mapname)
    with patch('offramp_motion.shape_category', side_effect=promote_transform), unittest.TestCase().assertRaisesRegex(AssertionError, 'promoted'):
        grade(texts['on'])
    assert r['transformed_support_geometry_acceptance'] == 'ABSTAIN'
    assert r['cases'][9]['independent_transform_oracle'] == 'NOT_IMPLEMENTED'
    def promote_entity(o, contact, shape, payload, mapname):
        if o[8] == 1 and o[9] == ENTITY_MODEL: return 'copied-world-brush-plane-bound', [5]
        return shape_category(o, contact, shape, payload, mapname)
    with patch('offramp_motion.shape_category', side_effect=promote_entity), unittest.TestCase().assertRaisesRegex(AssertionError, 'promoted'):
        grade(texts['on'])
    altered = change(texts['on'], 'ORACLE', 10, .5, lambda r: r[0] == '10' and r[2] == 'down2' and float(r[10]) < 1)
    with unittest.TestCase().assertRaises(AssertionError):
        compare(texts['nooracle'], texts['control'], texts['off'], altered, texts['repeat'])
    assert r['entity_support_geometry_acceptance'] == 'ABSTAIN'
    assert r['entity_removal_trajectory_gates'] == 'PASS'
    assert r['cases'][10]['accepted'] and not r['cases'][11]['accepted']
    def promote_embedded(o, contact, shape, payload, mapname):
        if o[6] == 1 and o[9] == EMBEDDED_MODEL: return 'copied-world-brush-plane-bound', [5]
        return shape_category(o, contact, shape, payload, mapname)
    with patch('offramp_motion.shape_category', side_effect=promote_embedded), unittest.TestCase().assertRaisesRegex(AssertionError, 'promoted'):
        grade(texts['on'])
    altered = change(texts['on'], 'ORACLE', 10, .5, lambda r: r[0] == '12' and r[2] == 'down2' and float(r[10]) < 1)
    with unittest.TestCase().assertRaises(AssertionError):
        compare(texts['nooracle'], texts['control'], texts['off'], altered, texts['repeat'])
    assert r['embedded_support_geometry_acceptance'] == 'ABSTAIN'
    assert r['embedded_removal_trajectory_gates'] == 'PASS'
    assert r['cases'][12]['accepted'] and not r['cases'][13]['accepted']
    def promote_triangle(o, contact, shape, payload, mapname):
        if o[3] == 2: return 'copied-world-brush-plane-bound', [5]
        return shape_category(o, contact, shape, payload, mapname)
    with patch('offramp_motion.shape_category', side_effect=promote_triangle), unittest.TestCase().assertRaisesRegex(AssertionError, 'promoted'):
        grade(texts['on'])
    altered = change(texts['on'], 'ORACLE', 10, .5, lambda r: r[0] == '14' and r[2] == 'down2' and float(r[10]) < 1)
    grade(altered)  # A legal changed native result is NOT independent geometry proof.
    with unittest.TestCase().assertRaises(AssertionError):
        compare(texts['nooracle'], texts['control'], texts['off'], altered, texts['repeat'])
    assert r['triangle_support_geometry_acceptance'] == 'ABSTAIN'
    assert r['triangle_removal_trajectory_gates'] == 'PASS'
    assert r['cases'][14]['independent_triangle_query_oracle'] == 'NOT_IMPLEMENTED'
    assert r['cases'][14]['accepted'] and not r['cases'][15]['accepted']
    assert r['airborne_open_duck_unduck_native_gates'] == 'PASS'
    assert r['general_airborne_posture_acceptance'] == 'NOT_TESTED'
    # Fixture-only oracle arm has no capture backstop: plausible legal pose or
    # timer changes MUST still fail the matched native-air posture gates.
    for index, value in ((12, 128), (24, 985), (27, 0), (9, 1)):
        altered = change_case(texts['control'], 16, 'TICK', index, value, lambda row: row[1] == '3')
        with unittest.TestCase().assertRaises(AssertionError): grade(altered)
    assert r['cached_ground_approach_native_path_capture_gates'] == 'PASS'
    assert r['general_cached_recovery_portal_acceptance'] == 'NOT_TESTED'
    # Legal actor/query mutations in the fixture-only oracle arm cannot hide the
    # native ramp approach/removal, even with no capture comparison available.
    for case, index, value, pred in ((18, 8, 0, lambda row: row[8] == '1'),
            (18, 9, 0, lambda row: row[1] == '0'), (19, 8, 1, lambda row: row[1] == '0'),
            (19, 15, 1, lambda row: row[1] == '0')):
        altered = change_case(texts['control'], case, 'TICK', index, value, pred)
        with unittest.TestCase().assertRaises(AssertionError): grade(altered)
    print(f'{len(bad)+21} ACTED native motion controls, zero failed; capsule/transformed/entity/embedded/triangle actors ABSTAIN PASS')


def snapshot(engine):
    result = BASE_SNAPSHOT(engine); p = engine/'engine/common'/TARGET
    result[str(p)] = hashlib.sha256(p.read_bytes()).hexdigest() if p.exists() else None
    return result


def installer_controls(engine, primary):
    before = snapshot(engine); target = engine/'engine/common'/TARGET
    target.write_text('owned untracked native motion sentinel\n'); owned = snapshot(engine)
    try:
        for control in (False, True):
            try: instrument(engine, control)
            except RuntimeError: assert snapshot(engine) == owned
            else: raise AssertionError('Motion installer overwrote include')
            print('PASS motion include collision/refusal:', control)
    finally: target.unlink()
    assert snapshot(engine) == before
    for control in (False, True):
        if control:
            p = engine/'engine/common/pm_source.c'; original = p.read_bytes()
            p.write_bytes(original.replace(b'void PMSrc_Init', b'void DELIBERATELY_MISSING_Init'))
            changed = snapshot(engine)
            try:
                try: prepare(engine, True)
                except RuntimeError: assert snapshot(engine) == changed
                else: raise AssertionError('Fixture-only prepare accepted missing source anchor')
            finally: p.write_bytes(original)
        else:
            plan = prepare(engine); p = engine/'engine/common/pm_source.c'
            plan[p] = plan[p].replace('void PMSrc_Init', 'void DELIBERATELY_MISSING_Init')
            with patch('offramp_motion_smoke.hull_prepare', return_value=plan):
                try: instrument(engine)
                except RuntimeError: assert snapshot(engine) == before
                else: raise AssertionError('Motion installer accepted late generated anchor')
        assert snapshot(engine) == before
        print('PASS original/generated native motion anchor refusal:', control)
    # Existing multi-layer dirty/primary/repeat and generated-anchor controls,
    # but every install/refusal now goes through the FULL motion composer.
    with patch('test_offramp_hull.snapshot', side_effect=snapshot), patch('test_offramp_hull.instrument', side_effect=instrument):
        hull_tests.installer_controls(engine, primary)


def main():
    ap = argparse.ArgumentParser(description=__doc__); ap.add_argument('--arms', type=Path)
    ap.add_argument('--installer-engine', type=Path); ap.add_argument('--primary-engine', type=Path); a = ap.parse_args()
    r = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Tests))
    if not r.wasSuccessful(): raise SystemExit(1)
    if a.installer_engine:
        if not a.primary_engine: ap.error('--installer-engine requires --primary-engine')
        installer_controls(a.installer_engine, a.primary_engine)
    if a.arms: acted_controls(a.arms)


if __name__ == '__main__': main()
