#!/usr/bin/env python3
"""Patches 795/796: the menu's KSF board with pictures, and the new first-boot screens.

One client, no server, in its own basedir under --out (p744spec.py's fixture), online
consent and the real board directory, running cfg/test/p795board.cfg.  surf_beginner's
KSF board has 50 rows, every one with a picture, so the menu holds several picture
slots at once: P789's MP_Of read mp_used[-1] there and the menu VM died.

Graded on the menu's own lines:
  alive      `ui_board_test` answered after the board drew, with "slots held N", N >= 2
             (the state the crash needs), and no "boundcheck" in the log
  screens    the four screenshots were written; ui_strip_test's fit lines for both terms
--control expects the opposite of `alive`: a boundcheck failure and no status line.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from p744spec import prepare, sha  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--progs', type=Path, required=True)
    ap.add_argument('--control', action='store_true')
    ap.add_argument('--content', type=Path, default=Path('C:/FTESurf'))
    ap.add_argument('--client', type=Path, default=Path('C:/FTESurf/ftesurf64.exe'))
    ap.add_argument('--plugin', type=Path, default=Path('C:/FTESurf/fteplug_hl2_x64.dll'))
    a = ap.parse_args()
    a.out = a.out.resolve()
    if not any((p / 'OWNER.md').is_file() for p in a.out.parents):
        ap.error('--out must be beneath an owned task root')
    a.out.mkdir(parents=True, exist_ok=False)
    checks = []
    report = {'utc': datetime.now(timezone.utc).isoformat(), 'control': a.control,
              'progs': {p: sha(a.progs / p) for p in ('qwprogs.dat', 'csprogs.dat', 'menu.dat')},
              'client': sha(a.client), 'checks': checks}

    def check(ok, name):
        checks.append({'name': name, 'pass': bool(ok)})
        print(('PASS ' if ok else 'FAIL ') + name, flush=True)

    base = prepare(a, 'client')
    game = base / 'ftesurf'
    (game / 'data/consent.txt').write_text('FTESURF-CONSENT 1\nversion 6\naccepted 20261018-000000\n')
    cfg = (ROOT / 'ftesurf/cfg/test/p795board.cfg').read_text()
    (game / 'probe.cfg').write_text('log_name probe\nset lobby_dir "https://play.proto.bar"\nset update_consent 0\n' + cfg)
    proc = subprocess.Popen(
        [str(a.client), '-nohome', '-noreset', '-nobrowse', '-basedir', str(base),
         '-manifest', str(base / 'default.fmf'), '-window', '-width', '1280', '-height', '800',
         '-nosound', '+set', 'cfg_save_auto', '0', '+exec', 'probe.cfg'],
        cwd='C:/FTESurf', stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    (base / 'owned-pid.txt').write_text(str(proc.pid) + '\n')
    try:
        proc.wait(timeout=150)
    except subprocess.TimeoutExpired:
        proc.terminate()
        proc.wait(timeout=10)
        check(False, 'the client quit by itself')
    log = (game / 'logs/probe.log').read_text(encoding='utf-8', errors='replace') \
        if (game / 'logs/probe.log').exists() else ''
    (a.out / 'probe.log').write_text(log)
    held = [int(n) for n in re.findall(r'pictures: rows have them \d+; slots held (\d+)', log)]
    fault = re.search(r'(?i)boundcheck', log)
    report['slots_held'] = held
    report['fault'] = fault.group(0) if fault else None
    if a.control:
        check(fault and not held, 'control: the menu VM faults on the bound check, no status after')
    else:
        check(not fault, 'no bound-check failure')
        check(held and max(held) >= 2, 'the menu held two or more pictures and still answered')
        shots = sorted(p.name for p in (game / 'screenshots').glob('p79*'))
        report['screenshots'] = shots
        check(len(shots) >= 5, 'board, terms, full terms, F2 and main screenshots written')
        check(re.search(r'terms summary, journal box', log) and re.search(r'terms full, journal box', log),
              'both terms layouts measured')
    check('P795 ARM COMPLETE' in log or a.control, 'the cfg ran to its end')
    report['failures'] = sum(1 for c in checks if not c['pass'])
    (a.out / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    print('report', a.out / 'report.json', 'failures', report['failures'])


if __name__ == '__main__':
    main()
