#!/usr/bin/env python3
"""Focused fixture-format controls; synthetic bytes are NOT native coverage."""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import sys
import unittest

import p690spritefixture as f

OUTPUT = None


class FixtureTests(unittest.TestCase):
    def test_sprite_single_rgba_frame(self):
        data = f.sprite_bytes()
        header = struct.unpack_from('<4siifiiifi', data)
        self.assertEqual(header, (b'IDSP', 32, 2, 46., 64, 64, 1, 0., 0))
        self.assertEqual(struct.unpack_from('<5i', data, 36), (0, -32, 32, 64, 64))
        self.assertEqual(len(data), 36 + 20 + 64 * 64 * 4)
        self.assertEqual(data[56:], bytes((0, 255, 0, 128)) * 4096)

    def test_bsp_directory_geometry_and_actor(self):
        data = f.bsp_bytes()
        self.assertEqual(struct.unpack_from('<i', data)[0], 29)
        lumps, end = [], 124
        for i in range(15):
            offset, size = struct.unpack_from('<2i', data, 4 + 8 * i)
            self.assertEqual(offset, end)
            self.assertGreaterEqual(size, 0)
            end += size
            self.assertLessEqual(end, len(data))
            lumps.append(data[offset:end])
        self.assertEqual(end, len(data))
        self.assertEqual(lumps[0].count(b'"classname" "prop_dynamic"'), 1)
        self.assertIn(('"model" "' + f.SPRITE + '"').encode(), lumps[0])
        self.assertIn(b'"origin" "272 0 64"', lumps[0])
        self.assertNotIn(b'"env_sprite"', lumps[0])
        self.assertEqual(len(lumps[3]), 12 * 12)
        self.assertEqual(len(lumps[7]), 3 * 20)
        self.assertEqual(len(lumps[14]), 64)
        for i in range(3):
            plane, side, first, count, tex = struct.unpack_from('<Hhihh', lumps[7], i * 20)
            self.assertEqual((plane, side, first, count, tex), (i, 0, i * 4, 4, i))
        self.assertEqual(struct.unpack_from('<2h', lumps[5], 4), (-2, -2))
        self.assertEqual(struct.pack('<3H', 0, 1, 2), lumps[11])

    def test_shader_alpha_and_determinism(self):
        shader = f.shader_bytes()
        self.assertEqual(shader.count(b'blendFunc src_alpha one_minus_src_alpha'), 2)
        self.assertEqual(shader.count(b'alphaGen const 0.5'), 2)
        self.assertNotIn(b'program ', shader)
        for emit in (f.bsp_bytes, f.sprite_bytes, f.shader_bytes):
            self.assertEqual(emit(), emit())

    def test_manifest_and_collision_no_overwrite(self):
        root = OUTPUT / 'fixture'
        manifest = f.generate(root)
        self.assertEqual(manifest, json.loads((root / 'fixture.json').read_text()))
        before = {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob('*') if p.is_file()}
        self.assertEqual(len(manifest['files']), 3)
        for relative, entry in manifest['files'].items():
            data = before[relative]
            self.assertEqual(len(data), entry['size'])
            self.assertEqual(hashlib.sha256(data).hexdigest(), entry['sha256'])
        with self.assertRaises(FileExistsError):
            f.generate(root)
        after = {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob('*') if p.is_file()}
        self.assertEqual(before, after)


def main():
    global OUTPUT
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True, help='NEW operator-owned directory')
    args = parser.parse_args()
    try:
        args.output.mkdir(exist_ok=False)
    except OSError as exc:
        parser.exit(1, f'Test output refused: {exc}\n')
    OUTPUT = args.output
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(FixtureTests))
    return 0 if result.wasSuccessful() else 1


if __name__ == '__main__':
    sys.exit(main())
