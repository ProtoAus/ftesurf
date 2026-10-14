"""Strict offline eligibility of three fixed stations for exact stationary sampling.

This diagnostic-only probe never accepts production performance or promotes mode2.
Changing authored animation makes a station INELIGIBLE, not a renderer defect.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re

import p690ordinary as ordinary
from p690cache import GateError, HASHES, STAMPS, parse_actor, require, sha

STATIONS = {
    'kitsune': dict(map='surf_kitsune', camera=(-14986.3, -14484.8, 772.3, 19.3, 125.6, 0), glare=.025),
    'tensor': dict(map='surf_tensor2', camera=(-11154.8291, -13481.6270, 13680.0312, 20.3577, 56.1566, 0), glare=.2),
    'demise': dict(map='surf_demise', camera=(-10303.4502, -6446.7588, 13508.9854, 8.2727, 74.8004, 0), glare=.025),
}
EXTRA_SETTINGS = dict(hl2_water=2, hl2_envmap=1, r_refractreflect_scale=1)


def state(row, station):
    require(row['arm'] == 'probe' and type(row['mode']) is int and row['mode'] in (1, 2)
            and row['phase'] == 'ordinary', 'unknown station mode state')
    expected = dict(ordinary.SETTINGS, **ordinary.QUIET_SETTINGS, **EXTRA_SETTINGS,
                    vbsp_glare_interval=station['glare'], r_blendsort=row['mode'])
    settings = row['settings']
    require('Effective' not in settings, 'locked effective station state')
    for key, value in expected.items():
        matches = re.findall(rf'"{key}" is "([^"\n]+)"', settings)
        require(len(matches) == 1, 'missing/duplicate station cvar ' + key)
        try:
            actual = float(matches[0])
        except ValueError as exc:
            raise GateError('malformed station cvar ' + key) from exc
        require(actual == value, 'wrong station cvar ' + key)
    p = re.findall(r'origin ([-\d.]+) ([-\d.]+) ([-\d.]+)\s+angles ([-\d.]+) ([-\d.]+) ([-\d.]+)', row['info'])
    require(len(p) == 1 and all(abs(float(a) - b) < .06 for a, b in zip(p[0], station['camera'])), 'wrong station body/aim')
    require(row['info'].count('velocity 0.0000 0.0000 0.0000') == 1, 'nonstationary station body')
    require(re.search(rf'timer (?:armed|idle|running) on {re.escape(station["map"])}(?:,|\s|$)', row['info']) is not None,
            'wrong station info world')


def actor(row, station):
    require(type(row['mode']) is int and row['mode'] in (1, 2) and row['rep'] in ('a', 'b'), 'unknown station actor')
    text = row['text']
    require(text.count('MV11_CACHE ticket=') == text.count('MV11_VIEW eye=') == 1, 'missing/duplicate station postdraw')
    a = parse_actor(text)
    require(a['world'] == f"maps/{station['map']}.bsp" and a['fromgame'] == 4
            and a['mode'] == row['mode'] and a['requested'] == a['inuse'] == a['cached'] == 0,
            'wrong station ordinary postdraw')
    eye, angles = a['eye'].split(','), a['angles'].split(',')
    require(len(eye) == len(angles) == 3, 'malformed station postdraw camera')
    require(all(abs(float(x) - y - z) < .15 for x, y, z in zip(eye, station['camera'][:3], (0, 0, 64))), 'wrong station postdraw eye')
    require(all(abs(float(x) - y) < .06 for x, y in zip(angles, station['camera'][3:])), 'wrong station postdraw aim')
    return a


def grade(root):
    import numpy as np
    from PIL import Image
    root = Path(root)
    d = json.loads((root / 'capture.json').read_text())
    require(type(d['schema']) is int and d['schema'] == 2 and d['restored'] is True, 'missing station restoration closure')
    require(d['station'] in STATIONS, 'unknown fixed station')
    station = STATIONS[d['station']]
    for key in ('protocol_sha256', 'driver_sha256', 'helper_sha256'):
        require(re.fullmatch('[0-9a-f]{64}', str(d.get(key, ''))) is not None, 'missing station provenance ' + key)
    before = json.loads((root / 'before.json').read_text())
    after = json.loads((root / 'restoration.json').read_text())
    require(after['restored'] is True and all(before[k] == after[k] for k in ('subject', 'installs', 'fixtures')), 'station restoration mismatch')
    require(set(before['subject']) == {*HASHES['merged'], 'ftesurf64.exe'}
            and len(before['installs']) == 2 and bool(before['fixtures']), 'incomplete station restoration inventory')
    require(d['stops'] == {'probe': dict(cl='quit, rc 0', sv='quit, rc 0')}, 'missing station rc0 stops')
    require(set(d['bundles']) == {'probe'}, 'wrong station probe bundle set')
    b = d['bundles']['probe']
    require(b['hashes'] == b['staged'] == HASHES['probe'] and STAMPS['probe'] in b['version']
            and '"vid_renderer" is "gl"' in b['version'], 'wrong exact station probe bundle/renderer')
    states = [(r['mode'], r['phase']) for r in d['modes']]
    require(len(states) == 2 and set(states) == {(1, 'ordinary'), (2, 'ordinary')}, 'missing/duplicate station state')
    for r in d['modes']:
        state(r, station)
    actors = {}
    for r in d['actors']:
        key = r['mode'], r['rep']
        require(key not in actors, 'duplicate station actor identity')
        actors[key] = actor(r, station)
    require(set(actors) == {(m, r) for m in (1, 2) for r in ('a', 'b')}, 'missing station actor')
    require(len({a['ticket'] for a in actors.values()}) == 4, 'stale station actor ticket')
    advances = {}
    for mode in (1, 2):
        a, b = actors[mode, 'a'], actors[mode, 'b']
        require(b['ticket'] > a['ticket'] and b['ordinary'] - a['ordinary'] >= 128, 'station ordinary did not advance128')
        require(a['eye'] == b['eye'] and a['angles'] == b['angles'], 'station rendered camera drift')
        advances[mode] = dict(draw_advance=b['ordinary'] - a['ordinary'], eye=a['eye'], angles=a['angles'])
    require(actors[1, 'a']['eye'] == actors[2, 'a']['eye']
            and actors[1, 'a']['angles'] == actors[2, 'a']['angles'], 'station mode camera drift')
    images, shot_paths = {}, set()
    for r in d['shots']:
        key = r['mode'], r['rep']
        require(r['arm'] == 'probe' and type(r['mode']) is int and key not in images, 'unknown/duplicate station PNG')
        require(r['path'] not in shot_paths, 'reused station PNG path')
        shot_paths.add(r['path'])
        with Image.open(ordinary.blob(root, r)) as im:
            require(im.format == 'PNG' and im.mode == 'RGB' and im.size == (960, 720), 'wrong station PNG format/size')
            image = np.asarray(im).copy()
        require(len(np.unique(image[::8, ::8].reshape(-1, 3), axis=0)) > 32, 'degenerate station PNG')
        images[key] = image
    require(set(images) == {(1, r) for r in ('hud-on', 'hud-off', 'hud-return', 'before', 'after')}
            | {(2, r) for r in ('before', 'after')}, 'missing/extra station PNG')
    samples, seen, paths, previous_end = [], set(), set(), 0
    expected = {('probe', m, 'cost', 'ordinary', r) for m in (1, 2) for r in range(2)}
    for r in d['samples']:
        key = r['arm'], r['mode'], r['metric'], r['phase'], r['rep']
        require(type(r['mode']) is int and type(r['rep']) is int and key in expected and key not in seen, 'unknown/duplicate station sample')
        seen.add(key)
        for name in (r['path'], r['wait']['path']):
            require(name not in paths, 'reused station sample/witness path')
            paths.add(name)
        start = ordinary.finite(r['start'], 'station sample start', positive=True)
        end = ordinary.finite(r['end'], 'station sample end', positive=True)
        require(previous_end < start < end, 'overlapping station sample commands')
        previous_end = end
        text = ordinary.sample_record(root, r, 2)
        require(re.findall(r'"r_speeds" is "([^"\n]+)"', text) == ['2'] and 'Effective' not in text, 'wrong station sampled r_speeds')
        window, cost = ordinary.cadence(text), ordinary.cost(text)
        require(window['mode'] == 2, 'wrong station sampled pacing')
        peers = [s for s in samples if s['mode'] == r['mode']]
        require(r['rep'] == len(peers), 'station sample sequence not consecutive')
        if peers:
            require(start - peers[-1]['end'] >= 3
                    and start - peers[-1]['end'] > window['count'] * window['avg_ms'] / 1000, 'overlapping station sampler windows')
            require(cost['fingerprint'] != peers[-1]['cost']['fingerprint'], 'stale station cost block')
        samples.append(dict(mode=r['mode'], rep=r['rep'], start=start, end=end, cadence=window, cost=cost))
    require(seen == expected, 'missing station sampler activity')

    def diff(a, b):
        changed = np.any(images[a] != images[b], axis=2)
        y, x = np.where(changed)
        return dict(changed_pixels=int(changed.sum()), bounds=None if not len(x)
                    else [int(x.min()), int(y.min()), int(x.max()), int(y.max())])

    hud_acted = diff((1, 'hud-on'), (1, 'hud-off'))
    hud_return = diff((1, 'hud-on'), (1, 'hud-return'))
    repeats = {m: diff((m, 'before'), (m, 'after')) for m in (1, 2)}
    failures = []
    if hud_acted['changed_pixels'] <= 1000:
        failures.append('HUD control did not act >1000pixels')
    if hud_return['changed_pixels']:
        failures.append('HUD-on fullframe return differs')
    failures += [f'mode{m} fullframe repeat differs' for m, r in repeats.items() if r['changed_pixels']]
    eligible = not failures
    return dict(verdict='ELIGIBLE exact stationary probe' if eligible else 'INELIGIBLE exact stationary protocol',
                eligible=eligible, station=d['station'], map=station['map'], failures=failures,
                hud_on_off=hud_acted, hud_return=hud_return, repeats=repeats, actors=advances,
                diagnostic_samples=samples, protocol_sha256=d['protocol_sha256'], driver_sha256=d['driver_sha256'],
                helper_sha256=d['helper_sha256'], receipts={n: sha(root / n) for n in ('capture.json', 'before.json', 'restoration.json')},
                scope='Diagnostic eligibility only; no production A/B/A, timing acceptance, animation defect, broad-map/default2 promotion or GPU/display proof')


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('capture', type=Path)
    args = ap.parse_args()
    try:
        result = grade(args.capture)
        print(json.dumps(result, indent=2))
        return 0 if result['eligible'] else 1
    except (GateError, KeyError, TypeError, ValueError, OSError) as exc:
        print(json.dumps(dict(verdict='INVALID station probe evidence', error=str(exc)), indent=2))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
