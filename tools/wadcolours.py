#!/usr/bin/env python3
"""wadcolours.py -- the average colour of every texture in Valve's GoldSrc WADs, for scripts/wadcolours.txt.

    python3 -I tools/wadcolours.py <out.txt> <Half-Life dir> [<extra wad or dir> ...]

A BSP-30 map names its textures; the pixels are in Half-Life's and Counter-Strike's WADs, which a player may
not have. The engine (client/wad.c, Patch 1660) then draws the face in the colour listed here.

    FTESURF-WADCOLOURS 1
    # stamp YYYYMMDDhhmmss
    <name> <rrggbb>          lower-case name, sorted as bytes; sRGB of the linear-light mean of mip 0
    # end <rows>

First source wins: valve, cstrike, czero, then the extras in the order given. A '{' texture's mean skips
its transparent index (255). No pixels are stored: one colour per name.
"""
import os
import struct
import sys
import time

GAMES = ('valve', 'cstrike', 'czero')
LIN = [((v / 255.0 + 0.055) / 1.055) ** 2.4 if v > 10 else v / 255.0 / 12.92 for v in range(256)]


def srgb(x):
    x = max(0.0, min(1.0, x))
    return int(round(255 * (1.055 * x ** (1 / 2.4) - 0.055 if x > 0.0031308 else 12.92 * x)))


def wad_colours(path):
    out = {}
    with open(path, 'rb') as f:
        head = f.read(12)
        if len(head) < 12 or head[:4] != b'WAD3':
            return out
        n, off = struct.unpack('<ii', head[4:12])
        if not 0 <= n <= 200000:
            return out
        f.seek(off)
        table = f.read(32 * n)
        for i in range(len(table) // 32):
            e = table[i * 32:(i + 1) * 32]
            pos, disksize, _size, typ, comp = struct.unpack('<iiibb', e[:14])
            if typ != 0x43 or comp or disksize < 40:
                continue
            f.seek(pos)
            lump = f.read(disksize)
            name = lump[:16].split(b'\0', 1)[0].decode('latin-1').lower().replace('*', '#')   # as W_CleanupName
            w, h, o0, _o1, _o2, o3 = struct.unpack('<IIIIII', lump[16:40])
            if not name or ' ' in name or not w or not h or w > 4096 or h > 4096:
                continue
            pal = o3 + (w // 8) * (h // 8) + 2
            if o0 + w * h > len(lump) or pal + 768 > len(lump):
                continue
            hist = [0] * 256
            for b in lump[o0:o0 + w * h]:
                hist[b] += 1
            if name.startswith('{'):
                hist[255] = 0
            total = sum(hist)
            if not total:
                continue
            rgb = [0.0, 0.0, 0.0]
            for idx, c in enumerate(hist):
                if c:
                    for k in range(3):
                        rgb[k] += c * LIN[lump[pal + idx * 3 + k]]
            out.setdefault(name, '%02x%02x%02x' % tuple(srgb(v / total) for v in rgb))
    return out


def wads_in(path):
    if os.path.isfile(path):
        return [path]
    return sorted(os.path.join(path, f) for f in os.listdir(path) if f.lower().endswith('.wad'))


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        return 2
    out, hl, extra = sys.argv[1], sys.argv[2], sys.argv[3:]
    sources = [os.path.join(hl, g) for g in GAMES if os.path.isdir(os.path.join(hl, g))] + extra
    table = {}
    for src in sources:
        got = 0
        for wad in wads_in(src):
            for name, col in wad_colours(wad).items():
                if name not in table:
                    table[name] = col
                    got += 1
        print('%6d new from %s' % (got, src))
    rows = sorted(table.items(), key=lambda kv: kv[0].encode('latin-1'))
    with open(out, 'w', newline='\n', encoding='latin-1') as f:
        f.write('FTESURF-WADCOLOURS 1\n# stamp %s\n' % time.strftime('%Y%m%d%H%M%S', time.gmtime()))
        for name, col in rows:
            f.write('%s %s\n' % (name, col))
        f.write('# end %d\n' % len(rows))
    print('rows', len(rows), '->', out)
    return 0


if __name__ == '__main__':
    sys.exit(main())
