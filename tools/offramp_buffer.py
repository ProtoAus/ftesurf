#!/usr/bin/env python3
"""Strict buffered replay controls; raw-contact loss is NOT geometric-exit proof."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import re

WIDTHS = {'BEGIN': 2, 'TICK': 16, 'CONTACT': 24, 'END': 3, 'COMPLETE': 0}


def require(ok, why):
    if not ok:
        raise AssertionError(why)


def parse(text):
    rows = {tag: [] for tag in WIDTHS}
    order = []
    for line in text.splitlines():
        pos = line.find('OFFRAMPBUF_')
        if pos < 0:
            continue
        words = line[pos:].split()
        tag = words[0].removeprefix('OFFRAMPBUF_')
        require(tag in WIDTHS, 'unknown buffer trace')
        require(len(words) == WIDTHS[tag] + 1, f'malformed {tag}')
        try:
            row = list(map(float, words[1:]))
        except ValueError as e:
            raise AssertionError('nonnumeric buffer trace') from e
        require(all(math.isfinite(x) for x in row), 'nonfinite buffer trace')
        rows[tag].append(row)
        order.append(tag)
    return rows, order


def clean_runtime(text):
    require(not any(s in text for s in ('Unknown command', 'QC VM error', 'Cannot call',
                                       'stack overflow', 'pm_recsim: cannot', 'DIFFERENT MAP')),
            'runtime/map failure')
    require('EXACT REPLAY' in text and 'seed      ' in text, 'incomplete exact replay state')
    require('OFFRAMPBUF_COMPLETE' in text, 'missing acted completion')
    arm = re.findall(r'ARM 4\s+exact: (\d+) of (\d+) packets reproduce', text)
    require(len(arm) == 1 and int(arm[0][1]) > 10, 'exact replay did not ACT')
    require(arm[0][0] == arm[0][1], 'file packet body did not reproduce exactly')
    require(re.search(r'map pin\s+file ([0-9a-f]+)\s+world \1\s+--[ \t]*(?:\^[0-9])*MATCH\b', text) is not None,
            'missing matching map pin')


def summary(text):
    clean_runtime(text)
    # Stable pm_recsim body/clock/world control outputs, not startup timestamps
    # or the optional diagnostic dump. These are not a cryptographic mover hash.
    pattern = r'(ARM [1-4].*|velocity error.*|bands:.*|physents:.*|portals:.*|map pin.*|v9 state.*|body\s+\d+.*)'
    return [re.sub(r'\^[0-9]', '', m.group(0)).rstrip()
            for m in re.finditer(pattern, text)]


def grade(text):
    clean_runtime(text)
    rows, order = parse(text)
    ts, cs = rows['TICK'], rows['CONTACT']
    require(len(rows['BEGIN']) == len(rows['END']) == len(rows['COMPLETE']) == 1,
            'missing/duplicate buffer envelope')
    require(order == ['BEGIN'] + ['TICK'] * len(ts) + ['CONTACT'] * len(cs) + ['END', 'COMPLETE'],
            'buffer trace out of order')
    version, cap = rows['BEGIN'][0]
    require(version == 1 and cap.is_integer() and cap > 0, 'unsupported buffer/cap')
    require(rows['END'][0] == [len(ts), len(cs), 0], 'missing rows or dropped buffer data')
    require(10 < len(ts) <= cap and 0 < len(cs) <= cap, 'buffered trajectory did not ACT')
    require([r[0] for r in ts] == list(range(len(ts))), 'tick ordinal gap/duplicate')
    require([r[0] for r in cs] == list(range(len(cs))), 'contact ordinal gap/duplicate')
    require(all(all(r[i].is_integer() and r[i] >= 0 for i in (1, 2, 3)) and
                r[4] > 0 and r[5] in (0, 1) and r[6] in (0, 1) for r in ts), 'invalid tick state')
    require(all(b[1] >= a[1] and b[2] >= a[2] and b[3] == a[3] + 1 and b[4] == a[4]
                for a, b in zip(ts, ts[1:])), 'unsupported discontinuous or unordered native clock')
    require(all(r[1].is_integer() and 0 <= r[1] < len(ts) and r[2].is_integer() and 0 <= r[2] < 64 and
                r[3].is_integer() and r[3] >= 0 and 0 <= r[4] < 1 and
                all(r[i] in (0, 1) for i in (21, 22, 23)) and
                all(r[15+i] <= r[18+i] for i in range(3)) for r in cs), 'invalid contact state')
    require(all(a[1] <= b[1] for a, b in zip(cs, cs[1:])), 'unordered contacts')
    require(all(.0999 <= abs(r[8]) <= .7001 and abs(math.sqrt(sum(x*x for x in r[6:9])) - 1) < .002
                for r in cs), 'invalid accepted ramp plane')
    by_tick = {}
    for r in cs:
        by_tick.setdefault(int(r[1]), []).append(r)
    for t in ts:
        hits = by_tick.get(int(t[0]), [])
        require(bool(hits) == bool(t[5]), 'raw contact disagrees with accepted ramp traces')
        if hits:
            require(t[13:16] == hits[-1][6:9], 'raw normal differs from last accepted ramp plane')
    losses = []
    for a, b in zip(ts, ts[1:]):
        if a[5] != 1 or b[5] != 0 or b[6] != 0:
            continue
        j = int(b[0])
        end = next((r for r in ts[j:] if r[5] or r[6]), None)
        last = by_tick[int(a[0])][-1]
        losses.append({'loss_ordinal': j, 'native_move_tick': int(b[3]),
                       'loss_position': b[7:10], 'previous_position': a[7:10],
                       'gap_ticks': None if end is None else int(end[0]) - j,
                       'gap_seconds': None if end is None else (end[0] - j) * b[4],
                       'next_state': 'not_observed' if end is None else ('ground' if end[6] else 'ramp'),
                       'previous_trace': {'ordinal': int(last[0]), 'physent_index': int(last[3]),
                                          'fraction': last[4], 'plane_dist': last[5], 'normal': last[6:9],
                                          'sweep_start': last[9:12], 'sweep_end': last[12:15],
                                          'hull_mins': last[15:18], 'hull_maxs': last[18:21],
                                          'recovery_plane': bool(last[21])}})
    require(losses, 'airborne contact loss did not ACT')
    digest = hashlib.sha256(json.dumps([ts, cs], separators=(',', ':')).encode()).hexdigest()
    return {'structural_gates': 'PASS', 'fix_acceptance': 'NOT_TESTED',
            'physical_exit_acceptance': 'NOT_TESTED', 'live_stage_acceptance': 'NOT_TESTED',
            'ticks': len(ts), 'contacts': len(cs), 'trace_sha256': digest,
            'losses': losses}


def compare(clean, off, on, repeat):
    reference = summary(clean)
    require(reference and all(summary(t) == reference for t in (off, on, repeat)),
            'clean/OFF/ON replay summaries differ')
    for t in (clean, off):
        rows, order = parse(t)
        require(order == ['COMPLETE'] and not rows['TICK'] and not rows['CONTACT'],
                'disabled/clean capture was not quiet')
    report = grade(on)
    again = grade(repeat)
    require(report == again, 'repeated immutable-input capture differs')
    report['clean_off_on_summary_parity'] = 'PASS'
    report['repeat_trace_equality'] = 'PASS'
    return report


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('capture', type=Path)
    ap.add_argument('--output', type=Path)
    a = ap.parse_args()
    result = grade(a.capture.read_text(errors='replace'))
    text = json.dumps(result, indent=2) + '\n'
    if a.output:
        a.output.write_text(text)
    print(text, end='')


if __name__ == '__main__':
    main()
