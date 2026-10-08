#!/usr/bin/env python3
"""Reader refusals, original-text seam composition and optional acted controls."""
import argparse
import contextlib
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from offramp_buffer import parse as parse_buffer
from offramp_origin import CHECKS, compare, grade, parse
from offramp_origin_smoke import compose, instrument, plan
from test_offramp_buffer import fixture as buffer_fixture


def fixture():
    rows = ['OFFRAMPORIGIN_CHECK %i %s 1' % (i, name) for i, name in enumerate(CHECKS, 1)]
    rows.append(f'OFFRAMPORIGIN_SELFTEST {len(CHECKS)} 0')
    for line in buffer_fixture().splitlines():
        rows.append(line)
        if line.startswith('OFFRAMPBUF_CONTACT '):
            c = line.split()[1:]
            rows.append(f'OFFRAMPORIGIN_CONTACT {c[0]} {c[1]} 0 1 12 12 0 1 {c[3]} maps/unit.bsp')
    return '\n'.join(rows) + '\n'


def change(text, index, value):
    lines = text.splitlines()
    for i, line in enumerate(lines):
        token = 'OFFRAMPORIGIN_CONTACT '
        if token in line:
            prefix, row = line.split(token, 1)
            words = row.split()
            words[index] = str(value)
            lines[i] = prefix + token + ' '.join(words)
            return '\n'.join(lines) + '\n'
    raise AssertionError('Origin counterfactual did not ACT')


def controls(text):
    lines = text.splitlines()
    first = next(l for l in lines if 'OFFRAMPORIGIN_CONTACT ' in l)
    bad = [('no-origin', '\n'.join(l for l in lines if 'OFFRAMPORIGIN_' not in l)),
           ('missing-row', '\n'.join(l for l in lines if l != first)),
           ('duplicate-row', text + first + '\n'),
           ('unknown-tag', text + 'OFFRAMPORIGIN_UNKNOWN 1\n'),
           ('malformed-row', text + 'OFFRAMPORIGIN_CONTACT 1\n'),
           ('selftest-failure', text.replace(f'OFFRAMPORIGIN_SELFTEST {len(CHECKS)} 0',
                                           f'OFFRAMPORIGIN_SELFTEST {len(CHECKS)} 1')),
           ('missing-selftest', '\n'.join(l for l in lines if 'OFFRAMPORIGIN_SELFTEST' not in l)),
           ('duplicate-selftest', text + f'OFFRAMPORIGIN_SELFTEST {len(CHECKS)} 0\n'),
           ('failed-check', text.replace('leaf-competition 1', 'leaf-competition 0')),
           ('wrong-check', text.replace('leaf-competition', 'different-test')),
           ('missing-check', '\n'.join(l for l in lines if 'OFFRAMPORIGIN_CHECK 1 ' not in l))]
    for label, i, value in [('ordinal', 0, -1), ('tick', 1, -1), ('physent', 8, -1),
                            ('fractional-id', 4, 1.5), ('nonfinite-id', 4, 'nan'),
                            ('route', 2, 4), ('kind', 3, 4), ('negative-leaf', 4, -1),
                            ('rootleaf', 5, -1), ('direct-leaf-mismatch', 5, 99),
                            ('depth', 6, -1), ('depth-overflow', 6, 65),
                            ('contents', 7, 0), ('contents-overflow', 7, 2**32),
                            ('model', 9, '-'), ('unsafe-model', 9, 'bad\\name'),
                            ('unknown-stale-fields', 3, 0), ('portal-promoted-witness', 2, 3)]:
        bad.append((label, change(text, i, value)))
    return bad


class Tests(unittest.TestCase):
    def test_positive(self):
        r = grade(fixture(), 'unit')
        self.assertEqual(r['origin_gates'], 'PASS')
        self.assertEqual(r['origin_categories'], {'world-brush-origin': 10})
        self.assertEqual(r['physical_exit_acceptance'], 'NOT_TESTED')
        self.assertEqual(r['winning_leaf_geometry_acceptance'], 'NOT_TESTED')
        self.assertEqual(r['cached_recovery_portal_runtime_acceptance'], 'NOT_TESTED')

    def test_counterfactuals(self):
        for name, text in controls(fixture()):
            with self.subTest(name=name), self.assertRaises(AssertionError):
                grade(text, 'unit')

    def test_quiet_parity_and_changed_repeat(self):
        on = fixture()
        clean = '\n'.join(l for l in buffer_fixture().splitlines()
                          if 'OFFRAMPBUF_' not in l or 'OFFRAMPBUF_COMPLETE' in l)
        self.assertEqual(compare(clean, clean, on, on, 'unit')['repeat_origin_equality'], 'PASS')
        changed = change(change(on, 4, 13), 5, 13)
        self.assertEqual(grade(changed, 'unit')['origin_gates'], 'PASS')
        with self.assertRaisesRegex(AssertionError, 'repeated winning origin'):
            compare(clean, clean, on, changed, 'unit')
        with self.assertRaises(AssertionError):
            compare(clean + 'OFFRAMPORIGIN_SELFTEST 12 0\n', clean, on, on, 'unit')

    def test_unsupported_origins_abstain(self):
        for idx, val, expected in [(2, 2, 'synthetic-recovery-plane'),
                                  (6, 1, 'embedded-model-unsupported'),
                                  (3, 2, 'world-triangle-unresolved'),
                                  (3, 3, 'world-patch-unsupported'),
                                  (9, '*1', 'model-unsupported')]:
            with self.subTest(expected=expected):
                r = grade(change(fixture(), idx, val), 'unit')
                self.assertEqual(r['origin_categories'][expected], 1)
                self.assertEqual(r['physical_exit_acceptance'], 'NOT_TESTED')
        self.assertEqual(grade(change(fixture(), 2, 1), 'unit')['origin_routes'][1], 1)
        # An unknown collider with canonical empty fields is allowed to abstain,
        # provided other rows prove that winning provenance ACTED.
        text = fixture()
        for i, v in ((3, 0), (4, -1), (5, -1), (6, 0), (7, 0), (9, '-'), (2, 3)):
            text = change(text, i, v)
        self.assertEqual(grade(text, 'unit')['origin_categories']['portal-unsupported'], 1)

    def test_composition_original_spans(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / 'source'
            p.write_text('ABC def GHI')
            result = compose([(p, 'ABC', 'GHI'), (p, 'GHI', 'ABC')])
            self.assertEqual(result[p], 'GHI def ABC')
            self.assertEqual(p.read_text(), 'ABC def GHI')
            for edits in ([(p, 'ABC def', ''), (p, 'def', '')],
                          [(p, 'missing', '')], [(p, ' ', '')]):
                with self.assertRaises(RuntimeError):
                    compose(edits)
            self.assertEqual(p.read_text(), 'ABC def GHI')


def snapshot(engine):
    paths = [engine / 'engine/common' / n for n in
             ('com_bih.c', 'pmovetst.c', 'pm_source.c', 'offramp_buffer_native.inc',
              'offramp_origin_native.h', 'offramp_origin_selftest.inc')]
    paths.append(engine / 'engine/server/sv_ccmds.c')
    return {str(p): hashlib.sha256(p.read_bytes()).hexdigest() if p.exists() else None for p in paths}


def installer_controls(engine, primary):
    before = snapshot(engine)
    edits, src, calls = plan(engine)
    late = edits[-1]
    broken = edits[:-1] + [(late[0], 'DELIBERATELY_MISSING_LATE_ANCHOR', late[2])]
    def refuse(label, thunk):
        try:
            thunk()
        except RuntimeError:
            if snapshot(engine) != before:
                raise AssertionError(f'Installer modified files during {label} refusal')
            print('PASS installer refusal:', label)
        else:
            raise AssertionError(f'Installer accepted {label}')
    with patch('offramp_origin_smoke.plan', return_value=(broken, src, calls)):
        refuse('missing-late-anchor fault injection', lambda: instrument(engine))
    target = engine / 'engine/common/offramp_origin_native.h'
    target.write_text('retained untracked sentinel\n')
    sentinel = snapshot(engine)
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            try:
                instrument(engine)
            except RuntimeError:
                assert snapshot(engine) == sentinel
            else:
                raise AssertionError('Installer overwrote existing include')
    finally:
        target.unlink()
    assert snapshot(engine) == before
    print('PASS installer refusal: existing include')
    source = engine / 'engine/common/pm_source.c'
    original = source.read_bytes()
    try:
        source.write_bytes(original + b'\n/* owned dirty refusal fixture */\n')
        dirty = snapshot(engine)
        try:
            instrument(engine)
        except RuntimeError:
            assert snapshot(engine) == dirty
        else:
            raise AssertionError('Installer accepted tracked-dirty worktree')
    finally:
        source.write_bytes(original)
    assert snapshot(engine) == before
    print('PASS installer refusal: tracked dirty (fixture restored)')
    refuse('primary checkout', lambda: instrument(primary))
    instrument(engine)
    installed = snapshot(engine)
    assert installed != before and all(installed.values())
    try:
        instrument(engine)
    except RuntimeError:
        assert snapshot(engine) == installed
    else:
        raise AssertionError('Installer accepted repeat installation')
    print('PASS installer: fresh install ACTED; repeat refused unchanged')


def acted_controls(arms):
    a = json.loads(arms.read_text())
    text = Path(a['on']['log']).read_text(errors='replace')
    grade(text, a['on']['map'])
    bad = controls(text)
    for name, copy in bad:
        try:
            grade(copy, a['on']['map'])
        except AssertionError:
            continue
        raise AssertionError(f'Acted origin counterfactual accepted: {name}')
    compare(*(Path(a[n]['log']).read_text(errors='replace') for n in ('clean', 'off', 'on', 'repeat')),
            a['on']['map'])
    print(f'{len(bad)+1} acted origin reader controls, zero failed; four-arm parity PASS')


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--arms', type=Path)
    ap.add_argument('--installer-engine', type=Path)
    ap.add_argument('--primary-engine', type=Path)
    a = ap.parse_args()
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Tests))
    if not result.wasSuccessful():
        raise SystemExit(1)
    if a.installer_engine:
        if not a.primary_engine:
            ap.error('--installer-engine needs --primary-engine')
        installer_controls(a.installer_engine, a.primary_engine)
    if a.arms:
        acted_controls(a.arms)


if __name__ == '__main__':
    main()
