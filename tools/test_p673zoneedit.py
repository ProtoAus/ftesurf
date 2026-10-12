#!/usr/bin/env python3
"""Grade P673 acting hosted controls and optional native loader manifest.
The pre-claim development logs used P672 markers; normalize that prefix only.
"""
import argparse
import json
import re
from pathlib import Path


def read(path):
    return re.sub(r'^\d{4}-\d\d-\d\d \d\d:\d\d:\d\d ', '',
                  Path(path).read_text(encoding='utf-8', errors='replace').replace('P673 ', 'P672 '), flags=re.M)


def between(text, start, end):
    a = text.find(start)
    b = text.find(end, a + len(start)) if a >= 0 else -1
    return text[a + len(start):b] if b >= 0 else ''


def values(text, names):
    out = []
    for name in names:
        hits = re.findall(r'"' + re.escape(name) + r'" is "([^"]+)"[^\n]*', text)
        if not hits:
            return None
        effective = re.findall(r'Effective value: "([^"]+)"', text)
        # Tests never deliberately write locked values; first read is effective.
        out.append(float(hits[-1]))
    return out


def rings(node):
    if isinstance(node, dict):
        if 'points' in node:
            yield node
        for v in node.values():
            yield from rings(v)
    elif isinstance(node, list):
        for v in node:
            yield from rings(v)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('log', type=Path)
    ap.add_argument('--loader-manifest', type=Path)
    args = ap.parse_args()
    text = read(args.log)
    results = []

    def check(name, ok):
        results.append(bool(ok))
        print(('ok   ' if ok else 'FAIL ') + name)

    start = between(text, 'P672 SPAWN set', 'P672 SPAWN reset')
    reset = between(text, 'P672 SPAWN reset', 'P672 SPAWN reloaded')
    check('spawn setter ACTED before reset', re.search(r'zone 0 start .* td 1 ', start))
    check('reset clears custom destination and survives save/reload',
          'spawn reset to the zone' in reset and
          len(re.findall(r'zone 0 start .* td 0 0 0 0 0 \[\]', reset)) >= 2)
    concave = between(text, 'P672 SPAWN reloaded', 'P672 CONCAVE reset')
    check('concave reset keeps an explicit safe zone-derived floor point',
          'spawn reset to the zone' in concave and
          re.search(r'zone 0 start .* pts 6 .* td 1 ', concave))
    empty = between(text, 'P672 CONCAVE reset', 'P672 SPAWN no-selection')
    check('empty-selection reset does not invent a zone', re.search(r'zones 0 points 0', empty))
    bhop = between(text, 'P672 BHOP effective', 'P672 SURF staged')
    surf = between(text, 'P672 SURF effective', 'P672 OTHER effective')
    names = ('sv_airaccelerate', 'pm_ticrate', 'sv_mintic', 'sv_maxtic', 'run_starthop')
    check('Bhop applies native mode, AA and all three 100 Hz clocks',
          'movement: bhop on surf_voyager, from local editor' in bhop and
          values(bhop, names) == [1000, 0.01, 0.01, 0.01, 0])
    check('Surf overrides forced Bhop and restores 66.67 Hz base mode',
          'movement: surf on surf_voyager, from local editor' in surf and
          values(surf, names) == [150, 0.015, 0.015, 0.015, 1])
    check('mode changes preserve the chosen speed cap',
          values(bhop, ('sv_maxvelocity',)) == values(surf, ('sv_maxvelocity',)) == [6000])
    other = between(text, 'P672 OTHER effective', 'P672 END')
    check('next unedited map does not inherit mode overrides',
          'from local editor' not in other and
          values(other, names[:4]) == [150, 0.015, 0.015, 0.015])
    game = args.log.resolve().parent.parent
    saved = game / 'data/maps/settings/local/surf_voyager.cfg'
    previous = Path(str(saved) + '.prev')
    expected = 'gamemode 1\nsv_maxvelocity 6000\nsv_gravity 800\nsv_airaccelerate 150\n'
    check('only mode plus three visible settings are serialized', saved.is_file() and
          saved.read_text(encoding='utf-8') == expected)
    check('atomic replacement preserves the Bhop predecessor', previous.is_file() and
          previous.read_text(encoding='utf-8') == expected.replace('gamemode 1', 'gamemode 2').replace('150\n', '1000\n'))
    zonefile = game / 'data/maps/zones/local/surf_voyager.json'
    rs = list(rings(json.loads(zonefile.read_text()))) if zonefile.is_file() else []
    p = rs[0].get('teleDestPos', []) if len(rs) == 1 else []
    check('saved concave spawn is inside the L, not the cut-out', len(p) == 3 and
          11136 < p[0] < 11392 and 11136 < p[1] < 11392 and
          (p[0] < 11200 or p[1] < 11200))
    check('main completed without VM/command errors', 'RUNLINES COMPLETE' in text and
          not re.search(r'boundcheck failed|Host_EndGame|Unknown command|Stack Overflow', text))
    if args.loader_manifest:
        for case in json.loads(args.loader_manifest.read_text()):
            data = read(case['log'])
            chunk = between(data, 'P670 LOADER values', 'P670 LOADER end')
            keys = ('sv_maxvelocity', 'sv_gravity', 'sv_airaccelerate',
                    'sv_accelerate', 'sv_maxspeed', 'sv_friction',
                    'pm_ticrate', 'sv_mintic', 'sv_maxtic')
            expected_values = case['expected']
            acted = ('map_settings: surf_voyager' in data if case['valid'] else
                     'invalid override ignored' in data)
            check('loader ' + case['name'], 'RUNLINES COMPLETE' in data and acted and
                  values(chunk, keys) == expected_values and
                  not re.search(r'Unknown command|boundcheck failed|Host_EndGame', data))
    print('P673: %d passed, %d failed, of %d' % (sum(results), len(results)-sum(results), len(results)))
    return 0 if all(results) else 1


if __name__ == '__main__':
    raise SystemExit(main())
