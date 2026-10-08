#!/usr/bin/env python3
"""Joint convex/schema units and ACTED retained native-trajectory controls."""
import argparse
import hashlib
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from offramp_motion import LABELS, MAX_STEPS, PARAMS, authored, compare, grade, joint_overlap, oracle_validate, parse, step_count
from offramp_motion_smoke import TARGET, instrument, prepare
import test_offramp_hull as hull_tests

BASE_SNAPSHOT = hull_tests.snapshot


def change(text, tag, index, value, pred=lambda r: True):
    lines = text.splitlines(); token = f'OFFRAMPMOTION_{tag} '
    for i, line in enumerate(lines):
        if token not in line: continue
        prefix, tail = line.split(token, 1); row = tail.split()
        if not pred(row): continue
        row[index] = str(value); lines[i] = prefix+token+' '.join(row)
        return '\n'.join(lines)+'\n'
    raise AssertionError('Motion counterfactual did not ACT')


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

    def test_explicit_fixture_profile_and_case_schema(self):
        self.assertEqual(len(PARAMS), 41)
        self.assertEqual(PARAMS['fixrampbugs'], 2)
        for c in range(len(LABELS)):
            brushes, seed = authored(c)
            self.assertEqual(len(seed), 12)
            self.assertEqual(len(brushes), 2 if c in (5, 7) else 1)
            self.assertEqual(len(brushes[0]['planes']), 7 if c == 2 else 6)
            self.assertEqual(step_count(c), 32 if c < 6 else (96 if c == 6 else MAX_STEPS))
        self.assertEqual(authored(7)[0][1]['mins'], [-32, -128, 50])
        self.assertEqual(authored(7)[0][1]['maxs'], [32, 128, 128])


def controls(text):
    lines = text.splitlines()
    def first(tag): return next(l for l in lines if f'OFFRAMPMOTION_{tag}' in l)
    tags = ('BEGIN', 'SOURCE', 'PARAM', 'CASE', 'BRUSH', 'PLANE', 'SEED', 'TICK', 'ORACLE', 'CASE_END', 'END', 'COMPLETE')
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
        ('ceiling-wrong-clear-hull', 'TICK', 21, 45, lambda r: r[0] == '7' and r[1] == '191')):
        bad.append((label, change(text, tag, index, value, pred)))
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
    print(f'{len(bad)+3} ACTED native motion controls, zero failed; eight trajectory/posture actors/queries/bindings PASS')


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
