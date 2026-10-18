#!/usr/bin/env python3
"""Synthetic acting controls for the read-only particle resource planner.

No installed content needed; all fixtures live in a TemporaryDirectory. Optional
real-map/corpus checks belong beside this suite, never in a public asset bundle.
"""
import io
import json
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest
import zipfile
import zlib

import dmx
from pcf_resources import Libraries, plan
from sourceassets import (Asset, BspSource, Content, DirectorySource, ResourceError,
                          VpkSource, asset_path, resolve_vmt)
from vtfsheet import SheetError, read_sheet


def pcf_bytes(elements):
    """Minimal real binary-v2 serializer, explicit (type, value) attributes."""
    strings = sorted({e[0] for e in elements} | {k for e in elements for k in e[2]})
    ids = {s: i for i, s in enumerate(strings)}
    data = bytearray(b'<!-- dmx encoding binary 2 format pcf 1 -->\n\0')
    data += struct.pack('<H', len(strings))
    for s in strings:
        data += s.encode() + b'\0'
    data += struct.pack('<i', len(elements))
    for type_, name, _attrs in elements:
        data += struct.pack('<H', ids[type_]) + name.encode() + b'\0' + bytes(16)

    def value(type_, v):
        if type_ in (1, 2):
            return struct.pack('<i', v)
        if type_ == 3:
            return struct.pack('<f', v)
        if type_ == 4:
            return bytes([v])
        if type_ == 5:
            return v.encode() + b'\0'
        if type_ == 15:
            return struct.pack('<i', len(v)) + b''.join(value(1, i) for i in v)
        raise AssertionError(type_)

    for _type, _name, attrs in elements:
        data += struct.pack('<i', len(attrs))
        for key, (type_, v) in attrs.items():
            data += struct.pack('<HB', ids[key], type_) + value(type_, v)
    return bytes(data)


def library(name, child=None, child_defined=False, delay=.25, material=None):
    attrs = {'max_particles': (2, 12)}
    if material:
        attrs['material'] = (5, material)
    elements = [('DmElement', 'root', {'particleSystemDefinitions': (15, [1])}),
                ('DmeParticleSystemDefinition', name, attrs)]
    if child:
        attrs['children'] = (15, [2])
        elements += [('DmeParticleChild', '', {'child': (1, 3), 'delay': (3, delay)}),
                     ('DmeParticleSystemDefinition', child,
                      {'max_particles': (2, 7)} if child_defined else {})]
    return pcf_bytes(elements)


def sheet_fixture(version=1, minor=3, extra=b''):
    uvs = [(.1, .2, .3, .4), (.2, .3, .4, .5), (.3, .4, .5, .6), (.4, .5, .6, .7)]
    frame = struct.pack('<f', 1) + b''.join(struct.pack('<4f', *uv)
              for uv in uvs[:1 if version == 0 else 4])
    sheet = struct.pack('<II', version, 1) + struct.pack('<IIIf', 2, 0x81, 1, 1) + frame + extra
    header = bytearray(88)
    struct.pack_into('<4sIII', header, 0, b'VTF\0', 7, minor, 88)
    struct.pack_into('<I', header, 68, 1)
    struct.pack_into('<3sBI', header, 80, b'\x10\0\0', 0, 88)
    return bytes(header) + struct.pack('<I', len(sheet)) + sheet


def old_vtf():
    data = bytearray(64)
    struct.pack_into('<4sIII', data, 0, b'VTF\0', 7, 1, 64)
    return bytes(data)


def bsp_file(path, entries):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, 'w', compression=zipfile.ZIP_STORED) as archive:
        for name, data in entries:
            archive.writestr(name, data)
    pak = stream.getvalue()
    head = bytearray(8 + 64 * 16 + 4)
    struct.pack_into('<4sI', head, 0, b'VBSP', 20)
    struct.pack_into('<4i', head, 8 + 40 * 16, len(head), len(pak), 0, 0)
    path.write_bytes(bytes(head) + pak)


def vpk_file(path, data, version=1, split=False, preload=3):
    arch = 0 if split else 0x7fff
    tree = b'pcf\0particles\0sample\0'
    tree += struct.pack('<IHHIIH', zlib.crc32(data), preload, arch, 0, len(data) - preload, 0xffff)
    tree += data[:preload] + b'\0\0\0'
    head = struct.pack('<III', 0x55AA1234, version, len(tree))
    if version == 2:
        head += struct.pack('<4I', 0 if split else len(data) - preload, 0, 0, 0)
    path.write_bytes(head + tree + (b'' if split else data[preload:]))
    if split:
        path.with_name(path.name[:-8] + '_000.vpk').write_bytes(data[preload:])


class ResourceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def put(self, name, data):
        file = self.root / name
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_bytes(data)
        return file

    def content(self):
        return Content([DirectorySource(self.root)])

    def test_union_named_cross_library_child_and_delay(self):
        self.put('particles/a.pcf', library('parent', 'child'))
        self.put('particles/b.pcf', library('child'))
        report = plan(self.content(), ['parent', 'child'])
        self.assertEqual(report['status'], 'resolved')
        self.assertEqual(len(report['libraries']), 2)
        self.assertEqual({s['name'] for s in report['systems']}, {'parent', 'child'})
        self.assertEqual(report['edges'], [dict(parent='particles/a.pcf#1', child='particles/b.pcf#1', delay=.25)])

    def test_local_child_identity_not_rebound_to_same_name(self):
        self.put('particles/a.pcf', library('parent', 'child', True))
        self.put('particles/b.pcf', library('child'))
        report = plan(self.content(), ['parent'])
        self.assertEqual(report['status'], 'resolved')
        self.assertEqual(report['edges'][0]['child'], 'particles/a.pcf#3')

    def test_missing_child_rolls_back_root(self):
        self.put('particles/a.pcf', library('parent', 'missing'))
        self.put('particles/b.pcf', library('valid'))
        report = plan(self.content(), ['parent', 'valid'])
        self.assertEqual(report['status'], 'incomplete')
        self.assertIn('missing particle', report['errors'][0]['error'])
        self.assertEqual([s['name'] for s in report['systems']], ['valid'])
        self.assertEqual(report['edges'], [])

    def test_ambiguous_names_refused_even_identical(self):
        for file in ('a', 'b'):
            self.put('particles/' + file + '.pcf', library('same'))
        report = plan(self.content(), ['same'])
        self.assertEqual(report['status'], 'incomplete')
        self.assertEqual(len(report['ambiguous_names']['same']), 2)
        self.assertIn('ambiguous particle', report['errors'][0]['error'])

    def test_graph_cycle_and_negative_reference_refused(self):
        self.put('particles/a.pcf', library('a', 'b'))
        self.put('particles/b.pcf', library('b', 'a'))
        report = plan(self.content(), ['a'])
        self.assertIn('cyclic particle', report['errors'][0]['error'])
        libs = Libraries(Content([]))
        data = pcf_bytes([('DmElement', 'root', {'particleSystemDefinitions': (15, [-1])})])
        with self.assertRaisesRegex(ResourceError, 'invalid DMX'):
            libs.add(Asset('bad.pcf', 'fixture', data), dmx.parse(data))

    def test_private_name_lookup_and_invalid_delay(self):
        data = pcf_bytes([('DmElement', 'root', {'particleSystemDefinitions': (15, [1])}),
                          ('DmeParticleSystemDefinition', 'private', {'preventNameBasedLookup': (4, True)})])
        self.put('particles/private.pcf', data)
        report = plan(self.content(), ['private'])
        self.assertIn('missing particle', report['errors'][0]['error'])
        self.put('particles/delay.pcf', library('parent', 'child', True, delay=-1))
        self.assertIn('invalid child delay', plan(self.content(), ['parent'])['errors'][0]['error'])

    def test_corrupt_or_unsupported_library_is_not_silent_success(self):
        self.put('particles/good.pcf', library('good'))
        self.put('particles/bad.pcf', library('bad').replace(b'binary 2', b'binary 5'))
        report = plan(self.content(), ['good'])
        self.assertEqual(report['status'], 'incomplete')
        self.assertEqual(len(report['systems']), 1)
        self.assertIn('version 5', report['errors'][0]['error'])
        self.put('particles/bad.pcf', library('bad')[:-1])
        self.assertEqual(plan(self.content(), ['good'])['status'], 'incomplete')

    def test_nonfinite_library_rejected_before_publishing(self):
        data = pcf_bytes([('DmElement', 'root', {'particleSystemDefinitions': (15, [1])}),
                          ('DmeParticleSystemDefinition', 'bad', {'radius': (3, float('nan'))})])
        self.put('particles/bad.pcf', data)
        report = plan(self.content(), ['bad'])
        self.assertEqual(report['libraries'], [])
        self.assertIn('nonfinite PCF', report['errors'][0]['error'])

    def test_bsp_priority_all_libraries_and_case_normalization(self):
        self.put('particles/a.pcf', library('shared'))
        bsp = self.root / 'map.bsp'
        bsp_file(bsp, [('Particles/A.PCF', library('map_a')), ('particles/b.pcf', library('map_b'))])
        pak = BspSource(bsp)
        try:
            report = plan(Content([pak, DirectorySource(self.root)]), ['map_a', 'map_b'])
            self.assertEqual(report['status'], 'resolved')
            self.assertEqual(len(report['libraries']), 2)
            self.assertTrue(all(r['source'].endswith(':pak') for r in report['libraries']))
        finally:
            pak.close()

    def test_bsp_duplicate_and_crc_bad_member_fail(self):
        bsp = self.root / 'map.bsp'
        bsp_file(bsp, [('particles/a.pcf', library('a')), ('Particles/A.PCF', library('b'))])
        pak = BspSource(bsp)
        try:
            report = plan(Content([pak]), ['a'])
            self.assertEqual(report['status'], 'incomplete')
            self.assertIn('duplicate BSP', report['errors'][0]['error'])
        finally:
            pak.close()
        payload = library('a')
        bsp_file(bsp, [('particles/a.pcf', payload)])
        bsp.write_bytes(bsp.read_bytes().replace(payload, b'X' + payload[1:], 1))
        pak = BspSource(bsp)
        try:
            report = plan(Content([pak]), ['a'])
            self.assertEqual(report['status'], 'incomplete')
            self.assertIn('CRC', report['errors'][0]['error'])
        finally:
            pak.close()

    def test_unselected_bad_archive_entries_reported_not_map_blockers(self):
        bsp = self.root / 'map.bsp'
        bsp_file(bsp, [('particles/a.pcf', library('a')),
                       ('models/unused.mdl', b'a'), ('Models/Unused.MDL', b'b'),
                       ('C:/old/unused.vmt', b'x')])
        pak = BspSource(bsp)
        try:
            report = plan(Content([pak]), ['a'])
            self.assertEqual(report['status'], 'resolved')
            self.assertEqual(len(report['archive_diagnostics']), 2)
            with self.assertRaisesRegex(ResourceError, 'duplicate BSP'):
                Content([pak]).read('models/unused.mdl')
        finally:
            pak.close()

    def test_unnamed_definition_retained_for_local_children(self):
        self.put('particles/a.pcf', library('a', child='temporary', child_defined=True)
                 .replace(b'temporary\0', b'\0'))
        report = plan(self.content(), ['a'])
        self.assertEqual(report['status'], 'resolved')
        self.assertEqual(report['edges'][0]['child'], 'particles/a.pcf#3')
        self.assertIn('', [s['name'] for s in report['systems']])

    def test_vpk_inline_split_preload_crc_and_truncation(self):
        payload = library('a')
        for version in (1, 2):
            for split in (False, True):
                path = self.root / 'test_dir.vpk'
                vpk_file(path, payload, version, split)
                self.assertEqual(VpkSource(path).read('particles/sample.pcf').data, payload)
        path = self.root / 'test_dir.vpk'
        vpk_file(path, payload, preload=len(payload))
        self.assertEqual(VpkSource(path).read('particles/sample.pcf').data, payload)
        vpk_file(path, payload)
        path.write_bytes(path.read_bytes()[:-1] + b'X')
        with self.assertRaisesRegex(ResourceError, 'CRC'):
            VpkSource(path).read('particles/sample.pcf')
        vpk_file(path, payload)
        data = path.read_bytes()
        for prefix in range(12 + struct.unpack_from('<I', data, 8)[0]):
            path.write_bytes(data[:prefix])
            with self.assertRaises(ResourceError):
                VpkSource(path)

    def test_ambiguous_vpks_require_explicit_order(self):
        for name in ('a', 'b'):
            vpk_file(self.root / (name + '_dir.vpk'), library(name))
        report = plan(self.content(), ['a'])
        self.assertIn('ambiguous VPK', report['errors'][0]['error'])
        ordered = Content([VpkSource(self.root/'b_dir.vpk'), VpkSource(self.root/'a_dir.vpk')])
        self.assertEqual(plan(ordered, ['b'])['status'], 'resolved')

    def test_paths_cannot_escape(self):
        for path in ('../x', '/x', 'C:/x', 'a//b', 'a/./b', 'a\n'):
            with self.assertRaises(ResourceError):
                asset_path(path)
        self.assertEqual(asset_path('Materials\\Fire.VMT'), 'materials/fire.vmt')

    def test_patch_insert_replace_and_material_identity(self):
        self.put('materials/base.vmt', b'ParticleSphere { "$basetexture" "old" "$additive" "0" }')
        self.put('materials/child.vmt', b'Patch { include "base.vmt" insert { "$basetexture" "ignored" "$overbrightfactor" "2" } replace { "$basetexture" "new" "$additive" "1" } }')
        shader, params, origins = resolve_vmt(self.content(), 'child')
        self.assertEqual(shader, 'particlesphere')
        self.assertEqual(params['$basetexture'], 'new')
        self.assertEqual(params['$overbrightfactor'], '2')
        self.assertEqual(len(origins), 2)
        self.put('materials/insert.vmt', b'Patch { include "base.vmt" insert { "$basetexture" "new" } replace { "$absent" "not_inserted" } }')
        _, effective, _ = resolve_vmt(self.content(), 'insert')
        self.assertEqual(effective['$basetexture'], 'new')
        self.assertNotIn('$absent', effective)

    def test_vmt_cycle_conditional_duplicate_and_missing_texture(self):
        self.put('materials/a.vmt', b'Patch { include b }')
        self.put('materials/b.vmt', b'Patch { include a }')
        with self.assertRaisesRegex(ResourceError, 'cycle'):
            resolve_vmt(self.content(), 'a')
        for data in (b'SpriteCard { "$basetexture" "a" [$WIN32] }',
                     b'SpriteCard { "$basetexture" "a" "$basetexture" "b" }'):
            self.put('materials/a.vmt', data)
            with self.assertRaises(ResourceError):
                resolve_vmt(self.content(), 'a')
        self.put('materials/a.vmt', b'Sprite { "$spriteorigin" "[ 0.50 0.50 ]" "$basetexture" "v" }')
        self.assertEqual(resolve_vmt(self.content(), 'a')[1]['$spriteorigin'], '[ 0.50 0.50 ]')
        self.put('materials/a.vmt', b'SpriteCard { "$basetexture" "missing" }')
        self.put('particles/a.pcf', library('a', material='a'))
        report = plan(self.content(), ['a'])
        self.assertIn('missing asset', report['errors'][0]['error'])

    def test_bake_look_uses_basetexture_and_source_additive_rule(self):
        # Patch 787: pcf.py's r_part texture is an IMAGE name and its blend follows Source.
        from pcf import material_look
        cases = ((b'SpriteCard { "$basetexture" "effects/tesla_glow" "$additive" 1 }', 'effects/tesla_glow', 'adda'),
                 (b'UnlitGeneric { "$basetexture" "p\\glow_04" $translucent 1 $Additive 1 }', 'p/glow_04', 'adda'),
                 (b'UnlitGeneric { "$basetexture" "p/glow_03" $translucent 1 }', 'p/glow_03', 'blendalpha'),
                 (b'Sprite { "$basetexture" "laser01" "$spriterendermode" 5 }', 'laser01', 'adda'),
                 (b'Sprite { "$basetexture" "laser01" "$spriterendermode" 4 }', 'laser01', 'blendalpha'),
                 (b'SpriteCard { "$additive" "0" }', 'a', 'blendalpha'))
        for data, image, blend in cases:
            self.put('materials/a.vmt', data)
            self.assertEqual(material_look(self.content(), 'a'), (image, blend), data)

    def test_complete_material_provenance_and_no_stale_map_cache(self):
        self.put('particles/a.pcf', library('a', material='a'))
        self.put('materials/a.vmt', b'ParticleSphere { "$basetexture" "old" }')
        self.put('materials/old.vtf', old_vtf())
        first = plan(self.content(), ['a'])
        self.assertEqual(first['status'], 'resolved')
        mat = first['systems'][0]['material']
        self.assertEqual(mat['shader'], 'particlesphere')
        self.assertIsNone(mat['textures']['basetexture']['sheet'])
        self.assertEqual(len(mat['textures']['basetexture']['sha256']), 64)
        self.put('materials/a.vmt', b'SpriteCard { "$basetexture" "new" }')
        self.put('materials/new.vtf', old_vtf())
        second = plan(self.content(), ['a'])
        self.assertEqual(second['systems'][0]['material']['textures']['basetexture']['path'], 'materials/new.vtf')

    def test_sheet_primary_selection_and_missing_sequence(self):
        self.put('materials/a.vmt', b'SpriteCard { "$basetexture" "a" }')
        self.put('materials/a.vtf', sheet_fixture())
        attrs = {'material': (5, 'a'), 'sequence_number': (2, 2)}
        elements = [('DmElement', 'root', {'particleSystemDefinitions': (15, [1])}),
                    ('DmeParticleSystemDefinition', 'a', attrs)]
        self.put('particles/a.pcf', pcf_bytes(elements))
        report = plan(self.content(), ['a'])
        self.assertEqual(report['status'], 'resolved')
        self.assertEqual(report['systems'][0]['primary_sequences'], [2])
        attrs['sequence_number'] = (2, 3)
        self.put('particles/a.pcf', pcf_bytes(elements))
        self.assertIn('sequence absent', plan(self.content(), ['a'])['errors'][0]['error'])

    def test_cli_incomplete_exit_and_machine_report(self):
        output = self.root/'plan.json'
        run = subprocess.run([sys.executable, str(Path(__file__).with_name('pcf_resources.py')),
                              '--content', str(self.root), '--effect', 'missing', '--json', str(output)],
                             capture_output=True, text=True)
        self.assertEqual(run.returncode, 2, run.stderr)
        self.assertEqual(json.loads(output.read_text())['status'], 'incomplete')
        self.assertIn('INCOMPLETE', run.stdout)
        self.assertFalse((self.root/'particles').exists())


class SheetTests(unittest.TestCase):
    def test_versions_channels_flags_and_every_truncated_prefix(self):
        for version in (0, 1):
            for minor in (3, 6):
                data = sheet_fixture(version, minor)
                sheet = read_sheet(data)
                self.assertEqual(sheet['version'], version)
                seq = sheet['sequences'][2]
                self.assertEqual(seq['flags_raw'], 0x81)
                self.assertEqual(seq['duration'], 1)
                uv = seq['frames'][0]['uv']
                self.assertEqual(len(uv), 4)
                self.assertEqual(uv[0] == uv[3], version == 0)
                for prefix in range(len(data)):
                    with self.assertRaises(SheetError, msg=(version, minor, prefix)):
                        read_sheet(data[:prefix])
        self.assertIsNone(read_sheet(old_vtf()))

    def test_bad_counts_durations_uv_flags_and_eof(self):
        for offset, fmt, value in [(68, '<I', 33), (84, '<I', 4), (88, '<I', 99999),
                (92, '<I', 2), (96, '<I', 65), (100, '<I', 64), (108, '<I', 4097),
                (112, '<f', float('nan')), (112, '<f', 2), (116, '<f', -1),
                (120, '<f', float('inf')), (120, '<f', 1.1), (83, '<B', 2), (83, '<B', 4)]:
            bad = bytearray(sheet_fixture())
            struct.pack_into(fmt, bad, offset, value)
            with self.assertRaises(SheetError, msg=(offset, value)):
                read_sheet(bad)
        with self.assertRaisesRegex(SheetError, 'unconsumed'):
            read_sheet(sheet_fixture(extra=b'X'))

    def test_duplicate_resources_and_length_crossing_next_resource(self):
        original = sheet_fixture()
        for tag, second_offset in [(b'\x10\0\0', 100), (b'\x30\0\0', 96), (b'\x30\0\0', 104)]:
            header = bytearray(original[:88]) + bytes(8)
            struct.pack_into('<I', header, 12, 96)
            struct.pack_into('<I', header, 68, 2)
            struct.pack_into('<I', header, 84, 96)
            struct.pack_into('<3sBI', header, 88, tag, 0, second_offset)
            with self.assertRaises(SheetError):
                read_sheet(bytes(header) + original[88:])


if __name__ == '__main__':
    unittest.main(verbosity=2)
