#!/usr/bin/env python3
"""Grade cfg/test/p718tags.cfg's dedicated-socket run. No player data is printed.

python tools/p718tags_check.py PATH/TO/RETAINED/RIG [--control]
Control expects the old label and stale latch; subject expects the repair.
"""
import argparse
import re
from pathlib import Path


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('rig', type=Path)
    ap.add_argument('--control', action='store_true')
    args = ap.parse_args()
    text = (args.rig / 'ftesurf/logs/runlines_smoke.log').read_text(
        encoding='utf-8', errors='replace')
    checks = []

    def check(name, ok):
        checks.append(bool(ok))
        print(('ok   ' if ok else 'FAIL ') + name)

    check('completed', 'RUNLINES COMPLETE' in text)
    check('no command/VM errors', not re.search(
        r'Unknown command|QC VM error|Cannot call|stack overflow', text))
    arms = dict(re.findall(r'P718 ([A-I]) [^\n]*\n(.*?)(?=P718 [A-I] |\Z)',
                           text, re.S))
    check('all nine arms acted', len(arms) == 9)
    reason = 'cheated' if args.control else 'practice'
    expected = {'A': ('clean', 0, 0, 0), 'B': (reason, 0, 1, 1),
                'C': (reason, 1, 1, 1) if args.control else ('segmented', 1, 0, 0),
                'D': (reason, 1, 1, 1), 'E': (reason, 1, 1, 1),
                'F': (reason, 1, 1, 1) if args.control else ('segmented', 1, 0, 0),
                'G': ('clean', 0, 0, 0), 'H': ('clean', 0, 0, 0),
                'I': ('clean', 0, 0, 0)}
    for arm, (kind, seg, cheat, latch) in expected.items():
        body = arms.get(arm, '')
        check(arm + ' class/latch',
              f'class: {kind} (seg {seg} cheat {cheat} cheatlatch {latch})' in body)
        check(arm + ' stage reason',
              f'stage class: stitch {seg} cheat {cheat}' in body)
        running = arm in 'ABCDEF I'.replace(' ', '')
        check(arm + ' timer/recorder acted',
              ('timer: running ' if running else 'timer: armed ') in body
              and f'recording {int(running)}' in body)
    check('noclip toggled in both directions', 'noclip ON' in text and 'noclip OFF' in text)
    check('active noclip was not cleansed', '(sv_cheats 0, noclip 1)' in arms.get('E', ''))
    check('subject has no Cheated display', args.control or not re.search(r'\bcheated\b', text, re.I))
    banner = 'CHEATED' if args.control else 'PRACTICE'
    check('full banner reason label', bool(re.search(
        rf'banner: draws "MAP COMPLETE"[^\n]*"{banner}"', text)))
    check('stage banner reason label', bool(re.search(
        rf'banner: draws "STAGE 1"[^\n]*"{banner}"', text)))
    filters = re.findall(r'tab local   filter (\w+)', text)
    check('practice filter and legacy alias',
          filters[-2:] == (['all', 'cheated'] if args.control else ['practice', 'practice']))
    for row, cheat, state in [(1, 0, 2), (2, 1, 2), (3, 0, 1)]:
        p = args.rig / f'ftesurf/data/saves/surf_dune/save{row:03}/state.txt'
        saved = p.read_text(encoding='utf-8') if p.exists() else ''
        check(f'save {row} has its own reason/state',
              f'\ncheat {cheat}\n' in saved and f'\nstate {state}\n' in saved)
    print(f'{len(checks)} checks, {len(checks) - sum(checks)} failed')
    return int(not all(checks))


if __name__ == '__main__':
    raise SystemExit(main())
