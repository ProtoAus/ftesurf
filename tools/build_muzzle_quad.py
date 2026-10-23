#!/usr/bin/env python3
"""Reproduce our tiny, untextured muzzle quad (no Valve data in this asset)."""
from pathlib import Path
import struct


def build():
    header = struct.pack('<4si64s9i', b'IDP3', 15, b'ftesurf-muzzle',
                         0, 1, 0, 1, 0, 108, 164, 164, 428)
    frame = struct.pack('<10f16s', 0, -1, -1, 0, 1, 1,
                        0, 0, 0, 1.415, b'flash')
    surface = struct.pack('<4s64s10i', b'IDP3', b'flash',
                          0, 1, 1, 4, 2, 108, 132, 200, 232, 264)
    triangles = struct.pack('<6i', 0, 1, 2, 0, 2, 3)
    shader = struct.pack('<64si', b'__white', 0)
    uv = struct.pack('<8f', 0, 1, 0, 0, 1, 0, 1, 1)
    vertices = b''.join(struct.pack('<3h2B', *v, 0, 64)
                        for v in [(0, -64, -64), (0, -64, 64),
                                  (0, 64, 64), (0, 64, -64)])
    data = header + frame + surface + triangles + shader + uv + vertices
    assert len(data) == 428
    return data


if __name__ == '__main__':
    path = Path(__file__).resolve().parents[1] / 'ftesurf/models/ftesurf/muzzle.md3'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(build())
    print(f'{path}: {path.stat().st_size} bytes (our geometry only)')
