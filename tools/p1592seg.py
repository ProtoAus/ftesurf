#!/usr/bin/env python3
"""P1592 arm: the file a resumed (segmented) run's finish writes, on a given engine + progs.

    python -B tools/p1592seg.py --out <dir under an OWNER.md root> --exe <client exe> --plugin <its hl2 dll>
                                --progs <dir with qwprogs/csprogs/menu.dat> [--held] [--label X]

A listen server on surf_dune's end room: the main start box in its corner and the end shrunk to a box
~450 u along yaw 55, so a straight walk is a run. Walk out (the run starts), sl_save while moving, stop,
tap the load (the run resumes from the save with its clock: TF_SHADOW|TF_SEGMENT), walk into the end.
--held turns on the held recording producer (sv_held_staging outside the game dirs, rec_held_metadata 1,
terms 9 -> 8), so the finish goes through the engine's held close (Held_PrepareCloseNamespace).
Graded from the subject's own output: the finish chat line, `cmd timer` before the finish, and the
files under data/runs/surf_dune/main/ with their header flags. Needs the rig lock; announce to peers.
"""
import argparse
import hashlib
import json
import re
import shutil
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import p840clock as R  # noqa: E402  take_lock/drop_lock/free_mb/owned
from spec_chat_smoke import Peer  # noqa: E402

CONTENT = Path('C:/FTESurf')
MAP = 'surf_dune'
BOX = (11500, 11600, 11080, 11180)   # start box in the end room's corner (P1384's)
END = (11800, 11950, 11500, 11700)   # the end, ~450 u along yaw 55 from O
O = (11550.0, 11130.0, 12914.0)


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()[:16]


def prepare(base, progs, plugin):
    game = base / 'ftesurf'
    for folder in ('glsl', 'scripts', 'models', 'particles'):
        if (CONTENT / 'ftesurf' / folder).is_dir():
            shutil.copytree(CONTENT / 'ftesurf' / folder, game / folder)
    for folder in ('fonts', 'ui'):
        if (CONTENT / 'ftesurf/gfx' / folder).is_dir():
            shutil.copytree(CONTENT / 'ftesurf/gfx' / folder, game / 'gfx' / folder)
    for folder in ('cfg', 'maps/zones/local', 'logs', 'data', 'downloads/csprogsvers'):
        (game / folder).mkdir(parents=True)
    (game / 'data/consent.txt').write_text('version 4\n')
    shutil.copy2(CONTENT / f'ftesurf/maps/{MAP}.bsp', game / f'maps/{MAP}.bsp')
    z = json.loads((CONTENT / f'ftesurf/maps/zones/local/{MAP}.json').read_text(encoding='utf-8'))
    main = z['tracks']['main']['zones']
    seg = main['segments'][0]
    seg['limitStartGroundSpeed'] = False
    reg = seg['checkpoints'][0]['regions'][0]
    reg['points'] = [[BOX[0], BOX[2]], [BOX[0], BOX[3]], [BOX[1], BOX[3]], [BOX[1], BOX[2]]]
    reg['bottom'], reg['height'] = 12912, 200
    reg.pop('teleDestTargetname', None)
    end = main['end']['regions'][0]
    end['points'] = [[END[0], END[2]], [END[0], END[3]], [END[1], END[3]], [END[1], END[2]]]
    end['bottom'], end['height'] = 12912, 200
    main['end']['regions'] = [end]
    main['segments'] = [seg]
    z['tracks'] = {'main': z['tracks']['main']}
    (game / f'maps/zones/local/{MAP}.json').write_text(json.dumps(z), encoding='utf-8')
    for leaf in ('qwprogs.dat', 'csprogs.dat', 'menu.dat'):
        shutil.copy2(progs / leaf, game / leaf)
    shutil.copy2(CONTENT / 'ftesurf/cfg/default.cfg', game / 'cfg/default.cfg')
    shutil.copy2(plugin, base / 'fteplug_hl2_x64.dll')
    (base / 'default.fmf').write_text(
        'FTEMANIFEST 1\nGAME FTESurfP1592Fixture\nBASEGAME ftesurf\n'
        'DISABLEHOMEDIR 1\nMAINCONFIG p1592-unused\n'
        'set sv_mintic 0.015\nset sv_maxtic 0.015\nset cl_netfps 66.6667\n')
    return game


def header_flags(path):
    head = path.read_bytes()[:4096].decode('utf-8', 'replace')
    m = re.search(r'^flags (\d+)', head, re.M)
    return int(m.group(1)) if m else None


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--exe', type=Path, required=True)
    ap.add_argument('--plugin', type=Path, required=True)
    ap.add_argument('--progs', type=Path, required=True)
    ap.add_argument('--held', action='store_true')
    ap.add_argument('--label', default='arm')
    a = ap.parse_args()
    a.out = a.out.resolve()
    R.owned(a.out)
    a.out.mkdir(parents=True, exist_ok=False)
    phys, commit = R.free_mb()
    print('free physical %d MB, commit %d MB' % (phys, commit), flush=True)
    if phys < 1500 or commit < 2200:
        raise SystemExit('not enough free memory')
    report = {'label': a.label, 'exe': sha(a.exe), 'plugin': sha(a.plugin), 'held': a.held,
              'qwprogs': sha(a.progs / 'qwprogs.dat'), 'csprogs': sha(a.progs / 'csprogs.dat')}
    print('hashes', report, flush=True)
    base = a.out / 'game'
    game = prepare(base, a.progs, a.plugin)
    stage = a.out / 'heldstage'          # outside every game dir of this rig
    lines = ['cfg_save_auto 0', 'con_savehistory 0', 'log_enable 1', 'log_dir logs', 'log_name probe',
             'log_readable 1', 'developer 0', 'set cl_idlefps 0', 'set cl_maxfps 100', 'set run_resume 0',
             'set lobby_dir ""', 'set lobby_master ""', 'set cl_run_upload 0', 'set cl_board_url ""',
             'set sv_public 0', 'set milk_enable 0', 'set update_autocheck 0', 'name "P1592Arm"',
             'set rec_terms 9', 'set rec_upload 1', 'set rec_enable 1']
    if a.held:
        stage.mkdir()
        lines += ['set sv_held_staging "%s"' % stage.as_posix(), 'set rec_held_metadata 1']
    lines += [f'map {MAP}']
    (game / 'probe.cfg').write_text('\n'.join(lines) + '\n')
    R.take_lock(f'p1592seg {a.label} (ftesurf-63 fork)')
    cl = None
    try:
        cl = Peer(a.exe, base, 'probe.cfg')
        cl.wait('FTESurf CSQC loaded', timeout=180)
        time.sleep(4)
        for line in ('menu_restart; ui_close', 'set rec_terms 9', 'cl_sl_leadin 0', 'cl_forwardspeed 200',
                     'rec_savelock 1'):
            cl.send(line)
            time.sleep(0.3)
        time.sleep(1.5)
        off = len(cl.text())
        cl.send('cmd timer')
        time.sleep(1.0)
        report['timer_idle'] = cl.text()[off:]
        cl.send(f'setpos {O[0]} {O[1]} {O[2]} 0 55 0')
        time.sleep(2.0)
        off = len(cl.text())
        cl.send('echo P1592 MARK run')
        cl.send('+forward')                  # out of the box: the run starts
        time.sleep(1.0)
        cl.send('sl_save')                   # moving, on the run
        time.sleep(0.3)
        cl.send('-forward')
        time.sleep(1.5)
        cl.send('+sl_hold 50;-sl_hold 50')   # tap the load: the run resumes from the save
        time.sleep(1.5)
        cl.send('cmd timer')
        time.sleep(1.0)
        cl.send('+forward')
        time.sleep(4.0)
        cl.send('-forward')
        time.sleep(3.0)
        cl.send('cmd timer')
        time.sleep(1.5)
        seg = cl.text()[off:]
        (a.out / 'run.log').write_text(seg, encoding='utf-8')
        report['resumed_line'] = (re.search(r'run resumed at [^\n]*', seg) or [None])[0]
        report['resumed_field'] = re.findall(r'(?:resumed|shadow) (\d+)\s+from save (\d+)', seg)
        report['finish_lines'] = [l for l in seg.splitlines()
                                  if re.search(r'from save \d+ -- not saved|segmented run|shadow run|finished|'
                                               r'practice --|not kept|held|refus', l, re.I)][:20]
        report['metadata_lines'] = re.findall(r'pause metadata[^\n]*', seg)
        runs = game / f'data/runs/{MAP}/main'
        files = sorted(p for p in runs.rglob('*') if p.is_file()) if runs.is_dir() else []
        report['files'] = [str(p.relative_to(game)).replace('\\', '/') for p in files]
        report['rec_flags'] = {str(p.name): header_flags(p) for p in files if p.suffix == '.rec'}
        report['staged'] = sorted(str(p.relative_to(stage)) for p in stage.rglob('*')) if stage.is_dir() else None
    finally:
        if cl:
            cl.stop()
        R.drop_lock()
    (a.out / 'report.json').write_text(json.dumps(report, indent=1), encoding='utf-8')
    print(json.dumps({k: v for k, v in report.items() if k != 'timer_idle'}, indent=1), flush=True)


if __name__ == '__main__':
    main()
