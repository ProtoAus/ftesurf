#!/usr/bin/env python3
"""P1400 arm: the Keyboard tab's typed command, key Edit/Clear and the new tool rows.

    python -B tools/p1400keys.py --out <dir under an OWNER.md root> --progs <build.ps1 -NoDeploy dir>

Hosted game in a --size window (1280x720). Keys are typed as window messages (WM_KEYDOWN on the game's own queue);
the field is focused with `config_menu focus`, what a click on it does. Graded on bindlist and the
panel's own status lines; screenshots are for a person. Needs the rig lock.
"""
import argparse
import json
import re
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import p840clock as R  # noqa: E402
import p1384lead as L  # noqa: E402
import p615link as K  # noqa: E402
from spec_chat_smoke import Peer  # noqa: E402
from p1392keys import binds  # noqa: E402

VK = {'enter': 0x0D, 'esc': 0x1B, 'back': 0x08, 'space': 0x20, 'end': 0x23}


def status(cl):
    off = len(cl.text())
    cl.send('config_menu status')
    time.sleep(1.0)
    return [l[20:] for l in cl.text()[off:].splitlines() if 'config_menu: open' in l or 'config_menu: tab' in l]


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--progs', type=Path, required=True)
    ap.add_argument('--size', default='1280x720', help='window WxH (Peer opens 640x480; vid_restart maximised it)')
    a = ap.parse_args()
    w, h = a.size.split('x')
    real = subprocess.Popen

    def sized(args, *k, **kw):
        if '-window' in args:
            i = args.index('-width')
            args = args[:i] + ['-width', w, '-height', h] + args[i + 4:]
        return real(args, *k, **kw)
    subprocess.Popen = sized
    a.out = a.out.resolve()
    R.owned(a.out)
    a.out.mkdir(parents=True, exist_ok=False)
    base = L.prepare(a.out, 'client', a.progs, a.progs / 'csprogs.dat')
    game = base / 'ftesurf'
    common = ['cfg_save_auto 0', 'con_savehistory 0', 'log_enable 1', 'log_dir logs', 'log_name probe',
              'log_readable 1', 'developer 0', 'set cl_idlefps 0', 'set cl_maxfps 100', 'set run_resume 0',
              'set lobby_dir ""', 'set lobby_master ""', 'set sv_public 0', 'set milk_enable 0',
              'set update_autocheck 0', 'name "P1400 Arm"', f'vid_conwidth {w}', f'vid_conheight {h}',
              f'map {L.MAP}']   # the 2D canvas is the layout's screen, whatever the window became
    (game / 'probe.cfg').write_text('\n'.join(common) + '\n')
    res = {}
    R.take_lock('p1400 keys arm (ftesurf-3a)')
    cl = None
    try:
        cl = Peer(L.CONTENT / 'ftesurf64.exe', base, 'probe.cfg')
        cl.wait('FTESurf CSQC loaded', timeout=180)
        time.sleep(4)
        cl.send('menu_restart; ui_close')
        time.sleep(1.5)
        keys = K.Keys(cl.proc.pid)

        def post(vk, down):
            lp = 1 | (keys.u.MapVirtualKeyW(vk, 0) << 16) | ((1 << 24) if vk == VK['end'] else 0)
            if not down:
                lp |= (1 << 30) | (1 << 31)
            keys.u.PostMessageW(keys.hwnd, 0x0100 if down else 0x0101, vk, lp)
            time.sleep(0.04)

        def type_(text):
            for ch in text:
                vk = VK['space'] if ch == ' ' else ord(ch.upper())
                post(vk, True)
                post(vk, False)
            time.sleep(0.3)

        def tap(name):
            post(VK[name], True)
            post(VK[name], False)
            time.sleep(0.4)

        def lines(off, pat='config_menu'):
            return [l[20:] for l in cl.text()[off:].splitlines() if pat in l][:10]

        b0 = binds(cl)
        res['before'] = {k: b0.get(k) for k in ('MOUSE4', 'HOME', 'ESCAPE', 'F3')}
        cl.send('config_menu keyboard')
        time.sleep(2)
        cl.send('screenshot p1400_keyboard.png')
        time.sleep(2)

        # 1. Your own command: focus, type, Enter, then a key click binds it.
        off = len(cl.text())
        cl.send('config_menu focus cmd')
        time.sleep(0.6)
        type_('echo p1400 own')
        res['typing_status'] = status(cl)
        cl.send('screenshot p1400_typing.png')
        time.sleep(2)
        tap('enter')
        res['after_enter_status'] = status(cl)
        cl.send('config_menu click MOUSE4')
        time.sleep(1)
        res['own_lines'] = lines(off)
        b1 = binds(cl)
        res['own_bound'] = {k: b1.get(k) for k in ('MOUSE4',)}
        res['own_status'] = status(cl)
        cl.send('screenshot p1400_own.png')
        time.sleep(2)

        # 2. Edit: the field starts with the bind; typed text appends; Enter binds it.
        off = len(cl.text())
        cl.send('config_menu focus edit MOUSE4')
        time.sleep(0.6)
        tap('end')
        type_(' x')
        cl.send('screenshot p1400_edit.png')
        time.sleep(2)
        tap('enter')
        b2 = binds(cl)
        res['edit_bound'] = {k: b2.get(k) for k in ('MOUSE4',)}
        # Esc in a field leaves the field, not the panel.
        cl.send('config_menu focus edit MOUSE4')
        time.sleep(0.6)
        tap('esc')
        res['esc_status'] = status(cl)
        b3 = binds(cl)
        res['esc_bound'] = {k: b3.get(k) for k in ('MOUSE4',)}
        # Empty edit clears; a kept key refuses.
        cl.send('config_menu editkey MOUSE4')
        time.sleep(0.6)
        cl.send('config_menu editkey ESCAPE echo nope')
        time.sleep(0.6)
        res['edit_lines'] = lines(off)
        b4 = binds(cl)
        res['cleared'] = {k: b4.get(k) for k in ('MOUSE4', 'ESCAPE')}

        # 3. A new tool row on a key, then off again.
        off = len(cl.text())
        cl.send('config_menu place report HOME')
        time.sleep(0.6)
        b5 = binds(cl)
        res['tool_bound'] = {k: b5.get(k) for k in ('HOME', 'F3')}
        cl.send('config_menu clearkey HOME')
        time.sleep(0.6)
        res['tool_lines'] = lines(off)
        b6 = binds(cl)
        res['tool_cleared'] = {k: b6.get(k) for k in ('HOME',)}

        cl.send('config_menu actions')
        time.sleep(1.5)
        cl.send('screenshot p1400_actions.png')
        time.sleep(2)
        cl.send('config_menu keyboard')
        time.sleep(1.5)
        cl.send('screenshot p1400_keyboard_end.png')
        time.sleep(2)
        cl.send('config_menu')
        time.sleep(1)
        res['closed_status'] = status(cl)
    finally:
        if cl is not None:
            cl.stop()
        R.drop_lock()
    res['screenshots'] = sorted(p.name for p in game.glob('screenshots/*'))
    (a.out / 'report.json').write_text(json.dumps(res, indent=1))
    print(json.dumps(res, indent=1))


if __name__ == '__main__':
    main()
