#!/usr/bin/env python3
"""Counterfactual checks on private visual traces; never modify the source rig."""
import argparse
import contextlib
import io
from pathlib import Path
import shutil
import tempfile

from stitched_visual import grade


def row(gd, column, value):
    p = gd / 'cfg/test/visual_warm1_cursor.txt'
    lines = p.read_text().splitlines()
    parts = lines[2].split()
    assert parts[column] != str(value), 'counterfactual did not ACT'
    parts[column] = str(value)
    lines[2] = ' '.join(parts)
    p.write_text('\n'.join(lines) + '\n')


def lines(gd, change):
    p = gd / 'cfg/test/visual_warm1_cursor.txt'
    before = p.read_text().splitlines()
    after = change(before)
    assert after != before, 'counterfactual did not ACT'
    p.write_text('\n'.join(after) + '\n')


def unit(gd):
    p = gd / 'cfg/test/visual_units.txt'
    assert p.read_text().split() == ['units', '9', '0']
    p.write_text('units 9 1\n')
    p = gd / 'logs/runlines_smoke.log'
    text = p.read_text()
    assert 'VISUAL CHECK raw-break-columns 1' in text
    p.write_text(text.replace('VISUAL CHECK raw-break-columns 1', 'VISUAL CHECK raw-break-columns 0', 1))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--rig', type=Path, required=True)
    a = ap.parse_args()
    source = a.rig / 'ftesurf'
    cases = [
        ('compiled-failure', unit),
        ('empty-trace', lambda gd: lines(gd, lambda s: s[:1])),
        ('truncated-row', lambda gd: lines(gd, lambda s: s[:2] + [' '.join(s[2].split()[:-1])] + s[3:])),
        ('missing-quarter', lambda gd: lines(gd, lambda s: s[:2] + s[3:])),
        ('duplicate-quarter', lambda gd: row(gd, 0, 0)),
        ('nan-velocity', lambda gd: row(gd, 9, 'nan')),
        ('infinite-camera', lambda gd: row(gd, 15, 'inf')),
        ('visual-position', lambda gd: row(gd, 6, 999)),
        ('visual-time', lambda gd: row(gd, 2, 999)),
        ('velocity', lambda gd: row(gd, 10, 9999)),
        ('raw-view', lambda gd: row(gd, 13, 45)),
        ('first-person-position', lambda gd: row(gd, 15, 999)),
        ('first-person-view', lambda gd: row(gd, 19, 45)),
        ('chase-view', lambda gd: row(gd, 25, 45)),
        ('bad-raw-index', lambda gd: row(gd, 31, -1)),
    ]
    with tempfile.TemporaryDirectory(prefix='visual-grade-', dir=a.rig.parent) as temp:
        for name, mutate in [('positive', None)] + cases:
            gd = Path(temp) / name
            for sub in ('cfg/test', 'logs'):
                (gd / sub).mkdir(parents=True)
            for pattern in ('stitch_*.txt', 'visual_*.txt'):
                for p in (source / 'cfg/test').glob(pattern):
                    shutil.copy2(p, gd / 'cfg/test' / p.name)
            for p in (source / 'logs').glob('*.log'):
                shutil.copy2(p, gd / 'logs' / p.name)
            if mutate:
                mutate(gd)
            rejected = False
            with contextlib.redirect_stdout(io.StringIO()):
                try:
                    grade(gd)
                except (AssertionError, ValueError, IndexError):
                    rejected = True
            assert rejected == bool(mutate), (name, 'grader accepted a negative or rejected the positive')
            print('PASS', name)
    print(f'{len(cases)+1} counterfactual checks, 0 failed')


if __name__ == '__main__':
    main()
