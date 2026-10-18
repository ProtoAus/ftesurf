#!/usr/bin/env python3
"""List the brushes of a Source BSP (v19-v21, and Strata's v25) near a player hull at a point.

  python tools/bspnear.py <map.bsp> x y z [--hull 16 62] [--within 4]

For each brush, d = n . (p + corner) - dist over its sides as compiled, where corner is the
hull corner deepest along -n; every d <= 0 means the hull overlaps the brush. A brush is
listed when its largest d is <= --within, sides sorted by d, with texture and bevel flag.
Use the full-precision normals it prints: at |x| ~ 15000 a normal rounded to 5 decimals
moves d by 0.08 (Patch 813). The engine also adds edge bevels the map lacks
(hl2_brushbevels 1), which are not listed here.
"""
import argparse, lzma, struct, sys


def lump(data, idx):
    off, ln, ver, fourcc = struct.unpack_from("<iiii", data, 8 + idx * 16)
    raw = data[off:off + ln]
    if raw[:4] == b"LZMA":
        actual, lsize = struct.unpack_from("<II", raw, 4)
        props = raw[12:17]
        alone = props + struct.pack("<Q", actual) + raw[17:17 + lsize]
        raw = lzma.decompress(alone, format=lzma.FORMAT_ALONE)
    return raw


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("bsp")
    ap.add_argument("x", type=float); ap.add_argument("y", type=float); ap.add_argument("z", type=float)
    ap.add_argument("--hull", type=float, nargs=2, default=[16, 62], metavar=("HALFW", "HEIGHT"))
    ap.add_argument("--within", type=float, default=4)
    a = ap.parse_args()
    data = open(a.bsp, "rb").read()
    assert data[:4] == b"VBSP", data[:4]
    ver = struct.unpack_from("<i", data, 4)[0]
    planes_raw = lump(data, 1)
    planes = [struct.unpack_from("<ffffi", planes_raw, i * 20) for i in range(len(planes_raw) // 20)]
    brushes_raw = lump(data, 18)
    brushes = [struct.unpack_from("<iii", brushes_raw, i * 12) for i in range(len(brushes_raw) // 12)]
    sides_raw = lump(data, 19)
    if struct.unpack_from("<i", data, 8 + 19 * 16 + 8)[0] >= 1:     # Strata v25: u32 plane, i32 texinfo, i32 disp, u8 bevel, u8 thin, pad
        sides = [struct.unpack_from("<IiiBB", sides_raw, i * 16) for i in range(len(sides_raw) // 16)]
    else:
        sides = [struct.unpack_from("<Hhhh", sides_raw, i * 8) for i in range(len(sides_raw) // 8)]
    texinfo_raw = lump(data, 6)
    texinfo_td = [struct.unpack_from("<i", texinfo_raw, i * 72 + 68)[0] for i in range(len(texinfo_raw) // 72)]
    texdata_raw = lump(data, 2)
    td_name = [struct.unpack_from("<i", texdata_raw, i * 32 + 12)[0] for i in range(len(texdata_raw) // 32)]
    strdata = lump(data, 43)
    strtab_raw = lump(data, 44)
    strtab = [struct.unpack_from("<i", strtab_raw, i * 4)[0] for i in range(len(strtab_raw) // 4)]

    def texname(ti):
        if ti < 0 or ti >= len(texinfo_td):
            return "-"
        td = texinfo_td[ti]
        if td < 0 or td >= len(td_name):
            return "?"
        o = strtab[td_name[td]]
        return strdata[o:strdata.index(b"\0", o)].decode("latin-1")

    hw, ht = a.hull
    mins = (-hw, -hw, 0.0)
    maxs = (hw, hw, ht)
    p = (a.x, a.y, a.z)
    print("VBSP v%d: %d planes %d brushes %d sides; hull %g x %g at %.3f %.3f %.3f" % (ver, len(planes), len(brushes), len(sides), hw, ht, *p))
    for bi, (first, num, contents) in enumerate(brushes):
        ds = []
        for s in range(first, first + num):
            pn, ti, disp, bevel = sides[s][:4]
            nx, ny, nz, dist, _ = planes[pn]
            corner = [mins[i] if (nx, ny, nz)[i] > 0 else maxs[i] for i in range(3)]
            d = sum((p[i] + corner[i]) * (nx, ny, nz)[i] for i in range(3)) - dist
            ds.append((d, s, pn, nx, ny, nz, dist, ti, bevel))
        if not ds:
            continue
        mx = max(x[0] for x in ds)
        if mx <= a.within:
            print("brush %d contents 0x%x sides %d  max d %.5f  %s" % (bi, contents, num, mx, "OVERLAPS HULL" if mx <= 0 else ""))
            for d, s, pn, nx, ny, nz, dist, ti, bevel in sorted(ds, key=lambda x: -x[0]):
                print("   d %+10.5f  n %+.5f %+.5f %+.5f  dist %+.4f  %s%s" % (d, nx, ny, nz, dist, texname(ti), "  (bevel)" if bevel else ""))


if __name__ == "__main__":
    main()
