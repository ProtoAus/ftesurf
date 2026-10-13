#!/usr/bin/env python3
"""Windows OS-denied live-planner/cold-replay controls using a retained signed feed.

No key, pin override, installed game, public feed or deployment. Bind only the
signed loopback mirror (fail if busy). Each synthetic arm is inventoried/exported
and retired; inputs stay read-only. --expect-before requires native misbehavior.
"""
import argparse
from collections import Counter
from contextlib import contextmanager
import ctypes
from ctypes import wintypes as w
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import threading
import time
from urllib.parse import urlsplit

import updatefeed
from test_update_handoff import owned_job
from test_update_native_recovery import digest
from test_ingame_update import owned_error


def sha(data):
    return hashlib.sha256(data).hexdigest()


class ExclusiveHTTPServer(ThreadingHTTPServer):
    allow_reuse_address = False
    allow_reuse_port = False

    def server_bind(self):
        # On Windows SO_REUSEADDR can steal an occupied listener; disabling it
        # alone is not sufficient protection against a second reusable socket.
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()


def busy_port_control():
    with ExclusiveHTTPServer(('127.0.0.1', 0), BaseHTTPRequestHandler) as first:
        address = first.server_address
        try:
            second = ExclusiveHTTPServer(address, BaseHTTPRequestHandler)
        except OSError as error:
            assert error.errno in (13, 10013, 10048) or error.winerror in (10013, 10048), str(error)
            return {'address': list(address), 'bind_error': error.errno, 'clients_launched': 0}
        else:
            second.server_close()
            raise AssertionError('owned busy port accepted duplicate bind')


def kernel32():
    k = ctypes.WinDLL('kernel32', use_last_error=True)
    k.CreateFileW.argtypes = [w.LPCWSTR, w.DWORD, w.DWORD, w.LPVOID, w.DWORD, w.DWORD, w.HANDLE]
    k.CreateFileW.restype = w.HANDLE
    k.CloseHandle.argtypes = [w.HANDLE]
    k.GetFileAttributesW.argtypes = [w.LPCWSTR]
    k.GetFileAttributesW.restype = w.DWORD
    return k


def read_probe(path, expected_error=None):
    k = kernel32()
    attrs = k.GetFileAttributesW(str(path))
    assert attrs != 0xffffffff, 'denied file must demonstrably exist'
    h = k.CreateFileW(str(path), 0x80000000, 7, None, 3, 0x80, None)
    error = ctypes.get_last_error() if h == ctypes.c_void_p(-1).value else 0
    if not error:
        assert k.CloseHandle(h), ctypes.get_last_error()
    assert error == (expected_error or 0), (str(path), error, expected_error)
    return {'read_error': error, 'attributes': attrs}


def security(path):
    adv = ctypes.WinDLL('advapi32', use_last_error=True)
    adv.GetFileSecurityW.argtypes = [w.LPCWSTR, w.DWORD, w.LPVOID, w.DWORD, ctypes.POINTER(w.DWORD)]
    need = w.DWORD()
    adv.GetFileSecurityW(str(path), 4, None, 0, ctypes.byref(need))
    assert need.value > 0, ctypes.get_last_error()
    buf = ctypes.create_string_buffer(need.value)
    assert adv.GetFileSecurityW(str(path), 4, buf, len(buf), ctypes.byref(need)), ctypes.get_last_error()
    return buf.raw


def dacl(descriptor):
    # SetFileSecurity can clear SE_DACL_AUTO_INHERITED without changing a single
    # ACE. Compare actual DACL bytes/protection, not that bookkeeping flag.
    adv = ctypes.WinDLL('advapi32', use_last_error=True)
    adv.GetSecurityDescriptorDacl.argtypes = [w.LPVOID, ctypes.POINTER(w.BOOL), ctypes.POINTER(w.LPVOID), ctypes.POINTER(w.BOOL)]
    buf = ctypes.create_string_buffer(descriptor)
    present, defaulted, acl = w.BOOL(), w.BOOL(), w.LPVOID()
    assert adv.GetSecurityDescriptorDacl(buf, ctypes.byref(present), ctypes.byref(acl), ctypes.byref(defaulted)), ctypes.get_last_error()
    size = ctypes.c_ushort.from_address(acl.value + 2).value if acl.value else 0
    data = ctypes.string_at(acl.value, size) if size else b''
    protected = bool(int.from_bytes(descriptor[2:4], 'little') & 0x1000)
    return present.value, defaulted.value, protected, data


@contextmanager
def denied(path, kind, receipt, expect_replacement=False):
    """Alter only this synthetic leaf, then restore access and prove restoration."""
    read_probe(path)
    original = path.read_bytes()
    k = kernel32()
    handle = descriptor = None
    try:
        if kind == 'share':
            handle = k.CreateFileW(str(path), 0x80000000, 0, None, 3, 0x80, None)
            assert handle != ctypes.c_void_p(-1).value, ctypes.get_last_error()
            receipt['denial'] = read_probe(path, 32)
        else:
            descriptor = security(path)
            # Everyone read-data DENY; no inherited ACL/owner changes or user SID output.
            command = subprocess.run(['icacls', str(path), '/deny', '*S-1-1-0:(RD)'], capture_output=True)
            assert command.returncode == 0, 'owned leaf read-data denial failed'
            receipt['denial'] = read_probe(path, 5)
        receipt['kind'] = kind
        yield
        if expect_replacement:
            # The pre-fix ACL arm replaces the file object itself, discarding
            # its read-deny ACEs. This is the bug actor, not failed setup.
            assert kind == 'acl' and path.read_bytes() != original
            receipt['replacement_access'] = read_probe(path)
        else:
            receipt['still_denied'] = read_probe(path, 32 if kind == 'share' else 5)
    finally:
        if handle is not None and handle != ctypes.c_void_p(-1).value:
            assert k.CloseHandle(handle), ctypes.get_last_error()
        if descriptor is not None:
            adv = ctypes.WinDLL('advapi32', use_last_error=True)
            adv.SetFileSecurityW.argtypes = [w.LPCWSTR, w.DWORD, w.LPVOID]
            buf = ctypes.create_string_buffer(descriptor)
            assert adv.SetFileSecurityW(str(path), 4, buf), 'cannot restore owned leaf DACL'
            assert dacl(security(path)) == dacl(descriptor), 'owned leaf DACL restoration changed ACEs/protection'
            receipt['dacl_restored'] = True
        receipt['restored'] = read_probe(path)
        receipt['original_sha256'] = sha(original)
        receipt['after_sha256'] = sha(path.read_bytes())


def inventory(dest):
    rows = {}
    for p in sorted(dest.rglob('*')):
        assert not p.is_symlink() and not (getattr(p.lstat(), 'st_file_attributes', 0) & 0x400), 'linked runtime path'
        if p.is_file():
            rows[p.relative_to(dest).as_posix()] = {'size': p.stat().st_size, 'sha256': sha(p.read_bytes())}
    return rows


def export(dest, evidence):
    evidence.mkdir()
    (evidence / 'inventory.json').write_text(json.dumps(inventory(dest), indent=2) + '\n')
    for p in dest.rglob('*'):
        rel = p.relative_to(dest)
        if p.is_file() and (p.suffix == '.log' or rel.as_posix().startswith('.ftesurf-updater/') and p.name != 'install.lock'
                            or rel.as_posix().startswith('ftesurf/cfg/test/')):
            target = evidence / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(p, target)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    for name in ['engine', 'feed', 'runtime-root', 'evidence']:
        ap.add_argument('--' + name, type=Path, required=True)
    ap.add_argument('--objects', type=Path, action='append', required=True, help='read-only closure roots; repeat for retained synthetic additions')
    ap.add_argument('--expect-before', action='store_true')
    ap.add_argument('--phase', choices=['all', 'live', 'cold'], default='all')
    a = ap.parse_args()
    assert os.name == 'nt', 'Windows native driver only'
    engine = a.engine.resolve(strict=True)
    root, evidence = a.runtime_root.absolute(), a.evidence.absolute()
    assert not root.exists() and not evidence.exists(), 'fresh uniquely owned roots required'
    signed = a.feed.read_bytes()
    manifest = updatefeed.verify(signed)
    mirror = urlsplit(manifest['mirrors'][0])
    assert mirror.scheme == 'http' and mirror.hostname == '127.0.0.1' and mirror.port and not mirror.path, 'retained signed loopback mirror required'
    files = {f['path']: f for f in manifest['files'] if f['platform'] in ('all', 'win64')}
    zone = next(p for p in files if p.startswith('ftesurf/maps/zones/local/'))
    mounts = 'ftesurf/fs_addons.txt'
    content = next(p for p in files if p.startswith('ftesurf/gfx/updater_fixture'))
    assert mounts in files
    payload, objects = {}, {}
    for path, entry in files.items():
        candidates = [base / entry['hash'][:2] / entry['hash'] for base in a.objects]
        obj = next((p for p in candidates if p.is_file()), None)
        assert obj and not obj.is_symlink(), 'missing/linked input object: ' + path
        data = obj.read_bytes()
        assert len(data) == entry['size'] and digest(data) == entry['hash'], 'corrupt input object: ' + path
        payload[path] = data
        objects['/objects/' + entry['hash'][:2] + '/' + entry['hash']] = data
    root.mkdir(parents=True)
    evidence.mkdir(parents=True)
    (root / 'OWNER.md').write_text('Synthetic Windows unreadability arms; no keys/install/player files. Evidence: ' + str(evidence) + '\n')
    result = {'engine_sha256': sha(engine.read_bytes()), 'feed_sha256': sha(signed),
              'harness_sha256': sha(Path(__file__).read_bytes()), 'expect_before': a.expect_before,
              'phase': a.phase, 'arms': [], 'retired': []}
    hits = Counter()
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            hits[self.path] += 1
            data = signed if self.path == '/update.json' else objects.get(self.path)
            if data is not None:
                self.send_response(200); self.send_header('Content-Length', str(len(data))); self.end_headers(); self.wfile.write(data)
            else:
                self.send_error(404)
        def log_message(self, *unused):
            pass
    server = thread = None
    old_content = b'previous managed ordinary content\n'
    old_zone = b'previous managed zone\n'
    old_mounts = b'// owned edited mount list\n'
    sentinels = {'ftesurf/ftesurf.cfg': b'cfg_save_auto 0\n// synthetic settings sentinel\n',
                 'ftesurf/data/runs/player-sentinel.rec': b'synthetic recording sentinel\n'}

    def prepare(name, target, mode='old', cold=False, protected_first=False):
        dest = root / name
        dest.mkdir()
        for path, data in payload.items():
            p = dest / path; p.parent.mkdir(parents=True, exist_ok=True); p.write_bytes(data)
        (dest / content).write_bytes(old_content)
        if target == zone: (dest / target).write_bytes(old_zone)
        else: (dest / target).write_bytes(old_mounts)
        for path, data in sentinels.items():
            p = dest / path; p.parent.mkdir(parents=True, exist_ok=True); p.write_bytes(data)
        meta = dest / '.ftesurf-updater'; meta.mkdir()
        (meta / 'consent').write_bytes(b'0\n' if cold else b'1\n')
        ledger = {'version': '0.1.24', 'files': {p: f['hash'] for p, f in files.items()}}
        ledger['files'][content] = digest(old_content)
        ledger['files'][target] = digest((dest / target).read_bytes())
        if mode == 'edited': (dest / target).write_bytes(b'// intervening protected edit\n')
        if mode == 'missing': (dest / target).unlink()
        (meta / 'state.json').write_text(json.dumps(ledger))
        # A pre-existing certificate is a sentinel; refusal must not replace it.
        (meta / 'installed.json').write_bytes(signed)
        if cold:
            pending = meta / 'ingame'; (pending / 'staged').mkdir(parents=True)
            (pending / 'manifest.json').write_bytes(signed)
            rows = [target, content] if protected_first else [content, target]
            for path in rows: (pending / 'staged' / files[path]['hash']).write_bytes(payload[path])
            (pending / 'journal.json').write_text(json.dumps({'attempts': 1, 'version': manifest['version'], 'files': [
                {'p': p, 'h': files[p]['hash'], 's': files[p]['size'], 'x': int(files[p]['exec'])} for p in rows]}))
        return dest, meta, ledger

    def metadata(meta):
        return {p.relative_to(meta).as_posix(): sha(p.read_bytes()) for p in meta.rglob('*') if p.is_file() and p.name != 'install.lock'}

    def guard(dest):
        for path, data in sentinels.items(): assert (dest / path).read_bytes() == data, path

    @contextmanager
    def arm(name, target, **kwargs):
        dest, meta, ledger = prepare(name, target, **kwargs)
        row = {'name': name, 'target': target, 'before_metadata': metadata(meta), 'before_inventory': inventory(dest)}
        result['arms'].append(row)
        try:
            yield dest, meta, ledger, row
            guard(dest)
            # Account for the only authorized managed mutations in each arm;
            # every other signed destination must remain byte-for-byte unchanged.
            changed = {content, target} if name.endswith(('-edited', '-missing')) or (name.startswith('cold-') and a.expect_before) else set()
            for path in files:
                if path not in changed:
                    assert sha((dest / path).read_bytes()) == row['before_inventory'][path]['sha256'], 'unexpected managed mutation: ' + path
            row['after_metadata'] = metadata(meta)
            row['status'] = 'PASS'
            print('PASS', name, flush=True)
        finally:
            # Export must succeed before deletion; restoration failures retain runtime.
            export(dest, evidence / name)
            if row.get('status') == 'PASS':
                shutil.rmtree(dest)
                assert not dest.exists(), 'owned arm retirement failed'
                result['retired'].append(name)

    def cold_run(dest, row, error=None):
        args = [str(engine), '-nohome', '-basedir', str(dest), '-manifest', str(dest / 'default.fmf'),
                '+set', 'cfg_save_auto', '0', '+set', 'cl_idlefps', '0', '+set', 'cl_maxfps', '100',
                '+set', 'con_savehistory', '0', '+set', 'vid_renderer', 'headless',
                '+set', 'update_autocheck', '0', '+set', 'log_name', 'recovery', '+set', 'log_enable', '1',
                '+echo', 'NATIVE_RECOVERY_ACTED', '+quit']
        job = None
        with (dest / 'native-output.log').open('wb') as out:
            p = subprocess.Popen(args, cwd='C:/FTESurf', stdout=out, stderr=subprocess.STDOUT, creationflags=4)
            row['pid'] = p.pid
            try:
                job = owned_job(p)
                resume = ctypes.WinDLL('ntdll').NtResumeProcess; resume.argtypes = [w.HANDLE]; resume.restype = ctypes.c_long
                assert resume(int(p._handle)) == 0
                if error:
                    fatal = owned_error(p, error)
                    (dest / 'fatal.log').write_text(fatal, encoding='utf-8')
                    assert p.returncode != 0
                else:
                    try:
                        p.wait(timeout=30)
                    except subprocess.TimeoutExpired:
                        fatal = owned_error(p, '')
                        (dest / 'unexpected-fatal.log').write_text(fatal, encoding='utf-8')
                        raise AssertionError('unexpected owned cold modal: ' + fatal)
                    assert p.returncode == 0
            finally:
                if job: assert kernel32().CloseHandle(job), ctypes.get_last_error()
                if p.poll() is None: p.terminate(); p.wait(timeout=10)
                row['exit'] = p.returncode
        text = '\n'.join(q.read_text(errors='replace') for q in dest.rglob('*.log'))
        if error:
            assert error in text and 'NATIVE_RECOVERY_ACTED' not in text
        else:
            assert 'NATIVE_RECOVERY_ACTED' in text, 'cold startup actor missing'
        return text

    def live(dest, target, row, expected_count=None, refusal=False, apply=False):
        cfg = dest / 'ftesurf/cfg/test/live.cfg'; cfg.parent.mkdir(parents=True, exist_ok=True)
        cfg.write_text('cfg_save_auto 0\ncl_idlefps 0\ncl_maxfps 100\ncon_savehistory 0\n'
                       'update_autocheck 0\nupdate_allow_insecure 1\n'
                       f'update_manifest_url "http://127.0.0.1:{mirror.port}/update.json"\n'
                       'developer 1\nlog_developer 1\nlog_name live\nlog_enable 1\n'
                       'echo WINDOWS_PLANNER_READY\n')
        args = [str(engine), '-plugin', '-nohome', '-basedir', str(dest), '-manifest', str(dest / 'default.fmf'),
                '+set', 'cfg_save_auto', '0', '+set', 'vid_renderer', 'headless', '+exec', 'cfg/test/live.cfg']
        logpath = dest / 'stdout.log'
        def logs():
            return '\n'.join(p.read_text(errors='replace') for p in dest.rglob('live*.log'))
        def wait_actor(p, actor):
            until = time.monotonic() + 30
            while time.monotonic() < until:
                text = logs()
                if actor in text: return text
                assert p.poll() is None, 'owned client exited before actor: ' + actor
                time.sleep(0.05)
            raise AssertionError('native actor missing: ' + actor + '; see ' + str(dest))
        job = None
        with logpath.open('wb') as out:
            p = subprocess.Popen(args, cwd='C:/FTESurf', stdin=subprocess.PIPE, stdout=out, stderr=subprocess.STDOUT, creationflags=4)
            row['pid'] = p.pid
            try:
                job = owned_job(p)
                resume = ctypes.WinDLL('ntdll').NtResumeProcess; resume.argtypes = [w.HANDLE]; resume.restype = ctypes.c_long
                assert resume(int(p._handle)) == 0
                def send(command):
                    assert len(command.encode()) < 255
                    p.stdin.write((command + '\n').encode()); p.stdin.flush()
                wait_actor(p, 'WINDOWS_PLANNER_READY')
                send('echo WINDOWS_PLANNER_CHECK; update_check force')
                actor = ('cannot read protected update file: ' + target) if refusal else f'update: {expected_count} file'
                wait_actor(p, actor)
                send('update_info; echo WINDOWS_PLANNER_PLANNED')
                planned = wait_actor(p, 'WINDOWS_PLANNER_PLANNED')
                assert ('update state : error' if refusal else 'update state : available') in planned
                row['plan_actor'] = actor
                row['plan_http'] = dict(hits)
                assert hits['/update.json'] == 1 and not any('/objects/' in k for k in hits)
                if apply or refusal:
                    send('update_apply')
                    if refusal: wait_actor(p, 'update: nothing to apply (state error)')
                    else: wait_actor(p, 'update: installed ' + str(expected_count) + ' file')
                send('update_info; echo WINDOWS_PLANNER_DONE; quit')
                p.wait(timeout=30)
                assert p.returncode == 0, ('client exit', p.returncode)
                text = logs()
                assert 'WINDOWS_PLANNER_DONE' in text and 'WINDOWS_PLANNER_CHECK' in text
                row['http'] = dict(hits)
            finally:
                if job:
                    assert kernel32().CloseHandle(job), ctypes.get_last_error()
                if p.poll() is None:
                    p.terminate(); p.wait(timeout=10)
                p.stdin.close()
                row['exit'] = p.returncode

    try:
        if a.phase in ('all', 'live'):
            # Fixed port comes from the unchanged signed mirror. Do not seize a peer port.
            result['busy_port_control'] = busy_port_control()
            server = ExclusiveHTTPServer(('127.0.0.1', mirror.port), Handler)
            thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
            for target, label in [(zone, 'zone'), (mounts, 'mounts')]:
                for kind in ['share', 'acl']:
                    with arm('live-' + label + '-' + kind, target) as (dest, meta, ledger, row):
                        hits.clear()
                        with denied(dest / target, kind, row):
                            live(dest, target, row, expected_count=2, refusal=not a.expect_before)
                        assert metadata(meta) == row['before_metadata'], 'planner changed authoritative metadata'
                        assert (dest / content).read_bytes() == old_content
                        assert (dest / target).read_bytes() == (old_zone if target == zone else old_mounts)
                        assert not (meta / 'ingame/journal.json').exists()
                        assert not list((meta / 'ingame/staged').glob('*'))
                for mode in ['edited', 'missing']:
                    with arm('live-' + label + '-' + mode, target, mode=mode) as (dest, meta, ledger, row):
                        hits.clear()
                        count = 2 if mode == 'missing' else 1
                        live(dest, target, row, expected_count=count, apply=True)
                        assert (dest / content).read_bytes() == payload[content]
                        expected = payload[target] if mode == 'missing' else b'// intervening protected edit\n'
                        assert (dest / target).read_bytes() == expected
                        state = json.loads((meta / 'state.json').read_text())
                        assert state['version'] == manifest['version'] and state['files'][content] == files[content]['hash']
                        assert state['files'][target] == (files[target]['hash'] if mode == 'missing' else ledger['files'][target])
                        assert (meta / 'installed.json').read_bytes() == signed
                        assert not (meta / 'ingame/journal.json').exists() and not list((meta / 'ingame/staged').glob('*'))
                        assert sum(n for p, n in hits.items() if '/objects/' in p) == count
        if a.phase in ('all', 'cold'):
            for target, label in [(zone, 'zone'), (mounts, 'mounts')]:
                for kind in ['share', 'acl']:
                    for first in [False, True]:
                        name = 'cold-' + label + '-' + kind + ('-first' if first else '-later')
                        with arm(name, target, cold=True, protected_first=first) as (dest, meta, ledger, row):
                            with denied(dest / target, kind, row, expect_replacement=a.expect_before and kind == 'acl'):
                                error = ('Unfinished content update' if kind == 'share' else None) if a.expect_before else 'Cannot read protected update file'
                                text = cold_run(dest, row, error)
                            if a.expect_before:
                                assert (dest / content).read_bytes() == payload[content], 'pre-fix earlier content actor did not ACT'
                                if kind == 'acl':
                                    assert (dest / target).read_bytes() == payload[target], 'pre-fix overwrite did not ACT'
                                    assert not (meta / 'ingame/journal.json').exists()
                                else:
                                    assert (dest / target).read_bytes() == (old_zone if target == zone else old_mounts)
                                    pending = json.loads((meta / 'ingame/journal.json').read_text())
                                    assert pending['attempts'] == 2 and [f['p'] for f in pending['files']] == [target]
                                state = json.loads((meta / 'state.json').read_text())
                                assert state['files'][content] == files[content]['hash']
                                assert state['version'] == ('0.1.24' if kind == 'share' else manifest['version'])
                                assert state['files'][target] == (ledger['files'][target] if kind == 'share' else files[target]['hash'])
                            else:
                                assert metadata(meta) == row['before_metadata'], 'cold refusal changed ledger/journal/staging'
                                assert (dest / content).read_bytes() == old_content
                                assert (dest / target).read_bytes() == (old_zone if target == zone else old_mounts)
                            row['native_actor'] = ('late mixed-install fatal/old content mutation' if kind == 'share' else 'startup/old protected overwrite') if a.expect_before else 'fatal protected-file refusal'
        result['status'] = 'PASS'
    except BaseException as error:
        result.update(status='FAIL', error=str(error))
        raise
    finally:
        if server:
            server.shutdown(); server.server_close(); thread.join(timeout=5)
            assert not thread.is_alive(), 'owned HTTP server did not stop'
        (evidence / 'result.json').write_text(json.dumps(result, indent=2) + '\n')


if __name__ == '__main__':
    main()
