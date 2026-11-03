"""tools/rampwear.py -- P1278: bake where players ride and board a map's ramps into an overlay.

  python tools/rampwear.py --map NAME [--replays GLOB] [--gamedir ftesurf] [--texel 8] [--dry]

Writes <gamedir>/data/rampwear/<map>.txt (the ridden ramp surfaces' triangles, world coordinates,
atlas UVs, one normal each) and <gamedir>/textures/rampwear/<map>.png (the mask), which
cl_rampwear.qc draws with glsl/ftesurf_rampwear.glsl.  Mask channels, per texel of a chart
(a brush face, or a whole displacement in its own grid):
  R  ride wear: hull contacts swept tick to tick, log-scaled to the map's 99th percentile
  G  boarding scratch: each arrival on a ramp streaks along the travel direction, stronger and
     longer the steeper the impact (asin(|v.n| / |v|) of the pre-clip velocity; parallel = none)
  BA the travel direction in the shader's frame of the surface normal (frame() below: u level
     along the ramp, v down the slope), 0.5 + 0.5 * (u, v)

Contacts come from Momentum replays (.mtv, tools/momreplay.py) with tools/rampinfer.py's rule:
airborne pairs one tick apart, no teleport, vz pushed above the fall step.  The touched surface
is the steep one (0.05 < nz < 0.7) whose plane sits the hull's support offset below the origin
(16 * (|nx| + |ny|): measured 0..2 units on surf_classics3) with the support corner over it.
Only the world model's faces and the displacements: a brush entity may move; static props are
not read."""
import argparse
import collections
import glob
import lzma
import math
import os
import struct
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import momreplay  # noqa: E402
import rampinfer  # noqa: E402

MOMENTUM = r'C:\Program Files (x86)\Steam\steamapps\common\Momentum Mod Playtest\momentum'
HULL = 16.0             # player half width
RIDE_R = 10.0           # ride brush radius, units
EMPTY = (0, 0, 128, 128)


def dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def unit(a):
    l = math.sqrt(dot(a, a)) or 1.0
    return (a[0] / l, a[1] / l, a[2] / l)


def frame(n):
    """(u, v): u level along the ramp, v down the slope.  glsl/ftesurf_rampwear.glsl builds the same."""
    l = math.hypot(n[0], n[1]) or 1.0
    u = (-n[1] / l, n[0] / l, 0.0)
    return u, cross(n, u)


# ------------------------------------------------------------------ BSP
class Bsp:
    def __init__(self, path):
        self.d = open(path, 'rb').read()
        self.version = struct.unpack_from('<i', self.d, 4)[0]

    def lump(self, i):
        o, n, ver, cc = struct.unpack_from('<iiii', self.d, 8 + 16 * i)
        b = self.d[o:o + n]
        if b[:4] == b'LZMA':
            size, csize = struct.unpack_from('<II', b, 4)
            dec = lzma.LZMADecompressor(lzma.FORMAT_RAW, filters=[
                lzma._decode_filter_properties(lzma.FILTER_LZMA1, b[12:17])])
            b = dec.decompress(b[17:17 + csize])[:size]
        return b, ver


class Facet:
    """A plane polygon the hull can rest on: a brush face, or one displacement triangle."""
    def __init__(self, chart, n, d, poly, cc=None):
        self.chart, self.n, self.d, self.poly = chart, n, d, poly
        self.u, self.v = frame(n)
        self.p2 = [(dot(self.u, w), dot(self.v, w)) for w in poly]
        self.cc = cc            # chart coords of the three vertices (a displacement triangle)
        self.lo = [min(w[i] for w in poly) for i in range(3)]
        self.hi = [max(w[i] for w in poly) for i in range(3)]

    def to2(self, p):
        return (dot(self.u, p), dot(self.v, p))

    def chart_of(self, p):
        q = self.to2(p)
        if self.cc is None:
            return q
        (x0, y0), (x1, y1), (x2, y2) = self.p2
        det = (y1 - y2) * (x0 - x2) + (x2 - x1) * (y0 - y2) or 1e-9
        l0 = ((y1 - y2) * (q[0] - x2) + (x2 - x1) * (q[1] - y2)) / det
        l1 = ((y2 - y0) * (q[0] - x2) + (x0 - x2) * (q[1] - y2)) / det
        l2 = 1.0 - l0 - l1
        return (l0 * self.cc[0][0] + l1 * self.cc[1][0] + l2 * self.cc[2][0],
                l0 * self.cc[0][1] + l1 * self.cc[1][1] + l2 * self.cc[2][1])

    def dist_outside(self, q):
        """0 inside the (convex) polygon, else the distance to its boundary."""
        inside, best = True, 1e9
        m = len(self.p2)
        area = sum(self.p2[i][0] * self.p2[(i + 1) % m][1] - self.p2[(i + 1) % m][0] * self.p2[i][1] for i in range(m))
        sgn = 1.0 if area >= 0 else -1.0
        for i in range(m):
            (x0, y0), (x1, y1) = self.p2[i], self.p2[(i + 1) % m]
            ex, ey = x1 - x0, y1 - y0
            if sgn * (ex * (q[1] - y0) - ey * (q[0] - x0)) < 0:
                inside = False
            l2 = ex * ex + ey * ey or 1e-9
            t = max(0.0, min(1.0, ((q[0] - x0) * ex + (q[1] - y0) * ey) / l2))
            best = min(best, math.hypot(q[0] - x0 - t * ex, q[1] - y0 - t * ey))
        return 0.0 if inside else best


class Chart:
    """What is painted and drawn as one block of the atlas."""
    def __init__(self, key):
        self.key = key
        self.facets = []
        self.verts = []         # world positions
        self.vcc = []           # chart coords per vertex
        self.tris = []          # (i, j, k, normal)
        self.ride = []          # (u0, v0, u1, v1, du, dv): segment in chart coords, direction in the shader frame
        self.boards = []        # (u, v, cu, cv, du, dv, degrees): point, chart-space travel, shader-frame travel
        self.hits = 0


def steep(n):
    return 0.05 < n[2] < 0.7


def load_charts(bsp):
    planes, _ = bsp.lump(1)
    verts, _ = bsp.lump(3)
    faces, fver = bsp.lump(7)
    edges, ever = bsp.lump(12)
    surfedges, _ = bsp.lump(13)
    models, _ = bsp.lump(14)
    texinfo, _ = bsp.lump(6)
    texdata, _ = bsp.lump(2)
    strtab, _ = bsp.lump(44)
    strdat, _ = bsp.lump(43)
    dispinfo, dver = bsp.lump(26)
    dispverts, _ = bsp.lump(33)
    if bsp.version < 19:
        raise SystemExit('BSP v%d: face layout not read here' % bsp.version)
    wide = fver >= 2                                                       # mod_vbsp.c strata_dface_t
    fsz, ffmt = (72, '<IBBxxiiii') if wide else (56, '<HBBiHHH')
    esz, efmt = (8, '<II') if ever >= 1 else (4, '<HH')
    first, count = struct.unpack_from('<ii', models, 40)                  # model 0: the world

    def texname(ti):
        td = struct.unpack_from('<i', texinfo, ti * 72 + 68)[0]
        sid = struct.unpack_from('<i', texdata, td * 32 + 12)[0]
        o = struct.unpack_from('<i', strtab, sid * 4)[0]
        return strdat[o:strdat.index(b'\0', o)].decode('latin-1').lower()

    def face(f):
        pn, side, onnode, fe, ne, ti, di = struct.unpack_from(ffmt, faces, f * fsz)
        if not wide and di == 0xFFFF:
            di = -1
        n = struct.unpack_from('<fff', planes, pn * 20)
        dd = struct.unpack_from('<f', planes, pn * 20 + 12)[0]
        if side:
            n, dd = (-n[0], -n[1], -n[2]), -dd
        poly = []
        for k in range(ne):
            se = struct.unpack_from('<i', surfedges, (fe + k) * 4)[0]
            a, b = struct.unpack_from(efmt, edges, abs(se) * esz)
            poly.append(struct.unpack_from('<fff', verts, (a if se >= 0 else b) * 12))
        return n, dd, poly, ti, di

    def drawn(ti):
        if ti < 0 or ti == 0xFFFF:
            return False
        flags = struct.unpack_from('<i', texinfo, ti * 72 + 64)[0]
        return not (flags & (0x4 | 0x80 | 0x200)) and not texname(ti).startswith('tools/')   # sky, nodraw, skip

    charts = []
    for f in range(first, first + count):
        n, dd, poly, ti, di = face(f)
        if di >= 0 or not steep(n) or len(poly) < 3 or not drawn(ti):
            continue
        c = Chart(('f', f))
        fa = Facet(c, n, dd, poly)
        c.facets.append(fa)
        c.verts = list(poly)
        c.vcc = list(fa.p2)
        for j in range(1, len(poly) - 1):
            c.tris.append((0, j, j + 1, n))
        charts.append(c)

    # displacements: vertices exactly as VBSP_LoadDisplacements builds them
    dstride = 232 if dver >= 1 else 176
    ndisp = 0
    for i in range(len(dispinfo) // dstride):
        o = i * dstride
        pos = struct.unpack_from('<fff', dispinfo, o)
        firstvert, power = struct.unpack_from('<i', dispinfo, o + 12)[0], struct.unpack_from('<i', dispinfo, o + 20)[0]
        fidx = struct.unpack_from('<I' if dver >= 1 else '<H', dispinfo, o + 36)[0]
        n0, dd, poly, ti, di = face(fidx)
        if len(poly) != 4 or not drawn(ti) or not (0 <= power <= 4):
            continue
        prim = min(range(4), key=lambda x: dot(sub(poly[x], pos), sub(poly[x], pos)))
        sv = [poly[(prim + k) & 3] for k in range(4)]
        w = 1 << power
        xyz = []
        for y in range(w + 1):
            for x in range(w + 1):
                fx, fy = x / w, y / w
                base = [(1 - fx) * (1 - fy) * sv[0][k] + (1 - fx) * fy * sv[1][k] + fx * fy * sv[2][k] + fx * (1 - fy) * sv[3][k] for k in range(3)]
                vn = struct.unpack_from('<ffff', dispverts, (firstvert + len(xyz)) * 20)
                xyz.append((base[0] + vn[0] * vn[3], base[1] + vn[1] * vn[3], base[2] + vn[2] * vn[3]))
        P = lambda x, y: xyz[y * (w + 1) + x]
        sx = sum(math.dist(P(x, y), P(x + 1, y)) for y in range(w + 1) for x in range(w)) / ((w + 1) * w)
        sy = sum(math.dist(P(x, y), P(x, y + 1)) for x in range(w + 1) for y in range(w)) / ((w + 1) * w)
        c = Chart(('d', i))
        c.verts = xyz
        c.vcc = [(x * sx, y * sy) for y in range(w + 1) for x in range(w + 1)]
        for y in range(w):
            for x in range(w):
                q = lambda a, b: b * (w + 1) + a
                if (x + y) & 1:
                    tri2 = ((q(x, y + 1), q(x + 1, y + 1), q(x + 1, y)), (q(x, y + 1), q(x + 1, y), q(x, y)))
                else:
                    tri2 = ((q(x, y), q(x, y + 1), q(x + 1, y + 1)), (q(x, y), q(x + 1, y + 1), q(x + 1, y)))
                for (ia, ib, ic) in tri2:
                    a, b, cc = xyz[ia], xyz[ib], xyz[ic]
                    nn = unit(cross(sub(b, a), sub(cc, a)))
                    if dot(nn, n0) < 0:     # outward, as the base face's (side-corrected) normal
                        nn = (-nn[0], -nn[1], -nn[2])
                    if not steep(nn):
                        continue
                    fa = Facet(c, nn, dot(nn, a), [a, b, cc], [c.vcc[ia], c.vcc[ib], c.vcc[ic]])
                    c.facets.append(fa)
                    c.tris.append((ia, ib, ic, nn))
        if c.facets:
            charts.append(c)
            ndisp += 1
    return charts, ndisp


class Grid:
    def __init__(self, facets, cell=512.0):
        self.cell, self.g = cell, collections.defaultdict(list)
        for f in facets:
            for cx in range(int(math.floor((f.lo[0] - 32) / cell)), int(math.floor((f.hi[0] + 32) / cell)) + 1):
                for cy in range(int(math.floor((f.lo[1] - 32) / cell)), int(math.floor((f.hi[1] + 32) / cell)) + 1):
                    self.g[(cx, cy)].append(f)

    def near(self, p):
        return self.g.get((int(math.floor(p[0] / self.cell)), int(math.floor(p[1] / self.cell))), ())


def touched(grid, o):
    """(facet, support point) the hull at origin o rests on, or (None, None)."""
    best = None
    for f in grid.near(o):
        if not (f.lo[2] - 80 <= o[2] <= f.hi[2] + 80):
            continue
        n = f.n
        gap = dot(n, o) - f.d - HULL * (abs(n[0]) + abs(n[1]))
        if not (-1.5 <= gap <= 3.0):
            continue
        c = (o[0] - math.copysign(HULL, n[0]) if abs(n[0]) > 1e-3 else o[0],
             o[1] - math.copysign(HULL, n[1]) if abs(n[1]) > 1e-3 else o[1], o[2])
        out = min(f.dist_outside(f.to2(c)), f.dist_outside(f.to2(o)))
        if out > HULL:
            continue
        key = (out > 0, abs(gap))
        if best is None or key < best[0]:
            best = (key, f, c)
    return (best[1], best[2]) if best else (None, None)


# ------------------------------------------------------------------ replays
def bake_replay(path, grid, stats):
    try:
        r = momreplay.parse(path)
    except Exception as ex:     # an unreadable replay is counted, never fatal
        stats['unreadable'] += 1
        stats['unreadable_' + type(ex).__name__] += 1
        return
    t, dt = r['ticks'], r['tick_interval']
    if len(t) < 3 or not dt:
        stats['short'] += 1
        return
    ok = [False]
    for a, b in zip(t, t[1:]):
        ok.append(b.tick - a.tick == 1 and not ((a.flags | b.flags) & 1) and
                  (a.noint is None or a.noint == b.noint) and
                  not rampinfer.snap((a.x, a.y, a.z), (a.vx, a.vy, a.vz), (b.x, b.y, b.z), (b.vx, b.vy, b.vz), dt))
    falls = collections.Counter(int(math.floor((t[i - 1].vz - t[i].vz) * 100 + 0.5)) for i in range(1, len(t)) if ok[i])
    falls = {k: c for k, c in falls.items() if 1 <= k <= rampinfer.HMAX}
    if not falls:
        stats['nofall'] += 1
        return
    top = max(falls.values())
    step = min(k for k, c in falls.items() if c == top) / 100.0
    stats['replays'] += 1
    prev = None             # (chart, chart point) of the previous tick's placed contact
    was = False             # the previous tick was a contact, placed or not: no arrival
    for i in range(1, len(t)):
        a, b = t[i - 1], t[i]
        contact = False
        if ok[i]:
            rr = (b.vz - a.vz) + step
            contact = rr > rampinfer.EPS and not (rr > rampinfer.FLAT * step and math.hypot(b.vx - a.vx, b.vy - a.vy) < rampinfer.FLATH)
        if not contact:
            prev, was = None, False
            continue
        stats['contacts'] += 1
        o = (b.x, b.y, b.z)
        f, c = touched(grid, o)
        arrival = not was
        was = True
        if f is None:
            prev = None
            continue
        ch = f.chart
        stats['placed'] += 1
        stats['placed_' + ch.key[0]] += 1
        ch.hits += 1
        q = f.chart_of(c)
        vel = (b.vx, b.vy, b.vz)
        vt = (dot(f.u, vel), dot(f.v, vel))
        l = math.hypot(vt[0], vt[1]) or 1.0
        dirn = (vt[0] / l, vt[1] / l)                       # shader frame
        ahead = f.chart_of((c[0] + vel[0] * 0.01, c[1] + vel[1] * 0.01, c[2] + vel[2] * 0.01))
        cd = (ahead[0] - q[0], ahead[1] - q[1])
        l = math.hypot(cd[0], cd[1]) or 1.0
        cdir = (cd[0] / l, cd[1] / l)                       # chart space
        if prev is not None and prev[0] is ch:
            ch.ride.append((prev[1][0], prev[1][1], q[0], q[1], dirn[0], dirn[1]))
        else:
            ch.ride.append((q[0], q[1], q[0], q[1], dirn[0], dirn[1]))
            if arrival:         # the tick before was in the air
                vpre = (a.vx, a.vy, a.vz - 0.5 * step)
                sp = math.sqrt(dot(vpre, vpre)) or 1.0
                vn = dot(vpre, f.n)
                ang = math.degrees(math.asin(min(1.0, -vn / sp))) if vn < 0 else 0.0
                stats['boards'] += 1
                stats['board_deg_%d' % min(30, int(ang // 5) * 5)] += 1
                ch.boards.append((q[0], q[1], cdir[0], cdir[1], dirn[0], dirn[1], ang))
        prev = (ch, q)


# ------------------------------------------------------------------ mask
def board_strength(ang):
    """Parallel boarding (~0 deg) leaves nothing; 20 deg or more is a full scratch."""
    return max(0.0, min(1.0, (ang - 1.5) / 18.5))


def paint(ch, texel):
    us = [p[0] for p in ch.vcc]
    vs = [p[1] for p in ch.vcc]
    u0, v0 = min(us) - 2 * texel, min(vs) - 2 * texel
    w = int(math.ceil((max(us) - u0) / texel)) + 3
    h = int(math.ceil((max(vs) - v0) / texel)) + 3
    ride = np.zeros((h, w), np.float32)
    scr = np.zeros((h, w), np.float32)
    dsum = np.zeros((h, w, 2), np.float32)
    yy, xx = np.mgrid[0:h, 0:w]
    cu = u0 + (xx + 0.5) * texel
    cv = v0 + (yy + 0.5) * texel

    def capsule(a, b, r):
        ax, ay, bx, by = a[0], a[1], b[0], b[1]
        ex, ey = bx - ax, by - ay
        l2 = ex * ex + ey * ey
        x0, x1 = int((min(ax, bx) - r - u0) / texel) - 1, int((max(ax, bx) + r - u0) / texel) + 2
        y0, y1 = int((min(ay, by) - r - v0) / texel) - 1, int((max(ay, by) + r - v0) / texel) + 2
        x0, y0, x1, y1 = max(0, x0), max(0, y0), min(w, x1), min(h, y1)
        if x0 >= x1 or y0 >= y1:
            return None, None
        su, sv = cu[y0:y1, x0:x1], cv[y0:y1, x0:x1]
        tt = np.clip(((su - ax) * ex + (sv - ay) * ey) / l2, 0, 1) if l2 > 1e-6 else np.zeros_like(su)
        return (slice(y0, y1), slice(x0, x1)), (np.hypot(su - ax - tt * ex, sv - ay - tt * ey), tt)

    for (a0, a1, b0, b1, du, dv) in ch.ride:
        sl, g = capsule((a0, a1), (b0, b1), RIDE_R + texel)
        if sl is None:
            continue
        wgt = np.clip(1.0 - g[0] / (RIDE_R + texel), 0, 1)
        ride[sl] += wgt
        dsum[sl][..., 0] += wgt * du
        dsum[sl][..., 1] += wgt * dv
    for (bu, bv, cdu, cdv, du, dv, ang) in ch.boards:
        s = board_strength(ang)
        if s <= 0:
            continue
        length = 48 + 420 * s
        width = 12 + 14 * s
        sl, g = capsule((bu, bv), (bu + cdu * length, bv + cdv * length), width)
        if sl is None:
            continue
        dist, tt = g
        val = s * np.clip(1.0 - dist / width, 0, 1) * (1.0 - 0.85 * tt)
        scr[sl] = np.maximum(scr[sl], val)
        dsum[sl][..., 0] += 4 * val * du
        dsum[sl][..., 1] += 4 * val * dv
    return dict(u0=u0, v0=v0, w=w, h=h, ride=ride, scr=scr, dsum=dsum)


def pack(charts, maxw):
    """Shelf packing, tallest first: ({key: (x, y)}, width, height)."""
    order = sorted(charts, key=lambda k: -charts[k]['h'])
    x = y = shelf = 0
    pos = {}
    for k in order:
        c = charts[k]
        if x + c['w'] > maxw:
            x, y, shelf = 0, y + shelf, 0
        pos[k] = (x, y)
        x += c['w']
        shelf = max(shelf, c['h'])
    return pos, maxw, y + shelf


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('--map', required=True)
    ap.add_argument('--replays', help='glob of .mtv files (default: Momentum momtv/*/<map>/*.mtv)')
    ap.add_argument('--bsp', help='default: Momentum maps/<map>.bsp')
    ap.add_argument('--gamedir', default=os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'ftesurf'))
    ap.add_argument('--texel', type=float, default=8.0, help='units per mask texel')
    ap.add_argument('--minhits', type=int, default=3, help='contacts a chart needs to carry wear')
    ap.add_argument('--grow', type=int, default=3, help='rings of touching steep surfaces drawn dirty without wear')
    ap.add_argument('--dry', action='store_true')
    a = ap.parse_args()

    bsp = Bsp(a.bsp or os.path.join(MOMENTUM, 'maps', a.map + '.bsp'))
    charts, ndisp = load_charts(bsp)
    grid = Grid([f for c in charts for f in c.facets])
    files = sorted(glob.glob(a.replays or os.path.join(MOMENTUM, 'momtv', '*', a.map, '*.mtv')))
    if not files:
        raise SystemExit('no replays for %s' % a.map)
    stats = collections.Counter()
    for fn in files:
        bake_replay(fn, grid, stats)
    used = [c for c in charts if c.hits >= a.minhits]
    # the rest of a ridden ramp: steep surfaces sharing a vertex with a drawn one, a.grow rings out
    vkey = lambda v: (round(v[0]), round(v[1]), round(v[2]))
    byv = collections.defaultdict(set)
    for i, c in enumerate(charts):
        for v in c.verts:
            byv[vkey(v)].add(i)
    drawn = set(i for i, c in enumerate(charts) if c.hits >= a.minhits)
    ring = set(drawn)
    for _ in range(a.grow):
        ring = set(j for i in ring for v in charts[i].verts for j in byv[vkey(v)]) - drawn
        drawn |= ring
    plain = [charts[i] for i in sorted(drawn) if charts[i].hits < a.minhits]
    print('%s: %d replays (%d read), %d contact ticks, %d placed (%d on brush faces, %d on displacements); '
          '%d of %d surfaces drawn (%d displacements of %d), %d boardings' % (
              a.map, len(files), stats['replays'], stats['contacts'], stats['placed'], stats['placed_f'], stats['placed_d'],
              len(used), len(charts), sum(1 for c in used if c.key[0] == 'd'), ndisp, stats['boards']))
    print('boarding angle, 5-degree bins:', ' '.join('%d:%d' % (k, stats['board_deg_%d' % k]) for k in range(0, 35, 5)))
    for k in sorted(stats):
        if k.startswith('unreadable_'):
            print('unreadable replays:', k[11:], stats[k])
    if not used:
        raise SystemExit('nothing to draw')

    texel = a.texel
    while True:
        painted = {c.key: paint(c, texel) for c in used}
        painted[('empty',)] = dict(u0=0, v0=0, w=4, h=4, ride=np.zeros((4, 4), np.float32),
                                   scr=np.zeros((4, 4), np.float32), dsum=np.zeros((4, 4, 2), np.float32))
        pos, W, H = pack(painted, 2048)
        if H <= 4096:
            break
        texel *= 1.25
        print('atlas %dx%d too tall; texel %.1f' % (W, H, texel))
    allride = np.concatenate([p['ride'][p['ride'] > 0] for p in painted.values()] or [np.zeros(1)])
    p99 = float(np.percentile(allride, 99)) if allride.size else 1.0
    img = np.zeros((H, W, 4), np.uint8)
    img[...] = EMPTY
    for k, p in painted.items():
        x, y = pos[k]
        wear = np.clip(np.log1p(p['ride']) / math.log1p(max(p99, 1e-3)), 0, 1)
        dl = np.hypot(p['dsum'][..., 0], p['dsum'][..., 1])
        du = np.where(dl > 1e-4, p['dsum'][..., 0] / np.maximum(dl, 1e-4), 0.0)
        dv = np.where(dl > 1e-4, p['dsum'][..., 1] / np.maximum(dl, 1e-4), 0.0)
        tile = np.stack([wear * 255, p['scr'] * 255, (0.5 + 0.5 * du) * 255, (0.5 + 0.5 * dv) * 255], -1)
        img[y:y + p['h'], x:x + p['w']] = np.clip(tile + 0.5, 0, 255).astype(np.uint8)
    print('atlas %dx%d, texel %.1f units, ride p99 %.1f, scratch texels %d; %d unridden neighbours drawn dirty' % (
        W, H, texel, p99, int(sum((p['scr'] > 0.05).sum() for p in painted.values())), len(plain)))

    # data/rampwear/<map>.txt, read by cl_rampwear.qc:
    #   rampwear 1 <map> <surfaces> <triangles>
    #   c <cx> <cy> <cz> <radius> <triangles>             a surface, its triangles follow
    #   t <x y z s t> x3 <nx ny nz>                       s, t in the atlas, t from the top
    ex, ey = pos[('empty',)]
    lines = ['rampwear 1 %s %d %d' % (a.map, len(used) + len(plain), sum(len(c.tris) for c in used + plain))]
    for c in used + plain:
        if c.key in painted:
            p = painted[c.key]
            x, y = pos[c.key]
            st = [((x + (pu - p['u0']) / texel) / W, (y + (pv - p['v0']) / texel) / H) for (pu, pv) in c.vcc]
        else:       # dirt only: every corner on the empty block's centre
            st = [((ex + 2.0) / W, (ey + 2.0) / H)] * len(c.verts)
        cen = [sum(v[i] for v in c.verts) / len(c.verts) for i in range(3)]
        rad = max(math.dist(cen, v) for v in c.verts)
        lines.append('c %.1f %.1f %.1f %.1f %d' % (cen[0], cen[1], cen[2], rad, len(c.tris)))
        for (i0, i1, i2, n) in c.tris:
            lines.append('t ' + ' '.join('%.3f %.3f %.3f %.5f %.5f' % (c.verts[k] + st[k]) for k in (i0, i1, i2)) +
                         ' %.4f %.4f %.4f' % n)
    if a.dry:
        print('dry run: nothing written')
        return
    from PIL import Image
    ddir = os.path.join(a.gamedir, 'data', 'rampwear')
    tdir = os.path.join(a.gamedir, 'textures', 'rampwear')
    os.makedirs(ddir, exist_ok=True)
    os.makedirs(tdir, exist_ok=True)
    with open(os.path.join(ddir, a.map + '.txt'), 'w', newline='\n') as fh:
        fh.write('\n'.join(lines) + '\n')
    Image.fromarray(img, 'RGBA').save(os.path.join(tdir, a.map + '.png'))
    print('wrote', os.path.join(ddir, a.map + '.txt'), 'and', os.path.join(tdir, a.map + '.png'),
          '(%d triangles)' % sum(len(c.tris) for c in used + plain))


if __name__ == '__main__':
    main()
