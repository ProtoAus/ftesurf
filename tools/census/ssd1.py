"""D1's exposure: setspeed pads that write a big HORIZONTAL speed but NOT a
vertical over 140, overlapping a start zone.

Those are the pads whose clip-into-vertical lands one packet after the touch, so a
flag set in the touch is already cleared (sv_timer.qc:9260) by the time `jumped`
fires.  The carrier path survives this because run_pushed is re-set on every command
the carrier is handed to the mover (sv_entities.qc:1110); a setspeed pad writes
velocity once and has nothing to re-arm.

409's own measurement is the scale: 3000 u/s of carrier clipped off a 26.57 degree
floor put 1453 u/s into velocity_z.  So any pad with a few hundred u/s of horizontal
next to a standable slope is a candidate.
"""
import contextlib, io, json, os, sys

sys.argv = ['pushcensus']
with contextlib.redirect_stdout(io.StringIO()):
    import pushcensus as pc
import bsplib
import sscensus as ss

NONJUMP = 140.0


def horiz(e):
    """-> (hmode, hspeed) as trigger_setspeed_touch computes them."""
    new = any(ss.key2(e, c, c.lower()) != 0.0 for c in (
        'Interval', 'HorizontalSpeedAmount', 'VerticalSpeedAmount',
        'KeepHorizontalSpeed', 'KeepVerticalSpeed'))
    if new:
        hspeed = ss.key2(e, 'HorizontalSpeedAmount', 'horizontalspeedamount')
        hmode = 4 if ss.key2(e, 'KeepHorizontalSpeed', 'keephorizontalspeed') else 0
        return hmode, hspeed
    return int(ss.key2(e, 'HorizontalSpeedMode', 'horizontalspeedmode')), \
        ss.key2(e, 'HorizontalSpeed', 'horizontalspeed')


def overlap(a, b):
    lo = [max(a[0][i], b[0][i]) for i in range(3)]
    hi = [min(a[1][i], b[1][i]) for i in range(3)]
    if any(hi[i] <= lo[i] for i in range(3)):
        return 0.0
    return (hi[0] - lo[0]) * (hi[1] - lo[1]) * (hi[2] - lo[2])


maps = {os.path.splitext(f)[0].lower(): os.path.join(pc.MAPS, f)
        for f in os.listdir(pc.MAPS) if f.lower().endswith('.bsp')}
zfiles = {os.path.splitext(f)[0].lower(): os.path.join(pc.ZON, f)
          for f in os.listdir(pc.ZON) if f.lower().endswith('.json')}

st = dict(pads=0, no_big_vertical=0, overlap_start=0, horiz_over_300=0,
          also_everytick=0)
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
        st['pads'] += 1
        vmode, vspeed = ss.vertical(e)
        # the case Patch 412's vertical predicate already covers
        if vmode in (1, 2) and vspeed > NONJUMP:
            continue
        st['no_big_vertical'] += 1
        box = pc.ent_box(e, models)
        if not box or max(overlap(box, s) for s in starts) <= 0.0:
            continue
        st['overlap_start'] += 1
        hmode, hspeed = horiz(e)
        if hmode == 4 or hspeed <= 300.0:
            continue
        st['horiz_over_300'] += 1
        et = ss.fires_every_command(e)
        if et:
            st['also_everytick'] += 1
        rows.append((name, hspeed, vspeed, vmode, et))

print(json.dumps(st, indent=1))
print('\n-- horizontal-only setspeed pads inside a start zone (D1 exposure) --')
for n, h, v, vm, et in sorted(rows, key=lambda r: -r[1]):
    print('  %-28s horiz %-9.1f vert %-8.1f vmode %-2d%s'
          % (n, h, v, vm, '  EveryTick' if et else ''))
