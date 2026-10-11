#!/usr/bin/env python3
"""sparkleshape.py -- the shape of Source's particle/sparkles, read off the .vtf.

    python tools/sparkleshape.py <sparkles.vtf | a game's *_dir.vpk> [...]

cl_emit.qc's mote shader (Patch 648) does not sample this texture: it computes
the shape, so a two-pixel mote is right at any size.  The shape it computes is

    alpha = clamp((1.17 - r) / 0.92, 0, 1)      r = distance from the centre, in half-sides

solid to 0.25 of the half-side, a straight line to nothing at 1.17, cut off by
the texture's square.  This prints the texture's own alpha against that, texel by
texel, and exits 1 if they are more than 0.06 apart in the mean (DXT5 alpha is
good to about 0.02) or the colour is not white.  Reads Valve's file where it is
installed; ships nothing.  Exit 2 when it cannot read one.
"""
import math
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sourceassets  # noqa: E402


def dxt5(data, w, h):
    px = [[(0, 0, 0, 0)] * w for _ in range(h)]
    o = 0
    for by in range(0, h, 4):
        for bx in range(0, w, 4):
            a0, a1 = data[o], data[o + 1]
            abits = int.from_bytes(data[o + 2:o + 8], 'little')
            c0, c1, cbits = struct.unpack_from('<HHI', data, o + 8)
            o += 16
            if a0 > a1:
                al = [a0, a1] + [((7 - i) * a0 + i * a1) // 7 for i in range(1, 7)]
            else:
                al = [a0, a1] + [((5 - i) * a0 + i * a1) // 5 for i in range(1, 5)] + [0, 255]
            rgb = lambda c: ((c >> 11) * 255 // 31, ((c >> 5) & 63) * 255 // 63, (c & 31) * 255 // 31)
            r0, r1 = rgb(c0), rgb(c1)
            cl = [r0, r1, tuple((2 * x + y) // 3 for x, y in zip(r0, r1)), tuple((x + 2 * y) // 3 for x, y in zip(r0, r1))]
            for i in range(16):
                x, y = bx + i % 4, by + i // 4
                if x < w and y < h:
                    px[y][x] = cl[(cbits >> (2 * i)) & 3] + (al[(abits >> (3 * i)) & 7],)
    return px


def top_mip(b):
    if b[:4] != b'VTF\0':
        raise ValueError('not a VTF')
    hsize, w, h = struct.unpack_from('<IHH', b, 12)
    fmt, mips, lfmt, lw, lh = struct.unpack_from('<iBiBB', b, 52)
    if fmt != 15:
        raise ValueError('image format %d, expected DXT5 (15)' % fmt)
    # mips are stored smallest first, after the header and the DXT1 thumbnail
    o = hsize + max(1, (lw + 3) // 4) * max(1, (lh + 3) // 4) * 8
    for m in range(mips - 1, 0, -1):
        o += max(1, ((w >> m) + 3) // 4) * max(1, ((h >> m) + 3) // 4) * 16
    return w, h, dxt5(b[o:], w, h)


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    bad = False
    for arg in sys.argv[1:]:
        try:
            if arg.lower().endswith('.vtf'):
                data = Path(arg).read_bytes()
            else:
                data = sourceassets.VpkSource(arg).read('materials/particle/sparkles.vtf').data
            w, h, px = top_mip(data)
        except Exception as ex:
            print('CANNOT READ %s: %s' % (arg, ex))
            return 2
        err = worst = 0.0
        white = True
        ring = {}
        for y in range(h):
            for x in range(w):
                r = math.hypot((x + 0.5) / (w / 2) - 1, (y + 0.5) / (h / 2) - 1)
                want = max(0.0, min(1.0, (1.17 - r) / 0.92))
                got = px[y][x][3] / 255.0
                err += abs(got - want)
                worst = max(worst, abs(got - want))
                white = white and (got == 0 or min(px[y][x][:3]) >= 247)
                ring.setdefault(int(r * 8), []).append((got, want))
        err /= w * h
        mean = sum(p[3] for row in px for p in row) / (255.0 * w * h)
        print('%s: %dx%d, mean alpha %.3f' % (arg, w, h, mean))
        print('  r/8   texture  computed')
        for k in sorted(ring):
            print('  %-5d %.2f     %.2f' % (k, sum(g for g, _ in ring[k]) / len(ring[k]), sum(v for _, v in ring[k]) / len(ring[k])))
        print('  mean difference %.3f, worst texel %.2f, colour %s' % (err, worst, 'white' if white else 'NOT white'))
        bad = bad or err > 0.06 or not white
    print('FAIL' if bad else 'PASS')
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
