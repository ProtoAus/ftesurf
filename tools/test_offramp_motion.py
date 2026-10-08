#!/usr/bin/env python3
"""Joint convex/schema units and ACTED retained native-trajectory controls."""
import argparse
import hashlib
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from offramp_motion import INSTANCE, LABELS, MAX_STEPS, PARAMS, authored, compare, grade, joint_overlap, oracle_validate, parse, shape_category, step_count
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

    def test_explicit_fixture_profile_and_case_schema(self):
        self.assertEqual(len(PARAMS), 42)
        self.assertEqual(PARAMS['fixrampbugs'], 2)
        for c in range(len(LABELS)):
            brushes, seed = authored(c)
            self.assertEqual(len(seed), 12)
            self.assertEqual(len(brushes), 2 if c in (5, 7) else 1)
            self.assertEqual(len(brushes[0]['planes']), 7 if c == 2 else 6)
            self.assertEqual(step_count(c), 32 if c < 6 or c >= 8 else (96 if c == 6 else MAX_STEPS))
        self.assertEqual(authored(7)[0][1]['mins'], [-32, -128, 50])
        self.assertEqual(authored(7)[0][1]['maxs'], [32, 128, 128])


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
    print(f'{len(bad)+7} ACTED native motion controls, zero failed; eight AABB/posture + capsule/transformed actors ABSTAIN PASS')


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
