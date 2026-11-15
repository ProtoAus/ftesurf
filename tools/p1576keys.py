#!/usr/bin/env python3
"""Patch 1576: injected keys dropped (in_keyguard), guard cvars refuse a map's cvar_ keys, in_guard_live.

One windowed listen-server client on a generated box map whose worldspawn sets cvar_ keys for the three
guard cvars and for in_rawinput_rdp, which is not protected: it reading 1 shows the map lock ran. Keys are
WM_KEYDOWN/UP posted to our own client's window (p762keys.Client; never focus, never the owner's input),
which Windows reports as a posted message, not hardware. Graded on the subject's own lines: the bind's
echo, cvar reads and the engine's dropped-key lines.

--exe C:/FTESurf/ftesurf64.exe (a pre-1576 build) is the control: the map lock takes the guard cvars,
in_keyguard is unknown and the posted key arrives in every phase.
Run under the rig lock. Writes only under --out.
"""
import argparse
import hashlib
from pathlib import Path
import shutil
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parent))
from p762keys import Client  # noqa: E402
from test_ui_modern import make_map  # noqa: E402

MAP = 'p1576box'
KEYS = {'cvar_in_keyguard': '0', 'cvar_in_rawinput_nolegacy': '0', 'cvar_in_rawinput_touchpad': '1',
        'cvar_in_rawinput_rdp': '1'}
VK_K = 0x4B


def prepare(content, out):
    base = out / 'client'
    game = base / 'ftesurf'
    for folder in ('cfg', 'glsl', 'scripts', 'particles', 'models', 'gfx/fonts', 'gfx/ui'):
        if (content / 'ftesurf' / folder).is_dir():
            shutil.copytree(content / 'ftesurf' / folder, game / folder)
    for folder in ('maps', 'logs', 'data'):
        (game / folder).mkdir(parents=True, exist_ok=True)
    (game / 'data/consent.txt').write_text('version 4\n')
    for leaf in ('qwprogs.dat', 'csprogs.dat', 'menu.dat'):
        shutil.copy2(content / 'ftesurf' / leaf, game / leaf)
    world = make_map().replace('"classname" "worldspawn"\n',
                               '"classname" "worldspawn"\n' + ''.join('"%s" "%s"\n' % kv for kv in KEYS.items()), 1)
    assert 'cvar_in_keyguard' in world
    (game / f'maps/{MAP}.map').write_text(world)
    (base / 'default.fmf').write_text('FTEMANIFEST 1\nGAME FTESurfP1576Fixture\nBASEGAME ftesurf\n'
                                      'DISABLEHOMEDIR 1\nMAINCONFIG p1576cfg\n')
    common = ['cfg_save_auto 0', 'con_savehistory 0', 'log_enable 1', 'log_dir logs', 'log_name probe',
              'log_readable 1', 'set cl_idlefps 0', 'set cl_maxfps 100', 'set run_resume 0', 'set lobby_dir ""',
              'set lobby_master ""', 'set cl_run_upload 0', 'set cl_board_url ""', 'set sv_public 0',
              'set milk_enable 0', 'set update_autocheck 0', 'developer 1', 'log_developer 1', f'map {MAP}.map']
    (game / 'probe.cfg').write_text('\n'.join(common) + '\n')
    return base


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--exe', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--content', type=Path, default=Path('C:/FTESurf'))
    a = ap.parse_args()
    a.exe, a.out = a.exe.resolve(), a.out.resolve()   # the client runs from C:/FTESurf
    out = a.out / time.strftime('p1576-%Y%m%dT%H%M%S')
    out.mkdir(parents=True)
    print('exe', a.exe, hashlib.sha256(a.exe.read_bytes()).hexdigest()[:8], 'out', out, flush=True)
    base = prepare(a.content, out)
    cl = Client(a.exe, base, 'probe.cfg')
    results = []

    def check(ok, name, detail=''):
        results.append(ok)
        print(('PASS ' if ok else 'FAIL ') + name + (' -- ' + detail if detail else ''), flush=True)

    def read(name):
        m = cl.query(name, r'"%s" is "([^"]*)"' % name, timeout=10)
        return m.group(1)

    try:
        end = time.monotonic() + 90
        rdp = ''
        while time.monotonic() < end:
            time.sleep(2)
            rdp = read('in_rawinput_rdp')
            if rdp == '1':
                break
        check(rdp == '1', 'map lock ran (unprotected control cvar in_rawinput_rdp took the map value)', rdp)
        for name, want in (('in_rawinput_nolegacy', '1'), ('in_rawinput_touchpad', '0'), ('in_keyguard', '1'),
                           ('in_guard_live', '7')):
            got = read(name)
            check(got == want, '%s after a map setting it to %s' % (name, KEYS.get('cvar_' + name, '-')),
                  'read %r, want %r' % (got, want))
        cl.send('menu_restart')
        time.sleep(1.5)
        cl.send('ui_close')
        time.sleep(1)
        for phase, guard, arrive in ((1, '0', True), (2, '1', False), (3, '0', True)):
            cl.send('in_keyguard ' + guard)
            cl.send('bind k "echo P1576-ARRIVED-%d"' % phase)
            time.sleep(.8)
            live = read('in_guard_live')
            off = len(cl.text())
            cl.key(VK_K, settle=2.5)
            text = cl.text()[off:]
            got = ('P1576-ARRIVED-%d' % phase) in text
            check(got == arrive, 'phase %d in_keyguard %s: posted key %s' % (phase, guard,
                  'arrived' if got else 'dropped'), 'in_guard_live %s; want %s' % (live,
                  'arrived' if arrive else 'dropped'))
            for line in text.splitlines():
                if 'in_keyguard:' in line or 'dropped a key' in line:
                    print('     subject: ' + line.strip(), flush=True)
        cl.send('in_rawinput_nolegacy 0')
        time.sleep(.5)
        live = read('in_guard_live')
        check(live == '2', 'in_guard_live drops bit 1 with in_rawinput_nolegacy 0 (keyguard 0 from phase 3)', live)
        cl.send('in_rawinput_nolegacy 1')
    finally:
        cl.stop()
    print('log', cl.log)
    print('%d/%d checks passed' % (sum(results), len(results)))
    return 0 if all(results) else 1


if __name__ == '__main__':
    sys.exit(main())
