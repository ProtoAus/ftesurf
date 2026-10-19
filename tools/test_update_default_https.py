#!/usr/bin/env python3
"""Windows default-HTTPS native/menu acceptance, using an exact existing release.

No signing keys, URL overrides, adapters, publication or real install writes.
Creates only a fresh owned synthetic runtime. Production availability/version drift
is a failed acceptance attempt, never permission to change the public feed.
"""
import argparse
import ctypes
from ctypes import wintypes as w
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import threading
import time
import urllib.request

from test_update_handoff import owned_job
import updatefeed

FEED = 'https://proto.bar/ftesurf/update.json'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def digest(data):
    return hashlib.blake2b(data, digest_size=32).hexdigest()


def utc():
    return datetime.now(timezone.utc).isoformat()


def argv_tokens(command):
    shell, kernel = ctypes.WinDLL('shell32', use_last_error=True), ctypes.WinDLL('kernel32', use_last_error=True)
    shell.CommandLineToArgvW.argtypes = [w.LPCWSTR, ctypes.POINTER(ctypes.c_int)]
    shell.CommandLineToArgvW.restype = ctypes.POINTER(w.LPWSTR)
    kernel.LocalFree.argtypes = [w.HLOCAL]; kernel.LocalFree.restype = w.HLOCAL
    count = ctypes.c_int()
    pointer = shell.CommandLineToArgvW(command, ctypes.byref(count))
    assert pointer, ctypes.get_last_error()
    try:
        return [pointer[i] for i in range(count.value)]
    finally:
        assert not kernel.LocalFree(pointer), ctypes.get_last_error()


def grade_exits(rows):
    conhost = Path(os.environ['SystemRoot']) / 'System32/conhost.exe'
    for row in rows:
        if Path(row['image']).resolve() == conhost and row['exit'] == 109:
            row['classification'] = 'OS console host ERROR_BROKEN_PIPE; product exits graded separately'
        else:
            assert row['exit'] == 0, ('owned process failed', row)


def local_path(path):
    # Rust's canonical executable argv uses the Win32 extended drive prefix.
    text = str(path)
    if text.startswith('\\\\?\\'):
        text = text[4:]
    return Path(text).resolve()


def grade_handoff(rows, dest, initial_pid):
    launchers = [r for r in rows if Path(r['image']).resolve() == dest / 'ftesurf-launcher.exe']
    returns = [r for r in rows if r['pid'] != initial_pid and Path(r['image']).resolve() == dest / 'ftesurf64.exe']
    assert len(launchers) == len(returns) == 1, ('real handoff census missing', rows)
    launch = argv_tokens(launchers[0]['argv'])
    assert len(launch) == 5 and local_path(launch[0]) == dest / 'ftesurf-launcher.exe', launch
    assert launch[1] == '--dir' and local_path(launch[2]) == dest, launch
    assert launch[3:] == ['--wait-for-game', '--yes'], launch
    returned = argv_tokens(returns[0]['argv'])
    assert len(returned) == 3 and local_path(returned[0]) == dest / 'ftesurf64.exe', returned
    assert returned[1:] == ['-manifest', 'default.fmf'], returned
    conhost = Path(os.environ['SystemRoot']) / 'System32/conhost.exe'
    assert all(r['pid'] == initial_pid or r in launchers or r in returns or Path(r['image']).resolve() == conhost for r in rows)


def grade_return(text):
    assert any('ui_update_probe: consent=1 state=uptodate screen=0 client=1' in line for line in text.splitlines()), 'returning title menu did not act'
    assert 'manifest     : ' + FEED in text


class OwnedGame:
    """Contain before resume; retain own process handles/argv/exit census."""
    def __init__(self, args, dest, evidence, name):
        self.dest, self.evidence, self.name = dest, evidence, name
        self.rows, self.handles, self.errors = {}, {}, []
        self.stop = threading.Event()
        self.k = ctypes.WinDLL('kernel32', use_last_error=True)
        self.k.QueryInformationJobObject.argtypes = [w.HANDLE, ctypes.c_int, w.LPVOID, w.DWORD, w.LPVOID]
        self.k.OpenProcess.argtypes = [w.DWORD, w.BOOL, w.DWORD]
        self.k.OpenProcess.restype = w.HANDLE
        self.k.QueryFullProcessImageNameW.argtypes = [w.HANDLE, w.DWORD, w.LPWSTR, ctypes.POINTER(w.DWORD)]
        self.k.GetExitCodeProcess.argtypes = [w.HANDLE, ctypes.POINTER(w.DWORD)]
        self.k.CloseHandle.argtypes = [w.HANDLE]
        self.nt = ctypes.WinDLL('ntdll')
        self.nt.NtQueryInformationProcess.argtypes = [w.HANDLE, w.ULONG, w.LPVOID, w.ULONG, ctypes.POINTER(w.ULONG)]
        self.nt.NtResumeProcess.argtypes = [w.HANDLE]
        self.nt.NtResumeProcess.restype = ctypes.c_long
        self.out = (evidence / (name + '-stdout.log')).open('wb')
        self.p = subprocess.Popen(args, cwd='C:/FTESurf', stdin=subprocess.PIPE,
                                  stdout=self.out, stderr=subprocess.STDOUT, creationflags=4)
        self.job = None
        self.thread = None
        try:
            self.job = owned_job(self.p)
            self.capture()
            self.thread = threading.Thread(target=self.monitor, daemon=True)
            self.thread.start()
            assert self.nt.NtResumeProcess(int(self.p._handle)) == 0, 'resume failed'
        except BaseException:
            self.close()
            raise

    def pids(self):
        buf = ctypes.create_string_buffer(8 + 64 * ctypes.sizeof(ctypes.c_size_t))
        assert self.k.QueryInformationJobObject(self.job, 3, buf, len(buf), None), ctypes.get_last_error()
        assigned, listed = (ctypes.c_ulong * 2).from_buffer(buf)
        assert assigned == listed and listed <= 64, 'truncated job census'
        return list((ctypes.c_size_t * listed).from_buffer(buf, 8))

    def argv(self, handle):
        size = w.ULONG()
        self.nt.NtQueryInformationProcess(handle, 60, None, 0, ctypes.byref(size))
        assert size.value, 'owned process argv size unavailable'
        buf = ctypes.create_string_buffer(size.value)
        assert self.nt.NtQueryInformationProcess(handle, 60, buf, len(buf), ctypes.byref(size)) == 0, 'owned argv read failed'
        class Unicode(ctypes.Structure):
            _fields_ = [('length', w.USHORT), ('maximum', w.USHORT), ('data', w.LPVOID)]
        text = Unicode.from_buffer(buf)
        return ctypes.wstring_at(text.data, text.length // 2)

    def capture(self):
        for pid in self.pids():
            if pid in self.rows:
                continue
            handle = self.k.OpenProcess(0x1000 | 0x100000, False, pid)
            assert handle, ('owned process handle unavailable', pid, ctypes.get_last_error())
            self.handles[pid] = handle
            buf, size = ctypes.create_unicode_buffer(32768), w.DWORD(32768)
            assert self.k.QueryFullProcessImageNameW(handle, 0, buf, ctypes.byref(size)), ctypes.get_last_error()
            self.rows[pid] = {'pid': pid, 'image': buf.value, 'argv': self.argv(handle), 'observed_utc': utc()}
            self.save()

    def save(self):
        (self.evidence / (self.name + '-processes.json')).write_text(json.dumps(list(self.rows.values()), indent=2) + '\n')

    def monitor(self):
        try:
            while not self.stop.wait(.02):
                self.capture()
        except BaseException as error:
            self.errors.append(repr(error))

    def logs(self, prefix=None):
        return '\n'.join(p.read_text(encoding='utf-8', errors='replace')
                         for p in (self.dest / 'ftesurf/logs').glob((prefix or self.name) + '*.log'))

    def wait(self, actor, prefix=None, timeout=45):
        until = time.monotonic() + timeout
        while time.monotonic() < until:
            assert not self.errors, self.errors
            text = self.logs(prefix)
            if actor in text:
                return text
            assert self.p.poll() is None or self.pids(), 'all owned processes exited before ' + actor
            time.sleep(.05)
        raise AssertionError('missing actor: ' + actor)

    def send(self, command):
        assert len(command.encode()) < 255
        assert self.p.poll() is None, 'initiator exited before command'
        self.p.stdin.write((command + '\n').encode())
        self.p.stdin.flush()

    def finish(self, restart=False):
        self.p.wait(timeout=45)
        until = time.monotonic() + 60
        while self.pids():
            assert not self.errors, self.errors
            assert time.monotonic() < until, 'owned descendants did not exit normally'
            time.sleep(.05)
        self.stop.set()
        self.thread.join(timeout=5)
        assert not self.thread.is_alive() and not self.errors, self.errors
        for pid, handle in self.handles.items():
            code = w.DWORD()
            assert self.k.GetExitCodeProcess(handle, ctypes.byref(code)), ctypes.get_last_error()
            self.rows[pid]['exit'] = code.value
        # Persist the COMPLETE census before any verdict can fail.
        self.save()
        (self.evidence / (self.name + '-precleanup.json')).write_text(json.dumps({'active_before_cleanup': 0, 'initial_exit': self.p.returncode}))
        assert self.p.returncode == 0, ('initial exit', self.p.returncode)
        grade_exits(list(self.rows.values()))
        if restart:
            grade_handoff(list(self.rows.values()), self.dest, self.p.pid)
        self.save()
        return {'initial_exit': self.p.returncode, 'active_before_cleanup': 0, 'processes': list(self.rows.values())}

    def close(self):
        self.stop.set()
        if self.thread:
            self.thread.join(timeout=5)
            assert not self.thread.is_alive(), 'monitor did not stop'
        if self.job:
            # Failure containment only; success is measured before closure.
            assert self.k.CloseHandle(self.job), ctypes.get_last_error()
            self.job = None
        if self.p.poll() is None:
            self.p.terminate()
            self.p.wait(timeout=10)
        for handle in self.handles.values():
            assert self.k.CloseHandle(handle), ctypes.get_last_error()
        self.handles.clear()
        self.p.stdin.close()
        self.out.close()


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--engine', type=Path, required=True)
    ap.add_argument('--engine-sha256', required=True)
    ap.add_argument('--archive', type=Path, required=True)
    ap.add_argument('--receipt', type=Path, required=True)
    ap.add_argument('--feed', type=Path, required=True, help='previously fetched production signed feed; require exact fresh HTTPS match')
    ap.add_argument('--runtime-root', type=Path, required=True)
    ap.add_argument('--evidence', type=Path, required=True)
    a = ap.parse_args()
    assert os.name == 'nt'
    engine, archive = a.engine.resolve(strict=True), a.archive.resolve(strict=True)
    dest, evidence = a.runtime_root.absolute(), a.evidence.absolute()
    assert not dest.exists() and not evidence.exists(), 'fresh owned roots required'
    assert dest.parent.is_dir() and evidence.parent.is_dir(), 'owned parent roots required'
    dest.mkdir(); evidence.mkdir()
    (dest / 'OWNER.md').write_text('Synthetic default HTTPS native test; only owned jobs/paths. Evidence: ' + str(evidence) + '\n')
    result = {'verdict': 'FAIL', 'started_utc': utc(), 'harness_sha256': sha(Path(__file__).read_bytes()), 'arms': []}
    protected = {}
    try:
        assert sha(engine.read_bytes()) == a.engine_sha256
        receipt = json.loads(a.receipt.read_text(encoding='utf-8-sig'))
        assert archive.name == receipt['archive']['name'] and archive.stat().st_size == receipt['archive']['bytes']
        assert sha(archive.read_bytes()).upper() == receipt['archive']['sha256'].upper()
        signed = a.feed.read_bytes()
        with urllib.request.urlopen(FEED, timeout=30) as response:
            assert response.url == FEED and response.read(2*1024*1024+1) == signed, 'production feed drift'
        manifest = updatefeed.verify(signed)
        assert manifest['version'] == receipt['version']
        assert all(f['size'] <= 32*1024*1024 for f in manifest['files']), 'native policy oversize row'
        assert all(url.startswith('https://') for url in manifest['mirrors'])
        unpack = subprocess.run(['C:/Program Files/7-Zip/7z.exe', 'x', '-y', '-bso0', '-bsp0', '-o' + str(dest), str(archive)],
                                capture_output=True, timeout=90)
        (evidence / 'extract.log').write_bytes(unpack.stdout + unpack.stderr)
        assert unpack.returncode == 0
        expected = receipt['content']['hashes']
        actual = {p.relative_to(dest).as_posix(): sha(p.read_bytes()).upper() for p in dest.rglob('*') if p.is_file() and p.name != 'OWNER.md'}
        (evidence / 'archive-hashes.json').write_text(json.dumps(actual, indent=2) + '\n')
        assert len(actual) == receipt['content']['file_count']
        assert sum((dest / p).stat().st_size for p in actual) == receipt['content']['raw_bytes']
        assert all(actual.get(p) == h.upper() for p, h in expected.items()), 'archive critical receipt mismatch'
        assert actual['ftesurf-launcher.exe'] == receipt['bootstrap']['sha256'].upper()
        assert actual['notices/bootstrap.txt'] == receipt['bootstrap']['notices_sha256'].upper()
        files = {f['path']: f for f in manifest['files'] if f['platform'] in ('all', 'win64')}
        assert set(actual) == set(files) | {'ftesurf-launcher.exe'}, 'archive signed closure mismatch'
        assert 'DISABLEHOMEDIR 1' in (dest / 'default.fmf').read_text(), 'returning game must not use owner home'
        assert all(digest((dest / p).read_bytes()) == f['hash'] and (dest / p).stat().st_size == f['size'] for p, f in files.items())
        result.update(engine_sha256=sha(engine.read_bytes()), archive_sha256=sha(archive.read_bytes()),
                      feed_sha256=sha(signed), version=manifest['version'], bootstrap_sha256=actual['ftesurf-launcher.exe'])
        meta = dest / '.ftesurf-updater'; meta.mkdir()
        state = {'version': manifest['version'], 'files': {p: f['hash'] for p, f in files.items()}}
        (meta / 'state.json').write_text(json.dumps(state))
        (meta / 'installed.json').write_bytes(signed)
        cfgdir = dest / 'ftesurf/cfg/test'; cfgdir.mkdir(parents=True)
        (cfgdir / 'https-return.cfg').write_text('cfg_save_auto 0\n')
        zone = next(p for p in files if p.startswith('ftesurf/maps/zones/local/'))
        protected = {'ftesurf/ftesurf.cfg': b'cfg_save_auto 0\nexec cfg/test/https-return.cfg\n// owned player settings\n',
                     'ftesurf/fs_addons.txt': b'// owned local mounts\n', zone: b'// owned edited zone\n',
                     'ftesurf/data/runs/player-sentinel.rec': b'owned recording\n', 'hl2/player-sentinel.txt': b'owned mounted content\n'}
        for path, data in protected.items():
            leaf = dest / path; leaf.parent.mkdir(parents=True, exist_ok=True); leaf.write_bytes(data)
        (dest / 'ftesurf/data/consent.txt').write_text('version 1\n')
        def guard():
            for path, data in protected.items():
                assert (dest / path).read_bytes() == data, 'changed sentinel: ' + path
            assert sha((dest / 'ftesurf-launcher.exe').read_bytes()).upper() == actual['ftesurf-launcher.exe']
        def start(name):
            (cfgdir / 'https-return.cfg').write_text('cfg_save_auto 0\n')
            (cfgdir / (name + '.cfg')).write_text('cfg_save_auto 0\ncl_idlefps 0\ncl_maxfps 100\nvid_fullscreen 0\nvid_width 1280\nvid_height 720\n'
                'volume 0\nmusicvolume 0\ncon_savehistory 0\ndeveloper 1\nlog_developer 1\n'
                f'log_name {name}\nlog_enable 1\nruleset_allow_in 1\nin 4 exec cfg/test/{name}-steps.cfg\n')
            (cfgdir / (name + '-steps.cfg')).write_text('cfg_save_auto 0\nmenu_restart\nwait 100\nwait 200\necho HTTPS_READY\n')
            return OwnedGame([str(engine), '-plugin', '-nohome', '-basedir', str(dest), '-manifest', str(dest / 'default.fmf'),
                              '-window', '+set', 'cfg_save_auto', '0', '+exec', 'cfg/test/' + name + '.cfg'], dest, evidence, name)
        def probe(game, marker):
            game.send('ui_update_probe; update_info; update_manifest_url; update_allow_insecure; echo ' + marker)
            text = game.wait(marker)
            assert 'manifest     : ' + FEED in text and '"update_allow_insecure" is "0"' in text
            assert 'client=1' in text and 'screen=0' in text and 'ui_hover: no control' not in text
            return text
        def click(game, button, marker):
            # P823: no Updates screen; its buttons were these engine commands.
            cmd = {'mu_off': 'update_permission 0', 'mu_enable': 'update_permission 1'}.get(button)
            # Same console batch: physical input cannot overwrite the SUI cursor
            # between the authentic hover/down/up callbacks on a busy desktop.
            game.send((cmd if cmd else 'ui_hover @' + button + '; ui_mouse down; ui_mouse up') + '; echo ' + marker)
            return game.wait(marker)
        def export_logs():
            for log in (dest / 'ftesurf/logs').glob('https-*.log'):
                (evidence / log.name).write_bytes(log.read_bytes())
            for png in (dest / 'ftesurf/screenshots').glob('https-*.png'):
                (evidence / png.name).write_bytes(png.read_bytes())
        # Authentic consent controls; no permission cvar/file writes.
        g = start('https-control')
        try:
            g.wait('HTTPS_READY')
            assert 'consent=-1' in probe(g, 'HTTPS_UNDECIDED')
            assert not (meta / 'consent').exists()
            before = (meta / 'state.json').read_bytes()
            click(g, 'mu_off', 'HTTPS_OFF_CLICKED')
            assert 'consent=0 state=disabled' in probe(g, 'HTTPS_OFF_PROBED')
            assert (meta / 'consent').read_bytes() == b'0\n' and (meta / 'state.json').read_bytes() == before
            click(g, 'mu_enable', 'HTTPS_ENABLE_CLICKED')
            g.wait('up to date')
            text = probe(g, 'HTTPS_ENABLED')
            assert 'consent=1 state=uptodate' in text and (meta / 'consent').read_bytes() == b'1\n'
            g.send('screenshot https-control.png; echo HTTPS_CONTROL_DONE; quit')
            row = g.finish(); row['arm'] = 'consent-control'; result['arms'].append(row)
            guard()
        finally:
            g.close(); export_logs()
        content = 'ftesurf/gfx/env/milk.png'
        for name, target, verdict in [('https-content', content, 'restart'), ('https-engine', 'ftesurf64.exe', 'launcher')]:
            assert target in files
            original = (dest / target).read_bytes()
            corrupt = b'owned default-HTTPS subject\n'
            (dest / target).write_bytes(corrupt)
            state = json.loads((meta / 'state.json').read_text()); state['version'] = '0.1.24'; state['files'][target] = '0' * 64
            (meta / 'state.json').write_text(json.dumps(state))
            g = start(name)
            try:
                g.wait('HTTPS_READY')
                g.wait('installed 1 file' if verdict == 'restart' else 'update includes engine binaries')
                text = probe(g, 'HTTPS_SUBJECT_PLANNED')
                assert 'consent=1 state=' + verdict in text
                assert (dest / target).read_bytes() == (original if verdict == 'restart' else corrupt)
                g.send('screenshot ' + name + '.png; echo HTTPS_PANE_CAPTURED')
                g.wait('HTTPS_PANE_CAPTURED')
                # Ordinary synthetic saved-settings hook; native fixed launcher argv unchanged.
                ret = name + '-return'
                (cfgdir / 'https-return.cfg').write_text('cfg_save_auto 0\ncl_idlefps 0\ncl_maxfps 100\nvid_fullscreen 0\nvolume 0\nmusicvolume 0\n'
                    f'log_name {ret}\nlog_enable 1\ndeveloper 1\nlog_developer 1\nruleset_allow_in 1\n'
                    f'echo HTTPS_REAL_RETURNING_GAME\nin 4 exec cfg/test/{ret}-steps.cfg\n')
                (cfgdir / (ret + '-steps.cfg')).write_text('cfg_save_auto 0\nmenu_restart\nwait 100\nwait 200\n'
                    'ui_update_probe\nupdate_info\necho HTTPS_RETURN_PANE_READY\n'
                    f'screenshot {ret}.png\nwait 60\nquit\n')
                click(g, 'mu_restart', 'HTTPS_RESTART_CLICKED')
                g.wait('HTTPS_REAL_RETURNING_GAME', prefix=ret, timeout=60)
                row = g.finish(restart=True)
                returned = g.logs(ret)
                grade_return(returned)
                assert 'HTTPS_RETURN_PANE_READY' in returned
                assert (dest / target).read_bytes() == original
                assert json.loads((meta / 'state.json').read_text())['version'] == manifest['version']
                assert (meta / 'installed.json').read_bytes() == signed
                assert digest((dest / target).read_bytes()) == files[target]['hash'], 'signed object repair actor missing'
                if verdict == 'restart':
                    assert 'update: installed 1 files' in text
                assert not (meta / 'ingame/journal.json').exists()
                row.update(arm=name, target=target, target_blake2b256=files[target]['hash'])
                result['arms'].append(row)
                guard()
            finally:
                g.close(); export_logs()
        for name in ['https-control', 'https-content', 'https-content-return', 'https-engine', 'https-engine-return']:
            assert (evidence / (name + '.png')).is_file(), 'real pane screenshot missing: ' + name
        guard()
        assert all(digest((dest / p).read_bytes()) == f['hash'] for p, f in files.items() if p not in protected)
        result['sentinels'] = {p: sha(data) for p, data in protected.items()}
        result['verdict'] = 'PASS'
    except BaseException as error:
        result['failure'] = repr(error)
        raise
    finally:
        result['finished_utc'] = utc()
        (evidence / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
        print(json.dumps({'verdict': result['verdict'], 'arms': len(result['arms']), 'evidence': str(evidence), 'failure': result.get('failure')}))


if __name__ == '__main__':
    main()
