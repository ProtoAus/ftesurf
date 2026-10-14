#!/usr/bin/env python3
"""Four focused BSP/actor/determinism controls; NOT native renderer coverage."""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import sys
import unittest

import p690brushfixture as f

OUTPUT = None


def lumps(data):
    result, end = [], 124
    for i in range(15):
        offset, size = struct.unpack_from('<2i', data, 4 + 8 * i)
        if offset != end or size < 0 or offset + size > len(data):
            raise ValueError('invalid BSP directory')
        end += size
        result.append(data[offset:end])
    if end != len(data):
        raise ValueError('trailing bytes')
    return result


class FixtureTests(unittest.TestCase):
    def test_inline_model_and_local_geometry(self):
        data = f.bsp_bytes(45)
        self.assertEqual(struct.unpack_from('<i', data)[0], 29)
        b = lumps(data)
        self.assertEqual(len(b[14]), 128)
        self.assertEqual(struct.unpack_from('<7i', b[14], 36), (0, 0, 0, 0, 1, 0, 3))
        self.assertEqual(struct.unpack_from('<7i', b[14], 100), (1, 1, 1, 1, 1, 3, 1))
        self.assertEqual(len(b[7]), 80)
        self.assertEqual(struct.unpack_from('<Hhihh', b[7], 60), (4, 0, 12, 4, 3))
        self.assertEqual(struct.unpack_from('<2h', b[5], 4), (-2, -2))
        self.assertEqual(struct.unpack_from('<2h', b[5], 28), (-3, -3))
        self.assertEqual(b[11], struct.pack('<4H', 0, 1, 2, 3))
        for i, expected in enumerate(((0, -32, -32), (0, -32, 32), (0, 32, 32), (0, 32, -32))):
            self.assertEqual(struct.unpack_from('<3f', b[3], (12 + i) * 12), expected)
        for i in range(4):
            self.assertEqual(struct.unpack_from('<2H', b[12], (13 + i) * 4),
                             (12 + i, 12 + (i + 1) % 4))

    def test_yaw_is_only_actor_difference(self):
        zero, rotated = lumps(f.bsp_bytes(0)), lumps(f.bsp_bytes(45))
        self.assertEqual(zero[1:], rotated[1:])
        self.assertEqual(zero[0].replace(b'"angles" "0 0 0"', b'"angles" "0 45 0"'), rotated[0])
        self.assertEqual(rotated[0].count(b'"classname" "func_wall"'), 1)
        for value in (b'"model" "*1"', b'"origin" "272 0 64"', b'"targetname" "mv17_pane"'):
            self.assertIn(value, rotated[0])
        for yaw in (-45, 90):
            with self.assertRaises(ValueError):
                f.bsp_bytes(yaw)

    def test_static_shader_and_determinism(self):
        shader = f.shader_bytes()
        self.assertEqual(shader.count(b'blendFunc src_alpha one_minus_src_alpha'), 3)
        self.assertEqual(shader.count(b'alphaGen const 0.5'), 3)
        self.assertIn(b'mv17_green', shader)
        self.assertNotIn(b'program ', shader)
        self.assertNotIn(b'deform', shader)
        self.assertEqual(f.bsp_bytes(45), f.bsp_bytes(45))
        self.assertEqual(f.shader_bytes(), f.shader_bytes())

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
