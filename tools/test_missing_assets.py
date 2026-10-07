#!/usr/bin/env python3
"""Dependency-free structure/ship controls for the missing-texture/ERROR assets."""
from pathlib import Path
import math
import struct
import unittest
import zlib

ROOT = Path(__file__).resolve().parents[1]


def png(data):
    data = bytes(data)
    if data[:8] != b'\x89PNG\r\n\x1a\n':
        raise ValueError('not PNG')
    pos, chunks = 8, {}
    while pos < len(data):
        if pos+12 > len(data):
            raise ValueError('truncated PNG chunk')
        size, = struct.unpack_from('>I', data, pos)
        tag = data[pos+4:pos+8]
        payload = data[pos+8:pos+8+size]
        if pos+12+size > len(data) or zlib.crc32(tag+payload) != struct.unpack_from('>I', data, pos+8+size)[0]:
            raise ValueError('PNG CRC/length')
        chunks[tag] = chunks.get(tag, b'')+payload
        pos += 12+size
    width, height = struct.unpack_from('>II', chunks[b'IHDR'])
    return width, height, chunks


def md3(data):
    if len(data) < 164:
        raise ValueError('truncated MD3')
    ident, version, _name, flags, nf, tags, ns, _skins, of, otags, offset, end = struct.unpack_from('<4si64s9i', data)
    if (ident, version, flags, nf, tags) != (b'IDP3', 15, 0, 1, 0):
        raise ValueError('unexpected MD3 header')
    if of != 108 or otags != 164 or offset != 164 or end != len(data) or ns != 6:
        raise ValueError('MD3 header offsets/surfaces')
    bounds = struct.unpack_from('<10f', data, of)
    if not all(math.isfinite(x) for x in bounds):
        raise ValueError('nonfinite bounds')
    surfaces = []
    for _ in range(ns):
        if offset+108 > len(data):
            raise ValueError('truncated surface header')
        ident, name, flags, nf, nskin, nv, nt, tri, shader, uv, xyz, size = struct.unpack_from('<4s64s10i', data, offset)
        if ident != b'IDP3' or flags or nf != 1 or nskin != 1 or not 0 < nv <= 4096 or not 0 < nt <= 8192:
            raise ValueError('surface header/limits')
        if (tri, shader, uv, xyz, size) != (108, 108+nt*12, 108+nt*12+68,
                                          108+nt*12+68+nv*8, 108+nt*12+68+nv*16):
            raise ValueError('surface offsets')
        if offset+size > len(data):
            raise ValueError('surface payload bounds')
        vertices = [struct.unpack_from('<3h', data, offset+xyz+i*8) for i in range(nv)]
        for i in range(nt):
            indices = struct.unpack_from('<3i', data, offset+tri+i*12)
            if any(not 0 <= n < nv for n in indices):
                raise ValueError('bad triangle reference')
            a, b, c = [vertices[n] for n in indices]
            u, v = [b[j]-a[j] for j in range(3)], [c[j]-a[j] for j in range(3)]
            cross = [u[1]*v[2]-u[2]*v[1], u[2]*v[0]-u[0]*v[2], u[0]*v[1]-u[1]*v[0]]
            if not any(cross):
                raise ValueError('quantized degenerate triangle')
        coords = [struct.unpack_from('<2f', data, offset+uv+i*8) for i in range(nv)]
        for vertex in vertices:
            if any(not bounds[j]-.016 <= vertex[j]/64 <= bounds[j+3]+.016 for j in range(3)):
                raise ValueError('vertex exceeds model bounds')
        surfaces.append(dict(name=name.split(b'\0')[0].decode(), vertices=nv, triangles=nt,
                             shader=data[offset+shader:offset+shader+64].split(b'\0')[0].decode(),
                             uv=coords))
        offset += size
    if offset != end:
        raise ValueError('unconsumed MD3 bytes')
    return surfaces


class MissingAssets(unittest.TestCase):
    def setUp(self):
        self.data = (ROOT/'ftesurf/models/missing_error.md3').read_bytes()

    def test_md3_geometry_and_materials(self):
        surfaces = md3(self.data)
        self.assertEqual([s['name'] for s in surfaces], ['letters','extrusion','halo0','halo1','halo2','halo3'])
        self.assertEqual([s['shader'] for s in surfaces], ['missing_error_face','missing_error_side']+['missing_error_halo']*4)
        self.assertLess(sum(s['triangles'] for s in surfaces), 6500)
        for i, s in enumerate(surfaces):
            self.assertEqual(set(s['uv']), {((i+.5)/8, .5)})

    def test_truncated_model_never_accepted(self):
        for length in (0, 100, 163, len(self.data)-1):
            with self.assertRaises(ValueError):
                md3(self.data[:length])

    def test_header_and_triangle_mutations_fail(self):
        bad = bytearray(self.data)
        struct.pack_into('<i', bad, 100, 165)
        with self.assertRaisesRegex(ValueError, 'header offsets'):
            md3(bad)
        bad = bytearray(self.data)
        struct.pack_into('<i', bad, 164+108, 99999)
        with self.assertRaisesRegex(ValueError, 'triangle reference'):
            md3(bad)

    def test_owner_checker_exact_alias_and_resolution(self):
        owner = (ROOT/'ftesurf/gfx/env/missingtexture.png').read_bytes()
        alias = (ROOT/'ftesurf/textures/no_texture.png').read_bytes()
        self.assertEqual(owner, alias)
        self.assertEqual(png(owner)[:2], (64,64))

    def test_palette_is_constant_texel_red_ramp(self):
        width, height, chunks = png((ROOT/'ftesurf/gfx/env/missing_error_palette.png').read_bytes())
        self.assertEqual((width,height), (8,1))
        colors = zlib.decompress(chunks[b'IDAT'])
        self.assertEqual(colors[0], 0)
        rgb = [tuple(colors[1+i*3:4+i*3]) for i in range(8)]
        self.assertEqual(rgb[:2], [(255,3,2),(97,0,0)])
        self.assertEqual(rgb[2:6], [(82,0,0),(41,0,0),(20,0,0),(9,0,0)])

    def test_png_mutation_rejected(self):
        bad = bytearray((ROOT/'ftesurf/gfx/env/missing_error_palette.png').read_bytes())
        bad[-5] ^= 1
        with self.assertRaisesRegex(ValueError, 'PNG CRC'):
            png(bad)

    def test_shader_dependencies_and_unlit_backend(self):
        shader = (ROOT/'ftesurf/scripts/missing_assets.shader').read_text()
        for name in {s['shader'] for s in md3(self.data)}:
            self.assertIn(name+'\n{', shader)
        self.assertEqual(shader.count('program default2d'), 3)
        self.assertEqual(shader.count('clampmap gfx/env/missing_error_palette.png'), 3)
        self.assertIn('blendfunc add', shader)
        self.assertNotIn('rgbgen const', '\n'.join(s for s in shader.splitlines() if not s.startswith('//')))

    def test_exact_asset_ship_entries(self):
        release = (ROOT/'src/release/release.ps1').read_text()
        for name in ['ftesurf/textures/no_texture.png','ftesurf/gfx/env/missingtexture.png',
                     'ftesurf/gfx/env/missing_error_palette.png']:
            self.assertIn("'"+name+"'", release)
        for name in ['ftesurf/models','ftesurf/scripts']:
            self.assertIn("Path = '"+name+"'", release)


if __name__ == '__main__':
    unittest.main(verbosity=2)
