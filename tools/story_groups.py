#!/usr/bin/env python3
"""Snapshot public aggregate Story group cuts (never player rows).

Run from repository root: python tools/story_groups.py --output tools/story-groups.json
The catalogue uses static milliseconds, not moving targets. Refresh is explicit.
"""
import argparse
import json
from pathlib import Path
import shlex
import time
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import urlopen


def courses(text):
    wanted = set()
    active = False
    for line in text.splitlines():
        w = shlex.split(line.split('//', 1)[0])
        if not w:
            continue
        if w[0] == 'list':
            active = w[1] == 'story'
        if active and w[0] == 'level' and w[1] != 'soon':
            wanted.add((w[1], int(w[3]) if len(w) == 4 else 0))
    return sorted(wanted | {('surf_autosave', 0), ('surf_gary_barlow', 0)})


def fetch(course):
    name, track = course
    url = 'https://play.proto.bar/api/board?' + urlencode({'groups': name, 'style': 'clean'})
    try:
        with urlopen(url, timeout=30) as response:
            data = json.load(response)
    except HTTPError as exc:
        if exc.code != 429:
            raise
        time.sleep(65)
        with urlopen(url, timeout=30) as response:
            data = json.load(response)
    leg = next((r for r in data['legs'] if r['track'] == track and r['leg'] == 0), None)
    return dict(leg or {}, map=name, track=track, epoch=data['t'])


def calibrate(text, snapshot):
    """Replace ordinary Story medals only; occupied courses and Events stay put."""
    refs = {(r['map'], r['track']): r for r in snapshot['courses']}
    out = []
    active = False
    for line in text.splitlines():
        w = shlex.split(line.split('//', 1)[0])
        if w and w[0] == 'list':
            active = w[1] == 'story'
        if active and w and w[0] in ('bronze', 'silver', 'gold'):
            continue
        out.append(line)
        if not active or not w or w[0] != 'level' or w[1] == 'soon':
            continue
        track = int(w[3]) if len(w) == 4 else 0
        row = refs[(w[1], track)]
        out.append('  bronze finish')
        if 'ms' not in row:
            continue
        for medal, i, group in [('silver', 4, 'G4'), ('gold', 2, 'G2')]:
            ms = row['ms'][i] + 1  # time is strict-under; groups include boundary ties
            minutes, rem = divmod(ms, 60000)
            seconds, millis = divmod(rem, 1000)
            out.append(f'  {medal} time {minutes}:{seconds:02d}.{millis:03d}'
                       f' // {group} {row["src"]} n={row["x"]}; boundary +1 ms')
    return '\n'.join(out) + '\n'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--catalogue', type=Path, default=Path('surfd/story.txt'))
    parser.add_argument('--output', type=Path)
    parser.add_argument('--apply-snapshot', type=Path)
    args = parser.parse_args()
    if args.apply_snapshot:
        args.catalogue.write_text(calibrate(args.catalogue.read_text(),
                                            json.loads(args.apply_snapshot.read_text())))
        return
    if args.output is None:
        parser.error('--output or --apply-snapshot is required')
    rows = []
    for course in courses(args.catalogue.read_text()):
        rows.append(fetch(course))
        time.sleep(1)
    args.output.write_text(json.dumps({'style': 'clean', 'courses': rows}, indent=2) + '\n')
    print(f'{len(rows)} courses; {sum("ms" in r for r in rows)} with group cuts')


if __name__ == '__main__':
    main()
