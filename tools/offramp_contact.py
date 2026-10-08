#!/usr/bin/env python3
"""Strict structural grader for private native/live contact diagnostics.

This is NOT a physics verifier, requested-clock oracle, or fix acceptance.
Reports native, sampled, held/event and actual-render stages separately. Native
clock association is packet-anchored; positions remain independent observations.
"""
import argparse
import json
import math
from pathlib import Path
import struct

WIDTHS = {'NATIVE': 13, 'PACKET': 9, 'ANCHOR': 4, 'SAMPLE': 10,
          'BODY': 9, 'EVENT': 8, 'RENDER': 8, 'HELD': 5}
EPS = 0.000002  # decimal printing / QC float32, NOT a timing tolerance


def require(ok, reason):
    if not ok:
        raise AssertionError(reason)


def f32(value):
    try:
        return struct.unpack('<f', struct.pack('<f', value))[0]
    except OverflowError as e:
        raise AssertionError('value outside QC float32 range') from e


def parse(text):
    out = {tag: [] for tag in WIDTHS}
    for line in text.splitlines():
        # Engine log timestamp/prefix is not part of the diagnostic grammar.
        start = line.find('OFFRAMP_')
        if start < 0:
            continue
        parts = line[start:].split()
        tag = parts[0].removeprefix('OFFRAMP_')
        require(tag in WIDTHS, 'unknown trace tag')
        require(len(parts) == WIDTHS[tag] + 1, f'malformed {tag} row')
        try:
            row = list(map(float, parts[1:]))
        except ValueError as e:
            raise AssertionError(f'nonnumeric {tag} row') from e
        require(all(math.isfinite(x) for x in row), f'nonfinite {tag} row')
        out[tag].append(row)
    return out


def unique(rows, indices, label):
    result = {}
    for row in rows:
        key = tuple(row[i] for i in indices)
        require(key not in result, f'duplicate {label} ordinal')
        result[key] = row
    return result


def distance(a, b):
    return math.dist(a, b)


def grade_text(server, client):
    require('RUNLINES COMPLETE' in client, 'missing acted completion')
    require(not any(x in server + client for x in
                    ('Unknown command', 'QC VM error', 'Cannot call', 'stack overflow')),
            'runtime error')
    native = parse(server)
    live = parse(client)
    require(all(not native[t] for t in WIDTHS if t not in ('NATIVE', 'PACKET', 'ANCHOR')) and
            all(not live[t] for t in ('NATIVE', 'PACKET', 'ANCHOR')), 'trace authority crossed sources')
    nr = native['NATIVE']
    samples = live['SAMPLE']
    require(len(nr) > 10 and len(samples) > 10, 'unacted native/live trace')
    nd = unique(nr, (0,), 'native')
    packets = unique(native['PACKET'], (0,), 'packet')
    anchors = unique(native['ANCHOR'], (0,), 'anchor')
    require(packets.keys() == anchors.keys(), 'missing/extra packet clock anchor')
    require(all(a[0] < b[0] for a, b in zip(nr, nr[1:])), 'unordered native ticks')
    require(all(r[0] >= 1 and r[0].is_integer() and r[1] > 0 and
                r[2] in (0, 1) and r[3] in (0, 1) for r in nr), 'invalid native state')
    require(any(r[2] == 1 for r in nr), 'native ramp ride did not ACT')
    require(all(0 < r[12] < .7 and abs(math.sqrt(sum(x*x for x in r[10:13])) - 1) < .002
                for r in nr if r[2]), 'invalid native ramp plane')
    # Only packets that actually advanced mover ticks own a final tick result.
    # Multiple packets can report the same mover tick without moving. Timer and
    # teleport QC can also change origin AFTER movement; do not assert equality
    # to that later origin as if it were a mover receipt.
    correlated = 0
    for key, packet in packets.items():
        anchor = anchors[key]
        require(packet[1].is_integer() and packet[2].is_integer() and anchor[3] > 0,
                'invalid packet clock')
        if (packet[1],) in nd and packet[3] == 2 and packet[4] == 1:
            row = nd[(packet[1],)]
            require(packet[5] == row[2], 'native/packet raw-contact mismatch')
            require(abs(row[1] - anchor[3]) < EPS, 'native/packet tickrate mismatch')
            require(abs(packet[2] - (packet[1] - anchor[1] - anchor[2])) < EPS,
                    'packet counted-clock mismatch')
            correlated += 1
    require(correlated > 10, 'native recording anchors did not ACT')

    sm = unique(samples, (0, 1), 'sample')
    bodies = unique(live['BODY'], (0, 1), 'body')
    require(sm.keys() == bodies.keys(), 'missing/extra sampled body')
    require(len({s[0] for s in samples}) == 1, 'multi-generation arm not supported')
    require([s[1] for s in samples] == list(range(len(samples))), 'sample ordinals are not contiguous')
    require(all(a[2] <= b[2] and a[3] <= b[3] and a[4] < b[4]
                for a, b in zip(samples, samples[1:])), 'unordered sample/command clock')
    held, last = 0, 0.0
    expected_leaves = []
    previous_kind = None
    for s in samples:
        # gen, ordinal, run time, wall time, commandframe, flags, kind,
        # held state, slot, break. Repeated run times MUST retain their ordinal.
        _, ordinal, t, _, _, flags, kind, on, slot, brk = s
        require(s[0].is_integer() and s[0] > 0 and ordinal.is_integer() and s[4].is_integer()
                and flags.is_integer() and 0 <= flags <= 31 and kind in (0, 1, 2)
                and on in (0, 1) and slot.is_integer() and brk in (0, 1), 'invalid sample state')
        raw = bool(int(flags) & 16)
        ground = bool(int(flags) & 1)
        if brk:
            # Line_Point explicitly expires the hold at t - 999, not zero.
            held, last = 0, f32(f32(t) - 999)
        if raw:
            last, held = f32(t), 1
        elif held and f32(t) >= last and f32(f32(t) - last) > f32(.08):
            held = 0
        want = 0 if ground else (2 if held else 1)
        require(kind == want and on == held, 'held-kind differs from raw/clock control')
        require(abs(bodies[(s[0], ordinal)][8] - last) < EPS, 'last-contact timestamp mismatch')
        if not brk and previous_kind == 2 and kind == 1:
            expected_leaves.append(s)
        previous_kind = kind
    require(expected_leaves, 'sampled surf-to-air leave did not ACT')
    events = unique(live['EVENT'], (0, 1, 2), 'event')
    leaves = [e for e in live['EVENT'] if e[2] == 2 and e[3] == 9]
    require(len(leaves) == len(expected_leaves), 'missing/extra surf-to-air leave mark')
    edges = []
    for a, b in zip(nr, nr[1:]):
        if b[0] == a[0] + 1 and a[2] == 1 and b[2] == 0 and b[3] == 0:
            # First recording packet at or after the loss. No guessed .rec
            # time, no requested scrub time and no wall-clock substitution.
            match = next((p for p in native['PACKET'] if p[1] >= b[0] and
                          p[3] == 2 and p[4] == 1), None)
            if match is None:
                continue
            an = anchors[(match[0],)]
            t = (b[0] - an[1] - an[2]) * an[3]
            future = next((r for r in nr if r[0] > b[0] and (r[2] or r[3])), None)
            duration = None if future is None else (future[0] - b[0]) * b[1]
            edges.append({'native_tick': int(b[0]), 'time': t, 'position': b[4:7],
                          'air_gap_seconds': duration, 'normal_before': a[10:13]})
    require(edges, 'native airborne contact loss did not ACT')
    metrics = []
    for s in expected_leaves:
        key = (s[8], s[1], 2.0)
        require(key in events, 'leave ordinal/slot mismatch')
        ev = events[key]
        body = bodies[(s[0], s[1])]
        require(ev[3] == 9 and abs(ev[4] - s[2]) < EPS and distance(ev[5:8], body[2:5]) < .002,
                'leave mark differs from its actual sampled point')
        raw = [r for r in samples if r[1] < s[1] and (int(r[5]) & 16)]
        require(raw, 'leave without a prior raw ride')
        positive = raw[-1]
        rendered = [r for r in live['RENDER'] if r[:3] == [s[8], s[1], 2.0]]
        require(rendered, 'actual leave rendering did not ACT')
        require(all(abs(r[3] - ev[4]) < EPS and distance(r[5:8], ev[5:8]) < .002
                    for r in rendered), 'rendered mark moved from its stored event')
        # Selection for a stage report, NOT a native snapshot resume oracle.
        before = [e for e in edges if e['time'] <= s[2] + EPS]
        require(before, 'sampled leave has no preceding native contact loss')
        edge = before[-1]
        metrics.append({'ordinal': int(s[1]), 'native_loss_tick': edge['native_tick'],
                        'native_loss_time': edge['time'], 'native_air_gap_seconds': edge['air_gap_seconds'],
                        'last_positive_sample_time': positive[2], 'mark_time': ev[4],
                        'observed_hold_seconds': s[2] - positive[2],
                        'sample_clock_step': s[2] - samples[int(s[1]) - 1][2],
                        'native_to_mark_seconds': ev[4] - edge['time'],
                        'native_to_mark_units': distance(edge['position'], ev[5:8]),
                        'sample_to_mark_units': distance(body[2:5], ev[5:8]),
                        'mark_to_render_units': max(distance(r[5:8], ev[5:8]) for r in rendered),
                        'render_observations': len(rendered)})
    require(len(live['HELD']) == 1 and live['HELD'][0][2:] == [1, 0, 0], 'auto-view did not ACT')
    require(abs(live['HELD'][0][0] - live['HELD'][0][1]) < EPS and
            any(abs(m['mark_time'] - live['HELD'][0][0]) < EPS for m in metrics),
            'held view did not select a measured leave')
    return {'structural_gates': 'PASS', 'fix_acceptance': 'NOT_TESTED',
            'native_ticks': len(nr), 'samples': len(samples), 'recording_packet_anchors': correlated,
            'native_airborne_edges': len(edges), 'leaves': metrics}


def grade(rig):
    gd = rig / 'ftesurf' if (rig / 'ftesurf/logs').is_dir() else rig
    return grade_text((gd / 'logs/runlines_server.log').read_text(errors='replace'),
                      (gd / 'logs/runlines_smoke.log').read_text(errors='replace'))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('rig', type=Path)
    ap.add_argument('--output', type=Path)
    a = ap.parse_args()
    result = grade(a.rig)
    text = json.dumps(result, indent=2) + '\n'
    if a.output:
        a.output.write_text(text)
    print(text, end='')


if __name__ == '__main__':
    main()
