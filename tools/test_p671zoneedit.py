#!/usr/bin/env python3
"""Grade P671's disposable hosted/remote and loader controls; silence is not a pass.

The fixture protocol retains its initial P670 labels; allocation moved to P671
when another session published P670 during testing. No prediction-arm tests change.
Main arm: cfg/test/p671zoneedit.cfg. Loader arm: cfg/test/p671settings.cfg,
with one data/maps/settings/local/surf_voyager.cfg fixture per owned overlay.
--loader-manifest is a JSON array of {name, exit, log}; valid plus the eight
named malformed fixtures are required. Never tests against a live install.
Synthetic input proves handler routing/ownership, NOT OS mouse/key delivery.
"""
import argparse
import json
import re
from pathlib import Path

STAMP = re.compile(r'^\d{4}-\d\d-\d\d \d\d:\d\d:\d\d ', re.M)


def read(path):
    return STAMP.sub('', Path(path).read_text(encoding='utf-8', errors='replace'))


def states(text):
    matches = list(re.finditer(r'^zone_edit: state (\d+) map \S+ zones (\d+) points (\d+) dirty (\d+) crc (\S+)', text, re.M))
    result = []
    for i, match in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        result.append(dict(state=int(match[1]), zones=int(match[2]), pts=int(match[3]),
                           dirty=int(match[4]), crc=match[5],
                           rows=re.findall(r'^zone_edit: zone \d+ (.*)$', text[match.end():end], re.M)))
    return result


def file_text(path):
    return path.read_text(encoding='utf-8') if path.is_file() else ''

NAMES = ('sv_maxvelocity', 'sv_gravity', 'sv_airaccelerate',
         'sv_accelerate', 'sv_maxspeed', 'sv_friction')
BAD = ('partial', 'unknown', 'duplicate', 'extra-token', 'nan', 'range',
       'oversize', 'embedded-nul')


def chunk(text, start, end):
    if start not in text or end not in text.split(start, 1)[1]:
        return ''
    return text.split(start, 1)[1].split(end, 1)[0]


def values(text, names=NAMES):
    result = []
    for name in names:
        found = re.findall(r'"' + name + r'" is "([0-9.]+)"', text)
        result.append(float(found[-1]) if found else None)
    return result


def rings(node):
    if isinstance(node, dict):
        if 'points' in node:
            yield node
        for child in node.values():
            yield from rings(child)
    elif isinstance(node, list):
        for child in node:
            yield from rings(child)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('log', type=Path)
    ap.add_argument('--loader-manifest', type=Path)
    ap.add_argument('--remote-log', type=Path)
    args = ap.parse_args()
    text = read(args.log)
    results = []

    def check(name, acted, ok):
        results.append((name, bool(ok) if acted else None))

    inp = chunk(text, 'P670 INPUT begin', 'P670 INPUT end')
    check('jump press/repeat and release after close', inp,
          'scan 32 down 0 took 0' in inp and
          len(re.findall(r'scan 32 down 1 took 1', inp)) == 3 and
          len(re.findall(r'Mouse: look', inp)) == 1 and
          'state 0 map' in inp and 'scan 32 down 0 took 1' in chunk(inp, 'zone_edit: off', 'P670 INPUT closed'))
    drag = chunk(text, 'P670 DRAG begin', 'P670 DRAG end')
    check('title drag changes position', drag,
          'window 908 112' in drag and 'window 278 182' in drag and 'scan 512 down 0 took 1' in drag)
    clamp = chunk(text, 'P670 CLAMP begin', 'P670 CLAMP end')
    check('drag clamps on screen', clamp, 'window 8 8' in clamp)
    edge = chunk(text, 'P670 EDGE begin', 'P670 EDGE end')
    snaps = re.findall(r'edge snap ([0-9.]+) ([0-9.]+) ([0-9.]+)', edge)
    check('corner priority, edge projection, Z-band refusal', len(snaps) == 3,
          snaps[0] == ('11136', '11136', '14272') and
          11136 <= float(snaps[1][0]) < 11140 and snaps[1][1:] == ('11250', '14272') and
          snaps[2] == ('11140', '11250', '15000'))
    single = chunk(text, 'P670 ROW single', 'P670 ROW double')
    double = chunk(text, 'P670 ROW double', 'P670 ROW end')
    mismatch = chunk(text, 'P670 ROW mismatch', 'P670 ROW mismatch end')
    check('single selects; double actually teleports', single and double,
          'zone_edit_goto' not in single and 'zone_goto: 0 -- start' in double and 'setpos ' in double)
    check('draft cannot warp to an unrelated server index', mismatch,
          'zones differ' in mismatch and 'zone_goto:' not in mismatch)
    before = states(chunk(text, 'P670 SNAP before', 'P670 SNAP after'))
    after = states(chunk(text, 'P670 SNAP after', 'P670 SNAP end'))
    check('Snap XYZ changes off-grid floor/top/ring', before and after,
          any('start track 9' in row and 'pts 4 z 5 118 box 1 3 45 61' in row for row in before[0]['rows']) and
          any('start track 9' in row and 'pts 4 z 0 128 box 0 0 48 64' in row for row in after[0]['rows']) and
          before[0]['crc'] != after[0]['crc'])
    resume = chunk(text, 'P670 RESUME before', 'P670 RESUME end')
    check('cursor toggle preserves a partly drawn polygon', resume,
          re.findall(r'cursor ([01]) polygon 1 corners 2', resume) == ['0', '1', '0'] and
          len(re.findall(r'state 5 map .* zones 0 points 0', resume)) == 3)
    before = states(chunk(text, 'P670 POLYGON before', 'P670 POLYGON after'))
    after = states(chunk(text, 'P670 POLYGON after', 'P670 POLYGON end'))
    check('six-point concave polygon survives save/readback', before and after,
          before[0]['zones'] == after[0]['zones'] == 1 and
          before[0]['pts'] == after[0]['pts'] == 6 and
          before[0]['crc'] == after[0]['crc'] and before[0]['rows'] == after[0]['rows'])
    bad = states(chunk(text, 'P670 INVALID status', 'P670 INVALID end'))
    check('crossed polygon cannot change the table', bad and after,
          bad[0]['state'] == 5 and bad[0]['crc'] == after[0]['crc'] and bad[0]['rows'] == after[0]['rows'])
    game = args.log.resolve().parent.parent
    path = game / 'data/maps/zones/local/surf_voyager.json'
    if path.is_file():
        saved = list(rings(json.loads(path.read_text(encoding='utf-8'))))
        ring = saved[0] if len(saved) == 1 else {}
        td = ring.get('teleDestPos', [])
        check('concave default spawn is inside, not in the cut-out', bool(td),
              len(ring.get('points', [])) == 6 and len(td) == 3 and
              11136 < td[0] < 11392 and 11136 < td[1] < 11392 and (td[0] < 11200 or td[1] < 11200))
    else:
        check('concave default spawn is inside, not in the cut-out', False, False)
    field = chunk(text, 'P670 FIELD begin', 'P670 FIELD end')
    check('numeric field edits survive jump; owned Enter repeat', field,
          'scan 127 down 1 took 1' in field and 'scan 127 down 0 took 1' in field and
          'maxvelocity 600\n' in field and len(re.findall(r'scan 13 down 1 took 1', field)) == 2)
    check('paste delivery reuses focused-field route (no OS clipboard read)', field,
          'synthetic paste took 0' in field and 'synthetic paste took 1' in field and
          'maxvelocity 600\n' in field)
    check('settings update preserves predecessor file', (game / 'data/maps/settings/local/surf_voyager.cfg').is_file(),
          'sv_maxvelocity 6000\n' in file_text(game / 'data/maps/settings/local/surf_voyager.cfg') and
          (game / 'data/maps/settings/local/surf_voyager.cfg.prev').is_file() and
          'sv_maxvelocity 600\n' in file_text(game / 'data/maps/settings/local/surf_voyager.cfg.prev'))
    baseline = chunk(text, 'P670 SETTINGS baseline', 'P670 SETTINGS reload')
    loaded = chunk(text, 'P670 SETTINGS reload', 'P670 SETTINGS loaded')
    check('settings ACT on the engine movement lock', baseline and loaded,
          values(baseline, NAMES[:3]) == [10000, 800, 150] and
          values(loaded, NAMES[:3]) == [6000, 700, 125] and 'map_settings: surf_voyager' in loaded)
    other = chunk(text, 'P670 SETTINGS othermap', 'P670 SETTINGS restored')
    lobby = chunk(text, 'P670 SETTINGS restored', 'P670 SETTINGS lobby')
    check('invalid file applies nothing; next map does not inherit', other,
          'invalid override ignored' in other and values(other, NAMES[:3]) == [3500, 800, 150])
    check('public-lobby guard uses original map rules', lobby,
          'map_settings: surf_voyager' not in lobby and values(lobby, NAMES[:3]) == [10000, 800, 150])
    check('runtime completed without VM/command errors', 'RUNLINES COMPLETE' in text,
          not re.search(r'boundcheck failed|Host_EndGame|Unknown command|Stack Overflow', text))

    if args.loader_manifest:
        manifest = json.loads(args.loader_manifest.read_text(encoding='utf-8'))
        cases = {case['name']: case for case in manifest}
        for name in ('valid',) + BAD:
            case = cases.get(name, {})
            log = Path(case.get('log', 'missing'))
            data = read(log) if log.is_file() else ''
            measured = chunk(data, 'P670 LOADER values', 'P670 LOADER end')
            expected = [6000, 700, 125, 8, 280, 3] if name == 'valid' else [10000, 800, 150, 5, 260, 4]
            acted = 'map_settings: surf_voyager' in data if name == 'valid' else 'invalid override ignored' in data
            check('loader ' + name, measured,
                  case.get('exit') == 0 and acted and values(measured) == expected and 'RUNLINES COMPLETE' in data)

    if args.remote_log:
        remote = read(args.remote_log)
        body = chunk(remote, 'P670 REMOTE begin', 'P670 REMOTE end')
        remote_game = args.remote_log.resolve().parent.parent
        cfg = remote_game / 'data/maps/settings/local/surf_voyager.cfg'
        check('remote console/synthetic cursor cannot write settings', body,
              body.count('Remote command refused') >= 3 and 'settings saved' not in body and
              'sv_maxvelocity 9000' in file_text(cfg) and not cfg.with_suffix('.cfg.prev').exists())
        check('dedicated ignores a valid local editor override', body,
              'map_settings: surf_voyager' not in remote and r'\sv_maxvelocity\10000' in remote and
              'RUNLINES COMPLETE' in remote)

    for name, ok in results:
        print('%-12s %s' % ('NOT MEASURED' if ok is None else ('ok' if ok else 'FAIL'), name))
    counts = [sum(ok is status for _, ok in results) for status in (True, False, None)]
    print('P671: %d passed, %d failed, %d not measured, of %d' % (*counts, len(results)))
    return 1 if counts[1] else (2 if counts[2] else 0)


if __name__ == '__main__':
    raise SystemExit(main())
