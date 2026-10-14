#!/usr/bin/env python3
"""Emit two self-contained rotated-inline-brush fixtures into a NEW directory.

No engine, launcher, install writes, downloads or BSP compiler. Native staging
and restoration are separate operator steps; see p690brushfixture.md.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import struct

MAPS = {0: 'mv17_brush_yaw0', 45: 'mv17_brush_yaw45'}
SHADER = 'scripts/mv17-brush.shader'
CAMERA = (0, 0, 0, 0, 0, 0)
pack = struct.pack


def bsp_bytes(yaw: int) -> bytes:
    """BSP29: three world quads, one local-space func_wall quad in model *1."""
    if yaw not in MAPS:
        raise ValueError('fixture yaw must be 0 or 45')
    background = [(600, -2048, -2048), (600, -2048, 2048),
                  (600, 2048, 2048), (600, 2048, -2048)]
    red = [(256, -32, 0), (256, -32, 128), (256, 32, 128), (256, 32, 0)]
    blue = [(64, -64, 0), (64, -64, 128), (512, 384, 128), (512, 384, 0)]
    green = [(0, -32, -32), (0, -32, 32), (0, 32, 32), (0, 32, -32)]
    h = 2 ** -.5
    planes = b''.join(pack('<4fi', *normal, dist, kind) for normal, dist, kind in
        [((-1., 0., 0.), -600., 3), ((-1., 0., 0.), -256., 3),
         ((-h, h, 0.), -128. * h, 3), ((1., 0., 0.), 0., 0),
         ((-1., 0., 0.), 0., 3)])
    vertices = b''.join(pack('<3f', *v) for v in background + red + blue + green)
    edges = pack('<2H', 0, 0) + b''.join(pack('<2H', q * 4 + i, q * 4 + (i + 1) % 4)
        for q in range(4) for i in range(4))
    surfedges = b''.join(pack('<i', i) for i in range(1, 17))
    names = ('mv17_black', 'mv17_red', 'mv17_blue', 'mv17_green')
    miptex = [pack('<16s6I', name.encode(), 16, 16, 40, 296, 360, 376) +
              bytes([224]) * (256 + 64 + 16 + 4) for name in names]
    starts, at = [], 20
    for tex in miptex:
        starts.append(at)
        at += len(tex)
    textures = pack('<5i', 4, *starts) + b''.join(miptex)
    texinfo = b''.join(pack('<8f2i', 0, 1, 0, 0, 0, 0, 1, 0, i, 0) for i in range(4))
    faces = b''.join(pack('<Hhihh4Bi', plane, 0, i * 4, 4, i, 255, 255, 255, 255, -1)
                     for i, plane in enumerate((0, 1, 2, 4)))
    nodes = (pack('<i2h6h2H', 3, -2, -2, -4096, -4096, -4096, 4096, 4096, 4096, 0, 3) +
             pack('<i2h6h2H', 4, -3, -3, -1, -32, -32, 1, 32, 32, 3, 1))
    clipnodes = pack('<i2h', 3, -1, -1) + pack('<i2h', 4, -1, -1)

    def leaf(contents: int, first: int, count: int) -> bytes:
        return pack('<ii6h2H4B', contents, -1, -4096, -4096, -4096,
                    4096, 4096, 4096, first, count, 0, 0, 0, 0)

    leaves = leaf(-2, 0, 0) + leaf(-1, 0, 3) + leaf(-1, 3, 1)
    marks = pack('<4H', 0, 1, 2, 3)
    models = (pack('<9f7i', -4096, -4096, -4096, 4096, 4096, 4096,
                   0, 0, 0, 0, 0, 0, 0, 1, 0, 3) +
              pack('<9f7i', -1, -32, -32, 1, 32, 32,
                   0, 0, 0, 1, 1, 1, 1, 1, 3, 1))
    entities = ('{\n"classname" "worldspawn"\n"message" "mv17 brush overlap"\n}\n'
        '{\n"classname" "info_player_start"\n"origin" "0 0 0"\n"angle" "0"\n}\n'
        '{\n"classname" "func_wall"\n"model" "*1"\n"targetname" "mv17_pane"\n'
        '"origin" "272 0 64"\n"angles" "0 ' + str(yaw) + ' 0"\n}\n')
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
    for name, color, alpha in [('mv17_black', '0 0 0', None), ('mv17_red', '1 0 0', .5),
                               ('mv17_blue', '0 0 1', .5), ('mv17_green', '0 1 0', .5)]:
        blend = '' if alpha is None else '  alphaGen const 0.5\n  blendFunc src_alpha one_minus_src_alpha\n'
        shaders.append(name + '\n{\n cull disable\n {\n  map $whiteimage\n'
                       '  rgbGen const ( ' + color + ' )\n' + blend + ' }\n}\n')
    return ''.join(shaders).encode()


def generate(output: Path) -> dict:
    output.mkdir(exist_ok=False)
    payloads = {'maps/' + name + '.bsp': bsp_bytes(yaw) for yaw, name in MAPS.items()}
    payloads[SHADER] = shader_bytes()
    files = {}
    for relative, data in payloads.items():
        path = output / relative
        path.parent.mkdir(exist_ok=True)
        path.write_bytes(data)
        files[relative] = {'size': len(data), 'sha256': hashlib.sha256(data).hexdigest()}
    manifest = {'schema': 1, 'maps': {str(k): v for k, v in MAPS.items()}, 'camera': list(CAMERA),
                'actor': {'classname': 'func_wall', 'model': '*1', 'origin': [272, 0, 64]},
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
