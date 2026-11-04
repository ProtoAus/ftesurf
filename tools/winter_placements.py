#!/usr/bin/env python3
"""Small provisional holiday manifests, using existing BSP entity parsing.

Only decorated maps get effects. Props are visual-only; CSQC validates a flat
floor once at load. Light-centred mist is a bounded artist approximation; no
runtime entity-lump walk or dynamic light sampling. Edit these small records for
final event maps instead of modifying/repacking third-party BSPs.
"""
import argparse
import hashlib
import math
from pathlib import Path

from vbsp_env import Bsp, parse_entities

MAPS = ('surf_christmas', 'surf_frost', 'surf_bluewinter')
DEFAULT_MAPS = Path('C:/Program Files (x86)/Steam/steamapps/common/Momentum Mod Playtest/momentum/maps')


def point(e):
    try:
        p = tuple(map(float, e.get('origin', '').split()))
        if len(p) == 3 and all(math.isfinite(x) for x in p):
            return p
    except ValueError:
        pass
    return None


def distance(a, b):
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))


def records(entities):
    spawns = [point(e) for e in entities if e.get('classname') in
              ('info_player_start', 'info_player_terrorist', 'info_player_counterterrorist')]
    spawns = [p for p in spawns if p is not None]
    if not spawns:
        raise ValueError('no player spawn for provisional placement')
    start = spawns[0]
    props = []
    # Keep the centre/run line clear. Native models have no physics/collision here.
    for kind, x, y, yaw, scale in [(3, 144, 128, 30, 0.8), (2, -144, 128, -30, 1),
                                    (5, 112, -96, 15, 1), (6, -112, -96, 45, 1),
                                    (4, -192, 32, 10, 0.7), (1, 192, 32, -10, 1)]:
        props.append(f'prop {kind} {start[0]+x:g} {start[1]+y:g} {start[2]:g} {yaw:g} {scale:g}')
    lights = []
    for e in entities:
        if e.get('classname') not in ('light', 'light_spot'):
            continue
        p = point(e)
        if p is not None:
            lights.append((distance(p, start), p, e))
    chosen = []
    for dist, p, e in sorted(lights, key=lambda row: row[0]):
        if len(chosen) >= 12:
            break
        if dist < 240 or any(distance(p, q) < 300 for q in chosen):
            continue
        chosen.append(p)
    mist = []
    for p in chosen:
        # Move a little into the room, in front of the light rather than its solid fixture.
        length = max(distance(start, p), 1)
        q = tuple(p[i] + (start[i] - p[i]) / length * 64 for i in range(3))
        mist.append('mist ' + ' '.join(f'{v:.3f}' for v in (*q, 48, 0.78, 0.85, 1, *p)))
    return props, mist


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--maps', nargs='+', default=MAPS)
    ap.add_argument('--mapdir', type=Path, default=DEFAULT_MAPS)
    ap.add_argument('--out', type=Path, default=Path(__file__).resolve().parents[1] / 'ftesurf/gfx/winter')
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    for name in a.maps:
        if not name or any(not (c.isascii() and (c.isalnum() or c in '_-')) for c in name):
            ap.error('map basename required')
        path = a.mapdir / (name + '.bsp')
        bsp = Bsp(path)
        props, mist = records(parse_entities(bsp.lump(0).decode('latin1')))
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        data = [f'winter 1 {name}', f'// Provisional start decorations; BSP SHA256 {digest}', *props, *mist]
        (a.out / (name + '.txt')).write_text('\n'.join(data) + '\n', encoding='ascii')
        print(f'{name}: {len(props)} prop candidates, {len(mist)} light/mist candidates')


if __name__ == '__main__':
    main()
