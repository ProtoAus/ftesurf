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
        if type_ == 8:
            return bytes(v)
        if type_ == 10:
            return struct.pack('<3f', *v)
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
        self.put('particles/bad.pcf', library('bad').replace(b'binary 2', b'binary 6'))
        report = plan(self.content(), ['good'])
        self.assertEqual(report['status'], 'incomplete')
        self.assertEqual(len(report['systems']), 1)
        self.assertIn('version 6', report['errors'][0]['error'])
        # Patch 1002 reads 2-5: a version-2 body labelled 5 is misread and must still refuse
        self.put('particles/bad.pcf', library('bad').replace(b'binary 2', b'binary 5'))
        self.assertEqual(plan(self.content(), ['good'])['status'], 'incomplete')
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


class RopeTests(unittest.TestCase):
    # Patch 791: a render_rope system bakes to a `rope` index line, not an r_part block,
    # and one with an operator outside pcf.ROPE_OPS is refused rather than guessed.
    def system(self, extra=None):
        ops_ = [('DmeParticleOperator', 'r', {'functionName': (5, 'render_rope')}),
                ('DmeParticleOperator', 'e', {'functionName': (5, 'emit_continuously'), 'emission_rate': (3, 8.0)}),
                ('DmeParticleOperator', 'l', {'functionName': (5, 'Lifetime Random'),
                                              'lifetime_min': (3, 3.0), 'lifetime_max': (3, 3.0)})]
        attrs = {'max_particles': (2, 1000), 'radius': (3, 1500.0), 'material': (5, 'particle\\beam.vmt'),
                 'renderers': (15, [2]), 'emitters': (15, [3]), 'initializers': (15, [4])}
        if extra:
            ops_.append(('DmeParticleOperator', 'x', {'functionName': (5, extra)}))
            attrs['operators'] = (15, [5])
        return pcf_bytes([('DmElement', 'root', {'particleSystemDefinitions': (15, [1])}),
                          ('DmeParticleSystemDefinition', 'beam', attrs)] + ops_)

    def test_rope_bakes_to_an_index_line(self):
        import collections, pcf
        blocks, runtime, skipped = pcf.bake(self.system(), 'm', collections.Counter())
        self.assertEqual((blocks, skipped), ([], []))
        rope = runtime[0]['rope']
        self.assertEqual((runtime[0]['rate'], rope['life'], rope['width']), (8.0, 3.0, 750.0))
        self.assertEqual(rope['image'], 'particle/beam')

    def test_rope_with_an_unknown_operator_is_refused(self):
        import collections, pcf
        blocks, runtime, skipped = pcf.bake(self.system('Velocity Noise'), 'm', collections.Counter())
        self.assertEqual(runtime, [])
        self.assertIn('render_rope with Velocity Noise', skipped[0][1])

    def test_rope_line_is_25_words_and_a_timed_emitter_refuses(self):
        import collections, pcf
        blocks, runtime, skipped = pcf.bake(self.system(), 'm', collections.Counter())
        w = pcf.rope_line('m', runtime[0], 'par').split()
        self.assertEqual(len(w), 25)
        # The reader's argv positions (cl_emit.qc Emit_RopeNote): image 3, rate 5, life 6,
        # width 13, alpha 17, start/end alpha 18/19, parent 24.
        self.assertEqual((w[3], w[5], w[6], w[13], w[17], w[18], w[19], w[24]),
                         ('particle/beam', '8', '3', '750', '1', '1', '1', 'par'))
        timed = pcf_bytes([('DmElement', 'root', {'particleSystemDefinitions': (15, [1])}),
                           ('DmeParticleSystemDefinition', 'beam',
                            {'max_particles': (2, 10), 'renderers': (15, [2]), 'emitters': (15, [3])}),
                           ('DmeParticleOperator', 'r', {'functionName': (5, 'render_rope')}),
                           ('DmeParticleOperator', 'e', {'functionName': (5, 'emit_continuously'),
                                                         'emission_rate': (3, 8.0), 'emission_duration': (3, 2.0)})])
        blocks, runtime, skipped = pcf.bake(timed, 'm', collections.Counter())
        self.assertIn('timed emitter', skipped[0][1])


class ColourFadeTests(unittest.TestCase):
    # Patch 1012: Color Fade becomes rgbdelta over the longest life plus an explicit rgbdeltatime.
    def system(self, fade, initializers=()):
        ops_ = [('DmeParticleOperator', 'r', {'functionName': (5, 'render_animated_sprites')}),
                ('DmeParticleOperator', 'e', {'functionName': (5, 'emit_continuously'), 'emission_rate': (3, 10.0)}),
                ('DmeParticleOperator', 'l', {'functionName': (5, 'Lifetime Random'),
                                              'lifetime_min': (3, 1.0), 'lifetime_max': (3, 3.0)}),
                ('DmeParticleOperator', 'c', dict(fade, functionName=(5, 'Color Fade')))]
        ops_ += [('DmeParticleOperator', 'i%d' % n, a) for n, a in enumerate(initializers)]
        attrs = {'max_particles': (2, 100), 'material': (5, 'particle\\p.vmt'), 'color': (8, [255, 255, 255, 255]),
                 'renderers': (15, [2]), 'emitters': (15, [3]), 'operators': (15, [5]),
                 'initializers': (15, [4] + list(range(6, 6 + len(initializers))))}
        return pcf_bytes([('DmElement', 'root', {'particleSystemDefinitions': (15, [1])}),
                          ('DmeParticleSystemDefinition', 'spark', attrs)] + ops_)

    def lines(self, data):
        import collections, pcf
        unknown = collections.Counter()
        blocks, runtime, skipped = pcf.bake(data, 'm', unknown)
        self.assertEqual(skipped, [])
        return [l.strip() for l in blocks[0].splitlines()], unknown

    def test_fade_is_a_rate_over_the_longest_life(self):
        # white -> (100, 0, 255) by half of a 3 s life: 1.5 s, so -155/1.5 and -255/1.5 a second
        lines, unknown = self.lines(self.system({'color_fade': (8, [100, 0, 255, 255]), 'fade_end_time': (3, 0.5)}))
        self.assertIn('rgbdelta -103.3 -170 0', lines)
        self.assertIn('rgbdeltatime 1.5', lines)
        self.assertLess(lines.index('rgbdelta -103.3 -170 0'), lines.index('rgbdeltatime 1.5'))
        self.assertFalse([k for k in unknown if 'Color Fade' in k], unknown)

    def test_fade_starts_from_the_middle_of_a_colour_range(self):
        rand = {'functionName': (5, 'Color Random'), 'color1': (8, [0, 0, 0, 255]), 'color2': (8, [200, 100, 50, 255])}
        lines, _ = self.lines(self.system({'color_fade': (8, [100, 50, 25, 255])}, [rand]))
        self.assertIn('rgbrand 200 100 50', lines)
        # mean start (100, 50, 25) is the target: nothing changes, so no rgbdelta line
        self.assertFalse([l for l in lines if l.startswith('rgbdelta')], lines)

    def test_start_angle_is_sources_not_ftes_random(self):
        # bhop_ceaseless redbooster2: no Rotation Random, so upright; FTE's default start is random
        lines, _ = self.lines(self.system({'color_fade': (8, [255, 255, 255, 255])}))
        self.assertIn('rotationstart 45', lines)   # FTE's upright quad
        rot = {'functionName': (5, 'Rotation Random'), 'rotation_offset_min': (3, 10.0), 'rotation_offset_max': (3, 40.0)}
        lines, _ = self.lines(self.system({'color_fade': (8, [255, 255, 255, 255])}, [rot]))
        self.assertIn('rotationstart 55 85', lines)

    def test_a_later_start_starts_at_birth_and_ends_on_target(self):
        # drawn from birth, so spread over 0..fade_end_time: 255 over 3 s, not over the last 1.5
        lines, unknown = self.lines(self.system({'color_fade': (8, [0, 0, 0, 255]), 'fade_start_time': (3, 0.5)}))
        self.assertIn('rgbdeltatime 3', lines)
        self.assertIn('rgbdelta -85 -85 -85', lines)
        self.assertTrue([k for k in unknown if 'starts at birth' in k], unknown)


class OrbitTests(unittest.TestCase):
    # Patch 1017: Movement Rotate Particle Around Axis -> orbit, the shell placed by the engine.
    def system(self, orbit, sphere=True, velocity=None):
        ops_ = [('DmeParticleOperator', 'r', {'functionName': (5, 'render_animated_sprites')}),
                ('DmeParticleOperator', 'e', {'functionName': (5, 'emit_continuously'), 'emission_rate': (3, 15.0)}),
                ('DmeParticleOperator', 'o', dict(orbit, functionName=(5, 'Movement Rotate Particle Around Axis'))),
                ('DmeParticleOperator', 'l', {'functionName': (5, 'Lifetime Random'),
                                              'lifetime_min': (3, 3.0), 'lifetime_max': (3, 3.0)})]
        inits = [5]
        if sphere:   # bhop_ceaseless butterfly: shell 60..256
            ops_.append(('DmeParticleOperator', 'p', {'functionName': (5, 'Position Within Sphere Random'),
                                                      'distance_min': (3, 60.0), 'distance_max': (3, 256.0)}))
            inits.append(6)
        if velocity:
            ops_.append(('DmeParticleOperator', 'v', dict(velocity, functionName=(5, 'Velocity Random'))))
            inits.append(len(ops_) + 1)
        attrs = {'max_particles': (2, 100), 'material': (5, 'particle\\p.vmt'),
                 'renderers': (15, [2]), 'emitters': (15, [3]), 'operators': (15, [4]),
                 'initializers': (15, inits)}
        return pcf_bytes([('DmElement', 'root', {'particleSystemDefinitions': (15, [1])}),
                          ('DmeParticleSystemDefinition', 's', attrs)] + ops_)

    def bake(self, data):
        import collections, pcf
        unknown = collections.Counter()
        blocks, runtime, skipped = pcf.bake(data, 'm', unknown)
        self.assertEqual(skipped, [])
        return runtime[0], [l.strip() for l in blocks[0].splitlines()], unknown

    def test_butterfly_orbits_a_shell_the_engine_places(self):
        rt, lines, unknown = self.bake(self.system({'Rotation Rate': (3, 50.0)}))
        self.assertIn('orbit 50 0 0 1\t// Patch 1017: degrees a second about the axis', lines)
        self.assertIn('spawnmode shell 60 256 1 1 1\t// radius, bias x y z', lines)
        self.assertEqual(rt['shape'], [0] + [0.0] * 7)    # cl_emit.qc hands over the emitter's origin
        self.assertFalse([k for k in unknown if 'Rotate' in k], unknown)

    def test_absent_rate_and_axis_are_sources_defaults(self):
        _, lines, _ = self.bake(self.system({}))
        self.assertIn('orbit 180 0 0 1\t// Patch 1017: degrees a second about the axis', lines)

    def test_a_velocity_spread_keeps_spawnvel(self):
        # the engine's shell randomises spawnvel per axis as box mode does
        vel = {'speed_in_local_coordinate_system_min': (10, [-20.0, -20.0, -20.0]),
               'speed_in_local_coordinate_system_max': (10, [20.0, 20.0, 20.0])}
        _, lines, _ = self.bake(self.system({'Rotation Rate': (3, 50.0)}, velocity=vel))
        self.assertIn('spawnvel 20 20', lines)

    def test_a_zero_rate_is_no_orbit(self):
        rt, lines, _ = self.bake(self.system({'Rotation Rate': (3, 0.0)}))
        self.assertFalse([l for l in lines if l.startswith('orbit') or l.startswith('spawnmode')], lines)
        self.assertEqual(rt['shape'][0], 2)


class ShapeTests(unittest.TestCase):
    # Patch 1012: defaults the DMX does not store, and the spawn volume handed to cl_emit.qc.
    def system(self, emitter, initializer, extra=None):
        ops_ = [('DmeParticleOperator', 'r', {'functionName': (5, 'render_animated_sprites')}),
                ('DmeParticleOperator', 'e', dict(emitter, functionName=(5, 'emit_continuously'))),
                ('DmeParticleOperator', 'l', {'functionName': (5, 'Lifetime Random'),
                                              'lifetime_min': (3, 2.0), 'lifetime_max': (3, 2.0)}),
                ('DmeParticleOperator', 'p', initializer)]
        attrs = {'max_particles': (2, 10000), 'material': (5, 'particle\\p.vmt'),
                 'renderers': (15, [2]), 'emitters': (15, [3]), 'initializers': (15, [4, 5])}
        attrs.update(extra or {})
        return pcf_bytes([('DmElement', 'root', {'particleSystemDefinitions': (15, [1])}),
                          ('DmeParticleSystemDefinition', 's', attrs)] + ops_)

    def index(self, data):
        import collections, pcf
        blocks, runtime, skipped = pcf.bake(data, 'm', collections.Counter())
        self.assertEqual(skipped, [])
        return runtime[0], [l.strip() for l in blocks[0].splitlines()]

    def test_absent_rate_and_draw_distance_are_sources_defaults(self):
        box = {'functionName': (5, 'Position Within Box Random')}
        rt, _ = self.index(self.system({}, box))
        self.assertEqual((rt['rate'], rt['maxdist']), (100.0, 100000.0))
        rt, _ = self.index(self.system({'emission_rate': (3, 7.0)}, box, {'maximum draw distance': (3, 600.0)}))
        self.assertEqual((rt['rate'], rt['maxdist']), (7.0, 600.0))

    def test_a_long_box_goes_to_qc_whole(self):
        # bhop_ceaseless purpleboost5: 256 x 5056, which spawnorg baked as a 1138 square
        box = {'functionName': (5, 'Position Within Box Random'),
               'min': (10, [-128.0, -2528.0, 0.0]), 'max': (10, [128.0, 2528.0, 0.0])}
        rt, lines = self.index(self.system({'emission_rate': (3, 50.0)}, box))
        self.assertEqual(rt['shape'][:4], [1, 128.0, 2528.0, 0.0])
        self.assertIn('spawnorg 0\t\t\t// cl_emit.qc places it: the index\'s shape columns', lines)
        self.assertFalse([l for l in lines if l.startswith('spawnmode')], lines)

    def test_a_flattened_sphere_is_a_ring(self):
        # bhop_ceaseless spiral: distance 350..375, bias 1 1 0
        sph = {'functionName': (5, 'Position Within Sphere Random'), 'distance_min': (3, 350.0),
               'distance_max': (3, 375.0), 'distance_bias': (10, [1.0, 1.0, 0.0]), 'speed_min': (3, 10.0),
               'speed_max': (3, 30.0)}
        rt, lines = self.index(self.system({'emission_rate': (3, 50.0)}, sph))
        self.assertEqual(rt['shape'], [2, 350.0, 375.0, 0.0, 1.0, 1.0, 0.0, 20.0])
        self.assertFalse([l for l in lines if l.startswith('spawnvel')], lines)

    def test_an_absolute_bias_keeps_one_half(self):
        # bhop_ceaseless purpleboostcirclelong: bias 0 1 0 with distance_bias_absolute_value 0 1 0
        sph = {'functionName': (5, 'Position Within Sphere Random'), 'distance_max': (3, 100.0),
               'distance_bias': (10, [0.0, 1.0, 0.0]), 'distance_bias_absolute_value': (10, [0.0, 1.0, 0.0])}
        rt, _ = self.index(self.system({'emission_rate': (3, 50.0)}, sph))
        self.assertEqual(rt['shape'][4:7], [0.0, 1001.0, 0.0])

    def test_index_line_carries_the_shape_columns(self):
        box = {'functionName': (5, 'Position Within Box Random'),
               'min': (10, [-10.0, -20.0, 0.0]), 'max': (10, [10.0, 20.0, 0.0])}
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / 'm.pcf'
            src.write_bytes(self.system({'emission_rate': (3, 5.0)}, box))
            game = Path(tmp) / 'game'
            (game / 'data').mkdir(parents=True)
            (game / 'particles').mkdir()
            subprocess.run([sys.executable, '-B', str(Path(__file__).with_name('pcf.py')), '--pcf', str(src),
                            '--map', 'm', '--gamedir', str(game)], check=True, capture_output=True)
            rows = [l.split() for l in (game / 'data' / 'mapparticles.txt').read_text().splitlines()
                    if l.startswith('psys ')]
        self.assertEqual(len(rows[0]), 26)
        # cl_emit.qc reads argv 18-25: shape, half extents, bias, radial
        self.assertEqual(rows[0][18:22], ['1', '10', '20', '0'])


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
