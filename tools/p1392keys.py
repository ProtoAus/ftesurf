#!/usr/bin/env python3
"""P1392 arm: the key configuration panel's Keyboard tab in a hosted game.

    python -B tools/p1392keys.py --out <dir under an OWNER.md root> --progs <build.ps1 -NoDeploy dir>

Opens `config_menu keyboard` and screenshots it, prints `config_menu layout caps`, places jump on
MOUSE4 and HOME by command (what a click does), screenshots, clears them (a right-click), checks
`bindlist` before and after, then the Actions tab. Graded on the binds the engine reports, the
panel's own status lines, and the screenshots (looked at by a person). Needs the rig lock.
"""
import argparse
import json
import re
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import p840clock as R  # noqa: E402
import p1384lead as L  # noqa: E402
from spec_chat_smoke import Peer  # noqa: E402


def binds(cl):
    off = len(cl.text())
    cl.send('bindlist')
    time.sleep(1.0)
    out = {}
    for l in cl.text()[off:].splitlines():
        m = re.match(r'.{20}(\S+)\s+"([^"]*)"', l)
        if m:
            out[m[1].upper()] = m[2]
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--progs', type=Path, required=True)
    a = ap.parse_args()
    a.out = a.out.resolve()
    R.owned(a.out)
    a.out.mkdir(parents=True, exist_ok=False)
    base = L.prepare(a.out, 'client', a.progs, a.progs / 'csprogs.dat')
    game = base / 'ftesurf'
    common = ['cfg_save_auto 0', 'con_savehistory 0', 'log_enable 1', 'log_dir logs', 'log_name probe',
              'log_readable 1', 'developer 0', 'set cl_idlefps 0', 'set cl_maxfps 100', 'set run_resume 0',
              'set lobby_dir ""', 'set lobby_master ""', 'set sv_public 0', 'set milk_enable 0',
              'set update_autocheck 0', 'name "P1392 Arm"', f'map {L.MAP}']
    (game / 'probe.cfg').write_text('\n'.join(common) + '\n')
    res = {}
    R.take_lock('p1392 keys arm (ftesurf-3a)')
    cl = None
    try:
        cl = Peer(L.CONTENT / 'ftesurf64.exe', base, 'probe.cfg')
        cl.wait('FTESurf CSQC loaded', timeout=180)
        time.sleep(6)
        cl.send('menu_restart; ui_close')
        time.sleep(1.5)
        b0 = binds(cl)
        res['before'] = {k: b0.get(k) for k in ('MOUSE4', 'HOME', 'SPACE', 'F3')}
        off = len(cl.text())
        cl.send('config_menu layout caps')
        time.sleep(1.5)
        res['layout'] = [l[20:] for l in cl.text()[off:].splitlines() if 'config_menu' in l or 'unknown' in l][:12]
        cl.send('config_menu keyboard')
        time.sleep(2)
        cl.send('screenshot p1392_keyboard.png')
        time.sleep(1.5)
        off = len(cl.text())
        cl.send('config_menu place jump MOUSE4')
        time.sleep(0.5)
        cl.send('config_menu place jump HOME')
        time.sleep(1.5)
        cl.send('screenshot p1392_placed.png')
        time.sleep(1.5)
        res['place_lines'] = [l[20:] for l in cl.text()[off:].splitlines() if 'config_menu' in l][:8]
        b1 = binds(cl)
        res['placed'] = {k: b1.get(k) for k in ('MOUSE4', 'HOME', 'SPACE')}
        off = len(cl.text())
        cl.send('config_menu clearkey MOUSE4')
        cl.send('config_menu clearkey HOME')
        time.sleep(1)
        res['clear_lines'] = [l[20:] for l in cl.text()[off:].splitlines() if 'config_menu' in l][:8]
        b2 = binds(cl)
        res['cleared'] = {k: b2.get(k) for k in ('MOUSE4', 'HOME', 'SPACE')}
        cl.send('config_menu actions')
        time.sleep(1.5)
        cl.send('screenshot p1392_actions.png')
        time.sleep(1.5)
        cl.send('config_menu')
        time.sleep(1)
    finally:
        if cl is not None:
            cl.stop()
        R.drop_lock()
    res['screenshots'] = sorted(p.name for p in game.glob('screenshots/*'))
    (a.out / 'report.json').write_text(json.dumps(res, indent=1))
    print(json.dumps(res, indent=1))


if __name__ == '__main__':
    main()
