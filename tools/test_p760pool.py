#!/usr/bin/env python3
"""Patch 760: grade p760pool.cfg -- board lines sized from a shared pool.

python tools/test_p760pool.py <rig>/ftesurf [--control]

FULL: the same run (over 8,192 samples) as lines 1, 9 and 64 keeps every sample in
each (`scores lines`' "pts", any build prints it): before this patch lines 9..64 held
8,192 and halved it.  FILL (pool lines from `lines native`): no two regions overlap
or reach into the replay's or the live run's fixed ones, every base is a whole chunk
group, no line holds more than its region, and at least 17 copies of the long run
are whole.  CLEAR: the pool is whole again.  Exit 2 is CANNOT MEASURE.
"""
import argparse
import pathlib
import re
import sys

LN_CAP = 65536
POOL = 8 * LN_CAP + (1253376 - 11 * LN_CAP)   # slots 1..8's old place and past the live run
FIXED = [(0, LN_CAP), (9 * LN_CAP, 11 * LN_CAP)]
CANNOT = 'CANNOT MEASURE: '


def sections(text):
    out, name = {}, None
    for line in text.splitlines():
        line = re.sub(r'^\d{4}-\d\d-\d\d \d\d:\d\d:\d\d ', '', line)
        m = re.search(r'==== (.+?) ====', line)
        if m:
            name = m.group(1)
            out.setdefault(name, [])
        elif name:
            out[name].append(line)
    return out


def samples(path):
    """The run's own samples: a line starts at the clock's zero, not the pad before."""
    n, body = 0, False
    for line in open(path, encoding='utf-8', errors='replace'):
        if line.startswith('begin'):
            body = True
        elif body and line[:1] in '-0123456789' and float(line.split()[0]) >= 0:
            n += 1
    return n


def pts(body):
    return {int(m.group(1)): int(m.group(2)) for m in
            (re.search(r'line (\d+) .* (\d+) pts \(', l) for l in body) if m}


def pool(body):
    head = next((re.search(r'lines: pool (\d+) samples free in (\d+) regions', l) for l in body
                 if 'lines: pool' in l), None)
    rows = [tuple(int(float(x)) for x in m.groups()) for m in
            (re.search(r'lnpool (\S+) base (\S+) cap (\S+) n (\S+) step (\S+)', l) for l in body) if m]
    return (head and (int(head.group(1)), int(head.group(2)))), rows


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('rig', type=pathlib.Path)
    ap.add_argument('--control', action='store_true')
    a = ap.parse_args()
    s = sections((a.rig / 'logs/runlines_smoke.log').read_text(errors='replace'))
    fails, notes = [], []
    kit, long = samples(a.rig / 'data/test/kit.rec'), samples(a.rig / 'data/test/long.rec')
    print('runs: kit %d samples, long %d' % (kit, long))
    if kit <= 8192:
        notes.append(CANNOT + 'the kit run fits the old 8,192 anyway')
    # Parsing guard: a %g print rounds 1,012,736 to 1.01274e+06 and reads as overlaps.
    if any('e+' in l for l in s.get('FILL', []) if 'lnpool' in l or 'lines: pool' in l):
        notes.append(CANNOT + 'the pool printed rounded numbers (an old %g print)')
    full = pts(s.get('FULL', []))
    print('FULL pts', full)
    for line in (1, 9, 64):
        if full.get(line) != kit:
            fails.append('FULL: line %d holds %s of %d samples' % (line, full.get(line), kit))
    if not a.control:
        head, rows = pool(s.get('FILL', []))
        fill = pts(s.get('FILL', []))
        print('FILL pool', head, '%d regions listed' % len(rows))
        spans = sorted((b, b + c, sl, n) for sl, b, c, n, st in rows if sl not in (0, 9, 10) and c > 0)
        for (a0, a1, s0, n0), (b0, b1, s1, n1) in zip(spans, spans[1:]):
            if b0 < a1:
                fails.append('FILL: slots %d and %d overlap (%d..%d, %d..%d)' % (s0, s1, a0, a1, b0, b1))
        for b0, b1, sl, n in spans:
            if b0 % 512:
                fails.append('FILL: slot %d starts at %d, not a chunk group' % (sl, b0))
            if n > b1 - b0:
                fails.append('FILL: slot %d holds %d in %d' % (sl, n, b1 - b0))
            for f0, f1 in FIXED:
                if b0 < f1 and f0 < b1:
                    fails.append('FILL: slot %d reaches into %d..%d' % (sl, f0, f1))
        whole = sum(1 for k, v in fill.items() if v == long)
        print('FILL long runs whole %d; points by line %s' % (whole, sorted(fill.items())))
        if whole < 17:
            fails.append('FILL: %d copies of the long run whole, want 17' % whole)
        if sum(b1 - b0 for b0, b1, sl, n in spans) + (head[0] if head else 0) != POOL:
            fails.append('FILL: regions %d + free %s is not the pool %d'
                         % (sum(b1 - b0 for b0, b1, sl, n in spans), head and head[0], POOL))
        head, rows = pool(s.get('CLEAR', []))
        print('CLEAR pool', head)
        if not head or head[0] != POOL:
            fails.append('CLEAR: %s free, the pool is %d' % (head and head[0], POOL))
    for n in notes:
        print(n)
    for f in fails:
        print('FAIL', f)
    if a.control:
        print('CONTROL: %d failures (a build without the patch must fail)' % len(fails))
        return 0 if fails else 1
    if fails:
        print('FAILED')
        return 1
    if any(n.startswith(CANNOT) for n in notes):
        return 2
    print('PASS')
    return 0


if __name__ == '__main__':
    sys.exit(main())
