#!/usr/bin/env python3
"""P1286: write ftesurf/models/christmas/flakes.iqm, the snow event's flake field.

Every flake is one triangle whose three vertices share ONE position (its seed) and carry corners
(0,0) (2,0) (0,2); the vertex shader (glsl/ftesurf_snow.glsl) moves the seed, wraps it into a box round
the eye and opens the corners into a camera-facing triangle that holds the round flake. The CPU never
touches a flake. Seeds span -1024..1024 on every axis, so the model's bounds hold the eye (the entity
sits on it) and it is never frustum-culled.

IQM, not OBJ: Mod_LoadObjModel refuses a mesh past 65535 indices and dedupes vertices by a linear
search over every vertex so far (quadratic). An IQM mesh's index VALUES must fit 16 bits (render.h:
GLQUAKE + HAVE_LEGACY), so the field is GROUPS meshes of PER flakes. Deterministic: same bytes every run.
"""
import argparse
import random
import struct
from pathlib import Path

PER = 16000   # 48000 vertices a mesh
IQM_POSITION, IQM_TEXCOORD, IQM_FLOAT = 0, 1, 7


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--groups", type=int, default=4)
    ap.add_argument("--out", default=str(Path(__file__).resolve().parent.parent / "ftesurf/models/christmas/flakes.iqm"))
    a = ap.parse_args()
    rnd = random.Random(1286)
    nflk = a.groups * PER
    nv = nflk * 3

    text = b"\0"
    names = []
    for g in range(a.groups):
        names.append(len(text)); text += b"flakes%d\0" % g
    mat = len(text); text += b"ftesurf_snow\0"
    while len(text) % 4:
        text += b"\0"

    pos = bytearray(); tc = bytearray(); tri = bytearray()
    corners = (0.0, 0.0, 2.0, 0.0, 0.0, 2.0)
    for f in range(nflk):
        p = struct.pack("<3f", *(float(rnd.randint(-1024, 1024)) for _ in range(3)))
        pos += p * 3
        tc += struct.pack("<6f", *corners)
        g = f // PER
        base = (f - g * PER) * 3 + g * PER * 3   # absolute; the loader subtracts the mesh's first vertex
        tri += struct.pack("<3I", base, base + 1, base + 2)

    hdr_size = 16 + 27 * 4
    ofs_text = hdr_size
    ofs_meshes = ofs_text + len(text)
    ofs_va = ofs_meshes + a.groups * 24
    ofs_pos = ofs_va + 2 * 20
    ofs_tc = ofs_pos + len(pos)
    ofs_tri = ofs_tc + len(tc)
    size = ofs_tri + len(tri)

    meshes = b"".join(struct.pack("<6I", names[g], mat, g * PER * 3, PER * 3, g * PER, PER) for g in range(a.groups))
    va = struct.pack("<5I", IQM_POSITION, 0, IQM_FLOAT, 3, ofs_pos) + struct.pack("<5I", IQM_TEXCOORD, 0, IQM_FLOAT, 2, ofs_tc)
    hdr = b"INTERQUAKEMODEL\0" + struct.pack("<27I",
        2, size, 0,                     # version, filesize, flags
        len(text), ofs_text,
        a.groups, ofs_meshes,
        2, nv, ofs_va,
        nflk, ofs_tri, 0,               # triangles, no adjacency
        0, 0, 0, 0, 0, 0,               # joints, poses, anims
        0, 0, 0, 0,                     # frames, framechannels, ofs_frames, ofs_bounds
        0, 0, 0, 0)                     # comment, extensions
    data = hdr + text + meshes + va + bytes(pos) + bytes(tc) + bytes(tri)
    assert len(data) == size
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(data)
    print("wrote %s: %d flakes in %d meshes, %d bytes" % (out, nflk, a.groups, size))


if __name__ == "__main__":
    main()
