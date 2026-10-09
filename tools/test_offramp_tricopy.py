#!/usr/bin/env python3
"""Copied-triangle schema/geometry units, optional actual native controls/refusals."""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re
import unittest
from unittest.mock import patch

from offramp_buffer import parse as buffer_parse
from offramp_motion import compare as motion_compare
from offramp_origin import integers, parse as origin_parse
import offramp_tricopy as tri
from offramp_tricopy_smoke import instrument, prepare
from offramp_motion_smoke import prepare as motion_prepare

NATIVE_ARMS = None
CONTACT = [0, 0, 0, 0, .4921875, 0, 0, 0, 1, 2, 2, 2, 2, 2, -2, -16, -16, 0, 16, 16, 62, 0, 0, 0]
ORIGIN = [0, 0, 0, 2, 0, 0, 0, 1, 0, '*authored_offramp_world']
VERTICES = [[0, 0, 0], [0, 10, 0], [10, 0, 0]]


def fixture(status=1):
    rows = [f'OFFRAMPTRICOPY_CHECK {i} {name} 1' for i, name in enumerate(tri.CHECKS, 1)]
    rows += [f'OFFRAMPTRICOPY_SELFTEST {len(tri.CHECKS)} 0', 'OFFRAMPTRICOPY_BEGIN 1 3',
             'OFFRAMPTRICOPY_SOURCE '+tri.source_digest()]
    data = [0, 0, status, 0, 1, 4, 0, 1, 2]+[x for v in VERTICES for x in v] if status == 1 else [0, 0, status]+[0]*15
    rows += ['OFFRAMPTRICOPY_CONTACT '+' '.join(map(str, data)),
             f'OFFRAMPTRICOPY_END 1 {int(status == 1)} {int(status == 2)}']
    return '\n'.join(rows)+'\n'


def change(text, tag, index, value, pred=lambda r: True):
    token = 'OFFRAMPTRICOPY_'+tag+' '
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if token not in line:
            continue
        prefix, tail = line.split(token, 1)
        row = tail.split()
        if pred(row):
            row[index] = str(value)
            lines[i] = prefix+token+' '.join(row)
            return '\n'.join(lines)+'\n'
    raise AssertionError('Triangle-copy counterfactual did not ACT')


class Units(unittest.TestCase):
    def test_complete_value_copy_schema(self):
        copy = tri.decode(fixture(), [CONTACT], [ORIGIN])[0]
        self.assertEqual(copy['vertices'], VERTICES)
        self.assertEqual(copy['indexes'], [0, 1, 2])
        self.assertEqual(copy['back_slab'], 4)
        self.assertNotIn('pointer', copy)

    def test_nontriangle_empty_payload(self):
        origin = ORIGIN[:]; origin[3] = 1
        copy = tri.decode(fixture(0), [CONTACT], [origin])[0]
        self.assertEqual(copy['status'], 0)
        self.assertEqual(copy['vertices'], [[0]*3 for _ in range(3)])
        with self.assertRaises(AssertionError): tri.decode(fixture(1), [CONTACT], [origin])

    def test_invalid_source_abstains_without_partial_data(self):
        copy = tri.decode(fixture(2), [CONTACT], [ORIGIN])[0]
        self.assertEqual(copy['status'], 2)
        with self.assertRaises(AssertionError): tri.contact_sweep(copy, CONTACT)
        for field in range(3, 18):
            with self.subTest(field=field), self.assertRaises(AssertionError):
                tri.decode(change(fixture(2), 'CONTACT', field, 1), [CONTACT], [ORIGIN])

    def test_unknown_and_malformed_rows_refuse(self):
        for extra in ('OFFRAMPTRICOPY_UNKNOWN 1', 'OFFRAMPTRICOPY_CONTACT 1'):
            with self.assertRaises(AssertionError): tri.parse(fixture()+extra+'\n')

    def test_numeric_and_binding_faults_refuse(self):
        for field, value in ((0, 1), (1, .5), (2, 3), (3, 99), (4, 2), (5, 5),
                             (6, -1), (6, .5), (6, 2**32), (9, 'nan'), (9, '1e100')):
            with self.subTest(field=field, value=value), self.assertRaises(AssertionError):
                tri.decode(change(fixture(), 'CONTACT', field, value), [CONTACT], [ORIGIN])
        with self.assertRaises(AssertionError):
            tri.decode(change(change(fixture(), 'CONTACT', 7, 0), 'CONTACT', 8, 0).replace('0 10 0 10 0 0', '0 0 0 0 0 0'), [CONTACT], [ORIGIN])

    def test_setup_envelope_and_counters_refuse(self):
        text = fixture(); lines = text.splitlines()
        for tag in tri.WIDTHS:
            line = next(l for l in lines if l.startswith('OFFRAMPTRICOPY_'+tag+' '))
            for changed in ('\n'.join(l for l in lines if l != line)+'\n', text+line+'\n'):
                with self.subTest(tag=tag), self.assertRaises(AssertionError): tri.decode(changed, [CONTACT], [ORIGIN])
        for tag, field, value in (('CHECK', 2, 0), ('SELFTEST', 1, 1), ('BEGIN', 0, 2), ('SOURCE', 0, '0'*64),
                                  ('END', 0, 2), ('END', 1, 0), ('END', 2, 1)):
            with self.assertRaises(AssertionError): tri.decode(change(text, tag, field, value), [CONTACT], [ORIGIN])

    def test_independent_copied_sweep_not_native_plane_or_tag_oracle(self):
        copy = tri.decode(fixture(), [CONTACT], [ORIGIN])[0]
        result = tri.contact_sweep(copy, CONTACT)
        self.assertEqual(result['independent_copied_triangle_sweep'], 'PASS')
        self.assertEqual(result['geometry_basis'], 'COPIED_WINNING_NATIVE_TRIANGLE')
        self.assertEqual(result['enter'], .5)
        self.assertEqual(result['expected_biased_fraction'], .4921875)

    def test_sweep_fraction_plane_hull_and_copy_faults_refuse(self):
        copy = tri.decode(fixture(), [CONTACT], [ORIGIN])[0]
        for field, value in ((4, .5), (5, .1), (6, .1), (20, 45), (21, 1)):
            row = CONTACT[:]; row[field] = value
            with self.assertRaises(AssertionError): tri.contact_sweep(copy, row)
        for field, value in (('status', 0), ('native_plane_tag', 1), ('native_bevels_applied', 0)):
            changed = deepcopy(copy); changed[field] = value
            with self.assertRaises(AssertionError): tri.contact_sweep(changed, CONTACT)

    def test_wrong_arity_missing_contact_or_origin_refuses(self):
        with self.assertRaises(AssertionError): tri.decode(fixture(), [], [])
        with self.assertRaises(AssertionError): tri.decode(fixture(), [CONTACT], [])
        with self.assertRaises(AssertionError): tri.decode(fixture(), [CONTACT, CONTACT], [ORIGIN, ORIGIN])


@unittest.skipUnless(NATIVE_ARMS, 'needs --native-arms fresh five-arm manifest')
class Native(unittest.TestCase):
    acted = 0

    @classmethod
    def setUpClass(cls):
        arms = json.loads(NATIVE_ARMS.read_text())
        cls.texts = [Path(arms[n]['log']).read_text(errors='replace') for n in ('nooracle', 'control', 'off', 'on', 'repeat')]
        cls.motion = motion_compare(*cls.texts)
        cls.result = tri.compare(*cls.texts)
        cls.blocks = re.findall(r'OFFRAMPMOTION_CASE [0-9]+ .*?(?=OFFRAMPMOTION_CASE_END [0-9]+ [0-9]+)', cls.texts[3], flags=re.S)

    def test_native_copy_count_binding_sweep_and_abstentions(self):
        self.assertEqual(self.result['copied_winning_triangle_binding'], 'PASS')
        self.assertEqual(self.result['copied_triangle_contacts'], 14)
        self.assertEqual(self.result['accepted_contact_rows'], 251)
        self.assertEqual(self.result['native_setup_checks_per_case'], 23)
        self.assertEqual(self.result['general_triangle_support'], 'ABSTAIN')
        self.assertTrue(all(c['accepted_sweep']['independent_copied_triangle_sweep'] == 'PASS'
                            for c in self.result['cases'][14]['contacts']))
        self.assertFalse(self.result['cases'][15]['contacts'])

    def test_every_actual_contact_has_exercised_binding_or_stale_copy_controls(self):
        full = empty = 0
        for block in self.blocks:
            buffer, _ = buffer_parse(block); raw, _ = origin_parse(block)
            origins = [integers(w[:9])+[w[9]] for w in raw['CONTACT']]
            copies = tri.decode(block, buffer['CONTACT'], origins)
            for copy in copies:
                pred = lambda r, ordinal=copy['ordinal']: r[0] == str(ordinal)
                faults = [(0, copy['ordinal']+1), (1, copy['tick']+.5), (2, 3), (9, 'nan')]
                if copy['status'] == 0:
                    faults += [(i, 1) for i in range(3, 18)]
                    empty += 1
                else:
                    full += 1
                    faults += [(3, 99), (4, 2), (5, 5), (6, -1), (6, .5), (6, 2**32)]
                for field, value in faults:
                    changed = change(block, 'CONTACT', field, value, pred)
                    with self.subTest(ordinal=copy['ordinal'], field=field), self.assertRaises(AssertionError):
                        tri.decode(changed, buffer['CONTACT'], origins)
                    Native.acted += 1
        self.assertEqual(full, 14)
        self.assertEqual(empty, 237)

    def test_actual_triangle_geometry_and_semantics_mutations_refuse(self):
        for copy in self.result['cases'][14]['contacts']:
            pred = lambda r, ordinal=copy['ordinal']: r[0] == str(ordinal) and r[2] == '1'
            for field, value in [(2, 0), (3, 1), (4, 0), (5, 3),
                                 *[(i, copy['indexes'][i-6]+3) for i in range(6, 9)],
                                 *[(i, copy['vertices'][(i-9)//3][(i-9)%3]+1) for i in range(9, 18)]]:
                # Select only the actual triangle CASE block; other cases reuse
                # local contact ordinals but status1 belongs only to case14.
                text = change(self.texts[3], 'CONTACT', field, value, pred)
                with self.assertRaises(AssertionError): tri.grade(text, self.motion)
                Native.acted += 1

    def test_every_accepted_triangle_sweep_has_fraction_plane_and_route_faults(self):
        buffer, _ = buffer_parse(self.blocks[14])
        for copy, contact in zip(self.result['cases'][14]['contacts'], buffer['CONTACT']):
            tri.contact_sweep(copy, contact)
            for field, value in ((4, .5), (5, contact[5]+.1), (6, contact[6]+.1), (20, 45), (21, 1)):
                row = contact[:]; row[field] = value
                with self.assertRaises(AssertionError): tri.contact_sweep(copy, row)
                Native.acted += 1

    def test_mirrored_copied_vertices_pass_old_parity_but_not_copy_binding(self):
        pred = lambda r: r[2] == '1'
        texts = [*self.texts[:3], *(change(t, 'CONTACT', 9, -255, pred) for t in self.texts[3:])]
        altered = motion_compare(*texts)
        self.assertEqual(altered['cases'], self.motion['cases'])
        with self.assertRaisesRegex(AssertionError, 'actual native leaf/index/wiring'):
            tri.compare(*texts)
        Native.acted += 1


def installer_controls(engine, primary=None):
    planned = prepare(engine)
    paths = list(planned)
    snapshot = lambda: {str(p): hashlib.sha256(p.read_bytes()).hexdigest() if p.exists() else None for p in paths}
    before = snapshot()
    for name in ('offramp_tricopy_types.h', 'offramp_tricopy_native.inc', 'offramp_tricopy_selftest.inc'):
        target = engine/'engine/common'/name
        assert not target.exists()
        target.write_text('owned triangle-copy include sentinel\n')
        sentinel = snapshot()
        try:
            try: instrument(engine)
            except RuntimeError: assert snapshot() == sentinel
            else: raise AssertionError('Triangle-copy installer overwrote include')
        finally:
            assert target.read_text() == 'owned triangle-copy include sentinel\n'
            target.unlink()
        assert snapshot() == before
        print('PASS triangle-copy include refusal:', name)
    for path, anchor in ((engine/'engine/common/offramp_origin_native.h', 'struct offramp_shape_s shape;'),
                         (engine/'engine/common/com_bih.c', '#endif\n\t}\n}\n\nstatic const q2mapsurface_t')):
        plan = motion_prepare(engine)
        assert anchor in plan[path]
        plan[path] = plan[path].replace(anchor, 'DELIBERATELY_MISSING_GENERATED_ANCHOR')
        with patch('offramp_tricopy_smoke.motion_prepare', return_value=plan):
            try: instrument(engine)
            except RuntimeError: assert snapshot() == before
            else: raise AssertionError('Triangle-copy installer accepted missing generated anchor')
        print('PASS triangle-copy late generated-anchor refusal:', path.name)
    bih = engine/'engine/common/com_bih.c'
    read = Path.read_text
    def changed_slab(path, *args, **kwargs):
        text = read(path, *args, **kwargs)
        return text.replace('planes[1].dist = -planes[0].dist + 4;', 'planes[1].dist = -planes[0].dist + 5;') if path == bih else text
    with patch.object(Path, 'read_text', changed_slab):
        try: instrument(engine)
        except RuntimeError: assert snapshot() == before
        else: raise AssertionError('Triangle-copy installer assumed drifted native slab')
    print('PASS triangle-copy native slab-drift refusal, all source/include bytes unchanged')
    original = bih.read_bytes()
    dirty = original+b'\n/* OWNED PRIVATE tracked-dirty refusal control */\n'
    bih.write_bytes(dirty)
    dirty_snapshot = snapshot()
    try:
        try: instrument(engine)
        except RuntimeError: assert snapshot() == dirty_snapshot
        else: raise AssertionError('Triangle-copy installer accepted tracked-dirty tree')
    finally:
        assert bih.read_bytes() == dirty, 'Do not overwrite a concurrent fixture edit'
        bih.write_bytes(original)
    assert snapshot() == before
    print('PASS triangle-copy actual tracked-dirty refusal; owned fixture restored EXACT')
    if primary:
        primary_paths = [primary/p.relative_to(engine) for p in paths]
        primary_snapshot = lambda: {str(p): hashlib.sha256(p.read_bytes()).hexdigest() if p.exists() else None for p in primary_paths}
        before_primary = primary_snapshot()
        try: instrument(primary)
        except RuntimeError: assert primary_snapshot() == before_primary
        else: raise AssertionError('Triangle-copy installer accepted owner primary checkout')
        print('PASS triangle-copy owner primary checkout refusal; source bytes unchanged')


if __name__ == '__main__':
    ap = argparse.ArgumentParser(add_help=False)
    ap.add_argument('--native-arms', type=Path)
    ap.add_argument('--installer-engine', type=Path)
    ap.add_argument('--primary-engine', type=Path)
    args, remaining = ap.parse_known_args()
    NATIVE_ARMS = args.native_arms
    Native.__unittest_skip__ = not bool(NATIVE_ARMS)
    program = unittest.main(argv=[__file__]+remaining, exit=False)
    if NATIVE_ARMS:
        print(f'{Native.acted} ACTED native triangle-copy refusal controls, {len(program.result.failures)+len(program.result.errors)} failed')
    if program.result.wasSuccessful() and args.installer_engine:
        installer_controls(args.installer_engine, args.primary_engine)
    raise SystemExit(not program.result.wasSuccessful())
