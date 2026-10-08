#!/usr/bin/env python3
"""Grade private winning-trace provenance. Never grades physical ramp exits."""
import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import re

from offramp_buffer import compare as compare_buffer, grade as grade_buffer, parse as parse_buffer, require

CHECKS = ('leaf-competition', 'legacy-equal-fraction-replaces', 'source-equal-fraction-keeps-first',
          'triangle-witness', 'losing-nested-model', 'winning-nested-model',
          'unstamped-nested-result', 'nohit-clears-witness', 'solid-abstains',
          'different-output-address', 'later-probe-preserves-copy',
          'losing-physent-preserves-winner', 'portal-physent-abstains', 'winning-physent-replaces-winner',
          'unstamped-physent-abstains', 'disabled-read-abstains')


def parse(text):
    rows = {'CHECK': [], 'SELFTEST': [], 'CONTACT': []}
    order = []
    for line in text.splitlines():
        pos = line.find('OFFRAMPORIGIN_')
        if pos < 0:
            continue
        words = line[pos:].split()
        tag = words[0].removeprefix('OFFRAMPORIGIN_')
        require(tag in rows, 'unknown origin trace')
        require(len(words) == {'CHECK': 4, 'SELFTEST': 3, 'CONTACT': 11}[tag], 'malformed origin trace')
        rows[tag].append(words[1:])
        order.append(tag)
    return rows, order


def integers(words):
    try:
        vals = [float(w) for w in words]
    except ValueError as e:
        raise AssertionError('nonnumeric origin trace') from e
    require(all(math.isfinite(v) and v.is_integer() for v in vals), 'nonfinite/noninteger origin trace')
    return [int(v) for v in vals]


def category(row, contact, mapname):
    _, _, route, kind, _, _, depth, _, entnum, model = row
    if route == 2:
        return 'synthetic-recovery-plane'
    if route == 3:
        return 'portal-unsupported'
    if any(contact[i] for i in (21, 22, 23)):
        return 'recovery-or-solid-unsupported'
    if not kind:
        return 'unwitnessed'
    if entnum:
        return 'entity-unsupported'
    if depth:
        return 'embedded-model-unsupported'
    if model != f'maps/{mapname}.bsp':
        return 'model-unsupported'
    return {1: 'world-brush-origin', 2: 'world-triangle-unresolved', 3: 'world-patch-unsupported'}[kind]


def grade(text, mapname):
    require(re.fullmatch(r'[A-Za-z0-9_-]+', mapname) is not None, 'unsafe map name')
    base = grade_buffer(text)
    buffer, _ = parse_buffer(text)
    contacts = buffer['CONTACT']
    rows, order = parse(text)
    expected_checks = [[str(i), name, '1'] for i, name in enumerate(CHECKS, 1)]
    require(rows['CHECK'] == expected_checks, 'missing/failed/reordered authored origin check')
    require(rows['SELFTEST'] == [[str(len(CHECKS)), '0']], 'missing/failed/duplicate origin selftest')
    require(order == ['CHECK'] * len(CHECKS) + ['SELFTEST'] + ['CONTACT'] * len(contacts),
            'missing/duplicate/unordered origin rows')
    origins = []
    for words, contact in zip(rows['CONTACT'], contacts):
        nums = integers(words[:9])
        ordinal, tick, route, kind, leaf, rootleaf, depth, contents, entnum = nums
        model = words[9]
        require((ordinal, tick, entnum) == (int(contact[0]), int(contact[1]), int(contact[3])),
                'origin not bound to accepted contact')
        require(route in range(4) and kind in range(4) and 0 <= depth <= 64 and
                0 <= contents <= 0xffffffff, 'invalid origin state')
        require(re.fullmatch(r'[A-Za-z0-9_./*:+-]+', model) is not None, 'unsafe origin model')
        if kind:
            require(0 <= leaf < 2**31 and 0 <= rootleaf < 2**31 and contents > 0 and model != '-',
                    'incomplete witnessed origin')
            require(depth != 0 or leaf == rootleaf, 'inconsistent direct leaf')
        else:
            require((leaf, rootleaf, depth, contents, model) == (-1, -1, 0, 0, '-'),
                    'unknown origin promoted stale fields')
        require(route != 3 or kind == 0, 'portal promoted a collider witness')
        row = nums + [model]
        row.append(category(row, contact, mapname))
        origins.append(row)
    require(any(r[3] for r in origins), 'winning provenance did not ACT')
    by_ordinal = {r[0]: r for r in origins}
    for loss in base['losses']:
        origin = by_ordinal[loss['previous_trace']['ordinal']]
        loss['previous_trace']['origin'] = dict(zip(
            ('contact_ordinal', 'tick_ordinal', 'route', 'kind', 'runtime_leaf', 'runtime_root_leaf',
             'embedded_depth', 'contents', 'physent_index', 'model', 'category'), origin))
    base.update(origin_gates='PASS', origin_sha256=hashlib.sha256(
                    json.dumps(origins, separators=(',', ':')).encode()).hexdigest(),
                origin_categories=dict(Counter(r[-1] for r in origins)),
                origin_routes=dict(Counter(r[2] for r in origins)), authored_origin_checks=len(CHECKS),
                winning_leaf_geometry_acceptance='NOT_TESTED',
                cached_recovery_portal_runtime_acceptance='NOT_TESTED')
    return base


def compare(clean, off, on, repeat, mapname):
    compare_buffer(clean, off, on, repeat)
    require(not parse(clean)[1] and not parse(off)[1], 'disabled/clean origin capture was not quiet')
    result = grade(on, mapname)
    require(result == grade(repeat, mapname), 'repeated winning origin differs')
    result.update(clean_off_on_summary_parity='PASS', repeat_origin_equality='PASS')
    return result


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--arms', type=Path, required=True)
    ap.add_argument('--output', type=Path, required=True)
    a = ap.parse_args()
    arms = json.loads(a.arms.read_text())
    require(set(arms) == {'clean', 'off', 'on', 'repeat'}, 'missing arms')
    identities = [(x['recording_sha256'], x['map'], x['map_sha256'], x['hl2_plugin_sha256'], x['progs'])
                  for x in arms.values()]
    require(all(x == identities[0] for x in identities), 'immutable input provenance differs')
    require(all(x['exit_code'] == 0 for x in arms.values()), 'server arm failed')
    require(arms['clean']['server_sha256'] != arms['on']['server_sha256'] and
            len({arms[n]['server_sha256'] for n in ('off', 'on', 'repeat')}) == 1, 'invalid server arms')
    result = compare(*(Path(arms[n]['log']).read_text(errors='replace')
                       for n in ('clean', 'off', 'on', 'repeat')), arms['on']['map'])
    result['arms'] = arms
    a.output.write_text(json.dumps(result, indent=2) + '\n')
    print('Winning origin gates:', result['origin_gates'])
    print('Ticks/contacts/airborne losses:', result['ticks'], result['contacts'], len(result['losses']))
    print('Origin categories:', result['origin_categories'])
    print('Winning-leaf geometry, physical exits and cached/recovery/portal runtime gates: NOT_TESTED')


if __name__ == '__main__':
    main()
