#!/usr/bin/env python3
"""P1548: the shipped colour index is what the hl2 plugin's binary search needs (mat_vmt.c VMT_IndexColour).

    python tools/test_matcolours.py [ftesurf/data/matcolours.txt]

Sorted by path in byte order with no duplicates, one '<path> <RRGGBB> <flags> [<RRGGBB>]' per line,
lowercase '/' paths with no materials/ prefix or extension, LF only.
"""
import re
import sys
from pathlib import Path

LINE = re.compile(r'^([a-z0-9_./\-+!$&()\[\]{}~@,;=\']+) ([0-9a-f]{6}) ([tadwusrex]+|-)( [0-9a-f]{6})?$')


def main():
    path = Path(sys.argv[1] if len(sys.argv) > 1 else 'ftesurf/data/matcolours.txt')
    raw = path.read_bytes()
    assert b'\r' not in raw, 'CR in the index (the repository stores LF)'
    keys, bad = [], []
    for n, line in enumerate(raw.decode('ascii').split('\n'), 1):
        if not line or line.startswith('//'):
            continue
        m = LINE.match(line)
        if not m or m.group(1).startswith('materials/') or m.group(1).endswith(('.vmt', '.vtf')) or '//' in m.group(1):
            bad.append((n, line))
            continue
        keys.append(m.group(1))
    assert not bad, f'{len(bad)} malformed lines, first {bad[:3]}'
    enc = [k.encode() for k in keys]
    assert enc == sorted(enc), 'not sorted in byte order: the plugin binary-searches it'
    assert len(set(keys)) == len(keys), 'duplicate paths'
    assert len(keys) > 10000, f'only {len(keys)} entries'
    print(f'ok: {len(keys)} entries, {len(raw) // 1024} KB')


if __name__ == '__main__':
    main()
