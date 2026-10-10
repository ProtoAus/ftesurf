#!/usr/bin/env python3
"""Hostile owner names on the product scoreboard: the native table must stay up.

The engine refuses a snapshot containing a control byte or malformed UTF-8, and a
refused label used to cost the whole table for that gesture. Uninstrumented progs;
the rows are local .rec headers written as bytes. Control = progs built before the
sanitizer, which must fall back, or this arm shows nothing. The other arms run the
subject under each string mode the builtins have (utf8_enable, com_parseutf8).
Graded on the table staying up; label text is only checked by eye in the screenshot.
GL, one machine.
"""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import time
from types import SimpleNamespace

from p590bridge import sha
from p603perf import prepare, status

# Each is one owner field. FTE markup (^U, ^{..}) is decoded by strdecolorize into the byte it names.
NAMES = [b'plain ascii', b'ctl\x01byte', b'^U0001markup', b'^{7f}delete', b'^{d800}surrogate', b'^U0000nul',
         b'overlong\xc0\x80', b'surrogate\xed\xa0\x80bytes', b'lone\x80cont', b'trunc\xe6\xbc', b'\xe6\xbc\xa2' * 40,
         b'A' * 200, 'café 漢字 ok'.encode(), b'tab\tin name']


def seed_names(game):
    for mapname in ('p603scores', 'p603scores.map'):
        folder = game / f'data/runs/{mapname}/main'
        for old in folder.glob('*.rec'): old.unlink()
        for row, name in enumerate(NAMES):
            head = (b'FTESURF-REC 5\nmap ' + mapname.encode() + b'\nowner "' + name + b'"\ntrack 0\n'
                    b'startseg 0\nleg 0\ntickrate 0.015\nflags 0\nbegin\n')
            samples = b''.join(b'%d %d 0 80 100 0 0 0 0 0 0 1 0 0 0\n' % (i, i) for i in range(20))
            (folder / f'{100+row:07d}_p603{row}_pb.rec').write_bytes(head + samples + b'end %d 20 0 0\n' % (100 + row))


# arm: (progs, cvars set before the rows are read). Engine defaults are utf8_enable 0, com_parseutf8 1.
ARMS = {'subject': ('subject', {}), 'utf8': ('subject', {'utf8_enable': 1}), 'quake': ('subject', {'com_parseutf8': 0}),
        'utf8quake': ('subject', {'utf8_enable': 1, 'com_parseutf8': 0}), 'control': ('control', {})}
MODE = {'utf8_enable': 0, 'com_parseutf8': 1}


def config(port, sets):
    return '\n'.join([
        'cfg_save_auto 0', 'set log_enable 1', 'set log_dir logs', 'set log_name perf', 'set log_readable 1',
        'set cl_idlefps 0', 'set cl_maxfps 100', 'set vid_vsync 0', 'set vid_conautoscale 0', 'set vid_conwidth 1920',
        'set vid_conheight 1080', 'set hud_scale 2', 'set developer 0', 'set name P603Names', 'set cl_run_upload 0',
        'set cl_board_url ""', *(f'set {k} {v}' for k, v in sets.items()), 'waitms 1500', 'menu_restart', 'waitms 700', 'ui_close', 'plug_load ui_imgui',
        f'connect 127.0.0.1:{port}', 'waitms 6500', 'ui_close', 'set ui_native_scores 1', 'set ui_native_scores_font 16',
        'scores tab local', 'scores leg 0', 'scores status', 'scores close', 'waitms 400',
        'echo P603 NAMES BASE', 'ui_imgui_status', 'scores open', 'waitms 1500',
        'echo P603 NAMES OPEN', 'ui_imgui_status', 'utf8_enable', 'com_parseutf8', 'screenshot names_open', 'scores close', 'waitms 500',
        'echo P603 NAMES CLOSED', 'ui_imgui_status', 'echo P603 NAMES FINISHED', 'quit']) + '\n'


def grade(rig):
    report = json.loads((rig / 'report.json').read_text())
    errors, seen = [], {}
    for arm, (progs, sets) in ARMS.items():
        meta = report['arms'].get(arm)
        if meta is None: errors.append(arm + ': missing arm'); continue
        text = (rig / arm / 'ftesurf/logs/perf.log').read_text(errors='replace')
        def need(ok, why):
            if not ok: errors.append(arm + ': ' + why)
        need(meta['returncode'] == 0 and text.count('P603 NAMES FINISHED') == 1 and 'FTESurf CSQC loaded' in text, 'incomplete run')
        need(not re.search(r'Unknown command|QC runtime error|CSQC_Abort', text, re.I), 'runtime error')
        need(re.search(rf'rows: {len(NAMES)} \({len(NAMES)} pass the filter\)', text), 'hostile rows did not load')
        for cvar, default in MODE.items():
            need(re.findall(rf'"{cvar}" is "([^"]*)"', text) == [str(sets.get(cvar, default))], cvar + ' is not the mode this arm names')
        marks = {name: status(line)[0] for name, line in
                 re.findall(r'P603 NAMES (BASE|OPEN|CLOSED)\s*[\r\n]+[^\r\n]*?(UIIMGUI STATUS [^\r\n]+)', text)}
        need(set(marks) == {'BASE', 'OPEN', 'CLOSED'}, 'counters missing')
        if set(marks) != {'BASE', 'OPEN', 'CLOSED'}: continue
        seen[arm] = marks['OPEN']
        need(marks['OPEN']['opens'] == marks['BASE']['opens'] + 1, 'table never tried to open natively')
        need(marks['CLOSED']['live'] == 0 and marks['CLOSED']['opens'] == marks['CLOSED']['closes'], 'owner leaked')
        need(len(list((rig / arm / 'ftesurf/screenshots').glob('names_open.*'))) == 1, 'screenshot missing')
        if progs == 'subject':
            need(marks['OPEN']['live'] == 1 and marks['OPEN']['failed'] == marks['BASE']['failed'] and
                 marks['OPEN']['rejected'] == 0 and marks['OPEN']['frames'] > marks['BASE']['frames'],
                 'native table refused a label or stopped drawing')
        else:
            # The pre-sanitizer build must show the defect: opened, then closed itself on a refused label.
            need(marks['OPEN']['live'] == 0, 'control stayed native: the names do not exercise the validator')
    return errors, seen


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--engine', type=Path, required=True)
    p.add_argument('--server', type=Path, required=True)
    p.add_argument('--plugin', type=Path, required=True)
    p.add_argument('--qc-artifacts', type=Path, required=True, help='subject product progs')
    p.add_argument('--control-qc', type=Path, required=True, help='product progs built before the sanitizer')
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    out = a.out.resolve()
    if os.name != 'nt' or not any((q / 'OWNER.md').is_file() for q in (out, *out.parents)):
        raise SystemExit('Windows and an owned --out (ancestor OWNER.md) required')
    out.mkdir(parents=True, exist_ok=True)
    rig = Path(tempfile.mkdtemp(prefix='p603-names-', dir=out))
    report = {'utc': datetime.now(timezone.utc).isoformat(), 'engine_sha256': sha(a.engine), 'plugin_sha256': sha(a.plugin),
              'subject_csprogs_sha256': sha(a.qc_artifacts / 'csprogs.dat'), 'control_csprogs_sha256': sha(a.control_qc / 'csprogs.dat'),
              'names': [n.decode('latin-1') for n in NAMES], 'arms': {}}
    for arm, (progs, sets) in ARMS.items():
        root = rig / arm; qc = a.qc_artifacts if progs == 'subject' else a.control_qc
        port = prepare(root, SimpleNamespace(rows=6, qc_artifacts=qc, engine=a.engine, server=a.server, plugin=a.plugin), arm)
        game = root / 'ftesurf'
        seed_names(game)
        (game / 'perf.cfg').write_text(config(port, sets))
        svcmd = [str(root / 'fteqwsv64.exe'), '-basedir', str(root), '-nohome', '-noplugins', '-port', str(port),
                 '+set', 'cfg_save_auto', '0', '+set', 'sv_public', '0', '+set', 'lobby_dir', '', '+map', 'p603scores.map']
        clcmd = [str(root / 'ftesurf64.exe'), '-basedir', str(root), '-nohome', '-nosound', '-nocdaudio', '-window',
                 '+set', 'plug_loaddefault', '0', '+set', 'vid_width', '1920', '+set', 'vid_height', '1080',
                 '+set', 'vid_fullscreen', '0', '+set', 'vid_winmaximize', '0', '+set', 'vid_renderer', 'gl',
                 '+set', 'cfg_save_auto', '0', '+exec', 'perf.cfg']
        with (root / 'server.log').open('w') as so, (root / 'launch.log').open('w') as co:
            sv = subprocess.Popen(svcmd, cwd=str(root), stdout=so, stderr=subprocess.STDOUT)
            try:
                time.sleep(2)
                if sv.poll() is not None: raise RuntimeError('owned server exited: ' + str(root))
                try: rc = subprocess.run(clcmd, cwd=str(root), stdout=co, stderr=subprocess.STDOUT, timeout=120).returncode
                except subprocess.TimeoutExpired: rc = None
            finally:
                if sv.poll() is None: sv.terminate(); sv.wait(timeout=10)
        report['arms'][arm] = {'returncode': rc}
        (rig / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
        print('Completed', arm, root, flush=True)
    errors, seen = grade(rig)
    for arm, s in seen.items(): print(arm, 'open counters', {k: s[k] for k in ('live', 'opens', 'closes', 'frames', 'rejected', 'failed')})
    for e in errors: print('FAIL', e)
    print('Names rig', rig, 'failures', len(errors)); raise SystemExit(bool(errors))
