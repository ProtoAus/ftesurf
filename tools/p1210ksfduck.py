#!/usr/bin/env python3
"""P1210: KSF imports' inferred ducked body, Python converter against the in-game loader.

For each KSF CSS/66t replay in --replays (names `<map>__replay_*` main, `<map>__z3K__replay_*`
bonus K), tools/ksfconvert.py converts it and counts DUCKED samples; one owned listen client
loads each map, opens the same file through `replay ksf` (cl_ksf.qc's KSF_BufLoad) and reads
`replay duckcount`. Per file the sample and ducked counts must be equal; files the converter
refuses are reported, and must be refused in game too. Read-only on --replays (copied into the
overlay). --out must be fresh and beneath an owned task root; --progs holds the three .dat files.
"""
import argparse
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import ksfconvert as C  # noqa: E402
import p1197snap as S  # noqa: E402


def course(name):
    m = re.match(r'([a-z0-9_]+?)__(?:z(\d+)__)?replay_', name)
    return (m.group(1), int(m.group(2)) - 30 if m.group(2) else 0) if m else (None, None)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--progs', type=Path, required=True)
    ap.add_argument('--replays', type=Path, action='append', required=True)
    ap.add_argument('--client', type=Path, default=Path('C:/FTESurf/ftesurf64.exe'))
    a = ap.parse_args()
    a.out = a.out.resolve()
    if not any((p / 'OWNER.md').is_file() for p in a.out.parents):
        ap.error('--out must be beneath an owned task root')
    a.out.mkdir(parents=True, exist_ok=False)
    jobs = []
    for d in a.replays:
        for f in sorted(d.glob('*.rec')):
            m, bonus = course(f.name)
            if not m or not (S.MAPS / f'{m}.bsp').is_file():
                continue
            try:
                text, info = C.convert(f.read_bytes(), m, bonus, 'FW')
                samples = [s.split() for s in text.splitlines() if s[:1].isdigit() or s[:1] == '-']
                py = (len(samples), sum(1 for s in samples if int(s[9]) & 2), info['duck_holds'])
            except ValueError as e:
                py = ('refused', str(e)[:60])
            jobs.append(dict(file=f.name, src=str(f), map=m, bonus=bonus, py=py))
    base = a.out / 'client'
    game = base / 'ftesurf'
    for folder in ('cfg', 'maps', 'logs', 'data/ksfcheck'):
        (game / folder).mkdir(parents=True, exist_ok=True)
    for leaf in ('qwprogs.dat', 'csprogs.dat', 'menu.dat'):
        shutil.copy2(a.progs / leaf, game / leaf)
    shutil.copy2(S.ROOT / 'ftesurf/cfg/default.cfg', game / 'cfg/default.cfg')
    shutil.copytree(S.ROOT / 'ftesurf/scripts', game / 'scripts')
    maps = sorted({j['map'] for j in jobs})
    for m in maps:
        shutil.copy2(S.MAPS / f'{m}.bsp', game / f'maps/{m}.bsp')
    for j in jobs:
        shutil.copy2(j['src'], game / 'data/ksfcheck' / j['file'])
    (base / 'default.fmf').write_text('FTEMANIFEST 1\nGAME FTESurfKsfDuck\nBASEGAME ftesurf\n'
                                      'DISABLEHOMEDIR 1\nMAINCONFIG duck-unused\n')
    subprocess.run(['python', str(S.ROOT / 'tools/seed_csprogs.py'), str(game / 'csprogs.dat')],
                   check=True, capture_output=True)
    common = ['cfg_save_auto 0', 'con_savehistory 0', 'log_enable 1', 'log_dir logs', 'log_name probe',
              'log_readable 1', 'set cl_idlefps 0', 'set cl_maxfps 60', 'set run_resume 0', 'set lobby_dir ""',
              'set lobby_master ""', 'set lobby_enable 0', 'set cl_run_upload 0', 'set cl_board_url ""',
              'set sv_public 0', 'cl_threadedphysics 0', 'name Duck']
    (game / 'probe.cfg').write_text('\n'.join(common) + '\n')
    cl = S.Client(a.client, base, 'probe.cfg')
    try:
        time.sleep(3)
        for m in maps:
            off = len(cl.text())
            cl.send(f'map {m}')
            cl.wait(r'VBSP: maps/' + re.escape(m) + r'\.bsp', off, timeout=180)
            end = time.monotonic() + 120
            while True:                 # then CSQC is up when its replay command answers
                try:
                    cl.query('replay duckcount', r'replay: duckcount samples', timeout=4)
                    break
                except RuntimeError:
                    if time.monotonic() > end or cl.proc.poll() is not None:
                        raise RuntimeError(f'{m} never came up')
            time.sleep(2)
            for j in (j for j in jobs if j['map'] == m):
                off = len(cl.text())
                cl.send('replay stop')
                cl.send(f"replay ksf data/ksfcheck/{j['file']} {m} {j['bonus']} FW")
                g = cl.query('replay duckcount', r'replay: duckcount samples (\d+) ducked (\d+) source (\S*)')
                j['game'] = (int(g.group(1)), int(g.group(2)), g.group(3))
                j['game_refused'] = 'refused' in cl.text()[off:] or g.group(3) != 'ksf'
            print(m, 'done', flush=True)
    finally:
        cl.stop()
        (a.out / 'report.json').write_text(json.dumps(jobs, indent=1))
    same = refused_both = bad = 0
    for j in jobs:
        if j['py'][0] == 'refused':
            ok = j.get('game_refused', False)
            refused_both += ok
        else:
            ok = not j.get('game_refused', True) and j['game'][:2] == j['py'][:2]
            same += ok
        if not ok:
            bad += 1
            print('MISMATCH', j['file'], 'py', j['py'], 'game', j.get('game'), 'refused', j.get('game_refused'))
    held = sum(j['py'][2] for j in jobs if j['py'][0] != 'refused')
    print(f'{same} files equal (holds {held}), {refused_both} refused by both, {bad} mismatched, of {len(jobs)}')
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
