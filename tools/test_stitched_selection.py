#!/usr/bin/env python3
"""Acted counterfactuals on a retained private --selection-audit rig.

Copies only diagnostic artifacts into private temporary directories, never
mutates the source rig, player saves, content junctions or evidence.
"""
import argparse
import contextlib
import io
from pathlib import Path
import shutil
import tempfile

from stitched_selection import grade


def field(gd, name, key, value):
    p = gd / 'cfg/test' / name
    lines = p.read_text().splitlines()
    indices = [i for i, s in enumerate(lines) if s.startswith(key + ' ')]
    assert len(indices) == 1, 'counterfactual did not act'
    lines[indices[0]] = key + ' ' + value
    p.write_text('\n'.join(lines) + '\n')


def closer_candidate(gd):
    p = gd / 'cfg/test/selection_server_cold2_hold1.txt'
    lines = p.read_text().splitlines()
    request = lines[0].split()[1:]
    selected = lines[1].split()[1:]
    assert request[1:] != selected[1:], 'closer counterfactual did not act'
    index = next(i for i, s in enumerate(lines) if s.startswith('row ' + selected[0] + ' '))
    lines[index] = 'row ' + ' '.join([selected[0]] + request[1:])
    p.write_text('\n'.join(lines) + '\n')


def raw_row(gd, remove):
    p = gd / 'cfg/test/stitch_warm2_hold1.txt'
    lines = p.read_text().splitlines()
    assert len(lines) > 10, 'raw counterfactual did not act'
    if remove:
        lines.pop()
    else:
        words = lines[-1].split()
        words[1] = '0'
        lines[-1] = ' '.join(words)
    p.write_text('\n'.join(lines) + '\n')


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--rig', type=Path, required=True)
    a = ap.parse_args()
    server = 'selection_server_cold2_hold1.txt'
    client = 'selection_client_cold2_hold1.txt'
    cases = [
        ('selected-pose', lambda gd: field(gd, server, 'selected', '100 0 0 0')),
        ('selected-clock', lambda gd: field(gd, server, 'selected', '1 0 0 0')),
        ('closer-candidate', closer_candidate),
        ('missing-ring', lambda gd: field(gd, server, 'rules', '.015 .5 1 0')),
        ('wrong-window', lambda gd: field(gd, server, 'rules', '.015 1 1 100')),
        ('missing-near-rule', lambda gd: field(gd, server, 'rules', '.015 .5 0 100')),
        ('wrong-wire-pose', lambda gd: field(gd, server, 'request', '100 0 0 0')),
        ('ack-clock', lambda gd: field(gd, client, 'ack', '1 2 2 .015')),
        ('ack-ticket', lambda gd: field(gd, client, 'ack', '100 1 2 .015')),
        ('load-not-acted', lambda gd: field(gd, client, 'event', '1 1 1')),
        ('clock-not-normalized', lambda gd: field(gd, 'selection_clock.txt', 'clock 49', '.735 .735 .690 .750')),
        ('raw-row-missing', lambda gd: raw_row(gd, True)),
        ('raw-row-corrupted', lambda gd: raw_row(gd, False)),
        ('cursor-wrong-pose', lambda gd: field(gd, 'selection_client_cold2_cursor.txt', 'cursor', '1.5 0 0 0')),
        ('nonfinite', lambda gd: field(gd, server, 'selected', 'nan 0 0 0')),
        ('short-row', lambda gd: field(gd, client, 'ack', '1')),
        ('missing-file', lambda gd: (gd / 'cfg/test' / server).unlink()),
        ('duplicate-field', lambda gd: field(gd, client, 'ack', '1 2 2 .015\nack 1 2 2 .015')),
    ]
    with tempfile.TemporaryDirectory(prefix='selection-grade-', dir=a.rig.parent) as temp:
        for name, mutate in [('positive', None)] + cases:
            gd = Path(temp) / name
            (gd / 'cfg/test').mkdir(parents=True)
            (gd / 'logs').mkdir()
            for pattern in ('selection_*.txt', 'stitch_*.txt', 'server_*.txt'):
                for p in (a.rig / 'ftesurf/cfg/test').glob(pattern):
                    shutil.copy2(p, gd / 'cfg/test' / p.name)
            for log in ('runlines_smoke.log', 'runlines_server.log'):
                shutil.copy2(a.rig / 'ftesurf/logs' / log, gd / 'logs' / log)
            if mutate:
                mutate(gd)
            rejected = False
            with contextlib.redirect_stdout(io.StringIO()):
                try:
                    grade(gd)
                except (AssertionError, FileNotFoundError):
                    rejected = True
            assert rejected == bool(mutate), (name, 'accepted a negative or rejected the positive')
            print('PASS', name)
    print(f'{len(cases) + 1} selection counterfactual checks, 0 failed')


if __name__ == '__main__':
    main()
