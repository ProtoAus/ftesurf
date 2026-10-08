#!/usr/bin/env python3
"""Counterfactual grader controls on a retained private six-cut rig.

python tools/test_stitched_rewind_smoke.py --rig <private rig> [--buffered]
Copies only test artifacts beside the rig; never mutates its evidence or saves.
"""
import argparse
import contextlib
import io
from pathlib import Path
import shutil
import tempfile

from stitched_rewind_smoke import grade


def change(path, old, new):
    text = path.read_text()
    assert old in text, 'counterfactual did not ACT'
    path.write_text(text.replace(old, new, 1))


def native_field(gd, name, field, value):
    path = gd / f'cfg/test/server_{name}.txt'
    lines = path.read_text().splitlines()
    found = [i for i, s in enumerate(lines) if s.startswith(field + ' ')]
    assert len(found) == 1
    lines[found[0]] = field + ' ' + value
    path.write_text('\n'.join(lines) + '\n')


def freeze_release(gd):
    path = gd / 'cfg/test/stitch_cold3_release.txt'
    held = (gd / 'cfg/test/stitch_cold3_hold2.txt').read_text().splitlines()
    released = path.read_text().splitlines()
    header = released[0].split()
    header[3] = held[0].split()[3]
    path.write_text(' '.join(header) + '\n' + released[1] + '\n' + '\n'.join(held[2:]) + '\n')


def shifted_request(gd, bad_body=False):
    path = gd / 'cfg/test/stitch_warm1_cursor.txt'
    lines = path.read_text().splitlines()
    words = lines[1].split()
    assert words[0] == 'cursor'
    words[1] = str(float(words[1]) + .2)
    lines[1] = ' '.join(words)
    path.write_text('\n'.join(lines) + '\n')
    if bad_body:
        native_field(gd, 'warm1_hold1', 'body', '0 0 0')


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--rig', type=Path, required=True)
    ap.add_argument('--buffered', action='store_true')
    a = ap.parse_args()
    source = a.rig / 'ftesurf'
    cases = [
        ('native-body', lambda gd: native_field(gd, 'cold2_hold1', 'body', '0 0 0')),
        ('empty-body', lambda gd: native_field(gd, 'cold2_hold1', 'body', '')),
        ('short-body', lambda gd: native_field(gd, 'cold2_hold1', 'body', '0 0')),
        ('empty-expected', lambda gd: native_field(gd, 'cold2_hold1', 'expected', '')),
        ('short-expected', lambda gd: native_field(gd, 'cold2_hold1', 'expected', '0 0')),
        ('native-nan', lambda gd: native_field(gd, 'cold2_hold1', 'body', 'nan 0 0')),
        ('native-infinity', lambda gd: native_field(gd, 'cold2_hold1', 'body', 'inf 0 0')),
        ('short-ticks', lambda gd: native_field(gd, 'cold2_hold1', 'ticks', '1')),
        ('duplicate-native', lambda gd: change(gd / 'cfg/test/server_cold2_hold1.txt', 'expected ', 'expected 0 0 0\nexpected ')),
        ('held-clock', lambda gd: native_field(gd, 'warm1_hold2', 'ticks', '1 2')),
        ('release-not-acted', lambda gd: native_field(gd, 'cold3_release', 'hold', '1 1 1')),
        ('missing-guard', lambda gd: change(gd / 'logs/runlines_server.log', 'STITCH GUARD cold-match', 'NOT A GUARD')),
        ('wrong-guard', lambda gd: change(gd / 'logs/runlines_server.log', 'STITCH GUARD cold-match 1 1', 'STITCH GUARD cold-match 0 1')),
        ('runtime-error', lambda gd: change(gd / 'logs/runlines_server.log', 'STITCH GUARD fresh-key', 'QC VM error\nSTITCH GUARD fresh-key')),
        ('release-raw-frozen', freeze_release),
        ('hold-raw-corrupted', lambda gd: change(gd / 'cfg/test/stitch_warm2_hold2.txt', '\n0.000', '\n0.001')),
        ('cold-prefix-corrupted', lambda gd: change(gd / 'data/saves/surf_dune/save001/trail.txt', '\n0.000', '\n0.001')),
        ('requested-clock', shifted_request),
        ('requested-clock-and-body', lambda gd: shifted_request(gd, bad_body=True)),
    ]
    if not a.buffered:
        cases.append(('cold-adopted-identity', lambda gd: native_field(gd, 'cold1_hold1', 'identity', '1 1')))
    with tempfile.TemporaryDirectory(prefix='stitch-grade-', dir=a.rig.parent) as temp:
        root = Path(temp)
        for name, mutate in [('positive', None)] + cases:
            gd = root / name
            (gd / 'cfg/test').mkdir(parents=True)
            (gd / 'logs').mkdir()
            (gd / 'data/saves/surf_dune/save001').mkdir(parents=True)
            for pattern in ('stitch_*.txt', 'server_*.txt'):
                for path in (source / 'cfg/test').glob(pattern):
                    shutil.copy2(path, gd / 'cfg/test' / path.name)
            for name in ('runlines_smoke.log', 'runlines_server.log'):
                shutil.copy2(source / 'logs' / name, gd / 'logs' / name)
            shutil.copy2(source / 'data/saves/surf_dune/save001/trail.txt', gd / 'data/saves/surf_dune/save001/trail.txt')
            if mutate:
                mutate(gd)
            rejected = False
            error = None
            with contextlib.redirect_stdout(io.StringIO()):
                try:
                    grade(gd, not a.buffered)
                except (AssertionError, RuntimeError) as exc:
                    rejected = True
                    error = exc
            assert rejected == bool(mutate), (gd.name, 'grader accepted a negative or rejected the positive')
            if gd.name == 'requested-clock':
                assert isinstance(error, RuntimeError) and 'requested-prefix controls failed' in str(error), error
            if gd.name == 'requested-clock-and-body':
                assert isinstance(error, AssertionError) and 'native body or held clock' in str(error), error
            print('PASS', gd.name)
    print(f'{len(cases) + 1} counterfactual checks, 0 failed')


if __name__ == '__main__':
    main()
