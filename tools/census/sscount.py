"""The honest count: setspeed pads with vel_z > 140 whose box has POSITIVE overlap
volume with a start zone -- not merely gap == 0, which includes a zero-width plane
contact (surf_prosurf's trigger_push was exactly that, and it is unreachable).

Also splits out the pads that lie ENTIRELY inside a start zone, which is the
strongest statement an AABB can make: the whole trigger volume is in the box the
player must occupy, so no part of the brush can be somewhere else.
"""
import contextlib, io, json, os, sys

sys.argv = ['pushcensus']
with contextlib.redirect_stdout(io.StringIO()):
    import pushcensus as pc
import bsplib
import sscensus as ss


def overlap(a, b):
    lo = [max(a[0][i], b[0][i]) for i in range(3)]
    hi = [min(a[1][i], b[1][i]) for i in range(3)]
    if any(hi[i] <= lo[i] for i in range(3)):
        return 0.0
    return (hi[0] - lo[0]) * (hi[1] - lo[1]) * (hi[2] - lo[2])


def vol(b):
    return max((b[1][0] - b[0][0]) * (b[1][1] - b[0][1]) * (b[1][2] - b[0][2]), 1e-9)


maps = {os.path.splitext(f)[0].lower(): os.path.join(pc.MAPS, f)
        for f in os.listdir(pc.MAPS) if f.lower().endswith('.bsp')}
zfiles = {os.path.splitext(f)[0].lower(): os.path.join(pc.ZON, f)
          for f in os.listdir(pc.ZON) if f.lower().endswith('.json')}

gap0 = positive = contained = 0
cmaps, pmaps = set(), set()
rows = []

for name in sorted(maps):
    try:
        ents, models = bsplib.read(maps[name])
    except Exception:
        continue
    pads = [e for e in ents if e.get('classname') in ss.CLASSES]
    if not pads:
        continue
    starts = []
    if name in zfiles:
        try:
            starts = pc.json_starts(zfiles[name])
        except Exception:
            starts = []
    if not starts:
        for e in ents:
            if e.get('classname') == 'trigger_momentum_timer_start':
                b = pc.ent_box(e, models)
                if b:
                    starts.append(b)
    if not starts:
        continue

    for e in pads:
        vmode, vspeed = ss.vertical(e)
        if vmode not in (1, 2) or vspeed <= 140:
            continue
        box = pc.ent_box(e, models)
        if not box:
            continue
        if min(pc.gap(box, s) for s in starts) > 0.0:
            continue
        gap0 += 1
        ov = max(overlap(box, s) for s in starts)
        if ov <= 0.0:
            continue
        positive += 1
        pmaps.add(name)
        frac = ov / vol(box)
        rows.append((name, vspeed, frac))
        if frac >= 0.999:
            contained += 1
            cmaps.add(name)

print(json.dumps(dict(
    gap_zero_as_first_reported=gap0,
    positive_overlap_volume=positive,
    pad_entirely_inside_a_start_zone=contained,
    maps_positive=len(pmaps),
    maps_contained=len(cmaps),
), indent=1))
print('\n-- pads ENTIRELY inside a start zone --')
for n, v, f in sorted(rows, key=lambda r: -r[1]):
    if f >= 0.999:
        print('  %-28s vel_z %.1f' % (n, v))
print('\n-- partial overlap --')
for n, v, f in sorted(rows, key=lambda r: -r[1]):
    if f < 0.999:
        print('  %-28s vel_z %-8.1f %.0f%% of pad inside' % (n, v, f * 100))
