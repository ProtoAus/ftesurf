#!/usr/bin/env python3
"""Dedicated red/green controls for save-lock player map progress markers.

Use --out UNDER an owned task root. Content junctions are removed on exit;
synthetic state/logs remain for inspection. No canonical player data is used.
"""
import argparse
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent
BASELINE = 'bdab71288b4823f5c56ce6510422f86a774741e6'
MODULES = ('sv_entities.qc', 'sv_saveloc.qc', 'sv_rewindstate.qc')


def build(out, baseline):
    src = ROOT / 'src'
    out.mkdir(parents=True, exist_ok=True)
    lines = (src / 'sv_progs.src').read_text().splitlines()
    lines[0] = os.path.relpath(out / 'qwprogs.dat', src).replace('\\', '/')
    if baseline:
        for module in MODULES:
            data = subprocess.check_output(['git', '-C', str(ROOT), 'show',
                                            f'{BASELINE}:src/server/{module}'])
            (out / module).write_bytes(data)
        for module in MODULES:
            old = 'server/' + module
            if old in lines:
                lines[lines.index(old)] = os.path.relpath(out / module, src).replace('\\', '/')
    idx = lines.index('server/sv_player.qc')
    lines.insert(idx, '../tools/fixtures/savemarker_begin.qc')
    lines.append('../tools/fixtures/savemarker.qc')
    listing = src / 'p735savemarker.src'
    if listing.exists():
        raise RuntimeError('Fixture manifest already exists; do not overwrite it')
    listing.write_text('\n'.join(lines) + '\n')
    try:
        result = subprocess.run([str(src / 'fteqcc64.exe'), '-srcfile', listing.name],
                                cwd=src, capture_output=True)
        text = (result.stdout + result.stderr).decode(errors='replace')
        (out / 'compile.log').write_text(text)
        if result.returncode or 'Done. 0 warnings' not in text or re.search(r': (warning|error)', text, re.I):
            raise RuntimeError(f'Fixture compile failed/warned ({result.returncode}); see {out / "compile.log"}')
    finally:
        listing.unlink()


def bridge(name, *args):
    p = subprocess.run([sys.executable, str(ROOT / 'tools/conbridge.py'), '--name', name, *args],
                       capture_output=True, text=True, encoding='utf-8', errors='replace')
    if p.returncode:
        raise RuntimeError('conbridge ' + args[0] + ': ' + p.stdout + p.stderr)
    return p.stdout


def run(out, progs, baseline, port, client, server):
    rig = out / 'runtime'
    if rig.exists():
        raise RuntimeError('Use a fresh output directory: never reuse mutable evidence')
    gd = rig / 'ftesurf'; gd.mkdir(parents=True)
    shutil.copy2(ROOT / 'default.fmf', rig / 'default.fmf')
    shutil.copy2(ROOT / 'ftesurf/fs_addons.default.txt', gd)
    # Match the shipped startup contract: cfg/default.cfg loads the VBSP plugin
    # and movement defaults. Do not copy ignored owner configs or credentials.
    configs = subprocess.check_output(['git', '-C', str(ROOT), 'ls-files', 'ftesurf/cfg'], text=True).splitlines()
    for config in configs:
        if '/test/' in config:
            continue
        dest = rig / config
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / config, dest)
    shutil.copy2(server.parent / 'fteplug_hl2_x64.dll', rig / 'fteplug_hl2_x64.dll')
    for p in ('csprogs.dat', 'menu.dat'):
        shutil.copy2(progs / p, gd / p)
    shutil.copy2(out / 'qwprogs.dat', gd / 'qwprogs.dat')
    (gd / 'downloads/csprogsvers').mkdir(parents=True)
    subprocess.run([sys.executable, str(ROOT / 'tools/seed_csprogs.py'), str(gd / 'csprogs.dat')],
                   check=True, capture_output=True)
    links = []
    name = 'p735-control' if baseline else 'p735-subject'
    started = False
    try:
        for content in ('maps', 'gfx', 'glsl', 'models', 'particles', 'scripts'):
            link = gd / content
            subprocess.run(['cmd', '/c', 'mklink', '/J', str(link), str(Path('C:/FTESurf/ftesurf') / content)],
                           check=True, capture_output=True)
            links.append(link)
        text = bridge(name, 'start', '--root', str(rig), '--client', str(client), '--server', str(server),
                      '--map', 'surf_dune', '--port', str(port), '--size', '640x480',
                      '--server-args=+set rec_stream 0 +set sv_cheats 1',
                      '--client-args=+set cfg_save_auto 0 +set cl_idlefps 0 +set cl_maxfps 100')
        (out / 'start.log').write_text(text)
        started = True
        bridge(name, 'send', 'say !m', '--read', '2.5')
        bridge(name, 'send', '+forward', '--read', '1.1')
        bridge(name, 'send', '--read', '0.2', '--', '-forward')
        bridge(name, 'send', 'cmd p735_savemarker', '--wait', 'SAVEMARKER COMPLETE', '--on-sv', '--timeout', '30')
        bridge(name, 'send', 'cmd p735_retry', '--wait', 'SAVEMARKER COLD COMPLETE', '--on-sv', '--timeout', '25')
        text = bridge(name, 'log', '--sv', '--all', '--limit', '2000')
        (out / 'server.log').write_text(text)
        for bad in ('SV_Error:', 'Host_Error:', 'runaway loop', 'QC VM error', 'Unknown command', 'stack overflow'):
            if bad in text:
                raise RuntimeError('Runtime fault: ' + bad)
        matches = re.findall(r'SAVEMARKER COMPLETE checks=(\d+) failed=(\d+)', text)
        if len(matches) != 1:
            raise RuntimeError('Exactly one completed acting fixture required')
        checks, failed = map(int, matches[0])
        if checks < 40:
            raise RuntimeError('Fixture did not exercise all controls')
        cold = re.findall(r'SAVEMARKER COLD COMPLETE restarted=(\d+) failed=(\d+)', text)
        if 'SAVEMARKER RETRY ACTOR sent=1' not in text or cold != [('1', '1' if baseline else '0')]:
            raise RuntimeError('Actual retry/map restart marker control failed to act as expected: ' + str(cold))
        failures = re.findall(r'SAVEMARKER FAIL ([^\r\n]+)', text)
        if baseline:
            required = ('ordinary load restores earlier progress',
                        'recorded rewind uses sampled not present marker',
                        'empty marker clears later progress',
                        'stale EndTouch cannot overwrite restored marker')
            if not failed or any(x not in failures for x in required):
                raise RuntimeError('Baseline did not falsify the required changed behaviors')
            print(f'PASS baseline detector: {failed}/{checks} expected assertion failures')
        elif failed:
            raise RuntimeError(f'{failed}/{checks} assertions failed: {failures}')
        else:
            print(f'PASS dedicated subject: {checks} assertions, 0 failed; real retry/map restart 1/0')
        for failure in failures:
            print('  baseline failure:', failure)
    finally:
        if started:
            bridge(name, 'stop')
        for link in links:
            if not (link.lstat().st_file_attributes & 0x400):
                raise RuntimeError('Expected content junction: ' + str(link))
            link.rmdir()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--out', required=True, type=Path)
    p.add_argument('--baseline', action='store_true')
    p.add_argument('--run', action='store_true')
    p.add_argument('--progs', type=Path)
    p.add_argument('--port', type=int, default=27557)
    p.add_argument('--client', type=Path, default=Path('C:/FTESurf/ftesurf64.exe'))
    p.add_argument('--server', type=Path, default=Path('C:/FTEQuake/fteqwsv64.exe'))
    a = p.parse_args()
    if not 27520 <= a.port <= 27620:
        p.error('Use a dedicated lobby-range test port')
    out = a.out.resolve()
    build(out, a.baseline)
    print('PASS zero-warning fixture build:', 'baseline' if a.baseline else 'subject')
    if a.run:
        if not a.progs:
            p.error('--run needs --progs')
        run(out, a.progs.resolve(), a.baseline, a.port, a.client, a.server)


if __name__ == '__main__':
    main()
