#!/usr/bin/env python3
"""Patch 762: config_menu, the key hints, the save-lock keys as binds, the vote card.

One windowed listen-server client on a generated box map, in an isolated basedir under
--out (its own MAINCONFIG, data root and logs; nothing of the install is written). Keys
are native WM_KEYDOWN/UP posted only to our own client's window (test_update_corner.py's
rule: never the owner's input, never focus). Graded on the subject's own lines: `bind`,
`config_menu status|hint`, `vote status`'s save count, the server's noclip line and the
config the panel saved. Screenshots of the hint, the panel and the vote card are kept.

--control runs the save-key gestures on a build without the patch: there `1` saves even
after its bind is cleared (a fixed scancode) and config_menu is an unknown command.
Run it under the rig lock (artifacts/rig_wait.py in this session's root).
"""
import argparse
import ctypes as C
from ctypes import wintypes as W
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_ui_modern import make_map  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
MAP = 'p762box'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def window(pid):
    user = C.WinDLL('user32', use_last_error=True)
    callback = C.WINFUNCTYPE(W.BOOL, W.HWND, W.LPARAM)
    user.GetWindowThreadProcessId.argtypes = (W.HWND, C.POINTER(W.DWORD))
    user.IsWindowVisible.argtypes = (W.HWND,)
    found = []

    @callback
    def visit(hwnd, _):
        actual = W.DWORD()
        user.GetWindowThreadProcessId(hwnd, C.byref(actual))
        if actual.value == pid and user.IsWindowVisible(hwnd):
            found.append(hwnd)
        return True

    user.EnumWindows(visit, 0)
    if len(found) != 1:
        raise RuntimeError(f'owned PID must have one visible HWND, found {len(found)}')
    return user, found[0]


class Client:
    def __init__(self, exe, base, cfg):
        self.base = base
        self.log = base / 'ftesurf/logs/probe.log'
        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        si.wShowWindow = 4              # shown, not activated
        self.proc = subprocess.Popen(
            [str(exe), '-plugin', '-nohome', '-noreset', '-nobrowse',
             '-basedir', str(base), '-manifest', str(base / 'default.fmf'),
             '-window', '-width', '1280', '-height', '720', '-nosound',
             '+set', 'cfg_save_auto', '0', '+exec', cfg],
            cwd='C:/FTESurf', stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL, startupinfo=si)
        (base / 'owned-pid.txt').write_text(str(self.proc.pid) + '\n')

    def text(self):
        return self.log.read_text(encoding='utf-8', errors='replace') if self.log.exists() else ''

    def send(self, line):
        self.proc.stdin.write(line.encode('utf-8') + b'\n')
        self.proc.stdin.flush()

    def wait(self, pattern, offset=0, timeout=30):
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            found = re.search(pattern, self.text()[offset:])
            if found:
                return found
            if self.proc.poll() is not None:
                raise RuntimeError(f'owned process exited {self.proc.returncode}: {self.log}')
            time.sleep(.1)
        raise RuntimeError(f'not reached: {pattern}: {self.log}')

    def query(self, command, pattern, timeout=20):
        offset = len(self.text())
        self.send(command)
        return self.wait(pattern, offset, timeout)

    def key(self, vk, settle=.5):
        """A native press and release of one virtual key, posted to our own window."""
        if self.proc.poll() is not None:
            raise RuntimeError('owned client already exited')
        user, hwnd = window(self.proc.pid)
        actual = W.DWORD()
        user.GetWindowThreadProcessId(hwnd, C.byref(actual))
        if actual.value != self.proc.pid:
            raise RuntimeError('HWND ownership changed')
        user.MapVirtualKeyW.argtypes = (W.UINT, W.UINT)
        scan = user.MapVirtualKeyW(vk, 0)
        ext = 1 << 24 if vk in (0x25, 0x26, 0x27, 0x28, 0x2D, 0x2E) else 0
        user.PostMessageW.argtypes = (W.HWND, W.UINT, W.WPARAM, W.LPARAM)
        for message, value in ((0x100, 1 | scan << 16 | ext), (0x101, 0xC0000001 | scan << 16 | ext)):
            if not user.PostMessageW(hwnd, message, vk, value):
                raise C.WinError(C.get_last_error())
            time.sleep(.12)
        time.sleep(settle)

    def stop(self):
        if self.proc.poll() is None:
            self.send('quit')
            try:
                self.proc.wait(timeout=15)
            except subprocess.TimeoutExpired:
                self.proc.terminate()
                self.proc.wait(timeout=10)


def prepare(a, out):
    base = out / 'client'
    game = base / 'ftesurf'
    for folder in ('cfg', 'glsl', 'scripts', 'particles', 'models', 'textures', 'gfx/fonts', 'gfx/ui',
                   'gfx/crosshairs'):
        if (a.content / 'ftesurf' / folder).is_dir():
            shutil.copytree(a.content / 'ftesurf' / folder, game / folder)
    for folder in ('maps', 'logs', 'data', 'screenshots', 'downloads/csprogsvers'):
        (game / folder).mkdir(parents=True, exist_ok=True)
    (game / 'data/consent.txt').write_text('version 4\n')
    for leaf in ('qwprogs.dat', 'csprogs.dat', 'menu.dat'):
        shutil.copy2(a.progs / leaf, game / leaf)
    shutil.copy2(a.cfgsrc / 'ftesurf/cfg/default.cfg', game / 'cfg/default.cfg')
    (game / f'maps/{MAP}.map').write_text(make_map())
    (base / 'default.fmf').write_text(
        'FTEMANIFEST 1\nGAME FTESurfP762Fixture\nBASEGAME ftesurf\n'
        'DISABLEHOMEDIR 1\nMAINCONFIG p762cfg\n'
        'set sv_mintic 0.015\nset sv_maxtic 0.015\nset cl_netfps 66.6667\n')
    common = ['cfg_save_auto 0', 'con_savehistory 0', 'log_enable 1', 'log_dir logs',
              'log_name probe', 'log_readable 1', 'set cl_idlefps 0', 'set cl_maxfps 100',
              'set run_resume 0', 'set lobby_dir ""', 'set lobby_master ""', 'set cl_run_upload 0',
              'set cl_board_url ""', 'set sv_public 0', 'set milk_enable 0', 'set update_autocheck 0',
              'developer 1', 'log_developer 1', f'map {MAP}.map']
    (game / 'probe.cfg').write_text('\n'.join(common) + '\n')
    return base


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--progs', type=Path, required=True, help='the ftesurf/ holding the three .dat')
    ap.add_argument('--cfgsrc', type=Path, required=True, help='the tree whose default.cfg goes with them')
    ap.add_argument('--control', action='store_true')
    ap.add_argument('--content', type=Path, default=Path('C:/FTESurf'))
    ap.add_argument('--client', type=Path, default=Path('C:/FTESurf/ftesurf64.exe'))
    a = ap.parse_args()
    a.out = a.out.resolve()
    if not any((p / 'OWNER.md').is_file() for p in a.out.parents):
        ap.error('--out must be beneath an owned task root')
    a.out.mkdir(parents=True, exist_ok=False)
    checks = []
    report = {'utc': datetime.now(timezone.utc).isoformat(), 'control': a.control,
              'progs': {p: sha(a.progs / p) for p in ('qwprogs.dat', 'csprogs.dat', 'menu.dat')},
              'client': sha(a.client), 'checks': checks}

    def check(ok, name, detail=''):
        checks.append({'name': name, 'pass': bool(ok), 'detail': detail})
        print(('PASS ' if ok else 'FAIL ') + name + (f'  [{detail}]' if detail else ''), flush=True)

    def bound(cl, key):
        # `bind <key>` prints `"<key>" = "<command>"` (link markup around the key on this engine);
        # an unbound key prints `"<key>" is not bound`.
        m = cl.query(f'bind {key}', r'(?:= "([^"\n]*)"|is not bound)')
        return m.group(1) if m.group(1) is not None else None

    def saves(cl):
        return int(cl.query('vote status', r'mapclock: .* saves (\d+)').group(1))

    def shot(cl, name):
        cl.send(f'screenshot {name}')
        time.sleep(1.2)
        found = sorted(cl.base.rglob(f'{name}*'))
        check(bool(found), f'screenshot {name} written', found[-1].name if found else '')

    def start(base):
        log = base / 'ftesurf/logs/probe.log'
        off = len(log.read_text(encoding='utf-8', errors='replace')) if log.exists() else 0   # the log appends
        cl = Client(a.client, base, 'probe.cfg')
        cl.wait('FTESurf CSQC loaded', off, timeout=60)
        time.sleep(2)
        cl.query('menu_restart; ui_close; cmd viewpos', r'setpos [-\d.]+ [-\d.]+ [-\d.]+', timeout=30)
        time.sleep(1)
        return cl

    VK = {'1': 0x31, 'z': 0x5A, 'k': 0x4B, 'j': 0x4A, 'x': 0x58, 'esc': 0x1B}
    base = prepare(a, a.out)
    try:
        run(a, base, check, bound, saves, shot, start, VK)
    finally:
        fails = [c['name'] for c in checks if not c['pass']]
        report['fails'] = fails
        (a.out / 'report.json').write_text(json.dumps(report, indent=1))
        print(f'{len(checks) - len(fails)} of {len(checks)} checks passed', flush=True)
    return 1 if fails or not checks else 0


def run(a, base, check, bound, saves, shot, start, VK):
    cl = start(base)
    try:
        if a.control:
            check(bound(cl, '1') is None, 'control: 1 has no bind (a fixed scancode saves)')
            n0 = saves(cl)
            cl.key(VK['1'], 1.5)
            n1 = saves(cl)
            check(n1 == n0 + 1, 'control: native 1 saves', f'{n0}->{n1}')
            cl.send('bind 1 ""')
            cl.key(VK['1'], 1.5)
            n2 = saves(cl)
            check(n2 == n1 + 1, 'control: 1 still saves with its bind cleared (cannot be moved)', f'{n1}->{n2}')
            m = cl.query('config_menu status', r'(Unknown command "config_menu"|config_menu: open)')
            check('Unknown' in m.group(1), 'control: config_menu does not exist')
            return

        # Boot 1: the shipped binds, the hint, the native keys.
        for key, want in (('z', 'save_menu'), ('1', 'sl_save'), ('2', '+sl_hold'), ('4', 'sl_del'),
                          ('k', 'config_menu'), ('x', 'gfx_menu'), ('v', 'noclip')):
            got = bound(cl, key)
            check(got == want, f'default.cfg binds {key} to {want}', str(got))
        m = cl.query('config_menu hint', r'config_menu: hint \[([^\]]*)\] shown (\d)')
        check(m.group(1) == 'Z|Saves;X|Graphics;C|HUD;V|Noclip;Bksp|Rewind;K|Keys' and m.group(2) == '1',
              'hint names the bound keys', m.group(1))
        shot(cl, 'p762_hud')

        n0 = saves(cl)
        cl.key(VK['1'], 1.5)
        n1 = saves(cl)
        check(n1 == n0 + 1, 'native 1 saves through its bind', f'{n0}->{n1}')
        cl.key(VK['z'])
        m = cl.query('config_menu status', r'savepanel (\d)')
        check(m.group(1) == '1', 'native z opens the save panel through save_menu')
        shot(cl, 'p762_savepanel')
        cl.key(VK['z'])
        m = cl.query('config_menu status', r'savepanel (\d)')
        check(m.group(1) == '0', 'native z closes it again (the panel lets z through to its bind)')

        cl.query('config_menu clear save 0', r'1 cleared from Save')    # printed as ^5config_menu^7: ...
        check(bound(cl, '1') == '', 'clear binds 1 to "" (persists over default.cfg)')
        cl.key(VK['1'], 1.5)
        n2 = saves(cl)
        check(n2 == n1, 'native 1 no longer saves once its bind is cleared', f'{n1}->{n2}')

        cl.key(VK['k'])
        m = cl.query('config_menu status', r'config_menu: open (\d)')
        check(m.group(1) == '1', 'native k opens the key panel')
        shot(cl, 'p762_panel')

        cl.query('config_menu capture turnleft 1', r'waiting for a key for turnleft')
        cl.key(VK['j'])
        check(bound(cl, 'j') == '+left', 'a captured native j is bound to +left')
        m = cl.query('config_menu status', r'config_menu: turnleft .* keys \[([^\]]*)\]')
        check(m.group(1) == 'e j', 'turn left lists e and j', m.group(1))

        off = len(cl.text())
        cl.query('config_menu capture noclip 0', r'waiting for a key for noclip')
        cl.key(VK['x'])
        check(bound(cl, 'x') == 'noclip', 'captured x moves noclip onto x')
        check(bound(cl, 'v') == '', "noclip's old key v is cleared")
        check('X: Noclip (was Graphics)' in cl.text()[off:], 'the status line names what x used to do')
        m = cl.query('config_menu hint', r'config_menu: hint \[([^\]]*)\]')
        check(m.group(1) == 'Z|Saves;C|HUD;X|Noclip;Bksp|Rewind;K|Keys', 'hint follows the new binds', m.group(1))

        cl.send('config_menu yaw 210')
        cl.send('config_menu sens 1.5')
        time.sleep(.5)
        m = cl.query('config_menu status', r'yawspeed ([\d.]+) sensitivity ([\d.]+)')
        check(m.group(1) == '210' and m.group(2) == '1.5', 'turn speed and sensitivity set', m.group(0))
        shot(cl, 'p762_panel2')

        off = len(cl.text())
        cl.key(VK['esc'])
        m = cl.query('config_menu status', r'config_menu: open (\d)')
        check(m.group(1) == '0', 'native ESC closes the panel')
        check('keys saved to ftesurf.cfg' in cl.text()[off:], 'closing a changed panel saves the config')

        off = len(cl.text())
        cl.key(VK['x'], 1.5)
        check(re.search(r'noclip (ON|OFF)', cl.text()[off:]) is not None,
              'native x runs noclip from the panel-made (insecure-level) bind')

        cl.send('vote fake open 2 30 3')
        cl.send('vote fake label 1 surf_utopia')
        cl.send('vote fake label 2 surf_kitsune')
        cl.send('vote fake label 3 "extend this map"')
        cl.send('vote fake votec "2 5 0"')
        time.sleep(1.5)
        shot(cl, 'p762_vote')
    finally:
        cl.stop()

    saved = (base / 'ftesurf/p762cfg.cfg')
    text = saved.read_text(errors='replace') if saved.exists() else ''
    for line in ('bindlevel j 30 "+left"', 'bindlevel v 30 ""', 'bindlevel x 30 "noclip"',
                 'bindlevel 1 30 ""'):
        check(line in text, f'saved config: {line}')
    check(re.search(r'cl_yawspeed "210"', text) is not None, 'saved config: cl_yawspeed 210')

    # Boot 2: default.cfg runs first and the saved binds win over it; then reset.
    cl = start(base)
    try:
        check(bound(cl, 'v') == '', 'after a restart v stays cleared (default.cfg would bind noclip)')
        check(bound(cl, 'x') == 'noclip', 'after a restart x is still noclip')
        check(bound(cl, '1') == '', 'after a restart 1 stays cleared')
        m = cl.query('config_menu status', r'yawspeed ([\d.]+)')
        check(m.group(1) == '210', 'after a restart turn speed is 210')
        cl.query('config_menu reset', r'every key back to its default')
        for key, want in (('x', 'gfx_menu'), ('v', 'noclip'), ('1', 'sl_save'), ('j', ''), ('e', '+left')):
            got = bound(cl, key)
            check(got == want, f'reset: {key} is {want or "cleared"}', str(got))
        m = cl.query('config_menu hint', r'config_menu: hint \[([^\]]*)\]')
        check(m.group(1) == 'Z|Saves;X|Graphics;C|HUD;V|Noclip;Bksp|Rewind;K|Keys', 'reset: hint back', m.group(1))
        # The reset's binds were made by the panel (insecure level): game-code commands must run from them.
        n0 = saves(cl)
        cl.key(VK['1'], 1.5)
        n1 = saves(cl)
        check(n1 == n0 + 1, 'native 1 runs sl_save from a panel-made bind', f'{n0}->{n1}')
        cl.key(VK['z'])
        m = cl.query('config_menu status', r'savepanel (\d)')
        check(m.group(1) == '1', 'native z runs save_menu from a panel-made bind')
    finally:
        cl.stop()


if __name__ == '__main__':
    sys.exit(main())
