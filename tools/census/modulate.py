"""Packed Modulate / DecalModulate materials across the map library, and which set $additive or $mod2x.

Patch 767 made Modulate multiply as Source's modulate_dx9.cpp does (DST_COLOR*ZERO, or
DST_COLOR*SRC_COLOR under $mod2x) and stopped $additive turning it into an add.  This counts
what that moves.  Reads only each pakfile's zip directory and its .vmt members.

usage: python tools/census/modulate.py [--list]
"""
import os, sys, io, re, struct, zipfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bsplib

MAPS = os.path.join(os.environ.get('MOMENTUM_DIR', r'C:\Program Files (x86)\Steam\steamapps\common\Momentum Mod Playtest\momentum'), 'maps')


class Window(io.RawIOBase):
    """A read-only view of [base, base+size) of a file, so zipfile can open an embedded pakfile."""
    def __init__(self, fh, base, size):
        self.fh, self.base, self.size, self.pos = fh, base, size, 0

    def readable(self):
        return True

    def seekable(self):
        return True

    def tell(self):
        return self.pos

    def seek(self, off, whence=0):
        self.pos = off if whence == 0 else self.pos + off if whence == 1 else self.size + off
        return self.pos

    def read(self, n=-1):
        if n < 0 or self.pos + n > self.size:
            n = self.size - self.pos
        self.fh.seek(self.base + self.pos)
        d = self.fh.read(n)
        self.pos += len(d)
        return d

    def readinto(self, b):
        d = self.read(len(b))
        b[:len(d)] = d
        return len(d)


SHADER = re.compile(rb'^\s*"?([A-Za-z_0-9]+)"?\s*(\{|$)', re.M)
tally = {'maps': 0, 'maps_with_modulate': 0, 'Modulate': 0, 'Modulate+additive': 0, 'Modulate+mod2x': 0,
         'DecalModulate': 0, 'DecalModulate+mod2x': 0, 'DecalModulate+additive': 0}
rows = []
for name in sorted(os.listdir(MAPS)):
    if not name.lower().endswith('.bsp'):
        continue
    with open(os.path.join(MAPS, name), 'rb') as fh:
        t = bsplib.lumps(fh)
        if not t:
            continue
        tally['maps'] += 1
        o, l, v, f = t[40]
        if l <= 0:
            continue
        try:
            z = zipfile.ZipFile(Window(fh, o, l))
        except zipfile.BadZipFile:
            continue
        hit = False
        for info in z.infolist():
            if not info.filename.lower().endswith('.vmt') or info.file_size > 65536:
                continue
            d = z.read(info)
            m = SHADER.search(d)
            if not m:
                continue
            sh = m.group(1).decode('latin1').lower()
            if sh not in ('modulate', 'decalmodulate'):
                continue
            key = 'Modulate' if sh == 'modulate' else 'DecalModulate'
            tally[key] += 1
            add = re.search(rb'\$additive"?\s+"?1', d, re.I) is not None
            m2 = re.search(rb'\$mod2x"?\s+"?1', d, re.I) is not None
            if add:
                tally[key + '+additive'] += 1
            if m2:
                tally[key + '+mod2x'] += 1
            if key == 'Modulate':
                hit = True
                rows.append((name[:-4], info.filename, 'additive' if add else '', 'mod2x' if m2 else ''))
        tally['maps_with_modulate'] += hit
print(tally)
if '--list' in sys.argv:
    for r in rows:
        print('%-32s %-60s %s %s' % r)
