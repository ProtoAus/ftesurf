#!/usr/bin/env python3
"""P1286: bake a map's sky mask for the snow event.

For every cell column of the map, the top of the highest solid brush that is not sky: a flake below it
is under a roof (glsl/ftesurf_snow.glsl hides it). The world's brushes are those in model 0's leaves
(lumps 5, 10, 17); a brush entity's are stored round (0,0,0), so only func_brush and func_illusionary
(static, unturned) are read, moved to their origin; triggers and movers never are. Each is clipped
against each column at the cell's centre. Sky brushes (a side flagged SURF_SKY/SKY2D or named
toolsskybox*), brushes with no visible side (all tools/ except toolsblack, or nodraw: clips, invisible
walls) and non-solid contents (clips, water) do not stop snow. Props and displacements are not read: a
flake under a displaced terrain is behind it anyway, and one under a prop roof is the known gap.

Writes <gamedir>/gfx/snowmask/<map>.txt ("snowmask 1 <map> x0 y0 cell width height z0 zrange") and
<gamedir>/gfx/snowmask/<map>.png (gfx/ since P1293; height in 16 bits: r high byte, g low). cl_snow.qc reads both.

  python tools/snowmask.py --map surf_christmas [--bsp PATH] [--cell 32] [--gamedir ftesurf]
"""
import argparse
import lzma
import os
import re
import struct
import sys
from pathlib import Path

import numpy as np

MAPDIRS = [r"C:\Program Files (x86)\Steam\steamapps\common\Momentum Mod Playtest\momentum\maps",
           r"C:\Program Files (x86)\Steam\steamapps\common\Counter-Strike Source\cstrike\maps"]
CONTENTS_SOLID, CONTENTS_WINDOW = 0x1, 0x2
SURF_SKY2D, SURF_SKY, SURF_NODRAW = 0x2, 0x4, 0x80


class Bsp:
    def __init__(self, path):
        self.d = open(path, "rb").read()
        if self.d[:4] != b"VBSP":
            raise SystemExit("%s: not a Source BSP" % path)

    def lump_version(self, i):
        return struct.unpack_from('<i', self.d, 8 + 16 * i + 8)[0]

    def lump(self, i):
        o, n = struct.unpack_from("<ii", self.d, 8 + 16 * i)
        b = self.d[o:o + n]
        if b[:4] == b"LZMA":
            size, csize = struct.unpack_from("<II", b, 4)
            dec = lzma.LZMADecompressor(lzma.FORMAT_RAW, filters=[
                lzma._decode_filter_properties(lzma.FILTER_LZMA1, b[12:17])])
            b = dec.decompress(b[17:17 + csize])[:size]
        return b


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--map", required=True)
    ap.add_argument("--bsp")
    ap.add_argument("--cell", type=float, default=32.0)
    ap.add_argument("--gamedir", default=str(Path(__file__).resolve().parent.parent / "ftesurf"))
    a = ap.parse_args()
    path = a.bsp or next((os.path.join(d, a.map + ".bsp") for d in MAPDIRS if os.path.isfile(os.path.join(d, a.map + ".bsp"))), None)
    if not path:
        raise SystemExit("%s.bsp not found in %s" % (a.map, MAPDIRS))
    bsp = Bsp(path)

    planes = np.frombuffer(bsp.lump(1), dtype=np.dtype([("n", "<f4", 3), ("d", "<f4"), ("t", "<i4")]))
    brushes = np.frombuffer(bsp.lump(18), dtype=np.dtype([("first", "<i4"), ("num", "<i4"), ("contents", "<i4")]))
    # Match native Strata v25 layouts (mod_vbsp.c), not guessed version strides.
    wide_sides = bsp.lump_version(19) == 1
    if bsp.lump_version(19) not in (0, 1):
        raise ValueError('unsupported brushside version')
    side_dtype = np.dtype({'names':['plane','texinfo','disp','bevel'],
        'formats':['<u4','<i4','<i4','u1'], 'offsets':[0,4,8,12], 'itemsize':16}) if wide_sides else np.dtype([('plane','<u2'),('texinfo','<i2'),('disp','<i2'),('bevel','<i2')])
    sides = np.frombuffer(bsp.lump(19), dtype=side_dtype)
    texinfo = bsp.lump(6)
    texdata = bsp.lump(2)
    strtab = struct.unpack_from("<%di" % (len(bsp.lump(44)) // 4), bsp.lump(44))
    strdata = bsp.lump(43)

    def texname(ti):
        td = struct.unpack_from("<i", texinfo, 72 * ti + 68)[0]
        o = strtab[struct.unpack_from("<i", texdata, 32 * td + 12)[0]]
        return strdata[o:strdata.index(b"\0", o)].decode("latin-1").lower()

    def texflags(ti):
        return struct.unpack_from("<i", texinfo, 72 * ti + 64)[0]

    def visible(t):
        n = texname(t)
        return not (texflags(t) & SURF_NODRAW) and (not n.startswith("tools/") or "black" in n)

    models = bsp.lump(14)
    nodes = bsp.lump(5)
    leafs = bsp.lump(10)
    if bsp.lump_version(17) not in (0, 1) or bsp.lump_version(5) not in (0, 1) or bsp.lump_version(10) not in (0, 1, 2):
        raise ValueError('unsupported collision tree version')
    wide_refs = bsp.lump_version(17) == 1
    refsize, reffmt = (4, 'I') if wide_refs else (2, 'H')
    leafbrush = struct.unpack_from('<%d%s' % (len(bsp.lump(17)) // refsize, reffmt), bsp.lump(17))
    nodesize = 48 if bsp.lump_version(5) == 1 else 32
    leafsize = 56 if bsp.lump_version(10) in (0, 2) else 32
    leafoffset, leaffmt = (44, '<II') if bsp.lump_version(10) == 2 else (24, '<HH')
    if len(nodes) % nodesize or len(leafs) % leafsize:
        raise ValueError('collision tree stride mismatch')

    def model_brushes(m):
        out, visited = set(), set()
        stack = [struct.unpack_from('<i', models, 48 * m + 36)[0]]
        while stack:
            n = stack.pop()
            if n < 0:
                leaf = -1 - n
                if leaf >= len(leafs) // leafsize:
                    raise ValueError('leaf index outside collision tree')
                f, c = struct.unpack_from(leaffmt, leafs, leafsize * leaf + leafoffset)
                if f + c > len(leafbrush):
                    raise ValueError('leaf brush range outside lump')
                out.update(leafbrush[f:f + c])
            else:
                if n in visited or n >= len(nodes) // nodesize:
                    raise ValueError('cyclic/out-of-range collision tree; refusing unbounded walk')
                visited.add(n)
                stack.extend(struct.unpack_from('<2i', nodes, nodesize * n + 4))
        if any(i >= len(brushes) for i in out):
            raise ValueError('brush reference outside lump')
        return out

    work = [(b, (0.0, 0.0, 0.0)) for b in sorted(model_brushes(0))]
    for blk in re.findall(r"\{[^{}]*\}", bsp.lump(0).decode("latin-1", "replace")):
        kv = dict(re.findall(r'"([^"]+)"\s+"([^"]*)"', blk))
        if kv.get("classname") in ("func_brush", "func_illusionary") and kv.get("model", "").startswith("*"):
            ang = [float(v) for v in kv.get("angles", "0 0 0").split()[:3]]
            if any(ang):
                continue
            org = tuple(float(v) for v in kv.get("origin", "0 0 0").split()[:3])
            work += [(b, org) for b in sorted(model_brushes(int(kv["model"][1:])))]

    wmin = np.array(struct.unpack_from("<3f", models, 0))
    wmax = np.array(struct.unpack_from("<3f", models, 12))
    cell = a.cell
    x0, y0 = float(np.floor(wmin[0])), float(np.floor(wmin[1]))
    w = int(np.ceil((wmax[0] - x0) / cell)) + 1
    h = int(np.ceil((wmax[1] - y0) / cell)) + 1
    # Powers of two: a 1001x987 mask reached the shader resampled, and the lookup drifted ~2% (hundreds of
    # units across a map) off the roofs. Cells past the map stay at z0 (no roof).
    w, h = 1 << int(np.ceil(np.log2(w))), 1 << int(np.ceil(np.log2(h)))
    z0 = float(np.floor(wmin[2])) - 1.0
    zr = float(np.ceil(wmax[2])) + 1.0 - z0
    top = np.full((h, w), z0, dtype=np.float64)

    used = sky = tool = 0
    for bi, org in work:
        b = brushes[bi]
        if not (b["contents"] & (CONTENTS_SOLID | CONTENTS_WINDOW)):
            continue
        ss = sides[b["first"]:b["first"] + b["num"]]
        tis = [int(s["texinfo"]) for s in ss if s["texinfo"] >= 0]
        if any(texflags(t) & (SURF_SKY | SURF_SKY2D) or texname(t).startswith("tools/toolsskybox") for t in tis):
            sky += 1
            continue
        if not any(visible(t) for t in tis):
            tool += 1
            continue
        pl = planes[ss["plane"]]
        n = pl["n"].astype(np.float64)
        d = pl["d"].astype(np.float64) + n @ np.array(org)     # a moved entity's planes
        mn, mx = np.full(3, -1e9), np.full(3, 1e9)
        for k in range(3):     # the axial bevels every brush carries give its box
            ax = np.abs(n[:, k]) > 0.9999
            if ax.any():
                mx[k] = min(mx[k], np.min(np.where(n[ax, k] > 0, d[ax], 1e9)))
                mn[k] = max(mn[k], np.max(np.where(n[ax, k] < 0, -d[ax], -1e9)))
        if np.any(mn < -1e8) or np.any(mx > 1e8):
            continue
        ix0, ix1 = int(np.floor((mn[0] - x0) / cell)), int(np.ceil((mx[0] - x0) / cell))
        iy0, iy1 = int(np.floor((mn[1] - y0) / cell)), int(np.ceil((mx[1] - y0) / cell))
        ix0, iy0, ix1, iy1 = max(ix0, 0), max(iy0, 0), min(ix1, w - 1), min(iy1, h - 1)
        if ix1 < ix0 or iy1 < iy0:
            continue
        X, Y = np.meshgrid(x0 + (np.arange(ix0, ix1 + 1) + 0.5) * cell, y0 + (np.arange(iy0, iy1 + 1) + 0.5) * cell)
        zt = np.full(X.shape, 1e9); zb = np.full(X.shape, -1e9); inside = np.ones(X.shape, bool)
        for (nx, ny, nz), dd in zip(n, d):
            r = dd - nx * X - ny * Y
            if nz > 1e-6:
                zt = np.minimum(zt, r / nz)
            elif nz < -1e-6:
                zb = np.maximum(zb, r / nz)
            else:
                inside &= r >= -0.01
        ok = inside & (zt > zb) & (zt < 1e8)
        if ok.any():
            sub = top[iy0:iy1 + 1, ix0:ix1 + 1]
            np.maximum(sub, np.where(ok, zt, z0), out=sub)
            used += 1

    gd = Path(a.gamedir)
    if not sky:     # nothing is under the sky: no mask, so it snows everywhere (cl_snow.qc, as r_snow_indoor 1)
        for f in (gd / "gfx/snowmask" / (a.map + ".png"), gd / "gfx/snowmask" / (a.map + ".txt")):
            if f.exists():
                f.unlink()
        print("snowmask %s: no sky brushes, no mask written (snow falls everywhere)" % a.map)
        return
    q = np.clip(np.round((top - z0) / zr * 65535.0), 0, 65535).astype(np.uint16)
    img = np.zeros((h, w, 3), np.uint8)
    img[..., 0] = q >> 8
    img[..., 1] = q & 255
    from PIL import Image
    (gd / "gfx/snowmask").mkdir(parents=True, exist_ok=True)
    Image.fromarray(img, "RGB").save(gd / "gfx/snowmask" / (a.map + ".png"))   # row 0 = y0
    (gd / "gfx/snowmask" / (a.map + ".txt")).write_text(
        "snowmask 1 %s %g %g %g %d %d %g %g\n" % (a.map, x0, y0, cell, w, h, z0, zr), encoding="ascii", newline="\n")
    print("snowmask %s: %dx%d cells of %g, %d of %d brushes stop snow (%d sky, %d invisible skipped), from %s"
          % (a.map, w, h, cell, used, len(work), sky, tool, path))


if __name__ == "__main__":
    main()
