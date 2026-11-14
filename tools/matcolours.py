#!/usr/bin/env python3
"""P1548: the colour index -- every material's average colour, for a player who does not have it.

    python tools/matcolours.py [--out ftesurf/data/matcolours.txt] [--steam <common dir>]

The hl2 plugin (mat_vmt.c) draws a material whose image is missing as one flat colour under its own
lighting instead of the pink/black checker. A map's own surfaces carry that colour already (dtexdata
reflectivity, P1191); props and 0x0 texdata do not, so this file does: one line per material, from the
games fs_addons.default.txt mounts, in the same precedence (first source wins).

    <path> <RRGGBB> <flags> [<tint RRGGBB>]

<path> is the material (or, where a material's $basetexture is named differently, that texture) without
"materials/" and extension, lowercase, '/'. RRGGBB is sRGB: the VTF header's reflectivity (the linear
average vtex wrote), else the low-res thumbnail's average; a material's $color2/$color follows as the
tint, which the VMT itself applies when it loads. Flags: t $translucent, a $alphatest, d $additive, w Water,
u UnlitGeneric (a Water line's colour is its $fogcolor), s Sprite/SpriteCard, r Refract, e $decal, x a texture line, - none.
"""
import argparse
import re
import struct
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sourceassets import VpkSource, DirectorySource, asset_path  # noqa: E402

STEAM = Path(r'C:\Program Files (x86)\Steam\steamapps\common')
SOURCES = [   # fs_addons.default.txt's order: Momentum, its bundled HL2, CS:S, HL2, then the automounts
    ('momentum', 'Momentum Mod Playtest/momentum'),
    ('momentum-hl2', 'Momentum Mod Playtest/mount/hl2_dir.vpk'),
    ('cstrike', 'Counter-Strike Source/cstrike/cstrike_pak_dir.vpk'),
    ('hl2-misc', 'Half-Life 2/hl2/hl2_misc_dir.vpk'),
    ('hl2-textures', 'Half-Life 2/hl2/hl2_textures_dir.vpk'),
    ('ep1', 'Half-Life 2/episodic/ep1_pak_dir.vpk'),
    ('ep2', 'Half-Life 2/ep2/ep2_pak_dir.vpk'),
    ('tf2-misc', 'Team Fortress 2/tf/tf2_misc_dir.vpk'),
    ('tf2-textures', 'Team Fortress 2/tf/tf2_textures_dir.vpk'),
    ('portal', 'Portal/portal/portal_pak_dir.vpk'),
    ('csgo', 'Counter-Strike Global Offensive/csgo/pak01_dir.vpk'),
]
# Never on a map surface or a map's prop: cosmetics, weapon skins, HUD/menu art.
SKIP = ('models/player/items/', 'models/workshop/', 'models/workshop_partner/', 'models/weapons/customization/',
        'backpack/', 'vgui/', 'hud/', 'console/', 'models/inventory_items/', 'panorama/', 'models/weapons/stattrack/',
        'models/weapons/uid/', 'models/weapons/v_models/', 'models/props_tauntprops/',
        'models/player/custom_player/', 'logo/')


class Sources:
    def __init__(self, steam):
        self.list = []
        for name, rel in SOURCES:
            p = steam / rel
            if p.is_dir():
                src = DirectorySource(p)
                keys = set(src.paths())
            elif p.is_file():
                src = VpkSource(p)
                keys = set(src.entries)
            else:
                print(f'# not installed: {rel}', file=sys.stderr)
                continue
            self.list.append((name, src, keys))

    def find(self, key):
        for name, src, keys in self.list:
            if key in keys:
                return name, src
        return None, None

    def read(self, key, head=None):
        name, src = self.find(key)
        if src is None:
            return None
        if head is None or isinstance(src, DirectorySource):
            data = src.read(key).data
            return data if head is None else data[:head]
        crc, archive, offset, length, pre = src.entries[key]   # header only: a VTF can be megabytes
        data = pre[:head]
        if len(data) < head and length:
            path, base = (src.path, src.database) if archive == 0x7fff else \
                (src.path.with_name(src.path.name[:-8] + '_%03d.vpk' % archive), 0)
            with path.open('rb') as f:
                f.seek(base + offset)
                data += f.read(min(length, head - len(data)))
        return data

    def vmts(self):
        seen = {}
        for name, src, keys in self.list:
            for k in keys:
                if k.endswith('.vmt') and k.startswith('materials/') and k not in seen:
                    seen[k] = name
        return seen


KEY = re.compile(r'"?(\$?[A-Za-z_][\w$%]*)"?\s+("([^"\r\n]*)"|([^\s{}"]+))')


def norm(p):
    """A VMT's path value as an asset key, or None: authored paths carry backslashes, a leading '/', doubles."""
    p = re.sub(r'/+', '/', p.replace('\\', '/').lower()).strip('/ ')
    try:
        return asset_path(p)
    except Exception:
        return None


def lenient(text):
    """Shader name and the first value of each key (any depth), for the keys this needs."""
    text = re.sub(r'//[^\r\n]*', '', text)
    m = re.match(r'\s*"?([A-Za-z_][\w]*)"?\s*\{', text)
    if not m:
        return None, {}
    keys = {}
    for k in KEY.finditer(text[m.end():]):
        name = k.group(1).lower()
        if name not in keys:
            keys[name] = k.group(3) if k.group(3) is not None else k.group(4)
    return m.group(1).lower(), keys


def material(srcs, path, depth=0):
    data = srcs.read(path)
    if data is None or depth > 4:
        return None, {}
    shader, keys = lenient(data.decode('latin-1'))
    if shader == 'patch' and 'include' in keys:
        inc = norm(keys['include'])
        if not inc:
            return None, {}
        if not inc.startswith('materials/'):
            inc = 'materials/' + inc
        if not inc.endswith('.vmt'):
            inc += '.vmt'
        base_shader, base = material(srcs, inc, depth + 1)
        base = dict(base)
        base.update({k: v for k, v in keys.items() if k != 'include'})
        return base_shader, base
    return shader, keys


def dxt1_average(block_data, n):
    r = g = b = cnt = 0
    for i in range(n):
        c0, c1, bits = struct.unpack_from('<HHI', block_data, i * 8)
        pal = []
        for c in (c0, c1):
            pal.append((((c >> 11) & 31) * 255 // 31, ((c >> 5) & 63) * 255 // 63, (c & 31) * 255 // 31))
        if c0 > c1:
            pal.append(tuple((2 * x + y) // 3 for x, y in zip(pal[0], pal[1])))
            pal.append(tuple((x + 2 * y) // 3 for x, y in zip(pal[0], pal[1])))
        else:
            pal.append(tuple((x + y) // 2 for x, y in zip(pal[0], pal[1])))
            pal.append(None)
        for p in range(16):
            col = pal[(bits >> (2 * p)) & 3]
            if col:
                r += col[0]; g += col[1]; b += col[2]; cnt += 1
    return (r // cnt, g // cnt, b // cnt) if cnt else None


def vtf_colour(srcs, tex):
    key = 'materials/' + tex + '.vtf'
    head = srcs.read(key, 1024)
    if not head or len(head) < 80 or head[:4] != b'VTF\0':
        return None
    major, minor, hsize = struct.unpack_from('<III', head, 4)
    refl = struct.unpack_from('<fff', head, 32)
    if all(0 < x <= 1 for x in refl) or (all(0 <= x <= 1 for x in refl) and sum(refl) > 0):
        return tuple(int(round(255 * (x ** (1 / 2.2)))) for x in refl)
    # zero reflectivity: the low-res thumbnail (DXT1 = format 13), 7.2 right after the header
    lowfmt, lw, lh = struct.unpack_from('<iBB', head, 57)
    if lowfmt != 13 or not lw or not lh:
        return None
    off = hsize
    if (major, minor) >= (7, 3):
        nres = struct.unpack_from('<I', head, 68)[0]
        off = None
        for i in range(min(nres, 32)):
            tag, flags, o = struct.unpack_from('<3sBI', head, 80 + i * 8)
            if tag == b'\x01\x00\x00':
                off = o
        if off is None:
            return None
    nblk = max(1, (lw + 3) // 4) * max(1, (lh + 3) // 4)
    data = srcs.read(key, off + nblk * 8)
    if not data or len(data) < off + nblk * 8:
        return None
    return dxt1_average(data[off:], nblk)


def tint(value):
    if not value:
        return None
    v = value.strip()
    nums = re.findall(r'-?[\d.]+', v)
    if len(nums) < 3:
        return None
    f = [float(x) for x in nums[:3]]
    if v.startswith('{'):
        f = [x / 255 for x in f]
    return [max(0.0, min(1.0, x)) for x in f]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default='ftesurf/data/matcolours.txt')
    ap.add_argument('--steam', type=Path, default=STEAM)
    a = ap.parse_args()
    t0 = time.time()
    srcs = Sources(a.steam)
    mats = srcs.vmts()
    lines, tex_lines, stats = {}, {}, dict(mats=0, skipped=0, nocolour=0, white=0)
    for path, src in sorted(mats.items()):
        key = path[len('materials/'):-4]
        if key.startswith(SKIP) or re.search(r'\s', key):    # CS:GO ships a few names ending in a space
            stats['skipped'] += 1
            continue
        shader, keys = material(srcs, path)
        if shader is None:
            continue
        if shader.startswith('water'):
            # a Water's colour is its fog: its $basetexture, where it has one, is a ripple/normal map
            fog = tint(keys.get('$fogcolor'))
            if fog:
                lines[key] = '%s %02x%02x%02x w' % (key, *(int(round(255 * x)) for x in fog))
                stats['mats'] += 1
            continue
        base = keys.get('$basetexture')
        base = norm(base).removeprefix('materials/') if base and norm(base) else None
        if base and base.endswith('.vtf'):
            base = base[:-4]
        col = vtf_colour(srcs, base) if base else vtf_colour(srcs, key)
        if col is None and not base:
            col = (255, 255, 255)    # no $basetexture: Source binds white under $color (P1039)
            stats['white'] += 1
        if col is None:
            stats['nocolour'] += 1
            continue
        t = tint(keys.get('$color2')) or tint(keys.get('$color'))
        flags = ''
        if keys.get('$translucent', '0').strip() not in ('0', ''):
            flags += 't'
        if keys.get('$alphatest', '0').strip() not in ('0', ''):
            flags += 'a'
        if keys.get('$additive', '0').strip() not in ('0', ''):
            flags += 'd'
        if shader.startswith('water'):
            flags += 'w'
        if shader.startswith('unlit'):
            flags += 'u'
        if shader.startswith('sprite'):
            flags += 's'
        if shader.startswith('refract'):
            flags += 'r'
        if keys.get('$decal', '0').strip() not in ('0', ''):
            flags += 'e'
        lines[key] = '%s %02x%02x%02x %s' % (key, *col, flags or '-') +             ((' %02x%02x%02x' % tuple(int(round(255 * x)) for x in t)) if t and t != [1.0, 1.0, 1.0] else '')
        stats['mats'] += 1
        if base and base != key and not base.startswith(SKIP) and not re.search(r'\s', base):
            tex_lines.setdefault(base, '%s %02x%02x%02x x' % (base, *col))
    for k, v in tex_lines.items():
        lines.setdefault(k, v)
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open('w', encoding='ascii', newline='\n') as f:
        f.write('// P1548 colour index: tools/matcolours.py, %s. <path> <RRGGBB sRGB> <flags: t a d w u x ->\n'
                % time.strftime('%Y-%m-%d'))
        f.write('// sources (first wins): %s\n' % ' '.join(n for n, s, k in srcs.list))
        for k in sorted(lines):
            f.write(lines[k] + '\n')
    print(f"{len(lines)} lines ({stats['mats']} materials, {len(lines) - stats['mats']} textures); "
          f"{stats['skipped']} skipped by prefix, {stats['nocolour']} without a colour, {stats['white']} white; "
          f"{out.stat().st_size / 1024:.0f} KB in {time.time() - t0:.0f} s")


if __name__ == '__main__':
    main()
