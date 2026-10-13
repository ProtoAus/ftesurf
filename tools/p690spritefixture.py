#!/usr/bin/env python3
"""Emit a self-contained sprite/world-alpha fixture into a NEW directory.

No engine, game launcher, install writes, asset downloads or BSP compiler.
Runtime staging/cleanup belongs to the operator; see p690spritefixture.md.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import struct

MAP = 'mv16_sprite_overlap'
SPRITE = 'progs/mv16_green.spr'
CAMERA = (0, 0, 0, 0, 0, 0)
pack = struct.pack


def sprite_bytes() -> bytes:
    """Quake SPR32, one 64x64 billboard frame, unpremultiplied green/alpha128."""
    header = pack('<4siifiiifi', b'IDSP', 32, 2, 46.0, 64, 64, 1, 0.0, 0)
    frame = pack('<5i', 0, -32, 32, 64, 64)
    return header + frame + bytes((0, 255, 0, 128)) * (64 * 64)


def bsp_bytes() -> bytes:
    """BSP29 quads, single visible empty leaf, no lighting/collision assets."""
    background = [(600, -2048, -2048), (600, -2048, 2048),
                  (600, 2048, 2048), (600, 2048, -2048)]
    red = [(256, -32, 0), (256, -32, 128), (256, 32, 128), (256, 32, 0)]
    blue = [(64, -64, 0), (64, -64, 128), (512, 384, 128), (512, 384, 0)]
    h = 2 ** -.5
    planes = b''.join(pack('<4fi', *normal, dist, kind) for normal, dist, kind in
        [((-1., 0., 0.), -600., 3), ((-1., 0., 0.), -256., 3),
         ((-h, h, 0.), -128. * h, 3), ((1., 0., 0.), 0., 0)])
    vertices = b''.join(pack('<3f', *v) for v in background + red + blue)
    edges = pack('<2H', 0, 0) + b''.join(pack('<2H', q * 4 + i, q * 4 + (i + 1) % 4)
        for q in range(3) for i in range(4))
    surfedges = b''.join(pack('<i', i) for i in range(1, 13))
    names = ('mv16_black', 'mv16_red', 'mv16_blue')
    miptex = [pack('<16s6I', name.encode(), 16, 16, 40, 296, 360, 376) +
              bytes([224]) * (256 + 64 + 16 + 4) for name in names]
    starts, at = [], 16
    for tex in miptex:
        starts.append(at)
        at += len(tex)
    textures = pack('<4i', 3, *starts) + b''.join(miptex)
    texinfo = b''.join(pack('<8f2i', 0, 1, 0, 0, 0, 0, 1, 0, i, 0) for i in range(3))
    faces = b''.join(pack('<Hhihh4Bi', i, 0, i * 4, 4, i, 255, 255, 255, 255, -1)
                     for i in range(3))
    nodes = pack('<i2h6h2H', 3, -2, -2, -4096, -4096, -4096, 4096, 4096, 4096, 0, 3)
    clipnodes = pack('<i2h', 3, -1, -1)

    def leaf(contents: int, first: int, count: int) -> bytes:
        return pack('<ii6h2H4B', contents, -1, -4096, -4096, -4096,
                    4096, 4096, 4096, first, count, 0, 0, 0, 0)

    leaves = leaf(-2, 0, 0) + leaf(-1, 0, 3)
    marks = pack('<3H', 0, 1, 2)
    models = pack('<9f7i', -4096, -4096, -4096, 4096, 4096, 4096,
                  0, 0, 0, 0, 0, 0, 0, 1, 0, 3)
    entities = ('{\n"classname" "worldspawn"\n"message" "mv16 sprite overlap"\n}\n'
        '{\n"classname" "info_player_start"\n"origin" "0 0 0"\n"angle" "0"\n}\n'
        '{\n"classname" "prop_dynamic"\n"model" "' + SPRITE + '"\n'
        '"origin" "272 0 64"\n"angles" "0 0 0"\n"modelscale" "1"\n"solid" "0"\n}\n')
    lumps = [entities.encode() + b'\0', planes, textures, vertices, b'', nodes,
             texinfo, faces, b'', clipnodes, leaves, marks, edges, surfedges, models]
    at, directory, body = 124, [], []
    for lump in lumps:
        directory.append(pack('<2i', at, len(lump)))
        body.append(lump)
        at += len(lump)
    return pack('<i', 29) + b''.join(directory + body)


def shader_bytes() -> bytes:
    shaders = []
    for name, color, alpha in [('mv16_black', '0 0 0', None),
                               ('mv16_red', '1 0 0', .5), ('mv16_blue', '0 0 1', .5)]:
        blend = '' if alpha is None else '  alphaGen const 0.5\n  blendFunc src_alpha one_minus_src_alpha\n'
        shaders.append(name + '\n{\n cull disable\n {\n  map $whiteimage\n'
                       '  rgbGen const ( ' + color + ' )\n' + blend + ' }\n}\n')
    return ''.join(shaders).encode()


def generate(output: Path) -> dict:
    # Refuse collisions before writing any payload or changing existing content.
    output.mkdir(exist_ok=False)
    payloads = {'maps/' + MAP + '.bsp': bsp_bytes(), SPRITE: sprite_bytes(),
                'scripts/mv16-sprite.shader': shader_bytes()}
    files = {}
    for relative, data in payloads.items():
        path = output / relative
        path.parent.mkdir(exist_ok=True)
        path.write_bytes(data)
        files[relative] = {'size': len(data), 'sha256': hashlib.sha256(data).hexdigest()}
    manifest = {'schema': 1, 'map': MAP, 'camera': list(CAMERA), 'sprite': SPRITE,
                'files': files, 'scope': 'fixture bytes only; no native acceptance'}
    (output / 'fixture.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True, help='NEW operator-owned directory')
    args = parser.parse_args()
    try:
        manifest = generate(args.output)
    except (OSError, ValueError) as exc:
        parser.exit(1, f'Fixture generation failed: {exc}\n')
    print(json.dumps(manifest, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
