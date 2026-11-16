#!/usr/bin/env python3
"""Patch 1597: a lobby requires online terms 9; a stored answer of 8 reports 0.

    python -B tools/p1597terms.py --out <dir under an OWNER.md root> --progs <dir with the three .dat>
                                  --cfgsrc <tree> [--control] [--client exe]

One windowed client per stored answer (data/consent.txt `version 8`, then `version 9`) hosts a local game on
p762keys' box map. Graded on the server's own line from `cmd timer` ("public pause metadata consent: <recorded>
(needs <tier>)") beside the client's rec_terms. With P1597: 8 -> 0 (needs 9), 9 -> 9 (needs 9). --control with
progs before P1597: both record 8 (needs 8). Run under the rig lock. Copied content is trimmed after; logs stay.
"""
import argparse
import json
import re
import shutil
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from p762keys import Client, prepare, sha  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--progs', type=Path, required=True, help='the ftesurf/ holding the three .dat')
    ap.add_argument('--cfgsrc', type=Path, required=True, help='the tree whose default.cfg goes with them')
    ap.add_argument('--control', action='store_true', help='progs before P1597: every answer records 8')
    ap.add_argument('--content', type=Path, default=Path('C:/FTESurf'))
    ap.add_argument('--client', type=Path, default=Path('C:/FTESurf/ftesurf64.exe'))
    a = ap.parse_args()
    a.out = a.out.resolve()
    if not any((p / 'OWNER.md').is_file() for p in a.out.parents):
        ap.error('--out must be beneath an owned task root')
    a.out.mkdir(parents=True, exist_ok=False)
    want = {8: ('8', '8'), 9: ('8', '8')} if a.control else {8: ('0', '9'), 9: ('9', '9')}
    checks = []
    report = {'utc': datetime.now(timezone.utc).isoformat(), 'control': a.control,
              'progs': {p: sha(a.progs / p) for p in ('qwprogs.dat', 'csprogs.dat', 'menu.dat')},
              'client': sha(a.client), 'checks': checks}

    def check(ok, name, detail=''):
        checks.append({'name': name, 'pass': bool(ok), 'detail': str(detail)})
        print(('ok   ' if ok else 'FAIL ') + name + '  ' + str(detail), flush=True)

    try:
        for tier in (8, 9):
            base = prepare(a, a.out / f'tier{tier}')
            game = base / 'ftesurf'
            (game / 'data/consent.txt').write_text(f'FTESURF-CONSENT 1\nversion {tier}\naccepted 20261117-000000\n')
            cfg = game / 'probe.cfg'
            cfg.write_text('set rec_upload 1\n' + cfg.read_text())
            cl = Client(a.client, base, 'probe.cfg')
            rt = got = None
            try:
                cl.wait('FTESurf CSQC loaded', 0, timeout=90)
                time.sleep(3)
                rt = cl.query('rec_terms', r'"rec_terms" is "([-\d.]+)"')[1]
                m = cl.query('cmd timer', r'public pause metadata consent: ([-\d.]+) \(needs ([-\d.]+)\)')
                got = (m[1], m[2])
            except RuntimeError as e:
                print('  ', e, flush=True)
            finally:
                cl.stop()
            text = cl.text()
            check(rt == str(tier), f'answer {tier}: the menu set rec_terms from the file', rt)
            check(got == want[tier], f'answer {tier}: the server records {want[tier][0]} (needs {want[tier][1]})', got)
            bad = re.findall(r'(?im)^.*(?:VM error|Unknown command|PR_ExecuteProgram|stack overflow).*$', text)
            check(not bad, f'answer {tier}: no VM error or unknown command', bad[:3])
            for leaf in game.iterdir():   # trim the copied content, keep logs and data
                if leaf.name in ('logs', 'data'):
                    continue
                if leaf.is_dir() and not leaf.is_symlink() and not getattr(leaf, 'is_junction', lambda: False)():
                    shutil.rmtree(leaf)
                elif leaf.is_file():
                    leaf.unlink()
    finally:
        fails = [c['name'] for c in checks if not c['pass']]
        report['fails'] = fails
        (a.out / 'report.json').write_text(json.dumps(report, indent=1))
        print(f'{len(checks) - len(fails)} of {len(checks)} checks passed', flush=True)
    return 1 if fails or not checks else 0


if __name__ == '__main__':
    sys.exit(main())
