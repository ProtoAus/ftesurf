#!/usr/bin/env python3
"""Convert a small, licensed Kenney Holiday Kit selection into static Z-up IQMs.

No Blender/runtime OBJ parse and no downloads on play. Input is the ORIGINAL
CC0 Holiday Kit 2.0 zip (see winter-assets.md); unrelated archive entries are
never extracted. Geometry rotates Y-up/Z-forward to Quake Z-up/X-forward.
"""
import argparse
import hashlib
import math
import random
import struct
import zipfile
from pathlib import Path

ARCHIVE_SHA = 'fde4d514d7297388d98058e8933ff614e071886f7ce57f9aea4b00d7698dd769'
SELECTION = ('snowman', 'snowman-hat', 'tree-decorated-snow', 'tree-snow-a',
             'present-a-cube', 'present-b-rectangle')
MATERIAL = 'models/christmas/holiday'


def iqm(name, vertices, triangles, material=MATERIAL):
    """Static position/UV/normal mesh. No animation/pose or per-frame CPU work."""
    if not vertices or len(vertices) > 65535 or not triangles:
        raise ValueError('invalid static mesh size')
    text = ('\0' + name + '\0' + material + '\0').encode()
    text += b'\0' * (-len(text) % 4)
    off_mesh = 124 + len(text)
    off_va = off_mesh + 24
    off_pos = off_va + 60
    pos = b''.join(struct.pack('<3f', *p) for p, uv, n in vertices)
    uv = b''.join(struct.pack('<2f', *uv) for p, uv, n in vertices)
    norm = b''.join(struct.pack('<3f', *n) for p, uv, n in vertices)
    off_uv, off_norm = off_pos + len(pos), off_pos + len(pos) + len(uv)
    off_tri = off_norm + len(norm)
    tri = b''.join(struct.pack('<3I', *t) for t in triangles)
    size = off_tri + len(tri)
    header = b'INTERQUAKEMODEL\0' + struct.pack('<27I',
        2, size, 0, len(text), 124, 1, off_mesh, 3, len(vertices), off_va,
        len(triangles), off_tri, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0)
    mesh = struct.pack('<6I', 1, len(name.encode()) + 2, 0, len(vertices), 0, len(triangles))
    va = b''.join(struct.pack('<5I', kind, 0, 7, count, off)
                  for kind, count, off in [(0, 3, off_pos), (1, 2, off_uv), (2, 3, off_norm)])
    data = header + text + mesh + va + pos + uv + norm + tri
    assert len(data) == size
    return data


def convert_obj(text, scale=48):
    positions, texcoords, normals, vertices, triangles, dedup = [], [], [], [], [], {}

    def rotate(v, s=1):
        return (v[2] * s, v[0] * s, v[1] * s)

    for line in text.splitlines():
        fields = line.split()
        if not fields or fields[0].startswith('#'):
            continue
        if fields[0] == 'v':
            positions.append(rotate(tuple(map(float, fields[1:4])), scale))
        elif fields[0] == 'vt':
            u, v = map(float, fields[1:3]); texcoords.append((u, 1 - v))
        elif fields[0] == 'vn':
            normals.append(rotate(tuple(map(float, fields[1:4]))))
        elif fields[0] == 'f':
            face = []
            for token in fields[1:]:
                key = tuple(map(int, token.split('/')))
                if len(key) != 3 or min(key) < 1:
                    raise ValueError('selection needs explicit positive position/UV/normal indices')
                if key not in dedup:
                    dedup[key] = len(vertices)
                    p, uv, n = key
                    vertices.append((positions[p - 1], texcoords[uv - 1], normals[n - 1]))
                face.append(dedup[key])
            for i in range(1, len(face) - 1):
                triangles.append((face[0], face[i], face[i + 1]))
    if any(not math.isfinite(v) for p, uv, n in vertices for v in (*p, *uv, *n)):
        raise ValueError('nonfinite mesh')
    return vertices, triangles


def mist_field():
    rnd = random.Random(1302)
    vertices, triangles = [], []
    for i in range(12):
        p = tuple(rnd.uniform(-0.55, 0.55) for _ in range(3))
        first = len(vertices)
        vertices.extend((p, uv, (0, 0, 1)) for uv in [(0, 0), (2, 0), (0, 2)])
        triangles.append((first, first + 1, first + 2))
    # Bounds cover the GPU-opened puffs too; these two vertices are not indexed.
    vertices.extend((p, (0, 0), (0, 0, 1)) for p in [(-1, -1, -1), (1, 1, 1)])
    return iqm('mist', vertices, triangles, 'ftesurf_mist')


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--archive', type=Path, required=True)
    ap.add_argument('--out', type=Path, default=Path(__file__).resolve().parents[1] / 'ftesurf/models/christmas')
    a = ap.parse_args()
    if hashlib.sha256(a.archive.read_bytes()).hexdigest() != ARCHIVE_SHA:
        ap.error('not the inspected original Holiday Kit 2.0 archive')
    a.out.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(a.archive) as z:
        for name in SELECTION:
            v, t = convert_obj(z.read('Models/OBJ format/' + name + '.obj').decode())
            data = iqm(name, v, t)
            (a.out / (name + '.iqm')).write_bytes(data)
            print(f'{name}: {len(v)} vertices, {len(t)} triangles, {len(data)} bytes')
        (a.out / 'palette.png').write_bytes(z.read('Models/OBJ format/Textures/colormap.png'))
        # Preserve legal text, normalise archive-only trailing tabs/CRLF for Git.
        licence = z.read('License.txt').decode('utf-8')
        (a.out / 'LICENSE-Kenney.txt').write_bytes(('\n'.join(line.rstrip() for line in licence.splitlines()) + '\n').encode('utf-8'))
    (a.out / 'mist.iqm').write_bytes(mist_field())
    # Smooth tiling data texture, not a runtime noise generator or a raymarch.
    from PIL import Image, ImageFilter
    rnd = random.Random(1302)
    im = Image.new('L', (64, 64))
    im.putdata([rnd.randrange(48, 256) for _ in range(64 * 64)])
    # Repeated neighbours make the blur seamless at the texture's wrap boundary.
    tile = Image.new('L', (192, 192))
    for y in range(3):
        for x in range(3):
            tile.paste(im, (x * 64, y * 64))
    tile = tile.filter(ImageFilter.GaussianBlur(2)).crop((64, 64, 128, 128))
    tile.save(a.out / 'mist-noise.png')


if __name__ == '__main__':
    main()
