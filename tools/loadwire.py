#!/usr/bin/env python3
"""P1453: the loading screen's map wireframes, taken from the map's own model files.

    python tools/loadwire.py --maps <dir of .bsp> [--picks tools/loadwire_picks.txt] [--out ftesurf/gfx/loadwire]
    python tools/loadwire.py --maps <dir> --suggest [--limit 40]

A pick is `<map> <model path> [flip]` (several lines for one map: the loading screen takes one at random;
`flip` turns it upside down, for a model stood up head-down -- see STAND_UP). The model
is read from the map's pakfile (or --content dirs), LOD 0 of every body part's first model, welded, simplified by
quadric edge collapse to at most --tris triangles, and written as gfx/loadwire/<map>.txt (m_loading.qc reads it):

    FTESURF-LOADWIRE 2
    model <path>
    closed 0|1       (1: every edge has two triangles, wound outward -- the menu culls back faces)
    v x y z          (centred on the box, longest side 62 units: the lobby avatar's height)
    t a b c f        (triangles, vertex indices; f: 1 edge ab drawn, 2 bc, 4 ca, 8 faces against its node's plane)
    n x y z d f b i c  (BSP nodes, root first: plane normal and distance, front and back child (-1 none), and the
                      triangles i..i+c-1 lying in that plane)

The menu draws the triangles back to front by walking the tree (exact from any side, so no two lines fight as
the model turns): each one's black fill, then its drawn edges.  Triangles that crossed a splitting plane are
clipped into pieces that keep their edges' flags; the cuts are never drawn.  An edge is drawn on a border or
where its two faces bend more than --flat degrees.

No blank lines: the menu's fgets reads one as the end of the file.

--suggest lists, for maps whose pakfile carries models, the most-placed custom model (static props and
prop_dynamic entities) and its triangle count, to choose picks from.
"""
import argparse
import io
import math
import os
import re
import struct
import sys
import zipfile
from collections import Counter, defaultdict

LUMP_ENTITIES, LUMP_GAME, LUMP_PAK = 0, 35, 40
QC_V, QC_T, QC_N = 1024, 1024, 1024   # m_loading.qc LW_V, LW_T, LW_N: over any, the model is simplified further
BSP_EPS = 0.01
STAND_UP = 0.3           # a model this flat (height / width) is turned 90 degrees about x to stand up: butterfly, donut
TARGET_SIZE = 62.0


class ModelError(Exception):
    pass


def pakfile(bsp):
    off, size = struct.unpack_from('<ii', bsp, 8 + LUMP_PAK * 16)
    if size <= 0:
        return None
    return zipfile.ZipFile(io.BytesIO(bsp[off:off + size]))


def lump(bsp, i):
    import lzma
    off, size, ver, unc = struct.unpack_from('<iiii', bsp, 8 + i * 16)
    blob = bsp[off:off + size]
    if unc and blob[:4] == b'LZMA':
        actual = struct.unpack_from('<I', blob, 4)[0]
        props = blob[12:17]
        d = props[0]
        dec = lzma.LZMADecompressor(lzma.FORMAT_RAW, filters=[{
            'id': lzma.FILTER_LZMA1, 'lc': d % 9, 'lp': (d // 9) % 5, 'pb': d // 45,
            'dict_size': struct.unpack_from('<I', props, 1)[0]}])
        blob = dec.decompress(blob[17:], actual)[:actual]
    return blob


class Files:
    """The map's pakfile, then each --content directory."""
    def __init__(self, pak, dirs):
        self.pak = pak
        self.names = {i.filename.lower().replace('\\', '/'): i for i in pak.infolist()} if pak else {}
        self.dirs = dirs

    def read(self, path):
        p = path.lower().replace('\\', '/')
        if p in self.names:
            return self.pak.read(self.names[p])
        for d in self.dirs:
            f = os.path.join(d, p)
            if os.path.isfile(f):
                return open(f, 'rb').read()
        return None


def triangles(files, path):
    """LOD 0 of every body part's first model: (positions, [(a,b,c)]) in model space."""
    mdl = files.read(path)
    if not mdl or mdl[:4] != b'IDST':
        raise ModelError('no model ' + path)
    ver = struct.unpack_from('<i', mdl, 4)[0]
    stem = path[:-4]
    vvd = files.read(stem + '.vvd')
    vtx = None
    for ext in ('.dx90.vtx', '.dx80.vtx', '.vtx', '.sw.vtx'):
        vtx = files.read(stem + ext)
        if vtx:
            break
    if not vvd or vvd[:4] != b'IDSV' or not vtx:
        raise ModelError('no vvd/vtx for ' + path)
    # VVD: LOD 0's vertices, through the fixup table when there is one.
    nfix, fixstart, vstart = struct.unpack_from('<iii', vvd, 48)
    nlod0 = struct.unpack_from('<i', vvd, 16)[0]
    raw = lambda i: struct.unpack_from('<3f', vvd, vstart + i * 48 + 16)
    if nfix:
        pos = []
        for k in range(nfix):
            lod, src, n = struct.unpack_from('<iii', vvd, fixstart + k * 12)
            if lod >= 0:
                pos.extend(raw(src + j) for j in range(n))
    else:
        pos = [raw(i) for i in range(nlod0)]
    # MDL body parts -> models -> meshes, with VTX alongside.
    nbody, bodyofs = struct.unpack_from('<ii', mdl, 232)
    vtx_nbody, vtx_bodyofs = struct.unpack_from('<ii', vtx, 28)
    if vtx_nbody != nbody:
        raise ModelError('vtx/mdl body parts differ ' + path)
    tris = []
    for b in range(nbody):
        mb = bodyofs + b * 16
        nmodels, _base, mofs = struct.unpack_from('<iii', mdl, mb + 4)
        if nmodels <= 0:
            continue
        mm = mb + mofs                               # first model only (body group 0)
        nmesh, meshofs = struct.unpack_from('<ii', mdl, mm + 72)
        vbase = struct.unpack_from('<i', mdl, mm + 84)[0] // 48
        vb = vtx_bodyofs + b * 8
        vn_models, vmofs = struct.unpack_from('<ii', vtx, vb)
        vm = vb + vmofs
        nlods, lodofs = struct.unpack_from('<ii', vtx, vm)
        vl = vm + lodofs                             # LOD 0
        vnmesh, vmeshofs = struct.unpack_from('<ii', vtx, vl)
        for m in range(min(nmesh, vnmesh)):
            mesh = mm + meshofs + m * 116
            moff = struct.unpack_from('<i', mdl, mesh + 12)[0]
            vme = vl + vmeshofs + m * 9
            nsg, sgofs = struct.unpack_from('<ii', vtx, vme)
            stride = 33 if ver >= 49 and _sg_wide(vtx, vme + sgofs, nsg) else 25
            for g in range(nsg):
                sg = vme + sgofs + g * stride
                nv, vofs, ni, iofs = struct.unpack_from('<iiii', vtx, sg)
                verts = [struct.unpack_from('<H', vtx, sg + vofs + k * 9 + 4)[0] for k in range(nv)]
                idx = struct.unpack_from('<%dH' % ni, vtx, sg + iofs)
                for k in range(0, ni - 2, 3):
                    a, c, d = (vbase + moff + verts[idx[k + j]] for j in range(3))
                    if max(a, c, d) < len(pos):
                        tris.append((a, c, d))
    if not tris:
        raise ModelError('no triangles in ' + path)
    return pos, tris


def _sg_wide(vtx, start, n):
    """CS:GO-era strip groups carry two more ints (33 bytes); pick the stride whose counts make sense."""
    if n <= 1:
        return False
    nv, vofs, ni, iofs = struct.unpack_from('<iiii', vtx, start + 25)
    return not (0 <= nv < 65536 and 0 <= ni < 1 << 20 and 0 < vofs < 1 << 24)


def weld(pos, tris):
    """Merge vertices at one position (Source splits them by UV and normal); drop degenerate and repeated triangles."""
    key, verts, remap = {}, [], []
    for p in pos:
        k = (round(p[0], 3), round(p[1], 3), round(p[2], 3))
        if k not in key:
            key[k] = len(verts)
            verts.append(p)
        remap.append(key[k])
    seen, out = set(), []
    for t in tris:
        a, b, c = remap[t[0]], remap[t[1]], remap[t[2]]
        if a == b or b == c or a == c:
            continue
        s = tuple(sorted((a, b, c)))
        if s not in seen:
            seen.add(s)
            out.append((a, b, c))
    return verts, out


def _plane(v, t):
    a, b, c = (v[i] for i in t)
    u = [b[i] - a[i] for i in range(3)]
    w = [c[i] - a[i] for i in range(3)]
    n = [u[1] * w[2] - u[2] * w[1], u[2] * w[0] - u[0] * w[2], u[0] * w[1] - u[1] * w[0]]
    l = math.sqrt(sum(x * x for x in n))
    if l < 1e-12:
        return None, 0.0
    n = [x / l for x in n]
    return n + [-sum(n[i] * a[i] for i in range(3))], l * 0.5


def _quad(pl, w):
    return [w * pl[i] * pl[j] for i in range(4) for j in range(4)]


def _cost(q, p):
    x = (p[0], p[1], p[2], 1.0)
    return sum(q[i * 4 + j] * x[i] * x[j] for i in range(4) for j in range(4))


def simplify(pos, tris, target):
    """Quadric edge collapse (Garland-Heckbert) to at most `target` triangles: borders weighted so a wing's
    outline stays, a collapse that would flip a triangle refused. A mesh already that small is only welded."""
    import heapq
    v, faces = weld(pos, tris)
    if len(faces) <= target:
        return v, faces
    v = [list(p) for p in v]
    q = [[0.0] * 16 for _ in v]
    vf = [set() for _ in v]
    alive = [True] * len(faces)
    faces = [list(f) for f in faces]
    for fi, f in enumerate(faces):
        pl, area = _plane(v, f)
        if pl is None:
            continue
        qq = _quad(pl, max(area, 1e-6))
        for i in f:
            q[i] = [q[i][k] + qq[k] for k in range(16)]
            vf[i].add(fi)
    # Border edges: a plane through the edge, perpendicular to its face, heavily weighted.
    cnt = defaultdict(list)
    for fi, f in enumerate(faces):
        for a_, b_ in ((f[0], f[1]), (f[1], f[2]), (f[2], f[0])):
            cnt[(min(a_, b_), max(a_, b_))].append(fi)
    for (a_, b_), fs in cnt.items():
        if len(fs) != 1:
            continue
        n, _ = _plane(v, faces[fs[0]])
        if n is None:
            continue
        e = [v[b_][i] - v[a_][i] for i in range(3)]
        bn = [e[1] * n[2] - e[2] * n[1], e[2] * n[0] - e[0] * n[2], e[0] * n[1] - e[1] * n[0]]
        l = math.sqrt(sum(x * x for x in bn)) or 1.0
        bn = [x / l for x in bn]
        pl = bn + [-sum(bn[i] * v[a_][i] for i in range(3))]
        qq = _quad(pl, 1000.0 * (sum(x * x for x in e) or 1.0))
        for i in (a_, b_):
            q[i] = [q[i][k] + qq[k] for k in range(16)]
    stamp = [0] * len(v)
    heap = []

    def push(a_, b_):
        qs = [q[a_][k] + q[b_][k] for k in range(16)]
        mid = [(v[a_][i] + v[b_][i]) * 0.5 for i in range(3)]
        best = min(((_cost(qs, c), c) for c in (v[a_], v[b_], mid)), key=lambda x: x[0])
        heapq.heappush(heap, (best[0], a_, b_, stamp[a_], stamp[b_], tuple(best[1])))

    for (a_, b_) in cnt:
        push(a_, b_)
    live = sum(alive)
    while live > target and heap:
        c_, a_, b_, sa, sb, p = heapq.heappop(heap)
        if stamp[a_] != sa or stamp[b_] != sb or a_ == b_:
            continue
        # Refuse a collapse that would flip a surviving triangle.
        ok = True
        for fi in vf[a_] | vf[b_]:
            if not alive[fi]:
                continue
            f = faces[fi]
            if a_ in f and b_ in f:
                continue
            n0, _ = _plane(v, f)
            g = [(list(p) if (i == a_ or i == b_) else v[i]) for i in f]
            n1, _ = _plane(g, (0, 1, 2))
            if n0 is None or n1 is None or sum(n0[i] * n1[i] for i in range(3)) < 0.2:
                ok = False
                break
        if not ok:
            continue
        v[a_] = list(p)
        q[a_] = [q[a_][k] + q[b_][k] for k in range(16)]
        for fi in list(vf[b_]):
            if not alive[fi]:
                continue
            f = faces[fi]
            if a_ in f:
                alive[fi] = False
                live -= 1
                for i in f:
                    vf[i].discard(fi)
                continue
            f[f.index(b_)] = a_
            vf[a_].add(fi)
        vf[b_].clear()
        stamp[a_] += 1
        stamp[b_] += 1
        nb = set()
        for fi in vf[a_]:
            if alive[fi]:
                nb.update(faces[fi])
        nb.discard(a_)
        for o in nb:
            push(min(a_, o), max(a_, o))
    out = [tuple(f) for fi, f in enumerate(faces) if alive[fi]]
    used = sorted({i for t in out for i in t})
    re_ = {o: n for n, o in enumerate(used)}
    return [tuple(v[i]) for i in used], [(re_[a_], re_[b_], re_[c_]) for a_, b_, c_ in out]


def normal(v, t):
    a, b, c = (v[i] for i in t)
    u = [b[i] - a[i] for i in range(3)]
    w = [c[i] - a[i] for i in range(3)]
    n = [u[1] * w[2] - u[2] * w[1], u[2] * w[0] - u[0] * w[2], u[0] * w[1] - u[1] * w[0]]
    l = math.sqrt(sum(x * x for x in n)) or 1.0
    return [x / l for x in n]


def _sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def orient(v, tris):
    """Consistent winding per connected part, each part turned outward by its signed volume.
    -> (tris, closed, by): closed when every edge has two triangles and the winding could be made consistent."""
    tris = [list(t) for t in tris]
    by = defaultdict(list)
    for ti, t in enumerate(tris):
        for a, b in ((t[0], t[1]), (t[1], t[2]), (t[2], t[0])):
            by[(min(a, b), max(a, b))].append(ti)
    closed = all(len(ts) == 2 for ts in by.values())
    seen = [False] * len(tris)

    def runs(t, a, b):          # t has the directed edge a->b
        return any(t[k] == a and t[(k + 1) % 3] == b for k in range(3))

    for s0 in range(len(tris)):
        if seen[s0]:
            continue
        seen[s0] = True
        part, stack = [s0], [s0]
        while stack:
            t = tris[stack.pop()]
            for a, b in ((t[0], t[1]), (t[1], t[2]), (t[2], t[0])):
                for tj in by[(min(a, b), max(a, b))]:
                    u = tris[tj]
                    if u is t:
                        continue
                    if not seen[tj]:
                        if runs(u, a, b):
                            u[1], u[2] = u[2], u[1]
                        seen[tj] = True
                        part.append(tj)
                        stack.append(tj)
                    elif runs(u, a, b):
                        closed = False      # not orientable: draw both sides
        vol = sum(_dot(v[tris[k][0]], _cross(v[tris[k][1]], v[tris[k][2]])) for k in part)
        if vol < 0:
            for k in part:
                tris[k][1], tris[k][2] = tris[k][2], tris[k][1]
    return tris, closed, by


def edge_flags(v, tris, by, flat_deg):
    """Per triangle, which of ab, bc, ca is drawn: a border, or a bend of more than flat_deg."""
    cosflat = math.cos(math.radians(flat_deg))
    out = []
    for ti, t in enumerate(tris):
        f = 0
        for bit, (a, b) in ((1, (t[0], t[1])), (2, (t[1], t[2])), (4, (t[2], t[0]))):
            ts = by[(min(a, b), max(a, b))]
            if len(ts) != 2 or ti not in ts:
                f |= bit
                continue
            o = tris[ts[0] if ts[1] == ti else ts[1]]
            c = _dot(normal(v, t), normal(v, o))
            if not any(o[k] == b and o[(k + 1) % 3] == a for k in range(3)):
                c = -c          # the pair could not be made consistent: compare as if it were
            if c < cosflat:
                f |= bit
        out.append(f)
    return out


def _poly_plane(pts):
    n = [0.0, 0.0, 0.0]
    for k in range(len(pts)):             # Newell
        a, b = pts[k], pts[(k + 1) % len(pts)]
        n[0] += (a[1] - b[1]) * (a[2] + b[2])
        n[1] += (a[2] - b[2]) * (a[0] + b[0])
        n[2] += (a[0] - b[0]) * (a[1] + b[1])
    l = math.sqrt(_dot(n, n))
    if l < 1e-9:
        return None
    n = (n[0] / l, n[1] / l, n[2] / l)
    return n, sum(_dot(n, p) for p in pts) / len(pts)


def _side(x):
    return 1 if x > BSP_EPS else (-1 if x < -BSP_EPS else 0)


def _clip(pts, flags, dist, side):
    """The `side` (+1 front, -1 back) part of a polygon; each vertex carries the flag of the edge leaving it, a cut
    edge gets 0.  Only an edge strictly crossing the plane is cut (an end within BSP_EPS of it is on it): cutting
    by the tolerance instead extrapolated the cut far past the plane (-0.009 to -0.011 put it at -4.5)."""
    out = []
    m = len(pts)
    for k in range(m):
        p, q, f = pts[k], pts[(k + 1) % m], flags[k]
        cp, cq = _side(dist[k]) * side, _side(dist[(k + 1) % m]) * side
        if cp >= 0:
            out.append((p, f if (cq >= 0 or cp > 0) else 0))
        if cp * cq < 0:
            dp, dq = dist[k], dist[(k + 1) % m]
            x = dp / (dp - dq)
            i = (p[0] + (q[0] - p[0]) * x, p[1] + (q[1] - p[1]) * x, p[2] + (q[2] - p[2]) * x)
            out.append((i, 0 if cp > 0 else f))
    return [o[0] for o in out], [o[1] for o in out]


def bsp(v, tris, flags):
    """Back-to-front order from any side: a BSP tree of the triangles (split where they cross a plane).
    -> (verts, tris (a, b, c, f), nodes (n, d, front, back, first, count), depth)."""
    polys = []
    for t, f in zip(tris, flags):
        pts = [v[k] for k in t]
        pl = _poly_plane(pts)
        if pl:
            polys.append((pts, [f & 1, (f >> 1) & 1, (f >> 2) & 1], pl[0]))
    nodes, otris, overts, vindex = [], [], [], {}

    def vid(p):
        key = (round(p[0], 2), round(p[1], 2), round(p[2], 2))
        if key not in vindex:
            vindex[key] = len(overts)
            overts.append(key)
        return vindex[key]

    def emit(pts, fl, own, nn):
        back = _dot(own, nn) < 0
        for k in range(1, len(pts) - 1):        # a fan: inner diagonals are not drawn
            ids = (vid(pts[0]), vid(pts[k]), vid(pts[k + 1]))
            if len(set(ids)) < 3:
                continue
            f = (fl[0] if k == 1 else 0) | (fl[k] << 1) | ((fl[k + 1] if k + 1 == len(pts) - 1 else 0) << 2)
            otris.append(ids + (f | (8 if back else 0),))

    depth = [0]

    def build(ps, lvl):
        if not ps:
            return -1
        depth[0] = max(depth[0], lvl)
        step = max(1, len(ps) // 24)
        best = None
        for c in ps[::step]:
            n, d = _poly_plane(c[0])
            fr = bk = sp = 0
            for q in ps:
                ds = [_dot(n, p) - d for p in q[0]]
                if all(x >= -BSP_EPS for x in ds) and not all(abs(x) < BSP_EPS for x in ds):
                    fr += 1
                elif all(x <= BSP_EPS for x in ds) and not all(abs(x) < BSP_EPS for x in ds):
                    bk += 1
                elif not all(abs(x) < BSP_EPS for x in ds):
                    sp += 1
            score = sp * 5 + abs(fr - bk)
            if best is None or score < best[0]:
                best = (score, n, d)
        _, n, d = best
        on, front, back = [], [], []
        for q in ps:
            pts, fl, own = q
            ds = [_dot(n, p) - d for p in pts]
            if all(abs(x) < BSP_EPS for x in ds):
                on.append(q)
            elif all(x >= -BSP_EPS for x in ds):
                front.append(q)
            elif all(x <= BSP_EPS for x in ds):
                back.append(q)
            else:
                for side, sgn in ((front, 1), (back, -1)):
                    cp, cf = _clip(pts, fl, ds, sgn)
                    if len(cp) >= 3 and _poly_plane(cp):
                        side.append((cp, cf, own))
        me = len(nodes)
        nodes.append(None)
        first = len(otris)
        for pts, fl, own in on:
            emit(pts, fl, own, n)
        cnt = len(otris) - first
        f_i = build(front, lvl + 1)
        b_i = build(back, lvl + 1)
        nodes[me] = (n, d, f_i, b_i, first, cnt)
        return me

    build(polys, 1)
    return overts, otris, nodes, depth[0]


def wire(files, path, target, flat_deg, flip=False):
    """-> (verts, tris, nodes, closed, depth, source triangle count), within the menu's limits."""
    pos, tris = triangles(files, path)
    while True:
        v, t = simplify(pos, tris, target)
        lo = [min(p[i] for p in v) for i in range(3)]
        hi = [max(p[i] for p in v) for i in range(3)]
        c = [(lo[i] + hi[i]) / 2 for i in range(3)]
        k = TARGET_SIZE / (max(hi[i] - lo[i] for i in range(3)) or 1.0)
        v = [tuple((p[i] - c[i]) * k for i in range(3)) for p in v]
        e = [(hi[i] - lo[i]) * k for i in range(3)]
        if e[2] < STAND_UP * max(e[0], e[1]):     # lying flat: side on it would only ever show its edge
            if e[1] > e[0]:     # stood up with its longer side across (a butterfly's wings), its shorter upright
                v = [(p[1], p[2], p[0]) for p in v]
            else:
                v = [(p[0], -p[2], p[1]) for p in v]
        if flip:
            v = [(p[0], -p[1], -p[2]) for p in v]
        t, closed, by = orient(v, t)
        ov, ot, nodes, depth = bsp(v, t, edge_flags(v, t, by, flat_deg))
        if len(ov) <= QC_V and len(ot) <= QC_T and len(nodes) <= QC_N and depth <= 200:
            return ov, ot, nodes, closed, depth, len(tris)
        if target < 60:
            raise ModelError('cannot fit the menu limits (%d verts, %d tris, %d nodes)' % (len(ov), len(ot), len(nodes)))
        target = int(target * 0.85)


def placed_models(bsp):
    """Model paths the map places, with how many times: static props and entity `model` keys."""
    count = Counter()
    ents = lump(bsp, LUMP_ENTITIES).decode('latin1', 'replace')
    for m in re.finditer(r'"model"\s+"([^"*][^"]*\.mdl)"', ents, re.I):
        count[m.group(1).lower().replace('\\', '/')] += 1
    g = lump(bsp, LUMP_GAME)
    if len(g) >= 4:
        n = struct.unpack_from('<i', g, 0)[0]
        for k in range(min(n, 64)):
            gid, flags, gver, goff, glen = struct.unpack_from('<4sHHii', g, 4 + k * 16)
            if gid[::-1] != b'sprp' or flags & 1 or glen < 4:
                continue
            sp = bsp[goff:goff + glen]
            nd = struct.unpack_from('<i', sp, 0)[0]
            names = [sp[4 + i * 128:4 + (i + 1) * 128].split(b'\0')[0].decode('latin1').lower() for i in range(nd)]
            for nm in names:
                count[nm.replace('\\', '/')] += 1        # one per dictionary entry: a floor, not a count
    return count


def suggest(args):
    rows = []
    for f in sorted(os.listdir(args.maps)):
        if not f.lower().endswith('.bsp'):
            continue
        try:
            bsp = open(os.path.join(args.maps, f), 'rb').read()
            pak = pakfile(bsp)
            if pak is None:
                continue
            files = Files(pak, [])
            custom = [n for n in files.names if n.endswith('.mdl')]
            if not custom:
                continue
            placed = placed_models(bsp)
            cands = sorted(custom, key=lambda n: (-placed.get(n, 0), n))
            for n in cands[:1]:
                try:
                    pos, tris = triangles(files, n)
                except (ModelError, struct.error, IndexError):
                    continue
                rows.append((len(custom), f[:-4], n, placed.get(n, 0), len(tris)))
        except (OSError, struct.error, zipfile.BadZipFile):
            continue
    rows.sort(reverse=True)
    for nc, mp, n, cnt, nt in rows[:args.limit]:
        print('%-28s %-56s placed %3d  tris %6d  (%d custom models)' % (mp, n, cnt, nt, nc))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--maps', required=True)
    ap.add_argument('--picks', default=os.path.join(os.path.dirname(__file__), 'loadwire_picks.txt'))
    ap.add_argument('--out', default=os.path.join(os.path.dirname(__file__), '..', 'ftesurf', 'gfx', 'loadwire'))
    ap.add_argument('--content', action='append', default=[], help='more directories to read models from')
    ap.add_argument('--tris', type=int, default=500)
    ap.add_argument('--flat', type=float, default=12.0, help='degrees: a flatter edge is not drawn')
    ap.add_argument('--suggest', action='store_true')
    ap.add_argument('--limit', type=int, default=40)
    args = ap.parse_args()
    if args.suggest:
        return suggest(args)
    picks = defaultdict(list)
    for ln in open(args.picks, encoding='utf-8'):
        ln = ln.split('#', 1)[0].split()
        if len(ln) >= 2:
            picks[ln[0].lower()].append((ln[1].lower(), 'flip' in ln[2:]))
    os.makedirs(args.out, exist_ok=True)
    bad = 0
    for mp, models in sorted(picks.items()):
        path = os.path.join(args.maps, mp + '.bsp')
        try:
            bsp = open(path, 'rb').read()
        except OSError:
            print('%s: no map' % mp)
            bad += 1
            continue
        files = Files(pakfile(bsp), args.content)
        lines = ['FTESURF-LOADWIRE 2']
        for m, flip in models:
            try:
                v, t, nodes, closed, depth, n0 = wire(files, m, args.tris, args.flat, flip)
            except (ModelError, struct.error, IndexError) as exc:
                print('%s: %s skipped (%s)' % (mp, m, exc))
                bad += 1
                continue
            lines.append('model %s' % m)
            lines.append('closed %d' % closed)
            lines += ['v %.2f %.2f %.2f' % p for p in v]
            lines += ['t %d %d %d %d' % x for x in t]
            lines += ['n %.5f %.5f %.5f %.3f %d %d %d %d' % (n[0], n[1], n[2], d, f, b, i, c)
                      for n, d, f, b, i, c in nodes]
            print('%s: %s  %d -> %d triangles after splits, %d vertices, %d nodes, depth %d, %s'
                  % (mp, m, n0, len(t), len(v), len(nodes), depth, 'closed' if closed else 'open'))
        if len(lines) > 1:
            with open(os.path.join(args.out, mp + '.txt'), 'w', encoding='ascii', newline='\n') as fh:
                fh.write('\n'.join(lines) + '\n')
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
