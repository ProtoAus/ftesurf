#!/usr/bin/env python3
"""Acted native developer-console control. --root must have an ownership marker.

Uses a private writable gamedir; junctions expose only installed content. Runs
one owned dedicated socket and client, never the owner's profile/processes.
Logs stay under --root; only diagnostic counts/hashes are suitable for reports.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import socket
import subprocess
import time


ROOT = Path(__file__).resolve().parents[1]
PATTERNS = {
    'area': r'area \d+ of \d+: \d+ area\(s\) reachable',
    'mark': r'mark/300f:',
    'jump': r'jump z: moving player',
    'cull': r'area cull over 300 frames',
}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def text(path):
    return path.read_text(errors='replace') if path.exists() else ''


class Engine:
    def __init__(self, exe, rig, label, server=False):
        self.log = rig / 'ftesurf/logs' / (label + '.log')
        if self.log.exists():
            raise RuntimeError('fresh log required: ' + str(self.log))
        argv = [str(exe), '-plugin', '-nobrowse', '-basedir', str(rig),
                '-manifest', str(rig / 'default.fmf'), '+set', 'cfg_save_auto', '0',
                '+set', 'con_savehistory', '0', '+set', 'run_resume', '0',
                '+set', 'rec_enable', '0', '+set', 'rec_stream', '0',
                '+set', 'rec_terms', '0', '+set', 'log_enable', '1',
                '+set', 'log_developer', '1', '+set', 'log_dir', 'logs',
                '+set', 'log_name', label, '+set', 'developer', '2']
        if server:
            argv += ['+set', 'sv_public', '0', '+set', 'sv_port', '27590',
                     '+set', 'hostname', 'P734-test', '+map', 'surf_kitsune']
        else:
            argv += ['-window', '-nosound', '+set', 'vid_width', '960',
                     '+set', 'vid_height', '540', '+set', 'cl_idlefps', '0',
                     '+set', 'cl_maxfps', '100', '+set', 'name', 'P734-test']
        env = os.environ.copy()
        env['PATH'] = 'C:/FTESurf;' + env['PATH']
        self.proc = subprocess.Popen(argv, cwd='C:/FTESurf', env=env,
            stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print('owned process', label, self.proc.pid, flush=True)

    def send(self, line):
        if self.proc.poll() is not None:
            raise RuntimeError('engine exited: ' + str(self.proc.returncode))
        self.proc.stdin.write((line + '\n').encode('ascii'))
        self.proc.stdin.flush()

    def ready(self):
        end = time.time() + 90
        while time.time() < end:
            self.send('echo P734_READY')
            time.sleep(0.5)
            if 'P734_READY' in text(self.log):
                return
        raise RuntimeError('engine did not become ready: ' + str(self.log))

    def wait(self, needle, since=0, timeout=45):
        end = time.time() + timeout
        while time.time() < end:
            if needle in text(self.log)[since:]:
                return
            if self.proc.poll() is not None:
                break
            time.sleep(0.25)
        raise RuntimeError('missing ' + needle + ' in ' + str(self.log))

    def close(self):
        if self.proc.poll() is None:
            self.send('quit')
            try:
                self.proc.wait(timeout=20)
            except subprocess.TimeoutExpired:
                self.proc.terminate()
                self.proc.wait(timeout=10)
                raise RuntimeError('owned engine needed termination')
        if self.proc.returncode:
            raise RuntimeError('engine exit ' + str(self.proc.returncode))


def prepare(root, content, progs):
    rig = root / 'rig'
    gd = rig / 'ftesurf'
    if rig.exists():
        return rig
    gd.mkdir(parents=True)
    shutil.copy2(ROOT / 'default.fmf', rig / 'default.fmf')
    for name in ('maps', 'gfx', 'models', 'particles'):
        source = content / 'ftesurf' / name
        target = gd / name
        if source.is_dir():
            subprocess.run(['cmd', '/c', 'mklink', '/J', str(target), str(source)],
                           check=True, capture_output=True)
    for name in ('glsl', 'scripts'):
        source = content / 'ftesurf' / name
        if source.is_dir():
            shutil.copytree(source, gd / name)
    shutil.copytree(ROOT / 'ftesurf/cfg', gd / 'cfg')
    shutil.copy2(ROOT / 'ftesurf/fs_addons.default.txt', gd / 'fs_addons.default.txt')
    for name in ('qwprogs.dat', 'csprogs.dat', 'menu.dat'):
        shutil.copy2(progs / name, gd / name)
    (gd / 'downloads/csprogsvers').mkdir(parents=True)
    subprocess.run(['python', str(ROOT / 'tools/seed_csprogs.py'), str(gd / 'csprogs.dat')],
                   check=True, capture_output=True)
    return rig


def phase(cl, name, enabled):
    if enabled is not None:
        cl.send('pm_jumpzdebug ' + str(enabled))
        cl.send('hl2_visdebug ' + str(enabled))
    cl.send('echo P734_BEGIN_' + name)
    cl.wait('P734_BEGIN_' + name)
    start = len(text(cl.log))
    cl.send('cmd zone_goto 1')
    time.sleep(1)
    cl.send('cmd viewpos')
    for _ in range(10):
        cl.send('+jump')
        time.sleep(0.4)
        cl.send('-jump')
        time.sleep(0.4)
    cl.send('cmd viewpos')
    time.sleep(1)
    body = text(cl.log)[start:]
    counts = {key: len(re.findall(pattern, body)) for key, pattern in PATTERNS.items()}
    return dict(counts=counts, viewpos=len(re.findall(r'setpos ', body)),
                unknown='Unknown command' in body)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--root', type=Path, required=True)
    ap.add_argument('--content', type=Path, default=Path('C:/FTESurf'))
    ap.add_argument('--progs', type=Path, default=Path('C:/FTESurf/ftesurf'))
    ap.add_argument('--client', type=Path, required=True)
    ap.add_argument('--plugin', type=Path, required=True)
    ap.add_argument('--server', type=Path, default=Path('C:/FTEQuake/fteqwsv64.exe'))
    ap.add_argument('--label', required=True)
    ap.add_argument('--control', action='store_true')
    ap.add_argument('--direct', action='store_true', help='execute the supplied client in place; keep the isolated gamedir')
    a = ap.parse_args()
    a.root = a.root.resolve()
    if not (a.root / 'OWNER.md').is_file():
        raise RuntimeError('root needs OWNER.md before population')
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.bind(('127.0.0.1', 27590))
    rig = prepare(a.root, a.content.resolve(), a.progs.resolve())
    binary = a.client.resolve() if a.direct else rig / 'p734client.exe'
    plugin = rig / 'fteplug_hl2_x64.dll'
    if not a.direct:
        shutil.copy2(a.client, binary)
    shutil.copy2(a.plugin, plugin)
    cl = sv = None
    results = dict(client_sha256=digest(binary), plugin_sha256=digest(plugin))
    try:
        sv = Engine(a.server.resolve(), rig, a.label + '-sv', server=True)
        sv.ready()
        cl = Engine(binary, rig, a.label + '-cl')
        cl.ready()
        cl.send('pm_selftest')
        cl.wait('all checks passed')
        cl.send('connect 127.0.0.1:27590')
        cl.wait('FTESurf CSQC loaded', timeout=90)
        time.sleep(3)
        cl.send('menu_restart')
        cl.send('ui_close')
        cl.send('cl_idlefps 0')
        cl.send('cl_maxfps 100')
        cl.send('cmd viewpos')
        cl.wait('setpos ')
        if not a.control:
            start = len(text(cl.log))
            cl.send('pm_jumpzdebug')
            cl.send('hl2_visdebug')
            for name in ('pm_jumpzdebug', 'hl2_visdebug'):
                cl.wait('"' + name + '" is "0"', since=start)
        phases = [('control', None)] if a.control else [('off', 0), ('on', 1), ('off_again', 0)]
        for name, enabled in phases:
            results[name] = phase(cl, name, enabled)
            print(name, results[name], flush=True)
        cl.send('screenshot ' + a.label)
        time.sleep(1)
        start = len(text(cl.log))
        cl.send('map bhop_eazy')
        cl.wait('FTESurf CSQC loaded', since=start, timeout=90)
        time.sleep(2)
        cl.send('echo P734_DET_BEGIN')
        cl.send('pm_dettest')
        cl.send('echo P734_DET_END')
        cl.wait('P734_DET_END')
        body = text(cl.log)
        probe = body.split('P734_DET_BEGIN')[-1].split('P734_DET_END')[0]
        results['dettest'] = [re.sub(r'^\d{4}-\d\d-\d\d \d\d:\d\d:\d\d ', '', line)
                              for line in probe.splitlines() if line.strip()]
        assert 'mapcrc' in probe and 'no map loaded' not in probe, results
        results['selftest_pass'] = 'all checks passed' in body
        results['vm_error'] = any(x in body for x in ('QC VM error', 'Host_Error', 'Sys_Error'))
        results['area_since_spawn'] = len(re.findall(PATTERNS['area'], body))
        if a.control:
            assert results['area_since_spawn'] > 0, results
            assert all(results['control']['counts'][k] > 0 for k in ('mark', 'jump')), results
        else:
            for name in ('off', 'off_again'):
                assert not any(results[name]['counts'].values()), results
                assert not results[name]['unknown'], results
            assert all(results['on']['counts'][k] > 0 for k in ('area', 'mark', 'jump')), results
        assert results['selftest_pass'] and not results['vm_error'], results
        print('PASS', a.label, flush=True)
    finally:
        errors = []
        for e in (cl, sv):
            if e:
                try:
                    e.close()
                except Exception as exc:
                    errors.append(str(exc))
        results['cleanup_errors'] = errors
        (a.root / 'artifacts' / (a.label + '.json')).write_text(json.dumps(results, indent=2) + '\n')
        if errors:
            raise RuntimeError(errors)


if __name__ == '__main__':
    main()
