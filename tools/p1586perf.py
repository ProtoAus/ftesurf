#!/usr/bin/env python3
"""Patch 1586: does the hook scan's worker cost the game's frames?

One windowed client at a fixed frame cap opens a journal, holds it 40 s (scans 0.5-2.5 s in, then every
10-20 s) and dumps r_frametime (exact tails and the slowest frames with how long ago). Runs alternate the
P1586 exe and a control without the scan, A B B A. r_frametime_dump overwrites the clipboard: the owner's
text is saved before and restored after each dump, and the run refuses if the clipboard holds anything but
text. Run under the rig lock.
"""
import argparse
import hashlib
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parent))
from p762keys import Client  # noqa: E402


def ps(cmd):
    return subprocess.run(['powershell', '-NoProfile', '-STA', '-Command', 'Add-Type -AssemblyName System.Windows.Forms; ' + cmd],
                          capture_output=True, text=True).stdout.strip()


def clip_save(path):
    kind = ps("$d=[Windows.Forms.Clipboard]::GetDataObject(); if ($d -eq $null -or $d.GetFormats().Count -eq 0) {'empty'} "
              "elseif ([Windows.Forms.Clipboard]::ContainsText() -and -not ([Windows.Forms.Clipboard]::ContainsImage() -or "
              "[Windows.Forms.Clipboard]::ContainsFileDropList())) {[IO.File]::WriteAllText('%s', [Windows.Forms.Clipboard]::GetText(), "
              "[Text.UTF8Encoding]::new($false)); 'text'} else {'other'}" % path)
    return kind


def clip_restore(path, kind):
    if kind == 'empty':
        return ps("[Windows.Forms.Clipboard]::Clear(); 'cleared'")
    return ps("$t=[IO.File]::ReadAllText('%s', [Text.UTF8Encoding]::new($false)); [Windows.Forms.Clipboard]::SetText($t); "
              "if ([Windows.Forms.Clipboard]::GetText() -eq $t) {'restored'} else {'MISMATCH'}" % path)


def one(exe, content, out, label, clip):
    base = out / label / 'client'
    game = base / 'ftesurf'
    for folder in ('cfg', 'glsl', 'scripts', 'gfx/fonts', 'gfx/ui'):
        if (content / 'ftesurf' / folder).is_dir():
            shutil.copytree(content / 'ftesurf' / folder, game / folder)
    for folder in ('logs', 'data'):
        (game / folder).mkdir(parents=True, exist_ok=True)
    for leaf in ('qwprogs.dat', 'csprogs.dat', 'menu.dat'):
        shutil.copy2(content / 'ftesurf' / leaf, game / leaf)
    (base / 'default.fmf').write_text('FTEMANIFEST 1\nGAME FTESurfP1586Perf\nBASEGAME ftesurf\nDISABLEHOMEDIR 1\nMAINCONFIG p1586cfg\n')
    (game / 'probe.cfg').write_text('\n'.join([
        'cfg_save_auto 0', 'con_savehistory 0', 'log_enable 1', 'log_dir logs', 'log_name probe', 'log_readable 1',
        'set cl_idlefps 0', 'set cl_maxfps 400', 'set update_autocheck 0', 'set milk_enable 0', 'set log_developer 1',
        'set r_frametime 1', 'set r_frametime_window 120']) + '\n')
    cl = Client(exe, base, 'probe.cfg')
    try:
        time.sleep(8)
        cl.send('in_journal_begin')
        cl.send('r_frametime_reset')
        time.sleep(40)
        kind = clip_save(clip)
        if kind not in ('text', 'empty'):
            raise SystemExit('the clipboard holds more than text: not dumping over it')
        off = len(cl.text())
        cl.send('r_frametime_dump')
        cl.wait(r'slowest frames', off, 15)
        time.sleep(0.5)
        print('     clipboard', kind, '->', clip_restore(clip, kind), flush=True)
        cl.send('in_journal_end data/perf.hid')
        time.sleep(2)
        text = cl.text()[off:]
    finally:
        cl.stop()
        Path(clip).unlink(missing_ok=True)
    m = re.search(r'avg ([\d.]+) ms .*?1% tail mean ([\d.]+) ms .*?0\.1% tail mean ([\d.]+) ms', text)
    st = re.search(r'stutters \(over [\d.]+x the median, ([\d.]+) ms\): (\d+)', text)
    scans = re.search(r'hook scans: (\d+), the last ([\d.]+) ms', text)
    slow = re.findall(r'\s([\d.]+)\s+([\d.]+) s ago', text)[:5]
    print('%-8s avg %s  1%% %s  0.1%% %s ms; stutters %s over %s ms; scans %s; slowest (ms, s ago) %s' % (
        label, m.group(1) if m else '?', m.group(2) if m else '?', m.group(3) if m else '?',
        st.group(2) if st else '?', st.group(1) if st else '?',
        '%s (last %s ms)' % scans.groups() if scans else 'none', slow), flush=True)
    return text


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--exe', type=Path, required=True, help='the P1586 build')
    ap.add_argument('--control', type=Path, required=True, help='a build without the scan')
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--content', type=Path, default=Path('C:/FTESurf'))
    a = ap.parse_args()
    out = a.out.resolve() / time.strftime('p1586perf-%Y%m%dT%H%M%S')
    clip = str(out / 'clip.txt')
    out.mkdir(parents=True)
    for p in (a.exe, a.control):
        print('exe', p, hashlib.sha256(p.read_bytes()).hexdigest()[:8], flush=True)
    for i, (label, exe) in enumerate((('scan1', a.exe), ('control1', a.control), ('control2', a.control), ('scan2', a.exe))):
        (out / label / 'dump.txt').parent.mkdir(parents=True, exist_ok=True)
        text = one(exe.resolve(), a.content, out, label, clip)
        (out / label / 'dump.txt').write_text(text, encoding='utf-8')
    return 0


if __name__ == '__main__':
    sys.exit(main())
