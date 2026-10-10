#!/usr/bin/env python3
"""Uninstrumented actual-scoreboard cost controls; engine 100-frame CPU buckets.

No QC probes, seams, changed product binary, injected native action or GPU timer.
Native/legacy use identical rows/map/view/config and the same loaded provider.
Absent is a third closed/open control. Retain logs, configs, screenshots and hashes.
"""
import argparse
import ctypes
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import re
import shutil
import socket
import statistics
import subprocess
import tempfile
import time

from p603scores import seed
from p590bridge import sha
from test_ui_modern import make_map
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
ARMS = ('native', 'legacy', 'absent')
PHASES = ('closed', 'open', 'closed_after')
BUCKETS = ('QC UpdateView', 'CSQC Drawing', '2d Elements', 'Total refresh', 'Draw Calls', 'Draw Indicies',
           'r_speeds overhead', 'Frame pacing', 'Present')


class Memory(ctypes.Structure):
    _fields_ = [('cb', ctypes.c_ulong), ('PageFaultCount', ctypes.c_ulong)] + [
        (name, ctypes.c_size_t) for name in ('PeakWorkingSetSize', 'WorkingSetSize',
        'QuotaPeakPagedPoolUsage', 'QuotaPagedPoolUsage', 'QuotaPeakNonPagedPoolUsage',
        'QuotaNonPagedPoolUsage', 'PagefileUsage', 'PeakPagefileUsage', 'PrivateUsage')]


def memory(handle):
    stats = Memory(); stats.cb = ctypes.sizeof(stats)
    fn = ctypes.WinDLL('psapi', use_last_error=True).GetProcessMemoryInfo
    fn.argtypes = (ctypes.c_void_p, ctypes.POINTER(Memory), ctypes.c_ulong)
    fn.restype = ctypes.c_int
    if not fn(int(handle), ctypes.byref(stats), stats.cb): raise ctypes.WinError(ctypes.get_last_error())
    return {'working_set': stats.WorkingSetSize, 'private_bytes': stats.PrivateUsage}


def prepare(root, a, arm):
    game = root / 'ftesurf'; game.mkdir(parents=True)
    (game / 'cfg').mkdir(); (game / 'cfg/default.cfg').write_text('cfg_save_auto 0\n')
    (game / 'downloads/csprogsvers').mkdir(parents=True)
    for folder in ('glsl', 'scripts', 'particles', 'models', 'gfx/fonts'):
        source = ROOT / 'ftesurf' / folder
        if not source.is_dir(): source = Path('C:/FTESurf/ftesurf') / folder
        if source.is_dir(): shutil.copytree(source, game / folder)
    (game / 'maps').mkdir(exist_ok=True); (game / 'maps/p603scores.map').write_text(make_map())
    seed(game, a.rows)
    for name in ('csprogs.dat', 'qwprogs.dat', 'menu.dat'):
        shutil.copy2(a.qc_artifacts / name, game / name)
    subprocess.run([os.sys.executable, str(ROOT / 'tools/seed_csprogs.py'), str(game / 'csprogs.dat')], check=True, stdout=subprocess.DEVNULL)
    shutil.copy2(a.engine, root / 'ftesurf64.exe'); shutil.copy2(a.server, root / 'fteqwsv64.exe')
    if arm != 'absent': shutil.copy2(a.plugin, root / 'fteplug_ui_imgui_x64.dll')
    (root / 'default.fmf').write_text('FTEMANIFEST 1\nGAME FTESurfScoresFixture\nNAME "Native scoreboard cost"\nBASEGAME ftesurf\nDISABLEHOMEDIR 1\nMAINCONFIG p603-unused\n')
    for port in range(27620, 27519, -1):
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            try: s.bind(('127.0.0.1', port))
            except OSError: continue
            return port
    raise RuntimeError('no designated dedicated test port free')


def config(arm, port, repeats, samples):
    lines = ['cfg_save_auto 0', 'set log_enable 1', 'set log_dir logs', 'set log_name perf', 'set log_readable 1',
             'set cl_idlefps 0', 'set cl_maxfps 100', 'set vid_vsync 0', 'set r_speeds 2',
             'set pr_enable_profiling 0', 'set vid_conautoscale 0', 'set vid_conwidth 1920',
             'set vid_conheight 1080', 'set hud_scale 2', 'set gl_conback 0',
             'set scr_conalpha 0', 'set developer 0', 'set log_developer 0',
             'set name P603Perf', 'set cl_run_upload 0', 'set cl_board_url ""',
             'waitms 1500', 'menu_restart', 'waitms 700', 'ui_close']
    if arm != 'absent': lines += ['plug_load ui_imgui', 'ui_imgui_status']
    lines += [f'connect 127.0.0.1:{port}', 'waitms 6500', 'ui_close',
              f'set ui_native_scores {int(arm == "native")}', 'set ui_native_scores_font 13', 'set hud_scale 2',
              'scores tab local', 'scores leg 0', 'scores status', 'scores close']
    for cycle in range(repeats):
        for phase in PHASES:
            lines += ['scores open' if phase == 'open' else 'scores close', 'waitms 1800',
                      f'echo P603 PERF BEGIN {cycle} {phase}']
            if arm != 'absent': lines += ['ui_imgui_status']
            for sample in range(samples):
                lines += ['waitms 1250', f'echo P603 PERF SAMPLE {cycle} {phase} {sample}',
                          'r_speeds_dump', 'waitms 100']
            if arm != 'absent': lines += ['ui_imgui_status']
            lines += [f'echo P603 PERF END {cycle} {phase}', f'screenshot perf_{cycle}_{phase}']
    lines += ['echo P603 PERF FINISHED', 'quit']
    return '\n'.join(lines) + '\n'


def status(text):
    return [{k: int(v) for k, v in re.findall(r'(\w+)=(\d+)\b', line) if k != 'version'}
            for line in re.findall(r'UIIMGUI STATUS ([^\r\n]+)', text)]


def parse(text):
    rows = []
    pattern = r'P603 PERF SAMPLE (\d+) (\w+) (\d+)(.*?)(?=P603 PERF (?:SAMPLE|BEGIN|END|FINISHED)|\Z)'
    for match in re.finditer(pattern, text, re.S):
        values = {}; count = 0
        for line in match[4].splitlines():
            value = re.search(r'\b([0-9]+(?:\.[0-9]+)?)\s+(' + '|'.join(map(re.escape, BUCKETS)) + r')\s*$', line)
            if value: values[value[2]] = float(value[1]); count += 1
        rows.append({'cycle': int(match[1]), 'phase': match[2], 'sample': int(match[3]), 'buckets': values,
                     'valid_dump': count == len(BUCKETS) and match[4].count('100-frame average') == 1 and
                     match[4].count('---- end r_speeds_dump ----') == 1})
    return rows


def grade(rig):
    report = json.loads((rig / 'report.json').read_text())
    errors = []
    def need(ok, why):
        if not ok: errors.append(why)
    need(report.get('planned_arms') == list(ARMS) and set(report.get('arms', {})) == set(ARMS), 'planned arms incomplete')
    repeats, samples = report.get('repeats', 0), report.get('samples', 0)
    need(repeats >= 2 and samples >= 3, 'insufficient repetitions/samples')
    expected = {(c, p, s) for c in range(repeats) for p in PHASES for s in range(samples)}
    for arm in ARMS:
        meta = report.get('arms', {}).get(arm, {})
        log = rig / arm / 'ftesurf/logs/perf.log'
        if not log.exists(): errors.append(arm + ': missing log'); continue
        text = log.read_text(errors='replace')
        need(meta.get('returncode') == 0 and meta.get('timed_out') is False, arm + ': failed exit')
        need(text.count('P603 PERF FINISHED') == 1 and 'FTESurf CSQC loaded' in text, arm + ': incomplete/quiet')
        need(not re.search(r'Unknown command|QC runtime error|CSQC_Abort|Shader double free|P603 (STATE|CAP)', text, re.I), arm + ': runtime error/instrumented QC')
        need('OpenGL renderer initialized' in text, arm + ': GL backend not positively identified')
        need(re.search(rf'rows: {report.get("rows", -1)} \({report.get("rows", -1)} pass the filter\)', text), arm + ': row workload absent/wrong')
        cfg = (rig / arm / 'ftesurf/perf.cfg').read_text()
        need('set pr_enable_profiling 0' in cfg and 'set r_speeds 2' in cfg, arm + ': timer/profile config changed')
        rows = parse(text)
        keys = [(r['cycle'], r['phase'], r['sample']) for r in rows]
        need(len(keys) == len(expected) and set(keys) == expected, arm + ': missing/duplicate sample')
        for row in rows:
            need(row['valid_dump'] and set(row['buckets']) == set(BUCKETS) and all(math.isfinite(v) and v >= 0 for v in row['buckets'].values()) and all(row['buckets'].get(k, 0) > 0 for k in BUCKETS[:6]), arm + ': empty/incomplete CPU or geometry witness')
        memories = meta.get('memory', [])
        need(len(memories) == len(expected) and {(m.get('cycle'), m.get('phase'), m.get('sample')) for m in memories} == expected, arm + ': memory sample missing/duplicate')
        need(all(m.get('private_bytes', 0) > 0 and m.get('working_set', 0) > 0 for m in memories), arm + ': empty memory witness')
        if arm != 'absent':
            for cycle in range(repeats):
                for phase in PHASES:
                    blocks = re.findall(rf'P603 PERF BEGIN {cycle} {phase}\b(.*?)P603 PERF END {cycle} {phase}\b', text, re.S)
                    need(len(blocks) == 1, arm + ': missing/duplicate phase'); stats = status(blocks[0]) if len(blocks) == 1 else []
                    need(len(stats) == 2, arm + ': missing native counters')
                    if len(stats) == 2:
                        opened = arm == 'native' and phase == 'open'
                        need(all(r.get('live') == int(opened) and r.get('rejected') == 0 for r in stats), arm + ': incorrect live/submission state')
                        if opened:
                            need(stats[1].get('frames', 0) > stats[0].get('frames', 0) and stats[1].get('submits', 0) > stats[0].get('submits', 0) and stats[1].get('uploads') == stats[0].get('uploads'), arm + ': native did not act/atlas reuploaded')
                        else:
                            need(stats[0] == stats[1] and stats[0].get('opens') == stats[0].get('closes'), arm + ': closed/legacy native work or leak')
        for cycle in range(repeats):
            for phase in PHASES:
                shots = list((rig / arm / 'ftesurf/screenshots').glob(f'perf_{cycle}_{phase}.*'))
                need(len(shots) == 1, arm + ': missing/ambiguous screenshot')
                if len(shots) == 1:
                    try:
                        with Image.open(shots[0]) as im:
                            need(im.size == (1920, 1080), arm + ': screenshot resolution changed')
                            pixels = im.convert('RGB').crop((688,355,1343,720))
                            ink = pixels.get_flattened_data() if hasattr(pixels, 'get_flattened_data') else tuple(pixels.getdata())
                            bright = sum(min(v) > 130 for v in ink)
                            blue = sum(b > r+20 and b > g+10 for r,g,b in ink)
                            need(bright > 1000 if phase == 'open' else bright < 900, arm + ': scoreboard glyphs did not act/close')
                            need((blue > 4000) == (phase == 'open' and arm == 'native'), arm + ': actual native/legacy screenshot route')
                    except (OSError, ValueError): errors.append(arm + ': unreadable screenshot')
        need(meta.get('csprogs_sha256') == report.get('csprogs_sha256'), arm + ': unequal/instrumented QC identity')
        need(meta.get('engine_sha256') == report.get('engine_sha256'), arm + ': unequal engine identity')
    return errors


def summary(rig):
    result = {'units': 'microseconds/frame CPU, except draw counts/indices; 100-frame engine snapshots', 'arms': {}}
    for arm in ARMS:
        rows = parse((rig / arm / 'ftesurf/logs/perf.log').read_text(errors='replace'))
        result['arms'][arm] = {}
        for phase in PHASES:
            result['arms'][arm][phase] = {}
            for bucket in BUCKETS:
                values = [r['buckets'][bucket] for r in rows if r['phase'] == phase]
                result['arms'][arm][phase][bucket] = {'median': statistics.median(values), 'min': min(values), 'max': max(values)}
    return result


def run(a):
    if os.name != 'nt': raise RuntimeError('Windows runtime required; grade is portable')
    if not any((p / 'OWNER.md').is_file() for p in (a.out.resolve(), *a.out.resolve().parents)):
        raise RuntimeError('--out requires ancestor OWNER.md')
    a.out.mkdir(parents=True, exist_ok=True)
    rig = Path(tempfile.mkdtemp(prefix='p603-perf-', dir=a.out))
    report = {'utc': datetime.now(timezone.utc).isoformat(), 'planned_arms': list(ARMS),
              'rows': a.rows, 'repeats': a.repeats, 'samples': a.samples,
              'csprogs_sha256': sha(a.qc_artifacts / 'csprogs.dat'), 'engine_sha256': sha(a.engine),
              'plugin_sha256': sha(a.plugin), 'arms': {},
              'limits': 'CPU bucket snapshots with identical r_speeds overlay; not GPU timing or broad device acceptance. Synthetic offline local rows. A native page holds 24 rows (6 with an older provider) and legacy shows about 19.5, so --rows 20 is the closest equal visible work; other stores measure different visible-row workloads. Memory includes the whole process.'}
    for arm in a.arms:
        root = rig / arm
        port = prepare(root, a, arm)
        game = root / 'ftesurf'
        (game / 'perf.cfg').write_text(config(arm, port, a.repeats, a.samples))
        svcmd = [str(root / 'fteqwsv64.exe'), '-basedir', str(root), '-nohome', '-noplugins', '-port', str(port),
                 '+set', 'cfg_save_auto', '0', '+set', 'sv_public', '0', '+set', 'lobby_dir', '', '+map', 'p603scores.map']
        clcmd = [str(root / 'ftesurf64.exe'), '-basedir', str(root), '-nohome', '-nosound', '-nocdaudio', '-window',
                 '+set', 'plug_loaddefault', '0', '+set', 'vid_width', '1920', '+set', 'vid_height', '1080',
                 '+set', 'vid_fullscreen', '0', '+set', 'vid_winmaximize', '0', '+set', 'vid_renderer', 'gl',
                 '+set', 'cfg_save_auto', '0', '+exec', 'perf.cfg']
        memories, seen, timed, rc = [], set(), False, None
        with (root / 'server.log').open('w') as so, (root / 'launch.log').open('w') as co:
            sv = subprocess.Popen(svcmd, cwd='C:/FTESurf', stdout=so, stderr=subprocess.STDOUT)
            try:
                time.sleep(2)
                if sv.poll() is not None: raise RuntimeError('owned server exited: ' + str(root))
                cl = subprocess.Popen(clcmd, cwd='C:/FTESurf', stdout=co, stderr=subprocess.STDOUT)
                try:
                    deadline = time.monotonic() + 90 + a.repeats * 3 * (6 + a.samples * 1.5)
                    while cl.poll() is None:
                        log = game / 'logs/perf.log'
                        text = log.read_text(errors='replace') if log.exists() else ''
                        for c, p, s in re.findall(r'P603 PERF SAMPLE (\d+) (\w+) (\d+)', text):
                            key = (int(c), p, int(s))
                            if key not in seen:
                                memories.append({'cycle': key[0], 'phase': p, 'sample': key[2], **memory(cl._handle)})
                                seen.add(key)
                        if time.monotonic() > deadline: timed = True; cl.terminate(); break
                        time.sleep(0.08)
                    rc = cl.wait(timeout=10)
                finally:
                    if cl.poll() is None: cl.terminate(); cl.wait(timeout=10)
            finally:
                if sv.poll() is None: sv.terminate(); sv.wait(timeout=10)
        report['arms'][arm] = {'returncode': rc, 'timed_out': timed, 'memory': memories,
                              'engine_sha256': sha(root / 'ftesurf64.exe'), 'csprogs_sha256': sha(game / 'csprogs.dat'),
                              'client_command': clcmd, 'server_command': svcmd}
        (rig / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
        print('Completed', arm, root, flush=True)
    errors = grade(rig)
    (rig / 'grade.json').write_text(json.dumps({'errors': errors}, indent=2) + '\n')
    if not errors: (rig / 'summary.json').write_text(json.dumps(summary(rig), indent=2) + '\n')
    for e in errors: print('FAIL', e)
    print('Cost rig', rig, 'failures', len(errors)); return int(bool(errors))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--engine', type=Path, default=Path('C:/msys64/home/Lex/fteqw-imgui-input/engine/release/fteqw64.exe'))
    p.add_argument('--server', type=Path, default=Path('C:/FTEQuake/fteqwsv64.exe'))
    p.add_argument('--qc-artifacts', type=Path)
    p.add_argument('--plugin', type=Path)
    p.add_argument('--out', type=Path)
    p.add_argument('--arms', nargs='+', choices=ARMS, default=list(ARMS), help='partial runs intentionally fail the complete-reader gate until explicitly combined')
    p.add_argument('--rows', type=int, default=6, choices=range(6, 257))
    p.add_argument('--repeats', type=int, default=2, choices=range(2, 11))
    p.add_argument('--samples', type=int, default=3, choices=range(3, 21))
    p.add_argument('command', nargs='?', choices=('run', 'grade'), default='run')
    p.add_argument('rig', nargs='?', type=Path)
    a = p.parse_args()
    if a.command == 'grade':
        if a.rig is None: p.error('grade requires a retained rig')
        errors = grade(a.rig)
        for e in errors: print('FAIL', e)
        print('failures', len(errors)); raise SystemExit(bool(errors))
    if a.qc_artifacts is None or a.plugin is None or a.out is None:
        p.error('run requires --qc-artifacts, --plugin and --out')
    raise SystemExit(run(a))
