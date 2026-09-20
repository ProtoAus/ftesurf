"""Patch 414 follow-up: can a now-live OnJump pad be read as a hopped start?

Patch 414 made OnJump fire for the first time, which on the LIVE ROTATION turned
937 outputs across 28 of the 93 maps from inert into active.  The ones that write
`AddOutput basevelocity` with a big Z are the anti-cheat question, because of how
Patch 409's gate is shaped:

    if (!e.run_pushed || e.run_jumpcmd)      <- press on with the accusation

A mover's rise is forgiven only when the player was NOT also pressing jump.  On an
OnJump pad the player is pressing jump BY CONSTRUCTION, so run_jumpcmd is always
TRUE and the gate always passes.  If such a pad sat inside a START zone and its
rise crossed PM_NONJUMP_VEL, the hop rule would read it as a hopped start and
taint an honest run -- the false-accusation half of AGENTS.md's sign-discipline
rule.

ANSWER, 2026-09-21, on the 93-map rotation: 202 OnJump basevelocity outputs, 114
of them over PM_NONJUMP_VEL, and ZERO with any overlap volume against a start
zone.  Not reachable.  Re-run this when the rotation changes -- it reads the
lobby cfgs, so it follows them.

Graded per tools/census/README.md: containment is the only claim an AABB can make
safely, and here even the looser overlap figure is zero, which is why this one is
conclusive without a live probe.
"""
import re, os, sys, json, contextlib, io
sys.path.insert(0, r'C:\FTESurf\tools\census')
sys.argv = ['x']
with contextlib.redirect_stdout(io.StringIO()):
    import pushcensus as pc
import bsplib

rot = set()
d = r'C:\FTESurf\ftesurf\cfg\lobby'
for f in sorted(os.listdir(d)):
    if f.endswith('.cfg'):
        t = open(os.path.join(d, f), errors='replace').read()
        for m in re.finditer(r'set\s+lobby_maps\s+"([^"]*)"', t, re.S):
            rot.update(x.lower() for x in m.group(1).split())

MAPS = pc.MAPS
zf = {os.path.splitext(f)[0].lower(): os.path.join(pc.ZON, f)
      for f in os.listdir(pc.ZON) if f.lower().endswith('.json')}

def overlap(a, b):
    lo = [max(a[0][i], b[0][i]) for i in range(3)]
    hi = [min(a[1][i], b[1][i]) for i in range(3)]
    if any(hi[i] <= lo[i] for i in range(3)):
        return 0.0
    return (hi[0]-lo[0])*(hi[1]-lo[1])*(hi[2]-lo[2])

def contained(a, b):
    return all(a[0][i] >= b[0][i] and a[1][i] <= b[1][i] for i in range(3))

tot = vert = over = cont = 0
rows = []
for name in sorted(rot):
    p = os.path.join(MAPS, name + '.bsp')
    if not os.path.exists(p):
        continue
    try:
        ents, models = bsplib.read(p)
        with open(p, 'rb') as fh:
            tbl = bsplib.lumps(fh); raw = bsplib.lump(fh, tbl, 0)
    except Exception:
        continue
    starts = []
    if name in zf:
        try: starts = pc.json_starts(zf[name])
        except Exception: starts = []
    if not starts:
        continue
    blocks = re.findall(rb'\{(.*?)\}', raw, re.S)
    for i, b in enumerate(blocks):
        kv = [(k.decode('latin1'), v.decode('latin1'))
              for k, v in re.findall(rb'"([^"]+)"\s*"([^"]*)"', b)]
        onj = [v for k, v in kv if k == 'OnJump']
        if not onj:
            continue
        d2 = {k.lower(): v for k, v in kv}
        for v in onj:
            if 'basevelocity' not in v.lower():
                continue
            tot += 1
            mm = re.search(r'basevelocity\s+(-?[\d.]+)\s+(-?[\d.]+)\s+(-?[\d.]+)', v)
            if not mm:
                continue
            vz = float(mm.group(3))
            if vz <= 140:
                continue
            vert += 1
            box = pc.ent_box(d2, models)
            if not box:
                continue
            if max(overlap(box, s) for s in starts) <= 0:
                continue
            over += 1
            c = any(contained(box, s) for s in starts)
            if c: cont += 1
            rows.append((name, vz, 'CONTAINED' if c else 'overlap', d2.get('hammerid')))

print('rotation maps with zone data + an OnJump basevelocity: scanned')
print('  OnJump basevelocity outputs        %d' % tot)
print('  ...whose Z exceeds PM_NONJUMP_VEL  %d' % vert)
print('  ...with positive overlap volume    %d' % over)
print('  ...fully CONTAINED in a start zone %d' % cont)
print()
for r in sorted(rows, key=lambda r: -r[1]):
    print('  %-24s vz %-8.0f %-10s hammerid %s' % r)
