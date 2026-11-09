#!/usr/bin/env python3
"""P1453: the loading screen's map wireframes, taken from the map's own model files.

    python tools/loadwire.py --maps <dir of .bsp> [--picks tools/loadwire_picks.txt] [--out ftesurf/gfx/loadwire]
    python tools/loadwire.py --maps <dir> --suggest [--limit 40]

A pick is `<map> <model path>` (several lines for one map: the loading screen takes one at random). The model
is read from the map's pakfile (or --content dirs), LOD 0 of every body part's first model, welded, simplified by
quadric edge collapse to at most --tris triangles, and written as gfx/loadwire/<map>.txt (m_loading.qc reads it):

    FTESURF-LOADWIRE 1
    model <path>
    v x y z          (centred on the box, longest side 62 units: the lobby avatar's height)
    t a b c          (triangles, vertex indices)
    e a b t1 t2      (drawn edges: their two triangles, t2 -1 on a border; near-flat neighbours dropped)

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


def edges(v, tris, flat_deg):
    """Every edge with its two triangles; one between near-coplanar neighbours is not drawn."""
    by = defaultdict(list)
    for ti, t in enumerate(tris):
        for a, b in ((t[0], t[1]), (t[1], t[2]), (t[2], t[0])):
            by[(min(a, b), max(a, b))].append(ti)
    cosflat = math.cos(math.radians(flat_deg))
    out = []
    for (a, b), ts in sorted(by.items()):
        if len(ts) == 2:
            n1, n2 = normal(v, tris[ts[0]]), normal(v, tris[ts[1]])
            if abs(sum(n1[i] * n2[i] for i in range(3))) > cosflat:
                continue
            out.append((a, b, ts[0], ts[1]))
        else:
            out.append((a, b, ts[0], -1))
    return out


def wire(files, path, target, flat_deg):
    pos, tris = triangles(files, path)
    v, t = simplify(pos, tris, target)
    lo = [min(p[i] for p in v) for i in range(3)]
    hi = [max(p[i] for p in v) for i in range(3)]
    c = [(lo[i] + hi[i]) / 2 for i in range(3)]
    k = TARGET_SIZE / (max(hi[i] - lo[i] for i in range(3)) or 1.0)
    v = [tuple((p[i] - c[i]) * k for i in range(3)) for p in v]
    return v, t, edges(v, t, flat_deg), len(tris)


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
            picks[ln[0].lower()].append(ln[1].lower())
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
        lines = ['FTESURF-LOADWIRE 1']
        for m in models:
            try:
                v, t, e, n0 = wire(files, m, args.tris, args.flat)
            except (ModelError, struct.error, IndexError) as exc:
                print('%s: %s skipped (%s)' % (mp, m, exc))
                bad += 1
                continue
            lines.append('model %s' % m)
            lines += ['v %.1f %.1f %.1f' % p for p in v]
            lines += ['t %d %d %d' % x for x in t]
            lines += ['e %d %d %d %d' % x for x in e]
            print('%s: %s  %d -> %d triangles, %d vertices, %d edges' % (mp, m, n0, len(t), len(v), len(e)))
        if len(lines) > 1:
            with open(os.path.join(args.out, mp + '.txt'), 'w', encoding='ascii', newline='\n') as fh:
                fh.write('\n'.join(lines) + '\n')
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
