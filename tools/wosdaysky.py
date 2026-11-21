#!/usr/bin/env python3
"""P1695: World of Surf's own daytime sky, gfx/env/wos_day{rt,bk,lf,ft,up,dn}.jpg -- the last stand-in R_SetSky
(engine gl/gl_warp.c) draws when a map's sky, r_skybox_default and HL2's sky_day01_01 are all missing.
Procedural, no source art: CC0, like everything this script writes. Deterministic for a given numpy/Pillow.
Usage: tools/wosdaysky.py [outdir]   (default ftesurf/gfx/env next to this tools/ folder)"""
import sys
from pathlib import Path
import numpy as np
from PIL import Image

N, SS = 1024, 2                     # face size, supersampling per axis
SUN_AZ, SUN_EL = 40.0, 38.0         # degrees; azimuth from +X toward +Y (Quake axes, Z up)
ZENITH = np.array([0.16, 0.36, 0.72])
HORIZON = np.array([0.72, 0.83, 0.94])
BELOW = np.array([0.44, 0.50, 0.57])
CLOUD_LIT = np.array([1.00, 0.985, 0.96])
CLOUD_SHADE = np.array([0.60, 0.65, 0.73])

# Face directions from (s, t), s = image right, t = image up, both -1..1. The Quake 2 / Half-Life layout,
# checked against valve/gfx/env/desert*.tga: every shared edge matches (mean |diff| 1-7 of 255, wrong order 21-37).
FACES = {
    'rt': lambda s, t: (np.ones_like(s), -s, t),
    'bk': lambda s, t: (s, np.ones_like(s), t),
    'lf': lambda s, t: (-np.ones_like(s), s, t),
    'ft': lambda s, t: (-s, -np.ones_like(s), t),
    'up': lambda s, t: (-t, -s, np.ones_like(s)),
    'dn': lambda s, t: (t, -s, -np.ones_like(s)),
}

rng = np.random.default_rng(1695)
PERM = rng.permutation(256)
ANG = rng.uniform(0, 2 * np.pi, 256)
GRAD = np.stack([np.cos(ANG), np.sin(ANG)], -1)


def perlin(x, y):
    xi, yi = np.floor(x), np.floor(y)
    xf, yf = x - xi, y - yi
    xi, yi = xi.astype(np.int64) & 255, yi.astype(np.int64) & 255

    def corner(ix, iy, dx, dy):
        g = GRAD[PERM[(PERM[ix & 255] + iy) & 255]]
        return g[..., 0] * dx + g[..., 1] * dy

    u = xf * xf * xf * (xf * (xf * 6 - 15) + 10)
    v = yf * yf * yf * (yf * (yf * 6 - 15) + 10)
    a = corner(xi, yi, xf, yf) + u * (corner(xi + 1, yi, xf - 1, yf) - corner(xi, yi, xf, yf))
    b = corner(xi, yi + 1, xf, yf - 1) + u * (corner(xi + 1, yi + 1, xf - 1, yf - 1) - corner(xi, yi + 1, xf, yf - 1))
    return a + v * (b - a)


def fbm(x, y, octaves=7):
    total, amp, freq = 0.0, 0.5, 1.0
    for o in range(octaves):
        c, s = np.cos(o * 1.7), np.sin(o * 1.7)         # rotate each octave so lattice axes do not line up
        total = total + amp * perlin(freq * (c * x - s * y) + 17.3 * o, freq * (s * x + c * y) - 9.1 * o)
        amp *= 0.5
        freq *= 2.03
    return total


def smoothstep(a, b, x):
    t = np.clip((x - a) / (b - a), 0, 1)
    return t * t * (3 - 2 * t)


def clouds(px, py):
    wx = fbm(px * 0.6 + 3.1, py * 0.6 - 7.7, 4)          # domain warp: billows instead of blobs
    wy = fbm(px * 0.6 - 5.3, py * 0.6 + 1.9, 4)
    n = fbm(px + 0.9 * wx, py + 0.9 * wy)
    return np.clip((n + 0.02) / 0.34, 0, 1) ** 1.3, n


def shade(dx, dy, dz):
    ln = np.sqrt(dx * dx + dy * dy + dz * dz)
    dx, dy, dz = dx / ln, dy / ln, dz / ln
    el, az = np.radians(SUN_EL), np.radians(SUN_AZ)
    sun = np.array([np.cos(el) * np.cos(az), np.cos(el) * np.sin(az), np.sin(el)])

    up = np.clip(dz, 0, 1)
    f = (1 - np.exp(-3.2 * up)) / (1 - np.exp(-3.2))
    sky = HORIZON + (ZENITH - HORIZON) * f[..., None]
    below = HORIZON + (BELOW - HORIZON) * (np.clip(-dz * 2.5, 0, 1) ** 0.7)[..., None]
    col = np.where((dz >= 0)[..., None], sky, below)

    # cloud layer: a plane above the eye, so clouds flatten and shrink toward the horizon
    h = 1.0 / np.maximum(dz + 0.12, 1e-3)               # below -0.12 the layer is invisible (alpha 0); keep it finite
    px, py = dx * h * 1.1, dy * h * 1.1
    dens, n = clouds(px, py)
    _, n_sun = clouds(px + sun[0] * 0.05, py + sun[1] * 0.05)
    lit = np.clip(0.55 + (n - n_sun) * 5.0, 0, 1)
    ccol = CLOUD_SHADE + (CLOUD_LIT - CLOUD_SHADE) * np.clip(lit * 0.75 + (1 - dens) * 0.35, 0, 1)[..., None]
    haze = 1 - smoothstep(0.0, 0.45, dz)
    ccol = ccol + (HORIZON - ccol) * (haze * 0.55)[..., None]
    alpha = dens * smoothstep(0.015, 0.22, dz)
    col = col + (ccol - col) * alpha[..., None]

    cosang = dx * sun[0] + dy * sun[1] + dz * sun[2]
    glow = 0.30 * np.exp((cosang - 1) * 14) + 0.30 * np.exp((cosang - 1) * 220)
    disc = smoothstep(0.99986, 0.99993, cosang) * 1.2
    col = col + (np.array([1.0, 0.95, 0.85]) * glow[..., None] * (1 - 0.6 * alpha)[..., None])
    col = col + disc[..., None] * (1 - 0.85 * alpha)[..., None]
    return np.clip(col, 0, 1)


def main():
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[1] / 'ftesurf/gfx/env'
    out.mkdir(parents=True, exist_ok=True)
    m = N * SS
    c = (np.arange(m) + 0.5) / m * 2 - 1
    s, t = np.meshgrid(c, -c)                            # row 0 is the top of the image (t = +1)
    dither = np.random.default_rng(95).uniform(-0.5, 0.5, (N, N, 3)) / 255
    for name, fn in FACES.items():
        img = shade(*fn(s, t)).reshape(N, SS, N, SS, 3).mean(axis=(1, 3)) + dither
        path = out / f'wos_day{name}.jpg'
        Image.fromarray(np.round(np.clip(img, 0, 1) * 255).astype(np.uint8)).save(path, quality=90, subsampling=0)
        print(path, path.stat().st_size)


if __name__ == '__main__':
    main()
