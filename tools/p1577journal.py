#!/usr/bin/env python3
"""Patch 1577: the .hid names modules from outside the game and Windows folders.

One windowed client on a fresh basedir (no server, no map) opens a developer journal, closes it and
quits. Graded on the file: one `modules <n>` header with n `module <class> <file>` lines, file names
only, and hidcheck -- this tree's and, with --oldreader, an older one -- reading it with no fault.
`module+` (loaded during the journal) is exercised by test_hidcheck's case_modules_tripwire; this arm
loads nothing into the client. --control with a pre-1577 build: no module lines at all.
Run under the rig lock.
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
    ap.add_argument('--oldreader', type=Path, help='an older tools/hidcheck.py: must not fault the new lines')
    ap.add_argument('--control', action='store_true', help='--exe is a pre-1577 build: no module lines expected')
    a = ap.parse_args()
    a.exe, a.out = a.exe.resolve(), a.out.resolve()
    out = a.out / time.strftime('p1577-%Y%m%dT%H%M%S')
    base = out / 'client'
    game = base / 'ftesurf'
    for folder in ('cfg', 'glsl', 'scripts', 'gfx/fonts', 'gfx/ui'):
        if (a.content / 'ftesurf' / folder).is_dir():
            shutil.copytree(a.content / 'ftesurf' / folder, game / folder)
    for folder in ('logs', 'data'):
        (game / folder).mkdir(parents=True, exist_ok=True)
    for leaf in ('qwprogs.dat', 'csprogs.dat', 'menu.dat'):
        shutil.copy2(a.content / 'ftesurf' / leaf, game / leaf)
    (base / 'default.fmf').write_text('FTEMANIFEST 1\nGAME FTESurfP1577Fixture\nBASEGAME ftesurf\n'
                                      'DISABLEHOMEDIR 1\nMAINCONFIG p1577cfg\n')
    (game / 'probe.cfg').write_text('\n'.join([
        'cfg_save_auto 0', 'con_savehistory 0', 'log_enable 1', 'log_dir logs', 'log_name probe',
        'log_readable 1', 'set cl_idlefps 0', 'set update_autocheck 0', 'set milk_enable 0']) + '\n')
    print('exe', a.exe, hashlib.sha256(a.exe.read_bytes()).hexdigest()[:8], 'out', out, flush=True)
    cl = Client(a.exe, base, 'probe.cfg')
    try:
        time.sleep(6)
        cl.send('in_journal_begin')
        time.sleep(1.0)
        cl.send('in_journal_note p1577')
        time.sleep(0.5)
        cl.send('in_journal_end data/p1577.hid')
        time.sleep(1.5)
    finally:
        cl.stop()
    hid = game / 'data/p1577.hid'
    results = []

    def check(ok, name, detail=''):
        results.append(ok)
        print(('PASS ' if ok else 'FAIL ') + name + (' -- ' + detail if detail else ''), flush=True)

    check(hid.exists(), 'journal written', str(hid))
    if not hid.exists():
        return 1
    lines = hid.read_text(encoding='utf-8', errors='replace').splitlines()
    head = lines[:lines.index('begin')] if 'begin' in lines else lines
    counts = [l for l in head if l.startswith('modules ')]
    mods = [l for l in head if l.startswith('module ')]
    late = [l for l in lines if l.startswith('module+ ')]
    if a.control:
        check(not counts and not mods and not late, 'control: no module lines', '%d/%d/%d' % (len(counts), len(mods), len(late)))
    else:
        n = int(counts[0].split()[1]) if counts else None
        check(len(counts) == 1 and n is not None and n >= 0 and n == len(mods),
              'header: modules <n> with n module lines', 'counts %r, %d named' % (counts, len(mods)))
        for l in mods + late:
            print('     subject: ' + l, flush=True)
        check(all(len(l.split()) == 3 and l.split()[1] in ('program', 'user', 'other') for l in mods + late),
              'every module line is <class> <file>')
        check(not any(':' in l or '\\' in l for l in mods + late), 'no paths, file names only')
    for label, reader in (('this tree', Path(__file__).resolve().parent / 'hidcheck.py'), ('older', a.oldreader)):
        if reader is None:
            continue
        p = subprocess.run([sys.executable, '-B', str(reader), '-v', str(hid)], capture_output=True, text=True)
        ok = p.returncode == 0 and ' 0 with faults' in p.stdout
        check(ok, 'hidcheck (%s) reads it with no fault' % label, p.stdout.strip().splitlines()[-1] if p.stdout else p.stderr[-200:])
        for l in p.stdout.splitlines():
            if 'module' in l.lower():
                print('     reader: ' + l.strip(), flush=True)
    print('%d/%d checks passed' % (sum(results), len(results)))
    return 0 if all(results) else 1


if __name__ == '__main__':
    sys.exit(main())
