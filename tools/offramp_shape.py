#!/usr/bin/env python3
"""Validate copied winning-brush geometry; numeric halfspace diagnostics ONLY.

Payload IDs deduplicate copied geometry, NOT collider identity. No Source lump
index mapping, physical exit, marker policy, tolerance/debounce or replay gate.
"""
import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path

from offramp_buffer import parse as parse_buffer, require
from offramp_geometry import gap
from offramp_origin import compare as compare_origin, grade as grade_origin, integers, parse as parse_origin

CAP, DICT_CAP = 64, 32768
CHECKS = ('whole-brush-copy', 'accepted-plane-membership', 'source-mutation-cannot-change-copy',
          'later-probe-preserves-geometry', 'losing-nested-shape', 'winning-nested-local-shape',
          'triangle-clears-brush-data', 'whole-shape-cap-abstention', 'null-brush-clears-shape',
          'invalid-side-count-abstains', 'losing-physent-shape', 'translated-instance-recorded',
          'capsule-metadata-recorded', 'hybrid-callback-not-direct-bih')
WIDTHS = {'CHECK': 3, 'SELFTEST': 2, 'BEGIN': 3, 'SHAPE': 9, 'PLANE': 6, 'CONTACT': 16, 'END': 4}


def numbers(words):
    try:
        values = [float(w) for w in words]
    except ValueError as e:
        raise AssertionError('nonnumeric shape data') from e
    require(all(math.isfinite(v) for v in values), 'nonfinite shape data')
    return values


def parse(text):
    rows = []
    for line in text.splitlines():
        pos = line.find('OFFRAMPGEOM_')
        if pos < 0:
            continue
        tokens = line[pos:].split()
        tag = tokens[0].removeprefix('OFFRAMPGEOM_')
        require(tag in WIDTHS and len(tokens)-1 == WIDTHS[tag], 'unknown/malformed geometry row')
        rows.append((tag, tokens[1:]))
    return rows


def decode(text, contacts, origins):
    rows = parse(text)
    head = [('CHECK', [str(i), name, '1']) for i, name in enumerate(CHECKS, 1)]
    head += [('SELFTEST', [str(len(CHECKS)), '0']), ('BEGIN', ['2', str(CAP), str(DICT_CAP)])]
    require(rows[:len(head)] == head, 'missing/failed/reordered geometry setup/header')
    pos = len(head)
    payloads, bound, canonical = {}, [], []
    for contact, origin in zip(contacts, origins):
        require(pos < len(rows), 'missing geometry contact')
        new_id = None
        if rows[pos][0] == 'SHAPE':
            words = rows[pos][1]
            vals = numbers(words)
            pid, status, sides = integers(words[:3])
            require(pid == len(payloads)+1 and pid <= DICT_CAP, 'duplicate/nonsequential payload ID')
            require(status in range(4) and 0 <= sides < 2**31, 'invalid snapshot status/count')
            mins, maxs = vals[3:6], vals[6:9]
            require(all(a <= b for a, b in zip(mins, maxs)), 'reversed brush bounds')
            if status == 0:
                require(sides == 0 and mins == maxs == [0]*3, 'missing shape promoted stale data')
            elif status == 1:
                require(4 <= sides <= CAP, 'incomplete/over-cap whole shape')
            elif status == 2:
                require(sides > CAP, 'cap abstention without over-cap source')
            planes = []
            canonical.append(('SHAPE', vals))
            pos += 1
            for index in range(sides if status == 1 else 0):
                require(pos < len(rows) and rows[pos][0] == 'PLANE', 'missing shape plane')
                words = rows[pos][1]
                require(integers(words[:2]) == [pid, index], 'duplicate/unordered/wrong-payload plane')
                vals = numbers(words)
                plane = vals[2:]
                require(abs(math.sqrt(sum(v*v for v in plane[:3]))-1) < .002, 'non-unit brush plane')
                planes.append(plane)
                canonical.append(('PLANE', vals))
                pos += 1
            payloads[pid] = {'payload_id': pid, 'status': status, 'source_side_count': sides,
                             'model_local_mins': mins, 'model_local_maxs': maxs, 'planes': planes}
            new_id = pid
        require(pos < len(rows) and rows[pos][0] == 'CONTACT', 'missing/unused payload or extra plane')
        words = rows[pos][1]
        vals = numbers(words)
        ordinal, tick, pid, leaf, rootleaf, depth, contents = integers(words[:7])
        capsule, native_bih = integers(words[14:])
        require((ordinal, tick) == (int(contact[0]), int(contact[1])), 'shape not bound to accepted contact')
        require(pid in payloads and (new_id is None or pid == new_id), 'undefined/unused shape payload')
        require((leaf, rootleaf, depth, contents) == tuple(origin[4:8]), 'shape not bound to winning origin')
        require(capsule in (0, 1) and native_bih in (0, 1), 'invalid hull/native flags')
        if origin[3] != 1:
            require(payloads[pid]['status'] == 0, 'non-brush origin promoted stale brush shape')
        if origin[3] == 0:
            require(native_bih == 0, 'unknown origin promoted native ownership')
        bound.append({'contact_ordinal': ordinal, 'tick_ordinal': tick, 'payload_id': pid,
                      'instance_origin': vals[7:10], 'instance_angles': vals[10:13],
                      'raw_instance_scale': vals[13], 'capsule': capsule, 'direct_bih_callback': native_bih})
        canonical.append(('CONTACT', vals))
        pos += 1
    statuses = Counter(payloads[r['payload_id']]['status'] for r in bound)
    expected = [len(bound), statuses[1], statuses[2], len(payloads)]
    require(pos == len(rows)-1 and rows[pos][0] == 'END' and integers(rows[pos][1]) == expected,
            'missing/duplicate/incorrect geometry footer')
    return payloads, bound, canonical


def category(origin, contact, row, shape, mapname):
    # Keep the origin reader's recovery/solid/embedded/entity/triangle abstention.
    from offramp_origin import category as origin_category
    reason = origin_category(origin, contact, mapname)
    if reason != 'world-brush-origin':
        return reason, []
    if shape['status'] != 1:
        return {0: 'brush-snapshot-missing', 2: 'whole-shape-cap-abstention', 3: 'invalid-source-shape'}[shape['status']], []
    if not row['direct_bih_callback']:
        return 'native-callback-unsupported', []
    if any(row['instance_origin']) or any(row['instance_angles']):
        return 'transformed-instance-unsupported', []
    if row['raw_instance_scale'] not in (0, 1):
        return 'instance-scale-unsupported', []
    if row['capsule']:
        return 'capsule-hull-unsupported', []
    # Exact serialized float equality: NO enlarged plane/collision tolerance.
    normal, distance = contact[6:9], contact[5]
    matches = [i for i, p in enumerate(shape['planes']) if p[:3] == normal and p[3] == distance]
    return ('copied-world-brush-plane-bound' if matches else 'accepted-plane-unmatched'), matches


def diagnostics(loss, shape, matches):
    trace = loss['previous_trace']
    points = {'accepted_sweep_point': [a+trace['fraction']*(b-a) for a, b in zip(trace['sweep_start'], trace['sweep_end'])],
              'previous_tick_end': loss['previous_position'], 'raw_loss_tick_end': loss['loss_position']}
    result = {'basis': 'copied runtime side halfspaces expanded by PREVIOUS CONTACT AABB; loss-tick hull not captured; numeric only',
              'hull_mins': trace['hull_mins'], 'hull_maxs': trace['hull_maxs'],
              'matching_runtime_side_indices': matches, 'points': {}}
    for name, point in points.items():
        values = [gap(p, point, trace['hull_mins'], trace['hull_maxs']) for p in shape['planes']]
        result['points'][name] = {'position': point, 'side_gaps': values, 'max_side_gap': max(values),
                                  'max_nonface_gap': max((v for i, v in enumerate(values) if i not in matches), default=None),
                                  'face_gaps': [values[i] for i in matches]}
    return result


def grade(text, mapname):
    base = grade_origin(text, mapname)
    buffer, _ = parse_buffer(text)
    contacts = buffer['CONTACT']
    raw, _ = parse_origin(text)
    origins = [integers(r[:9])+[r[9]] for r in raw['CONTACT']]
    payloads, bound, canonical = decode(text, contacts, origins)
    counts, static = Counter(), {}
    for origin, contact, row in zip(origins, contacts, bound):
        shape = payloads[row['payload_id']]
        row['status'], row['matching_runtime_side_indices'] = category(origin, contact, row, shape, mapname)
        counts[row['status']] += 1
        if (origin[3] == 1 and origin[8] == 0 and origin[6] == 0 and
                origin[9] == f'maps/{mapname}.bsp' and row['direct_bih_callback'] and
                not any(row['instance_origin']) and not any(row['instance_angles']) and
                row['raw_instance_scale'] in (0, 1)):
            key = (origin[9], origin[4])
            signature = (origin[7], json.dumps({k: v for k, v in shape.items() if k != 'payload_id'}, sort_keys=True))
            require(key not in static or static[key] == signature, 'one static runtime leaf changed geometry')
            static[key] = signature
    by_contact = {r['contact_ordinal']: r for r in bound}
    for loss in base['losses']:
        row = by_contact[loss['previous_trace']['ordinal']]
        shape = payloads[row['payload_id']]
        loss['winning_brush_snapshot'] = {'contact': row, 'copied_payload': shape}
        if row['status'] == 'copied-world-brush-plane-bound':
            loss['winning_brush_snapshot']['numeric_halfspaces'] = diagnostics(loss, shape, row['matching_runtime_side_indices'])
    base.update(structural_shape_gates='PASS',
                winning_brush_snapshot_gates='PASS' if counts['copied-world-brush-plane-bound'] else 'ABSTAIN',
                shape_sha256=hashlib.sha256(
                    json.dumps(canonical, separators=(',', ':')).encode()).hexdigest(),
                shape_contact_statuses=dict(counts), shape_payload_count=len(payloads),
                shape_side_cap=CAP, authored_shape_checks=len(CHECKS),
                shape_payloads=list(payloads.values()),
                winning_brush_movement_geometry_acceptance='NOT_TESTED')
    return base


def compare(clean, off, on, repeat, mapname):
    compare_origin(clean, off, on, repeat, mapname)
    require(not parse(clean) and not parse(off), 'clean/OFF shape output was not quiet')
    result = grade(on, mapname)
    require(result == grade(repeat, mapname), 'repeated winning brush snapshot differs')
    result.update(clean_off_on_summary_parity='PASS', repeat_shape_equality='PASS')
    return result


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--arms', type=Path, required=True)
    ap.add_argument('--output', type=Path, required=True)
    a = ap.parse_args()
    arms = json.loads(a.arms.read_text())
    require(set(arms) == {'clean', 'off', 'on', 'repeat'}, 'missing arms')
    identities = [(r['recording_sha256'], r['map'], r['map_sha256'], r['hl2_plugin_sha256'], r['progs']) for r in arms.values()]
    require(all(v == identities[0] for v in identities), 'immutable shape inputs differ')
    require(all(r['exit_code'] == 0 for r in arms.values()), 'server arm failed')
    require(arms['clean']['server_sha256'] != arms['on']['server_sha256'] and
            len({arms[n]['server_sha256'] for n in ('off', 'on', 'repeat')}) == 1, 'invalid server arms')
    result = compare(*(Path(arms[n]['log']).read_text(errors='replace') for n in ('clean', 'off', 'on', 'repeat')), arms['on']['map'])
    result['arms'] = arms
    a.output.write_text(json.dumps(result, indent=2)+'\n')
    print('Whole winning brush snapshot gates:', result['winning_brush_snapshot_gates'])
    print('Ticks/contacts/raw airborne losses:', result['ticks'], result['contacts'], len(result['losses']))
    print('Copied payloads/contact statuses:', result['shape_payload_count'], result['shape_contact_statuses'])
    print('Authored movement geometry, physical exit/classifier/live mark acceptance: NOT_TESTED')


if __name__ == '__main__':
    main()
