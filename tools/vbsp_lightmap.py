#!/usr/bin/env python3
"""
vbsp_lightmap.py -- decode a Source BSP's lightmap samples INDEPENDENTLY of the
engine, so "is the renderer wrong or is the data wrong" stops being a matter of
opinion.

WHY THIS EXISTS.  Build 11 measured surf_666's ramp brush entities rendering at
0.73x their own texture with a red/blue ratio of 1.01, against a world floor at
0.29x and R/B 1.59.  A SCALE FACTOR CANNOT CHANGE A RATIO -- so overbright,
gamma and tonemapping are all excluded by that one number, and the only question
left is whether the luxels the engine loaded for those faces are the luxels VRAD
wrote for them.  This reads the BSP with no engine code in the path at all.

R/B IS THE FIGURE THAT TRANSFERS.  The absolute magnitude depends on a decode
convention (Valve's TexLightToLinear is c * 2^exponent, with the /255 and the
gamma applied later and differently by every consumer), but the ratio between
two channels of the same luxel is convention-free.  So the comparison against
the engine's own `r_texdiag` LUX line is made on R/B first and on magnitude only
as a sanity check.

Usage:
    python vbsp_lightmap.py <map.bsp>              # every model, summarised
    python vbsp_lightmap.py <map.bsp> 283          # one model, per-face
    python vbsp_lightmap.py <map.bsp> 0 --faces 20 # world, first 20 faces
"""

import lzma
import math
import os
import struct
import sys

# ---------------------------------------------------------------------------
#  Lumps.  Only the ones this needs.
# ---------------------------------------------------------------------------
LUMP_TEXDATA             = 2
LUMP_TEXINFO             = 6
LUMP_FACES               = 7
LUMP_LIGHTING            = 8
LUMP_MODELS              = 14
LUMP_TEXDATA_STRING_DATA = 43
LUMP_TEXDATA_STRING_TABLE= 44
LUMP_LIGHTING_HDR        = 53
LUMP_FACES_HDR           = 58

# Source surface flags we care about (bspflags.h).
SURF_SKY      = 0x0004
SURF_WARP     = 0x0008
SURF_TRANS    = 0x0010
SURF_NOLIGHT  = 0x0400
SURF_NODRAW   = 0x0080
SURF_BUMPLIGHT= 0x0800     # THE one that changes the sample stride


class Bsp:
    def __init__(self, path):
        self.data = open(path, "rb").read()
        ident, self.version = struct.unpack_from("<ii", self.data, 0)
        if ident != 0x50534256:                      # 'VBSP'
            raise SystemExit("not a VBSP file (ident %08x)" % ident)
        self.lumps = []
        for i in range(64):
            ofs, ln, ver, fourcc = struct.unpack_from("<iii4s", self.data, 8 + i * 16)
            self.lumps.append((ofs, ln, ver, fourcc))

    def lump(self, n):
        """Raw bytes of a lump, LZMA-decompressed if Valve compressed it.

        A compressed lump carries a big-endian uncompressed size in the fourCC
        field and starts with Valve's own 17-byte 'LZMA' header rather than a
        standard .lzma one, so Python's raw filter has to be fed the property
        bytes by hand.
        """
        ofs, ln, ver, fourcc = self.lumps[n]
        if ln == 0:
            return b""
        raw = self.data[ofs:ofs + ln]
        if fourcc != b"\0\0\0\0":
            magic, actual, lzmasize = struct.unpack_from("<III", raw, 0)
            if magic != 0x414D5A4C:                  # 'LZMA'
                raise SystemExit("lump %d flagged compressed but has no LZMA header" % n)
            props = raw[12:17]
            lc_lp_pb = props[0]
            lc = lc_lp_pb % 9
            lc_lp_pb //= 9
            lp = lc_lp_pb % 5
            pb = lc_lp_pb // 5
            dict_size = struct.unpack_from("<I", props, 1)[0]
            dec = lzma.LZMADecompressor(
                format=lzma.FORMAT_RAW,
                filters=[{"id": lzma.FILTER_LZMA1, "dict_size": max(dict_size, 4096),
                          "lc": lc, "lp": lp, "pb": pb}])
            out = dec.decompress(raw[17:17 + lzmasize], actual)
            if len(out) != actual:
                print("  warning: lump %d decompressed to %d, header said %d"
                      % (n, len(out), actual), file=sys.stderr)
            return out
        return raw


def texnames(bsp):
    """texdata index -> material name."""
    sdata = bsp.lump(LUMP_TEXDATA_STRING_DATA)
    stab  = bsp.lump(LUMP_TEXDATA_STRING_TABLE)
    offs  = struct.unpack("<%di" % (len(stab) // 4), stab)
    names = []
    for o in offs:
        e = sdata.find(b"\0", o)
        names.append(sdata[o:e].decode("latin-1"))
    td = bsp.lump(LUMP_TEXDATA)
    out = []
    for i in range(len(td) // 32):
        nid = struct.unpack_from("<i", td, i * 32 + 12)[0]
        out.append(names[nid] if 0 <= nid < len(names) else "?")
    return out


def load(path):
    bsp = Bsp(path)

    # HDR wins in the engine unless hl2_favour_ldr, so report which exists.
    hdr_faces = bsp.lumps[LUMP_FACES_HDR][1]
    hdr_light = bsp.lumps[LUMP_LIGHTING_HDR][1]
    faces_lump = LUMP_FACES_HDR if hdr_faces else LUMP_FACES
    light_lump = LUMP_LIGHTING_HDR if hdr_light else LUMP_LIGHTING

    faces = bsp.lump(faces_lump)
    light = bsp.lump(light_lump)
    tinfo = bsp.lump(LUMP_TEXINFO)
    models = bsp.lump(LUMP_MODELS)
    tnames = texnames(bsp)

    print("%s  VBSP v%d" % (os.path.basename(path), bsp.version))
    print("  faces  lump %-2d  %8d bytes  %6d faces" % (faces_lump, len(faces), len(faces) // 56))
    print("  light  lump %-2d  %8d bytes%s" % (light_lump, len(light),
          "   (no HDR lump at all)" if not hdr_light else ""))
    print("  models          %8d bytes  %6d models" % (len(models), len(models) // 48))
    return bsp, faces, light, tinfo, models, tnames


def face(faces, i):
    (planenum, side, onnode, firstedge, numedges, texinfo, dispinfo,
     fogvol, s0, s1, s2, s3, lightofs, area,
     lmin0, lmin1, lsize0, lsize1, origface, nprims, firstprim,
     smooth) = struct.unpack_from("<HBBihhhh4BifiiiiiHHI", faces, i * 56)
    return dict(texinfo=texinfo, dispinfo=dispinfo, styles=(s0, s1, s2, s3),
                lightofs=lightofs, lw=lsize0 + 1, lh=lsize1 + 1, area=area)


def texinfo_of(tinfo, n):
    flags, texdata = struct.unpack_from("<ii", tinfo, n * 72 + 64)
    return flags, texdata


def decode(light, f, bumped):
    """Mean linear RGB of a face's FLAT lightmap set, style 0.

    Valve's TexLightToLinear is c * 2^exponent.  On a bumped face the samples
    are stored as four consecutive sets -- flat, then three directional -- and
    lightofs points at the flat one, so reading the first w*h is right either
    way.  `bumped` is returned so the caller can see whether a face that looks
    wrong is one of them.
    """
    n = f["lw"] * f["lh"]
    o = f["lightofs"]
    if o < 0 or o + n * 4 > len(light):
        return None
    r = g = b = 0.0
    for k in range(n):
        cr, cg, cb, ex = struct.unpack_from("<BBBb", light, o + k * 4)
        s = math.pow(2.0, ex)
        r += cr * s
        g += cg * s
        b += cb * s
    return (r / n, g / n, b / n)


def summarise(name, samples, nfaces, nolight, nosamples, bumpfaces, disp):
    if not samples:
        # Print the counters anyway.  "no lit faces" is only informative when it
        # says WHY -- a model whose faces are all TEX_SPECIAL is a trigger volume
        # and expected; one whose faces all have lightofs -1 is the bug.
        print("  %-10s %5d faces  lit 0      -- unlit --"
              "                                        bump %-4d disp %-4d nolight %-4d nosamples %d"
              % (name, nfaces, bumpfaces, disp, nolight, nosamples))
        return
    tot = len(samples)
    r = sum(s[0] for s in samples) / tot
    g = sum(s[1] for s in samples) / tot
    b = sum(s[2] for s in samples) / tot
    rb = (r / b) if b > 0.0001 else 0
    print("  %-10s %5d faces  lit %-5d  mean %8.4f %8.4f %8.4f   R/B %5.2f"
          "   bump %-4d disp %-4d nolight %-4d nosamples %d"
          % (name, nfaces, tot, r, g, b, rb, bumpfaces, disp, nolight, nosamples))


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    path = sys.argv[1]
    want = int(sys.argv[2]) if len(sys.argv) > 2 else None
    maxfaces = 12
    if "--faces" in sys.argv:
        maxfaces = int(sys.argv[sys.argv.index("--faces") + 1])

    bsp, faces, light, tinfo, models, tnames = load(path)
    nmodels = len(models) // 48

    print()
    print("  model      faces  lit         mean R        G        B      R/B"
          "   bump disp nolight nosamples")

    for m in range(nmodels):
        firstface, numfaces = struct.unpack_from("<ii", models, m * 48 + 40)
        samples = []
        nolight = nosamples = bumpfaces = disp = 0
        detail = []
        for i in range(firstface, firstface + numfaces):
            f = face(faces, i)
            flags, texdata = texinfo_of(tinfo, f["texinfo"])
            if flags & SURF_NOLIGHT:
                nolight += 1
                continue
            if f["dispinfo"] >= 0:
                disp += 1
            bumped = bool(flags & SURF_BUMPLIGHT)
            if bumped:
                bumpfaces += 1
            if f["lightofs"] < 0 or f["styles"][0] == 255:
                nosamples += 1
                continue
            v = decode(light, f, bumped)
            if v is None:
                nosamples += 1
                continue
            samples.append(v)
            if want == m and len(detail) < maxfaces:
                detail.append((i, f, flags, texdata, bumped, v))

        label = "world" if m == 0 else "*%d" % m
        if want is None or want == m:
            summarise(label, samples, numfaces, nolight, nosamples, bumpfaces, disp)

        for (i, f, flags, texdata, bumped, v) in detail:
            rb = (v[0] / v[2]) if v[2] > 0.0001 else 0
            print("      face %-6d %-42s  %2dx%-2d  ofs %-9d styles %-16s"
                  " %8.4f %8.4f %8.4f  R/B %5.2f %s%s"
                  % (i, tnames[texdata][:42], f["lw"], f["lh"], f["lightofs"],
                     ",".join(str(s) for s in f["styles"]),
                     v[0], v[1], v[2], rb,
                     "BUMP " if bumped else "",
                     "DISP" if f["dispinfo"] >= 0 else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
