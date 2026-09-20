"""Census: trigger_push volumes that overlap or sit near a START zone.

Start zones come from the shipped zone JSON where one exists (segments[0]
.checkpoints[0] of the main track and of every bonus -- sh_zones.qc:1351), else
from the map's own trigger_momentum_timer_start brushes (sv_zones.qc:82).
trigger_push bounds = its brush model's mins/maxs (models lump) + its origin key.
"""
import json, os, sys, traceback
import bsplib

MOM = os.environ.get("MOMENTUM_DIR",
                    r"C:\Program Files (x86)\Steam\steamapps\common\Momentum Mod Playtest\momentum")
MAPS = os.path.join(MOM, "maps")
ZON = os.path.join(MAPS, "zones", "online")
NEAR = float(sys.argv[1]) if len(sys.argv) > 1 else 300.0


def json_starts(path):
    """-> list of (mins, maxs) boxes for every START zone in the file."""
    d = json.load(open(path, 'r', encoding='utf-8-sig'))
    tracks = d.get('tracks') or {}
    out = []
    cands = []
    if isinstance(tracks.get('main'), dict):
        cands.append(tracks['main'])
    for b in (tracks.get('bonuses') or []):
        if isinstance(b, dict):
            cands.append(b)
    for t in cands:
        segs = ((t.get('zones') or {}).get('segments') or [])
        if not segs:
            continue
        cps = (segs[0] or {}).get('checkpoints') or []
        if not cps:
            continue
        for r in (cps[0] or {}).get('regions') or []:
            pts = r.get('points') or []
            if len(pts) < 3:
                continue
            xs = [p[0] for p in pts]
            ys = [p[1] for p in pts]
            b = r.get('bottom', 0.0)
            h = r.get('height', 0.0)
            out.append(((min(xs), min(ys), b), (max(xs), max(ys), b + h)))
    return out


def ent_box(e, models):
    md = e.get('model', '')
    try:
        o = [float(t) for t in e.get('origin', '0 0 0').split()[:3]]
    except ValueError:
        o = [0.0, 0.0, 0.0]
    if len(o) != 3:
        o = [0.0, 0.0, 0.0]
    if md.startswith('*'):
        i = int(md[1:])
        if i >= len(models):
            return None
        mn, mx, _ = models[i]
        return ((o[0] + mn[0], o[1] + mn[1], o[2] + mn[2]),
                (o[0] + mx[0], o[1] + mx[1], o[2] + mx[2]))
    return None


def gap(a, b):
    """0 if the AABBs intersect, else the largest per-axis separation."""
    g = 0.0
    for i in range(3):
        d = max(a[0][i] - b[1][i], b[0][i] - a[1][i])
        if d > g:
            g = d
    return g


def main():
    zfiles = {os.path.splitext(f)[0].lower(): os.path.join(ZON, f)
              for f in os.listdir(ZON) if f.lower().endswith('.json')}
    bsps = {os.path.splitext(f)[0].lower(): os.path.join(MAPS, f)
            for f in os.listdir(MAPS) if f.lower().endswith('.bsp')}

    stats = dict(bsp_total=len(bsps), zoned=0, scanned=0, unreadable=0,
                 nostart=0, nopush=0, maps_push=0,
                 maps_overlap=0, maps_near=0, pointpush=0,
                 zonesrc_json=0, zonesrc_bsp=0)
    hits_overlap, hits_near = [], []

    for name in sorted(bsps):
        p = bsps[name]
        try:
            ents, models = bsplib.read(p)
        except Exception:
            stats['unreadable'] += 1
            continue
        if ents is None:
            stats['unreadable'] += 1
            continue
        stats['scanned'] += 1

        starts = []
        if name in zfiles:
            stats['zoned'] += 1
            try:
                starts = json_starts(zfiles[name])
                if starts:
                    stats['zonesrc_json'] += 1
            except Exception:
                starts = []
        if not starts:
            for e in ents:
                if e.get('classname') == 'trigger_momentum_timer_start':
                    b = ent_box(e, models)
                    if b:
                        starts.append(b)
            if starts:
                stats['zonesrc_bsp'] += 1
        if not starts:
            stats['nostart'] += 1
            continue

        pushes = [e for e in ents if e.get('classname') == 'trigger_push']
        if not pushes:
            stats['nopush'] += 1
            continue
        stats['maps_push'] += 1

        nov = nnear = 0
        best = None
        for e in pushes:
            b = ent_box(e, models)
            if b is None:
                stats['pointpush'] += 1
                continue
            g = min(gap(b, s) for s in starts)
            if best is None or g < best:
                best = g
            if g <= 0.0:
                nov += 1
            elif g <= NEAR:
                nnear += 1
        if nov:
            stats['maps_overlap'] += 1
            hits_overlap.append((name, nov, len(pushes)))
        if nov or nnear:
            stats['maps_near'] += 1
            hits_near.append((name, nov, nnear, len(pushes), best))

    print(json.dumps(stats, indent=1))
    print('\n-- maps with a trigger_push OVERLAPPING a start zone (%d) --' % len(hits_overlap))
    for n, nov, tot in hits_overlap:
        print('  %-34s %3d of %3d pushes' % (n, nov, tot))
    print('\n-- maps with a push overlapping OR within %g u (%d) --' % (NEAR, len(hits_near)))
    for n, nov, nn, tot, best in hits_near:
        print('  %-34s overlap=%-3d near=%-3d of %-3d  min gap=%.1f' % (n, nov, nn, tot, best))



if __name__ == '__main__':
    main()
