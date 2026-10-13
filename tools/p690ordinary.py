"""Strict OFFLINE gate for the pinned P690 stationary ordinary-render capture.

No launch, staging, install writes or performance inference beyond this station.
Present cadence and CPU-side refresh service cost are deliberately separate.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import re
import statistics

from p690cache import GateError, HASHES, STAMPS, parse_actor, require, sha

ARMS = ('p688', 'merged', 'p688-return')
ALL_ARMS = ('probe', *ARMS)
LIMIT = 1.20
SETTINGS = dict(r_temporalscenecache=0, r_wateralpha_extendpvs=0, r_novis=0,
    hl2_translucent=1, hl2_refract=2, fov=100, vid_srgb=0, r_renderscale=2,
    vid_vsync=0, gl_finish=0, cl_idlefps=0, cl_maxfps=100, sys_framepacing=2,
    sys_framepacing_drain=2, r_speeds=0)
QUIET_SETTINGS = {
    **{key: 0 for key in ('hud_timer', 'hud_mapinfo', 'hud_mouse', 'hud_energy',
        'hud_board', 'hud_specby', 'hud_debug', 'hud_seq', 'hud_strafe', 'hud_keys',
        'hud_speed', 'hud_crosshair', 'hud_chat', 'sensitivity', 'm_yaw', 'm_pitch',
        'in_windowed_mouse', 'r_hdr_irisadaptation', 'r_hdr_framebuffer', 'cl_nopred',
        'cl_netfps')},
    'cl_predict_extrapolate': 1, 'cl_predict_timenudge': .5,
}
CAMERA = (-14986.3, -14484.8, 772.3, 19.3, 125.6, 0)
EYE = (-14986.237, -14484.737, 836.362)


def finite(value, label, positive=False):
    require(isinstance(value, (int, float)) and not isinstance(value, bool)
            and math.isfinite(value) and (value > 0 if positive else value >= 0),
            f'{label}: invalid finite number')
    return float(value)


def blob(root, row):
    name = row['path']
    require(isinstance(name, str) and Path(name).name == name and name not in ('', '.', '..'), 'unsafe evidence path')
    p = root / name
    require(p.is_file() and not p.is_symlink() and not getattr(p.lstat(), 'st_file_attributes', 0) & 1024,
            f'missing/linked evidence {name}')
    require(sha(p) == row['sha256'], f'evidence hash mismatch {name}')
    return p


def clean(text):
    return re.sub(r'^\d{4}-\d\d-\d\d \d\d:\d\d:\d\d ', '', text, flags=re.M)


def cadence(text):
    text = clean(text)
    count = re.findall(r'Present cadence \(last (\d+) swaps\):', text)
    mode = re.findall(r'^sys_framepacing mode: (\d+)$', text, re.M)
    interval = re.findall(r'interval\s+: avg ([\d.]+) ms \(([\d.]+) fps\)  min ([\d.]+)  max ([\d.]+) ms', text)
    jitter = re.findall(r'jitter \(stddev\)\s+: ([\d.]+) us\s+spread \(max-min\) ([\d.]+) us', text)
    require(len(count) == len(mode) == len(interval) == len(jitter) == 1, 'cadence: missing/duplicate/malformed sample')
    require(int(count[0]) == 128, 'cadence: needs full128-swap ring')
    avg, fps, low, high = map(float, interval[0])
    std, spread = map(float, jitter[0])
    for n, v in zip(('avg', 'fps', 'min', 'max', 'jitter', 'spread'), (avg, fps, low, high, std, spread)):
        finite(v, 'cadence ' + n, positive=n in ('avg', 'fps', 'min', 'max'))
    require(low <= avg <= high and std <= spread + 2, 'cadence: invalid range/jitter')
    require(abs(spread - (high - low) * 1000) <= 2, 'cadence: spread mismatch')
    require(abs(fps - 1000 / avg) <= max(.2, fps * .002), 'cadence: interval/fps mismatch')
    return dict(mode=int(mode[0]), count=128, avg_ms=avg, min_ms=low, max_ms=high,
                jitter_us=std, spread_us=spread)


def cost(text):
    text = clean(text)
    blocks = re.findall(r'---- r_speeds_dump \(us/frame, (\d+)-frame average\) ----\n(.*?)---- end r_speeds_dump ----', text, re.S)
    require(len(blocks) == 1 and int(blocks[0][0]) == 100
            and len(re.findall(r'^---- r_speeds_dump ', text, re.M)) == 1
            and text.splitlines().count('---- end r_speeds_dump ----') == 1,
            'cost: needs exactly one full100-frame block')
    pairs = re.findall(r'^\s*([-+\w.]+) ([^\n]+)$', blocks[0][1], re.M)
    values = {}
    for v, label in pairs:
        label = label.strip()
        require(label not in values, 'cost: duplicate bucket')
        try:
            values[label] = float(v)
        except ValueError as exc:
            raise GateError('cost: malformed number') from exc
        finite(values[label], 'cost ' + label)
    names = ('Total refresh', 'r_speeds overhead', 'Transparent Batches', 'Frame pacing', 'Draw Calls', 'World Batches', 'Draw Indicies')
    require(all(n in values for n in names), 'cost: missing timing/draw bucket')
    adjusted = values['Total refresh'] - values['r_speeds overhead']
    finite(adjusted, 'cost adjusted refresh', positive=True)
    require(all(values[n] > 0 for n in ('Transparent Batches', 'Draw Calls', 'World Batches', 'Draw Indicies')), 'cost: absent world/transparent draw activity')
    require(all(values[n].is_integer() for n in ('Draw Calls', 'World Batches', 'Draw Indicies')), 'cost: fractional draw quantity')
    return dict(raw_us=values['Total refresh'], observer_us=values['r_speeds overhead'], adjusted_us=adjusted,
                transparents_us=values['Transparent Batches'], pacing_us=values['Frame pacing'],
                draws=values['Draw Calls'], world_batches=values['World Batches'], indices=values['Draw Indicies'],
                fingerprint=tuple(sorted(values.items())))


def mode_state(row, quiet=False):
    require(row['arm'] in ALL_ARMS and type(row['mode']) is int and row['mode'] in (1, 2), 'unknown mode identity')
    expected = dict(SETTINGS, **(QUIET_SETTINGS if quiet else {}), r_blendsort=row['mode'])
    if row['phase'] == 'slow':
        expected.update(sys_framepacing=4, cl_maxfps=20)
    require(row['phase'] in ('ordinary', 'slow', 'timing-return'), 'unknown phase')
    settings = row['settings']
    require('Effective' not in settings, 'locked effective cvar not supported')
    for key, value in expected.items():
        found = re.findall(rf'"{key}" is "([^"\n]+)"', settings)
        require(len(found) == 1, f'missing/duplicate cvar {key}')
        try:
            actual = float(found[0])
        except ValueError as exc:
            raise GateError('malformed cvar ' + key) from exc
        require(math.isfinite(actual) and actual == value, 'wrong cvar ' + key)
    info = row['info']
    p = re.search(r'origin ([-\d.]+) ([-\d.]+) ([-\d.]+)\s+angles ([-\d.]+) ([-\d.]+) ([-\d.]+)', info)
    require(p and all(abs(float(a) - b) < .06 for a, b in zip(p.groups(), CAMERA)), 'wrong stationary camera')
    require('velocity 0.0000 0.0000 0.0000' in info, 'nonstationary body')


def stats(rows, metric):
    name = 'avg_ms' if metric == 'cadence' else 'adjusted_us'
    values = [r[name] for r in rows]
    out = dict(groups=len(values), values=values, median=statistics.median(values), min=min(values), max=max(values))
    if metric == 'cadence':
        out['jitter_us'] = [r['jitter_us'] for r in rows]
        out['max_interval_ms'] = [r['max_ms'] for r in rows]
    else:
        for name in ('raw_us', 'observer_us', 'transparents_us', 'pacing_us', 'draws', 'world_batches', 'indices'):
            out[name] = [r[name] for r in rows]
    return out


def sample_record(root, row, schema):
    """Schema2 binds a complete current-send primary to a hashed completion wait."""
    raw = blob(root, row).read_text()
    text = clean(raw)
    if schema == 2:
        ticket = f"{row['arm']}_m{row['mode']}_{row['metric']}_{row['phase']}_{row['rep']}"
        require(row.get('ticket') == ticket, 'wrong sample ticket identity')
        begin = 'MV14_BEGIN_' + ticket
        end = '---- end r_speeds_dump ----' if row['metric'] == 'cost' else 'MV14_END_' + ticket
        lines = [line for line in text.splitlines() if line.strip()]
        require(lines and lines[0] == begin and lines[-1] == end
                and lines.count(begin) == lines.count(end) == 1
                and len(re.findall(r'^MV14_BEGIN_', text, re.M)) == 1,
                'missing/duplicate/unbounded sample ticket')
        witness = row.get('wait')
        require(isinstance(witness, dict), 'missing sample wait witness')
        start = finite(witness.get('start'), 'sample wait start', positive=True)
        stop = finite(witness.get('end'), 'sample wait end', positive=True)
        require(start == row['start'] and start < stop <= row['end'], 'sample wait interval mismatch')
        wait = blob(root, witness).read_text().strip()
        match = re.fullmatch(r'MATCH cl after \d+(?:\.\d+)? s: (\d{4}-\d\d-\d\d \d\d:\d\d:\d\d '
                + re.escape(end) + ')', wait)
        require(match is not None, 'sample completion wait did not act')
        require(match[1] == [line for line in raw.splitlines() if line.strip()][-1],
                'sample completion witness/primary mismatch')
    if row['metric'] == 'cadence':
        require('r_speeds_dump' not in text, 'cost report in cadence-only sample')
    return text


def grade(root):
    import numpy as np
    from PIL import Image
    root = Path(root)
    data = json.loads((root / 'capture.json').read_text())
    schema = data['schema']
    require(type(schema) is int and schema in (1, 2) and data['restored'] is True, 'missing restoration closure')
    if schema == 2:
        require(all(re.fullmatch(r'[0-9a-f]{64}', str(data.get(k, ''))) for k in
                ('protocol_sha256', 'driver_sha256')), 'missing quiet protocol/driver provenance')
    before = json.loads((root / 'before.json').read_text())
    restoration = json.loads((root / 'restoration.json').read_text())
    require(restoration['restored'] is True and all(before[k] == restoration[k]
            for k in ('subject', 'installs', 'fixtures')), 'fixture/native/install restoration mismatch')
    require(set(before['subject']) == {*HASHES['merged'], 'ftesurf64.exe'}
            and len(before['installs']) == 2 and bool(before['fixtures']), 'incomplete restoration inventory')
    require(set(data['stops']) == set(ALL_ARMS) and all(s == dict(cl='quit, rc 0', sv='quit, rc 0')
            for s in data['stops'].values()), 'missing native rc0 stop closure')
    require(set(data['bundles']) == set(ALL_ARMS), 'missing/extra production/probe bundle')
    for arm, bundle in data['bundles'].items():
        require(bundle['hashes'] == bundle['staged'] == HASHES[arm], 'wrong exact bundle ' + arm)
        require(STAMPS[arm] in bundle['version'], 'wrong version stamp ' + arm)
        require('"vid_renderer" is "gl"' in bundle['version'], 'wrong renderer ' + arm)
    expected_states = {(a, m, 'ordinary') for a in ALL_ARMS for m in (1, 2)} | {
        ('merged', 2, 'slow'), ('merged', 2, 'timing-return')}
    states = [(r['arm'], r['mode'], r['phase']) for r in data['modes']]
    require(len(states) == len(set(states)) and set(states) == expected_states, 'missing/duplicate mode state')
    for row in data['modes']:
        mode_state(row, quiet=schema == 2)
    actors = {}
    for row in data['actors']:
        key = row['mode'], row['rep']
        require(key not in actors, 'duplicate postdraw actor')
        require(row['mode'] in (1, 2) and row['rep'] in ('a', 'b')
                and row['text'].count('MV11_CACHE ticket=') == row['text'].count('MV11_VIEW eye=') == 1,
                'malformed/duplicate postdraw actor')
        a = parse_actor(row['text'])
        require(a['world'] == 'maps/surf_kitsune.bsp' and a['fromgame'] == 4 and a['mode'] == row['mode']
                and a['requested'] == a['inuse'] == 0 and a['cached'] == 0, 'wrong ordinary postdraw actor')
        eye = a['eye'].split(',')
        require(len(eye) == 3 and all(abs(float(x) - y) < .002 for x, y in zip(eye, EYE)), 'wrong postdraw eye')
        require(a['angles'] == '19.297,125.601,0.000', 'wrong postdraw angles')
        actors[key] = a
    require(set(actors) == {(m, r) for m in (1, 2) for r in ('a', 'b')}, 'missing postdraw actor')
    tickets = [actors[k]['ticket'] for k in sorted(actors)]
    require(len(set(tickets)) == 4, 'stale postdraw ticket')
    for m in (1, 2):
        a, b = actors[m, 'a'], actors[m, 'b']
        require(b['ticket'] > a['ticket'] and b['ordinary'] - a['ordinary'] >= 128, 'postdraw counter did not advance128')
    pictures = {}
    for row in data['shots']:
        key = row['arm'], row['mode'], row['rep']
        require(key not in pictures, 'duplicate screenshot identity')
        with Image.open(blob(root, row)) as im:
            require(im.format == 'PNG' and im.mode == 'RGB', 'not RGB PNG')
            image = np.asarray(im).copy()
        require(image.shape == (720, 960, 3), 'wrong PNG size')
        require(len(np.unique(image[::8, ::8].reshape(-1, 3), axis=0)) > 32, 'empty/degenerate station PNG')
        pictures[key] = image
    expected_shots = {(a, m, r) for a in ALL_ARMS for m in (1, 2) for r in ('before', 'after')} | {('merged', 2, 'timing-return')}
    require(set(pictures) == expected_shots, 'missing/extra station screenshot')
    for arm in ALL_ARMS:
        for m in (1, 2):
            require(np.array_equal(pictures[arm, m, 'before'], pictures[arm, m, 'after']), 'unstable station repeat')
    for m in (1, 2):
        require(np.array_equal(pictures['p688', m, 'before'], pictures['p688-return', m, 'before']), 'failed P688 pixel return')
        require(np.array_equal(pictures['probe', m, 'before'], pictures['merged', m, 'before']), 'diagnostic/production pixel mismatch')
    require(np.array_equal(pictures['merged', 1, 'before'], pictures['p688', 1, 'before']), 'mode1 product pixels changed')
    acted = int(np.any(pictures['merged', 2, 'before'] != pictures['p688', 2, 'before'], axis=2).sum())
    require(acted > 1000, 'mode2 sorter did not act on station pixels')
    require(np.array_equal(pictures['merged', 2, 'timing-return'], pictures['merged', 2, 'before']), 'failed timing-control pixel return')
    expected = {(a, m, metric, 'ordinary', r) for a in ARMS for m in (1, 2)
                for metric in ('cadence', 'cost') for r in range(6)} | {
                ('merged', 2, metric, 'slow', r) for metric in ('cadence', 'cost') for r in range(2)} | {
                ('merged', 2, 'cadence', 'timing-return', r) for r in range(2)}
    seen, paths, groups = set(), set(), {}
    previous_end = 0
    for row in data['samples']:
        key = row['arm'], row['mode'], row['metric'], row['phase'], row['rep']
        require(type(row['mode']) is int and type(row['rep']) is int and key in expected
                and key not in seen and row['path'] not in paths, 'unknown/duplicate sample identity/path')
        seen.add(key); paths.add(row['path'])
        start = finite(row['start'], 'sample start', positive=True)
        end = finite(row['end'], 'sample end', positive=True)
        require(end > start and start > previous_end, 'invalid/overlapping command interval')
        previous_end = end
        text = sample_record(root, row, schema)
        if schema == 2:
            witness_path = row['wait']['path']
            require(witness_path not in paths, 'reused sample completion witness path')
            paths.add(witness_path)
        speeds = re.findall(r'"r_speeds" is "([^"\n]+)"', text)
        require(speeds == ['0' if row['metric'] == 'cadence' else '2'] and 'Effective' not in text,
                'wrong sampled r_speeds (never accept3/GPU finishes)')
        window = cadence(text)
        require(window['mode'] == (4 if row['phase'] == 'slow' else 2), 'wrong sampled pacing mode')
        parsed = window if row['metric'] == 'cadence' else dict(cost(text), cadence_witness=window)
        group = key[:4]
        rows = groups.setdefault(group, [])
        if rows:
            require(row['rep'] == rows[-1]['rep'] + 1, 'sample sequence not consecutive')
            gap = start - rows[-1]['end']
            require(gap >= (8 if row['phase'] == 'slow' else 3), 'insufficient sample separation')
            require(gap > window['count'] * window['avg_ms'] / 1000, 'overlapping cadence rings')
            if row['metric'] == 'cost':
                require(all(parsed['fingerprint'] != p['fingerprint'] for p in rows), 'stale100-frame timing block')
        else:
            require(row['rep'] == 0, 'sample sequence must start0')
        rows.append(dict(rep=row['rep'], start=start, end=end, **parsed))
    require(seen == expected, 'missing stationary timing samples')
    summary = {f'{a}/m{m}/{metric}/{phase}': stats(rows, metric) for (a, m, metric, phase), rows in groups.items()}
    comparisons = []
    for m in (1, 2):
        for metric in ('cadence', 'cost'):
            med = lambda arm, phase='ordinary': summary[f'{arm}/m{m}/{metric}/{phase}']['median']
            initial, subject, returned = med('p688'), med('merged'), med('p688-return')
            require(.80 <= returned / initial <= LIMIT, f'P688 return drift m{m} {metric}')
            require(subject / initial <= LIMIT and subject / returned <= LIMIT, f'merged regression m{m} {metric}')
            comparisons.append(dict(mode=m, metric=metric, merged_initial=subject / initial,
                                    merged_return=subject / returned, return_initial=returned / initial))
    slow_cad = summary['merged/m2/cadence/slow']['median'] / summary['merged/m2/cadence/ordinary']['median']
    slow_cost = summary['merged/m2/cost/slow']['median'] / summary['merged/m2/cost/ordinary']['median']
    require(slow_cad > 3 and slow_cost > 3 and all(v > 20000 for v in summary['merged/m2/cost/slow']['pacing_us']), 'native timing slowdown did not act')
    returned = summary['merged/m2/cadence/timing-return']['median'] / summary['merged/m2/cadence/ordinary']['median']
    require(.80 <= returned <= LIMIT, 'failed timing-control cadence return')
    return dict(verdict='PASS bounded ordinary stationary cadence/service cost', capture_schema=schema,
                protocol_sha256=data.get('protocol_sha256'), driver_sha256=data.get('driver_sha256'), groups=summary,
                comparisons=comparisons, mode2_acted_pixels=acted,
                control=dict(cadence_ratio=slow_cad, cost_ratio=slow_cost, cadence_return_ratio=returned),
                receipts={name: sha(root / name) for name in ('capture.json', 'before.json', 'restoration.json')},
                scope='Kitsune fixed station; cap100; GL WGL swap-return cadence, NOT display/GPU completion; overlay-adjusted CPU-side refresh, NOT whole-host-frame/GPU time; no broad/default2 acceptance')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('capture', type=Path, help='read-only directory containing capture.json/logs/PNGs')
    args = p.parse_args()
    try:
        print(json.dumps(grade(args.capture), indent=2))
        return 0
    except (GateError, KeyError, TypeError, ValueError, OSError) as exc:
        print('FAIL ordinary stationary gate: ' + str(exc))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
