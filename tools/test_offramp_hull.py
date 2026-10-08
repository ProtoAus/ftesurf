#!/usr/bin/env python3
"""Hull schema/actual-point controls; no movement-trajectory acceptance."""
import argparse
import hashlib
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from offramp_hull import CAP, CHECKS, compare, grade, parse
from offramp_hull_smoke import instrument
from offramp_shape_smoke import prepare as shape_prepare
import test_offramp_shape as shape_tests

SHAPE_SNAPSHOT = shape_tests.snapshot


def fixture():
    base = shape_tests.fixture()
    rows = ['OFFRAMPHULL_CHECK %i %s 1' % (i, name) for i, name in enumerate(CHECKS, 1)]
    rows += [f'OFFRAMPHULL_SELFTEST {len(CHECKS)} 0', f'OFFRAMPHULL_BEGIN 1 {CAP}']
    hull = '-16 -16 0 16 16 62 0 0 0 0 0 0 62 45'
    for line in base.splitlines():
        if line.startswith('OFFRAMPBUF_TICK '):
            rows.append('OFFRAMPHULL_TICK '+line.split()[1]+' '+hull)
    for line in base.splitlines():
        if line.startswith('OFFRAMPBUF_CONTACT '):
            r = line.split()[1:]
            rows.append(f'OFFRAMPHULL_CONTACT {r[0]} {r[1]} '+hull)
    rows.append('OFFRAMPHULL_END 13 10')
    return base+'\n'.join(rows)+'\n'


def change(text, tag, index, value, pred=lambda r: True):
    lines = text.splitlines()
    token = f'OFFRAMPHULL_{tag} '
    for i, line in enumerate(lines):
        if token not in line:
            continue
        prefix, tail = line.split(token, 1)
        row = tail.split()
        if not pred(row):
            continue
        row[index] = str(value)
        lines[i] = prefix+token+' '.join(row)
        return '\n'.join(lines)+'\n'
    raise AssertionError('Hull counterfactual did not ACT')


def controls(text):
    lines = text.splitlines()
    def first(tag):
        return next(l for l in lines if f'OFFRAMPHULL_{tag} ' in l)
    bad = [(f'missing-{tag}', '\n'.join(l for l in lines if l != first(tag)))
           for tag in ('CHECK', 'SELFTEST', 'BEGIN', 'TICK', 'CONTACT', 'END')]
    bad += [(f'duplicate-{tag}', text+first(tag)+'\n')
            for tag in ('CHECK', 'SELFTEST', 'BEGIN', 'TICK', 'CONTACT', 'END')]
    bad += [('native-buffer-capacity-mismatch', text.replace('OFFRAMPBUF_BEGIN 1 32768', 'OFFRAMPBUF_BEGIN 1 32769')),
            ('unknown', text+'OFFRAMPHULL_UNKNOWN 1\n'), ('malformed', text+'OFFRAMPHULL_TICK 1\n'),
            ('failed-setup', text.replace('actual-nondefault-standing-hull 1', 'actual-nondefault-standing-hull 0')),
            ('failed-selftest', text.replace(f'OFFRAMPHULL_SELFTEST {len(CHECKS)} 0', f'OFFRAMPHULL_SELFTEST {len(CHECKS)} 1'))]
    for label, tag, index, value in [('version', 'BEGIN', 0, 2), ('capacity', 'BEGIN', 1, CAP+1),
                                    ('tick-ordinal', 'TICK', 0, -1), ('tick-ordinal-fraction', 'TICK', 0, .5),
                                    ('contact-ordinal', 'CONTACT', 0, -1), ('contact-tick', 'CONTACT', 1, -1),
                                    ('footer-ticks', 'END', 0, -1), ('footer-contacts', 'END', 1, -1)]:
        bad.append((label, change(text, tag, index, value)))
    for tag, offset in (('TICK', 1), ('CONTACT', 2)):
        for label, index, value in [('reversed', 0, 99999), ('zero-width', 0, 16), ('nonfinite', 2, 'nan'),
                                    ('out-of-float', 5, '1e100'), ('capsule-enum', 6, 2), ('pmtype-enum', 7, 9),
                                    ('fractional-pmtype', 7, .5), ('ducked-enum', 8, 2), ('ducking-enum', 9, 2),
                                    ('negative-timer', 10, -1), ('nonfinite-timer', 10, 'inf'),
                                    ('fractional-buttons', 11, .5), ('buttons-range', 11, 2**31),
                                    ('nonfinite-raw-standheight', 12, 'nan'), ('nonfinite-raw-duckheight', 13, 'inf')]:
            bad.append((f'{tag}-{label}', change(text, tag, offset+index, value)))
    bad += [('trace-bounds-disagree', change(text, 'CONTACT', 2, -17)),
            ('trace-capsule-disagree', change(text, 'CONTACT', 8, 1))]
    # A correctly shaped row in the wrong position must not bind by sorting.
    a, b = first('TICK'), first('CONTACT')
    bad.append(('reordered', text.replace(a, 'HULL_ROW_SWAP').replace(b, a).replace('HULL_ROW_SWAP', b)))
    return bad


def clean(text):
    return shape_tests.clean('\n'.join(l for l in text.splitlines() if 'OFFRAMPHULL_' not in l)+'\n')


class Tests(unittest.TestCase):
    def test_positive(self):
        r = grade(fixture(), 'unit')
        self.assertEqual(r['hull_capture_gates'], 'PASS')
        self.assertEqual(r['authored_hull_setup_checks'], len(CHECKS))
        self.assertEqual(r['hull_loss_statuses'], {'captured-world-brush-aabb-numeric-only': 1})
        self.assertEqual(r['physical_exit_acceptance'], 'NOT_TESTED')
        self.assertEqual(r['authored_movement_trajectory_acceptance'], 'NOT_TESTED')
        d = r['losses'][0]['winning_brush_snapshot']['numeric_halfspaces']
        self.assertNotIn('hull_mins', d)  # No previous-contact hull for every point.
        self.assertEqual(d['points']['raw_loss_tick_end']['captured_hull']['maxs'], [16, 16, 62])

    def test_counterfactuals(self):
        for name, text in controls(fixture()):
            with self.subTest(name=name), self.assertRaises(AssertionError):
                grade(text, 'unit')

    def test_changed_loss_hull_is_used_not_previous_contact(self):
        text = fixture()
        at_loss = lambda r: r[0] == '6'
        text = change(change(text, 'TICK', 6, 45, at_loss), 'TICK', 9, 1, at_loss)
        r = grade(text, 'unit')
        d = r['losses'][0]['winning_brush_snapshot']['numeric_halfspaces']['points']
        self.assertEqual(d['accepted_sweep_point']['captured_hull']['maxs'][2], 62)
        self.assertEqual(d['previous_tick_end']['captured_hull']['maxs'][2], 62)
        self.assertEqual(d['raw_loss_tick_end']['captured_hull']['maxs'][2], 45)
        self.assertFalse(d['raw_loss_tick_end']['same_bounds_as_previous_contact'])
        # The negative-z face support MUST differ by 17 when the loss hull shrinks.
        original = grade(fixture(), 'unit')['losses'][0]['winning_brush_snapshot']['numeric_halfspaces']['points']
        self.assertEqual(d['raw_loss_tick_end']['side_gaps'][5]-original['raw_loss_tick_end']['side_gaps'][5], 17)

    def test_legal_capsule_or_non_normal_tick_abstains(self):
        for index, value, reason in ((7, 1, 'sample-capsule-hull-unsupported'), (8, 3, 'sample-movement-type-unsupported')):
            text = change(fixture(), 'TICK', index, value, lambda r: r[0] == '6')
            r = grade(text, 'unit')
            self.assertEqual(r['hull_loss_statuses'], {reason: 1})
            self.assertNotIn('numeric_halfspaces', r['losses'][0]['winning_brush_snapshot'])
            self.assertEqual(r['physical_exit_acceptance'], 'NOT_TESTED')

    def test_raw_heights_are_not_guessed_hulls(self):
        text = change(change(fixture(), 'TICK', 13, 0), 'TICK', 14, -1)
        self.assertEqual(grade(text, 'unit')['hull_capture_gates'], 'PASS')

    def test_quiet_and_repeat(self):
        text = fixture(); quiet = clean(text)
        self.assertEqual(compare(quiet, quiet, text, text, 'unit')['repeat_hull_equality'], 'PASS')
        changed = change(text, 'TICK', 11, 1)
        self.assertEqual(grade(changed, 'unit')['hull_capture_gates'], 'PASS')
        with self.assertRaisesRegex(AssertionError, 'repeated actual hull'):
            compare(quiet, quiet, text, changed, 'unit')
        with self.assertRaises(AssertionError):
            compare(quiet+'OFFRAMPHULL_BEGIN 1 32768\n', quiet, text, text, 'unit')


def snapshot(engine):
    result = SHAPE_SNAPSHOT(engine)
    for name in ('offramp_hull_native.inc', 'offramp_hull_selftest.inc'):
        p = engine/'engine/common'/name
        result[str(p)] = hashlib.sha256(p.read_bytes()).hexdigest() if p.exists() else None
    return result


def installer_controls(engine, primary):
    before = snapshot(engine)
    for name in ('offramp_hull_native.inc', 'offramp_hull_selftest.inc'):
        target = engine/'engine/common'/name
        target.write_text('owned untracked hull collision sentinel\n')
        sentinel = snapshot(engine)
        try:
            try: instrument(engine)
            except RuntimeError: assert snapshot(engine) == sentinel
            else: raise AssertionError('Hull installer overwrote include')
        finally: target.unlink()
        assert snapshot(engine) == before
        print('PASS hull include refusal:', name)
    prepared = shape_prepare(engine)
    path = engine/'engine/common/offramp_buffer_native.inc'
    prepared[path] = prepared[path].replace('OfframpShape_End', 'DELIBERATELY_MISSING_GENERATED_ANCHOR')
    with patch('offramp_hull_smoke.shape_prepare', return_value=prepared):
        try: instrument(engine)
        except RuntimeError: assert snapshot(engine) == before
        else: raise AssertionError('Hull installer accepted missing generated seam')
    print('PASS hull late generated-anchor refusal, no files changed')
    with patch('test_offramp_shape.snapshot', side_effect=snapshot), patch('test_offramp_shape.instrument', side_effect=instrument):
        shape_tests.installer_controls(engine, primary)


def acted_controls(arms):
    a = json.loads(arms.read_text())
    texts = {k: Path(v['log']).read_text(errors='replace') for k, v in a.items()}
    r = compare(*(texts[k] for k in ('clean', 'off', 'on', 'repeat')), a['on']['map'])
    assert r['hull_capture_gates'] == 'PASS'
    bad = controls(texts['on'])
    for name, text in bad:
        assert text != texts['on'], f'Counterfactual did not ACT: {name}'
        try: grade(text, a['on']['map'])
        except AssertionError: continue
        raise AssertionError(f'Acted hull counterfactual accepted: {name}')
    print(f'{len(bad)+1} acted hull reader controls, zero failed; four-arm hull equality PASS')


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--arms', type=Path)
    ap.add_argument('--installer-engine', type=Path)
    ap.add_argument('--primary-engine', type=Path)
    a = ap.parse_args()
    r = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Tests))
    if not r.wasSuccessful(): raise SystemExit(1)
    if a.installer_engine:
        if not a.primary_engine: ap.error('--installer-engine requires --primary-engine')
        installer_controls(a.installer_engine, a.primary_engine)
    if a.arms: acted_controls(a.arms)


if __name__ == '__main__':
    main()
