#!/usr/bin/env python3
"""Repeated cold starts on one renderer: does device enumeration survive, and does it list a GPU?

Win32VK_EnumerateDevices read an uninitialised local when vulkan-1.dll was already
loaded (always, when Vulkan is the running renderer). Garbage that happened to be
NULL listed no device; any other garbage was called. Control and subject starts
alternate; each start is a new process in its own owned rig. No server, no map.
"""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
from types import SimpleNamespace

from p590bridge import sha
from p603perf import prepare


def start(root, renderer, n):
    game = root / 'ftesurf'
    name = f'cold{n:02d}'
    (game / 'cold.cfg').write_text('\n'.join([
        'cfg_save_auto 0', 'set log_enable 1', 'set log_dir logs', f'set log_name {name}', 'set log_readable 1',
        'set cl_idlefps 0', 'set cl_maxfps 100', 'waitms 2500', 'echo VKENUM OPTS BEGIN', '_vid_renderer_opts',
        'echo VKENUM OPTS END', 'echo VKENUM FINISHED', 'quit']) + '\n')
    cmd = [str(root / 'ftesurf64.exe'), '-basedir', str(root), '-nohome', '-nosound', '-nocdaudio', '-window',
           '+set', 'plug_loaddefault', '0', '+set', 'vid_width', '1280', '+set', 'vid_height', '720',
           '+set', 'vid_fullscreen', '0', '+set', 'vid_winmaximize', '0', '+set', 'vid_renderer', renderer,
           '+set', 'cfg_save_auto', '0', '+exec', 'cold.cfg']
    with (root / f'{name}.launch.log').open('w') as out:
        try: rc = subprocess.run(cmd, cwd=str(root), stdout=out, stderr=subprocess.STDOUT, timeout=60).returncode
        except subprocess.TimeoutExpired: rc = None
    log = game / 'logs' / (name + '.log')
    text = log.read_text(errors='replace') if log.exists() else ''
    opts = re.search(r'VKENUM OPTS BEGIN(.*?)VKENUM OPTS END', text, re.S)
    return {'n': n, 'returncode': rc, 'initialized': ' renderer initialized' in text,
            'finished': text.count('VKENUM FINISHED') == 1,
            # R_DeviceEnumerated only ever sees "Vulkan-<gpu name>" from a successful enumeration.
            'listed': re.findall(r'Vulkan-[^"\r\n]*?(?:GeForce|Radeon|Intel|Arc|llvmpipe)[^"\r\n\\]*', opts[1])[:1] if opts else []}


def grade(report):
    errors = []
    for arm in ('control', 'subject'):
        runs = report['arms'].get(arm, [])
        if len(runs) != report['starts']: errors.append(arm + ': start count')
        if not all(r['initialized'] for r in runs): errors.append(arm + ': requested renderer did not initialise on every start')
    subject, control = report['arms'].get('subject', []), report['arms'].get('control', [])
    bad = [r['n'] for r in subject if r['returncode'] != 0 or not r['finished'] or not r['listed']]
    if bad: errors.append(f'subject: starts {bad} crashed, hung or listed no GPU')
    # The control must show the defect, or this run says nothing about the fix.
    if all(r['returncode'] == 0 and r['listed'] for r in control):
        errors.append('control never failed: not demonstrated on this run')
    return errors


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--control', type=Path, required=True, help='client built without the fix')
    p.add_argument('--subject', type=Path, required=True)
    p.add_argument('--server', type=Path, required=True, help='only copied beside the client by the shared rig recipe')
    p.add_argument('--qc-artifacts', type=Path, required=True)
    p.add_argument('--plugin', type=Path, required=True)
    p.add_argument('--renderer', default='vk')
    p.add_argument('--starts', type=int, default=20)
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    out = a.out.resolve()
    if os.name != 'nt' or not any((q / 'OWNER.md').is_file() for q in (out, *out.parents)):
        raise SystemExit('Windows and an owned --out (ancestor OWNER.md) required')
    out.mkdir(parents=True, exist_ok=True)
    rig = Path(tempfile.mkdtemp(prefix='vkenum-', dir=out))
    report = {'utc': datetime.now(timezone.utc).isoformat(), 'renderer': a.renderer, 'starts': a.starts,
              'control_sha256': sha(a.control), 'subject_sha256': sha(a.subject), 'arms': {'control': [], 'subject': []}}
    for arm, exe in (('control', a.control), ('subject', a.subject)):
        prepare(rig / arm, SimpleNamespace(rows=6, qc_artifacts=a.qc_artifacts, engine=exe, server=a.server, plugin=a.plugin), arm)
    for n in range(a.starts):
        for arm in ('control', 'subject'):
            report['arms'][arm].append(start(rig / arm, a.renderer, n))
            (rig / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    errors = grade(report)
    for arm, runs in report['arms'].items():
        print(arm, 'exit0', sum(r['returncode'] == 0 for r in runs), 'crashed', sum(r['returncode'] not in (0, None) for r in runs),
              'hung', sum(r['returncode'] is None for r in runs), 'listed-gpu', sum(bool(r['listed']) for r in runs), 'of', len(runs))
    for e in errors: print('FAIL', e)
    print('Cold-start rig', rig, 'failures', len(errors)); raise SystemExit(bool(errors))
