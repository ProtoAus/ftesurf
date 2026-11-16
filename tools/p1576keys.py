#!/usr/bin/env python3
"""Patch 1576: keys other programs send are dropped (in_keyguard) and in_guard_live says what applies.

One windowed listen-server client on a generated box map. Keys are WM_KEYDOWN/UP posted to our own
client's window (p762keys.Client; never focus, never the owner's input), which Windows reports as a
posted message, not hardware. No hardware key ever reaches this client, so the session fallback
("every key so far came from another program") is reached on purpose at the end. Graded on the
subject's own lines: the bind's echo, cvar reads and the engine's Input: lines. The map lock refusal
is p1573guard.py --latch --live (a real map's entities; a generated .map sets no cvar_ keys).

--exe C:/FTESurf/ftesurf64.exe (a pre-1576 build) is the control: in_keyguard is unknown there and
the posted key arrives in every phase.
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
    (game / f'maps/{MAP}.map').write_text(make_map())
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

    def bind(tag):
        cl.send('bind k "echo P1576-ARRIVED-%s"' % tag)
        time.sleep(.3)

    def tap(settle=2.5):
        off = len(cl.text())
        cl.key(VK_K, settle=settle)
        return off

    def arrived(off, tag):
        return ('P1576-ARRIVED-%s' % tag) in cl.text()[off:]

    def subject(off):
        for line in cl.text()[off:].splitlines():
            if 'in_keyguard:' in line or 'Input: ' in line:
                print('     subject: ' + line.strip(), flush=True)

    try:
        end = time.monotonic() + 90
        while time.monotonic() < end:
            time.sleep(2)
            try:
                read('in_guard_live')
                break
            except RuntimeError:
                pass
        cl.send('in_keyguard 1')        # p762keys' launcher turns it off for its own arms
        time.sleep(1.5)
        for name, want in (('in_rawinput_nolegacy', '1'), ('in_rawinput_touchpad', '0'), ('in_guard_live', '7')):
            got = read(name)
            check(got == want, 'engine default %s' % name, 'read %r, want %r' % (got, want))
        cl.send('menu_restart')
        time.sleep(1.5)
        cl.send('ui_close')
        time.sleep(1)
        for phase, guard, arrive in ((1, '0', True), (2, '1', False), (3, '0', True)):
            cl.send('in_keyguard ' + guard)
            bind(phase)
            time.sleep(1.5)             # past GUARD_WEAKEN_DELAY
            live = read('in_guard_live')
            off = tap()
            got = arrived(off, phase)
            check(got == arrive, 'phase %d in_keyguard %s: posted key %s' % (phase, guard, 'arrived' if got else 'dropped'),
                  'in_guard_live %s; want %s' % (live, 'arrived' if arrive else 'dropped'))
            subject(off)
        # Switched off: published at once, still applied for the delay, then applied.
        cl.send('in_keyguard 1')
        bind('W1')
        time.sleep(1.5)
        cl.send('in_keyguard 0')
        time.sleep(.15)
        live = read('in_guard_live')
        off = tap(settle=.4)
        check(live == '3' and not arrived(off, 'W1'), 'just switched off: in_guard_live says so at once, the key is still dropped',
              'in_guard_live %s, arrived %s' % (live, arrived(off, 'W1')))
        bind('W2')
        time.sleep(1.5)
        off = tap()
        check(arrived(off, 'W2'), 'after the delay the switch-off applies')
        # A release of a held key passes (nothing sticks), and bit 4 drops out for a moment.
        bind('H')
        off = len(cl.text())
        cl.post(VK_K, 'down', settle=.6)
        cl.send('in_keyguard 1')
        time.sleep(.3)
        cl.post(VK_K, 'up', settle=.05)
        now_live = read('in_guard_live')
        time.sleep(2.0)
        after_live = read('in_guard_live')
        check(arrived(off, 'H') and now_live == '3' and after_live == '7',
              'held key: its injected release passes and in_guard_live loses 4, then gets it back',
              'pressed %s, in_guard_live %s then %s' % (arrived(off, 'H'), now_live, after_live))
        # What defeats a guard is read from what runs: the rdp setting changes nothing without a
        # Remote Desktop device bound (none here); DirectInput takes over at in_restart.
        cl.send('in_rawinput_rdp 1')
        time.sleep(.5)
        got = read('in_guard_live')
        cl.send('in_rawinput_rdp 0')
        check(got == '7', 'in_rawinput_rdp 1 with no RDP device bound: in_guard_live 7', 'read %s' % got)
        # DirectInput is not exercised: `in_dinput 1` kills the client at input init (0xC0000374) on the
        # installed engine as well (BACKLOG), so INS_GuardPublish's `dinput` case cannot be reached here.
        a = read('in_guard_lapses')
        b = read('in_guard_lapses')
        check(a.isdigit() and b.isdigit() and int(b) > int(a),
              'a console command from another program (this driver\'s stdin) is a lapse', '%s then %s' % (a, b))
        # No hardware key on the rig: the 8th dropped message stops the dropping for the session.
        bind('S')
        off = len(cl.text())
        cl.key(VK_K, settle=.4)
        cl.key(VK_K, settle=1.0)
        said = 'every key so far came from another program' in cl.text()[off:]
        live = read('in_guard_live')
        bind('S2')
        off2 = tap()
        check(said and live == '10' and arrived(off2, 'S2'),
              'no hardware key and 8 drops: dropping stops, in_guard_live 10 (clicks and keys cannot run), keys arrive',
              'said %s, in_guard_live %s, arrived %s' % (said, live, arrived(off2, 'S2')))
        subject(off)
        cl.send('in_rawinput_nolegacy 0')
        time.sleep(.5)
        live = read('in_guard_live')
        check(live == '10', 'in_rawinput_nolegacy 0 after the fallback: still 10', live)
        cl.send('in_rawinput_nolegacy 1')
    finally:
        cl.stop()
    print('log', cl.log)
    print('%d/%d checks passed' % (sum(results), len(results)))
    return 0 if all(results) else 1


if __name__ == '__main__':
    sys.exit(main())
