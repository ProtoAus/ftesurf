#!/usr/bin/env python3
"""Validate actual accepted-contact and tick-end hull/posture snapshots.

Separate AABBs for each sampled point; NEVER reuse a previous contact hull at a
later tick. Copied brush halfspaces are numeric diagnostics, NOT physical exits,
movement acceptance, posture-policy validation or marker/debounce decisions.
"""
import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path

from offramp_buffer import parse as parse_buffer, require
from offramp_geometry import gap
from offramp_origin import integers
from offramp_shape import compare as compare_shape, grade as grade_shape

CAP = 32768
CHECKS = ('actual-nondefault-standing-hull', 'actual-crouched-hull-and-posture',
          'transition-flag-does-not-guess-small-hull', 'capsule-and-movement-type-copied',
          'mutable-source-cannot-change-snapshot', 'contact-and-tick-snapshots-can-differ',
          'raw-height-fallback-is-not-observed-height')
WIDTHS = {'CHECK': 3, 'SELFTEST': 2, 'BEGIN': 2, 'TICK': 15, 'CONTACT': 16, 'END': 2}


def parse(text):
    rows = []
    for line in text.splitlines():
        pos = line.find('OFFRAMPHULL_')
        if pos < 0:
            continue
        tokens = line[pos:].split()
        tag = tokens[0].removeprefix('OFFRAMPHULL_')
        require(tag in WIDTHS and len(tokens)-1 == WIDTHS[tag], 'unknown/malformed hull row')
        rows.append((tag, tokens[1:]))
    return rows


def state(words):
    try:
        vals = [float(w) for w in words]
    except ValueError as e:
        raise AssertionError('nonnumeric hull data') from e
    require(all(math.isfinite(v) and abs(v) <= 3.4028235e38 for v in vals), 'nonfinite/out-of-float hull data')
    require(all(a < b for a, b in zip(vals[:3], vals[3:6])), 'reversed/degenerate hull bounds')
    capsule, pmtype, ducked, ducking = integers(words[6:10])
    buttons = integers(words[11:12])[0]
    require(capsule in (0, 1) and ducked in (0, 1) and ducking in (0, 1), 'invalid hull/posture flags')
    require(0 <= pmtype <= 8, 'invalid movement type')
    require(vals[10] >= 0 and -2**31 <= buttons < 2**31, 'invalid duck timer/buttons')
    return {'mins': vals[:3], 'maxs': vals[3:6], 'capsule': capsule, 'pm_type': pmtype,
            'ducked': ducked, 'ducking': ducking, 'ducktime_ms': vals[10], 'oldbuttons': buttons,
            'raw_standheight': vals[12], 'raw_duckheight': vals[13]}


def decode(text, ticks, contacts, shape_contacts):
    rows = parse(text)
    head = [('CHECK', [str(i), name, '1']) for i, name in enumerate(CHECKS, 1)]
    head += [('SELFTEST', [str(len(CHECKS)), '0']), ('BEGIN', ['1', str(CAP)])]
    require(rows[:len(head)] == head, 'missing/failed/reordered hull setup/header')
    pos = len(head)
    bound_ticks, bound_contacts, canonical = [], [], []
    for tick in ticks:
        require(pos < len(rows) and rows[pos][0] == 'TICK', 'missing/reordered hull tick')
        words = rows[pos][1]
        require(integers(words[:1]) == [int(tick[0])], 'hull not bound to native tick')
        bound_ticks.append(state(words[1:]))
        canonical.append(('TICK', [int(tick[0]), bound_ticks[-1]]))
        pos += 1
    for contact, shape in zip(contacts, shape_contacts):
        require(pos < len(rows) and rows[pos][0] == 'CONTACT', 'missing/reordered hull contact')
        words = rows[pos][1]
        require(integers(words[:2]) == [int(contact[0]), int(contact[1])], 'hull not bound to accepted contact')
        hull = state(words[2:])
        require(hull['mins'] == contact[15:18] and hull['maxs'] == contact[18:21],
                'hull differs from accepted trace bounds')
        require(hull['capsule'] == shape['capsule'], 'hull differs from winning trace capsule metadata')
        bound_contacts.append(hull)
        canonical.append(('CONTACT', [int(contact[0]), int(contact[1]), hull]))
        pos += 1
    require(pos == len(rows)-1 and rows[pos][0] == 'END' and
            integers(rows[pos][1]) == [len(ticks), len(contacts)], 'missing/duplicate/incorrect hull footer')
    return bound_ticks, bound_contacts, canonical


def diagnostics(loss, shape, matches, hulls):
    trace = loss['previous_trace']
    points = {'accepted_sweep_point': [a+trace['fraction']*(b-a) for a, b in zip(trace['sweep_start'], trace['sweep_end'])],
              'previous_tick_end': loss['previous_position'], 'raw_loss_tick_end': loss['loss_position']}
    result = {'basis': 'copied runtime halfspaces expanded separately by EACH POINT actual captured AABB; numeric only',
              'matching_runtime_side_indices': matches, 'points': {}}
    contact = hulls['accepted_sweep_point']
    for name, point in points.items():
        hull = hulls[name]
        values = [gap(p, point, hull['mins'], hull['maxs']) for p in shape['planes']]
        result['points'][name] = {'position': point, 'captured_hull': hull,
                                 'same_bounds_as_previous_contact': (hull['mins'], hull['maxs']) == (contact['mins'], contact['maxs']),
                                 'side_gaps': values, 'max_side_gap': max(values),
                                 'max_nonface_gap': max((v for i, v in enumerate(values) if i not in matches), default=None),
                                 'face_gaps': [values[i] for i in matches]}
    return result


def grade(text, mapname):
    base = grade_shape(text, mapname)
    buffer, _ = parse_buffer(text)
    require(buffer['BEGIN'] == [[1.0, float(CAP)]], 'native buffer/hull capacity mismatch')
    # Shape decoder's contact order is ordinal-bound; losses are not the full
    # contact set. Decode all snapshots again, not a guessed loss-only mapping.
    from offramp_origin import parse as parse_origin
    from offramp_shape import decode as decode_shape
    origins, _ = parse_origin(text)
    origins = [integers(r[:9])+[r[9]] for r in origins['CONTACT']]
    _, shape_contacts, _ = decode_shape(text, buffer['CONTACT'], origins)
    ticks, contacts, canonical = decode(text, buffer['TICK'], buffer['CONTACT'], shape_contacts)
    statuses = Counter()
    for loss in base['losses']:
        ordinal = loss['loss_ordinal']
        hulls = {'accepted_sweep_point': contacts[loss['previous_trace']['ordinal']],
                 'previous_tick_end': ticks[ordinal-1], 'raw_loss_tick_end': ticks[ordinal]}
        loss['actual_hulls'] = hulls
        snapshot = loss['winning_brush_snapshot']
        # Remove the predecessor reader's explicitly previous-hull-only view.
        # It must never be mistaken for this reader's point-specific geometry.
        snapshot.pop('numeric_halfspaces', None)
        status = snapshot['contact']['status']
        if status == 'copied-world-brush-plane-bound':
            if any(h['capsule'] for h in hulls.values()):
                status = 'sample-capsule-hull-unsupported'
            elif any(h['pm_type'] != 0 for h in hulls.values()):
                status = 'sample-movement-type-unsupported'
            else:
                status = 'captured-world-brush-aabb-numeric-only'
                snapshot['numeric_halfspaces'] = diagnostics(
                    loss, snapshot['copied_payload'], snapshot['contact']['matching_runtime_side_indices'], hulls)
        loss['actual_hull_geometry_status'] = status
        statuses[status] += 1
    posture = Counter((h['ducked'], h['ducking']) for h in ticks)
    base.update(hull_capture_gates='PASS', authored_hull_setup_checks=len(CHECKS),
                hull_sha256=hashlib.sha256(json.dumps(canonical, separators=(',', ':'), sort_keys=True).encode()).hexdigest(),
                hull_loss_statuses=dict(statuses), tick_posture_counts={f'ducked={d},ducking={g}': n for (d, g), n in posture.items()},
                authored_movement_trajectory_acceptance='NOT_TESTED')
    return base


def compare(clean, off, on, repeat, mapname):
    compare_shape(clean, off, on, repeat, mapname)
    require(not parse(clean) and not parse(off), 'clean/OFF hull output was not quiet')
    result = grade(on, mapname)
    require(result == grade(repeat, mapname), 'repeated actual hull capture differs')
    result.update(clean_off_on_summary_parity='PASS', repeat_hull_equality='PASS')
    return result


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--arms', type=Path, required=True)
    ap.add_argument('--output', type=Path, required=True)
    a = ap.parse_args()
    arms = json.loads(a.arms.read_text())
    require(set(arms) == {'clean', 'off', 'on', 'repeat'}, 'missing arms')
    identities = [(r['recording_sha256'], r['map'], r['map_sha256'], r['hl2_plugin_sha256'], r['progs']) for r in arms.values()]
    require(all(v == identities[0] for v in identities), 'immutable hull inputs differ')
    require(all(r['exit_code'] == 0 for r in arms.values()), 'server arm failed')
    require(arms['clean']['server_sha256'] != arms['on']['server_sha256'] and
            len({arms[n]['server_sha256'] for n in ('off', 'on', 'repeat')}) == 1, 'invalid server arms')
    result = compare(*(Path(arms[n]['log']).read_text(errors='replace') for n in ('clean', 'off', 'on', 'repeat')), arms['on']['map'])
    result['arms'] = arms
    a.output.write_text(json.dumps(result, indent=2)+'\n')
    print('Actual hull/posture gates:', result['hull_capture_gates'])
    print('Ticks/contacts/raw airborne losses:', result['ticks'], result['contacts'], len(result['losses']))
    print('Hull setup checks:', result['authored_hull_setup_checks'])
    print('Authored trajectories, physical exit/classifier/live mark acceptance: NOT_TESTED')


if __name__ == '__main__':
    main()
