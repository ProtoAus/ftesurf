#!/usr/bin/env python3
"""P1443: a surf run's energy ledger, ramp by ramp, from a recording and the map's planes.

  python tools/surfledger.py <map.bsp> <run.rec> [<run.rec> ...] [--json out.json]

Energy is E = |v|^2/2 + g*z, shown as the speed it is worth at the run's lowest point
(vE = sqrt(|v|^2 + 2g(z - zmin))); gravity only trades height for speed, so vE moves only with strafing,
clips and map forces. Each tick is explained by Source's air move -- half gravity, AirAccelerate
(sv_airaccelerate, the 30 u/s wish cap), the collision, half gravity -- at the row's own yaw and
moves. What the air move cannot explain is the collision: its residual r points out of the plane
hit, and |w|^2/2 - |v + g*dt/2|^2/2 (w the pre-collision velocity) is the energy it removed. A ramp
is the BSP plane that normal and the hull's support point land on.

Rows are per-tick samples (KSF imports, Momentum conversions); a pair more than one tick apart
is skipped, so a native .rec sampled per packet gives a partial ledger.
"""
import argparse
import json
import math
import struct
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
from bspnear import lump  # noqa: E402

AIR_EPS = 0.05          # |residual| below this is free air (measured: median 0.0001 on surf_null)
GAP_TICKS = 3           # air ticks that end a ride (a shorter gap is a hop along the same ramp)
DUCK_SHIFT = 8.5        # a duck or unduck in the air moves the origin this far: g*8.5 of real game energy


def read_rec(path):
    hdr, rows = {}, []
    for line in open(path, encoding='latin-1'):
        p = line.split()
        if not p:
            continue
        c = p[0][0]
        if not (c == '-' or c.isdigit()):
            if len(p) >= 2 and not rows:
                hdr[p[0]] = ' '.join(p[1:])
            continue
        try:
            v = [float(x) for x in p[:17]]
        except ValueError:
            continue
        if len(v) < 14:
            continue
        rows.append(dict(t=v[0], o=tuple(v[1:4]), v=tuple(v[4:7]), yaw=v[8], fl=int(v[9]),
                         fwd=v[11], side=v[12]))
    return hdr, rows


def read_planes(bsp):
    data = open(bsp, 'rb').read()
    if data[:4] != b'VBSP':
        raise SystemExit(f'{bsp}: not a Source BSP')
    raw = lump(data, 1)
    return [struct.unpack_from('<ffffi', raw, i * 20)[:4] for i in range(len(raw) // 20)]


class PlaneIndex:
    """Planes bucketed by rounded normal, for the hull-support lookup."""

    def __init__(self, planes):
        self.planes, self.b = planes, {}
        for i, (x, y, z, d) in enumerate(planes):
            self.b.setdefault((round(x, 1), round(y, 1), round(z, 1)), []).append(i)

    def find(self, n, d, ntol=0.004, dtol=1.5):
        best = None
        k0 = (round(n[0], 1), round(n[1], 1), round(n[2], 1))
        for dx in (-0.1, 0, 0.1):
            for dy in (-0.1, 0, 0.1):
                for dz in (-0.1, 0, 0.1):
                    for i in self.b.get((round(k0[0] + dx, 1), round(k0[1] + dy, 1), round(k0[2] + dz, 1)), ()):
                        x, y, z, pd = self.planes[i]
                        en = math.sqrt((x - n[0]) ** 2 + (y - n[1]) ** 2 + (z - n[2]) ** 2)
                        ed = abs(pd - d)
                        if en < ntol and ed < dtol and (best is None or (en, ed) < best[1:]):
                            best = (i, en, ed)
        return best[0] if best else -1


def air_accel(vel, yaw, fwd, side, aa, dt, cap, maxspeed):
    y = math.radians(yaw)
    wx = math.cos(y) * fwd + math.sin(y) * side
    wy = math.sin(y) * fwd - math.cos(y) * side
    ws = math.hypot(wx, wy)
    if ws < 1e-6:
        return 0.0, 0.0
    dx, dy = wx / ws, wy / ws
    ws = min(ws, maxspeed)
    add = min(ws, cap) - (vel[0] * dx + vel[1] * dy)
    if add <= 0:
        return 0.0, 0.0
    a = min(aa * ws * dt, add)
    return a * dx, a * dy


def ledger(rows, planes, g, aa, dt, cap, maxspeed, hw):
    """Per tick: kind ('ground', 'air', 'clip', 'gap', 'warp'), strafe gain, clip loss, plane."""
    t0 = next((i for i, r in enumerate(rows) if r['t'] >= 0), 0)
    z0 = min(r['o'][2] for r in rows[t0:])
    ticks = []
    for i in range(t0 + 1, len(rows)):
        a, b = rows[i - 1], rows[i]
        k = dict(i=i, t=b['t'], o=b['o'], v=b['v'], kind='air', strafe=0.0, clip=0.0, other=0.0, plane=-1, n=None)
        if abs((b['t'] - a['t']) - dt) > dt * 0.25:
            k['kind'] = 'gap'
        elif a['fl'] & 1 or b['fl'] & 1:
            k['kind'] = 'ground'
        else:
            ax, ay = air_accel(a['v'], b['yaw'], b['fwd'], b['side'], aa, dt, cap, maxspeed)
            va = (a['v'][0] + ax, a['v'][1] + ay, a['v'][2])
            k['strafe'] = (va[0] ** 2 + va[1] ** 2 - a['v'][0] ** 2 - a['v'][1] ** 2) / 2
            w = (va[0], va[1], va[2] - g * dt / 2)
            r = (b['v'][0] - w[0], b['v'][1] - w[1], b['v'][2] - (w[2] - g * dt / 2))
            rl = math.sqrt(r[0] ** 2 + r[1] ** 2 + r[2] ** 2)
            step = math.dist(a['o'], b['o'])
            if step > (math.sqrt(sum(x * x for x in a['v'])) + 400) * dt * 2 + 8:
                k['kind'] = 'warp'                      # a teleport: the move cannot explain the step
            elif rl >= AIR_EPS:
                vb = (b['v'][0], b['v'][1], b['v'][2] + g * dt / 2)
                k['clip'] = ((w[0] ** 2 + w[1] ** 2 + w[2] ** 2) - (vb[0] ** 2 + vb[1] ** 2 + vb[2] ** 2)) / 2
                n = (r[0] / rl, r[1] / rl, r[2] / rl)
                wn = w[0] * n[0] + w[1] * n[1] + w[2] * n[2]
                if wn < 0 and k['clip'] > -1:           # removed velocity into a plane: a collision
                    k['kind'], k['n'] = 'clip', n
                    # TryPlayerMove runs the first f of the tick unclipped (to the plane), the rest clipped,
                    # all before the second half of gravity: the books then carry g*dt*|w.n|*nz*(1/2 - f)
                    # more than the clip removed (exact for one plane). f from the hull's support distance.
                    f = 0.0
                    if n[2] > 0:
                        hs = hw * (abs(n[0]) + abs(n[1]))
                        sa = n[0] * a['o'][0] + n[1] * a['o'][1] + n[2] * a['o'][2] - hs
                        sb = n[0] * b['o'][0] + n[1] * b['o'][1] + n[2] * b['o'][2] - hs
                        f = max(0.0, min(1.0, (sa - sb) / (-wn * dt)))
                    k['clip'] -= -g * dt * wn * n[2] * (0.5 - f)
                    k['f'] = f
                    if n[2] > 0:
                        d = n[0] * b['o'][0] + n[1] * b['o'][1] + n[2] * b['o'][2] - hw * (abs(n[0]) + abs(n[1]))
                        k['plane'] = planes.find(n, d)
                else:
                    k['kind'] = 'force'                 # added energy or no plane: a booster, trigger, push
                    k['other'] = -k['clip']
                    k['clip'] = 0.0
        e = (b['v'][0] ** 2 + b['v'][1] ** 2 + b['v'][2] ** 2) / 2 + g * (b['o'][2] - z0)
        ea = (a['v'][0] ** 2 + a['v'][1] ** 2 + a['v'][2] ** 2) / 2 + g * (a['o'][2] - z0)
        k['resid'] = (e - ea) - (k['strafe'] - k['clip'] + k['other']) if k['kind'] in ('air', 'clip', 'force') else 0.0
        k['duck'] = 0.0
        q = round(k['resid'] / (g * DUCK_SHIFT))
        if q and abs(k['resid'] - q * g * DUCK_SHIFT) < g * 0.5:
            k['duck'] = q * g * DUCK_SHIFT              # the origin moved 8.5 with the hull
            k['resid'] -= k['duck']
        k['vE'] = math.sqrt(max(0.0, 2 * e))
        k['speed'] = math.hypot(b['v'][0], b['v'][1])
        ticks.append(k)
    return ticks, z0


def ramp_kind(n):
    if n is None:
        return '-'
    if n[2] >= 0.7:
        return 'floor'
    if n[2] > 0.02:
        return 'ramp'
    if n[2] > -0.02:
        return 'wall'
    return 'ceiling'


def segments(ticks, dt):
    """Rides: contact runs on one plane (short air gaps allowed); air between them."""
    segs, cur, gap = [], None, 0
    for k in ticks:
        on = k['kind'] == 'clip' and ramp_kind(k['n']) == 'ramp'
        if on and cur is not None and gap <= GAP_TICKS:
            cur['ticks'].append(k)
            cur['clip'] += k['clip']
            cur['strafe'] += k['strafe']
            cur['planes'][k['plane']] = cur['planes'].get(k['plane'], 0) + 1
            gap = 0
            continue
        if cur is not None and not on:
            gap += 1
            if gap <= GAP_TICKS:
                cur['ticks'].append(k)
                cur['strafe'] += k['strafe']
                continue
        if cur is not None:
            segs.append(cur)
            cur = None
        if on:
            cur = dict(plane=k['plane'], n=k['n'], ticks=[k], clip=k['clip'], strafe=k['strafe'], board=k,
                       planes={k['plane']: 1})
            gap = 0
    if cur is not None:
        segs.append(cur)
    out, prev = [], None
    for s in segs:
        while s['ticks'] and s['ticks'][-1]['kind'] != 'clip':
            s['ticks'].pop()                            # trailing air belongs to the next flight
        first, last = s['ticks'][0], s['ticks'][-1]
        air = [k for k in ticks if (prev is None or k['i'] > prev['i']) and k['i'] < first['i']]
        main = max(s['planes'].items(), key=lambda kv: kv[1])[0]
        out.append(dict(
            plane=main, board_plane=s['plane'], planes=len(s['planes']), n=s['n'],
            resid=sum(k['resid'] for k in s['ticks']), t_board=first['t'], t_leave=last['t'],
            ride_s=(last['i'] - first['i'] + 1) * dt,
            board_loss=first['clip'],
            ride_clip=s['clip'] - first['clip'],
            ride_strafe=sum(k['strafe'] for k in s['ticks']),
            air_s=len(air) * dt,
            air_strafe=sum(k['strafe'] for k in air),
            air_other=sum(k['other'] for k in air) - sum(k['clip'] for k in air),
            duck=sum(k['duck'] for k in air) + sum(k['duck'] for k in s['ticks']),
            vE_board=first['vE'], vE_leave=last['vE'],
            speed_board=math.sqrt(sum(x * x for x in first['v'])), speed_leave=last['speed'],
            board_v=first['v'], leave_v=last['v'], leave_o=last['o'], board_o=first['o']))
        prev = last
    return out


def dv(e, vE):
    """An energy (per unit mass) as the speed it is worth at vE."""
    return e / vE if vE > 1 else 0.0


def report(name, segs, ticks):
    kinds = {}
    for k in ticks:
        kinds[k['kind']] = kinds.get(k['kind'], 0) + 1
    print(f'== {name}: {len(ticks)} ticks ' + ' '.join(f'{a} {b}' for a, b in sorted(kinds.items())))
    print('  #  plane faces  board t  vE in  board loss  ride +strafe -clip  leave vE  air s  air +strafe  other   duck  unexpl')
    for j, s in enumerate(segs):
        print(f'{j:3d} {s["plane"]:6d} {s["planes"]:4d} {s["t_board"]:8.2f} {s["vE_board"]:6.0f} {-dv(s["board_loss"], s["vE_board"]):9.1f}'
              f'  {s["ride_s"]:4.2f}s {dv(s["ride_strafe"], s["vE_board"]):+6.1f} {-dv(s["ride_clip"], s["vE_board"]):+6.1f}'
              f'  {s["vE_leave"]:7.0f} {s["air_s"]:5.2f} {dv(s["air_strafe"], s["vE_board"]):+9.1f} {dv(s["air_other"], s["vE_board"]):+7.1f}'
              f' {dv(s["duck"], s["vE_board"]):+6.1f} {dv(s["resid"], s["vE_board"]):+7.1f}')
    tot = lambda f: sum(dv(s[f], s['vE_board']) for s in segs)
    res = [abs(k['resid']) for k in ticks if k['kind'] in ('air', 'clip')]
    res.sort()
    if res:
        print(f'  accounting check: |observed - explained| energy per tick, median {res[len(res) // 2]:.2f}, '
              f'p99 {res[int(len(res) * 0.99)]:.1f} (u/s)^2')
    print(f'  totals (as speed): board loss {-tot("board_loss"):.0f}  ride strafe {tot("ride_strafe"):+.0f}'
          f'  ride clip {-tot("ride_clip"):+.0f}  air strafe {tot("air_strafe"):+.0f}  air other {tot("air_other"):+.0f}  duck {tot("duck"):+.0f}'
          f'  unexplained {tot("resid"):+.0f}')


def compare(out):
    """Ramp by ramp across runs that rode the same ramps in the same order: board loss, ride net
    (strafe - clip) and air net (strafe + forces + duck) as speed, and the best of each."""
    names = list(out)
    seqs = [[s['plane'] for s in out[n]['segments']] for n in names]
    if len({len(q) for q in seqs}) != 1:
        print()
        print('(compare: the runs rode different numbers of ramps -- not aligned)')
        return
    print()
    print('== ramp by ramp (as speed; higher is better)')
    print('  ramp  ' + '  '.join(f'{n[-10:]:>26}' for n in names) + '      best of')
    print('        ' + '  '.join(f'{"board":>8}{"ride":>9}{"air":>9}' for _ in names) +
          f'  {"board":>8}{"ride":>9}{"air":>9}')
    best = [0.0, 0.0, 0.0]
    runs = {n: [0.0, 0.0, 0.0] for n in names}
    for j in range(len(seqs[0])):
        cells, row = [], []
        for n in names:
            sg = out[n]['segments'][j]
            v = sg['vE_board']
            b = -dv(sg['board_loss'], v)
            r = dv(sg['ride_strafe'] - sg['ride_clip'], v)
            ai = dv(sg['air_strafe'] + sg['air_other'] + sg['duck'], v)
            row.append((b, r, ai))
            cells.append(f'{b:8.1f}{r:+9.1f}{ai:+9.1f}')
            runs[n] = [runs[n][0] + b, runs[n][1] + r, runs[n][2] + ai]
        bb = [max(x[i] for x in row) for i in range(3)]
        best = [best[i] + bb[i] for i in range(3)]
        print(f'  {j:4d}  ' + '  '.join(cells) + f'  {bb[0]:8.1f}{bb[1]:+9.1f}{bb[2]:+9.1f}')
    print('  total ' + '  '.join(f'{r[0]:8.0f}{r[1]:+9.0f}{r[2]:+9.0f}' for r in runs.values()) +
          f'  {best[0]:8.0f}{best[1]:+9.0f}{best[2]:+9.0f}')
    for n in names:
        print(f'  {n}: net {sum(runs[n]):+.0f}; the best of the three on every ramp would be {sum(best):+.0f}')


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('bsp')
    ap.add_argument('recs', nargs='+')
    ap.add_argument('--gravity', type=float, default=800)
    ap.add_argument('--airaccelerate', type=float, default=150)
    ap.add_argument('--aircap', type=float, default=30)
    ap.add_argument('--maxspeed', type=float, default=250)
    ap.add_argument('--hull', type=float, default=16, help='hull half-width (support point on a ramp)')
    ap.add_argument('--json')
    a = ap.parse_args()
    planes = PlaneIndex(read_planes(a.bsp))
    out = {}
    for rec in a.recs:
        hdr, rows = read_rec(rec)
        dt = float(hdr.get('movetickrate', hdr.get('tickrate', '0.015')))
        ticks, z0 = ledger(rows, planes, a.gravity, a.airaccelerate, dt, a.aircap, a.maxspeed, a.hull)
        segs = segments(ticks, dt)
        name = f'{Path(rec).stem} ({hdr.get("owner", "?")}, {hdr.get("ksftime", "?")} s)'
        report(name, segs, ticks)
        out[Path(rec).stem] = dict(header=hdr, z0=z0, dt=dt, segments=segs)
    if len(out) > 1:
        compare(out)
    if a.json:
        Path(a.json).write_text(json.dumps(out, indent=1))


if __name__ == '__main__':
    main()
