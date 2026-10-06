"""Synthetic controls: absence, coverage, partial decode and stale cfgs differ."""
import collections
import io
from pathlib import Path
import struct
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import zipfile

import particlecoverage as audit


def bsp(path, effects=(), pcfs=None):
    entities = ''.join('{\n"classname" "info_particle_system"\n'
                       '"effect_name" "%s"\n"start_active" "1"\n}\n' % e
                       for e in effects).encode()
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, 'w') as pak:
        for name, value in (pcfs or {}).items():
            pak.writestr(name, value)
    header = bytearray(1036)
    struct.pack_into('<4si', header, 0, b'VBSP', 20)
    struct.pack_into('<2i', header, 8, len(header), len(entities))
    data = archive.getvalue() if pcfs else b''
    struct.pack_into('<2i', header, 8+40*16, len(header)+len(entities), len(data))
    path.write_bytes(header+entities+data)


def parse(data):
    if data == b'bad':
        raise audit.dmx.DmxError('unsupported encoding')
    return SimpleNamespace(format='pcf', elements=[SimpleNamespace(name=data.decode())],
                           root={'particleSystemDefinitions': [0]})


def bake(data, mapname, unknown):
    unknown['fixture operator'] += 1
    return ['r_part fixture\n{\n}'], [{'name': data.decode()}], []


class CoverageTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.path = self.root/'subject.bsp'
        self.index = self.root/'index.txt'
        self.index.write_text('# current index\n')
        self.patches = [patch.object(audit.dmx, 'parse', side_effect=parse),
                        patch.object(audit.pcf, 'bake', side_effect=bake)]
        for p in self.patches:
            p.start()
            self.addCleanup(p.stop)
        self.addCleanup(self.tmp.cleanup)

    def run_map(self, baked=()):
        return audit.audit_map(self.path, set(baked), self.root)

    def test_no_particle_entities_does_not_require_cfg(self):
        bsp(self.path)
        self.assertIsNone(self.run_map())

    def test_no_embedded_library_is_not_claimed_translatable(self):
        bsp(self.path, ['shared_effect'])
        row = self.run_map()
        self.assertEqual(row['unbaked_effects'], ['shared_effect'])
        self.assertEqual(row['translatable_effects'], [])
        self.assertEqual(row['entities'], 1)

    def test_two_libraries_are_unioned_not_overwritten(self):
        bsp(self.path, ['first', 'second'], {'particles/a.pcf': b'first',
                                           'particles/b.pcf': b'second'})
        row = self.run_map(['first'])
        self.assertEqual(row['referenced_translatable_effects'], ['first', 'second'])
        self.assertEqual(row['unbaked_effects'], ['second'])
        self.assertEqual(row['unsupported_operators']['fixture operator'], 2)
        self.assertIsNone(row['cfg_matches_current_translator'])

    def test_bad_library_keeps_map_and_other_library_visible(self):
        bsp(self.path, ['first', 'second'], {'particles/a.pcf': b'first',
                                           'particles/b.pcf': b'bad'})
        report = audit.census(self.root, self.index, self.root)
        self.assertEqual(report['summary']['maps_with_particle_entities'], 1)
        self.assertEqual(report['summary']['particle_entities'], 2)
        self.assertEqual(report['summary']['errors'], 1)
        self.assertEqual(report['maps'][0]['translatable_effects'], ['first'])
        self.assertIn('unsupported encoding', report['errors'][0]['error'])

    def test_index_children_do_not_cover_entity_effect(self):
        fields = ['psys', 'subject', 'parent'] + ['0']*14 + ['-']
        child = ['psys', 'subject', 'child'] + ['0']*14 + ['parent']
        self.index.write_text('particles subject 2\n'+' '.join(fields)+'\n'+' '.join(child)+'\n')
        self.assertEqual(audit.baked_index(self.index)['subject'], {'parent'})

    def test_old_index_is_explicit_error(self):
        self.index.write_text('psys subject effect 16 0 0 0 32 1 1024\n')
        with self.assertRaisesRegex(ValueError, '18-column'):
            audit.baked_index(self.index)

    def test_round_trip_detects_changed_cfg(self):
        bsp(self.path, ['first'], {'particles/a.pcf': b'first'})
        blocks, _, _ = bake(b'first', 'subject', collections.Counter())
        header = audit.pcf.HEADER % dict(map='subject', src='a.pcf', n=1, total=1)
        cfg = self.root/'subject.cfg'
        cfg.write_text(header+'\n'+'\n\n'.join(blocks)+'\n')
        self.assertTrue(self.run_map(['first'])['cfg_matches_current_translator'])
        cfg.write_text(cfg.read_text()+'// drift\n')
        self.assertFalse(self.run_map(['first'])['cfg_matches_current_translator'])

    def test_cli_errors_return_incomplete_status(self):
        report = dict(summary={'errors': 1}, maps=[], errors=[{'error': 'fixture'}])
        with patch.object(audit, 'census', return_value=report), \
                patch.object(audit.sys, 'argv', ['particlecoverage.py']), \
                patch('sys.stdout', new_callable=io.StringIO) as output:
            self.assertEqual(audit.main(), 2)
            self.assertIn('INCOMPLETE', output.getvalue())

    def test_invalid_bsp_not_silent_success(self):
        self.path.write_bytes(b'not a BSP')
        report = audit.census(self.root, self.index, self.root)
        self.assertEqual(report['summary']['maps_scanned'], 1)
        self.assertEqual(report['summary']['errors'], 1)
        self.assertEqual(report['maps'], [])


if __name__ == '__main__':
    unittest.main()
