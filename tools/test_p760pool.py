#!/usr/bin/env python3
"""Patch 760: grade p760pool.cfg -- board lines sized from a shared pool.

python tools/test_p760pool.py <rig>/ftesurf [--control]

FULL: the same run (over 8,192 samples) as lines 1, 9 and 64 keeps every sample in
each (`scores lines`' "pts", any build prints it): before this patch lines 9..64 held
8,192 and halved it.  FILL (pool and free regions from `lines native`): no two
regions, used or free, overlap or reach into the fixed ones (replay, live run, the
ghost's whole-run PB), every base is a whole chunk group, no line holds more than its
region, and exactly as many copies of the long run are whole as the pool's two ranges
hold after the three short ones.  FREED: lines 5 and 6 off, one free region covers both.  REUSE:
the short run ticked into line 5 again lies inside it.  CLEAR: the pool whole, in its
two ranges.  Exit 2 is CANNOT MEASURE.
"""
import argparse
import pathlib
import re
import sys

LN_CAP = 65536
TOTAL = 1253376
RANGES = [(LN_CAP, 9 * LN_CAP), (11 * LN_CAP, TOTAL - LN_CAP)]   # slots 1..8's place; live run to PB
POOL = sum(b - a for a, b in RANGES)
FIXED = [(0, LN_CAP), (9 * LN_CAP, 11 * LN_CAP), (TOTAL - LN_CAP, TOTAL)]


def align(n):
    return -(-n // 512) * 512
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


def free(body):
    return [(int(m.group(1)), int(m.group(1)) + int(m.group(2))) for m in
            (re.search(r'lnfree (\d+) len (\d+)', l) for l in body) if m]


def layout(name, body, fails):
    """Every region, used or free, apart and inside the arenas, off the fixed ones."""
    head, rows = pool(body)
    used = [(b, b + c, 'slot %d' % sl) for sl, b, c, n, st in rows
            if sl not in (0, 9, 10, 68) and c > 0]
    spans = sorted(used + [(a, b, 'free') for a, b in free(body)])
    for (a0, a1, w0), (b0, b1, w1) in zip(spans, spans[1:]):
        if b0 < a1:
            fails.append('%s: %s and %s overlap (%d..%d, %d..%d)' % (name, w0, w1, a0, a1, b0, b1))
    for a0, a1, w in spans:
        if a0 % 512 or a1 % 512:
            fails.append('%s: %s at %d..%d, not whole chunk groups' % (name, w, a0, a1))
        for f0, f1 in FIXED:
            if a0 < f1 and f0 < a1:
                fails.append('%s: %s reaches into %d..%d' % (name, w, f0, f1))
    if sum(a1 - a0 for a0, a1, w in spans) != POOL:
        fails.append('%s: regions add to %d, the pool is %d' % (name, sum(a1 - a0 for a0, a1, w in spans), POOL))
    return rows


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
        rows = layout('FILL', s.get('FILL', []), fails)
        fill = pts(s.get('FILL', []))
        for sl, b, c, n, st in rows:
            if n > c:
                fails.append('FILL: slot %d holds %d in %d' % (sl, n, c))
        whole = sum(1 for k, v in fill.items() if v == long)
        # A run cannot span the live run's slots, so each range holds its own count
        # (measured: the short runs land in the upper one, 8 + 7, not 991,232 // 58,368).
        short = [b for sl, b, c, n, st in rows if c == align(kit)]
        want = sum((r1 - r0 - align(kit) * sum(1 for b in short if r0 <= b < r1)) // align(long)
                   for r0, r1 in RANGES)
        if len(short) != 3:
            fails.append('FILL: %d regions the short run\'s size, want 3' % len(short))
        print('FILL long runs whole %d (the pool holds %d); points by line %s'
              % (whole, want, sorted(fill.items())))
        if whole != want:
            fails.append('FILL: %d copies of the long run whole, the pool holds %d' % (whole, want))
        old = {sl: (b, b + c) for sl, b, c, n, st in rows}
        layout('FREED', s.get('FREED', []), fails)
        hole = [f for f in free(s.get('FREED', [])) if 5 in old and 6 in old
                and f[0] <= min(old[5][0], old[6][0]) and f[1] >= max(old[5][1], old[6][1])]
        print('FREED slots 5 %s and 6 %s; one free region over both: %s'
              % (old.get(5), old.get(6), hole))
        if not hole:
            fails.append('FREED: lines 5 and 6 off, no one free region covers both')
        rows = layout('REUSE', s.get('REUSE', []), fails)
        new = [(b, b + c) for sl, b, c, n, st in rows if sl == 5]
        print('REUSE slot 5 at %s' % new)
        if not hole or not new or not (hole[0][0] <= new[0][0] and new[0][1] <= hole[0][1]):
            fails.append('REUSE: line 5 again is not inside the freed hole (%s)' % new)
        head, rows = pool(s.get('CLEAR', []))
        print('CLEAR pool', head)
        if not head or head != (POOL, 2):
            fails.append('CLEAR: %s (free, regions); the pool is %d in 2' % (head, POOL))
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
