#!/usr/bin/env python3
"""Owned Windows menu/restart controls. A test adapter confines the real launcher to loopback.
The adapter is NOT a shipped bootstrap and does not prove default public-feed availability.
"""
import argparse
from collections import Counter
import ctypes
from ctypes import wintypes as w
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import threading
import time

import updatefeed
from test_ingame_update import owned_error

ADAPTER = r'''
#include <windows.h>
#include <process.h>
#include <stdio.h>
#include <stdlib.h>
#include <wchar.h>
int wmain(int argc, wchar_t **argv)
{
	const wchar_t *log = _wgetenv(L"OWNED_UPDATER_ADAPTER_LOG");
	const wchar_t *launcher = _wgetenv(L"OWNED_UPDATER_LAUNCHER");
	const wchar_t *url = _wgetenv(L"OWNED_UPDATER_URL");
	const wchar_t *output = _wgetenv(L"OWNED_UPDATER_LAUNCHER_LOG");
	FILE *out;
	intptr_t child;
	DWORD code;
	const wchar_t *args[32];
	int n = 0, i;
	if (!log || !launcher || !url || !output) return 91;
	out = _wfopen(log, L"w");
	if (!out) return 92;
	fprintf(out, "adapter_pid=%lu\n", GetCurrentProcessId());
	for (i = 0; i < argc; i++) fprintf(out, "arg%d=%ls\n", i, argv[i]);
	fflush(out);
	if (argc != 5 || wcscmp(argv[1], L"--dir") || wcscmp(argv[3], L"--wait-for-game") || wcscmp(argv[4], L"--yes")) return 93;
	args[n++] = launcher;
	for (i = 1; i < argc; i++) args[n++] = argv[i];
	args[n++] = L"--allow-insecure"; args[n++] = L"--manifest-url"; args[n++] = url;
	args[n++] = L"--"; args[n++] = L"-nohome"; args[n++] = L"-basedir"; args[n++] = argv[2];
	args[n++] = L"-window"; args[n++] = L"+set"; args[n++] = L"cfg_save_auto"; args[n++] = L"0";
	args[n++] = L"+set"; args[n++] = L"name"; args[n++] = L"UpdaterRig";
	args[n++] = L"+exec"; args[n++] = L"cfg/test/handoff-return.cfg"; args[n] = NULL;
	if (!_wfreopen(output, L"w", stdout) || !_wfreopen(output, L"a", stderr)) return 96;
	child = _wspawnv(_P_NOWAIT, launcher, args);
	if (child == -1) return 94;
	fprintf(out, "launcher_pid=%lu\n", GetProcessId((HANDLE)child)); fflush(out);
	WaitForSingleObject((HANDLE)child, INFINITE);
	GetExitCodeProcess((HANDLE)child, &code); CloseHandle((HANDLE)child);
	fprintf(out, "launcher_exit=%lu\n", code); fclose(out);
	return (int)code;
}
'''



def owned_job(process):
    """Bind the owned game and ALL its future descendants to a kill-on-close job."""
    class Basic(ctypes.Structure):
        _fields_ = [('user', ctypes.c_int64), ('job_user', ctypes.c_int64), ('flags', w.DWORD),
                    ('min_ws', ctypes.c_size_t), ('max_ws', ctypes.c_size_t), ('active', w.DWORD),
                    ('affinity', ctypes.c_size_t), ('priority', w.DWORD), ('scheduling', w.DWORD)]
    class IO(ctypes.Structure):
        _fields_ = [(name, ctypes.c_uint64) for name in ['read_ops', 'write_ops', 'other_ops', 'read_bytes', 'write_bytes', 'other_bytes']]
    class Limits(ctypes.Structure):
        _fields_ = [('basic', Basic), ('io', IO), ('process_mem', ctypes.c_size_t), ('job_mem', ctypes.c_size_t),
                    ('peak_process_mem', ctypes.c_size_t), ('peak_job_mem', ctypes.c_size_t)]
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.CreateJobObjectW.argtypes = [w.LPVOID, w.LPCWSTR]; kernel.CreateJobObjectW.restype = w.HANDLE
    kernel.SetInformationJobObject.argtypes = [w.HANDLE, ctypes.c_int, w.LPVOID, w.DWORD]
    kernel.AssignProcessToJobObject.argtypes = [w.HANDLE, w.HANDLE]
    kernel.CloseHandle.argtypes = [w.HANDLE]
    job = kernel.CreateJobObjectW(None, None); assert job, ctypes.get_last_error()
    info = Limits(); info.basic.flags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
    assert kernel.SetInformationJobObject(job, 9, ctypes.byref(info), ctypes.sizeof(info)), ctypes.get_last_error()
    if not kernel.AssignProcessToJobObject(job, int(process._handle)):
        kernel.CloseHandle(job)
        process.terminate(); process.wait(timeout=10)
        raise AssertionError('could not isolate owned descendants in job: ' + str(ctypes.get_last_error()))
    return job


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--work-root', type=Path, required=True)
    ap.add_argument('--control-stage', type=Path, required=True)
    ap.add_argument('--engine-release', type=Path, required=True)
    ap.add_argument('--engine-exe', type=Path, help='Explicit pre-fix native control override')
    ap.add_argument('--progs', type=Path, help='Fresh isolated QC outputs to overlay on the frozen stage')
    ap.add_argument('--launcher', type=Path, required=True)
    ap.add_argument('--arm', choices=['all', 'toggle', 'missing', 'held', 'outage', 'restart', 'permission-link', 'restart-link', 'wait-lock', 'recovery-version'], default='all')
    a = ap.parse_args()
    assert os.name == 'nt', 'Windows runtime driver'
    root = a.work_root.resolve()
    assert not root.exists(), 'fresh owned rig required'
    root.mkdir(parents=True)
    (root / 'OWNER.md').write_text('Owned updater menu/handoff fixtures; synthetic player sentinels. Test-only loopback adapter, not product bootstrap. Retain evidence; stop only recorded handles/PIDs.\n')
    stage = root / 'stage'
    shutil.copytree(a.control_stage, stage)
    shutil.copyfile(a.engine_exe or a.engine_release / 'fteqw64.exe', stage / 'ftesurf64.exe')
    for plugin in ['fteplug_hl2_x64.dll', 'fteplug_ui_imgui_x64.dll']:
        shutil.copyfile(a.engine_release / plugin, stage / plugin)
    if a.progs:
        for progs in ['menu.dat', 'csprogs.dat', 'qwprogs.dat']:
            shutil.copyfile(a.progs / progs, stage / 'ftesurf' / progs)
    fixture_rel = 'ftesurf/gfx/updater_fixture.txt'
    fixture = stage / fixture_rel
    fixture.write_bytes(b'old updater control\n')
    protected = {'ftesurf/ftesurf.cfg': b'cfg_save_auto 0\n// owned user sentinel\n',
                 'ftesurf/fs_addons.txt': b'// owned mounted game sentinel\n',
                 'hl2/player-sentinel.txt': b'owned mounted asset\n',
                 'ftesurf/maps/zones/local/surf_updater_fixture.json': b'owned edited zone\n',
                 'ftesurf/data/runs/player-sentinel.rec': b'owned recording sentinel\n'}
    http = root / 'http'; http.mkdir()
    hits = Counter(); failure = {'feed': False, 'object': False}
    class Handler(SimpleHTTPRequestHandler):
        def do_GET(self):
            hits[self.path] += 1
            if (self.path == '/update.json' and failure['feed']) or (self.path.startswith('/objects/') and failure['object']):
                self.send_error(503); return
            super().do_GET()
        def log_message(self, *args): pass
    server = ThreadingHTTPServer(('127.0.0.1', 0), partial(Handler, directory=str(http)))
    thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
    url = f'http://127.0.0.1:{server.server_port}'
    seed = Path('C:/FTESurf-private/keys/ftesurf-updates/seed').read_bytes()
    serial = 0
    def publish(version):
        nonlocal serial
        serial += 1
        output = root / f'feed-{serial}'
        updatefeed.build({'win64': stage}, output, version, [url], seed)
        for obj in (output / 'objects').glob('*/*'):
            dest = http / 'objects' / obj.parent.name / obj.name
            dest.parent.mkdir(parents=True, exist_ok=True); shutil.copyfile(obj, dest)
        shutil.copyfile(output / 'update.json', http / 'update.json')
        return (http / 'update.json').read_bytes()
    baseline = publish('0.1.24'); bm = updatefeed.verify(baseline)
    control = root / 'control-stage'; shutil.copytree(stage, control)
    fixture.write_bytes(b'new updater control\n'); upgrade = publish('0.1.25'); um = updatefeed.verify(upgrade)
    processes = []
    def install(name, permission):
        dest = root / name; shutil.copytree(control, dest)
        meta = dest / '.ftesurf-updater'; meta.mkdir()
        (meta / 'consent').write_text(str(permission) + '\n')
        (meta / 'state.json').write_text(json.dumps({'version': '0.1.24', 'files': {f['path']: f['hash'] for f in bm['files']}}))
        (meta / 'installed.json').write_bytes(baseline)
        (dest / 'ftesurf/data').mkdir(exist_ok=True)
        (dest / 'ftesurf/data/consent.txt').write_text('version 1\n')
        for rel, content in protected.items():
            p = dest / rel; p.parent.mkdir(parents=True, exist_ok=True); p.write_bytes(content)
        return dest
    def sentinels(dest):
        for rel, content in protected.items(): assert (dest / rel).read_bytes() == content, rel
    def logs(dest, name):
        return '\n'.join(p.read_text(errors='replace') for p in (dest / 'ftesurf/logs').glob(name + '*.log'))
    def wait_actor(p, dest, name, actor):
        until = time.monotonic() + 30
        while time.monotonic() < until:
            text = logs(dest, name)
            if actor in text: return text
            assert p.poll() is None, f'client exited before {actor}'
            time.sleep(0.05)
        raise AssertionError('missing actor: ' + actor)
    # P823: no Updates screen. Its buttons were the menu's way into these engine commands;
    # Restart to update is the title menu's corner button.
    UPDATE_CMDS = {'mu_enable': 'update_permission 1', 'mu_disable': 'update_permission 0',
                   'mu_off': 'update_permission 0', 'mu_check': 'update_check force'}
    def click(id):
        if id in UPDATE_CMDS: return UPDATE_CMDS[id] + '\nwait 60\n'
        return f'ui_hover @{id}\nwait 5\nui_mouse down\nwait 5\nui_mouse up\nwait 60\n'
    def start(dest, name, steps, env=None, manifest_url=None):
        cfgdir = dest / 'ftesurf/cfg/test'; cfgdir.mkdir(parents=True, exist_ok=True)
        (cfgdir / (name + '.cfg')).write_text('cfg_save_auto 0\ncl_idlefps 0\ncl_maxfps 100\nvid_fullscreen 0\nvid_width 1280\nvid_height 720\nvolume 0\nmusicvolume 0\n'
            f'developer 1\nlog_developer 1\nlog_name {name}\nlog_enable 1\n'
            f'update_allow_insecure 1\nupdate_manifest_url "{manifest_url or url + "/update.json"}"\n'
            f'name UpdaterRig\nruleset_allow_in 1\nin 2 exec cfg/test/{name}-steps.cfg\n')
        (cfgdir / (name + '-steps.cfg')).write_text('cfg_save_auto 0\nmenu_restart\nwait 60\nwait 100\n' + steps)
        stdout = (dest / (name + '-stdout.log')).open('wb')
        p = subprocess.Popen([str(dest / 'ftesurf64.exe'), '-nohome', '-basedir', str(dest), '-manifest', str(dest / 'default.fmf'), '-window',
                              '+set', 'cfg_save_auto', '0', '+set', 'name', 'UpdaterRig', '+exec', f'cfg/test/{name}.cfg'],
                             cwd='C:/FTESurf', stdout=stdout, stderr=subprocess.STDOUT, env=env)
        job = owned_job(p)
        processes.append((p, stdout, job)); return p
    def finish(p, dest, name):
        p.wait(timeout=45)
        assert p.returncode == 0, f'client exit {p.returncode:#x}'
        sentinels(dest)
        text = logs(dest, name)
        for line in text.splitlines():
            if any(k in line for k in ['ui_update_probe:', 'ui_mouse:', 'ui_hover: no control', 'update:', 'update state', 'last error', 'handoff-actor:']): print(line)
        assert 'ui_update_probe:' in text, 'menu actor missing'
        assert 'ui_hover: no control' not in text, 'button not drawn'
        return text
    def objects(): return sum(n for p, n in hits.items() if p.startswith('/objects/'))
    def adapter(dest, linked=False, provision=True):
        source = root / 'handoff-adapter.c'; source.write_text(ADAPTER)
        target = root / 'handoff-adapter.exe'
        compile_env = dict(os.environ, PATH='C:/msys64/ucrt64/bin;C:/msys64/usr/bin;' + os.environ['PATH'], TEMP=str(root), TMP=str(root), TMPDIR=str(root))
        r = subprocess.run(['C:/msys64/ucrt64/bin/gcc.exe', '-municode', '-Wall', '-Wextra', '-O2', '-static', str(source), '-o', str(target)], env=compile_env, capture_output=True, text=True)
        (root / 'adapter-build.log').write_text(r.stdout + r.stderr)
        assert r.returncode == 0 and not r.stderr, f'adapter build must be warning-free: exit {r.returncode:#x}, {r.stderr}'
        if provision:
            if linked: (dest / 'ftesurf-launcher.exe').symlink_to(target)
            else: shutil.copyfile(target, dest / 'ftesurf-launcher.exe')
        cfgdir = dest / 'ftesurf/cfg/test'; cfgdir.mkdir(parents=True, exist_ok=True)
        (cfgdir / 'handoff-return.cfg').write_text('cfg_save_auto 0\ncl_idlefps 0\ncl_maxfps 100\nvid_fullscreen 0\nvolume 0\nmusicvolume 0\n'
            'log_name handoff-return\nlog_enable 1\ndeveloper 1\nlog_developer 1\n'
            f'update_allow_insecure 1\nupdate_manifest_url "{url}/update.json"\n'
            'ruleset_allow_in 1\necho handoff-actor: real returning game\nin 3 quit\n')
        return dict(os.environ, OWNED_UPDATER_ADAPTER_LOG=str(dest / 'adapter.log'), OWNED_UPDATER_LAUNCHER=str(a.launcher.resolve()), OWNED_UPDATER_URL=url + '/update.json', OWNED_UPDATER_LAUNCHER_LOG=str(dest / 'launcher.log'))
    def returned(dest, version):
        until = time.monotonic() + 45
        while time.monotonic() < until:
            adapter_text = (dest / 'adapter.log').read_text(errors='replace') if (dest / 'adapter.log').exists() else ''
            if 'launcher_exit=' in adapter_text: break
            time.sleep(0.05)
        assert 'launcher_exit=0' in adapter_text, adapter_text
        assert f'FTESurf {version} is ready.' in (dest / 'launcher.log').read_text(errors='replace'), 'real launcher update actor missing'
        assert 'arg1=--dir' in adapter_text and f'arg2={dest.as_posix()}/.' in adapter_text.replace('\\', '/') and 'arg3=--wait-for-game' in adapter_text and 'arg4=--yes' in adapter_text, adapter_text
        assert 'handoff-actor: real returning game' in logs(dest, 'handoff-return'), 'real Rust launch did not act'
        assert json.loads((dest / '.ftesurf-updater/state.json').read_text())['version'] == version
        sentinels(dest)
    try:
        if a.arm in ['all', 'recovery-version']:
            for case in ['older', 'ledger']:
                dest = install('recovery-' + case, 0); hits.clear()
                (dest / fixture_rel).write_bytes(fixture.read_bytes())
                meta = dest / '.ftesurf-updater'
                state = {'version': '0.1.25', 'files': {f['path']: f['hash'] for f in um['files']}}
                (meta / 'state.json').write_bytes(b'{broken recovery ledger' if case == 'ledger' else json.dumps(state).encode())
                (meta / 'installed.json').write_bytes(upgrade)
                entry = next(f for f in bm['files'] if f['path'] == fixture_rel)
                recovery = meta / 'ingame'; (recovery / 'staged').mkdir(parents=True)
                (recovery / 'manifest.json').write_bytes(baseline)
                marker = json.dumps({'attempts': 1, 'version': '0.1.24', 'files': [{'p': entry['path'], 'h': entry['hash'], 's': entry['size'], 'x': 0}]}).encode()
                (recovery / 'journal.json').write_bytes(marker)
                (recovery / 'staged' / entry['hash']).write_bytes((control / fixture_rel).read_bytes())
                p = start(dest, 'recovery-' + case, 'ui_update_probe\nquit\n')
                expected = 'Older signed recovery release.' if case == 'older' else 'Cannot read the update recovery ledger.'
                fatal = owned_error(p, expected); (dest / 'fatal.log').write_text(fatal)
                assert not hits and (dest / fixture_rel).read_bytes() == fixture.read_bytes()
                assert (recovery / 'journal.json').read_bytes() == marker
                assert (recovery / 'staged' / entry['hash']).is_file()
                sentinels(dest)
                print('PASS native cold ' + case + ' recovery guard: OWNED fatal actor before network/mount/replacement, journal/cache intact')
        if a.arm in ['all', 'permission-link']:
            dest = install('permission-link', 0); hits.clear()
            target = root / 'permission-target.txt'; target.write_bytes(b'owned permission target\n')
            link = dest / '.ftesurf-updater/consent.tmp'; link.symlink_to(target)
            try:
                p = start(dest, 'permission-link', click('mu_enable') + 'wait 400\nui_update_probe\nupdate_info\nquit\n')
                text = finish(p, dest, 'permission-link')
                assert 'linked permission path; permission was not changed' in text
                assert 'consent=0 state=disabled' in text and not hits
                assert target.read_bytes() == b'owned permission target\n'
                assert (dest / '.ftesurf-updater/consent').read_text() == '0\n'
            finally:
                if link.is_symlink(): link.unlink()
                # A pre-fix control may have moved the link to the final consent name.
                consent = dest / '.ftesurf-updater/consent'
                if consent.is_symlink(): consent.unlink()
            print('PASS real consent.tmp file symlink: target/permission unchanged, ZERO requests')
        if a.arm in ['all', 'restart-link']:
            dest = install('restart-link', 1); hits.clear(); env = adapter(dest, linked=True)
            try:
                steps = 'wait 400\nui_update_probe\n' + click('mu_restart') + 'ui_update_probe\nupdate_info\nupdate_error\necho handoff-actor: refused linked bootstrap\nscreenshot linked.png\nquit\n'
                p = start(dest, 'restart-link', steps, env); text = finish(p, dest, 'restart-link')
                assert 'linked launcher path; restart was not started' in text and 'handoff-actor: refused linked bootstrap' in text
                assert '"update_error" is "linked launcher path; restart was not started.' in text
                assert 'Use a regular local launcher beside FTESurf, then retry.' in text
                assert not (dest / 'adapter.log').exists(), 'linked executable was spawned'
            finally: (dest / 'ftesurf-launcher.exe').unlink()
            print('PASS real launcher file symlink: restart refused BEFORE process spawn, current game survives')
        if a.arm in ['all', 'toggle']:
            dest = install('toggle', 0); hits.clear()
            steps = click('mu_enable') + 'wait 400\nui_update_probe\nupdate_info\n'
            steps += click('mu_disable') + 'ui_update_probe\nwait 60\n'
            steps += click('mu_enable') + 'wait 400\nui_update_probe\nupdate_info\nscreenshot toggle.png\nquit\n'
            p = start(dest, 'toggle', steps); text = finish(p, dest, 'toggle')
            probes = [l for l in text.splitlines() if 'ui_update_probe:' in l]
            assert len(probes) == 3 and 'consent=1 state=restart' in probes[0] and 'consent=0 state=disabled' in probes[1], probes
            assert 'consent=1 state=uptodate' in probes[2], probes[2]
            assert hits['/update.json'] == 2 and objects() == 1, dict(hits)
            assert (dest / '.ftesurf-updater/consent').read_text() == '1\n'
            print('PASS actual enable/disable/re-enable clicks: stored permission and TWO checks, ONE object')
        if a.arm in ['all', 'missing']:
            dest = install('missing', 1); hits.clear()
            steps = 'wait 400\nui_update_probe\n' + click('mu_restart') + 'ui_update_probe\nupdate_info\nupdate_error\necho handoff-actor: survived missing launcher\nscreenshot missing.png\nquit\n'
            p = start(dest, 'missing', steps); text = finish(p, dest, 'missing')
            assert 'launcher is missing or could not start' in text and 'handoff-actor: survived missing launcher' in text
            probes = [line for line in text.splitlines() if 'ui_update_probe:' in line]
            assert len(probes) == 2 and all('consent=1 state=restart screen=0 client=1' in line for line in probes), probes
            reason = 'Restart was not started: launcher is missing or could not start.'
            assert f'last error   : {reason}' in text and f'"update_error" is "{reason}' in text, 'failed restart did not publish its pane error'
            assert 'https://proto.bar/ftesurf/, put it beside FTESurf and retry.' in text
            assert list((dest / 'ftesurf/screenshots').glob('missing*.png')), 'pane screenshot missing'
            assert hits['/update.json'] == 1 and objects() == 1
            print('PASS missing bootstrap: actual click survives with pending state and actionable read-only pane error (inspect PNG)')
        if a.arm in ['all', 'missing']:
            dest = install('missing-engine', 1); hits.clear()
            engine_bytes = (stage / 'ftesurf64.exe').read_bytes()
            try:
                with (stage / 'ftesurf64.exe').open('ab') as f: f.write(b'owned missing-launcher trailer')
                publish('0.1.25')
                steps = 'wait 400\nui_update_probe\n' + click('mu_restart') + 'ui_update_probe\nupdate_info\nupdate_error\nscreenshot missing-engine.png\nquit\n'
                p = start(dest, 'missing-engine', steps); text = finish(p, dest, 'missing-engine')
                probes = [line for line in text.splitlines() if 'ui_update_probe:' in line]
                assert len(probes) == 2 and all('consent=1 state=launcher screen=0 client=1' in line for line in probes), probes
                assert f'last error   : {reason}' in text and f'"update_error" is "{reason}' in text
                assert hits['/update.json'] == 1 and objects() == 0, dict(hits)
                assert (dest / fixture_rel).read_bytes() == b'old updater control\n'
                assert (dest / 'ftesurf64.exe').read_bytes() == engine_bytes
                print('PASS missing bootstrap for binary delta: launcher-required state retained, pane error published, ZERO objects/live mutation')
            finally:
                (stage / 'ftesurf64.exe').write_bytes(engine_bytes)
                (http / 'update.json').write_bytes(upgrade)
        if a.arm in ['all', 'missing']:
            dest = install('missing-retry', 1); hits.clear()
            env = adapter(dest, provision=False)
            steps = 'wait 400\nui_update_probe\n' + click('mu_restart') + 'ui_update_probe\nupdate_info\nupdate_error\necho handoff-actor: missing launcher observed\nwait 1000\n'
            steps += click('mu_restart') + 'update_info\nupdate_error\necho handoff-actor: cfg tail before retry quit\n'
            p = start(dest, 'missing-retry', steps, env)
            text = wait_actor(p, dest, 'missing-retry', 'handoff-actor: missing launcher observed')
            assert reason in text and 'state=restart' in text and not (dest / 'adapter.log').exists()
            shutil.copyfile(root / 'handoff-adapter.exe', dest / 'ftesurf-launcher.exe')
            text = finish(p, dest, 'missing-retry')
            retry = text.split('handoff-actor: missing launcher observed', 1)[1]
            assert 'last error' not in retry and '"update_error" is ""' in retry, 'successful same-game retry retained the spawn failure'
            returned(dest, '0.1.25')
            assert hits['/update.json'] == 2 and objects() == 1, dict(hits)
            assert (dest / fixture_rel).read_bytes() == fixture.read_bytes()
            print('PASS same-game missing-bootstrap retry -> real Rust -> real returning engine; error cleared, ZERO additional objects')
        if a.arm in ['all', 'held']:
            dest = install('held', 1); hits.clear()
            kernel = ctypes.WinDLL('kernel32', use_last_error=True)
            kernel.CreateFileW.argtypes = [w.LPCWSTR, w.DWORD, w.DWORD, w.LPVOID, w.DWORD, w.DWORD, w.HANDLE]
            kernel.CreateFileW.restype = w.HANDLE; kernel.CloseHandle.argtypes = [w.HANDLE]
            handle = kernel.CreateFileW(str(dest / fixture_rel), 0x80000000, 3, None, 3, 0x80, None)
            assert handle != w.HANDLE(-1).value, ctypes.get_last_error()
            try:
                p = start(dest, 'held', 'wait 400\nui_update_probe\nupdate_info\nquit\n'); text = finish(p, dest, 'held')
                assert 'is locked, will finish on next launch' in text and 'state=restart' in text
                assert (dest / fixture_rel).read_bytes() == b'old updater control\n'
                assert (dest / '.ftesurf-updater/ingame/journal.json').exists()
                assert json.loads((dest / '.ftesurf-updater/state.json').read_text())['version'] == '0.1.24'
                assert objects() == 1
            finally: assert kernel.CloseHandle(handle)
            hits.clear(); p = start(dest, 'held-return', 'wait 200\nui_update_probe\nupdate_info\nquit\n'); text = finish(p, dest, 'held-return')
            assert (dest / fixture_rel).read_bytes() == fixture.read_bytes() and objects() == 0
            assert not (dest / '.ftesurf-updater/ingame/journal.json').exists()
            assert json.loads((dest / '.ftesurf-updater/state.json').read_text())['version'] == '0.1.25'
            print('PASS real held live file: defer old bytes/version; cold recovery completes after handle release, ZERO objects')
        if a.arm in ['all', 'outage']:
            for kind in ['feed', 'object']:
                dest = install('outage-' + kind, 1); hits.clear(); failure[kind] = True
                steps = 'wait 400\nui_update_probe\nupdate_info\necho handoff-actor: outage observed\nwait 500\n'
                steps += click('mu_check') + 'wait 400\nui_update_probe\nupdate_info\nquit\n'
                p = start(dest, 'outage-' + kind, steps)
                text = wait_actor(p, dest, 'outage-' + kind, 'handoff-actor: outage observed')
                assert 'state=error' in text and hits['/update.json'] >= 1
                assert (dest / fixture_rel).read_bytes() == b'old updater control\n'
                assert not (dest / '.ftesurf-updater/ingame/journal.json').exists()
                assert json.loads((dest / '.ftesurf-updater/state.json').read_text())['version'] == '0.1.24'
                failure[kind] = False
                text = finish(p, dest, 'outage-' + kind)
                assert 'state=restart' in text and (dest / fixture_rel).read_bytes() == fixture.read_bytes()
                assert 'last error' not in text.split('handoff-actor: outage observed', 1)[1], 'successful retry retained a stale native error'
                print('PASS native ' + kind + ' HTTP 503: error actor and no live mutation; Check now click retries successfully')
        if a.arm in ['all', 'outage']:
            dest = install('outage-connect', 1); hits.clear()
            with socket.socket() as unused:
                unused.bind(('127.0.0.1', 0)); port = unused.getsockname()[1]
            steps = 'wait 400\nui_update_probe\nupdate_info\necho handoff-actor: connection refusal observed\nwait 100\n'
            steps += f'update_manifest_url "{url}/update.json"\n' + click('mu_check') + 'wait 400\nui_update_probe\nupdate_info\nquit\n'
            p = start(dest, 'outage-connect', steps, manifest_url=f'http://127.0.0.1:{port}/update.json')
            text = wait_actor(p, dest, 'outage-connect', 'handoff-actor: connection refusal observed')
            assert 'state=error' in text and not hits, 'connection-refusal actor missing or wrong service contacted'
            assert (dest / fixture_rel).read_bytes() == b'old updater control\n'
            assert not (dest / '.ftesurf-updater/ingame/journal.json').exists()
            text = finish(p, dest, 'outage-connect')
            assert 'state=restart' in text and hits['/update.json'] == 1 and objects() == 1
            assert (dest / fixture_rel).read_bytes() == fixture.read_bytes()
            assert 'last error' not in text.split('handoff-actor: connection refusal observed', 1)[1]
            print('PASS native loopback connection refusal: error actor, ZERO requests to live service/no mutation, successful explicit retry')
        if a.arm in ['all', 'wait-lock']:
            dest = install('wait-lock', 0); hits.clear()
            p = start(dest, 'wait-lock', 'ui_update_probe\necho handoff-actor: waiting game lock\nwait 500\nquit\n')
            wait_actor(p, dest, 'wait-lock', 'handoff-actor: waiting game lock')
            out = (dest / 'launcher.log').open('wb')
            child = subprocess.Popen([str(a.launcher.resolve()), '--dir', str(dest), '--yes', '--no-launch', '--wait-for-game', '--allow-insecure', '--manifest-url', url + '/update.json'], cwd=dest, stdout=out, stderr=subprocess.STDOUT)
            processes.append((child, out, owned_job(child)))
            time.sleep(0.75)
            assert child.poll() is None and p.poll() is None and not hits, 'launcher did not wait before requests'
            assert (dest / '.ftesurf-updater/consent').read_text() == '0\n', 'waiting launcher changed permission before lock'
            finish(p, dest, 'wait-lock'); child.wait(timeout=30)
            assert child.returncode == 0 and hits['/update.json'] == 1 and objects() == 1
            assert (dest / fixture_rel).read_bytes() == fixture.read_bytes()
            assert (dest / '.ftesurf-updater/consent').read_text() == '1\n'
            print('PASS actual native lock -> real Rust --wait-for-game: ZERO requests/writes while blocked; then ONE verified update')
        if a.arm in ['all', 'restart']:
            dest = install('restart', 1); hits.clear()
            # Force a benign signed root delta so the native actor MUST hand off, not apply it.
            with (stage / 'ftesurf64.exe').open('ab') as f: f.write(b'owned handoff trailer')
            publish('0.1.26')
            env = adapter(dest)
            p = start(dest, 'restart', 'wait 400\nui_update_probe\nupdate_info\n' + click('mu_restart') + 'echo handoff-actor: cfg tail before queued quit\n', env)
            text = finish(p, dest, 'restart')
            assert 'state=launcher' in text
            returned(dest, '0.1.26')
            assert (dest / 'ftesurf64.exe').read_bytes() == (stage / 'ftesurf64.exe').read_bytes()
            assert objects() == 2, dict(hits)
            print('PASS fixed native spawn -> real Rust wait/update -> real returning engine actor, normal exits, exact argv and protected bytes')
        # Success requires the adapter/launcher/returning-game descendants to have exited, too.
        class Accounting(ctypes.Structure):
            _fields_ = [(name, ctypes.c_int64) for name in ['user', 'kernel', 'period_user', 'period_kernel']] + [(name, w.DWORD) for name in ['faults', 'total', 'active', 'terminated']]
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel.QueryInformationJobObject.argtypes = [w.HANDLE, ctypes.c_int, w.LPVOID, w.DWORD, w.LPVOID]
        for p, out, job in processes:
            until = time.monotonic() + 5
            while True:
                info = Accounting()
                assert kernel.QueryInformationJobObject(job, 1, ctypes.byref(info), ctypes.sizeof(info), None), ctypes.get_last_error()
                if not info.active: break
                assert time.monotonic() < until, 'owned descendants survived a successful arm'
                time.sleep(0.05)
        (root / 'process-cleanup.json').write_text(json.dumps({'owned_jobs': len(processes), 'active_descendants': 0}))
    finally:
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel.CloseHandle.argtypes = [w.HANDLE]
        for p, out, job in processes:
            # Closing the job contains even a failed adapter's returning game. No PID/name kills.
            assert kernel.CloseHandle(job)
            if p.poll() is None: p.wait(timeout=10)
            out.close()
        server.shutdown(); server.server_close(); thread.join(timeout=5)
    print('Handoff arms passed; owned evidence retained at', root)


if __name__ == '__main__': main()
