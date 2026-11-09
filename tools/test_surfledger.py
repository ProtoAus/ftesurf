#!/usr/bin/env python3
"""P1443: surfledger against a synthetic run built with Source's own move order.

A fall with air strafing onto one ramp plane, ridden a second, then off into the air. The ledger
must call every free tick air, find the ramp's plane, book the board loss the clip really removed,
and close the energy books to float error -- and a ledger without the half-gravity return
(the mutant below) must not.
"""
import math
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import surfledger as L  # noqa: E402

G, AA, DT, CAP, MS, HW = 800.0, 150.0, 0.015, 30.0, 250.0, 16.0
N = (0.0, -math.sin(math.radians(50)), math.cos(math.radians(50)))   # a 50-degree surf ramp facing -y
D = -2000.0                                                          # plane: n . p = D


def dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def build():
    rows, o, v, t = [], [0.0, 2600.0, 600.0], [900.0, 0.0, 0.0], -0.03
    yaw, on, touching = 0.0, 0, False
    for i in range(150):
        side = 400.0 if i % 40 < 20 else -400.0
        if touching and on < 60:
            side = -400.0                         # into the ramp (right is -y at yaw ~0) while riding it
        touching = False
        yaw += 1.5 if side > 0 else -1.5
        ax, ay = L.air_accel(v, yaw, 0.0, side, AA, DT, CAP, MS)
        w = [v[0] + ax, v[1] + ay, v[2] - G * DT / 2]
        end = [o[k] + w[k] * DT for k in range(3)]
        support = lambda p: dot(N, p) - HW * (abs(N[0]) + abs(N[1]))
        wn = dot(w, N)
        if support(end) < D and wn < 0 and on < 60:
            # TryPlayerMove: to the plane, clip, the rest of the tick along it
            f = max(0.0, min(1.0, (support(o) - D) / (-wn * DT)))
            hit = [o[k] + w[k] * DT * f for k in range(3)]
            w = [w[k] - wn * N[k] for k in range(3)]
            end = [hit[k] + w[k] * DT * (1 - f) for k in range(3)]
            on += 1
            touching = True
        o = end
        v = [w[0], w[1], w[2] - G * DT / 2]
        t += DT
        rows.append(dict(t=round(t, 6), o=tuple(o), v=tuple(v), yaw=yaw, fl=0, fwd=0.0, side=side))
    return rows


def check(rows, mutant=False):
    planes = L.PlaneIndex([(N[0], N[1], N[2], D), (0.0, 0.0, 1.0, -100.0)])
    if mutant:                                    # the ledger without the half-gravity return
        src = Path(L.__file__).read_text(encoding='utf-8')
        line = "k['clip'] -= -g * dt * wn * n[2] * (0.5 - f)"
        assert line in src
        ns = {'__file__': L.__file__, '__name__': 'surfledger_mutant'}
        exec(compile(src.replace(line, 'pass'), 'mutant', 'exec'), ns)
        ticks, z0 = ns['ledger'](rows, planes, G, AA, DT, CAP, MS, HW)
    else:
        ticks, z0 = L.ledger(rows, planes, G, AA, DT, CAP, MS, HW)
    kinds = {}
    for k in ticks:
        kinds[k['kind']] = kinds.get(k['kind'], 0) + 1
    worst = max(abs(k['resid']) for k in ticks)
    segs = L.segments(ticks, DT)
    return kinds, worst, segs, ticks


def main():
    rows = build()
    kinds, worst, segs, ticks = check(rows)
    fails = []
    if kinds.get('clip', 0) < 30 or kinds.get('air', 0) < 50:
        fails.append(f'kinds {kinds}')
    if len(segs) != 1 or segs[0]['plane'] != 0:
        fails.append(f'segments {[(s["plane"], s["t_board"]) for s in segs]}')
    if worst > 0.5:
        fails.append(f'books do not close: worst tick {worst:.3f}')
    first = next(k for k in ticks if k['kind'] == 'clip')
    if first['clip'] < 100:
        fails.append(f'board loss {first["clip"]:.1f} -- the fall should hit the ramp hard')
    _, mworst, _, _ = check(rows, mutant=True)
    if mworst < 1.0:
        fails.append(f'the mutant without the half-gravity return also closes ({mworst:.3f}): the check is blind')
    print(f'kinds {kinds}; worst tick {worst:.4f}; mutant worst {mworst:.1f}; board loss {first["clip"]:.1f}; '
          f'segments {len(segs)} plane {segs[0]["plane"] if segs else None}')
    if fails:
        print('FAIL: ' + '; '.join(fails))
        return 1
    print('ok')
    return 0


if __name__ == '__main__':
    sys.exit(main())
