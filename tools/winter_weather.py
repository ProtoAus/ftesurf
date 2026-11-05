#!/usr/bin/env python3
"""P1309: bake optional static sky-portal/liquid meshes, roof LUT and original audio.

No world material replacement, runtime BSP walk/trace/capture, or physics changes.
Uses the existing Source reader, snow roof clipper and static IQM writer. Assets
are prepared before play; this is not native visual or frame-time acceptance.
"""
import argparse
import hashlib
import math
import struct
import subprocess
import sys
import wave
from pathlib import Path

import numpy as np
from PIL import Image
from holiday_assets import iqm
from rampwear import Bsp

MAPS = ('surf_christmas', 'surf_frost', 'surf_bluewinter')
MOM_MAPS = Path('C:/Program Files (x86)/Steam/steamapps/common/Momentum Mod Playtest/momentum/maps')
MAX_SKY_TRI = 4096
MAX_ICE_TRI = 8192
MAX_ROOF = 65536


def roof_header(name, x, y, step, width, height, sky_triangles, ice_triangles):
    """The ten-token Weather_Load contract shared by both map producers."""
    return (f'weather 1 {name} {x:g} {y:g} {step:g} {width} {height} '
            f'{sky_triangles} {ice_triangles}\n')


def kind(flags, texture, normal):
    if flags & (0x80 | 0x200):
        return None
    if flags & (0x2 | 0x4):
        return 'sky'
    if normal[2] >= 0.85 and (flags & 0x8 or any(s in texture for s in ('water', 'lava', 'slime'))):
        return 'lava' if 'lava' in texture or 'slime' in texture else 'water'
    return None


def surfaces(bsp):
    planes, _ = bsp.lump(1)
    xyz, _ = bsp.lump(3)
    faces, fv = bsp.lump(7)
    edges, ev = bsp.lump(12)
    sedges, _ = bsp.lump(13)
    models, _ = bsp.lump(14)
    info, _ = bsp.lump(6)
    data, _ = bsp.lump(2)
    table, _ = bsp.lump(44)
    strings, _ = bsp.lump(43)
    if bsp.version < 19:
        raise ValueError('requires inspected Source v19+ face layout')
    size, fmt = (72, '<IBBxxiiii') if fv >= 2 else (56, '<HBBiHHH')
    esize, efmt = (8, '<II') if ev >= 1 else (4, '<HH')
    first, count = struct.unpack_from('<ii', models, 40)
    for f in range(first, first + count):
        plane, side, _on, start, n, ti, disp = struct.unpack_from(fmt, faces, f * size)
        if ti < 0 or ti == 65535 or n < 3 or (disp >= 0 if fv >= 2 else disp != 65535):
            continue
        normal = struct.unpack_from('<3f', planes, plane * 20)
        if side:
            normal = tuple(-v for v in normal)
        flags, td = struct.unpack_from('<ii', info, ti * 72 + 64)
        sid = struct.unpack_from('<i', data, td * 32 + 12)[0]
        offset = struct.unpack_from('<i', table, sid * 4)[0]
        texture = strings[offset:strings.index(b'\0', offset)].decode('latin1').lower()
        selected = kind(flags, texture, normal)
        if not selected:
            continue
        poly = []
        for i in range(n):
            edge = struct.unpack_from('<i', sedges, (start + i) * 4)[0]
            a, b = struct.unpack_from(efmt, edges, abs(edge) * esize)
            poly.append(struct.unpack_from('<3f', xyz, (a if edge >= 0 else b) * 12))
        if not all(math.isfinite(v) for p in poly for v in p) or not all(math.isfinite(v) for v in normal):
            raise ValueError('nonfinite selected face')
        yield selected, normal, poly


def meshes(bsp):
    vertex = {'sky': [], 'ice': []}
    triangle = {'sky': [], 'ice': []}
    seen = set()
    for selected, normal, poly in surfaces(bsp):
        group = 'sky' if selected == 'sky' else 'ice'
        for i in range(1, len(poly) - 1):
            points = (poly[0], poly[i], poly[i + 1])
            key = (group, tuple(sorted(points)))
            if key in seen:
                continue
            seen.add(key)
            a = np.array(points[1]) - points[0]
            b = np.array(points[2]) - points[0]
            if float(np.linalg.norm(np.cross(a, b))) < 1e-5:
                continue
            first = len(vertex[group])
            for p in points:
                # Half-unit visual frost thickness only, never a collision plane.
                q = p if group == 'sky' else tuple(p[j] + normal[j] * 0.5 for j in range(3))
                # Constant per-face lava bit; shader tiles from world position.
                uv = (1.0 if selected == 'lava' else 0.0, 0.0)
                vertex[group].append((q, uv, normal))
            triangle[group].append((first, first + 1, first + 2))
    for group, limit in [('sky', MAX_SKY_TRI), ('ice', MAX_ICE_TRI)]:
        if len(triangle[group]) > limit:
            print(f'HOLD {group}: {len(triangle[group])} triangles exceeds {limit}; other features continue')
            vertex[group].clear()
            triangle[group].clear()
    return vertex, triangle


def roof_data(meta, image):
    row = meta.split()
    if row[:2] != ['snowmask', '1'] or len(row) != 10:
        raise ValueError('not a known roof metadata version')
    x, y, cell = map(float, row[3:6])
    w, h = map(int, row[6:8])
    z0, zr = map(float, row[8:10])
    if not (0 < w * h <= MAX_ROOF and 0 < w <= 256 and 0 < h <= 256 and cell > 0 and zr > 0):
        raise ValueError('roof size/range exceeds bounded native bulk read')
    if not all(math.isfinite(v) for v in (x, y, cell, z0, zr)):
        raise ValueError('nonfinite roof bounds')
    rgb = np.asarray(image.convert('RGB'), dtype=np.uint16)
    if rgb.shape[:2] != (h, w):
        raise ValueError('roof image/header mismatch')
    q = (rgb[..., 0] << 8) | rgb[..., 1]
    heights = (z0 + q.astype(np.float64) / 65535 * zr).astype('<f4')
    return (x, y, cell, w, h), heights


def original_noise(out):
    """One static tiling roughness/crack sample instead of runtime noise loops."""
    out.parent.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(1309)
    y, x = np.mgrid[:64, :64]
    sites = rng.uniform(0, 64, (18, 2))
    distance = []
    for px, py in sites:
        dx, dy = np.abs(x - px), np.abs(y - py)
        dx, dy = np.minimum(dx, 64 - dx), np.minimum(dy, 64 - dy)
        distance.append(np.sqrt(dx * dx + dy * dy))
    near = np.partition(np.array(distance), 1, axis=0)[:2]
    crack = np.clip(1 - (near[1] - near[0]) / 0.7, 0, 1)
    image = np.zeros((64, 64, 3), dtype=np.uint8)
    image[..., 0] = np.clip(near[0] * 12 + 48, 0, 255).astype(np.uint8)
    image[..., 1] = (crack * 255).astype(np.uint8)
    image[..., 2] = 128
    Image.fromarray(image).save(out)
    from PIL import ImageDraw, ImageFilter
    alpha = Image.new('L', (64, 128))
    draw = ImageDraw.Draw(alpha)
    points = [(32, 10)]
    for y in range(22, 119, 12):
        points.append((int(rng.integers(22, 43)), y))
    draw.line(points, fill=255, width=2)
    for index, sign in [(2, -1), (4, 1), (6, -1)]:
        x, y = points[index]
        draw.line([(x, y), (x + sign * 9, y + 6), (x + sign * 16, y + 19)], fill=190, width=1)
    bolt = Image.new('RGBA', alpha.size, (255, 255, 255, 0))
    bolt.putalpha(alpha.filter(ImageFilter.GaussianBlur(0.35)))
    bolt.save(out.with_name('lightning.png'))


def original_audio(out):
    """Original procedural PCM, fixed seed/quiet peaks; no codec or sampled asset."""
    out.mkdir(parents=True, exist_ok=True)
    rate = 22050
    rng = np.random.default_rng(1309)

    def write(name, signal):
        if not np.isfinite(signal).all() or np.max(np.abs(signal)) < 0.001:
            raise ValueError('silent/nonfinite procedural sound')
        data = (np.clip(signal, -0.9, 0.9) * 32767).astype('<i2')
        with wave.open(str(out / (name + '.wav')), 'wb') as f:
            f.setnchannels(1); f.setsampwidth(2); f.setframerate(rate)
            f.writeframes(data.tobytes())

    def filtered_noise(seconds, cutoff):
        n = int(rate * seconds)
        bins = np.fft.rfftfreq(n, 1 / rate)
        spectrum = np.fft.rfft(rng.normal(0, 1, n))
        spectrum /= np.sqrt(1 + (bins / cutoff) ** 4)
        spectrum[0] = 0
        value = np.fft.irfft(spectrum, n)
        return value / max(float(np.max(np.abs(value))), 1e-9)

    for name, cutoff, gain in [('wind-out', 950, 0.32), ('wind-in', 220, 0.22)]:
        signal = filtered_noise(4, cutoff)
        # FFT result is cyclic; slow cyclic gust and tiny edge fade hide loop joins.
        t = np.arange(len(signal)) / len(signal)
        edge = np.minimum(np.minimum(t * 100, (1 - t) * 100), 1)
        write(name, signal * (0.65 + 0.35 * np.sin(t * math.tau) ** 2) * edge * gain)
    for name, cutoff, gain in [('thunder-out', 1700, 0.78), ('thunder-in', 400, 0.52)]:
        signal = filtered_noise(3, cutoff)
        t = np.arange(len(signal)) / rate
        envelope = (1 - np.exp(-t * 18)) * np.exp(-t * 1.65)
        envelope *= np.minimum((3 - t) * 8, 1)
        write(name, signal * envelope * gain)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--maps', nargs='+', default=MAPS)
    ap.add_argument('--mapdir', type=Path, default=MOM_MAPS)
    ap.add_argument('--gamedir', type=Path, required=True)
    a = ap.parse_args()
    original_audio(a.gamedir / 'sound/winter')
    original_noise(a.gamedir / 'gfx/weather/ice-noise.png')
    for name in a.maps:
        if not name or any(not (c.isascii() and (c.isalnum() or c == '_')) for c in name):
            ap.error('map basename required')
        path = a.mapdir / (name + '.bsp')
        bsp = Bsp(str(path))
        vertex, triangle = meshes(bsp)
        if not triangle['sky'] and not triangle['ice']:
            print(f'SKIP {name}: no eligible in-budget world sky/liquid; no false outdoor classification')
            continue
        # Existing cosmetic prefix skips default native convex decomposition.
        model = a.gamedir / 'models/gibs/winterweather'
        model.mkdir(parents=True, exist_ok=True)
        for group in ('sky', 'ice'):
            if triangle[group]:
                material = 'ftesurf_weather_' + group + '_v1'
                (model / (name + '-' + group + '.iqm')).write_bytes(iqm(name + '-' + group, vertex[group], triangle[group], material))
        bounds, _ = bsp.lump(14)
        low = struct.unpack_from('<3f', bounds)
        high = struct.unpack_from('<3f', bounds, 12)
        cell = 128
        pot = lambda n: 1 << max(0, int(math.ceil(n) - 1).bit_length())
        while max(pot((high[0] - low[0]) / cell + 4), pot((high[1] - low[1]) / cell + 4)) > 256:
            cell *= 2
        subprocess.run([sys.executable, str(Path(__file__).with_name('snowmask.py')), '--map', name, '--bsp', str(path), '--cell', str(cell), '--gamedir', str(a.gamedir)], check=True)
        mask = a.gamedir / 'gfx/snowmask' / name
        meta = mask.with_suffix('.txt')
        if not meta.is_file():
            raise ValueError('no sky roof field: do not silently claim outdoor classification')
        dims, heights = roof_data(meta.read_text(), Image.open(mask.with_suffix('.png')))
        weather = a.gamedir / 'gfx/weather'
        weather.mkdir(parents=True, exist_ok=True)
        x, y, step, w, h = dims
        header = roof_header(name, x, y, step, w, h, len(triangle['sky']), len(triangle['ice']))
        (weather / (name + '.roof')).write_bytes(header.encode('ascii') + heights.tobytes())
        print(f'{name}: sky {len(triangle["sky"])}tri, ice {len(triangle["ice"])}tri, roof {w}x{h}; BSP {hashlib.sha256(path.read_bytes()).hexdigest()}')


if __name__ == '__main__':
    main()
