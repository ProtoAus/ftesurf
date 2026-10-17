"""Offline (Patch 764): a static prop's .phy hull, ledge by ledge (the same walk as mod_phy.c).
Reports per model: ledges, convexity, internal walls (a face of one ledge lying on a face
of another, opposite normal), and for each wall edge on the outer surface, the angle the
wall makes with its ledge's outer face there and how far a four-unit slab behind the wall
would stand above that face.  usage: physeams.py <bsp> <model path in the pakfile>..."""
import io, os, struct, sys, zipfile, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bsplib

def u32(b, o): return struct.unpack_from('<I', b, o)[0]
def i32(b, o): return struct.unpack_from('<i', b, o)[0]
def i16(b, o): return struct.unpack_from('<h', b, o)[0]
def f32(b, o): return struct.unpack_from('<f', b, o)[0]

def ledges_of(phy):
    hsize, _, nsolid, _ = struct.unpack_from('<iiii', phy, 0)
    assert nsolid == 1, nsolid
    base = hsize
    ssize = i32(phy, base)
    end = base + 4 + ssize
    assert phy[base+4:base+8] == b'VPHY'
    surf = base + 32
    root = surf + i32(phy, surf + 32)
    out, stack = [], [root]
    while stack:
        o = stack.pop()
        offr, offl = i32(phy, o), i32(phy, o + 4)
        if offr == 0:
            out.append(o + offl); continue
        stack.append(o + 28); stack.append(o + offr)
    res = []
    for lo in out:
        cpo, ntri = i32(phy, lo), i16(phy, lo + 12)
        pts = lo + cpo
        tris = []
        for t in range(ntri):
            tp = lo + 16 + t * 16
            tris.append(tuple(u32(phy, tp + 4 + k * 4) & 0xffff for k in range(3)))
        used = sorted({i for tr in tris for i in tr})
        P = {}
        for i in used:
            x, y, z = f32(phy, pts + i*16), f32(phy, pts + i*16 + 4), f32(phy, pts + i*16 + 8)
            P[i] = (x / 0.0254, z / 0.0254, -y / 0.0254)
        res.append((P, tris))
    return res

def sub(a, b): return (a[0]-b[0], a[1]-b[1], a[2]-b[2])
def dot(a, b): return a[0]*b[0] + a[1]*b[1] + a[2]*b[2]
def cross(a, b): return (a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0])
def norm(a):
    l = math.sqrt(dot(a, a)); return (a[0]/l, a[1]/l, a[2]/l) if l > 1e-9 else None

def faces(P, tris):
    cen = [sum(p[k] for p in P.values()) / len(P) for k in range(3)]
    F = []
    for tr in tris:
        a, b, c = (P[i] for i in tr)
        n = norm(cross(sub(b, a), sub(c, a)))
        if not n: continue
        if dot(n, sub(a, cen)) < 0: n = (-n[0], -n[1], -n[2])
        F.append((n, dot(n, a), tr))
    return F

def main():
    bsp = sys.argv[1]
    with open(bsp, 'rb') as fh:
        t = bsplib.lumps(fh)
        pak = bsplib.lump(fh, t, 40)
    z = zipfile.ZipFile(io.BytesIO(pak))
    names = {n.lower(): n for n in z.namelist()}
    for mdl in sys.argv[2:]:
        phyname = mdl[:-4] + '.phy'
        phy = z.read(names[phyname.lower()])
        L = ledges_of(phy)
        Fs = [faces(P, tris) for P, tris in L]
        nonconvex = 0
        for (P, tris), F in zip(L, Fs):
            for n, d, _ in F:
                if max(dot(n, p) for p in P.values()) - d > 0.1:
                    nonconvex += 1; break
        # internal walls: a face of ledge i coplanar (opposite normal) with a face of ledge j
        walls = []
        for i, Fi in enumerate(Fs):
            for n, d, tr in Fi:
                for j, Fj in enumerate(Fs):
                    if j == i: continue
                    if any(dot(n, m) < -0.99999 and abs(d + e) < 0.05 for m, e, _ in Fj):
                        walls.append((i, n, d, tr)); break
        # for each wall face, the outer faces of the same ledge sharing an edge with it
        acute = []
        for i, n, d, tr in walls:
            P, _ = L[i]
            wall_edges = {frozenset(e) for e in ((tr[0], tr[1]), (tr[1], tr[2]), (tr[2], tr[0]))}
            for m, e, tr2 in Fs[i]:
                if tr2 == tr or abs(dot(m, n)) > 0.999: continue
                edges2 = {frozenset(x) for x in ((tr2[0], tr2[1]), (tr2[1], tr2[2]), (tr2[2], tr2[0]))}
                if not (wall_edges & edges2): continue
                if any(tr2 == w[3] for w in walls): continue  # neighbour is a wall too
                if m[2] < 0.2: continue                        # not a surf/standing face
                c = dot(n, m)                                   # cos of the angle between outward normals
                interior = 180 - math.degrees(math.acos(max(-1, min(1, c))))
                slab = -4 * c                                   # slab back edge above the face
                acute.append((interior, slab, i, m))
        print('%s: %d ledges, %d not convex, %d internal wall faces' % (mdl, len(L), nonconvex, len(walls)))
        stand = [a for a in acute if a[1] > 0]
        print('  wall/surface edges: %d; slab stands above the surface at %d (interior angle < 90)' % (len(acute), len(stand)))
        if stand:
            s = sorted(stand, key=lambda a: -a[1])
            print('  highest: %.3f units (interior %.2f deg); median %.3f; over 1/32: %d' % (
                s[0][1], s[0][0], s[len(s)//2][1], sum(1 for a in s if a[1] > 0.03125)))

if __name__ == '__main__':
    main()
