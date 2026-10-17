"""Which files a map packs are answered by an EARLIER mount instead, and whether that copy differs.

The engine searches the map's own pakfile LAST (fs.c FS_AddPathHandle, SPF_TEMPORARY appends at
the tail); Source searches it first.  Mount order below is the client's `path` listing on Lex's PC,
17 Oct 2026.  Content is compared by CRC32 (a VPK entry carries the file's CRC32).

Patch 765 makes materials/ prefer the map pakfile; everything else still loses to these mounts.

usage: python tools/census/shadowed.py <map>... [--all]   (--all also lists identical shadows)
"""
import sys, os, io, struct, zipfile, zlib
from collections import Counter
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bsplib

S = "C:/Program Files (x86)/Steam/steamapps/common/"
MAPS = S + "Momentum Mod Playtest/momentum/maps/"
MOUNTS = [
    ("dir", S + "Momentum Mod Playtest/momentum"),
    ("vpk", S + "Counter-Strike Source/cstrike/cstrike_pak_dir.vpk"),
    ("dir", S + "Counter-Strike Source/cstrike"),
    ("vpk", S + "Half-Life 2/hl2/hl2_misc_dir.vpk"),
    ("vpk", S + "Half-Life 2/hl2/hl2_pak_dir.vpk"),
    ("vpk", S + "Half-Life 2/hl2/hl2_textures_dir.vpk"),
    ("dir", S + "Half-Life 2/hl2"),
    ("vpk", S + "Team Fortress 2/tf/tf2_misc_dir.vpk"),
    ("vpk", S + "Team Fortress 2/tf/tf2_textures_dir.vpk"),
    ("dir", S + "Team Fortress 2/tf"),
    ("vpk", S + "Counter-Strike Global Offensive/csgo/pak01_dir.vpk"),
    ("dir", S + "Counter-Strike Global Offensive/csgo"),
    ("vpk", S + "Portal 2/portal2/pak01_dir.vpk"),
    ("dir", S + "Portal 2/portal2"),
]


def read_vpk(path):
    """-> {lowercase path: crc32}"""
    out = {}
    with open(path, 'rb') as f:
        sig, ver, tree = struct.unpack('<III', f.read(12))
        if sig != 0x55aa1234:
            return out
        if ver == 2:
            f.read(16)
        data = f.read(tree)
    p = 0

    def cstr():
        nonlocal p
        e = data.index(b'\0', p)
        s = data[p:e].decode('latin1')
        p = e + 1
        return s
    while True:
        ext = cstr()
        if not ext:
            break
        while True:
            d = cstr()
            if not d:
                break
            while True:
                n = cstr()
                if not n:
                    break
                crc, pre = struct.unpack('<IH', data[p:p + 6])
                p += 18 + pre
                full = (n + '.' + ext) if d == ' ' else (d + '/' + n + '.' + ext)
                out[full.lower()] = crc
    return out


vpks = {}
for kind, p in MOUNTS:
    if kind == 'vpk' and os.path.exists(p):
        vpks[p] = read_vpk(p)

show_all = '--all' in sys.argv
for mp in [a for a in sys.argv[1:] if not a.startswith('--')]:
    fh = open(MAPS + mp + ".bsp", 'rb')
    t = bsplib.lumps(fh)
    o, l, v, f4 = t[40]
    fh.seek(o)
    z = zipfile.ZipFile(io.BytesIO(fh.read(l)))
    tally = Counter()
    rows = []
    for info in z.infolist():
        n = info.filename.replace(chr(92), '/').lower()
        if not (n.startswith('materials/') or n.startswith('models/')):
            continue
        tally['packed'] += 1
        mine = zlib.crc32(z.read(info)) & 0xffffffff
        for kind, p in MOUNTS:
            if kind == 'vpk':
                if p in vpks and n in vpks[p]:
                    theirs = vpks[p][n]
                    break
            else:
                fp = os.path.join(p, n)
                if os.path.isfile(fp):
                    theirs = zlib.crc32(open(fp, 'rb').read()) & 0xffffffff
                    break
        else:
            continue
        same = theirs == mine
        tally['shadowed same' if same else 'shadowed DIFFERENT'] += 1
        if not same or show_all:
            rows.append(("same" if same else "DIFF", os.path.basename(p) if kind == 'vpk' else p.split('/common/')[1], n))
    print("== %s: %s" % (mp, dict(tally)))
    for r in sorted(rows, key=lambda r: (r[1], r[2])):
        print("  %-4s %-40s %s" % r)
