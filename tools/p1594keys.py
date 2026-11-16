#!/usr/bin/env python3
"""Patch 1594: the .hid's keytimes line, driven with posted key taps.

One windowed client on a fresh basedir opens a journal, receives N posted taps (WM_KEYDOWN then WM_KEYUP, no
keyboard behind them, in_keyguard 0 so they reach the game), and closes it. Each release then has no raw
release to pair with, so `keytimes` must count N releases alone and time no pair, and P1424's 'y' must count
the N presses. A rig cannot press a real key: the matched buckets are graded by the owner's own journals
(lextest), not here. --control with a pre-1594 build: no keytimes line. Run under the rig lock.
"""
import argparse
import hashlib
from pathlib import Path
import shutil
import subprocess
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parent))
from p762keys import Client  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--exe', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--content', type=Path, default=Path('C:/FTESurf'))
    ap.add_argument('--taps', type=int, default=10)
    ap.add_argument('--oldreader', type=Path, help='an older tools/hidcheck.py: must not fault the new line')
    ap.add_argument('--control', action='store_true', help='--exe is a pre-1594 build: no keytimes line expected')
    a = ap.parse_args()
    a.exe, a.out = a.exe.resolve(), a.out.resolve()
    out = a.out / time.strftime('p1594-%Y%m%dT%H%M%S')
    base = out / 'client'
    game = base / 'ftesurf'
    for folder in ('cfg', 'glsl', 'scripts', 'gfx/fonts', 'gfx/ui'):
        if (a.content / 'ftesurf' / folder).is_dir():
            shutil.copytree(a.content / 'ftesurf' / folder, game / folder)
    for folder in ('logs', 'data'):
        (game / folder).mkdir(parents=True, exist_ok=True)
    for leaf in ('qwprogs.dat', 'csprogs.dat', 'menu.dat'):
        shutil.copy2(a.content / 'ftesurf' / leaf, game / leaf)
    (base / 'default.fmf').write_text('FTEMANIFEST 1\nGAME FTESurfP1594Fixture\nBASEGAME ftesurf\n'
                                      'DISABLEHOMEDIR 1\nMAINCONFIG p1594cfg\n')
    (game / 'probe.cfg').write_text('\n'.join([
        'cfg_save_auto 0', 'con_savehistory 0', 'log_enable 1', 'log_dir logs', 'log_name probe',
        'log_readable 1', 'set cl_idlefps 0', 'set update_autocheck 0', 'set milk_enable 0']) + '\n')
    print('exe', a.exe, hashlib.sha256(a.exe.read_bytes()).hexdigest()[:8], 'out', out, flush=True)
    cl = Client(a.exe, base, 'probe.cfg')
    try:
        time.sleep(6)
        cl.send('in_journal_begin')
        time.sleep(1.0)
        for _ in range(a.taps):
            cl.key(0x57, settle=0.3)        # W: a down and an up, posted to the client's own window
        time.sleep(1.0)                     # past RAWKEY_WINDOW
        # A release waits for the next key or raw event to be decided (as P1424's presses do); real play
        # always has one.  A release of a key never pressed is that event, and is itself not judged.
        cl.post(0x51, 'up', settle=0.5)
        cl.send('in_journal_end data/p1594.hid')
        time.sleep(2.0)
    finally:
        cl.stop()
    results = []

    def check(ok, name, detail=''):
        results.append(ok)
        print(('PASS ' if ok else 'FAIL ') + name + (' -- ' + detail if detail else ''), flush=True)

    hid = game / 'data/p1594.hid'
    check(hid.exists(), 'journal written', str(hid))
    if not hid.exists():
        return 1
    lines = hid.read_text(encoding='utf-8', errors='replace').splitlines()
    kt = [l.split()[1:] for l in lines if l.startswith('keytimes ')]
    ys = sum(int(l.split()[2]) for l in lines if l.split()[:1] == ['y'] and len(l.split()) >= 3)  # y <dt> <keys> <nohandle>
    obs = [l for l in lines if l.startswith('kbdobserve ')]
    for l in [l for l in lines if l.startswith('keytimes') or l.startswith('kbdobserve')]:
        print('     subject: ' + l, flush=True)
    if a.control:
        check(not kt, 'control: no keytimes line', '%d' % len(kt))
    else:
        check(obs == ['kbdobserve 1'], 'the keyboard is observed', '%r' % obs)
        check(len(kt) == 1 and len(kt[0]) == 17, 'one keytimes line of 17 counts', '%r' % kt)
        if len(kt) == 1 and len(kt[0]) == 17:
            v = [int(x) for x in kt[0]]
            check(sum(v[0:16]) == 0, 'no pair timed (nothing pressed a real key)', '%r' % v[0:16])
            check(v[16] == a.taps, 'every posted release counted alone', '%d of %d' % (v[16], a.taps))
        print('     P1424 y presses: %d' % ys, flush=True)
    for label, reader in (('this tree', Path(__file__).resolve().parent / 'hidcheck.py'), ('older', a.oldreader)):
        if reader is None:
            continue
        p = subprocess.run([sys.executable, '-B', str(reader), '-v', str(hid)], capture_output=True, text=True)
        ok = p.returncode == 0 and ' 0 with faults' in p.stdout
        check(ok, 'hidcheck (%s) reads it with no fault' % label,
              p.stdout.strip().splitlines()[-1] if p.stdout else p.stderr[-200:])
        for l in p.stdout.splitlines():
            if 'keytimes' in l or 'release' in l:
                print('     reader: ' + l.strip(), flush=True)
    print('%d/%d checks passed' % (sum(results), len(results)))
    return 0 if all(results) else 1


if __name__ == '__main__':
    sys.exit(main())
